from pathlib import Path
import sys

import pytest

pytest.importorskip("chess")

ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT))

from analysis.analysis_engine import classify_wdl_delta  # noqa: E402
from analysis.stockfish import wdl_expected_score  # noqa: E402


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
    assert classify_wdl_delta(0.01) == ""
    assert classify_wdl_delta(-0.049) == ""
    assert classify_wdl_delta(-0.05) == "?!"
    assert classify_wdl_delta(-0.10) == "?"
    assert classify_wdl_delta(-0.20) == "??"
