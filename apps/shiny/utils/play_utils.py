from __future__ import annotations

import chess
import chess.engine

from analysis.stockfish import ensure_stockfish_binary, format_pv, format_score

DEFAULT_ENGINE_TIME = 0.15


def board_from_moves(moves: list[chess.Move], ply: int | None = None) -> chess.Board:
    """Build a board from a move list up to ply."""
    board = chess.Board()
    limit = len(moves) if ply is None else max(0, min(ply, len(moves)))
    for move in moves[:limit]:
        board.push(move)
    return board


def engine_best_move(
    board: chess.Board,
    skill_level: int,
    think_time: float = DEFAULT_ENGINE_TIME,
) -> tuple[chess.Move | None, chess.engine.PovScore | None, list[chess.Move]]:
    """Return the engine's best move, score, and PV."""
    path = ensure_stockfish_binary()
    engine = chess.engine.SimpleEngine.popen_uci(str(path))
    try:
        engine.configure({"Skill Level": max(0, min(int(skill_level), 20))})
        limit = chess.engine.Limit(time=think_time)
        info = engine.analyse(board, limit)
        pv = info.get("pv", [])
        move = pv[0] if pv else None
        return move, info.get("score"), pv
    finally:
        engine.quit()

def format_engine_eval(
    board: chess.Board,
    score: chess.engine.PovScore | None,
    pv: list[chess.Move],
) -> str:
    """Format an engine evaluation line."""
    if score is None:
        return "Eval: --"
    score_text = format_score(score.pov(chess.WHITE))
    pv_text = format_pv(board, pv) if pv else ""
    if pv_text:
        return f"Eval: {score_text} — {pv_text}"
    return f"Eval: {score_text}"
