from ._abs_state import GameState
from ..scaling.spawn_rules import spawn_platforms
from ..ui.colors import *
from ..tile import Tile
import math

class TileSpawnState(GameState):
    """Spawn floor(players/2) new platforms, then transition to PlayState."""

    def __init__(self, settings, spawn_rules, round_num=1):
        self.settings = settings
        self.spawn_rules = spawn_rules
        self.round_num = round_num
        self.timer = 0.0
        self.spawned = False
        self.border_frac = 0.0

    def enter(self, engine):
        self.timer = 0.0
        self.spawned = False
        self.border_frac = 0.0

        engine.draw_rect_outline_scaled(0, 0, 16, 32, BLUE, 1.0, thickness=2)
        # self.border_frac = 0.0

    def update(self, engine, dt: float):
        self.timer += dt
        engine.clear()

        if self.timer < 1.0:
            r_text = f"{self.round_num}"
            # Center the text: board 16x32, large font 5x7 with 1px spacing
            width = len(r_text) * 6 - (1 if len(r_text) > 1 else 0)
            x = (16 - width) // 2 + 1
            y = 12
            engine.draw_text_large(r_text, x, y, YELLOW)
        else:
            if not self.spawned:
                count = self.settings.tile_spawn_per_round
                new = spawn_platforms(engine, self.spawn_rules, self.settings,
                                       count, self.round_num, PLATFORM_COLORS)
                if not new and count > 0:
                    return ("end", {"reason": "board_full", "round_num": self.round_num})
                self.spawned = True

            for ent in engine.entities:
                if isinstance(ent, Tile) and ent.alive:
                    c = ent.color
                    for tx, ty in ent.get_position():
                        engine.set_pixel(tx, ty, *c)

        # Border acts as the spawn timer: color shifts from BLUE -> YELLOW and brightness increases.
        # During the initial round-number display, pause the border animation.
        if self.timer < 1.0:
            engine.draw_rect_outline_scaled(0, 0, 16, 32, BLUE, 1.0, thickness=2)
        else:
            # Map timer 1.0..3.0 -> frac 0..1
            spawn_frac = min(1.0, max(0.0, (self.timer - 1.0) / 2.0))
            # Fade the border back to blue over the final `fade` seconds
            fade = 0.25
            if self.timer >= 3.0 - fade:
                remaining = max(0.0, 3.0 - self.timer)
                t = remaining / fade  # 1.0 -> 0.0 as timer goes 3-fade -> 3
                target_frac = spawn_frac * t
            else:
                target_frac = spawn_frac

            # Smooth border fraction using exponential smoothing (time-constant)
            tau = 0.6
            alpha = 1.0 - math.exp(-dt / tau) if dt > 0 else 0.0
            self.border_frac += (target_frac - self.border_frac) * alpha

            r = int(BLUE[0] + self.border_frac * (YELLOW[0] - BLUE[0]))
            g = int(BLUE[1] + self.border_frac * (YELLOW[1] - BLUE[1]))
            b = int(BLUE[2] + self.border_frac * (YELLOW[2] - BLUE[2]))
            border_color = (r, g, b)
            brighten_factor = 1.0 + self.border_frac * 1.0
            engine.draw_rect_outline_scaled(0, 0, 16, 32, border_color, brighten_factor, thickness=2)

        if self.timer >= 3.0:
            return ("play", {"round_num": self.round_num})

    def exit(self, engine):
        pass