from state_utils import get_input_params, reset_game_state


class DummyInput:
    def __init__(self, think_time, engine_threads, multipv) -> None:
        self._think_time = think_time
        self._engine_threads = engine_threads
        self._multipv = multipv

    def think_time(self):
        return self._think_time

    def engine_threads(self):
        return self._engine_threads

    def multipv(self):
        return self._multipv


class DummyReactive:
    def __init__(self) -> None:
        self.value = None

    def set(self, value):
        self.value = value


def test_get_input_params_parses_and_clamps():
    params = get_input_params(DummyInput("0.05", "12", "0"))
    assert params["think_time"] == 0.1
    assert params["threads"] == 8
    assert params["multipv"] == 1


def test_reset_game_state_sets_defaults():
    reactive_values = {
        "game": DummyReactive(),
        "moves": DummyReactive(),
        "sans": DummyReactive(),
        "ply": DummyReactive(),
        "analysis_ready": DummyReactive(),
        "eval": DummyReactive(),
        "pv": DummyReactive(),
        "annotations": DummyReactive(),
        "summary": DummyReactive(),
        "annotation_status": DummyReactive(),
        "evals": DummyReactive(),
        "engine_move": DummyReactive(),
        "info": DummyReactive(),
    }

    reset_game_state(reactive_values)

    assert reactive_values["game"].value is None
    assert reactive_values["moves"].value == []
    assert reactive_values["sans"].value == []
    assert reactive_values["ply"].value == 0
    assert reactive_values["analysis_ready"].value is False
    assert reactive_values["eval"].value == "CPL: --"
    assert reactive_values["pv"].value == []
    assert reactive_values["annotations"].value == {}
    assert reactive_values["summary"].value == {}
    assert reactive_values["annotation_status"].value == "idle"
    assert reactive_values["evals"].value == []
    assert reactive_values["engine_move"].value is None
    assert reactive_values["info"].value["white"] == "Unknown"
