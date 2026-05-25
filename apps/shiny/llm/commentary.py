from __future__ import annotations

import re
import threading
from dataclasses import dataclass
from typing import Iterator

import chess

from .client import OpenAICompatibleClient, httpx_available
from .config import LLMConfig, load_llm_config

_SECTION_ORDER = (
    "Summary",
    "Engine View",
    "Candidate Moves",
    "Risks",
    "Commentary",
)
_SECTION_PATTERN = re.compile(
    r"^##\s+(Summary|Engine View|Candidate Moves|Risks|Commentary)\s*$",
    re.MULTILINE,
)
_CPL_PATTERN = re.compile(r"^CPL:\s*(-?\d+)$")


@dataclass(frozen=True, slots=True)
class CommentaryContext:
    fen: str
    ply: int
    san: str | None
    side_to_move: str
    move_history: list[str]
    eval_text: str
    cpl: int | None
    wdl: float | None
    pv_lines: list[str]
    prior_pv_lines: list[str]
    headers: dict[str, str]


@dataclass(frozen=True, slots=True)
class CommentaryResult:
    summary: str
    engine_view: str
    candidate_moves: list[str]
    risks: list[str]
    commentary_markdown: str
    raw_text: str


@dataclass(frozen=True, slots=True)
class CommentaryEvent:
    kind: str
    delta: str = ""
    result: CommentaryResult | None = None
    error: str | None = None


def commentary_runtime_status() -> tuple[LLMConfig | None, str | None]:
    config, error = load_llm_config()
    if error is not None:
        return None, error
    if not httpx_available():
        return None, "LLM commentary disabled: install httpx to enable the HTTP client."
    return config, None


def has_usable_engine_context(eval_text: str, pv_lines: list[str]) -> bool:
    if not pv_lines:
        return False
    if not eval_text:
        return False
    if eval_text == "CPL: …":
        return False
    return not eval_text.startswith("Engine unavailable")


def build_commentary_context(
    board: chess.Board,
    *,
    ply: int,
    sans: list[str],
    eval_text: str,
    pv_lines: list[str],
    prior_pv_lines: list[str],
    wdl: float | None,
    headers: dict[str, str],
    history_window: int = 8,
) -> CommentaryContext:
    start = max(0, ply - history_window)
    san = sans[ply - 1] if 0 < ply <= len(sans) else None
    context_headers = {
        key: value
        for key, value in headers.items()
        if isinstance(value, str) and value and value != "Unknown"
    }
    return CommentaryContext(
        fen=board.fen(),
        ply=ply,
        san=san,
        side_to_move="White" if board.turn == chess.WHITE else "Black",
        move_history=sans[start:ply],
        eval_text=eval_text,
        cpl=_extract_cpl(eval_text),
        wdl=wdl,
        pv_lines=list(pv_lines),
        prior_pv_lines=list(prior_pv_lines),
        headers=context_headers,
    )


def build_commentary_messages(context: CommentaryContext) -> list[dict[str, str]]:
    system_prompt = (
        "You are a chess analyst writing concise move commentary for a GUI. "
        "Use the supplied engine context only; do not invent tactics or lines. "
        "Return exactly these Markdown sections in order: "
        "## Summary, ## Engine View, ## Candidate Moves, ## Risks, ## Commentary. "
        "Use bullet lists for Candidate Moves and Risks."
    )
    user_prompt = _format_context(context)
    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]


def stream_commentary(
    context: CommentaryContext,
    *,
    stop_event: threading.Event | None = None,
) -> Iterator[CommentaryEvent]:
    config, error = commentary_runtime_status()
    if error is not None or config is None:
        yield CommentaryEvent(kind="error", error=error or "LLM commentary unavailable.")
        return

    client = OpenAICompatibleClient(config)
    chunks: list[str] = []

    try:
        for delta in client.stream_chat(
            build_commentary_messages(context), stop_event=stop_event
        ):
            if stop_event is not None and stop_event.is_set():
                yield CommentaryEvent(kind="cancelled")
                return
            chunks.append(delta)
            yield CommentaryEvent(kind="delta", delta=delta)
    except Exception as exc:  # pragma: no cover - exercised by integration tests
        if stop_event is not None and stop_event.is_set():
            yield CommentaryEvent(kind="cancelled")
            return
        yield CommentaryEvent(kind="error", error=str(exc))
        return

    if stop_event is not None and stop_event.is_set():
        yield CommentaryEvent(kind="cancelled")
        return

    raw_text = "".join(chunks).strip()
    yield CommentaryEvent(kind="complete", result=parse_commentary(raw_text))


def parse_commentary(raw_text: str) -> CommentaryResult:
    text = raw_text.strip()
    sections = {name: "" for name in _SECTION_ORDER}
    matches = list(_SECTION_PATTERN.finditer(text))

    for index, match in enumerate(matches):
        name = match.group(1)
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        sections[name] = text[start:end].strip()

    commentary_text = sections["Commentary"] or text
    summary = sections["Summary"] or _first_paragraph(commentary_text)
    engine_view = sections["Engine View"]
    candidate_moves = _parse_bullets(sections["Candidate Moves"])
    risks = _parse_bullets(sections["Risks"])

    return CommentaryResult(
        summary=summary,
        engine_view=engine_view,
        candidate_moves=candidate_moves,
        risks=risks,
        commentary_markdown=commentary_text,
        raw_text=text,
    )


def _format_context(context: CommentaryContext) -> str:
    history = " ".join(context.move_history) if context.move_history else "None"
    pv_lines = "\n".join(f"- {line}" for line in context.pv_lines) or "- None"
    prior_pv_lines = (
        "\n".join(f"- {line}" for line in context.prior_pv_lines) or "- None"
    )
    headers = (
        "\n".join(f"- {key}: {value}" for key, value in sorted(context.headers.items()))
        or "- None"
    )
    played_move = context.san or "Start position"
    cpl = str(context.cpl) if context.cpl is not None else "None"
    wdl = f"{context.wdl:.2f}" if context.wdl is not None else "None"
    return f"""Comment on the current chess position using the engine context below.
Keep the summary and commentary concise and practical.

Current position
- Ply: {context.ply}
- Played move: {played_move}
- Side to move: {context.side_to_move}
- FEN: {context.fen}
- Recent SAN history: {history}
- Eval line: {context.eval_text}
- Current CPL: {cpl}
- Current expected score: {wdl}

Current PVs
{pv_lines}

Prior ply best line
{prior_pv_lines}

Game headers
{headers}
"""


def _extract_cpl(eval_text: str) -> int | None:
    match = _CPL_PATTERN.match((eval_text or "").strip())
    if match is None:
        return None
    try:
        return int(match.group(1))
    except ValueError:
        return None


def _parse_bullets(section: str) -> list[str]:
    items: list[str] = []
    for line in section.splitlines():
        item = line.strip()
        if not item:
            continue
        if item.startswith(("- ", "* ")):
            item = item[2:].strip()
        items.append(item)
    return items


def _first_paragraph(text: str) -> str:
    for chunk in text.split("\n\n"):
        chunk = chunk.strip()
        if chunk:
            return chunk
    return ""
