"""
Tkinter dual-screen control panel + scoreboard, synced with the game over UDP
(same pattern as external EvilEye-style games: game binds GAME_BIND_PORT, GUI binds GUI_BIND_PORT).
"""

from __future__ import annotations

import json
import queue
import socket
import threading
import time
import tkinter as tk
from typing import Any, Callable, Optional

LOCAL_IP = "127.0.0.1"

# Bidirectional UDP (game ↔ Tk): game binds GAME, sends state to GUI; GUI binds GUI, sends cmds to GAME.
# Pair 4626 / 7800; GUI listen port uses 7800 + 1 (7801) so the base 7800 stays the documented “state” side.
MATRIX_UDP_GAME_BIND = 4626
MATRIX_UDP_GUI_BIND = 7801  # 7800 + 1


class DualRuntimeCtx:
    """Shared between the UDP loop and the Tk app."""

    def __init__(self):
        self.running = True
        self.game = None
        self.net = None
        self.quit_from_remote = threading.Event()


def run_gui_udp_loop(
    ctx: DualRuntimeCtx,
    game_bind_port: int,
    gui_bind_port: int,
    state_builder: Callable[[Any], dict],
    on_command: Callable[[DualRuntimeCtx, str, dict], None],
    sleep_s: float = 0.1,
    post_tick: Optional[Callable[[DualRuntimeCtx], None]] = None,
) -> None:
    """
    Game side: bind `game_bind_port`, push JSON state to `gui_bind_port`, read commands on the same socket.
    """
    gui_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    gui_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        gui_sock.bind((LOCAL_IP, game_bind_port))
    except OSError:
        gui_sock.close()
        raise
    gui_sock.settimeout(0.1)

    while ctx.running:
        state_data = state_builder(ctx.game)
        try:
            gui_sock.sendto(json.dumps(state_data).encode("utf-8"), (LOCAL_IP, gui_bind_port))
        except Exception:
            pass

        try:
            data, _ = gui_sock.recvfrom(4096)
            cmd_data = json.loads(data.decode("utf-8"))
            cmd = cmd_data.get("cmd")
            if cmd:
                on_command(ctx, cmd, cmd_data)
        except socket.timeout:
            pass
        except Exception:
            pass

        if post_tick is not None:
            post_tick(ctx)

        time.sleep(sleep_s)

    gui_sock.close()


def cleanup_matrix_game(ctx: DualRuntimeCtx, frame_len: int) -> None:
    if ctx.net is not None:
        try:
            ctx.net.send_packet(b"\x00" * frame_len)
        except Exception:
            pass
        ctx.net.running = False
        ctx.net = None
    ctx.game = None


class MatrixGameDisplays:
    def __init__(
        self,
        root: tk.Tk,
        ctx: DualRuntimeCtx,
        gui_bind_port: int,
        game_bind_port: int,
        control_title: str,
        scoreboard_title: str,
        min_players: int = 2,
        max_players: int = 6,
    ):
        self.root = root
        self.ctx = ctx
        self.gui_bind_port = gui_bind_port
        self.game_bind_port = game_bind_port

        self.root.title(control_title)
        self.root.geometry("440x580")
        self.root.configure(bg="#1e272e")

        self._panel_bg = "#1e272e"
        self._player_idle = "#485460"
        self._player_sel = "#00d8d6"
        self._diff_idle = "#586272"
        self._diff_colors = {1: "#55efc4", 2: "#a29bfe", 3: "#fab1a0"}

        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind((LOCAL_IP, gui_bind_port))
        self.sock.settimeout(0.1)

        self.msg_queue: queue.Queue = queue.Queue()
        self.gui_running = True
        self.min_players = min_players
        self.max_players = max_players

        self._setup_control_panel(control_title)
        self._setup_scoreboard(scoreboard_title)

        self.listener_thread = threading.Thread(target=self._listen_to_game, daemon=True)
        self.listener_thread.start()
        self.process_queue()

    def _style_player_btn(self, btn: tk.Button, selected: bool) -> None:
        btn.config(
            bg=self._player_sel if selected else self._player_idle,
            fg="#1e272e" if selected else "#dfe6e9",
            activebackground=self._player_sel if selected else "#5d656d",
            activeforeground="#1e272e" if selected else "#dfe6e9",
            relief=tk.FLAT,
            bd=0,
            highlightthickness=2 if selected else 0,
            highlightbackground="#00cec9",
            highlightcolor="#00cec9",
        )

    def _style_diff_btn(self, btn: tk.Button, idx: int, selected: bool) -> None:
        c = self._diff_colors[idx]
        btn.config(
            bg=c if selected else self._diff_idle,
            fg="#1e272e" if selected else "#dfe6e9",
            activebackground=c if selected else "#6c7888",
            activeforeground="#1e272e",
            relief=tk.RAISED if selected else tk.GROOVE,
            bd=3 if selected else 2,
        )

    def _setup_control_panel(self, control_title: str):
        title = tk.Label(
            self.root,
            text=control_title,
            font=("Arial", 17, "bold"),
            bg=self._panel_bg,
            fg="#dfe6e9",
        )
        title.pack(pady=(18, 10))

        tk.Label(
            self.root,
            text="Players",
            font=("Arial", 11),
            bg=self._panel_bg,
            fg="#74b9ff",
        ).pack(pady=(8, 2))

        self.players_var = tk.IntVar(value=self.min_players)
        self.player_buttons: list[tk.Button] = []
        btn_frame = tk.Frame(self.root, bg=self._panel_bg)
        btn_frame.pack()
        for i in range(self.min_players, self.max_players + 1):
            btn = tk.Button(
                btn_frame,
                text=str(i),
                font=("Arial", 13, "bold"),
                width=3,
                height=1,
                cursor="hand2",
                command=lambda num=i: self._select_players(num),
            )
            self._style_player_btn(btn, i == self.min_players)
            btn.pack(side=tk.LEFT, padx=4, pady=4)
            self.player_buttons.append(btn)

        tk.Label(
            self.root,
            text="Difficulty",
            font=("Arial", 11),
            bg=self._panel_bg,
            fg="#fd79a8",
        ).pack(pady=(16, 2))

        self.difficulty_var = tk.IntVar(value=2)
        self.diff_buttons: list[tk.Button] = []
        d_frame = tk.Frame(self.root, bg=self._panel_bg)
        d_frame.pack()
        labels = ["Easy", "Normal", "Hard"]
        for idx, lab in enumerate(labels, start=1):
            btn = tk.Button(
                d_frame,
                text=lab,
                font=("Arial", 11, "bold"),
                width=9,
                height=2,
                cursor="hand2",
                command=lambda d=idx: self._select_difficulty(d),
            )
            self._style_diff_btn(btn, idx, idx == 2)
            btn.pack(side=tk.LEFT, padx=5, pady=6)
            self.diff_buttons.append(btn)

        act = tk.Frame(self.root, bg=self._panel_bg)
        act.pack(fill=tk.X, padx=28, pady=(20, 8))

        tk.Button(
            act,
            text="▶  Run game",
            font=("Arial", 14, "bold"),
            bg="#00b894",
            fg="white",
            activebackground="#00cec9",
            activeforeground="#1e272e",
            relief=tk.RAISED,
            bd=3,
            cursor="hand2",
            pady=10,
            command=self.send_start,
        ).pack(fill=tk.X, pady=(0, 10))

        tk.Button(
            act,
            text="↺  Reset session",
            font=("Arial", 12, "bold"),
            bg="#6c5ce7",
            fg="#dfe6e9",
            activebackground="#a29bfe",
            activeforeground="#1e272e",
            relief=tk.SUNKEN,
            bd=3,
            cursor="hand2",
            pady=8,
            command=self.send_restart,
        ).pack(fill=tk.X, pady=(0, 10))

        tk.Button(
            act,
            text="✕  Exit",
            font=("Arial", 12, "bold"),
            bg="#2d3436",
            fg="#ff7675",
            activebackground="#636e72",
            activeforeground="#ff7675",
            relief=tk.FLAT,
            bd=0,
            cursor="hand2",
            pady=8,
            command=self.send_quit,
        ).pack(fill=tk.X)

    def _select_players(self, num: int):
        self.players_var.set(num)
        for i, btn in enumerate(self.player_buttons):
            n = self.min_players + i
            self._style_player_btn(btn, n == num)

    def _select_difficulty(self, d: int):
        self.difficulty_var.set(d)
        for i, btn in enumerate(self.diff_buttons, start=1):
            self._style_diff_btn(btn, i, i == d)

    def _setup_scoreboard(self, scoreboard_title: str):
        self.score_window = tk.Toplevel(self.root)
        self.score_window.title(scoreboard_title)
        self.score_window.geometry("520x560")
        self.score_window.configure(bg="#000000")

        self.lbl_state = tk.Label(
            self.score_window,
            text="Waiting for start…",
            font=("Arial", 20, "bold"),
            bg="black",
            fg="#fdcb6e",
        )
        self.lbl_state.pack(pady=16)

        self.lbl_turn = tk.Label(
            self.score_window,
            text="",
            font=("Arial", 21, "bold"),
            bg="black",
            fg="#74b9ff",
        )
        self.lbl_turn.pack(pady=6)

        self.lbl_detail = tk.Label(
            self.score_window,
            text="",
            font=("Arial", 13),
            bg="black",
            fg="#b2bec3",
            justify=tk.LEFT,
        )
        self.lbl_detail.pack(pady=8, padx=12, anchor="w")

        self.lbl_scores = tk.Label(
            self.score_window,
            text="",
            font=("Arial", 15),
            bg="black",
            fg="#dfe6e9",
            justify=tk.LEFT,
        )
        self.lbl_scores.pack(pady=12, padx=12, anchor="w")

        self.lbl_winner = tk.Label(
            self.score_window,
            text="",
            font=("Arial", 22, "bold"),
            bg="black",
            fg="#55efc4",
        )
        self.lbl_winner.pack(pady=12)

    def send_command(self, cmd_dict: dict):
        try:
            self.sock.sendto(
                json.dumps(cmd_dict).encode("utf-8"),
                (LOCAL_IP, self.game_bind_port),
            )
        except Exception as e:
            print(f"Send command error: {e}")

    def send_start(self):
        self.send_command(
            {
                "cmd": "start",
                "players": self.players_var.get(),
                "difficulty": self.difficulty_var.get(),
            }
        )

    def send_restart(self):
        self.send_command({"cmd": "restart"})

    def send_quit(self):
        self.send_command({"cmd": "quit"})
        self.gui_running = False
        self.ctx.running = False
        try:
            self.root.destroy()
        except Exception:
            pass

    def _listen_to_game(self):
        while self.gui_running and self.ctx.running:
            try:
                data, _ = self.sock.recvfrom(8192)
                state = json.loads(data.decode("utf-8"))
                self.msg_queue.put(state)
            except socket.timeout:
                continue
            except Exception:
                pass

    def process_queue(self):
        if self.ctx.quit_from_remote.is_set():
            self.gui_running = False
            try:
                self.root.destroy()
            except Exception:
                pass
            return

        try:
            while True:
                state = self.msg_queue.get_nowait()
                self.update_scoreboard(state)
        except queue.Empty:
            pass

        if self.gui_running and self.ctx.running:
            self.root.after(100, self.process_queue)

    def update_scoreboard(self, state: dict):
        game_state = state.get("state", "")
        self.lbl_state.config(text=f"State: {game_state}")

        turn = state.get("turn")
        if turn:
            self.lbl_turn.config(text=f"Turn: player {turn}")
        else:
            self.lbl_turn.config(text="")

        detail = state.get("detail", "")
        self.lbl_detail.config(text=detail or "")

        scores = state.get("scores") or []
        if scores:
            lines = "\n".join(f"Player {i + 1}: {s}" for i, s in enumerate(scores))
            self.lbl_scores.config(text=f"Scores\n{lines}")
        else:
            self.lbl_scores.config(text=state.get("scores_label", "—"))

        winner_text = state.get("winner_text", "")
        winner = state.get("winner")
        if winner_text:
            self.lbl_winner.config(text=str(winner_text))
        elif state.get("show_winner") and winner is not None:
            self.lbl_winner.config(text=f"Player {winner} wins!")
        else:
            self.lbl_winner.config(text="")
