from __future__ import annotations

import os
import platform
import stat
import tarfile
import time
import urllib.request
import zipfile
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
    time_limit: float = 5.0,
    depth: int | None = None,
    multipv: int = 3,
    stop_event=None,
):
    path = ensure_stockfish_binary()
    engine = chess.engine.SimpleEngine.popen_uci(str(path))
    try:
        if depth is None:
            limit = chess.engine.Limit(time=time_limit)
        else:
            limit = chess.engine.Limit(time=time_limit, depth=depth)

        start = time.monotonic()
        with engine.analysis(board, limit, multipv=multipv) as analysis:
            latest: dict[int, tuple[str, str]] = {}
            for info in analysis:
                if stop_event is not None and stop_event.is_set():
                    analysis.stop()
                    break
                if "score" in info and "pv" in info:
                    score = info["score"].pov(chess.WHITE)
                    line_score = format_score(score)
                    line_pv = format_pv(board, info["pv"])
                    rank = int(info.get("multipv", 1))
                    latest[rank] = (line_score, line_pv)
                    ordered = [
                        f"{line_score} — {line_pv}"
                        for _, (line_score, line_pv) in sorted(latest.items())
                    ]
                    best = latest.get(1, (line_score, line_pv))[0]
                    yield best, ordered
                if time.monotonic() - start >= time_limit:
                    break
    finally:
        engine.quit()


def evaluate_positions(
    board: chess.Board,
    moves: list[chess.Move],
    time_limit: float = 1.0,
    stop_event=None,
) -> list[int]:
    path = ensure_stockfish_binary()
    engine = chess.engine.SimpleEngine.popen_uci(str(path))
    try:
        limit = chess.engine.Limit(time=time_limit)
        evals: list[int] = []
        work_board = board.copy()
        info = engine.analyse(work_board, limit)
        evals.append(score_to_cp(info["score"].pov(chess.WHITE)))
        for move in moves:
            if stop_event is not None and stop_event.is_set():
                break
            work_board.push(move)
            info = engine.analyse(work_board, limit)
            evals.append(score_to_cp(info["score"].pov(chess.WHITE)))
        return evals
    finally:
        engine.quit()
