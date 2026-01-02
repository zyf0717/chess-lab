"""Utilities for parsing and managing chess games."""

from __future__ import annotations

import io
import re
from datetime import datetime, timedelta

import chess
import chess.pgn


def parse_pgn(pgn_text: str):
    """Parse PGN text into a game and SAN move list."""
    game = chess.pgn.read_game(io.StringIO(pgn_text))
    if game is None:
        raise ValueError("No game found in PGN input.")

    board = game.board()
    moves = []
    sans = []
    for move in game.mainline_moves():
        sans.append(board.san(move))
        moves.append(move)
        board.push(move)

    return game, moves, sans


def move_rows(sans: list[str]) -> list[tuple[int, str, str]]:
    """Group SAN moves into numbered rows."""
    rows = []
    for idx in range(0, len(sans), 2):
        move_no = idx // 2 + 1
        white = sans[idx]
        black = sans[idx + 1] if idx + 1 < len(sans) else ""
        rows.append((move_no, white, black))
    return rows


def parse_date(value: str | None) -> datetime.date | None:
    """Parse a date string with flexible separators."""
    if not value or "?" in value:
        return None
    parts = [p for p in re.split(r"\D+", value.strip()) if p]
    if len(parts) == 1 and len(parts[0]) == 8:
        parts = [parts[0][:4], parts[0][4:6], parts[0][6:]]
    if len(parts) != 3:
        return None
    if len(parts[0]) == 4:
        year, month, day = parts
    elif len(parts[2]) == 4:
        year, month, day = parts[2], parts[1], parts[0]
    else:
        year, month, day = parts
    try:
        return datetime(int(year), int(month), int(day)).date()
    except ValueError:
        return None


def parse_time(value: str | None) -> datetime.time | None:
    """Parse a PGN time string."""
    if not value or "?" in value:
        return None
    for fmt in ("%H:%M:%S", "%H:%M"):
        try:
            return datetime.strptime(value, fmt).time()
        except ValueError:
            continue
    return None


def parse_datetime(date_value: str | None, time_value: str | None) -> datetime | None:
    """Combine PGN date and time."""
    date_part = parse_date(date_value)
    time_part = parse_time(time_value)
    if date_part and time_part:
        return datetime.combine(date_part, time_part)
    return None


def format_datetime(value: datetime | None) -> str:
    """Format a datetime for display."""
    if value is None:
        return "Unknown"
    return value.strftime("%Y-%m-%d %H:%M:%S")


def format_date(value: datetime.date | None) -> str:
    """Format a date for display."""
    if value is None:
        return "Unknown"
    return value.strftime("%Y-%m-%d")


def format_duration(start: datetime | None, end: datetime | None) -> str:
    """Format the duration between timestamps."""
    if start is None or end is None:
        return "Unknown"
    delta = end - start
    if delta.total_seconds() < 0:
        delta += timedelta(days=1)
    seconds = int(delta.total_seconds())
    hours, remainder = divmod(seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


def extract_game_info(game: chess.pgn.Game | None) -> dict[str, str | bool]:
    """Extract PGN headers into display strings."""
    if game is None:
        return {
            "start": "Unknown",
            "end": "Unknown",
            "duration": "Unknown",
            "white": "Unknown",
            "black": "Unknown",
            "white_elo": "Unknown",
            "black_elo": "Unknown",
        }

    headers = game.headers
    start_dt = parse_datetime(
        headers.get("UTCDate") or headers.get("Date"),
        headers.get("UTCTime") or headers.get("Time"),
    )
    end_dt = parse_datetime(
        headers.get("EndDate") or headers.get("UTCDate") or headers.get("Date"),
        headers.get("EndTime"),
    )
    date_fallback = format_date(parse_date(headers.get("Date")))

    if start_dt is None or end_dt is None:
        return {
            "date_only": True,
            "date": date_fallback,
            "white": headers.get("White", "Unknown"),
            "black": headers.get("Black", "Unknown"),
            "white_elo": headers.get("WhiteElo", "Unknown"),
            "black_elo": headers.get("BlackElo", "Unknown"),
        }

    return {
        "date_only": False,
        "start": format_datetime(start_dt),
        "end": format_datetime(end_dt),
        "duration": format_duration(start_dt, end_dt),
        "white": headers.get("White", "Unknown"),
        "black": headers.get("Black", "Unknown"),
        "white_elo": headers.get("WhiteElo", "Unknown"),
        "black_elo": headers.get("BlackElo", "Unknown"),
    }


def board_at_ply(
    game: chess.pgn.Game | None, moves: list[chess.Move], ply: int
) -> chess.Board:
    """Return the board at a given ply."""
    if game is None:
        board = chess.Board()
    else:
        board = game.board()
        for move in moves[:ply]:
            board.push(move)
    return board
