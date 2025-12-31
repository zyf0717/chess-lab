from __future__ import annotations

import os
import platform
import stat
import tarfile
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
