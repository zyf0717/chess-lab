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
    assert line == "Move: 1. e4 ?! (120)"
