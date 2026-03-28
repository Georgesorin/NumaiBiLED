from ..tile import Tile
from ..ui.colors import *
from ..scaling.spawn_rules import spawn_platforms
from ._abs_state import GameState
import time

class InitialTilePatternState(GameState):
    """
    Spawn the initial batch of platforms (ceil(players/2)+1).
    The game waits here until every platform has been touched at least once.
    """

    def __init__(self, settings, spawn_rules):
        self.settings = settings
        self.spawn_rules = spawn_rules
        self.spawned = False
        self.timer = 0.0

    def enter(self, engine):
        self.timer = 0.0
        self.spawned = False

    def update(self, engine, dt: float):
        self.timer += dt
        engine.clear()

        if not self.spawned:
            count = self.settings.tile_spawn_initial
            spawn_platforms(engine, self.spawn_rules, self.settings, count, 1, PLATFORM_COLORS)
            for ent in engine.entities:
                if isinstance(ent, Tile):
                    ent.last_pressed_time = time.time() + 9999
                    ent.ever_pressed = False
            self.spawned = True

        pressed_xy = engine.get_pressed_xy()
        platforms = [e for e in engine.entities if isinstance(e, Tile)]

        for plat in platforms:
            for px, py in pressed_xy:
                if plat.contains_tile(px, py):
                    plat.ever_pressed = True
                    break

        all_touched = all(p.ever_pressed for p in platforms)

        for plat in platforms:
            if plat.ever_pressed:
                engine.draw_rect(plat.position, plat.dimensions, plat.color)
            else:
                blink = (int(self.timer * 4) % 2) == 0
                c = plat.color if blink else self._dim(plat.color, 0.25)
                engine.draw_rect(plat.position, plat.dimensions, c)

        touched = sum(1 for p in platforms if p.ever_pressed)
        engine.draw_text_small(f"{touched}/{len(platforms)}", 1, 0, WHITE)

        if all_touched:
            return ("play", {"round_num": 1})

    def exit(self, engine):
        for ent in engine.entities:
            if isinstance(ent, Tile):
                ent.last_pressed_time = time.time()

    @staticmethod
    def _dim(color, factor):
        return tuple(max(0, int(c * factor)) for c in color)