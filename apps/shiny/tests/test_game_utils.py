import pytest

pytest.importorskip("chess")

from game_utils import board_at_ply, move_rows, parse_pgn


def test_move_rows_groups_sans():
    rows = move_rows(["e4", "e5", "Nf3"])
    assert rows == [(1, "e4", "e5"), (2, "Nf3", "")]


def test_parse_pgn_and_board_at_ply():
    pgn = """
[Event "Test"]
[Site "?"]
[Date "2024.01.01"]
[Round "1"]
[White "White"]
[Black "Black"]
[Result "*"]

1. e4 e5 2. Nf3 Nc6 *
"""
    game, moves, sans = parse_pgn(pgn)
    assert len(moves) == 4
    assert sans[:2] == ["e4", "e5"]

    board = board_at_ply(game, moves, 2)
    assert board.fullmove_number == 2
