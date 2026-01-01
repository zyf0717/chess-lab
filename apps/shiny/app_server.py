from __future__ import annotations

import io
import math
import queue
import threading
from datetime import datetime, timedelta

import chess
import chess.pgn
import chess.svg
from analysis.stockfish import clamp_score, evaluate_positions, stream_analysis
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
    eval_val = reactive.Value("CPL: --")
    pv_val = reactive.Value([])
    prev_pv_val = reactive.Value([])
    analysis_done = reactive.Value(False)
    analysis_ready = reactive.Value(False)
    annotations_val = reactive.Value({})
    summary_val = reactive.Value({})
    annotation_status = reactive.Value("idle")
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
        tuple[int, dict[int, str], dict[str, dict[str, int]]]
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

    def _parse_date(value: str | None):
        if not value or "?" in value:
            return None
        try:
            return datetime.strptime(value, "%Y.%m.%d").date()
        except ValueError:
            return None

    def _parse_time(value: str | None):
        if not value or "?" in value:
            return None
        for fmt in ("%H:%M:%S", "%H:%M"):
            try:
                return datetime.strptime(value, fmt).time()
            except ValueError:
                continue
        return None

    def _parse_datetime(date_value: str | None, time_value: str | None):
        date_part = _parse_date(date_value)
        time_part = _parse_time(time_value)
        if date_part and time_part:
            return datetime.combine(date_part, time_part)
        return None

    def _format_dt(value: datetime | None) -> str:
        if value is None:
            return "Unknown"
        return value.strftime("%Y-%m-%d %H:%M:%S")

    def _format_duration(start: datetime | None, end: datetime | None) -> str:
        if start is None or end is None:
            return "Unknown"
        delta = end - start
        if delta.total_seconds() < 0:
            delta += timedelta(days=1)
        seconds = int(delta.total_seconds())
        hours, remainder = divmod(seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"

    def _set_game_info(game: chess.pgn.Game | None) -> None:
        if game is None:
            info_val.set(
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
            return

        headers = game.headers
        start_dt = _parse_datetime(
            headers.get("UTCDate") or headers.get("Date"),
            headers.get("UTCTime") or headers.get("Time"),
        )
        end_dt = _parse_datetime(
            headers.get("EndDate") or headers.get("UTCDate") or headers.get("Date"),
            headers.get("EndTime"),
        )
        info_val.set(
            {
                "start": _format_dt(start_dt),
                "end": _format_dt(end_dt),
                "duration": _format_duration(start_dt, end_dt),
                "white": headers.get("White", "Unknown"),
                "black": headers.get("Black", "Unknown"),
                "white_elo": headers.get("WhiteElo", "Unknown"),
                "black_elo": headers.get("BlackElo", "Unknown"),
            }
        )

    def _load_pgn(pgn_text: str) -> None:
        if not pgn_text.strip():
            game_val.set(None)
            moves_val.set([])
            sans_val.set([])
            ply_val.set(0)
            analysis_ready.set(False)
            eval_val.set("CPL: --")
            pv_val.set([])
            annotations_val.set({})
            summary_val.set({})
            annotation_status.set("idle")
            engine_move_val.set(None)
            _set_game_info(None)
            return

        try:
            game, moves, sans = parse_pgn(pgn_text)
        except ValueError:
            game_val.set(None)
            moves_val.set([])
            sans_val.set([])
            ply_val.set(0)
            analysis_ready.set(False)
            eval_val.set("CPL: --")
            pv_val.set([])
            annotations_val.set({})
            summary_val.set({})
            annotation_status.set("idle")
            engine_move_val.set(None)
            _set_game_info(None)
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

    def _classify_delta(delta_cp: int) -> str:
        cpl = max(0, -delta_cp)
        if cpl >= 300:
            return "??"
        if cpl >= 150:
            return "?"
        if cpl >= 70:
            return "?!"
        return ""

    def _summarize_annotations(
        annotations: dict[int, str],
        cpl_by_ply: dict[int, int],
        total_plies: int,
    ) -> dict[str, dict[str, int | float]]:
        labels = ["??", "?", "?!"]
        counts = {
            "White": {label: 0 for label in labels},
            "Black": {label: 0 for label in labels},
        }
        neutral = {"White": 0, "Black": 0}
        totals = {"White": 0, "Black": 0}
        moves = {"White": 0, "Black": 0}
        for ply in range(1, total_plies + 1):
            side = "White" if ply % 2 == 1 else "Black"
            moves[side] += 1
            totals[side] += cpl_by_ply.get(ply, 0)
            label = annotations.get(ply, "")
            if label:
                counts[side][label] += 1
            else:
                neutral[side] += 1
        counts["White"]["OK"] = neutral["White"]
        counts["Black"]["OK"] = neutral["Black"]
        counts["White"]["avg_cpl"] = (
            totals["White"] / moves["White"] if moves["White"] else 0.0
        )
        counts["Black"]["avg_cpl"] = (
            totals["Black"] / moves["Black"] if moves["Black"] else 0.0
        )
        return counts

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
            return

        try:
            think_time = float(input.think_time())
        except (TypeError, ValueError):
            think_time = 1.0
        think_time = max(1.0, min(think_time, 60.0))

        if annotation_stop is not None:
            annotation_stop.set()
        annotation_stop = threading.Event()
        local_queue: queue.Queue[
            tuple[int, dict[int, str], dict[str, dict[str, int]]]
        ] = queue.Queue()
        annotation_queue = local_queue
        annotation_id += 1
        current_id = annotation_id
        annotation_status.set("running")

        def worker(
            base_fen: str,
            move_list: list[chess.Move],
            stop_event: threading.Event,
            out_queue: queue.Queue,
            time_limit: float,
        ):
            try:
                base_board = chess.Board(base_fen)
                evals = evaluate_positions(
                    base_board, move_list, time_limit=time_limit, stop_event=stop_event
                )
                if stop_event.is_set() or len(evals) <= 1:
                    return
                label_annotations: dict[int, str] = {}
                display_annotations: dict[int, str] = {}
                cpl_by_ply: dict[int, int] = {}
                for ply in range(1, len(evals)):
                    prev_cp = clamp_score(evals[ply - 1])
                    curr_cp = clamp_score(evals[ply])
                    delta = curr_cp - prev_cp
                    mover_is_white = (ply % 2) == 1
                    delta_for_mover = delta if mover_is_white else -delta
                    cpl_cp = max(0, -int(delta_for_mover))
                    cpl_by_ply[ply] = cpl_cp
                    label = _classify_delta(delta_for_mover)
                    if label:
                        display_annotations[ply] = f"{label} ({cpl_cp})"
                        label_annotations[ply] = label
                summary = _summarize_annotations(
                    label_annotations, cpl_by_ply, len(move_list)
                )
                out_queue.put((current_id, display_annotations, summary))
            except Exception:
                out_queue.put((current_id, {}, {}))

        annotation_thread = threading.Thread(
            target=worker,
            args=(game.board().fen(), moves, annotation_stop, local_queue, think_time),
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
        local_queue: queue.Queue[
            tuple[int, int | str | None, list[str], str | None, list[str] | None, bool]
        ] = queue.Queue()
        analysis_queue = local_queue

        eval_val.set("CPL: …")
        pv_val.set([])
        prev_pv_val.set([])
        analysis_done.set(False)
        engine_move_val.set(None)

        def worker(
            fen_str: str,
            prev_fen_str: str | None,
            stop_event: threading.Event,
            out_queue: queue.Queue,
        ):
            try:
                board_obj = chess.Board(fen_str)
                prev_board = chess.Board(prev_fen_str) if prev_fen_str else None
                for delta_cp, lines, best_move, prev_pv, done in stream_analysis(
                    board_obj,
                    time_limit=think_time,
                    multipv=multipv,
                    stop_event=stop_event,
                    best_move_board=prev_board,
                ):
                    if stop_event.is_set():
                        break
                    if delta_cp is None:
                        out_queue.put(
                            (current_id, None, lines, best_move, prev_pv, done)
                        )
                        continue
                    # Convert white-POV delta to mover CPL for display.
                    delta_for_mover = delta_cp if mover_is_white else -delta_cp
                    cpl = max(0, -delta_for_mover)
                    out_queue.put(
                        (current_id, cpl, lines, best_move, prev_pv, done)
                    )
            except Exception as exc:
                out_queue.put(
                    (current_id, f"Engine unavailable: {exc}", [], None, None, True)
                )

        analysis_thread = threading.Thread(
            target=worker,
            args=(fen, prev_fen, analysis_stop, local_queue),
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
        while True:
            try:
                message_id, annotations, summary = annotation_queue.get_nowait()
            except queue.Empty:
                break
            if message_id == annotation_id:
                latest_annotations = annotations
                latest_summary = summary
        if latest_annotations is not None:
            annotations_val.set(latest_annotations)
        if latest_summary is not None:
            summary_val.set(latest_summary)
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

    @output
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

    @output
    @render.text
    def eval_line():
        message = eval_val()
        if isinstance(message, str) and message.startswith("Engine unavailable"):
            return message

        cpl_display = "--"
        if isinstance(message, str) and message.startswith("CPL:"):
            cpl_display = message.split(":", 1)[1].strip()
        elif isinstance(message, str) and message:
            cpl_display = message

        ply = ply_val()
        sans = sans_val()
        move_text = "--"
        move_prefix = ""
        annotation = ""
        if ply > 0 and ply <= len(sans):
            move_no = (ply + 1) // 2
            move_prefix = f"{move_no}. " if (ply % 2) == 1 else f"{move_no}... "
            move_text = sans[ply - 1]
            annotation_text = annotations_val().get(ply, "")
            if annotation_text:
                annotation = f" {annotation_text.split()[0]}"

        return f"Move: {move_prefix}{move_text}{annotation} ({cpl_display})"

    @output
    @render.ui
    def fen_line():
        fen = _current_board().fen()
        return ui.tags.div(
            ui.tags.span("FEN:", class_="text-muted me-1"),
            ui.tags.code(fen),
            class_="fen-line small text-center",
        )

    @output
    @render.ui
    def game_info():
        info = info_val()
        return ui.tags.table(
            {"class": "table table-sm text-center mb-0"},
            ui.tags.thead(
                ui.tags.tr(
                    ui.tags.th("Start"),
                    ui.tags.th("End"),
                    ui.tags.th("Duration"),
                    ui.tags.th("White (Elo)"),
                    ui.tags.th("Black (Elo)"),
                )
            ),
            ui.tags.tbody(
                ui.tags.tr(
                    ui.tags.td(info["start"]),
                    ui.tags.td(info["end"]),
                    ui.tags.td(info["duration"]),
                    ui.tags.td(f"{info['white']} ({info['white_elo']})"),
                    ui.tags.td(f"{info['black']} ({info['black_elo']})"),
                )
            ),
        )

    @output
    @render.ui
    def pv():
        lines = pv_val()
        if not lines:
            return ui.p("PV will appear here.", class_="text-muted")
        return ui.tags.div(
            ui.tags.div("PV:", class_="text-muted small mb-0"),
            ui.tags.ol(*[ui.tags.li(line) for line in lines], class_="mb-0"),
        )

    @output
    @render.ui
    def prev_pv():
        lines = prev_pv_val()
        if not lines:
            return ui.p(
                "Prior ply PV will appear here.", class_="text-muted small mb-1"
            )
        highlight_ready = analysis_done()

        def _normalize_san(value: str) -> str:
            return value.rstrip("+#")

        def _first_pv_move(pv_line: str) -> str | None:
            _, sep, pv = pv_line.partition("—")
            pv_part = pv.strip() if sep else pv_line.strip()
            if not pv_part:
                return None
            tokens = pv_part.split()
            if not tokens:
                return None
            if tokens[0].endswith(".") or tokens[0].endswith("..."):
                return tokens[1] if len(tokens) > 1 else None
            return tokens[0]

        ply = ply_val()
        current_san = None
        if ply > 0:
            sans = sans_val()
            if ply <= len(sans):
                current_san = _normalize_san(sans[ply - 1])

        items = []
        for line in lines:
            first_move = _first_pv_move(line)
            if current_san and first_move:
                first_move = _normalize_san(first_move)
            if highlight_ready and current_san and first_move == current_san:
                items.append(ui.tags.li(line, class_="text-success"))
            else:
                items.append(ui.tags.li(line))
        return ui.tags.div(
            ui.tags.div("Prior ply:", class_="text-muted small mb-0"),
            ui.tags.ol(*items, class_="mb-0"),
        )

    @output
    @render.ui
    def move_summary():
        status = annotation_status()
        summary = summary_val()
        if status == "running" and not summary:
            return ui.p("Analyzing...", class_="text-muted")
        if not summary:
            return ui.p("No annotations yet.", class_="text-muted")
        order = ["??", "?", "?!", "OK"]
        white_counts = summary.get("White", {})
        black_counts = summary.get("Black", {})
        white_avg = float(white_counts.get("avg_cpl", 0.0))
        black_avg = float(black_counts.get("avg_cpl", 0.0))
        white_avg_cpl = round(white_avg)
        black_avg_cpl = round(black_avg)
        white_elo = 3100 * math.exp(-0.01 * white_avg_cpl)
        black_elo = 3100 * math.exp(-0.01 * black_avg_cpl)
        note = (
            ui.p("Analyzing...", class_="text-muted mb-1")
            if status == "running"
            else None
        )
        table = ui.tags.table(
            {"class": "table table-sm text-center mb-0"},
            ui.tags.thead(
                ui.tags.tr(
                    ui.tags.th("Player"),
                    *[ui.tags.th(label) for label in order],
                    ui.tags.th("Avg CPL"),
                    ui.tags.th("Est Elo"),
                )
            ),
            ui.tags.tbody(
                ui.tags.tr(
                    ui.tags.td("White"),
                    *[ui.tags.td(str(white_counts.get(label, 0))) for label in order],
                    ui.tags.td(str(white_avg_cpl)),
                    ui.tags.td(f"{white_elo:.0f}"),
                ),
                ui.tags.tr(
                    ui.tags.td("Black"),
                    *[ui.tags.td(str(black_counts.get(label, 0))) for label in order],
                    ui.tags.td(str(black_avg_cpl)),
                    ui.tags.td(f"{black_elo:.0f}"),
                ),
            ),
        )
        if note is None:
            return table
        return ui.tags.div(note, table)

    @output
    @render.ui
    def move_list():
        sans = sans_val()
        if not sans:
            return ui.p("No moves loaded.", class_="text-muted")

        rows = move_rows(sans)
        current_ply = ply_val()
        annotations = annotations_val()
        table_rows = []

        for row_index, (move_no, white, black) in enumerate(rows):
            white_ply = row_index * 2 + 1
            black_ply = row_index * 2 + 2

            white_attrs = {"data-ply": str(white_ply)}
            if white_ply == current_ply:
                white_attrs["class"] = "is-selected"
            white_label = annotations.get(white_ply, "")
            white_text = f"{white} {white_label}".rstrip()

            if black:
                black_attrs = {"data-ply": str(black_ply)}
                if black_ply == current_ply:
                    black_attrs["class"] = "is-selected"
                black_label = annotations.get(black_ply, "")
                black_text = f"{black} {black_label}".rstrip()
                black_cell = ui.tags.td(black_text, **black_attrs)
            else:
                black_cell = ui.tags.td("")

            table_rows.append(
                ui.tags.tr(
                    ui.tags.td(str(move_no)),
                    ui.tags.td(white_text, **white_attrs),
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
