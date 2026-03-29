from ._abs_state import GameState
import time
from ..tile import Tile
from ..ui.colors import *

from ..scaling.spawn_rules import SpawnRules

_sfx_pressed = None
_sfx_timeout = None
_sfx_loaded = False

def _load_sfx():
    global _sfx_pressed, _sfx_timeout, _sfx_loaded
    if _sfx_loaded: return
    try:
        import pygame
        import os
        if not pygame.mixer.get_init():
            pygame.mixer.init()
        base = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'assets', 'sfx'))
        p1 = os.path.join(base, 'tile_pressed.wav')
        p2 = os.path.join(base, 'tile_fade.wav')
        if os.path.exists(p1):
            _sfx_pressed = pygame.mixer.Sound(p1)
        if os.path.exists(p2):
            _sfx_timeout = pygame.mixer.Sound(p2)
        _sfx_loaded = True
    except Exception:
        pass

DARK_BLUE = (0, 0, 100)

def _build_thick_border_one_lap(board_w, board_h, thickness):
    """One clockwise lap; each step along the frame adds `thickness` deep pixels."""
    w, h = board_w, board_h
    t = thickness
    pts = []
    for x in range(w):
        for k in range(t):
            pts.append((x, k))
    for y in range(t, h - t):
        for k in range(t):
            pts.append((w - 1 - k, y))
    for x in range(w - 1, -1, -1):
        for k in range(t):
            pts.append((x, h - 1 - k))
    for y in range(h - t - 1, t - 1, -1):
        for k in range(t):
            pts.append((k, y))
    return pts


_THICK_BORDER_16x32 = _build_thick_border_one_lap(16, 32, thickness=2)

class PlayState(GameState):
    """Main gameplay: keep all platforms alive by pressing them before timeout."""

    def __init__(self, settings, spawn_rules, round_num=1):
        self.settings = settings
        self.spawn_rules = spawn_rules
        self.round_num = round_num
        self.round_timer_curr = 0.0
        self.round_duration = settings.get_round_timer(round_num)
        self.border_path = _THICK_BORDER_16x32
        self.border_path_len = len(self.border_path)

    def enter(self, engine):
        _load_sfx()
        self.round_timer_curr = 0.0
        keep_alive = self.settings.get_tile_timeout(self.round_num)
        for ent in engine.entities:
            if isinstance(ent, Tile):
                ent.timeout_duration = keep_alive
                ent.last_pressed_time = time.time()

    def update(self, engine, dt: float):
        self.round_timer_curr += dt
        engine.clear()

        held_xy = engine.get_held_xy()

        for ent in engine.entities:
            if isinstance(ent, Tile) and ent.alive:
                for px, py in held_xy:
                    if ent.contains_tile(px, py):
                        if time.time() - ent.last_pressed_time > 0.2:
                            if _sfx_pressed:
                                try:
                                    _sfx_pressed.play()
                                except Exception:
                                    pass
                        ent.press()
                        break

        for ent in engine.entities:
            if isinstance(ent, Tile) and ent.alive:
                if ent.should_kill:
                    if _sfx_timeout:
                        try:
                            _sfx_timeout.play()
                        except Exception:
                            pass
                    ent.alive = False
                    return ("end", {"reason": "timeout", "round_num": self.round_num})

        for ent in engine.entities:
            if isinstance(ent, Tile) and ent.alive:
                c = ent.get_color()
                for tx, ty in ent.get_position():
                    engine.set_pixel(tx, ty, *c)

        round_frac = min(1.0, self.round_timer_curr / self.round_duration)

        filled = int(round_frac * self.border_path_len)
        filled = filled - (filled % 2)

        tr = round_frac
        r = int(DARK_BLUE[0] + tr * (CYAN[0] - DARK_BLUE[0]))
        g = int(DARK_BLUE[1] + tr * (CYAN[1] - DARK_BLUE[1]))
        b = int(DARK_BLUE[2] + tr * (CYAN[2] - DARK_BLUE[2]))

        for i in range(filled):
            px, py = self.border_path[i]
            engine.set_pixel(px, py, r, g, b)

        if self.round_timer_curr >= self.round_duration:
            return ("spawn", {"round_num": self.round_num + 1})

    def exit(self, engine):
        pass