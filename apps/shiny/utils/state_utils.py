"""State helpers for the Shiny app."""

from __future__ import annotations

DEFAULT_INFO = {
    "date_only": False,
    "date": "Unknown",
    "start": "Unknown",
    "end": "Unknown",
    "duration": "Unknown",
    "white": "Unknown",
    "black": "Unknown",
    "white_elo": "Unknown",
    "black_elo": "Unknown",
}

_DEFAULT_STATE = {
    "game": None,
    "moves": list,
    "sans": list,
    "ply": 0,
    "analysis_ready": False,
    "analysis_done": False,
    "eval": "CPL: --",
    "pv": list,
    "prev_pv": list,
    "annotations": dict,
    "label_annotations": dict,
    "summary": dict,
    "annotation_status": "idle",
    "evals": list,
    "wdl_scores": list,
    "wdl": None,
    "prev_wdl": None,
    "engine_move": None,
    "info": lambda: DEFAULT_INFO.copy(),
}


def reset_game_state(reactive_values: dict) -> None:
    """Reset reactive values to defaults."""
    for key, default in _DEFAULT_STATE.items():
        if key not in reactive_values:
            continue
        value = default() if callable(default) else default
        reactive_values[key].set(value)


def _scale_resources_by_elo(elo: int) -> tuple[int, float, int]:
    """
    Scale computational resources based on ELO rating.
    Returns (threads, think_time, depth) scaled linearly from 1400-3000.

    ELO 1400: 1 thread, 0.2s, depth 5
    ELO 2200: 4 threads, 0.6s, depth 12 (midpoint)
    ELO 3000: 8 threads, 1.0s, depth 20
    """
    elo_clamped = max(1400, min(elo, 3000))
    elo_normalized = (elo_clamped - 1400) / (3000 - 1400)  # 0.0 to 1.0

    threads = 1 + int(elo_normalized * 7)  # 1 to 8
    think_time = 0.2 + elo_normalized * 0.8  # 0.2 to 1.0
    depth = 5 + int(elo_normalized * 15)  # 5 to 20

    return threads, think_time, depth


def get_input_params(input_obj) -> dict:
    """Extract and clamp engine parameters."""
    try:
        think_time = float(input_obj.think_time())
    except (TypeError, ValueError):
        think_time = 1.0
    think_time = max(0.1, min(think_time, 60.0))

    try:
        thread_count = int(input_obj.engine_threads())
    except (TypeError, ValueError):
        thread_count = 1
    thread_count = max(1, min(thread_count, 8))

    try:
        multipv = int(input_obj.multipv())
    except (TypeError, ValueError):
        multipv = 3
    multipv = max(1, min(multipv, 8))

    try:
        elo = int(input_obj.enginePlayElo())
    except (TypeError, ValueError, AttributeError):
        elo = None

    depth = None
    if elo is not None:
        elo = max(1400, min(elo, 3000))
        # Scale resources for play mode based on ELO
        thread_count, think_time, depth = _scale_resources_by_elo(elo)

    return {
        "think_time": think_time,
        "threads": thread_count,
        "multipv": multipv,
        "elo": elo,
        "depth": depth,
    }
