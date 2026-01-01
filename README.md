# Chess Lab

An interactive chess analysis platform built with Python Shiny, featuring real-time Stockfish engine analysis, move annotation, and performance metrics.

![License](https://img.shields.io/badge/license-GPL--3.0-blue.svg)
![Python](https://img.shields.io/badge/python-3.12-blue.svg)

## Features

### Core Functionality
- PGN game import from files or text input
- Interactive SVG board visualization with move highlighting
- Real-time Stockfish engine evaluation with configurable parameters
- Automatic move quality assessment (blunders, mistakes, inaccuracies)
- Multi-line principal variation analysis (MultiPV)
- Estimated Elo ratings based on average centipawn loss

### Analysis Capabilities
- Centipawn loss (CPL) tracking per move
- Move quality classification:
  - `??` Blunder (≥300 CPL)
  - `?` Mistake (≥150 CPL)
  - `?!` Inaccuracy (≥70 CPL)
  - `OK` Good move
- Player performance statistics and move quality breakdown
- Performance-based Elo estimation
- Previous position analysis comparing played moves with engine recommendations

### Configuration Options
- Engine threads (1-8)
- Analysis time per position (0.1-60 seconds)
- Number of principal variations (1-8)
- Theme selection

## Installation

### Prerequisites
- Python 3.12
- Conda (recommended) or pip

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

### Setup with pip

```bash
pip install shiny chess pandas pydantic shinyswatch
```

## Project Structure

```
chess-lab/
├── apps/
│   └── shiny/
│       ├── app.py              # Main application entry point
│       ├── app_ui.py           # UI layout and styling
│       ├── app_server.py       # Server logic and reactive components
│       ├── game_utils.py       # PGN parsing and game utilities
│       ├── analysis_engine.py  # Chess analysis and annotation logic
│       ├── analysis/
│       │   ├── __init__.py
│       │   └── stockfish.py    # Stockfish engine integration
│       └── stockfish/          # Stockfish binary (auto-downloaded)
├── data/
│   └── pgn/                    # Sample PGN game files
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

### Analysis Configuration

- Engine Threads: Increase for faster analysis (higher CPU usage)
- Think Time: Longer duration produces more accurate evaluation
- MultiPV: Analyze multiple best move candidates (1-8 lines)

### Move Annotation

Click "Annotate Moves" to perform full game analysis. The system evaluates each position with Stockfish, calculates centipawn loss per move, assigns quality symbols, generates performance statistics, and estimates player Elo ratings.

## Architecture

### Module Overview

#### `app.py`
Main application entry point that combines UI and server components.

#### `app_ui.py`
Defines the complete user interface including sidebar controls, board display, move list table, analysis output panels, and game metadata display.

#### `app_server.py`
Core server logic with reactive programming. Manages application state, handles user interactions, streams real-time analysis, coordinates move annotation, and renders UI components.

#### `game_utils.py`
Chess game utilities for PGN parsing, metadata extraction, board position management, and move formatting.

#### `analysis_engine.py`
Chess analysis engine implementing move quality classification, annotation generation, performance statistics, Elo estimation, and threading workers for analysis tasks.

#### `analysis/stockfish.py`
Stockfish integration providing automatic binary download, multi-platform support, position evaluation, MultiPV analysis streaming, and concurrent position analysis.

## Technical Details

### Engine Integration

The application automatically downloads the appropriate Stockfish binary on first run. Supported platforms: Linux (x86_64, aarch64), macOS (Intel, Apple Silicon), and Windows (x86_64).

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

Estimated Elo uses the formula:
```
Elo ≈ 3100 × e^(-0.01 × avg_CPL)
```

## Dependencies

Core dependencies:
- `shiny` - Web application framework
- `chess` - Python chess library
- `shinyswatch` - Theme support
- `pandas` - Data manipulation
- `pydantic` - Data validation

See `requirements.yml` for complete list.

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
