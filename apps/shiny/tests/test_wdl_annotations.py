import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    import chess  # noqa: F401
    HAS_CHESS = True
except ImportError:
    HAS_CHESS = False

if HAS_CHESS:
    from analysis.analysis_engine import classify_wdl_delta, summarize_annotations
    from analysis.stockfish import score_to_wdl_expectation
else:
    classify_wdl_delta = None
    summarize_annotations = None
    score_to_wdl_expectation = None


class DummyWDL:
    def __init__(self, wins: int, draws: int, losses: int) -> None:
        self.wins = wins
        self.draws = draws
        self.losses = losses


class DummyScore:
    def __init__(self, wins: int, draws: int, losses: int) -> None:
        self._wdl = DummyWDL(wins, draws, losses)

    def wdl(self):
        return self._wdl


@pytest.mark.skipif(not HAS_CHESS, reason="python-chess not available")
def test_classify_wdl_delta_thresholds():
    assert classify_wdl_delta(-0.01) == ""
    assert classify_wdl_delta(-0.05) == "?!"
    assert classify_wdl_delta(-0.10) == "?"
    assert classify_wdl_delta(-0.20) == "??"
    assert classify_wdl_delta(-0.50) == "??"


@pytest.mark.skipif(not HAS_CHESS, reason="python-chess not available")
def test_summarize_annotations_sets_metric_meta():
    annotations = {1: "?!", 2: "?", 3: ""}
    metric_by_ply = {1: 0.05, 2: 0.12, 3: 0.0}
    summary = summarize_annotations(annotations, metric_by_ply, 3, metric_name="wdl")
    assert summary["meta"]["metric"] == "wdl"
    assert summary["White"]["avg_metric"] == 0.05
    assert summary["Black"]["avg_metric"] == 0.12


@pytest.mark.skipif(not HAS_CHESS, reason="python-chess not available")
def test_score_to_wdl_expectation():
    score = DummyScore(wins=50, draws=10, losses=40)
    expectation = score_to_wdl_expectation(score)
    assert expectation == (50 + 0.5 * 10) / 100
