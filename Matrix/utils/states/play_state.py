from ._abs_state import GameState
import time
from ..tile import Tile
from ..ui.colors import *

class PlayState(GameState):
    """Main gameplay: keep all platforms alive by pressing them before timeout."""

    def __init__(self, settings, spawn_rules, round_num=1):
        self.settings = settings
        self.spawn_rules = spawn_rules
        self.round_num = round_num
        self.round_timer_curr = 0.0
        self.round_duration = settings.get_round_timer(round_num)

    def enter(self, engine):
        self.round_timer_curr = 0.0
        keep_alive = self.settings.get_tile_timeout(self.round_num)
        for ent in engine.entities:
            if isinstance(ent, Tile):
                ent.timeout_duration = keep_alive
                ent.last_pressed_time = time.time()

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

        r_text = f"R{self.round_num}"
        engine.draw_text_small(r_text, 10, 0, WHITE)

        round_frac = min(1.0, self.round_timer_curr / self.round_duration)
        engine.draw_progress_bar(0, 27, 16, 1.0 - round_frac, GREEN, (20, 20, 20))

        if self.round_timer_curr >= self.round_duration:
            return ("spawn", {"round_num": self.round_num + 1})

    def exit(self, engine):
        pass