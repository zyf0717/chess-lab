from __future__ import annotations

import asyncio
import queue
import threading
import time

import chess
import chess.svg
import plotly.graph_objects as go
from analysis import annotate_game_worker, classify_delta, stream_analysis_worker
from shiny import reactive, render, ui
from shinyswatch import theme_picker_server
from shinywidgets import render_widget
from utils import (
    DEFAULT_INFO,
    best_move_uci,
    board_at_ply,
    create_eval_graph,
    extract_first_pv_move,
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
    sans_from_board,
)

BOARD_SIZE = 480


def server(input, output, session):
    theme_picker_server()
    game_state = reactive.Value(chess.Board())
    game_val = reactive.Value(None)
    moves_val = reactive.Value([])
    sans_val = reactive.Value([])
    ply_val = reactive.Value(0)
    eval_val = reactive.Value("CPL: --")
    pv_val = reactive.Value([])
    prev_pv_val = reactive.Value([])
    wdl_val = reactive.Value(None)
    prev_wdl_val = reactive.Value(None)
    analysis_done = reactive.Value(False)
    analysis_ready = reactive.Value(False)
    annotations_val = reactive.Value({})  # Display annotations for moves table
    label_annotations_val = reactive.Value({})  # All annotations for per-move analysis
    summary_val = reactive.Value({})
    annotation_status = reactive.Value("idle")
    evals_val = reactive.Value([])
    wdl_scores_val = reactive.Value([])
    info_val = reactive.Value(DEFAULT_INFO.copy())
    analysis_queue: queue.Queue[
        tuple[
            int,
            int | str | None,
            list[str],
            str | None,
            list[str] | None,
            float | None,
            float | None,
            bool,
        ]
    ] = queue.Queue()
    analysis_thread: threading.Thread | None = None
    analysis_stop: threading.Event | None = None
    analysis_id = 0
    last_analysis_key: tuple[str, int, float, int] | None = None
    engine_move_val = reactive.Value(None)
    eval_trigger_time = reactive.Value(0.0)  # Track when to trigger eval
    annotation_queue: queue.Queue[
        tuple[
            int,
            dict[int, str],
            dict[int, str],
            dict[str, dict[str, int | float]],
            list[int],
            list[float],
        ]
    ] = queue.Queue()
    annotation_thread: threading.Thread | None = None
    annotation_stop: threading.Event | None = None
    annotation_id = 0

    state = {
        "game": game_val,
        "moves": moves_val,
        "sans": sans_val,
        "ply": ply_val,
        "analysis_ready": analysis_ready,
        "analysis_done": analysis_done,
        "eval": eval_val,
        "pv": pv_val,
        "prev_pv": prev_pv_val,
        "annotations": annotations_val,
        "label_annotations": label_annotations_val,
        "summary": summary_val,
        "annotation_status": annotation_status,
        "evals": evals_val,
        "wdl_scores": wdl_scores_val,
        "wdl": wdl_val,
        "prev_wdl": prev_wdl_val,
        "engine_move": engine_move_val,
        "info": info_val,
    }

    def _stop_worker(
        stop_event: threading.Event | None, thread: threading.Thread | None
    ) -> None:
        if stop_event is not None:
            stop_event.set()
        if thread is not None and thread.is_alive():
            thread.join(timeout=1.0)

    def _shutdown_analysis() -> None:
        _stop_worker(analysis_stop, analysis_thread)
        _stop_worker(annotation_stop, annotation_thread)

    session.on_ended(_shutdown_analysis)

    def _set_game_info(game):
        """Refresh game metadata."""
        info_val.set(extract_game_info(game))

    def _set_ply(ply: int) -> None:
        """Use for navigation; direct ply_val.set() for reset/load to avoid extra deps."""
        total = len(moves_val())
        ply = max(0, min(ply, total))
        if ply != ply_val():
            ply_val.set(ply)

    play_jump_to_end = False

    def _load_pgn(pgn_text: str) -> None:
        if not pgn_text.strip():
            reset_game_state(state)
            return

        reset_game_state(state)
        try:
            game, moves, sans = parse_pgn(pgn_text)
        except ValueError:
            return

        game_val.set(game)
        moves_val.set(moves)
        sans_val.set(sans)
        # Avoid _set_ply here to keep _auto_analyze independent of ply changes.
        # See _set_ply() for details.
        ply_val.set(0)
        analysis_ready.set(True)
        analysis_done.set(False)
        _set_game_info(game)

    @reactive.Effect
    def _auto_analyze():
        nonlocal play_jump_to_end
        if play_jump_to_end:
            play_jump_to_end = False
            return
        pgn_text = input.pgn_text() or ""
        if pgn_text.strip():
            _load_pgn(pgn_text)
            return

        upload = input.pgn_upload()
        if upload:
            path = upload[0]["datapath"]
            with open(path, "r", encoding="utf-8") as handle:
                _load_pgn(handle.read())
                return

        _load_pgn("")

    @reactive.Effect
    @reactive.event(input.pgn_text)
    def _clear_upload_on_text():
        pgn_text = input.pgn_text() or ""
        if not pgn_text.strip():
            return
        if input.pgn_upload():
            session.send_custom_message("clear_pgn_upload", {})

    @reactive.Effect
    @reactive.event(input.pgn_upload)
    def _clear_text_on_upload():
        if input.pgn_upload() and (input.pgn_text() or "").strip():
            ui.update_text_area("pgn_text", value="")

    @reactive.Effect
    @reactive.event(input.prev_move)
    def _prev_move():
        _set_ply(ply_val() - 1)

    @reactive.Effect
    @reactive.event(input.next_move)
    def _next_move():
        _set_ply(ply_val() + 1)

    @reactive.Effect
    @reactive.event(input.first_move)
    def _first_move():
        _set_ply(0)

    @reactive.Effect
    @reactive.event(input.last_move)
    def _last_move():
        _set_ply(len(moves_val()))

    @reactive.Effect
    @reactive.event(input.move_back_2)
    def _move_back_2():
        _set_ply(ply_val() - 2)

    @reactive.Effect
    @reactive.event(input.move_forward_2)
    def _move_forward_2():
        _set_ply(ply_val() + 2)

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
            wdl_scores_val.set([])
            annotation_status.set("idle")
            return

        params = get_input_params(input)
        think_time = params["think_time"]
        thread_count = params["threads"]
        evaluation_metric = input.evaluation_metric() or "cpl"

        if annotation_stop is not None:
            annotation_stop.set()
        annotation_stop = threading.Event()
        local_queue: queue.Queue[
            tuple[
                int,
                dict[int, str],
                dict[int, str],
                dict[str, dict[str, int | float]],
                list[int],
                list[float],
            ]
        ] = queue.Queue()
        annotation_queue = local_queue
        annotation_id += 1
        current_id = annotation_id
        summary_val.set({})
        annotation_status.set("running")

        # Update button to show it's running
        ui.update_action_button("annotate_moves", label="Annotating...", disabled=True)

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
                evaluation_metric,
            ),
            daemon=True,
        )
        annotation_thread.start()

    @reactive.Effect
    def _update_annotate_button_state():
        """Update button state based on annotation status."""
        status = annotation_status()
        if status == "running":
            ui.update_action_button(
                "annotate_moves", label="Annotating...", disabled=True
            )
        else:
            ui.update_action_button(
                "annotate_moves", label="Annotate Game", disabled=False
            )

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
            tuple[
                int,
                int | str | None,
                list[str],
                str | None,
                list[str] | None,
                float | None,
                float | None,
                bool,
            ]
        ] = queue.Queue()
        analysis_queue = local_queue

        eval_val.set("CPL: …")
        pv_val.set([])
        prev_pv_val.set([])
        wdl_val.set(None)
        prev_wdl_val.set(None)
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

        # Clear engine move and analysis state immediately to prevent stale UI
        engine_move_val.set(None)
        analysis_done.set(False)

        # Set trigger time to 0.2 seconds from now
        eval_trigger_time.set(time.time() + 0.2)

    @reactive.Effect
    def _debounced_eval():
        """Actually trigger eval after debounce delay."""
        if not analysis_ready():
            return

        # Check every 0.05 seconds if it's time to trigger
        reactive.invalidate_later(0.05)

        trigger_time = eval_trigger_time()
        if trigger_time == 0.0:
            return

        # If we've reached the trigger time, start the evaluation
        if time.time() >= trigger_time:
            eval_trigger_time.set(0.0)  # Reset trigger time
            board = _current_board()
            ply = ply_val()
            prev_fen = None
            if ply > 0:
                prev_fen = _board_at_ply(ply - 1).fen()
            mover_is_white = (ply % 2) == 1
            _start_streaming_eval(board, prev_fen, mover_is_white)

    def _drain_latest_eval():
        latest = None
        analysis_complete = False
        while True:
            try:
                item = analysis_queue.get_nowait()
            except queue.Empty:
                break
            if item[0] == analysis_id:
                latest = item
                analysis_complete = analysis_complete or item[-1]
        return latest, analysis_complete

    def _drain_latest_annotation():
        latest = None
        while True:
            try:
                item = annotation_queue.get_nowait()
            except queue.Empty:
                break
            if item[0] == annotation_id:
                latest = item
        return latest

    @reactive.Effect
    def _drain_eval_queue():
        nonlocal analysis_queue, analysis_id
        reactive.invalidate_later(0.2)
        latest, analysis_complete = _drain_latest_eval()
        if latest is None:
            return
        _, message, lines, best_move, prev_pv, wdl_score, prev_wdl_score, _ = latest

        if isinstance(message, str) and message.startswith("Engine unavailable"):
            eval_val.set(message)
        elif message is None:
            eval_val.set("CPL: --")
        else:
            eval_val.set(f"CPL: {message}")

        pv_val.set(lines)
        if prev_pv is not None:
            prev_pv_val.set(prev_pv)
        if best_move is not None:
            engine_move_val.set(best_move)
        if wdl_score is not None:
            wdl_val.set(wdl_score)
        if prev_wdl_score is not None:
            prev_wdl_val.set(prev_wdl_score)
        if analysis_complete:
            analysis_done.set(True)

    @reactive.Effect
    def _drain_annotation_queue():
        nonlocal annotation_queue, annotation_id
        reactive.invalidate_later(0.4)
        latest = _drain_latest_annotation()
        if latest is None:
            return
        _, annotations, label_annotations, summary, evals, wdl_scores = latest
        annotations_val.set(annotations)
        label_annotations_val.set(label_annotations)
        summary_val.set(summary)
        evals_val.set(evals if evals else [])
        wdl_scores_val.set(wdl_scores if wdl_scores else [])
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
        _set_ply(ply)

    @render.ui
    def board_view():
        board = _current_board()
        arrows = []
        moves = moves_val()
        ply = ply_val()
        last_move = moves[ply - 1] if ply > 0 and ply <= len(moves) else None
        arrow_keys: set[tuple[int, int]] = set()

        def _append_arrow(move: chess.Move) -> None:
            key = (move.from_square, move.to_square)
            if key in arrow_keys:
                return
            arrow_keys.add(key)
            arrows.append(
                chess.svg.Arrow(
                    move.from_square,
                    move.to_square,
                    color="green",
                )
            )

        if analysis_done():
            # Prior ply best move.
            prev_pv_lines = prev_pv_val()
            if prev_pv_lines and ply > 0:
                prev_san = extract_first_pv_move(prev_pv_lines[0])
                if prev_san:
                    prev_board = _board_at_ply(ply - 1)
                    try:
                        prev_best_move = prev_board.parse_san(prev_san)
                    except ValueError:
                        prev_best_move = None
                    if prev_best_move:
                        _append_arrow(prev_best_move)

            # Current ply best move.
            best_move_uci = engine_move_val()
            if best_move_uci:
                try:
                    best_move = chess.Move.from_uci(best_move_uci)
                except ValueError:
                    best_move = None
                if best_move:
                    _append_arrow(best_move)

        svg = chess.svg.board(
            board=board,
            size=BOARD_SIZE,
            arrows=arrows,
            lastmove=last_move,
        )
        return ui.HTML(svg)

    @render.text
    def eval_line():
        return format_eval_line(
            eval_val(),
            ply_val(),
            sans_val(),
            label_annotations_val(),  # Use label_annotations for full quality labels
            classify_delta,
            pv_val(),
            wdl_val(),
            input.evaluation_metric() or "cpl",
            wdl_scores_val(),  # Pass all WDL scores for calculating deltas
            prev_wdl_val(),  # Pass previous WDL from live analysis
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
        pv_lines = pv_val()
        next_san = sans[ply] if ply < len(sans) else None
        return render_pv_list(
            pv_lines,
            next_san,
            False,
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
            False,  # Disable highlighting for prior ply
            title="Prior ply:",
            empty_msg="Prior ply PV will appear here.",
        )

    @render.ui
    def move_summary():
        return render_summary_table(
            summary_val(),
            annotation_status(),
            input.evaluation_metric() or "cpl",
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
                    _set_ply(clicked_ply)

            # Attach click handler to all traces
            for trace in fw.data:
                trace.on_click(_on_click_callback)

            return fw

        return fig

    @reactive.Effect
    @reactive.event(input.flipPlayBoard)
    async def _flip_play_board():
        await session.send_custom_message("board_flip", {})

    @reactive.Effect
    @reactive.event(input.player_move)
    async def process_move():
        move_data = input.player_move()
        if not move_data:
            return

        source = move_data.get("from")
        target = move_data.get("to")
        if not source or not target or source == target:
            return

        current_board = game_state.get().copy()

        # Convert JS coordinates to Python move object
        try:
            move = chess.Move.from_uci(f"{source}{target}")
        except chess.InvalidMoveError:
            return

        if move in current_board.legal_moves:
            # Update Python truth; the client already moved the piece.
            current_board.push(move)
            game_state.set(current_board)
            return

        # Move failed: force JS to revert to current valid state.
        last_move = (
            current_board.move_stack[-1].uci() if current_board.move_stack else None
        )
        await session.send_custom_message(
            "board_update", {"fen": current_board.fen(), "last_move": last_move}
        )

    engine_task: asyncio.Task | None = None

    async def _run_engine_move(
        board_snapshot: chess.Board, start_fen: str, params: dict
    ) -> None:
        engine_move_uci = await asyncio.to_thread(
            best_move_uci,
            board_snapshot,
            params["think_time"],
            params["threads"],
            3,
        )
        if not engine_move_uci:
            return

        latest = game_state.get()
        if latest.fen() != start_fen:
            return

        try:
            move = chess.Move.from_uci(engine_move_uci)
        except chess.InvalidMoveError:
            return
        if move not in latest.legal_moves:
            return

        updated = latest.copy()
        updated.push(move)
        game_state.set(updated)
        last_move = updated.move_stack[-1].uci() if updated.move_stack else None
        await session.send_custom_message(
            "board_update", {"fen": updated.fen(), "last_move": last_move}
        )

    @reactive.Effect
    @reactive.event(game_state, input.engine_side)
    def computer_move():
        nonlocal engine_task
        board = game_state.get().copy()
        if board.is_game_over():
            return
        engine_side = (input.engine_side() or "black").lower()
        if engine_side == "none":
            return
        if engine_side not in ("white", "black"):
            engine_side = "black"
        engine_turn = chess.WHITE if engine_side == "white" else chess.BLACK
        if board.turn != engine_turn:
            return
        if engine_task is not None and not engine_task.done():
            return

        params = get_input_params(input)
        start_fen = board.fen()
        loop = asyncio.get_running_loop()
        engine_task = loop.create_task(
            _run_engine_move(board.copy(), start_fen, params)
        )

    @render.ui
    def play_move_list():
        board = game_state.get().copy()
        sans = sans_from_board(board)
        current_ply = len(sans)
        return render_move_list(sans, current_ply, {}, move_rows)

    @render.download(filename="play.pgn")
    def download_play_pgn():
        board = game_state.get().copy()
        game = chess.pgn.Game.from_board(board)
        exporter = chess.pgn.StringExporter(
            headers=False, variations=False, comments=False
        )
        return game.accept(exporter)

    @reactive.Effect
    @reactive.event(input.analyze_play_position)
    def _analyze_play_position():
        nonlocal play_jump_to_end
        board = game_state.get().copy()
        game = chess.pgn.Game.from_board(board)
        exporter = chess.pgn.StringExporter(
            headers=False, variations=False, comments=False
        )
        pgn_text = game.accept(exporter)
        play_jump_to_end = True
        _load_pgn(pgn_text)
        _set_ply(len(moves_val()))
        ui.update_text_area("pgn_text", value=pgn_text)
        ui.update_navset("main_nav", selected="Analysis")

    @reactive.Effect
    @reactive.event(input.resetPlayBoard)
    async def _reset_play_board():
        game_state.set(chess.Board())
        await session.send_custom_message(
            "board_update", {"fen": chess.STARTING_FEN, "last_move": None}
        )
