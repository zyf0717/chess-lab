from contextlib import nullcontext
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
