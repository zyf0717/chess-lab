# Architecture and development

## Application layout

The Python app lives under `apps/shiny/`. Its Conda dependencies are declared in [environment.yml](../environment.yml).

| Module | Responsibility |
| --- | --- |
| [`chess_lab.py`](../apps/shiny/chess_lab.py) | Loads `.env` and starts the Shiny app. |
| [`app_ui.py`](../apps/shiny/app_ui.py) and [`app_server.py`](../apps/shiny/app_server.py) | Render the interface and manage the active game, selected ply, and workers for each session. |
| [`analysis/position.py`](../apps/shiny/analysis/position.py) | Streams single-position updates and computes mover-relative CPL. |
| [`analysis/analysis_engine.py`](../apps/shiny/analysis/analysis_engine.py) | Annotates full games and summarizes move quality. |
| [`analysis/stockfish.py`](../apps/shiny/analysis/stockfish.py) | Resolves the Stockfish binary, runs UCI searches, and reads scores and candidate lines. |
| [`utils/`](../apps/shiny/utils/) | Parses PGNs, reconstructs boards, and formats analysis for the UI. |
| [`llm/`](../apps/shiny/llm/) | Builds commentary prompts and consumes responses from the configured endpoint. |

## Position analysis

Call `analyze_position()` with the current `chess.Board`, its optional predecessor, and the engine settings. Pass boards with their move history so Stockfish can account for repetitions. Each `PositionAnalysisUpdate` contains the current and prior PV lines and White expected scores when available, the current best move in UCI notation, and the last mover's CPL. Successful streams end with `done=True`. The preceding board is needed to compute CPL. [Position analysis API](../apps/shiny/analysis/position.py)

To run the stream directly from Python, use the Conda environment and run this from the repository root. Configure `STOCKFISH_PATH` in the process environment if you need a specific binary.

```bash
PYTHONPATH=apps/shiny python - <<'PY'
import chess
from analysis import analyze_position

previous = chess.Board()
current = previous.copy()
current.push_san("e4")

for update in analyze_position(current, previous, time_limit=0.3, multipv=2, threads=1):
    if update.done:
        print(update.centipawn_loss, update.pv_lines)
PY
```

### Scheduling and cancellation

Shiny debounces position and engine setting changes and consumes a dedicated queue for each search. When the request changes, Shiny signals cancellation and detaches the old queue so stale updates cannot overwrite the current position. Cancellation is cooperative. A predecessor search already in progress can run until its time limit. Other Python callers can pass a `threading.Event` and close the generator if they stop consuming it early. Engine stream exceptions propagate to the caller. [Shiny server](../apps/shiny/app_server.py)

Full-game annotation runs separately. It evaluates each ply and can distribute positions across multiple Stockfish processes. The result updates the move table, summary, and evaluation graph together. [Annotation worker](../apps/shiny/analysis/analysis_engine.py)

## Local development

During development, activate `chess-lab` and run Shiny with reload from the repository root.

```bash
shiny run --reload --port 8008 apps/shiny/chess_lab.py
```

The test suite uses mocked engine results and a real Stockfish search.

```bash
python -m pytest apps/shiny/tests
```

Chess Lab uses [Shiny for Python](https://shiny.posit.co/py/), [python-chess](https://python-chess.readthedocs.io/), and [Stockfish](https://stockfishchess.org/).
