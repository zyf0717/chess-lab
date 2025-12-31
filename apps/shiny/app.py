from __future__ import annotations

import io

import chess
import chess.pgn
import chess.svg
from shiny import App, reactive, render, ui

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


def move_rows(sans: list[str]) -> list[tuple[int, str, str]]:
    rows = []
    for idx in range(0, len(sans), 2):
        move_no = idx // 2 + 1
        white = sans[idx]
        black = sans[idx + 1] if idx + 1 < len(sans) else ""
        rows.append((move_no, white, black))
    return rows


app_ui = ui.page_fluid(
    ui.tags.style(
        """
        body {
            font-family: "Garamond", "Palatino Linotype", "Book Antiqua", serif;
            background: linear-gradient(135deg, #f6efe4, #e6d9c7);
            color: #1f1c17;
        }

        .section {
            background: rgba(255, 255, 255, 0.9);
            border: 1px solid rgba(35, 26, 18, 0.15);
            border-radius: 14px;
            padding: 1rem;
            box-shadow: 0 18px 40px rgba(28, 20, 12, 0.12);
        }

        .section h3 {
            margin-top: 0;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            font-size: 0.95rem;
        }

        .board-frame {
            display: grid;
            place-items: center;
            min-height: 420px;
        }

        .controls {
            display: grid;
            gap: 0.6rem;
        }

        .nav-row {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 0.5rem;
        }

        .moves-table {
            width: 100%;
            border-collapse: collapse;
            font-size: 0.95rem;
        }

        .moves-table th,
        .moves-table td {
            padding: 0.25rem 0.35rem;
            text-align: left;
        }

        .moves-table thead {
            color: #6b6256;
            border-bottom: 1px solid rgba(35, 26, 18, 0.15);
        }

        .status {
            color: #6b6256;
            font-size: 0.95rem;
            margin-top: 0.5rem;
        }
        """
    ),
    ui.h2("Chess Lab"),
    ui.row(
        ui.column(
            3,
            ui.div(
                {"class": "section controls"},
                ui.h3("PGN Input"),
                ui.input_file("pgn_upload", "Upload PGN", accept=[".pgn", ".txt"]),
                ui.input_text_area(
                    "pgn_text",
                    "Or paste PGN",
                    placeholder="Paste PGN here...",
                    rows=8,
                ),
                ui.input_action_button("analyze", "Analyze"),
                ui.div(
                    {"class": "nav-row"},
                    ui.input_action_button("prev_move", "Back"),
                    ui.input_action_button("next_move", "Forward"),
                ),
                ui.output_text("status_line"),
            ),
        ),
        ui.column(
            6,
            ui.div(
                {"class": "section board-frame"},
                ui.output_ui("board_view"),
            ),
        ),
        ui.column(
            3,
            ui.div(
                {"class": "section"},
                ui.h3("Moves"),
                ui.output_ui("move_list"),
            ),
        ),
    ),
)


def server(input, output, session):
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
    @render.ui
    def move_list():
        sans = sans_val()
        if not sans:
            return ui.p("No moves loaded.", class_="status")

        rows = move_rows(sans)
        return ui.tags.table(
            {"class": "moves-table"},
            ui.tags.thead(
                ui.tags.tr(
                    ui.tags.th("#"),
                    ui.tags.th("White"),
                    ui.tags.th("Black"),
                )
            ),
            ui.tags.tbody(
                *[
                    ui.tags.tr(
                        ui.tags.td(str(move_no)),
                        ui.tags.td(white),
                        ui.tags.td(black),
                    )
                    for move_no, white, black in rows
                ]
            ),
        )


app = App(app_ui, server)
