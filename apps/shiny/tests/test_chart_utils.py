import pytest

plotly = pytest.importorskip("plotly")

from chart_utils import create_eval_graph


def test_create_eval_graph_placeholder_running():
    fig = create_eval_graph([], "running")
    assert fig.layout.annotations[0].text == "Evaluating..."


def test_create_eval_graph_placeholder_empty():
    fig = create_eval_graph([], "idle")
    assert (
        fig.layout.annotations[0].text
        == "Annotate the game to see the evaluation graph"
    )


def test_create_eval_graph_with_data():
    fig = create_eval_graph([0, 50, -25], "idle")
    assert len(fig.data) == 4
