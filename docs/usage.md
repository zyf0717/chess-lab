# User guide

## Analyze a game

1. In **Analysis**, upload a PGN or paste its text. Chess Lab loads the first game's main line and starts evaluating its initial position. Paste `1. e4 e5 2. Nf3 Nc6 *` to try it.
2. Use the board buttons to go to the start, previous ply, next ply, or end. A ply is one move by one side. The left and right arrow keys step one ply backward and forward. The up and down keys step two plies backward and forward. You can also select a move in the table.
3. Read **PV** for candidate lines from the current position and **Prior ply** for lines from before the selected move. The evaluation line shows centipawn loss (CPL) and expected score (ES) when the engine provides enough data.
4. Select an **Evaluation metric** and click **Annotate Game**. The move table marks mistakes, the summary reports counts and average CPL by side, and the evaluation graph plots the position score in pawns from White's perspective. Click a graph point to jump to its ply.

### Engine settings

| Setting | Effect |
| --- | --- |
| Engine lines (1–8) | Limits the number of candidate lines shown in live analysis (MultiPV). |
| Engine time (0.3, 1, 3, or 10 seconds) | Sets the time budget for each position search. Comparing a position with its predecessor takes two searches. |
| CPU threads (1–8) | Sets Stockfish threads for live analysis and the worker limit for full-game annotation. |

Once candidate lines appear, open **LLM Commentary** to request an explanation from your configured endpoint. See the [commentary setup](commentary.md#configuration).

### Evaluation and move labels

Stockfish scores and expected scores are shown from White's perspective. A positive engine score favors White. The expected score uses Stockfish's win, draw, and loss counts and ranges from 0 to 1.

```text
ES = (wins + 0.5 × draws) / (wins + draws + losses)
```

For move labels, Chess Lab measures the change from the mover's perspective. Subtract the score before the move from the score after it and reverse the sign for a Black move. Loss is `max(0, -change)`. CPL uses centipawn scores clamped to −1,000 through +1,000 before differencing. WDL uses the change in expected score. One centipawn is one hundredth of a pawn.

| Label | Centipawn loss | Expected score loss |
| --- | ---: | ---: |
| `??` | ≥ 300 | ≥ 0.20 |
| `?` | 150–299 | ≥ 0.10 and < 0.20 |
| `?!` | 70–149 | ≥ 0.05 and < 0.10 |
| Good | | ≥ 0.02 and < 0.05 |
| Excellent | | > 0 and < 0.02 |
| Best | | 0 |
| OK | < 70 | |

Full-game annotation counts a checkmating move as OK. In WDL mode the move table shows the three mistake labels, and the summary also counts Best, Excellent, and Good.

## Play against Stockfish

In **Play**, choose the engine side and Elo, then drag pieces to move. Choose **None** under **Engine plays** to move both sides. Set **Promote pawn to** before dropping a pawn on its promotion square.

- **Analyze Position** opens Analysis at the final ply of the game so far.
- **Download PGN** saves the current game as `play.pgn`.
- **Flip Board** changes orientation. **Reset Board** starts a new game.

## Stockfish setup

Chess Lab checks `STOCKFISH_PATH` for a local binary and then looks in `apps/shiny/stockfish/`. If it finds neither, it downloads and caches an archive on the first engine search. The launcher loads repository-root `.env` settings and gives existing process environment variables precedence.

| Variable | Value |
| --- | --- |
| `STOCKFISH_PATH` | Path to a local executable. Use this to select a version or run the engine offline. |
| `STOCKFISH_URL` | URL of the archive to download when no local binary is available. |

The built-in download targets Linux x86-64 with AVX2, Linux ARM64, Intel and Apple Silicon macOS, and Windows x86-64 with AVX2. Use `STOCKFISH_PATH` if your system needs a different build. The Play board loads its JavaScript and piece images from remote hosts. [Engine download targets](../apps/shiny/analysis/stockfish.py) · [Board assets](../apps/shiny/app_ui.py)
