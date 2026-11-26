# Chess Lab

Chess Lab is a Python Shiny workbench for playing and analyzing chess. Import a PGN to stream Stockfish evaluations, compare candidate moves, and annotate the game. Play against Stockfish and send the resulting position to Analysis or export the game as PGN.

## Quick start

From the repository root, create the Conda environment and start Chess Lab.

```bash
conda env create -f environment.yml
conda activate chess-lab
shiny run --port 8008 apps/shiny/chess_lab.py
```

Open [Chess Lab](http://localhost:8008). On the first engine search, Chess Lab downloads Stockfish if a local binary is unavailable. To use your own binary, see the [Stockfish setup](docs/usage.md#stockfish-setup).

## Documentation

- [User guide](docs/usage.md) covers PGN import, navigation, evaluation metrics, Play, and Stockfish setup.
- [Architecture and development](docs/architecture.md) covers the position analysis API, worker lifecycles, and tests.
- [LLM commentary](docs/commentary.md) covers configuration, the request payload, and streamed responses.
- [BinProp experiment](docs/experiments/binprop.md) records the archived commentary experiment.

## License

Chess Lab is by [zyf0717](https://github.com/zyf0717) and is licensed under [GPL-3.0](LICENSE).
