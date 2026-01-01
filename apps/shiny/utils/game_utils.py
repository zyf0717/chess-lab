"""Utilities for parsing and managing chess games."""

from __future__ import annotations

import io
from datetime import datetime, timedelta

import chess
import chess.pgn


def parse_pgn(pgn_text: str):
    """Parse PGN text and return game, moves, and SAN notation.

    Args:
        pgn_text: PGN format game text

    Returns:
        Tuple of (game, moves, sans)

    Raises:
        ValueError: If no valid game found in PGN
    """
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
    """Convert SAN list to display rows with move numbers.

    Args:
        sans: List of moves in standard algebraic notation

    Returns:
        List of tuples (move_number, white_move, black_move)
    """
    rows = []
    for idx in range(0, len(sans), 2):
        move_no = idx // 2 + 1
        white = sans[idx]
        black = sans[idx + 1] if idx + 1 < len(sans) else ""
        rows.append((move_no, white, black))
    return rows


def parse_date(value: str | None) -> datetime.date | None:
    """Parse PGN date field."""
    if not value or "?" in value:
        return None
    try:
        return datetime.strptime(value, "%Y.%m.%d").date()
    except ValueError:
        return None


def parse_time(value: str | None) -> datetime.time | None:
    """Parse PGN time field."""
    if not value or "?" in value:
        return None
    for fmt in ("%H:%M:%S", "%H:%M"):
        try:
            return datetime.strptime(value, fmt).time()
        except ValueError:
            continue
    return None


def parse_datetime(date_value: str | None, time_value: str | None) -> datetime | None:
    """Combine PGN date and time fields into datetime."""
    date_part = parse_date(date_value)
    time_part = parse_time(time_value)
    if date_part and time_part:
        return datetime.combine(date_part, time_part)
    return None


def format_datetime(value: datetime | None) -> str:
    """Format datetime for display."""
    if value is None:
        return "Unknown"
    return value.strftime("%Y-%m-%d %H:%M:%S")


def format_duration(start: datetime | None, end: datetime | None) -> str:
    """Calculate and format game duration."""
    if start is None or end is None:
        return "Unknown"
    delta = end - start
    if delta.total_seconds() < 0:
        delta += timedelta(days=1)
    seconds = int(delta.total_seconds())
    hours, remainder = divmod(seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


def extract_game_info(game: chess.pgn.Game | None) -> dict[str, str]:
    """Extract game metadata from PGN headers.

    Args:
        game: Chess game object or None

    Returns:
        Dictionary with game info fields
    """
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

    return {
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
    """Get board position at a specific ply.

    Args:
        game: Chess game object
        moves: List of moves
        ply: Position index (0 = starting position)

    Returns:
        Board at the specified ply
    """
    if game is None:
        board = chess.Board()
    else:
        board = game.board()
        for move in moves[:ply]:
            board.push(move)
    return board
