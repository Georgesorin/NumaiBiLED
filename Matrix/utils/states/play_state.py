from ._abs_state import GameState
import time
from ..tile import Tile
from ..ui.colors import *

from ..scaling.spawn_rules import SpawnRules
import math

class PlayState(GameState):
    """Main gameplay: keep all platforms alive by pressing them before timeout."""

    def __init__(self, settings, spawn_rules, round_num=1):
        self.settings = settings
        self.spawn_rules = spawn_rules
        self.round_num = round_num
        self.round_timer_curr = 0.0
        self.round_duration = settings.get_round_timer(round_num)
        self.border_frac = 0.0
        self.border_hold = 0.0

    def enter(self, engine):
        self.round_timer_curr = 0.0
        keep_alive = self.settings.get_tile_timeout(self.round_num)
        for ent in engine.entities:
            if isinstance(ent, Tile):
                ent.timeout_duration = keep_alive
                ent.last_pressed_time = time.time()
        # Reset border color to blue immediately when entering play
        engine.draw_rect_outline_scaled(0, 0, 16, 32, BLUE, 1.0, thickness=2)
        self.border_frac = 0.0
        # Hold the blue border for a short time to avoid visual flash
        self.border_hold = 0.15

    def update(self, engine, dt: float):
        self.round_timer_curr += dt
        engine.clear()

        pressed_xy = engine.get_pressed_xy()

        for ent in engine.entities:
            if isinstance(ent, Tile) and ent.alive:
                for px, py in pressed_xy:
                    if ent.contains_tile(px, py):
                        ent.press()
                        break

        for ent in engine.entities:
            if isinstance(ent, Tile) and ent.alive:
                if ent.should_kill:
                    ent.alive = False
                    return ("end", {"reason": "timeout", "round_num": self.round_num})

        for ent in engine.entities:
            if isinstance(ent, Tile) and ent.alive:
                c = ent.get_color()
                for tx, ty in ent.get_position():
                    engine.set_pixel(tx, ty, *c)

        # r_text = f"R{self.round_num}"
        # engine.draw_text_small(r_text, 10, 0, WHITE)

        round_frac = min(1.0, self.round_timer_curr / self.round_duration)

        # If we're still in the initial hold period, keep border blue.
        if self.border_hold > 0.0:
            self.border_hold = max(0.0, self.border_hold - dt)
            engine.draw_rect_outline_scaled(0, 0, 16, 32, BLUE, 1.0, thickness=2)
        else:
            # Smooth the visual border fraction using exponential smoothing
            # `tau` is the time constant in seconds; larger tau => slower smoothing.
            tau = 0.6
            alpha = 1.0 - math.exp(-dt / tau) if dt > 0 else 0.0
            self.border_frac += (round_frac - self.border_frac) * alpha

            # Border acts as the timer: color shifts from BLUE -> YELLOW and brightness increases.
            r = int(BLUE[0] + self.border_frac * (YELLOW[0] - BLUE[0]))
            g = int(BLUE[1] + self.border_frac * (YELLOW[1] - BLUE[1]))
            b = int(BLUE[2] + self.border_frac * (YELLOW[2] - BLUE[2]))
            border_color = (r, g, b)
            brighten_factor = 1.0 + self.border_frac * 1.0
            engine.draw_rect_outline_scaled(0, 0, 16, 32, border_color, brighten_factor, thickness=2)

        if self.round_timer_curr >= self.round_duration:
            return ("spawn", {"round_num": self.round_num + 1})

    def exit(self, engine):
        pass