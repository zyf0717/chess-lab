import pytest

pytest.importorskip("chess")

import queue
import threading

import chess
from analysis.analysis_engine import annotate_game_worker, classify_wdl_delta
from analysis.stockfish import wdl_expected_score


class DummyWdl:
    def __init__(self, wins: int, draws: int, losses: int) -> None:
        self.wins = wins
        self.draws = draws
        self.losses = losses


class DummyWdlMethod:
    def __init__(self, wins: int, draws: int, losses: int) -> None:
        self._wins = wins
        self._draws = draws
        self._losses = losses

    def wdl(self):
        return self._wins, self._draws, self._losses


def test_wdl_expected_score_from_attributes():
    wdl = DummyWdl(5, 3, 2)
    assert wdl_expected_score(wdl) == 0.65


def test_wdl_expected_score_from_method():
    wdl = DummyWdlMethod(1, 2, 1)
    assert wdl_expected_score(wdl) == 0.5


def test_classify_wdl_delta_thresholds():
    # Best move (no loss)
    assert classify_wdl_delta(0.01) == "Best"
    assert classify_wdl_delta(0.00) == "Best"
    # Excellent move (minimal loss)
    assert classify_wdl_delta(-0.01) == "Excellent"
    assert classify_wdl_delta(-0.019) == "Excellent"
    # Good move (small loss)
    assert classify_wdl_delta(-0.02) == "Good"
    assert classify_wdl_delta(-0.049) == "Good"
    # Inaccuracy
    assert classify_wdl_delta(-0.05) == "?!"
    # Mistake
    assert classify_wdl_delta(-0.10) == "?"
    # Blunder
    assert classify_wdl_delta(-0.20) == "??"


def test_checkmate_annotated_as_ok():
    """Test that checkmate moves are annotated as OK, not as blunders."""
    # Simple position: Fool's Mate
    board = chess.Board()
    moves = [
        chess.Move.from_uci("f2f3"),  # 1. f3
        chess.Move.from_uci("e7e5"),  # 1... e5
        chess.Move.from_uci("g2g4"),  # 2. g4
        chess.Move.from_uci("d8h4"),  # 2... Qh4# (checkmate)
    ]

    stop_event = threading.Event()
    result_queue = queue.Queue()

    # Run annotation worker
    try:
        annotate_game_worker(
            board.fen(),
            moves,
            stop_event,
            result_queue,
            1,
            time_limit=0.1,
            worker_count=1,
            evaluation_metric="cpl",
        )

        # Get results - now returns 6 elements: id, display_annotations, label_annotations, summary, evals, wdl_scores
        result = result_queue.get(timeout=10)
        _, display_annotations, label_annotations, summary, _, _ = result

        # Check that the checkmate move (ply 4) is NOT annotated with an error
        # (checkmate should have no annotation, which means it's not marked as an error)
        assert (
            4 not in display_annotations
        ), f"Checkmate should not have an annotation, but got: {display_annotations.get(4)}"

        # Verify Black has no errors (checkmate move is not counted as a mistake)
        black_counts = summary.get("Black", {})
        assert (
            black_counts.get("??", 0) == 0
        ), f"Black should have no blunders: {summary}"
        assert (
            black_counts.get("?", 0) == 0
        ), f"Black should have no mistakes: {summary}"
        assert (
            black_counts.get("?!", 0) == 0
        ), f"Black should have no inaccuracies: {summary}"
    except Exception as e:
        pytest.fail(f"Test failed with exception: {e}")
