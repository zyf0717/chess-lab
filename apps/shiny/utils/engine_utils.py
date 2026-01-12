"""Engine helpers for play mode."""

from __future__ import annotations

import chess
from analysis import stream_analysis


def best_move_uci(
    board: chess.Board,
    think_time: float,
    threads: int,
    multipv: int = 3,
    elo: int | None = None,
    depth: int | None = None,
) -> str | None:
    """Return the best move UCI string for the given board."""
    best_move = None
    for _, _, best_move_uci, _, _, _, done in stream_analysis(
        board,
        time_limit=think_time,
        depth=depth,
        elo=elo,
        multipv=multipv,
        threads=threads,
    ):
        if best_move_uci:
            best_move = best_move_uci
        if done:
            break
    return best_move
