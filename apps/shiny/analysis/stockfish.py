from __future__ import annotations

import os
import platform
import stat
import tarfile
import time
import urllib.request
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import chess
import chess.engine

DEFAULT_URLS = {
    (
        "Linux",
        "x86_64",
    ): "https://github.com/official-stockfish/Stockfish/releases/latest/download/stockfish-ubuntu-x86-64-avx2.tar",
    (
        "Linux",
        "aarch64",
    ): "https://github.com/official-stockfish/Stockfish/releases/latest/download/stockfish-android-armv8.tar",
    (
        "Darwin",
        "x86_64",
    ): "https://github.com/official-stockfish/Stockfish/releases/latest/download/stockfish-macos-x86-64-avx2.tar",
    (
        "Darwin",
        "arm64",
    ): "https://github.com/official-stockfish/Stockfish/releases/latest/download/stockfish-macos-m1-apple-silicon.tar",
    (
        "Windows",
        "AMD64",
    ): "https://github.com/official-stockfish/Stockfish/releases/latest/download/stockfish-windows-x86-64-avx2.zip",
}


def stockfish_dir() -> Path:
    return Path(__file__).resolve().parents[1] / "stockfish"


def _find_binary(search_dir: Path) -> Path | None:
    archive_suffixes = {".zip", ".tar", ".gz", ".bz2", ".xz", ".7z"}
    for candidate in search_dir.rglob("*"):
        if not candidate.is_file():
            continue
        name = candidate.name.lower()
        if any(name.endswith(suffix) for suffix in archive_suffixes):
            continue
        if (
            name == "stockfish"
            or name.startswith("stockfish")
            and not name.endswith(".txt")
        ):
            return candidate
    return None


def _extract_archive(archive: Path, dest: Path) -> None:
    if archive.suffix == ".zip":
        with zipfile.ZipFile(archive, "r") as zf:
            zf.extractall(dest)
        return

    if archive.suffix == ".tar":
        with tarfile.open(archive, "r:*") as tf:
            tf.extractall(dest)
        return

    if archive.suffixes[-2:] in ([".tar", ".gz"], [".tar", ".bz2"], [".tar", ".xz"]):
        with tarfile.open(archive, "r:*") as tf:
            tf.extractall(dest)
        return

    raise RuntimeError(f"Unsupported Stockfish archive format: {archive.name}")


def _download(url: str, dest: Path) -> None:
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0 (compatible; chess-lab/1.0)"},
    )
    with urllib.request.urlopen(request) as response:
        dest.write_bytes(response.read())


def ensure_stockfish_binary() -> Path:
    env_path = os.getenv("STOCKFISH_PATH")
    if env_path:
        path = Path(env_path)
        if path.exists():
            return path

    target_dir = stockfish_dir()
    target_dir.mkdir(parents=True, exist_ok=True)

    existing = _find_binary(target_dir)
    if existing:
        return existing

    url = os.getenv("STOCKFISH_URL")
    if not url:
        system = platform.system()
        machine = platform.machine()
        url = DEFAULT_URLS.get((system, machine))

    if not url:
        raise RuntimeError(
            "No Stockfish binary available for this platform. "
            "Set STOCKFISH_PATH or STOCKFISH_URL."
        )

    archive_name = url.split("/")[-1]
    archive_path = target_dir / archive_name

    try:
        _download(url, archive_path)
    except Exception as exc:
        raise RuntimeError(f"Failed to download Stockfish: {exc}") from exc

    if not zipfile.is_zipfile(archive_path) and not tarfile.is_tarfile(archive_path):
        snippet = ""
        try:
            snippet = archive_path.read_text(errors="ignore").strip().splitlines()[0]
        except (OSError, UnicodeDecodeError, IndexError):
            snippet = ""
        archive_path.unlink(missing_ok=True)
        message = (
            "Downloaded file is not a valid archive. "
            "This usually means the host returned HTML instead of the binary."
        )
        if snippet:
            message += f" First line: {snippet[:120]}"
        raise RuntimeError(message)

    extract_dir = target_dir / "download"
    extract_dir.mkdir(parents=True, exist_ok=True)
    try:
        _extract_archive(archive_path, extract_dir)
    except (zipfile.BadZipFile, tarfile.ReadError, OSError) as exc:
        raise RuntimeError(f"Failed to extract Stockfish archive: {exc}") from exc

    binary = _find_binary(extract_dir)
    if not binary:
        raise RuntimeError("Downloaded Stockfish archive did not contain a binary.")

    final_path = target_dir / binary.name
    binary.replace(final_path)
    final_path.chmod(final_path.stat().st_mode | stat.S_IEXEC)
    return final_path


def format_score(score: chess.engine.PovScore) -> str:
    mate = score.mate()
    if mate is not None:
        return f"Mate in {mate}"

    centipawns = score.score()
    if centipawns is None:
        return "Eval: ?"

    value = centipawns / 100.0
    sign = "+" if value >= 0 else ""
    return f"{sign}{value:.2f}"


def format_pv(board: chess.Board, pv: list[chess.Move], max_plies: int = 16) -> str:
    temp = board.copy()
    parts = []
    for idx, move in enumerate(pv[:max_plies]):
        san = temp.san(move)
        if temp.turn == chess.WHITE:
            parts.append(f"{temp.fullmove_number}. {san}")
        else:
            if idx == 0:
                parts.append(f"{temp.fullmove_number}... {san}")
            else:
                parts.append(san)
        temp.push(move)
    return " ".join(parts)


def score_to_cp(score: chess.engine.PovScore, mate_score: int = 10000) -> int:
    value = score.score(mate_score=mate_score)
    if value is None:
        return 0
    return int(value)


def clamp_score(score_cp: int, threshold: int = 1000) -> int:
    return max(-threshold, min(score_cp, threshold))


def wdl_expected_score(wdl) -> float | None:
    """
    Compute the expected score for White from win/draw/loss (WDL) statistics.

    The input ``wdl`` is expected to be an object representing WDL information.
    It may provide ``wins``, ``draws``, and ``losses`` attributes directly, or a
    ``wdl()`` method returning a tuple ``(wins, draws, losses)``. If possible,
    the statistics are converted to White's point of view via ``wdl.pov(chess.WHITE)``.

    The expected score is calculated using the formula:

        (wins + 0.5 * draws) / total

    where ``total = wins + draws + losses``. If the input is ``None``, if the
    necessary statistics cannot be obtained, or if ``total <= 0``, the function
    returns ``None``.

    Returns:
        float | None: A value between 0.0 and 1.0 representing the expected
        score for White, or ``None`` if it cannot be computed.
    """
    if wdl is None:
        return None
    try:
        wdl = wdl.pov(chess.WHITE)
    except Exception:
        pass
    wins = getattr(wdl, "wins", None)
    draws = getattr(wdl, "draws", None)
    losses = getattr(wdl, "losses", None)
    if wins is None or draws is None or losses is None:
        try:
            wins, draws, losses = wdl.wdl()
        except Exception:
            return None
    total = wins + draws + losses
    if total <= 0:
        return None
    return (wins + 0.5 * draws) / total


class StockfishAnalyzer:
    def __init__(self, path: Path):
        self._engine = chess.engine.SimpleEngine.popen_uci(str(path))

    def analyse(
        self, board: chess.Board, depth: int = 12, time_limit: float = 0.1
    ) -> str:
        limit = chess.engine.Limit(depth=depth, time=time_limit)
        info = self._engine.analyse(board, limit)
        score = info["score"].pov(chess.WHITE)
        return format_score(score)

    def close(self) -> None:
        self._engine.quit()


def stream_analysis(
    board: chess.Board,
    time_limit: float = 10.0,
    depth: int | None = None,
    multipv: int = 3,
    threads: int = 1,
    stop_event=None,
    best_move_board: chess.Board | None = None,
):
    """Yield (delta_cp_white, pv_lines, best_move_uci, prev_pv_lines, done)."""
    path = ensure_stockfish_binary()
    engine = chess.engine.SimpleEngine.popen_uci(str(path))
    try:
        try:
            engine.configure({"Threads": max(1, int(threads))})
        except Exception:
            pass
        if depth is None:
            limit = chess.engine.Limit(time=time_limit)
        else:
            limit = chess.engine.Limit(time=time_limit, depth=depth)

        best_move_uci = None
        prev_cp = None
        prev_lines = None
        if best_move_board is not None:
            try:
                if multipv <= 1:
                    prev_info = engine.analyse(best_move_board, limit)
                    prev_score = prev_info["score"].pov(chess.WHITE)
                    prev_cp = clamp_score(score_to_cp(prev_score))
                    prev_pv = prev_info.get("pv")
                    if prev_pv:
                        prev_lines = [
                            f"{format_score(prev_score)} — "
                            f"{format_pv(best_move_board, prev_pv)}"
                        ]
                        best_move_uci = prev_pv[0].uci()
                else:
                    prev_infos = engine.analyse(best_move_board, limit, multipv=multipv)
                    latest_prev: list[tuple[int, str, int, str | None]] = []
                    for info in prev_infos:
                        score = info["score"].pov(chess.WHITE)
                        line_score = format_score(score)
                        line_pv = format_pv(best_move_board, info["pv"])
                        rank = int(info.get("multipv", 1))
                        first_move = info["pv"][0].uci() if info.get("pv") else None
                        latest_prev.append(
                            (
                                rank,
                                f"{line_score} — {line_pv}",
                                clamp_score(score_to_cp(score)),
                                first_move,
                            )
                        )
                    latest_prev.sort(key=lambda item: item[0])
                    if latest_prev:
                        prev_lines = [line for _, line, _, _ in latest_prev]
                        prev_cp = latest_prev[0][2]
                        best_move_uci = latest_prev[0][3]
            except Exception:
                prev_cp = None
                prev_lines = None

        start = time.monotonic()
        with engine.analysis(board, limit, multipv=multipv) as analysis:
            latest: dict[int, tuple[str, str, str | None]] = {}
            latest_delta = None
            latest_lines: list[str] | None = None
            latest_best = None
            for info in analysis:
                if stop_event is not None and stop_event.is_set():
                    analysis.stop()
                    break
                if "score" in info and "pv" in info:
                    score = info["score"].pov(chess.WHITE)
                    curr_cp = clamp_score(score_to_cp(score))
                    delta_cp = None
                    if prev_cp is not None:
                        delta_cp = curr_cp - prev_cp
                    line_score = format_score(score)
                    line_pv = format_pv(board, info["pv"])
                    rank = int(info.get("multipv", 1))
                    first_move = info["pv"][0].uci() if info["pv"] else None
                    latest[rank] = (line_score, line_pv, first_move)
                    ordered = [
                        f"{line_score} — {line_pv}"
                        for _, (line_score, line_pv, _) in sorted(latest.items())
                    ]
                    latest_delta = delta_cp
                    latest_lines = ordered
                    # Get the best move from the current position (rank 1)
                    if 1 in latest:
                        latest_best = latest[1][2]
                    yield latest_delta, latest_lines, latest_best, prev_lines, False
                if time.monotonic() - start >= time_limit:
                    break
        if stop_event is not None and stop_event.is_set():
            return
        if latest_lines is None:
            latest_lines = []
        yield latest_delta, latest_lines, latest_best, prev_lines, True
    finally:
        engine.quit()


def evaluate_positions(
    board: chess.Board,
    moves: list[chess.Move],
    time_limit: float = 1.0,
    workers: int = 1,
    stop_event=None,
    include_wdl: bool = False,
) -> list[int] | tuple[list[int], list[float]]:
    if stop_event is not None and stop_event.is_set():
        return ([], []) if include_wdl else []

    path = ensure_stockfish_binary()
    workers = max(1, int(workers))
    if workers <= 1:
        engine = chess.engine.SimpleEngine.popen_uci(str(path))
        try:
            if include_wdl:
                try:
                    engine.configure({"UCI_ShowWDL": True})
                except Exception:
                    pass
            limit = chess.engine.Limit(time=time_limit)
            evals: list[int] = []
            wdl_scores: list[float] = []
            work_board = board.copy()
            info = engine.analyse(work_board, limit)
            evals.append(score_to_cp(info["score"].pov(chess.WHITE)))
            if include_wdl:
                wdl_scores.append(wdl_expected_score(info.get("wdl")) or 0.5)
            for move in moves:
                if stop_event is not None and stop_event.is_set():
                    break
                work_board.push(move)
                info = engine.analyse(work_board, limit)
                evals.append(score_to_cp(info["score"].pov(chess.WHITE)))
                if include_wdl:
                    wdl_scores.append(wdl_expected_score(info.get("wdl")) or 0.5)
            return (evals, wdl_scores) if include_wdl else evals
        finally:
            engine.quit()

    work_board = board.copy()
    fen_items: list[tuple[int, str]] = [(0, work_board.fen())]
    for idx, move in enumerate(moves, start=1):
        if stop_event is not None and stop_event.is_set():
            return ([], []) if include_wdl else []
        work_board.push(move)
        fen_items.append((idx, work_board.fen()))

    if not fen_items:
        return ([], []) if include_wdl else []

    workers = min(workers, len(fen_items))
    chunk_size = (len(fen_items) + workers - 1) // workers
    chunks = [
        fen_items[i : i + chunk_size] for i in range(0, len(fen_items), chunk_size)
    ]

    def _analyse_fens(
        fen_batch: list[tuple[int, str]],
    ) -> list[tuple[int, int, float | None]]:
        engine = chess.engine.SimpleEngine.popen_uci(str(path))
        try:
            try:
                engine.configure({"Threads": 1})
            except Exception:
                pass
            if include_wdl:
                try:
                    engine.configure({"UCI_ShowWDL": True})
                except Exception:
                    pass
            limit = chess.engine.Limit(time=time_limit)
            results: list[tuple[int, int, float | None]] = []
            for idx, fen in fen_batch:
                if stop_event is not None and stop_event.is_set():
                    break
                board_obj = chess.Board(fen)
                info = engine.analyse(board_obj, limit)
                wdl_score = wdl_expected_score(info.get("wdl")) if include_wdl else None
                results.append((idx, score_to_cp(info["score"].pov(chess.WHITE)), wdl_score))
            return results
        finally:
            engine.quit()

    results_by_idx: dict[int, int] = {}
    wdl_by_idx: dict[int, float] = {}
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = [executor.submit(_analyse_fens, chunk) for chunk in chunks]
        for future in as_completed(futures):
            if stop_event is not None and stop_event.is_set():
                return ([], []) if include_wdl else []
            for idx, score, wdl_score in future.result():
                results_by_idx[idx] = score
                if include_wdl:
                    wdl_by_idx[idx] = wdl_score if wdl_score is not None else 0.5

    evals = [results_by_idx.get(idx, 0) for idx in range(len(fen_items))]
    if include_wdl:
        wdl_scores = [wdl_by_idx.get(idx, 0.5) for idx in range(len(fen_items))]
        return evals, wdl_scores
    return evals
