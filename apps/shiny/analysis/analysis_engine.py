"""Analysis and annotation logic for chess games."""

from __future__ import annotations

import math
import queue
import threading
import time

import chess
from analysis.stockfish import (
    clamp_score,
    evaluate_positions,
    evaluate_positions_with_wdl,
    stream_analysis,
)


def classify_delta(delta_cp: int) -> str:
    """Classify move quality based on centipawn loss.

    Args:
        delta_cp: Change in evaluation (mover perspective)

    Returns:
        Annotation symbol ("??", "?", "?!", or "")
    """
    cpl = max(0, -delta_cp)
    if cpl >= 300:
        return "??"
    if cpl >= 150:
        return "?"
    if cpl >= 70:
        return "?!"
    return ""


def classify_wdl_delta(delta_wdl: float) -> str:
    """Classify move quality based on WDL expectation delta.

    Args:
        delta_wdl: Change in WDL expectation (mover perspective)

    Returns:
        Annotation symbol ("??", "?", "?!", or "")
    """
    wdl_loss = max(0.0, -delta_wdl)
    if wdl_loss >= 0.20:
        return "??"
    if wdl_loss >= 0.10:
        return "?"
    if wdl_loss >= 0.05:
        return "?!"
    return ""

def summarize_annotations(
    annotations: dict[int, str],
    metric_by_ply: dict[int, float],
    total_plies: int,
    metric_name: str = "cpl",
) -> dict[str, dict[str, int | float]]:
    """Generate summary statistics from move annotations.

    Args:
        annotations: Map of ply to annotation label
        metric_by_ply: Map of ply to average loss metric
        total_plies: Total number of plies in game
        metric_name: Metric name for summary metadata

    Returns:
        Dictionary with statistics for White and Black
    """
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
        totals[side] += metric_by_ply.get(ply, 0.0)
        label = annotations.get(ply, "")
        if label:
            counts[side][label] += 1
        else:
            neutral[side] += 1

    counts["White"]["OK"] = neutral["White"]
    counts["Black"]["OK"] = neutral["Black"]
    counts["White"]["avg_metric"] = (
        totals["White"] / moves["White"] if moves["White"] else 0.0
    )
    counts["Black"]["avg_metric"] = (
        totals["Black"] / moves["Black"] if moves["Black"] else 0.0
    )
    counts["meta"] = {"metric": metric_name}
    return counts


def calculate_estimated_elo(avg_cpl: float) -> float:
    """Estimate Elo rating from average centipawn loss.

    Args:
        avg_cpl: Average centipawn loss

    Returns:
        Estimated Elo rating
    """
    return 3100 * math.exp(-0.01 * avg_cpl)


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
    """Worker function to annotate all moves in a game.

    Args:
        base_fen: Starting FEN position
        move_list: List of moves to analyze
        stop_event: Threading event to signal stop
        out_queue: Queue to put results
        current_id: Analysis session ID
        time_limit: Time limit per position
        worker_count: Number of engine threads
    """
    try:
        start_time = time.monotonic()
        base_board = chess.Board(base_fen)
        if annotation_metric == "wdl":
            evals, wdl_values = evaluate_positions_with_wdl(
                base_board,
                move_list,
                time_limit=time_limit,
                workers=worker_count,
                stop_event=stop_event,
            )
        else:
            evals = evaluate_positions(
                base_board,
                move_list,
                time_limit=time_limit,
                workers=worker_count,
                stop_event=stop_event,
            )
            wdl_values = []

        if stop_event.is_set() or len(evals) <= 1:
            return

        label_annotations: dict[int, str] = {}
        display_annotations: dict[int, str] = {}
        metric_by_ply: dict[int, float] = {}

        for ply in range(1, len(evals)):
            mover_is_white = (ply % 2) == 1
            if annotation_metric == "wdl" and wdl_values:
                prev_wdl = wdl_values[ply - 1]
                curr_wdl = wdl_values[ply]
                delta = curr_wdl - prev_wdl
                delta_for_mover = delta if mover_is_white else -delta
                wdl_loss = max(0.0, -delta_for_mover)
                metric_by_ply[ply] = wdl_loss
                label = classify_wdl_delta(delta_for_mover)
                if label:
                    display_annotations[ply] = f"{label} ({wdl_loss:.1%})"
                    label_annotations[ply] = label
            else:
                prev_cp = clamp_score(evals[ply - 1])
                curr_cp = clamp_score(evals[ply])
                delta = curr_cp - prev_cp
                delta_for_mover = delta if mover_is_white else -delta
                cpl_cp = max(0, -int(delta_for_mover))
                metric_by_ply[ply] = cpl_cp
                label = classify_delta(delta_for_mover)
                if label:
                    display_annotations[ply] = f"{label} ({cpl_cp})"
                    label_annotations[ply] = label

        metric_name = "wdl" if annotation_metric == "wdl" else "cpl"
        summary = summarize_annotations(
            label_annotations, metric_by_ply, len(move_list), metric_name=metric_name
        )
        summary_meta = summary.setdefault("meta", {})
        summary_meta["duration_sec"] = time.monotonic() - start_time
        out_queue.put((current_id, display_annotations, summary, evals))
    except Exception:
        out_queue.put((current_id, {}, {}, []))


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
    """Worker function for streaming position analysis.

    Args:
        fen_str: FEN string of position to analyze
        prev_fen_str: FEN of previous position (for best move comparison)
        stop_event: Threading event to signal stop
        out_queue: Queue to put results
        current_id: Analysis session ID
        mover_is_white: Whether white is to move
        think_time: Analysis time limit
        multipv: Number of principal variations
        engine_threads: Number of engine threads
    """
    try:
        board_obj = chess.Board(fen_str)
        prev_board = chess.Board(prev_fen_str) if prev_fen_str else None

        for delta_cp, lines, best_move, prev_pv, done in stream_analysis(
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
                out_queue.put((current_id, None, lines, best_move, prev_pv, done))
                continue

            # Convert white-POV delta to mover CPL for display
            delta_for_mover = delta_cp if mover_is_white else -delta_cp
            cpl = max(0, -delta_for_mover)
            out_queue.put((current_id, cpl, lines, best_move, prev_pv, done))
    except Exception as exc:
        out_queue.put((current_id, f"Engine unavailable: {exc}", [], None, None, True))
