# LLM Commentary Payload

This documents the outbound request shape used by the Chess Lab commentary layer in `apps/shiny/llm/`.

## Transport

- Method: `POST`
- URL: `LLM_BASE_URL + LLM_CHAT_PATH`
- Default path: `/v1/chat/completions`
- Current local router path: `/smart`
- Streaming: always `true`

## Headers

Always sent:

```http
Content-Type: application/json
```

Sent only when configured:

```http
Authorization: Bearer <LLM_API_KEY>
X-Reasoning-Effort: <low|medium|high>
```

## JSON Body

The client sends this OpenAI-compatible shape:

```json
{
  "model": "Qwen/Qwen3.6-35B-A3B",
  "messages": [
    {
      "role": "system",
      "content": "You are a chess analyst writing concise move commentary for a GUI. Use the supplied engine context only; do not invent tactics or lines. Return exactly these Markdown sections in order: ## Summary, ## Engine View, ## Candidate Moves, ## Risks, ## Commentary. Use bullet lists for Candidate Moves and Risks."
    },
    {
      "role": "user",
      "content": "Comment on the current chess position using the engine context below.\nKeep the summary and commentary concise and practical.\n\nCurrent position\n- Ply: 12\n- Played move: Nf3\n- Side to move: Black\n- FEN: rnbqkb1r/pppp1ppp/5n2/4p3/4P3/5N2/PPPP1PPP/RNBQKB1R b KQkq - 1 2\n- Recent SAN history: e4 e5 Nf3\n- Eval line: CPL: 35\n- Current CPL: 35\n- Current expected score: 0.58\n\nCurrent PVs\n- +0.45 — Bc4 Nc6 d3\n- +0.31 — Bb5 a6 Ba4\n\nPrior ply best line\n- +0.30 — Nf3 Nc6 Bb5\n\nGame headers\n- black: Beta\n- date: 2026.01.04\n- white: Alpha\n"
    }
  ],
  "stream": true,
  "temperature": 0.2,
  "max_tokens": 2000
}
```

## Message Construction

The request always contains exactly two messages:

1. `system`
   - fixed instruction to act as a chess analyst
   - fixed output contract with these Markdown sections:
     - `## Summary`
     - `## Engine View`
     - `## Candidate Moves`
     - `## Risks`
     - `## Commentary`
2. `user`
   - generated from live app state for the selected ply

## User Prompt Fields

The user message is built from `CommentaryContext` and includes:

- `ply`
- `played move` SAN for the selected ply, or `Start position`
- `side to move`
- `fen`
- `recent SAN history`
  - last `history_window` plies, default `8`
- `eval line`
  - raw UI eval string such as `CPL: 35`
- `current CPL`
  - parsed integer from the eval line when available
- `current expected score`
  - WDL-derived value when available
- `prior expected score`
  - prior-ply White-POV ES/WDL when available
- `wdl delta`
  - both White-POV and mover-POV changes from prior ply to current ply
- `current PVs`
  - one bullet per live engine PV line
- `prior ply best line`
  - one bullet per prior-ply PV line
- `current PV eval score`
  - extracted from the first live PV line when present
- `prior PV eval score`
  - extracted from the first prior-ply PV line when present
- `eval delta`
  - both White-POV and mover-POV numeric change when both PV evals are numeric
- `game headers`
  - filtered to non-empty string values not equal to `Unknown`

The user prompt also includes an explicit metric guide:

- PV eval is White POV
- ES/WDL is White POV in `[0.00, 1.00]`
- CPL is non-negative and mover-centric
- changes should be interpreted in both White POV and mover POV

## Streaming Response Handling

The client consumes SSE and only renders assistant text from:

- `choices[0].delta.content`
- `choices[0].message.content` as fallback in non-delta responses

It ignores:

- `delta.reasoning`
- `delta.reasoning_content`
- malformed SSE frames

The final accumulated text is then parsed back into:

- `summary`
- `engine_view`
- `candidate_moves`
- `risks`
- `commentary_markdown`

## Config Inputs

The payload and route are controlled by root `.env`:

```dotenv
LLM_BASE_URL=http://127.0.0.1:12340
LLM_CHAT_PATH=/smart
LLM_MODEL=Qwen/Qwen3.6-35B-A3B
LLM_API_KEY=
LLM_REASONING_EFFORT=low
LLM_TIMEOUT_SEC=30
LLM_MAX_TOKENS=2000
LLM_TEMPERATURE=0.2
```

## Source of Truth

- Request config: `apps/shiny/llm/config.py`
- HTTP request assembly: `apps/shiny/llm/client.py`
- Prompt assembly: `apps/shiny/llm/commentary.py`
