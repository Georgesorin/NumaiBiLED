"""
Tkinter dual-screen control panel + scoreboard, synced with the game over UDP
(same pattern as external EvilEye-style games: game binds GAME_BIND_PORT, GUI binds GUI_BIND_PORT).
"""

from __future__ import annotations

import json
import queue
import re
import socket
import subprocess
import sys
import threading
import time
import tkinter as tk
import tkinter.font as tkfont
from typing import Any, Callable, Optional, Tuple

LOCAL_IP = "127.0.0.1"

# (x, y, width, height, is_primary)
MonitorInfo = Tuple[int, int, int, int, bool]


def _enum_monitors_windows() -> list[MonitorInfo]:
    """Enumerate monitors via Win32 (primary flag from MONITORINFO)."""
    if sys.platform != "win32":
        return []
    try:
        import ctypes
        from ctypes import wintypes

        user32 = ctypes.windll.user32

        class RECT(ctypes.Structure):
            _fields_ = [
                ("left", ctypes.c_long),
                ("top", ctypes.c_long),
                ("right", ctypes.c_long),
                ("bottom", ctypes.c_long),
            ]

        class MONITORINFO(ctypes.Structure):
            _fields_ = [
                ("cbSize", wintypes.DWORD),
                ("rcMonitor", RECT),
                ("rcWork", RECT),
                ("dwFlags", wintypes.DWORD),
            ]

        MONITORINFOF_PRIMARY = 1
        results: list[MonitorInfo] = []

        MonitorEnumProc = ctypes.WINFUNCTYPE(
            ctypes.c_bool,
            wintypes.HMONITOR,
            wintypes.HDC,
            ctypes.POINTER(RECT),
            wintypes.LPARAM,
        )

        def _cb(h_monitor, _hdc, _lprc, _data):
            mi = MONITORINFO()
            mi.cbSize = ctypes.sizeof(MONITORINFO)
            if not user32.GetMonitorInfoW(h_monitor, ctypes.byref(mi)):
                return True
            r = mi.rcMonitor
            w = r.right - r.left
            h = r.bottom - r.top
            primary = bool(mi.dwFlags & MONITORINFOF_PRIMARY)
            results.append((int(r.left), int(r.top), int(w), int(h), primary))
            return True

        cb = MonitorEnumProc(_cb)
        user32.EnumDisplayMonitors(None, None, cb, 0)
        return results
    except Exception:
        return []


def _enum_monitors_xrandr() -> list[MonitorInfo]:
    """Linux/X11: parse `xrandr --query` (no primary flag → first is treated as primary later)."""
    try:
        out = subprocess.check_output(
            ["xrandr", "--query"],
            text=True,
            timeout=4,
            stderr=subprocess.DEVNULL,
        )
    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
        return []
    found: list[MonitorInfo] = []
    for line in out.splitlines():
        parts = line.split()
        if len(parts) < 2 or parts[1] != "connected":
            continue
        m = re.search(r"(\d+)x(\d+)\+(\d+)\+(\d+)", line)
        if not m:
            continue
        w, h, x, y = map(int, m.groups())
        is_primary = bool(re.search(r"\bprimary\b", line))
        found.append((x, y, w, h, is_primary))
    return found


def _enum_monitors() -> list[MonitorInfo]:
    mons = _enum_monitors_windows()
    if mons:
        return mons
    return _enum_monitors_xrandr()


def _pick_primary_secondary(
    monitors: list[MonitorInfo],
) -> tuple[Optional[Tuple[int, int, int, int]], Optional[Tuple[int, int, int, int]]]:
    """Return (primary_rect, secondary_rect) as (x,y,w,h); secondary None if single monitor."""
    if not monitors:
        return None, None
    primary_t = next((m for m in monitors if m[4]), None)
    if primary_t is None:
        primary_t = min(monitors, key=lambda m: (m[0], m[1]))
    px, py, pw, ph, _ = primary_t
    primary_rect = (px, py, pw, ph)
    others = [m for m in monitors if m != primary_t]
    if not others:
        return primary_rect, None
    sx, sy, sw, sh, _ = others[0]
    return primary_rect, (sx, sy, sw, sh)

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


def _process_udp_command(
    ctx: DualRuntimeCtx,
    on_command: Callable[[DualRuntimeCtx, str, dict], None],
    data: bytes,
) -> None:
    try:
        cmd_data = json.loads(data.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return
    raw = cmd_data.get("cmd")
    if raw is None:
        return
    cmd = raw.strip().lower() if isinstance(raw, str) else raw
    if cmd:
        on_command(ctx, cmd, cmd_data)


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
            gui_sock.settimeout(0.1)
            data, _ = gui_sock.recvfrom(65536)
            _process_udp_command(ctx, on_command, data)
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
        self._ui_scale = 1.0
        self._fonts: dict[str, tkfont.Font] = {}

        self._control_outer = tk.Frame(self.root, bg=self._panel_bg)
        self._control_outer.pack(fill=tk.BOTH, expand=True)
        self._control_parent = tk.Frame(self._control_outer, bg=self._panel_bg)
        self._control_parent.place(relx=0.5, rely=0.5, anchor="center")

        self._make_fonts(1.0, 1.0)
        self._setup_control_panel(control_title, self._control_parent)
        self._setup_scoreboard(scoreboard_title)

        self.listener_thread = threading.Thread(target=self._listen_to_game, daemon=True)
        self.listener_thread.start()
        self.process_queue()
        self.root.after(100, self._apply_fullscreen_layout)
        self.root.after(350, self._apply_centered_scaled_layout)

    def _apply_fullscreen_layout(self) -> None:
        """Primary monitor: control fullscreen. Secondary: scoreboard fullscreen (Windows + Linux)."""
        if not self.gui_running:
            return
        try:
            self.root.update_idletasks()
            primary, secondary = _pick_primary_secondary(_enum_monitors())
            if primary and secondary:
                px, py, pw, ph = primary
                sx, sy, sw, sh = secondary
                self.root.geometry(f"{pw}x{ph}+{px}+{py}")
                self.root.deiconify()
                self.root.lift()
                self.root.attributes("-fullscreen", True)
                self.score_window.geometry(f"{sw}x{sh}+{sx}+{sy}")
                self.score_window.deiconify()
                self.score_window.lift()
                self.score_window.attributes("-fullscreen", True)
            elif primary:
                px, py, pw, ph = primary
                self.root.geometry(f"{pw}x{ph}+{px}+{py}")
                self.root.attributes("-fullscreen", True)
                half = max(pw // 2, 1)
                self.score_window.attributes("-fullscreen", False)
                self.score_window.geometry(f"{pw - half}x{ph}+{px + half}+{py}")
            else:
                sw = self.root.winfo_screenwidth()
                sh = self.root.winfo_screenheight()
                self.root.geometry(f"{sw}x{sh}+0+0")
                self.root.attributes("-fullscreen", True)
                half = max(sw // 2, 1)
                self.score_window.attributes("-fullscreen", False)
                self.score_window.geometry(f"{sw - half}x{sh}+{half}+0")
        except tk.TclError:
            pass
        self.root.after(120, self._apply_centered_scaled_layout)

    def _make_fonts(self, scale_ctrl: float, scale_sb: float) -> None:
        def f(n: int, bold: bool, sc: float) -> tkfont.Font:
            ps = max(8, int(n * sc))
            return tkfont.Font(family="Arial", size=ps, weight="bold" if bold else "normal")

        self._fonts = {
            "title": f(17, True, scale_ctrl),
            "section": f(11, False, scale_ctrl),
            "player_btn": f(13, True, scale_ctrl),
            "diff_btn": f(11, True, scale_ctrl),
            "run": f(14, True, scale_ctrl),
            "exit": f(12, True, scale_ctrl),
            "sb_state": f(20, True, scale_sb),
            "sb_turn": f(21, True, scale_sb),
            "sb_detail": f(13, False, scale_sb),
            "sb_scores": f(15, False, scale_sb),
            "sb_winner": f(22, True, scale_sb),
        }

    def _apply_centered_scaled_layout(self) -> None:
        """Scale fonts from each window size; panels stay centered via place(..., relx/rely 0.5)."""
        if not self.gui_running:
            return
        try:
            self.root.update_idletasks()
            rw = max(self.root.winfo_width(), 1)
            rh = max(self.root.winfo_height(), 1)
            if rw < 80 or rh < 80:
                self.root.after(100, self._apply_centered_scaled_layout)
                return
            sc = max(0.65, min(2.0, min(rw, rh) / 640.0))
            self._ui_scale = sc

            self.score_window.update_idletasks()
            sw = max(self.score_window.winfo_width(), 1)
            sh = max(self.score_window.winfo_height(), 1)
            ssb = max(0.65, min(2.0, min(sw, sh) / 640.0)) if sw >= 80 and sh >= 80 else sc

            self._make_fonts(sc, ssb)

            for w, key in (
                (getattr(self, "_lbl_control_title", None), "title"),
                (getattr(self, "_lbl_players", None), "section"),
                (getattr(self, "_lbl_difficulty", None), "section"),
                (getattr(self, "_btn_run", None), "run"),
                (getattr(self, "_btn_exit", None), "exit"),
            ):
                if w is not None and key in self._fonts:
                    w.config(font=self._fonts[key])

            for btn in self.player_buttons:
                btn.config(font=self._fonts["player_btn"])
            for btn in self.diff_buttons:
                btn.config(font=self._fonts["diff_btn"])

            for w, key in (
                (self.lbl_state, "sb_state"),
                (self.lbl_turn, "sb_turn"),
                (self.lbl_detail, "sb_detail"),
                (self.lbl_scores, "sb_scores"),
                (self.lbl_winner, "sb_winner"),
            ):
                if w is not None and key in self._fonts:
                    w.config(font=self._fonts[key])
        except tk.TclError:
            pass

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

    def _setup_control_panel(self, control_title: str, parent: tk.Widget):
        self._lbl_control_title = tk.Label(
            parent,
            text=control_title,
            font=self._fonts["title"],
            bg=self._panel_bg,
            fg="#dfe6e9",
        )
        self._lbl_control_title.pack(pady=(18, 10))

        self._lbl_players = tk.Label(
            parent,
            text="Players",
            font=self._fonts["section"],
            bg=self._panel_bg,
            fg="#74b9ff",
        )
        self._lbl_players.pack(pady=(8, 2))

        self.players_var = tk.IntVar(value=self.min_players)
        self.player_buttons = []
        btn_frame = tk.Frame(parent, bg=self._panel_bg)
        btn_frame.pack()
        for i in range(self.min_players, self.max_players + 1):
            btn = tk.Button(
                btn_frame,
                text=str(i),
                font=self._fonts["player_btn"],
                width=3,
                height=1,
                cursor="hand2",
                command=lambda num=i: self._select_players(num),
            )
            self._style_player_btn(btn, i == self.min_players)
            btn.pack(side=tk.LEFT, padx=4, pady=4)
            self.player_buttons.append(btn)

        self._lbl_difficulty = tk.Label(
            parent,
            text="Difficulty",
            font=self._fonts["section"],
            bg=self._panel_bg,
            fg="#fd79a8",
        )
        self._lbl_difficulty.pack(pady=(16, 2))

        self.difficulty_var = tk.IntVar(value=2)
        self.diff_buttons = []
        d_frame = tk.Frame(parent, bg=self._panel_bg)
        d_frame.pack()
        labels = ["Easy", "Normal", "Hard"]
        for idx, lab in enumerate(labels, start=1):
            btn = tk.Button(
                d_frame,
                text=lab,
                font=self._fonts["diff_btn"],
                width=9,
                height=2,
                cursor="hand2",
                command=lambda d=idx: self._select_difficulty(d),
            )
            self._style_diff_btn(btn, idx, idx == 2)
            btn.pack(side=tk.LEFT, padx=5, pady=6)
            self.diff_buttons.append(btn)

        act = tk.Frame(parent, bg=self._panel_bg)
        act.pack(fill=tk.X, padx=28, pady=(20, 8))

        self._btn_run = tk.Button(
            act,
            text="▶  Run game",
            font=self._fonts["run"],
            bg="#00b894",
            fg="white",
            activebackground="#00cec9",
            activeforeground="#1e272e",
            relief=tk.RAISED,
            bd=3,
            cursor="hand2",
            pady=10,
            command=self.send_start,
        )
        self._btn_run.pack(fill=tk.X, pady=(0, 10))

        self._btn_exit = tk.Button(
            act,
            text="✕  Exit",
            font=self._fonts["exit"],
            bg="#2d3436",
            fg="#ff7675",
            activebackground="#636e72",
            activeforeground="#ff7675",
            relief=tk.FLAT,
            bd=0,
            cursor="hand2",
            pady=8,
            command=self.send_quit,
        )
        self._btn_exit.pack(fill=tk.X)

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
        self.score_window.configure(bg="#000000")

        score_outer = tk.Frame(self.score_window, bg="black")
        score_outer.pack(fill=tk.BOTH, expand=True)
        score_body = tk.Frame(score_outer, bg="black")
        score_body.place(relx=0.5, rely=0.5, anchor="center")

        self.lbl_state = tk.Label(
            score_body,
            text="Waiting for start…",
            font=self._fonts["sb_state"],
            bg="black",
            fg="#fdcb6e",
        )
        self.lbl_state.pack(pady=16)

        self.lbl_turn = tk.Label(
            score_body,
            text="",
            font=self._fonts["sb_turn"],
            bg="black",
            fg="#74b9ff",
        )
        self.lbl_turn.pack(pady=6)

        self.lbl_detail = tk.Label(
            score_body,
            text="",
            font=self._fonts["sb_detail"],
            bg="black",
            fg="#b2bec3",
            justify=tk.LEFT,
        )
        self.lbl_detail.pack(pady=8, padx=12, anchor="center")

        self.lbl_scores = tk.Label(
            score_body,
            text="",
            font=self._fonts["sb_scores"],
            bg="black",
            fg="#dfe6e9",
            justify=tk.CENTER,
        )
        self.lbl_scores.pack(pady=12, padx=12, anchor="center")

        self.lbl_winner = tk.Label(
            score_body,
            text="",
            font=self._fonts["sb_winner"],
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
