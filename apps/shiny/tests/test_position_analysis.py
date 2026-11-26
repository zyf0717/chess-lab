from threading import Event
from unittest.mock import Mock

import chess
import pytest

from analysis import PositionAnalysisUpdate, analyze_position, position


@pytest.mark.parametrize(
    ("moves", "white_delta"),
    [("e4", -40), ("e4 e5", 40)],
)
def test_position_analysis_reports_loss_for_the_last_mover(
    monkeypatch, moves, white_delta
):
    board = chess.Board()
    for move in moves.split():
        board.push_san(move)
    previous_board = board.copy()
    previous_board.pop()
    latest = (["current PV"], "g1f3", ["previous PV"], 0.55, 0.60)

    def engine_updates(*args, **kwargs):
        yield None, *latest, False
        yield white_delta, *latest, False
        yield -white_delta, *latest, True

    stream_analysis = Mock(side_effect=engine_updates)
    monkeypatch.setattr(position, "stream_analysis", stream_analysis)

    updates = list(
        analyze_position(board, previous_board, time_limit=0.3, multipv=2, threads=1)
    )

    stream_analysis.assert_called_once_with(
        board,
        time_limit=0.3,
        multipv=2,
        threads=1,
        stop_event=None,
        best_move_board=previous_board,
    )
    assert [update.centipawn_loss for update in updates] == [None, 40, 0]
    assert [update.done for update in updates] == [False, False, True]
    assert updates[-1] == PositionAnalysisUpdate(0, *latest, True)


def test_position_analysis_cancellation_closes_the_engine_stream(monkeypatch):
    stop_event = Event()
    closed = Mock()

    def engine_updates(*args, **kwargs):
        try:
            yield None, [], None, None, None, None, False
            yield None, [], None, None, None, None, True
        finally:
            closed()

    monkeypatch.setattr(position, "stream_analysis", engine_updates)
    updates = analyze_position(
        chess.Board(), time_limit=0.3, multipv=1, threads=1, stop_event=stop_event
    )

    assert next(updates).done is False
    stop_event.set()
    assert list(updates) == []
    closed.assert_called_once_with()


def test_position_analysis_propagates_engine_errors(monkeypatch):
    monkeypatch.setattr(
        position, "stream_analysis", Mock(side_effect=OSError("engine exited"))
    )

    with pytest.raises(OSError, match="engine exited"):
        next(analyze_position(chess.Board(), time_limit=0.3, multipv=1, threads=1))
