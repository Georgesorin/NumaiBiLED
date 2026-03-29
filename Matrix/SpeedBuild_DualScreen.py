"""
Speed Build (Memory Matrix) — control panel + scoreboard over UDP/Tkinter.
Run from the Matrix folder: python3 SpeedBuild_DualScreen.py
"""

from __future__ import annotations

import os
import sys
import threading

_sys_root = os.path.dirname(os.path.abspath(__file__))
if _sys_root not in sys.path:
    sys.path.insert(0, _sys_root)

import tkinter as tk

from utils.data import (
    NetworkManager,
    game_thread_func,
    FRAME_DATA_LENGTH,
    SpeedBuildSettings,
    load_config,
)
from utils.master import GameMaster
from utils.states import SBInitState, SBShowState, SBPlayState, SBReviewState
from utils.ui.gui_dual_displays import (
    DualRuntimeCtx,
    MATRIX_UDP_GAME_BIND,
    MATRIX_UDP_GUI_BIND,
    MatrixGameDisplays,
    cleanup_matrix_game,
    run_gui_udp_loop,
)

_CFG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "matrix_config.json")


class DummySpawnRules:
    def reset(self):
        pass


class Player:
    def __init__(self, pid, base_x, base_y):
        self.id = pid
        self.base_x = base_x
        self.base_y = base_y
        self.board = [[(0, 0, 0) for _ in range(6)] for _ in range(6)]
        self.score = 0
        self.completion_time = None


transitions = {
    "init": lambda s, sr, **k: SBInitState(s, sr, **k),
    "show": lambda s, sr, **k: SBShowState(s, sr, PlayerClass=Player, **k),
    "play": lambda s, sr, **k: SBPlayState(s, sr, **k),
    "review": lambda s, sr, **k: SBReviewState(s, sr, **k),
}


def _sb_match_scores(st):
    if not hasattr(st, "players") or not hasattr(st, "target_drawing"):
        return []
    td = st.target_drawing
    return [
        sum(1 for y in range(6) for x in range(6) if p.board[y][x] == td[y][x])
        for p in st.players
    ]


def _state_speedbuild(game):
    if game is None:
        return {
            "state": "WAITING",
            "turn": None,
            "scores": [],
            "detail": "Choose players and difficulty, then Run game.",
            "scores_label": "—",
        }
    st = game.engine.state
    name = type(st).__name__ if st else "UNKNOWN"
    settings = game.settings
    detail = [
        f"Players: {settings.player_count}",
        f"Difficulty: {settings.difficulty}",
    ]

    if hasattr(settings, "status_text") and settings.status_text:
        detail.append(f"Mode: {settings.status_text}")
    if hasattr(settings, "time_left") and not getattr(settings, "hide_timer", True):
        detail.append(f"Time left: {settings.time_left:.1f}s")

    scores = []
    winner_text = ""
    show_winner = False

    if name == "SBPlayState":
        scores = _sb_match_scores(st)
    elif name == "SBReviewState":
        scores = [p.score for p in st.players]
        show_winner = True
        if st.is_tie:
            winner_text = "Tie game!"
        elif st.winner is not None:
            winner_text = f"Winner: player {st.winner.id}"
        else:
            winner_text = "Results"

    return {
        "state": name,
        "turn": None,
        "scores": scores,
        "winner": st.winner.id if name == "SBReviewState" and st.winner is not None and not st.is_tie else None,
        "winner_text": winner_text,
        "show_winner": show_winner,
        "detail": "\n".join(detail),
        "scores_label": "Correct cells (max 36) per player" if scores else "—",
    }


def _start_speedbuild(ctx: DualRuntimeCtx, players: int, difficulty: int) -> None:
    if ctx.game is not None and ctx.game.running:
        return
    if ctx.game is not None and not ctx.game.running:
        cleanup_matrix_game(ctx, FRAME_DATA_LENGTH)

    pl = min(6, max(2, int(players)))
    diff = min(3, max(1, int(difficulty)))
    settings = SpeedBuildSettings(pl, diff)
    settings.hide_timer = True
    settings.hide_status = True
    spawn_rules = DummySpawnRules()

    def make_start():
        return SBInitState(settings, spawn_rules)

    ctx.game = GameMaster(make_start, settings, spawn_rules, transitions)
    cfg = load_config(_CFG_FILE)
    ctx.net = NetworkManager(ctx.game, config=cfg)
    ctx.net.start_bg()
    threading.Thread(target=game_thread_func, args=(ctx.game,), daemon=True).start()


def _on_command(ctx: DualRuntimeCtx, cmd: str, data: dict) -> None:
    if cmd == "start":
        _start_speedbuild(ctx, int(data.get("players", 2)), int(data.get("difficulty", 2)))
    elif cmd == "quit":
        ctx.running = False
        if ctx.game is not None:
            ctx.game.running = False
        cleanup_matrix_game(ctx, FRAME_DATA_LENGTH)
        ctx.quit_from_remote.set()


def _post_tick(ctx: DualRuntimeCtx) -> None:
    if ctx.game is not None and not ctx.game.running:
        cleanup_matrix_game(ctx, FRAME_DATA_LENGTH)


def main():
    ctx = DualRuntimeCtx()
    root = tk.Tk()
    app = MatrixGameDisplays(
        root,
        ctx,
        gui_bind_port=MATRIX_UDP_GUI_BIND,
        game_bind_port=MATRIX_UDP_GAME_BIND,
        control_title="Speed Build — Control",
        scoreboard_title="Speed Build — Scoreboard",
        min_players=2,
        max_players=6,
    )
    threading.Thread(
        target=run_gui_udp_loop,
        args=(ctx, MATRIX_UDP_GAME_BIND, MATRIX_UDP_GUI_BIND, _state_speedbuild, _on_command),
        kwargs={"post_tick": _post_tick},
        daemon=True,
    ).start()

    def on_closing():
        ctx.running = False
        if ctx.game is not None:
            ctx.game.running = False
        cleanup_matrix_game(ctx, FRAME_DATA_LENGTH)
        app.gui_running = False
        try:
            app.score_window.destroy()
        except Exception:
            pass
        root.destroy()

    root.protocol("WM_DELETE_WINDOW", on_closing)
    root.mainloop()
    ctx.running = False
    cleanup_matrix_game(ctx, FRAME_DATA_LENGTH)


if __name__ == "__main__":
    main()
