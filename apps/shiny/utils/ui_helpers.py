"""UI rendering helper functions."""

from __future__ import annotations

from shiny import ui


def normalize_san(san: str) -> str:
    """Remove check/checkmate symbols from SAN notation.

    Args:
        san: Standard algebraic notation move

    Returns:
        Normalized SAN without +/#
    """
    return san.rstrip("+#")


def extract_first_pv_move(pv_line: str) -> str | None:
    """Extract first move from PV line.

    Args:
        pv_line: Principal variation line string

    Returns:
        First move in SAN notation or None
    """
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
    """Render principal variation lines with optional highlighting.

    Args:
        lines: List of PV line strings
        target_san: SAN move to highlight (if found)
        highlight_ready: Whether highlighting is enabled
        title: Title text
        empty_msg: Message when no lines available
        highlight_color: Color for highlighting ("success" for green, "warning" for orange)

    Returns:
        Shiny UI element
    """
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
    calculate_elo_func,
) -> ui.Tag:
    """Render move annotation summary table.

    Args:
        summary: Summary dictionary with player statistics
        status: Annotation status ("running", "idle", etc.)
        calculate_elo_func: Function to calculate Elo from CPL

    Returns:
        Shiny UI element
    """
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
    white_elo = calculate_elo_func(white_avg)
    black_elo = calculate_elo_func(black_avg)

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

    if note is None and footnote is None:
        return table
    return ui.tags.div(*(value for value in (note, table, footnote) if value))


def render_move_list(
    sans: list[str],
    current_ply: int,
    annotations: dict[int, str],
    move_rows_func,
) -> ui.Tag:
    """Render move list table with annotations.

    Args:
        sans: List of moves in SAN notation
        current_ply: Currently selected ply
        annotations: Map of ply to annotation string
        move_rows_func: Function to convert sans to display rows

    Returns:
        Shiny UI element
    """
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


def render_game_info_table(info: dict[str, str]) -> ui.Tag:
    """Render game information table.

    Args:
        info: Dictionary with game metadata

    Returns:
        Shiny UI table element
    """
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


def format_eval_line(
    eval_message: str | int,
    ply: int,
    sans: list[str],
    annotations: dict[int, str],
    classify_func,
) -> str:
    """Format evaluation line with move and annotation.

    Args:
        eval_message: Evaluation message or centipawn value
        ply: Current ply number
        sans: List of moves in SAN notation
        annotations: Map of ply to annotation
        classify_func: Function to classify centipawn delta

    Returns:
        Formatted evaluation string
    """
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
    annotation = ""
    if ply > 0 and ply <= len(sans):
        move_no = (ply + 1) // 2
        move_prefix = f"{move_no}. " if (ply % 2) == 1 else f"{move_no}... "
        move_text = sans[ply - 1]
        annotation_text = annotations.get(ply, "")
        label = ""
        if annotation_text:
            label = annotation_text.split()[0]
        elif cpl_value is not None:
            label = classify_func(-cpl_value)
        if label:
            annotation = f" {label}"

    return f"Move: {move_prefix}{move_text}{annotation} ({cpl_display})"
