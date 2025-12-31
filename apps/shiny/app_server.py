from __future__ import annotations

import io

import chess
import chess.pgn
import chess.svg
from shiny import reactive, render, ui
from shinyswatch import theme_picker_server

BOARD_SIZE = 480


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


def move_rows(sans: list[str]) -> list[tuple[int, str, str]]:
    rows = []
    for idx in range(0, len(sans), 2):
        move_no = idx // 2 + 1
        white = sans[idx]
        black = sans[idx + 1] if idx + 1 < len(sans) else ""
        rows.append((move_no, white, black))
    return rows


def server(input, output, session):
    theme_picker_server()

    game_val = reactive.Value(None)
    moves_val = reactive.Value([])
    sans_val = reactive.Value([])
    ply_val = reactive.Value(0)

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
            game_val.set(None)
            moves_val.set([])
            sans_val.set([])
            ply_val.set(0)
            return

        try:
            game, moves, sans = parse_pgn(pgn_text)
        except ValueError as e:
            game_val.set(None)
            moves_val.set([])
            sans_val.set([])
            ply_val.set(0)
            return

        game_val.set(game)
        moves_val.set(moves)
        sans_val.set(sans)
        ply_val.set(0)

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

    @reactive.Effect
    @reactive.event(input.move_cell)
    def _jump_to_selected_cell():
        payload = input.move_cell()
        if not payload or not isinstance(payload, dict):
            return
        ply = payload.get("ply")
        try:
            ply = int(ply)
        except (TypeError, ValueError):
            return

        total = len(moves_val())
        ply = max(0, min(ply, total))
        if ply != ply_val():
            ply_val.set(ply)

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
    @render.ui
    def move_list():
        sans = sans_val()
        if not sans:
            return ui.p("No moves loaded.", class_="text-muted")

        rows = move_rows(sans)
        current_ply = ply_val()
        table_rows = []

        for row_index, (move_no, white, black) in enumerate(rows):
            white_ply = row_index * 2 + 1
            black_ply = row_index * 2 + 2

            white_attrs = {"data-ply": str(white_ply)}
            if white_ply == current_ply:
                white_attrs["class"] = "is-selected"

            if black:
                black_attrs = {"data-ply": str(black_ply)}
                if black_ply == current_ply:
                    black_attrs["class"] = "is-selected"
                black_cell = ui.tags.td(black, **black_attrs)
            else:
                black_cell = ui.tags.td("")

            table_rows.append(
                ui.tags.tr(
                    ui.tags.td(str(move_no)),
                    ui.tags.td(white, **white_attrs),
                    black_cell,
                )
            )

        return ui.tags.table(
            {"class": "table table-sm move-table"},
            ui.tags.thead(
                ui.tags.tr(
                    ui.tags.th("#"),
                    ui.tags.th("White"),
                    ui.tags.th("Black"),
                )
            ),
            ui.tags.tbody(*table_rows),
        )
