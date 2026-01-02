"""State helpers for the Shiny app."""

from __future__ import annotations


DEFAULT_INFO = {
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

    return {
        "think_time": think_time,
        "threads": thread_count,
        "multipv": multipv,
    }
