from __future__ import annotations

import queue
import threading

import chess
import chess.svg
import plotly.graph_objects as go
from analysis import (
    annotate_game_worker,
    calculate_estimated_elo,
    classify_delta,
    stream_analysis_worker,
)
from shiny import reactive, render, ui
from shinyswatch import theme_picker_server
from shinywidgets import render_widget
from utils import (
    board_at_ply,
    create_eval_graph,
    extract_game_info,
    format_eval_line,
    get_input_params,
    move_rows,
    parse_pgn,
    render_game_info_table,
    render_move_list,
    render_pv_list,
    render_summary_table,
    reset_game_state,
)

BOARD_SIZE = 360


def server(input, output, session):
    theme_picker_server()

    game_val = reactive.Value(None)
    moves_val = reactive.Value([])
    sans_val = reactive.Value([])
    ply_val = reactive.Value(0)
    eval_val = reactive.Value("CPL: --")
    pv_val = reactive.Value([])
    prev_pv_val = reactive.Value([])
    analysis_done = reactive.Value(False)
    analysis_ready = reactive.Value(False)
    annotations_val = reactive.Value({})
    summary_val = reactive.Value({})
    annotation_status = reactive.Value("idle")
    evals_val = reactive.Value([])
    info_val = reactive.Value(
        {
            "start": "Unknown",
            "end": "Unknown",
            "duration": "Unknown",
            "white": "Unknown",
            "black": "Unknown",
            "white_elo": "Unknown",
            "black_elo": "Unknown",
        }
    )
    analysis_queue: queue.Queue[
        tuple[int, int | str | None, list[str], str | None, list[str] | None, bool]
    ] = queue.Queue()
    analysis_thread: threading.Thread | None = None
    analysis_stop: threading.Event | None = None
    analysis_id = 0
    last_analysis_key: tuple[str, int, float] | None = None
    engine_move_val = reactive.Value(None)
    annotation_queue: queue.Queue[
        tuple[int, dict[int, str], dict[str, dict[str, int]], list[int]]
    ] = queue.Queue()
    annotation_thread: threading.Thread | None = None
    annotation_stop: threading.Event | None = None
    annotation_id = 0

    def _shutdown_analysis() -> None:
        if analysis_stop is not None:
            analysis_stop.set()
        if analysis_thread is not None and analysis_thread.is_alive():
            analysis_thread.join(timeout=1.0)
        if annotation_stop is not None:
            annotation_stop.set()
        if annotation_thread is not None and annotation_thread.is_alive():
            annotation_thread.join(timeout=1.0)

    session.on_ended(_shutdown_analysis)

    def _set_game_info(game):
        """Update game info reactive value."""
        info_val.set(extract_game_info(game))

    def _load_pgn(pgn_text: str) -> None:
        reactive_vals = {
            "game": game_val,
            "moves": moves_val,
            "sans": sans_val,
            "ply": ply_val,
            "analysis_ready": analysis_ready,
            "eval": eval_val,
            "pv": pv_val,
            "annotations": annotations_val,
            "summary": summary_val,
            "annotation_status": annotation_status,
            "evals": evals_val,
            "engine_move": engine_move_val,
            "info": info_val,
        }

        if not pgn_text.strip():
            reset_game_state(reactive_vals)
            return

        try:
            game, moves, sans = parse_pgn(pgn_text)
        except ValueError:
            reset_game_state(reactive_vals)
            return

        game_val.set(game)
        moves_val.set(moves)
        sans_val.set(sans)
        ply_val.set(0)
        analysis_ready.set(True)
        annotations_val.set({})
        summary_val.set({})
        annotation_status.set("idle")
        engine_move_val.set(None)
        _set_game_info(game)

    @reactive.Effect
    def _auto_analyze():
        pgn_text = ""
        upload = input.pgn_upload()
        if upload:
            path = upload[0]["datapath"]
            with open(path, "r", encoding="utf-8") as handle:
                pgn_text = handle.read()

        if not pgn_text.strip():
            pgn_text = input.pgn_text() or ""
        _load_pgn(pgn_text)

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

    def _board_at_ply(ply: int) -> chess.Board:
        """Get board at specific ply."""
        return board_at_ply(game_val(), moves_val(), ply)

    @reactive.Effect
    @reactive.event(input.annotate_moves)
    def _annotate_moves():
        nonlocal annotation_id, annotation_stop, annotation_queue, annotation_thread
        if not analysis_ready():
            return

        game = game_val()
        if game is None:
            return
        moves = moves_val()
        if not moves:
            annotations_val.set({})
            summary_val.set({})
            evals_val.set([])
            return

        params = get_input_params(input)
        think_time = params["think_time"]
        thread_count = params["threads"]

        if annotation_stop is not None:
            annotation_stop.set()
        annotation_stop = threading.Event()
        local_queue: queue.Queue[
            tuple[int, dict[int, str], dict[str, dict[str, int]], list[int]]
        ] = queue.Queue()
        annotation_queue = local_queue
        annotation_id += 1
        current_id = annotation_id
        summary_val.set({})
        annotation_status.set("running")

        annotation_thread = threading.Thread(
            target=annotate_game_worker,
            args=(
                game.board().fen(),
                moves,
                annotation_stop,
                local_queue,
                current_id,
                think_time,
                thread_count,
            ),
            daemon=True,
        )
        annotation_thread.start()

    def _board_at_ply(ply: int) -> chess.Board:
        game = game_val()
        moves = moves_val()
        if game is None:
            board = chess.Board()
        else:
            board = game.board()
            for move in moves[:ply]:
                board.push(move)
        return board

    def _current_board() -> chess.Board:
        return _board_at_ply(ply_val())

    def _start_streaming_eval(
        board: chess.Board, prev_fen: str | None, mover_is_white: bool
    ) -> None:
        nonlocal analysis_id, analysis_stop, analysis_queue, analysis_thread, last_analysis_key
        params = get_input_params(input)
        multipv = params["multipv"]
        engine_threads = params["threads"]
        think_time = params["think_time"]
        fen = board.fen()
        analysis_key = (fen, multipv, think_time, engine_threads)
        if analysis_key == last_analysis_key:
            return

        last_analysis_key = analysis_key
        analysis_id += 1
        current_id = analysis_id

        if analysis_stop is not None:
            analysis_stop.set()
        analysis_stop = threading.Event()
        local_queue: queue.Queue[
            tuple[int, int | str | None, list[str], str | None, list[str] | None, bool]
        ] = queue.Queue()
        analysis_queue = local_queue

        eval_val.set("CPL: …")
        pv_val.set([])
        prev_pv_val.set([])
        analysis_done.set(False)
        engine_move_val.set(None)

        analysis_thread = threading.Thread(
            target=stream_analysis_worker,
            args=(
                fen,
                prev_fen,
                analysis_stop,
                local_queue,
                current_id,
                mover_is_white,
                think_time,
                multipv,
                engine_threads,
            ),
            daemon=True,
        )
        analysis_thread.start()

    @reactive.Effect
    def _trigger_eval():
        if not analysis_ready():
            return
        _ = ply_val()
        _ = moves_val()
        _ = input.multipv()
        _ = input.engine_threads()
        _ = input.think_time()
        board = _current_board()
        ply = ply_val()
        prev_fen = None
        if ply > 0:
            prev_fen = _board_at_ply(ply - 1).fen()
        mover_is_white = (ply % 2) == 1
        _start_streaming_eval(board, prev_fen, mover_is_white)

    @reactive.Effect
    def _drain_eval_queue():
        nonlocal analysis_queue, analysis_id
        reactive.invalidate_later(0.2)
        latest_set = False
        latest = None
        latest_lines = None
        latest_move = None
        latest_prev_pv = None
        analysis_complete = False
        while True:
            try:
                message_id, message, lines, best_move, prev_pv, done = (
                    analysis_queue.get_nowait()
                )
            except queue.Empty:
                break
            if message_id == analysis_id:
                latest_set = True
                latest = message
                latest_lines = lines
                latest_move = best_move
                latest_prev_pv = prev_pv
                analysis_complete = analysis_complete or done
        if latest_set:
            if isinstance(latest, str) and latest.startswith("Engine unavailable"):
                eval_val.set(latest)
            elif latest is None:
                eval_val.set("CPL: --")
            else:
                eval_val.set(f"CPL: {latest}")
        if latest_lines is not None:
            pv_val.set(latest_lines)
        if latest_prev_pv is not None:
            prev_pv_val.set(latest_prev_pv)
        if latest_move is not None:
            engine_move_val.set(latest_move)
        if analysis_complete:
            analysis_done.set(True)

    @reactive.Effect
    def _drain_annotation_queue():
        nonlocal annotation_queue, annotation_id
        reactive.invalidate_later(0.4)
        latest_annotations = None
        latest_summary = None
        latest_evals = None
        while True:
            try:
                message_id, annotations, summary, evals = annotation_queue.get_nowait()
            except queue.Empty:
                break
            if message_id == annotation_id:
                latest_annotations = annotations
                latest_summary = summary
                latest_evals = evals
        if latest_annotations is not None:
            annotations_val.set(latest_annotations)
        if latest_summary is not None:
            summary_val.set(latest_summary)
            evals_val.set(latest_evals if latest_evals else [])
            annotation_status.set("idle")

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

    @render.ui
    def board_view():
        board = _current_board()
        arrows = []
        moves = moves_val()
        ply = ply_val()
        if ply > 0 and ply <= len(moves):
            last_move = moves[ply - 1]
            arrows.append(
                chess.svg.Arrow(
                    last_move.from_square,
                    last_move.to_square,
                    color="#2f6f5e",
                )
            )
        best_move_uci = engine_move_val()
        if best_move_uci:
            try:
                best_move = chess.Move.from_uci(best_move_uci)
                arrows.append(
                    chess.svg.Arrow(
                        best_move.from_square,
                        best_move.to_square,
                        color="#c64b2a",
                    )
                )
            except ValueError:
                pass

        svg = chess.svg.board(board=board, size=BOARD_SIZE, arrows=arrows)
        return ui.HTML(svg)

    @render.text
    def eval_line():
        return format_eval_line(
            eval_val(),
            ply_val(),
            sans_val(),
            annotations_val(),
            classify_delta,
        )

    @render.ui
    def fen_line():
        fen = _current_board().fen()
        return ui.tags.div(
            ui.tags.span("FEN:", class_="text-muted me-1"),
            ui.tags.code(fen),
            class_="fen-line small text-center",
        )

    @render.ui
    def game_info():
        return render_game_info_table(info_val())

    @render.ui
    def pv():
        ply = ply_val()
        sans = sans_val()
        next_san = sans[ply] if ply < len(sans) else None
        return render_pv_list(
            pv_val(),
            next_san,
            analysis_done(),
            title="PV:",
            empty_msg="PV will appear here.",
        )

    @render.ui
    def prev_pv():
        ply = ply_val()
        sans = sans_val()
        current_san = sans[ply - 1] if ply > 0 and ply <= len(sans) else None
        return render_pv_list(
            prev_pv_val(),
            current_san,
            analysis_done(),
            title="Prior ply:",
            empty_msg="Prior ply PV will appear here.",
        )

    @render.ui
    def move_summary():
        return render_summary_table(
            summary_val(),
            annotation_status(),
            calculate_estimated_elo,
        )

    @render.ui
    def move_list():
        return render_move_list(
            sans_val(),
            ply_val(),
            annotations_val(),
            move_rows,
        )

    @render_widget
    def eval_graph():
        fig = create_eval_graph(evals_val(), annotation_status())

        # If it's a full figure with data, convert to FigureWidget with click handlers
        if evals_val() and len(evals_val()) > 1:
            fw = go.FigureWidget(fig)
            plies = list(range(0, len(evals_val())))

            def _on_click_callback(trace, points, selector):
                """Handle click events on the graph."""
                if points and points.point_inds:
                    clicked_ply = plies[points.point_inds[0]]
                    total = len(moves_val())
                    clicked_ply = max(0, min(clicked_ply, total))
                    if clicked_ply != ply_val():
                        ply_val.set(clicked_ply)

            # Attach click handler to all traces
            for trace in fw.data:
                trace.on_click(_on_click_callback)

            return fw

        return fig
