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
        if self.timer >= 3.0:
            return ("play", {"round_num": self.round_num})

    def exit(self, engine):
        pass