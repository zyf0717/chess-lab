from contextlib import nullcontext
from threading import Event
from unittest.mock import Mock

import chess
import chess.engine

from analysis import stockfish


def test_stream_delta_stays_with_the_top_pv(monkeypatch):
    board = chess.Board()
    board.push_san("e4")
    engine = Mock()
    engine.analyse.return_value = [
        {
            "score": chess.engine.PovScore(chess.engine.Cp(10), chess.WHITE),
            "pv": [chess.Move.from_uci("e2e4")],
            "multipv": 1,
        },
    ]
    engine.analysis.return_value = nullcontext(
        [
            {
                "score": chess.engine.PovScore(chess.engine.Cp(15), chess.WHITE),
                "pv": [chess.Move.from_uci("c7c5")],
                "multipv": 1,
            },
            {
                "score": chess.engine.PovScore(chess.engine.Cp(80), chess.WHITE),
                "pv": [chess.Move.from_uci("e7e5")],
                "multipv": 2,
            },
        ]
    )
    monkeypatch.setattr(stockfish, "ensure_stockfish_binary", lambda: "stockfish")
    monkeypatch.setattr(chess.engine.SimpleEngine, "popen_uci", lambda _: engine)

    frames = list(
        stockfish.stream_analysis(board, multipv=2, best_move_board=board.root())
    )

    assert [frame[0] for frame in frames] == [5, 5, 5]
    assert frames[-1][1] == ["+0.15 — 1... c5", "+0.80 — 1... e5"]
    assert frames[-1][2] == "c7c5"
    assert frames[-1][-1] is True


def test_stream_skips_current_search_when_cancelled_during_previous_search(monkeypatch):
    board = chess.Board()
    board.push_san("e4")
    stop_event = Event()
    engine = Mock()

    def cancel_previous_search(*args, **kwargs):
        stop_event.set()
        return []

    engine.analyse.side_effect = cancel_previous_search
    monkeypatch.setattr(stockfish, "ensure_stockfish_binary", lambda: "stockfish")
    monkeypatch.setattr(chess.engine.SimpleEngine, "popen_uci", lambda _: engine)

    updates = stockfish.stream_analysis(
        board, stop_event=stop_event, best_move_board=board.root()
    )
    assert list(updates) == []
    engine.analysis.assert_not_called()
    engine.quit.assert_called_once_with()
