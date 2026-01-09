# Chess Lab

An interactive chess analysis workbench built with Python Shiny. It streams Stockfish analysis, annotates games by centipawn loss or expected score (WDL), and visualizes evaluations over time.

![License](https://img.shields.io/badge/license-GPL--3.0-blue.svg)
![Python](https://img.shields.io/badge/python-3.12-blue.svg)

## Features

### Core Functionality
- PGN import from file upload or text paste
- Interactive SVG board with arrows for last move and engine best move
- Streaming Stockfish evaluation with MultiPV and per-move deltas
- Move annotation by centipawn loss (CPL) or expected score (WDL)
- Evaluation graph and move summary after full-game annotation
- Theme picker and keyboard navigation

### Analysis Capabilities
- Per-move CPL deltas with live PVs and expected score (WDL) display
- Move quality labels:
  - CPL mode: `??` (≥300), `?` (≥150), `?!` (≥70), `OK` (otherwise)
  - WDL mode: `??` (≥0.20 loss), `?` (≥0.10), `?!` (≥0.05), `Good` (≥0.02), `Excellent` (>0.00), `Best` (no loss)
- Summary table with per-side counts and average CPL
- Prior-ply PV comparison and best-move arrows

### Configuration Options
- Engine lines (MultiPV 1-8)
- Engine time per move (0.3, 1, 3, 10 seconds)
- CPU threads (1-8)
- Evaluation metric (CPL or ES/WDL)
- Theme selection

## Installation

### Prerequisites
- Python 3.12
- Conda

### Setup with Conda

1. Clone the repository:
```bash
git clone https://github.com/zyf0717/chess-lab.git
cd chess-lab
```

2. Create and activate the conda environment:
```bash
conda env create -f requirements.yml
conda activate chess-lab
```

3. Run the application:
```bash
shiny run --reload --port 8008 ./apps/shiny/app.py
```

4. Open your browser to `http://localhost:8008`

5. Alternatively, you can run with:
```bash
python ./apps/shiny/chess_lab.py
```

## Project Structure

```
chess-lab/
├── apps/
│   └── shiny/
│       ├── app.py              # Main application entry point
│       ├── app_ui.py           # UI layout and styling
│       ├── app_server.py       # Server logic and reactive components
│       ├── chess_lab.py        # Optional Python entry point
│       ├── utils/              # Utility modules
│       │   ├── __init__.py     # Module exports
│       │   ├── game_utils.py   # PGN parsing and game utilities
│       │   ├── chart_utils.py  # Plotly chart generation
│       │   ├── ui_helpers.py   # UI rendering helpers
│       │   └── state_utils.py  # State management utilities
│       ├── analysis/           # Chess analysis modules
│       │   ├── __init__.py     # Module exports
│       │   ├── analysis_engine.py  # Move annotation and evaluation
│       │   └── stockfish.py    # Stockfish engine integration
│       └── tests/              # Unit tests
├── data/
│   └── pgn/                    # Sample PGN game files
├── cron.sh                     # Optional local runner script
├── requirements.yml            # Conda environment specification
├── LICENSE                     # GPL-3.0 license
└── README.md                   # This file
```

## Usage

### Loading a Game

1. Upload a PGN file using the file picker
2. Paste PGN text directly into the text area
3. The game loads automatically and analysis begins

### Navigation

- First Move: Jump to starting position
- Previous/Next Move: Navigate one move at a time
- Last Move: Jump to final position
- Move Table: Click any move to jump directly to that position
- Keyboard shortcuts: left/right (single ply), up/down (two plies)
- Click the evaluation graph to jump to a ply

### Analysis Configuration

- Engine Lines: Analyze multiple best-move candidates (MultiPV)
- Engine Time: Longer duration produces more accurate evaluation
- CPU Threads: Higher values increase analysis throughput

### Move Annotation

Click "Annotate Game" to run a full analysis. The system evaluates each position with Stockfish, calculates deltas, assigns labels by the selected metric, and populates the summary table and evaluation graph.

## Architecture

### Module Overview

#### Core Application
- **`app.py`**: Main application entry point that combines UI and server components
- **`app_ui.py`**: Complete user interface including sidebar controls, board display, move list table, analysis panels, and game metadata

#### Server Logic
- **`app_server.py`**: Core server with reactive programming, application state management, user interaction handling, real-time analysis streaming, and UI rendering coordination

#### Utilities (`utils/`)
- **`game_utils.py`**: PGN parsing, metadata extraction, board position management, and move formatting
- **`chart_utils.py`**: Plotly evaluation graph generation with interactive features
- **`ui_helpers.py`**: Reusable UI rendering functions for tables, lists, and formatted output
- **`state_utils.py`**: Application state management and parameter validation helpers

#### Analysis (`analysis/`)
- **`analysis_engine.py`**: Move quality classification, game annotation, summary stats, and threaded analysis workers
- **`stockfish.py`**: Stockfish integration with automatic binary download, multi-platform support, position evaluation, and MultiPV analysis streaming

## Technical Details

### Engine Integration

The application automatically downloads the appropriate Stockfish binary on first run. Supported platforms: Linux (x86_64, aarch64), macOS (Intel, Apple Silicon), and Windows (x86_64).

Override behavior with:
- `STOCKFISH_PATH` to point to a local binary
- `STOCKFISH_URL` to provide an alternate download URL

### Performance Optimization

- Threaded analysis prevents UI blocking
- Streaming results provide real-time evaluation updates
- Concurrent evaluation enables parallel position analysis
- Reactive programming minimizes unnecessary state updates

### Move Quality Formula

Centipawn loss is calculated as:
```
CPL = max(0, -(eval_after - eval_before))
```

Expected score (WDL) is computed from Stockfish W/D/L counts:
```
ES = (wins + 0.5 * draws) / (wins + draws + losses)
```

## Dependencies

Core dependencies:
- `shiny` - Web application framework
- `chess` - Python chess library
- `shinyswatch` - Theme support
- `pandas` - Data manipulation
- `pydantic` - Data validation
- `plotly` - Evaluation graph
- `shinywidgets`/`anywidget` - Plotly widget support

See `requirements.yml` for complete list.

## Tests

```bash
pytest ./apps/shiny/tests
```

## Contributing

Contributions are welcome. Please submit a Pull Request.

## License

This project is licensed under the GNU General Public License v3.0 - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- [Stockfish](https://stockfishchess.org/) - Open-source chess engine
- [python-chess](https://python-chess.readthedocs.io/) - Chess library
- [Shiny for Python](https://shiny.posit.co/py/) - Web framework

## Author

zyf0717 - [@zyf0717](https://github.com/zyf0717)

---

Note: Internet connection required on first run to download the platform-appropriate Stockfish binary.
