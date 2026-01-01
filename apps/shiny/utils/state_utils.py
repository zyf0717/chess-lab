"""State management utilities for the Shiny app."""

from __future__ import annotations


def reset_game_state(reactive_values: dict) -> None:
    """Reset all game-related reactive values to initial state.

    Args:
        reactive_values: Dictionary of reactive value objects to reset
    """
    reactive_values["game"].set(None)
    reactive_values["moves"].set([])
    reactive_values["sans"].set([])
    reactive_values["ply"].set(0)
    reactive_values["analysis_ready"].set(False)
    reactive_values["eval"].set("CPL: --")
    reactive_values["pv"].set([])
    reactive_values["annotations"].set({})
    reactive_values["summary"].set({})
    reactive_values["annotation_status"].set("idle")
    reactive_values["evals"].set([])
    reactive_values["engine_move"].set(None)
    reactive_values["info"].set(
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


def get_input_params(input_obj) -> dict:
    """Extract and validate analysis parameters from input.

    Args:
        input_obj: Shiny input object

    Returns:
        Dictionary with validated parameters
    """
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
