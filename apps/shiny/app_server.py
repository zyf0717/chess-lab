from __future__ import annotations

import io
import queue
import threading

import chess
import chess.pgn
import chess.svg
from analysis.stockfish import stream_analysis
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
    eval_val = reactive.Value("Eval: --")
    pv_val = reactive.Value([])
    analysis_ready = reactive.Value(False)
    analysis_queue: queue.Queue[tuple[int, str]] = queue.Queue()
    analysis_thread: threading.Thread | None = None
    analysis_stop: threading.Event | None = None
    analysis_id = 0
    last_analysis_key: tuple[str, int, float] | None = None

    def _shutdown_analysis() -> None:
        if analysis_stop is not None:
            analysis_stop.set()
        if analysis_thread is not None and analysis_thread.is_alive():
            analysis_thread.join(timeout=1.0)

    session.on_ended(_shutdown_analysis)

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
            analysis_ready.set(False)
            eval_val.set("Eval: --")
            pv_val.set([])
            return

        try:
            game, moves, sans = parse_pgn(pgn_text)
        except ValueError as e:
            game_val.set(None)
            moves_val.set([])
            sans_val.set([])
            ply_val.set(0)
            analysis_ready.set(False)
            eval_val.set("Eval: --")
            pv_val.set([])
            return

        game_val.set(game)
        moves_val.set(moves)
        sans_val.set(sans)
        ply_val.set(0)
        analysis_ready.set(True)

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

    def _current_board() -> chess.Board:
        game = game_val()
        moves = moves_val()
        ply = ply_val()
        if game is None:
            board = chess.Board()
        else:
            board = game.board()
            for move in moves[:ply]:
                board.push(move)
        return board

    def _start_streaming_eval(board: chess.Board) -> None:
        nonlocal analysis_id, analysis_stop, analysis_queue, analysis_thread, last_analysis_key
        try:
            multipv = int(input.multipv())
        except (TypeError, ValueError):
            multipv = 3
        multipv = max(1, min(multipv, 8))
        try:
            think_time = float(input.think_time())
        except (TypeError, ValueError):
            think_time = 5.0
        think_time = max(1.0, min(think_time, 60.0))
        fen = board.fen()
        analysis_key = (fen, multipv, think_time)
        if analysis_key == last_analysis_key:
            return

        last_analysis_key = analysis_key
        analysis_id += 1
        current_id = analysis_id

        if analysis_stop is not None:
            analysis_stop.set()
        analysis_stop = threading.Event()
        local_queue: queue.Queue[tuple[int, str]] = queue.Queue()
        analysis_queue = local_queue

        eval_val.set("Eval: …")
        pv_val.set([])

        def worker(fen_str: str, stop_event: threading.Event, out_queue: queue.Queue):
            try:
                board_obj = chess.Board(fen_str)
                for score, lines in stream_analysis(
                    board_obj,
                    time_limit=think_time,
                    multipv=multipv,
                    stop_event=stop_event,
                ):
                    if stop_event.is_set():
                        break
                    out_queue.put((current_id, f"Eval: {score}", lines))
            except Exception as exc:
                out_queue.put((current_id, f"Engine unavailable: {exc}", []))

        analysis_thread = threading.Thread(
            target=worker,
            args=(fen, analysis_stop, local_queue),
            daemon=True,
        )
        analysis_thread.start()

    @reactive.Effect
    def _trigger_eval():
        if not analysis_ready():
            return
        _ = ply_val()
        _ = moves_val()
        board = _current_board()
        _start_streaming_eval(board)

    @reactive.Effect
    def _drain_eval_queue():
        nonlocal analysis_queue, analysis_id
        reactive.invalidate_later(0.2)
        latest = None
        latest_lines = None
        while True:
            try:
                message_id, message, lines = analysis_queue.get_nowait()
            except queue.Empty:
                break
            if message_id == analysis_id:
                latest = message
                latest_lines = lines
        if latest is not None:
            eval_val.set(latest)
        if latest_lines is not None:
            pv_val.set(latest_lines)

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
        board = _current_board()
        svg = chess.svg.board(board=board, size=BOARD_SIZE)
        return ui.HTML(svg)

    @output
    @render.text
    def eval_line():
        return eval_val()

    @output
    @render.ui
    def pv_lines():
        lines = pv_val()
        if not lines:
            return ui.p("Top lines will appear here.", class_="text-muted")
        return ui.tags.ol(*[ui.tags.li(line) for line in lines], class_="mb-0")

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
