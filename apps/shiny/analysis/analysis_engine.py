"""Analysis and annotation logic for chess games."""

from __future__ import annotations

import queue
import threading
import time

import chess
from analysis.stockfish import clamp_score, evaluate_positions, stream_analysis


def classify_delta(delta_cp: int) -> str:
    """Classify centipawn loss into symbols."""
    cpl = max(0, -delta_cp)
    if cpl >= 300:
        return "??"
    if cpl >= 150:
        return "?"
    if cpl >= 70:
        return "?!"
    return ""


def classify_wdl_delta(delta_score: float) -> str:
    """Classify expected score loss."""
    loss = max(0.0, -delta_score)
    if loss >= 0.20:
        return "??"
    if loss >= 0.10:
        return "?"
    if loss >= 0.05:
        return "?!"
    if loss >= 0.02:
        return "Good"
    if loss > 0.00:
        return "Excellent"
    return "Best"


def summarize_annotations(
    annotations: dict[int, str],
    cpl_by_ply: dict[int, int],
    total_plies: int,
) -> dict[str, dict[str, int | float]]:
    """Summarize annotation counts and averages."""
    all_labels = ["Best", "Excellent", "Good", "?!", "?", "??"]
    error_labels = ["??", "?", "?!"]
    counts = {
        "White": {label: 0 for label in all_labels},
        "Black": {label: 0 for label in all_labels},
    }
    totals = {"White": 0, "Black": 0}
    moves = {"White": 0, "Black": 0}

    for ply in range(1, total_plies + 1):
        side = "White" if ply % 2 == 1 else "Black"
        moves[side] += 1
        totals[side] += cpl_by_ply.get(ply, 0)
        label = annotations.get(ply, "")
        if label in all_labels:
            counts[side][label] += 1
        # Note: unmarked moves (empty label) are not counted in any category

    # Calculate OK count (for CPL metric: all non-error moves)
    for side in ["White", "Black"]:
        ok_count = moves[side]
        for error_label in error_labels:
            ok_count -= counts[side][error_label]
        counts[side]["OK"] = ok_count
    counts["White"]["avg_cpl"] = (
        totals["White"] / moves["White"] if moves["White"] else 0.0
    )
    counts["Black"]["avg_cpl"] = (
        totals["Black"] / moves["Black"] if moves["Black"] else 0.0
    )
    return counts


def annotate_game_worker(
    base_fen: str,
    move_list: list[chess.Move],
    stop_event: threading.Event,
    out_queue: queue.Queue,
    current_id: int,
    time_limit: float,
    worker_count: int,
    annotation_metric: str = "cpl",
):
    """Annotate all moves in a game."""
    try:
        start_time = time.monotonic()
        base_board = chess.Board(base_fen)
        include_wdl = annotation_metric == "wdl"
        eval_result = evaluate_positions(
            base_board,
            move_list,
            time_limit=time_limit,
            workers=worker_count,
            stop_event=stop_event,
            include_wdl=include_wdl,
        )
        if include_wdl:
            evals, wdl_scores = eval_result
        else:
            evals = eval_result
            wdl_scores = []

        if stop_event.is_set() or len(evals) <= 1:
            return

        label_annotations: dict[int, str] = {}
        display_annotations: dict[int, str] = {}
        cpl_by_ply: dict[int, int] = {}

        board_copy = chess.Board(base_fen)
        for ply in range(1, len(evals)):
            board_copy.push(move_list[ply - 1])
            prev_cp = clamp_score(evals[ply - 1])
            curr_cp = clamp_score(evals[ply])
            delta = curr_cp - prev_cp
            mover_is_white = (ply % 2) == 1
            delta_for_mover = delta if mover_is_white else -delta
            cpl_cp = max(0, -int(delta_for_mover))
            cpl_by_ply[ply] = cpl_cp

            if board_copy.is_checkmate():
                # Checkmate is always marked as OK - don't add any annotation
                # (no entry in label_annotations means it's counted as "OK")
                pass
            elif include_wdl and wdl_scores:
                prev_wdl = wdl_scores[ply - 1]
                curr_wdl = wdl_scores[ply]
                # Skip WDL-based annotation if either score is None
                if prev_wdl is not None and curr_wdl is not None:
                    wdl_delta = curr_wdl - prev_wdl
                    wdl_delta_for_mover = wdl_delta if mover_is_white else -wdl_delta
                    label = classify_wdl_delta(wdl_delta_for_mover)
                    if label:
                        # Track all labels for summary statistics
                        label_annotations[ply] = label
                        # Only display errors (not Best/Excellent/Good) in moves table
                        if label in ["??", "?", "?!"]:
                            display_annotations[ply] = (
                                f"{label} ({wdl_delta_for_mover:.2f})"
                            )
            else:
                label = classify_delta(delta_for_mover)
                if label:
                    # For CPL-based annotation, only errors are labeled anyway
                    display_annotations[ply] = f"{label} ({cpl_cp})"
                    label_annotations[ply] = label

        summary = summarize_annotations(label_annotations, cpl_by_ply, len(move_list))
        summary["meta"] = {"duration_sec": time.monotonic() - start_time}
        out_queue.put(
            (
                current_id,
                display_annotations,
                label_annotations,  # Add label_annotations for per-move display
                summary,
                evals,
                wdl_scores if include_wdl else [],
            )
        )
    except Exception:
        out_queue.put((current_id, {}, {}, {}, [], []))


def stream_analysis_worker(
    fen_str: str,
    prev_fen_str: str | None,
    stop_event: threading.Event,
    out_queue: queue.Queue,
    current_id: int,
    mover_is_white: bool,
    think_time: float,
    multipv: int,
    engine_threads: int,
):
    """Stream analysis updates for a position."""
    try:
        board_obj = chess.Board(fen_str)
        prev_board = chess.Board(prev_fen_str) if prev_fen_str else None

        for (
            delta_cp,
            lines,
            best_move,
            prev_pv,
            wdl_score,
            prev_wdl_score,
            done,
        ) in stream_analysis(
            board_obj,
            time_limit=think_time,
            multipv=multipv,
            threads=engine_threads,
            stop_event=stop_event,
            best_move_board=prev_board,
        ):
            if stop_event.is_set():
                break

            if delta_cp is None:
                out_queue.put(
                    (
                        current_id,
                        None,
                        lines,
                        best_move,
                        prev_pv,
                        wdl_score,
                        prev_wdl_score,
                        done,
                    )
                )
                continue

            # Convert white-POV delta to mover CPL for display
            delta_for_mover = delta_cp if mover_is_white else -delta_cp
            cpl = max(0, -delta_for_mover)
            out_queue.put(
                (
                    current_id,
                    cpl,
                    lines,
                    best_move,
                    prev_pv,
                    wdl_score,
                    prev_wdl_score,
                    done,
                )
            )
    except Exception as exc:
        out_queue.put(
            (current_id, f"Engine unavailable: {exc}", [], None, None, None, None, True)
        )
