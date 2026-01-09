"""UI rendering helper functions."""

from __future__ import annotations

from analysis.analysis_engine import classify_wdl_delta
from shiny import ui


def normalize_san(san: str) -> str:
    """Strip check symbols from SAN."""
    return san.rstrip("+#")


def extract_first_pv_move(pv_line: str) -> str | None:
    """Return the first move from a PV line."""
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


def render_pv_list(
    lines: list[str],
    target_san: str | None,
    highlight_ready: bool,
    title: str = "PV:",
    empty_msg: str = "PV will appear here.",
    highlight_color: str = "success",
) -> ui.Tag:
    """Render principal variation lines."""
    if not lines:
        return ui.p(empty_msg, class_="text-muted")

    items = []
    for line in lines:
        first_move = extract_first_pv_move(line)
        is_match = False
        if target_san and first_move:
            first_move_norm = normalize_san(first_move)
            target_norm = normalize_san(target_san)
            is_match = first_move_norm == target_norm

        if highlight_ready and is_match:
            items.append(ui.tags.li(line, class_=f"text-{highlight_color}"))
        else:
            items.append(ui.tags.li(line))

    return ui.tags.div(
        ui.tags.div(title, class_="text-muted small mb-0"),
        ui.tags.ol(*items, class_="mb-0"),
    )


def render_summary_table(
    summary: dict,
    status: str,
    evaluation_metric: str = "cpl",
) -> ui.Tag:
    """Render the annotation summary table."""
    if status == "running" and not summary:
        return ui.p("Analyzing...", class_="text-muted")
    if not summary:
        return ui.p("No annotations yet.", class_="text-muted")

    # Choose column order based on annotation metric
    if evaluation_metric == "wdl":
        order = ["Best", "Excellent", "Good", "?!", "?", "??"]
    else:
        order = ["??", "?", "?!", "OK"]
    white_counts = summary.get("White", {})
    black_counts = summary.get("Black", {})
    white_avg = float(white_counts.get("avg_cpl", 0.0))
    black_avg = float(black_counts.get("avg_cpl", 0.0))
    white_avg_cpl = round(white_avg)
    black_avg_cpl = round(black_avg)

    note = (
        ui.p("Analyzing...", class_="text-muted mb-1") if status == "running" else None
    )

    meta = summary.get("meta", {}) if isinstance(summary, dict) else {}
    duration = meta.get("duration_sec")
    footnote = (
        ui.tags.div(
            f"Analysis completed in {float(duration):.2f} seconds.",
            class_="text-muted small mt-1 fst-italic",
        )
        if duration is not None
        else None
    )

    table = ui.tags.table(
        {"class": "table table-sm text-center mb-0"},
        ui.tags.thead(
            ui.tags.tr(
                ui.tags.th("Player"),
                *[ui.tags.th(label) for label in order],
                ui.tags.th("Avg CPL"),
            )
        ),
        ui.tags.tbody(
            ui.tags.tr(
                ui.tags.td("White"),
                *[ui.tags.td(str(white_counts.get(label, 0))) for label in order],
                ui.tags.td(str(white_avg_cpl)),
            ),
            ui.tags.tr(
                ui.tags.td("Black"),
                *[ui.tags.td(str(black_counts.get(label, 0))) for label in order],
                ui.tags.td(str(black_avg_cpl)),
            ),
        ),
    )

    if note is None and footnote is None:
        return table
    return ui.tags.div(*(value for value in (note, table, footnote) if value))


def render_move_list(
    sans: list[str],
    current_ply: int,
    annotations: dict[int, str],
    move_rows_func,
) -> ui.Tag:
    """Render the move list table."""
    if not sans:
        return ui.p("No moves loaded.", class_="text-muted")

    rows = move_rows_func(sans)
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


def render_game_info_table(info: dict[str, str | bool]) -> ui.Tag:
    """Render the game metadata table."""
    if info.get("date_only"):
        return ui.tags.table(
            {"class": "table table-sm text-center mb-0"},
            ui.tags.thead(
                ui.tags.tr(
                    ui.tags.th("Date"),
                    ui.tags.th("White"),
                    ui.tags.th("Black"),
                )
            ),
            ui.tags.tbody(
                ui.tags.tr(
                    ui.tags.td(info.get("date", "Unknown")),
                    ui.tags.td(f"{info['white']} ({info['white_elo']})"),
                    ui.tags.td(f"{info['black']} ({info['black_elo']})"),
                )
            ),
        )
    return ui.tags.table(
        {"class": "table table-sm text-center mb-0"},
        ui.tags.thead(
            ui.tags.tr(
                ui.tags.th("Start"),
                ui.tags.th("End"),
                ui.tags.th("Duration"),
                ui.tags.th("White"),
                ui.tags.th("Black"),
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


def format_eval_line(
    eval_message: str | int,
    ply: int,
    sans: list[str],
    annotations: dict[int, str],
    classify_func,
    pv_lines: list[str] | None = None,
    wdl_score: float | None = None,
    evaluation_metric: str = "cpl",
    wdl_scores: list[float] | None = None,
    prev_wdl_score: float | None = None,
) -> str:
    """Format the eval header line."""
    if isinstance(eval_message, str) and eval_message.startswith("Engine unavailable"):
        return eval_message

    cpl_display = "--"
    cpl_value = None
    if isinstance(eval_message, str) and eval_message.startswith("CPL:"):
        cpl_display = eval_message.split(":", 1)[1].strip()
    elif isinstance(eval_message, str) and eval_message:
        cpl_display = eval_message
    try:
        cpl_value = int(float(cpl_display))
    except (TypeError, ValueError):
        cpl_value = None

    move_text = "--"
    move_prefix = ""
    annotation = "--"
    eval_display = "--"
    es_display = "--"

    if ply > 0 and ply <= len(sans):
        move_no = (ply + 1) // 2
        move_prefix = f"{move_no}. " if (ply % 2) == 1 else f"{move_no}... "
        move_text = sans[ply - 1]

        # Get annotation - always calculate on-the-fly from engine data
        if evaluation_metric == "cpl":
            # For CPL metric: use error labels or "OK"
            if cpl_value is not None:
                label = classify_func(-cpl_value)
                annotation = label if label else "OK"
            else:
                annotation = "OK"
        else:

            def _label_from_wdl(curr: float | None, prev: float | None) -> str | None:
                if curr is None or prev is None:
                    return None
                mover_is_white = (ply % 2) == 1
                delta = curr - prev
                delta_for_mover = delta if mover_is_white else -delta
                return classify_wdl_delta(delta_for_mover)

            annotation = _label_from_wdl(wdl_score, prev_wdl_score) or "--"
            if annotation == "--" and wdl_scores and len(wdl_scores) > ply:
                annotation = (
                    _label_from_wdl(wdl_scores[ply], wdl_scores[ply - 1]) or "--"
                )
            if annotation == "--" and annotations:
                annotation = annotations.get(ply, "--")

        # Parse eval from top PV line (format: "+0.25 — e4 e5 Nf3" or "Mate in 3 — ...")
        if pv_lines and len(pv_lines) > 0:
            top_pv = pv_lines[0]
            if " — " in top_pv:
                eval_part = top_pv.split(" — ")[0].strip()
                # Check if it's a mate score
                if "Mate" in eval_part:
                    eval_display = eval_part
                else:
                    # It's a regular eval like "+0.25" or "-1.50"
                    eval_display = eval_part

        # ES (Expected Score) from WDL
        if wdl_score is not None:
            es_display = f"{wdl_score:.2f}"

    return f"{move_prefix}{move_text} | {annotation} | Eval: {eval_display} | CPL: {cpl_display} | ES: {es_display}"
