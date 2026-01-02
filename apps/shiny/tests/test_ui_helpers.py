import pytest

pytest.importorskip("shiny")

from ui_helpers import extract_first_pv_move, format_eval_line, normalize_san


def test_normalize_san_strips_checks():
    assert normalize_san("Qh5+") == "Qh5"
    assert normalize_san("Qh7#") == "Qh7"


def test_extract_first_pv_move_handles_prefixes():
    assert extract_first_pv_move("1. e4 e5") == "e4"
    assert extract_first_pv_move("1... c5") == "c5"
    assert extract_first_pv_move("Nf3 d6") == "Nf3"


def test_format_eval_line_uses_annotation():
    line = format_eval_line(
        "CPL: 120",
        1,
        ["e4"],
        {1: "?! (120)"},
        lambda value: "??",
    )
    assert line == "1. e4 | ?! | Eval: -- | CPL: 120 | ES: --"


def test_format_eval_line_with_pv():
    # Test with PV lines that include eval
    line = format_eval_line(
        "CPL: 50",
        2,
        ["e4", "e5"],
        {},
        lambda value: "",
        pv_lines=["-0.10 — Nf3 Nc6 Bb5", "+0.25 — d4 exd4 Qxd4"],
        wdl_score=0.48,
    )
    assert line == "1... e5 | OK | Eval: -0.10 | CPL: 50 | ES: 0.48"


def test_format_eval_line_checkmate_annotation():
    line = format_eval_line(
        "CPL: --",
        4,
        ["f3", "e5", "g4", "Qh4#"],
        {4: "OK"},
        lambda value: "??",
    )
    assert line == "2... Qh4# | OK | Eval: -- | CPL: -- | ES: --"


def test_format_eval_line_with_mate_score():
    # Test with mate score in PV
    line = format_eval_line(
        "CPL: --",
        2,
        ["f3", "e5"],
        {},
        lambda value: "",
        pv_lines=["Mate in 2 — Qh4# Kf1"],
        wdl_score=1.0,
    )
    assert line == "1... e5 | OK | Eval: Mate in 2 | CPL: -- | ES: 1.00"
