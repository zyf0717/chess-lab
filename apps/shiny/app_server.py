from __future__ import annotations

import io

import chess
import chess.pgn
import chess.svg
import pandas as pd
from shiny import reactive, render, ui
from shinyswatch import theme_picker_server

BOARD_SIZE = 360


def parse_pgn(pgn_text: str):
    game = chess.pgn.read_game(io.StringIO(pgn_text))
    if game is None:
        raise ValueError("No game found in PGN input.")

    board = game.board()
    moves = []
    sans = []
    for move in game.mainline_moves():
        sans.append(board.san(move))
        moves.append(move)
        board.push(move)

    return game, moves, sans


def move_rows(sans: list[str]) -> list[tuple[str, str]]:
    rows = []
    for idx in range(0, len(sans), 2):
        move_no = idx // 2 + 1
        white = f"{move_no}. {sans[idx]}"
        black = sans[idx + 1] if idx + 1 < len(sans) else ""
        rows.append((white, black))
    return rows


def server(input, output, session):
    theme_picker_server()

    game_val = reactive.Value(None)
    moves_val = reactive.Value([])
    sans_val = reactive.Value([])
    ply_val = reactive.Value(0)
    status_val = reactive.Value("Upload or paste PGN, then analyze.")

    @reactive.Effect
    @reactive.event(input.analyze)
    def _analyze():
        pgn_text = ""
        upload = input.pgn_upload()
        if upload:
            path = upload[0]["datapath"]
            with open(path, "r", encoding="utf-8") as handle:
                pgn_text = handle.read()

        if not pgn_text.strip():
            pgn_text = input.pgn_text() or ""

        if not pgn_text.strip():
            status_val.set("Please provide PGN text or upload a PGN file.")
            game_val.set(None)
            moves_val.set([])
            sans_val.set([])
            ply_val.set(0)
            return

        try:
            game, moves, sans = parse_pgn(pgn_text)
        except ValueError as exc:
            status_val.set(str(exc))
            game_val.set(None)
            moves_val.set([])
            sans_val.set([])
            ply_val.set(0)
            return

        game_val.set(game)
        moves_val.set(moves)
        sans_val.set(sans)
        ply_val.set(0)
        status_val.set(f"Loaded {len(moves)} moves.")

    @reactive.Effect
    @reactive.event(input.prev_move)
    def _prev_move():
        ply = ply_val()
        if ply > 0:
            ply_val.set(ply - 1)

    @reactive.Effect
    @reactive.event(input.next_move)
    def _next_move():
        ply = ply_val()
        moves = moves_val()
        if ply < len(moves):
            ply_val.set(ply + 1)

    @reactive.Effect
    @reactive.event(input.first_move)
    def _first_move():
        ply_val.set(0)

    @reactive.Effect
    @reactive.event(input.last_move)
    def _last_move():
        ply_val.set(len(moves_val()))

    @output
    @render.text
    def status_line():
        moves = moves_val()
        ply = ply_val()
        if moves:
            return f"Move {ply} of {len(moves)}"
        return status_val()

    @output
    @render.ui
    def board_view():
        game = game_val()
        moves = moves_val()
        ply = ply_val()
        if game is None:
            board = chess.Board()
        else:
            board = game.board()
            for move in moves[:ply]:
                board.push(move)

        svg = chess.svg.board(board=board, size=BOARD_SIZE)
        return ui.HTML(svg)

    @output
    @render.data_frame
    def move_list():
        sans = sans_val()
        if not sans:
            empty = pd.DataFrame(columns=["White", "Black"])
            return render.DataGrid(empty)

        rows = move_rows(sans)
        data = pd.DataFrame(rows, columns=["White", "Black"])
        return render.DataGrid(data)
