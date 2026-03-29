"""
Keep Alive (Game 1) — touch control panel + scoreboard via UDP/Tkinter.
Run from the Matrix folder: python3 Game1_DualScreen.py
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
    BOARD_WIDTH,
    FRAME_DATA_LENGTH,
)
from utils.data.network import load_config
from utils.master import GameMaster
from utils.scaling import GameSettings, SpawnRules
from utils.states import (
    GameStartState,
    InitialTilePatternState,
    TileSpawnState,
    PlayState,
    GameOverState,
)
from utils.ui.gui_dual_displays import (
    DualRuntimeCtx,
    MATRIX_UDP_GAME_BIND,
    MATRIX_UDP_GUI_BIND,
    MatrixGameDisplays,
    cleanup_matrix_game,
    run_gui_udp_loop,
)

transitions = {
    "start": lambda settings, spawn_rules, **kwargs: GameStartState(settings, spawn_rules, **kwargs),
    "initial_spawn": lambda settings, spawn_rules, **kwargs: InitialTilePatternState(settings, spawn_rules, **kwargs),
    "spawn": lambda settings, spawn_rules, **kwargs: TileSpawnState(settings, spawn_rules, **kwargs),
    "play": lambda settings, spawn_rules, **kwargs: PlayState(settings, spawn_rules, **kwargs),
    "end": lambda settings, spawn_rules, **kwargs: GameOverState(settings, spawn_rules, **kwargs),
}


def _state_game1(game):
    if game is None:
        return {
            "state": "WAITING",
            "turn": None,
            "scores": [],
            "winner": None,
            "detail": "Choose players and difficulty, then Run game.",
            "scores_label": "—",
        }
    st = game.engine.state
    name = type(st).__name__ if st else "UNKNOWN"
    detail_parts = []
    round_num = getattr(st, "round_num", None)
    if round_num is not None:
        detail_parts.append(f"Round: {round_num}")
    if name == "PlayState":
        dur = getattr(st, "round_duration", 0) or 1
        t = getattr(st, "round_timer_curr", 0)
        detail_parts.append(f"Round time: {max(0, dur - t):.1f}s / {dur:.1f}s")
    elif name == "GameOverState":
        detail_parts.append(f"Reason: {getattr(st, 'reason', '')}")
        detail_parts.append(f"Rounds survived: {getattr(st, 'round_num', 0)}")

    scores_label = "—"
    if name == "PlayState" and round_num is not None:
        scores_label = f"Current round: {round_num}"
    elif name == "GameOverState":
        scores_label = f"Last round: {getattr(st, 'round_num', 0)}"

    return {
        "state": name,
        "turn": None,
        "scores": [],
        "winner": None,
        "winner_text": "",
        "show_winner": False,
        "detail": "\n".join(detail_parts) if detail_parts else f"Players: {game.settings.player_count}",
        "scores_label": scores_label,
    }


def _start_game1(ctx: DualRuntimeCtx, players: int, difficulty: int) -> None:
    if ctx.game is not None and ctx.game.running:
        return
    if ctx.game is not None and not ctx.game.running:
        cleanup_matrix_game(ctx, FRAME_DATA_LENGTH)

    diff_names = ["easy", "medium", "hard"]
    d = min(3, max(1, int(difficulty)))
    difficulty_key = diff_names[d - 1]
    settings = GameSettings(int(players), difficulty_key)
    spawn_rules = SpawnRules(settings, BOARD_WIDTH)

    def make_start():
        return GameStartState(settings, spawn_rules)

    ctx.game = GameMaster(make_start, settings, spawn_rules, transitions)
    ctx.net = NetworkManager(ctx.game, config=load_config())
    ctx.net.start_bg()
    threading.Thread(target=game_thread_func, args=(ctx.game,), daemon=True).start()


def _on_command(ctx: DualRuntimeCtx, cmd: str, data: dict) -> None:
    if cmd == "start":
        pl = int(data.get("players", 2))
        pl = min(6, max(2, pl))
        diff = int(data.get("difficulty", 2))
        _start_game1(ctx, pl, diff)
    elif cmd == "restart":
        if ctx.game is not None:
            ctx.game.restart()
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
        control_title="Keep Alive — Control",
        scoreboard_title="Keep Alive — Scoreboard",
        min_players=2,
        max_players=6,
    )
    threading.Thread(
        target=run_gui_udp_loop,
        args=(ctx, MATRIX_UDP_GAME_BIND, MATRIX_UDP_GUI_BIND, _state_game1, _on_command),
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
