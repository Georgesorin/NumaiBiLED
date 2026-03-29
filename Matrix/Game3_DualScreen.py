"""
Snake (Game 3) — panou control + scoreboard, UDP + Tkinter.
Rulează din folderul Matrix: python3 Game3_DualScreen.py
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
    SnakeSettings,
    load_config,
)
from utils.master import GameMaster
from utils.states import SnakeStartState, SnakePlayState, SnakeEndState
from utils.ui.gui_dual_displays import (
    DualRuntimeCtx,
    MATRIX_UDP_GAME_BIND,
    MATRIX_UDP_GUI_BIND,
    MatrixGameDisplays,
    cleanup_matrix_game,
    run_gui_udp_loop,
)

_TRANSITIONS = {
    "start": lambda s, _r, **kw: SnakeStartState(**kw),
    "play": lambda s, _r, **kw: SnakePlayState(settings=s, **kw),
    "end": lambda s, _r, **kw: SnakeEndState(**kw),
}


def _state_snake(game):
    if game is None:
        return {
            "state": "WAITING",
            "turn": None,
            "scores": [],
            "detail": "Selectează jucători și dificultate, apoi START.",
            "scores_label": "—",
        }
    st = game.engine.state
    name = type(st).__name__ if st else "UNKNOWN"
    detail = [f"Jucători: {game.settings.player_count}"]

    if name == "SnakePlayState":
        detail.append(f"HP: {game.settings.hp}/{game.settings.max_hp}")
        detail.append(f"Fructe distruse: {st.players_destroyed} · Mâncate de șarpe: {st.snake_ate}")
    elif name == "SnakeEndState":
        detail.append(f"Timp: {int(st.play_time)}s")
        detail.append(f"Fructe distruse: {st.players_destroyed} · Șarpe a mâncat: {st.snake_ate}")
        detail.append(f"Motiv: {st.reason}")

    scores_label = "—"
    if name == "SnakePlayState":
        scores_label = (
            f"Fructe distruse: {st.players_destroyed}\n"
            f"Mâncate de șarpe: {st.snake_ate}"
        )
    elif name == "SnakeEndState":
        scores_label = (
            f"Final — distruse: {st.players_destroyed}, "
            f"șarpe: {st.snake_ate}, timp {int(st.play_time)}s"
        )

    winner_text = ""
    show_winner = False
    if name == "SnakeEndState":
        show_winner = True
        winner_text = "Victorie jucători!" if st.win else "Șarpele a câștigat!"

    return {
        "state": name,
        "turn": None,
        "scores": [],
        "winner": None,
        "winner_text": winner_text,
        "show_winner": show_winner,
        "detail": "\n".join(detail),
        "scores_label": scores_label,
    }


def _start_snake(ctx: DualRuntimeCtx, players: int, difficulty: int) -> None:
    if ctx.game is not None and ctx.game.running:
        return
    if ctx.game is not None and not ctx.game.running:
        cleanup_matrix_game(ctx, FRAME_DATA_LENGTH)

    diff_map = {1: "easy", 2: "medium", 3: "hard"}
    d = min(3, max(1, int(difficulty)))
    diff_name = diff_map.get(d, "medium")
    pl = min(6, max(2, int(players)))
    settings = SnakeSettings(pl, diff_name)

    ctx.game = GameMaster(lambda: SnakeStartState(), settings, None, _TRANSITIONS)
    ctx.net = NetworkManager(ctx.game, config=load_config())
    ctx.net.start_bg()
    threading.Thread(target=game_thread_func, args=(ctx.game,), daemon=True).start()


def _on_command(ctx: DualRuntimeCtx, cmd: str, data: dict) -> None:
    if cmd == "start":
        _start_snake(ctx, int(data.get("players", 2)), int(data.get("difficulty", 2)))
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
        control_title="Snake — panou control",
        scoreboard_title="Snake — scoreboard",
        min_players=2,
        max_players=6,
    )
    threading.Thread(
        target=run_gui_udp_loop,
        args=(ctx, MATRIX_UDP_GAME_BIND, MATRIX_UDP_GUI_BIND, _state_snake, _on_command),
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
