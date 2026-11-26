# LLM commentary

Open **LLM Commentary** in Analysis once Stockfish has produced candidate lines. Chess Lab sends the selected position, engine analysis, recent moves, and available game metadata to the configured endpoint. Selecting another ply clears the panel and cancels the active commentary request.

## Configuration

Set `LLM_BASE_URL` in the repository-root `.env` to enable commentary. Existing environment variables take precedence. Optional fields can be omitted if your endpoint uses the defaults.

| Variable | Default | Purpose |
| --- | --- | --- |
| `LLM_BASE_URL` | Unset | Base URL of an OpenAI-compatible endpoint. |
| `LLM_CHAT_PATH` | `/v1/chat/completions` | Path appended to the base URL. |
| `LLM_MODEL` | Unset | Model ID if the endpoint requires one. |
| `LLM_API_KEY` | Unset | Bearer token if the endpoint requires authentication. |
| `LLM_REASONING_EFFORT` | Unset | Optional header value of `low`, `medium`, or `high`. |
| `LLM_TIMEOUT_SEC` | `30` | HTTP timeout in seconds. |
| `LLM_MAX_TOKENS` | `700` | Maximum output tokens requested. |
| `LLM_TEMPERATURE` | `0.2` | Sampling temperature requested. |

For example, a local router that selects its own model can use the following configuration.

```dotenv
LLM_BASE_URL=http://127.0.0.1:12340
LLM_CHAT_PATH=/smart
LLM_REASONING_EFFORT=low
LLM_MAX_TOKENS=2000
```

## Request

The client sends an HTTP `POST` to `LLM_BASE_URL + LLM_CHAT_PATH` with streaming enabled and `Content-Type: application/json`. It adds `Authorization: Bearer <LLM_API_KEY>` and `X-Reasoning-Effort: <low|medium|high>` when the corresponding values are configured.

### JSON body

The client sends the following OpenAI-compatible payload. The example abbreviates the user message and uses a configured output limit of 2,000 tokens.

```json
{
  "messages": [
    {
      "role": "system",
      "content": "You are a chess analyst writing concise move commentary for a GUI. Use the supplied engine context only; do not invent tactics or lines. Return exactly these Markdown sections in order: ## Summary, ## Engine View, ## Candidate Moves, ## Risks, ## Commentary. Use bullet lists for Candidate Moves and Risks."
    },
    {
      "role": "user",
      "content": "Comment on the current chess position using the engine context below.\n\nCurrent position\n- Ply: 3\n- Played move: Nf3\n- Side to move: Black\n- FEN: rnbqkbnr/pppp1ppp/8/4p3/4P3/5N2/PPPP1PPP/RNBQKB1R b KQkq - 1 2\n- Recent SAN history: e4 e5 Nf3\n\nCurrent PVs\n- +0.30 — 2... Nc6 3. Bb5\n"
    }
  ],
  "stream": true,
  "temperature": 0.2,
  "max_tokens": 2000
}
```

When `LLM_MODEL` is unset, the payload omits `model` so an endpoint such as `/smart` can route the request.

The fixed `system` message specifies the five Markdown sections. The `user` message comes from live app state for the selected ply.

### User prompt fields

`CommentaryContext` supplies the following fields.

- `ply`
- `played move` SAN for the selected ply, or `Start position`
- `last move side`
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

The prompt explains how to interpret White-relative scores, mover-relative CPL, and deltas. See [evaluation and move labels](usage.md#evaluation-and-move-labels).

## Streaming response

The client consumes server-sent events (SSE) and renders assistant text from these fields.

- `choices[0].delta.content` as a string or a list of text fragments.
- `choices[0].message.content` as a fallback within an SSE event.

The client skips reasoning fields and malformed JSON. The app parses the accumulated text into `summary`, `engine_view`, `candidate_moves`, `risks`, and `commentary_markdown`.

## Implementation

- [Configuration](../apps/shiny/llm/config.py)
- [HTTP request and SSE client](../apps/shiny/llm/client.py)
- [Prompt assembly and response parsing](../apps/shiny/llm/commentary.py)
