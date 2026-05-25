import threading

import pytest

pytest.importorskip("chess")

import chess

from llm.commentary import (
    CommentaryEvent,
    CommentaryResult,
    build_commentary_context,
    build_commentary_messages,
    has_usable_engine_context,
    parse_commentary,
    stream_commentary,
)


_SAMPLE_OUTPUT = """## Summary
White keeps the initiative after a forcing move.

## Engine View
The top line keeps pressure on f7 and limits Black's development.

## Candidate Moves
- Bc4 with a direct attack on f7
- d4 to open the center while Black is behind

## Risks
- Overextending the queen can lose tempi
- Ignoring development may let Black consolidate

## Commentary
White should keep the initiative and develop with tempo.
"""


def test_has_usable_engine_context_requires_pv_and_no_engine_error():
    assert has_usable_engine_context("CPL: 42", ["+0.30 — Nf3 Nc6"]) is True
    assert has_usable_engine_context("CPL: …", ["+0.30 — Nf3 Nc6"]) is False
    assert has_usable_engine_context("Engine unavailable: boom", ["+0.30 — Nf3 Nc6"]) is False
    assert has_usable_engine_context("CPL: 42", []) is False


def test_parse_commentary_extracts_sections():
    result = parse_commentary(_SAMPLE_OUTPUT)

    assert result.summary == "White keeps the initiative after a forcing move."
    assert result.engine_view.startswith("The top line keeps pressure")
    assert result.candidate_moves == [
        "Bc4 with a direct attack on f7",
        "d4 to open the center while Black is behind",
    ]
    assert result.risks == [
        "Overextending the queen can lose tempi",
        "Ignoring development may let Black consolidate",
    ]
    assert "develop with tempo" in result.commentary_markdown


def test_parse_commentary_degrades_on_partial_output():
    result = parse_commentary("Practical move. Keep developing and avoid drifting.")

    assert result.summary == "Practical move. Keep developing and avoid drifting."
    assert result.engine_view == ""
    assert result.candidate_moves == []
    assert result.risks == []
    assert result.commentary_markdown == "Practical move. Keep developing and avoid drifting."


def test_build_commentary_messages_include_position_context():
    board = chess.Board()
    board.push_san("e4")
    board.push_san("e5")
    board.push_san("Nf3")
    context = build_commentary_context(
        board,
        ply=3,
        sans=["e4", "e5", "Nf3"],
        eval_text="CPL: 35",
        pv_lines=["+0.45 — Bc4 Nc6 d3"],
        prior_pv_lines=["+0.30 — Nf3 Nc6 Bb5"],
        wdl=0.58,
        prev_wdl=0.52,
        headers={"white": "Alpha", "black": "Beta", "date": "2026.01.04"},
    )

    messages = build_commentary_messages(context)
    user_message = messages[1]["content"]

    assert context.move_history == ["e4", "e5", "Nf3"]
    assert "Recent SAN history: e4 e5 Nf3" in user_message
    assert "Eval line: CPL: 35" in user_message
    assert "Expected score (ES/WDL) is also White POV and ranges from 0.00 to 1.00." in user_message
    assert "Current PV eval (White POV): +0.45" in user_message
    assert "Prior PV eval (White POV): +0.30" in user_message
    assert "Eval delta from prior to current (White POV): +0.15" in user_message
    assert "Eval delta caused by played move (mover POV): +0.15" in user_message
    assert "Current ES/WDL (White POV): 0.58" in user_message
    assert "Prior ES/WDL (White POV): 0.52" in user_message
    assert "ES/WDL delta caused by played move (mover POV): +0.06" in user_message
    assert "+0.45 — Bc4 Nc6 d3" in user_message
    assert "date: 2026.01.04" in user_message


def test_stream_commentary_yields_deltas_and_complete(monkeypatch):
    board = chess.Board()
    context = build_commentary_context(
        board,
        ply=0,
        sans=[],
        eval_text="CPL: 0",
        pv_lines=["+0.20 — e4 e5 Nf3"],
        prior_pv_lines=[],
        wdl=0.5,
        prev_wdl=None,
        headers={},
    )

    class StubClient:
        def __init__(self, config):
            self.config = config

        def stream_chat(self, messages, *, stop_event=None):
            yield "## Summary\n"
            yield "Start position is balanced.\n\n## Commentary\nDevelop normally."

    monkeypatch.setattr(
        "llm.commentary.commentary_runtime_status",
        lambda: (object(), None),
    )
    monkeypatch.setattr("llm.commentary.OpenAICompatibleClient", StubClient)

    events = list(stream_commentary(context, stop_event=threading.Event()))

    assert [event.kind for event in events] == ["delta", "delta", "complete"]
    assert events[-1].result == CommentaryResult(
        summary="Start position is balanced.",
        engine_view="",
        candidate_moves=[],
        risks=[],
        commentary_markdown="Develop normally.",
        raw_text="## Summary\nStart position is balanced.\n\n## Commentary\nDevelop normally.",
    )


def test_stream_commentary_yields_cancelled_when_stop_event_is_set(monkeypatch):
    board = chess.Board()
    context = build_commentary_context(
        board,
        ply=0,
        sans=[],
        eval_text="CPL: 0",
        pv_lines=["+0.20 — e4 e5 Nf3"],
        prior_pv_lines=[],
        wdl=0.5,
        prev_wdl=None,
        headers={},
    )
    stop_event = threading.Event()
    stop_event.set()

    class StubClient:
        def __init__(self, config):
            self.config = config

        def stream_chat(self, messages, *, stop_event=None):
            yield "ignored"

    monkeypatch.setattr(
        "llm.commentary.commentary_runtime_status",
        lambda: (object(), None),
    )
    monkeypatch.setattr("llm.commentary.OpenAICompatibleClient", StubClient)

    events = list(stream_commentary(context, stop_event=stop_event))

    assert events == [CommentaryEvent(kind="cancelled")]
