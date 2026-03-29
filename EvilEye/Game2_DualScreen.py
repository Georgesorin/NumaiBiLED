"""
Dispatcher (Game 2) — touch control panel + scoreboard via UDP/Tkinter.
Run from the EvilEye folder: python3 Game2_DualScreen.py
"""

from __future__ import annotations

import os
import sys
import threading

_sys_root = os.path.dirname(os.path.abspath(__file__))
if _sys_root not in sys.path:
    sys.path.insert(0, _sys_root)

import tkinter as tk

from utils.data.network import load_config, configure_from_discovery, NetworkManager
from utils.master.master import GameMaster, game_thread_func
from utils.scaling.game_settings import DispatcherSettings
from utils.states import (
    DispatcherSetupState,
    DispatcherCountdownState,
    DispatcherPlayState,
    GameOverState,
)
from utils.ui.gui_dual_displays import (
    DualRuntimeCtx,
    EVILEYE_UDP_GAME_BIND,
    EVILEYE_UDP_GUI_BIND,
    EvilEyeGameDisplays,
    cleanup_evileye_game,
    run_gui_udp_loop,
)

transitions = {
    "setup": lambda settings, **kwargs: DispatcherSetupState(settings, **kwargs),
    "countdown": lambda settings, **kwargs: DispatcherCountdownState(settings, **kwargs),
    "play": lambda settings, **kwargs: DispatcherPlayState(settings, **kwargs),
    "end": lambda settings, **kwargs: GameOverState(settings, **kwargs),
}


def _state_dispatcher(game):
    if game is None:
        return {
            "state": "WAITING",
            "turn": None,
            "scores": [],
            "winner": None,
            "detail": "Choose players and difficulty, then Run game.",
            "scores_label": "\u2014",
        }
    st = game.engine.state
    name = type(st).__name__ if st else "UNKNOWN"
    detail_parts = [f"Players: {game.settings.player_count}"]

    scores = []
    winner_text = ""
    show_winner = False
    scores_label = "\u2014"

    if name == "DispatcherPlayState":
        data = getattr(st, "data", None)
        if data is not None:
            detail_parts.append(f"Score: {data.score}")
            detail_parts.append(f"Time left: {max(0, data.game_timer):.1f}s")
            if data.is_crashed:
                detail_parts.append("STATUS: CRASHED!")
            scores_label = f"Score: {data.score}"
    elif name == "DispatcherCountdownState":
        detail_parts.append("Countdown\u2026")
    elif name == "GameOverState":
        show_winner = True
        score = getattr(st, "score", None)
        if score is not None:
            winner_text = f"Final score: {score}"
            scores_label = f"Final score: {score}"
        else:
            winner_text = "Game Over"

    return {
        "state": name,
        "turn": None,
        "scores": scores,
        "winner": None,
        "winner_text": winner_text,
        "show_winner": show_winner,
        "detail": "\n".join(detail_parts),
        "scores_label": scores_label,
    }


def _start_dispatcher(ctx: DualRuntimeCtx, players: int, difficulty: int) -> None:
    if ctx.game is not None and ctx.game.running:
        return
    if ctx.game is not None and not ctx.game.running:
        cleanup_evileye_game(ctx)

    diff_names = ["easy", "medium", "hard"]
    d = min(3, max(1, int(difficulty)))
    difficulty_key = diff_names[d - 1]
    settings = DispatcherSettings(int(players), difficulty_key)

    def make_start():
        return DispatcherSetupState(settings)

    ctx.game = GameMaster(make_start, settings, transitions)

    cfg_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "eye_ctrl_config.json")
    cfg = load_config(cfg_path)
    cfg, _ = configure_from_discovery(cfg, cfg_path)
    ctx.net = NetworkManager(ctx.game, config=cfg)
    ctx.net.start_bg()
    threading.Thread(target=game_thread_func, args=(ctx.game,), daemon=True).start()


def _on_command(ctx: DualRuntimeCtx, cmd: str, data: dict) -> None:
    if cmd == "start":
        pl = int(data.get("players", 4))
        diff = int(data.get("difficulty", 2))
        _start_dispatcher(ctx, pl, diff)
    elif cmd == "quit":
        ctx.running = False
        if ctx.game is not None:
            ctx.game.running = False
        cleanup_evileye_game(ctx)
        ctx.quit_from_remote.set()


def _post_tick(ctx: DualRuntimeCtx) -> None:
    if ctx.game is not None and not ctx.game.running:
        cleanup_evileye_game(ctx)


def main():
    ctx = DualRuntimeCtx()
    root = tk.Tk()
    app = EvilEyeGameDisplays(
        root,
        ctx,
        gui_bind_port=EVILEYE_UDP_GUI_BIND,
        game_bind_port=EVILEYE_UDP_GAME_BIND,
        control_title="Dispatcher \u2014 Control",
        scoreboard_title="Dispatcher \u2014 Scoreboard",
        min_players=2,
        max_players=8,
        valid_player_counts=[2, 3, 4, 6, 8],
    )
    threading.Thread(
        target=run_gui_udp_loop,
        args=(ctx, EVILEYE_UDP_GAME_BIND, EVILEYE_UDP_GUI_BIND, _state_dispatcher, _on_command),
        kwargs={"post_tick": _post_tick},
        daemon=True,
    ).start()

    def on_closing():
        ctx.running = False
        if ctx.game is not None:
            ctx.game.running = False
        cleanup_evileye_game(ctx)
        app.gui_running = False
        try:
            app.score_window.destroy()
        except Exception:
            pass
        root.destroy()

    root.protocol("WM_DELETE_WINDOW", on_closing)
    root.mainloop()
    ctx.running = False
    cleanup_evileye_game(ctx)


if __name__ == "__main__":
    main()
