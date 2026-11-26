"""Streaming evaluation of a single chess position."""

from __future__ import annotations

from collections.abc import Generator
from contextlib import closing
from dataclasses import dataclass
from threading import Event

import chess

from .stockfish import stream_analysis


@dataclass(frozen=True)
class PositionAnalysisUpdate:
    centipawn_loss: int | None
    pv_lines: list[str]
    best_move_uci: str | None
    previous_pv_lines: list[str] | None
    white_expected_score: float | None
    previous_white_expected_score: float | None
    done: bool


def analyze_position(
    board: chess.Board,
    previous_board: chess.Board | None = None,
    *,
    time_limit: float,
    multipv: int,
    threads: int,
    stop_event: Event | None = None,
) -> Generator[PositionAnalysisUpdate, None, None]:
    """Yield updates and a final snapshot, with loss measured for the last mover.

    Pass the preceding position to compute loss. The time limit applies to each
    engine search. Both boards retain their move history.

    Cancellation ends the stream without a final snapshot. Engine errors propagate
    to the caller. Close the generator if you stop consuming it early.
    """
    if stop_event is not None and stop_event.is_set():
        return

    mover_is_white = board.turn == chess.BLACK
    engine_updates = stream_analysis(
        board,
        time_limit=time_limit,
        multipv=multipv,
        threads=threads,
        stop_event=stop_event,
        best_move_board=previous_board,
    )
    with closing(engine_updates):
        for (
            delta_cp,
            lines,
            best_move,
            previous_lines,
            wdl,
            previous_wdl,
            done,
        ) in engine_updates:
            if stop_event is not None and stop_event.is_set():
                return

            loss = None
            if delta_cp is not None:
                mover_delta = delta_cp if mover_is_white else -delta_cp
                loss = max(0, -mover_delta)

            yield PositionAnalysisUpdate(
                centipawn_loss=loss,
                pv_lines=lines,
                best_move_uci=best_move,
                previous_pv_lines=previous_lines,
                white_expected_score=wdl,
                previous_white_expected_score=previous_wdl,
                done=done,
            )
