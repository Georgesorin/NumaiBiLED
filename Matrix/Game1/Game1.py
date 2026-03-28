import time
import random
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from game_engine import (
    GameEngine, GameState, GameMaster, NetworkManager,
    load_config, run_game,
    BOARD_WIDTH, BOARD_HEIGHT,
    BLACK, WHITE, RED, YELLOW, GREEN, BLUE, CYAN, MAGENTA, ORANGE,
)

PLATFORM_COLORS = [GREEN, CYAN, MAGENTA, YELLOW, BLUE, ORANGE, RED, WHITE]

_CFG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tetris_config.json")


# ============================================================
#  Platform Entity
# ============================================================

class Platform:
    def __init__(self, x, y, w, h, color, keep_alive_sec):
        self.x = x
        self.y = y
        self.w = w
        self.h = h
        self.color = color
        self.keep_alive_sec = keep_alive_sec
        self.last_pressed_time = time.time()
        self.alive = True
        self.flash_phase = 0.0

    @property
    def timed_out(self):
        return (time.time() - self.last_pressed_time) > self.keep_alive_sec

    @property
    def time_remaining(self):
        return max(0.0, self.keep_alive_sec - (time.time() - self.last_pressed_time))

    @property
    def urgency(self):
        """0.0 = just pressed, 1.0 = about to expire."""
        elapsed = time.time() - self.last_pressed_time
        return min(1.0, elapsed / self.keep_alive_sec)

    def contains_tile(self, tx, ty):
        return self.x <= tx < self.x + self.w and self.y <= ty < self.y + self.h

    def press(self):
        self.last_pressed_time = time.time()

    def tile_indices(self):
        """Yield all (x, y) cells that belong to this platform."""
        for dy in range(self.h):
            for dx in range(self.w):
                yield (self.x + dx, self.y + dy)

    def render_color(self):
        u = self.urgency
        if u < 0.5:
            return self.color
        freq = 2 + int(u * 10)
        self.flash_phase += 0.05
        on = (int(self.flash_phase * freq) % 2) == 0
        if u > 0.85:
            return RED if on else BLACK
        return self.color if on else self._dim(self.color, 0.3)

    @staticmethod
    def _dim(color, factor):
        return tuple(max(0, int(c * factor)) for c in color)


# ============================================================
#  SpawnRules – hotspot map for platform placement
# ============================================================

class SpawnRules:
    """
    Maintains a heat map over the grid of valid 2x2 spawn positions.
    Each time a platform is placed, nearby positions gain heat while
    distant ones stay cold.  On spawn, the coldest fraction of candidates
    is excluded so platforms don't appear in the far opposite corner.
    """

    PLAY_H = 26
    PW = 2
    PH = 2

    def __init__(self, board_w=BOARD_WIDTH, play_h=26, cutoff_fraction=0.25):
        self.board_w = board_w
        self.play_h = play_h
        self.cutoff_fraction = cutoff_fraction
        self._grid_w = board_w // self.PW
        self._grid_h = play_h // self.PH
        self.heat = [[1.0] * self._grid_w for _ in range(self._grid_h)]

    def reset(self):
        for gy in range(self._grid_h):
            for gx in range(self._grid_w):
                self.heat[gy][gx] = 1.0

    def _pos_to_grid(self, x, y):
        return x // self.PW, y // self.PH

    def _grid_to_pos(self, gx, gy):
        return gx * self.PW, gy * self.PH

    def _distance(self, gx1, gy1, gx2, gy2):
        return ((gx1 - gx2) ** 2 + (gy1 - gy2) ** 2) ** 0.5

    def update(self, placed_x, placed_y):
        """Recalculate heat after a platform is placed at (placed_x, placed_y)."""
        pgx, pgy = self._pos_to_grid(placed_x, placed_y)
        max_dist = self._distance(0, 0, self._grid_w - 1, self._grid_h - 1)

        for gy in range(self._grid_h):
            for gx in range(self._grid_w):
                dist = self._distance(gx, gy, pgx, pgy)
                proximity = 1.0 - (dist / max_dist)
                self.heat[gy][gx] += proximity

    def pick(self, engine):
        """
        Return (x, y) for a new 2x2 platform, or None if the board is full.
        Excludes overlapping positions and the coldest `cutoff_fraction` of
        remaining candidates, then picks randomly weighted by heat.
        """
        occupied = set()
        for ent in engine.entities:
            if isinstance(ent, Platform):
                for pos in ent.tile_indices():
                    occupied.add(pos)

        scored = []
        for gy in range(self._grid_h):
            for gx in range(self._grid_w):
                x, y = self._grid_to_pos(gx, gy)
                cells = [(x + dx, y + dy) for dx in range(self.PW) for dy in range(self.PH)]
                if any(c in occupied for c in cells):
                    continue
                scored.append((x, y, self.heat[gy][gx]))

        if not scored:
            return None

        scored.sort(key=lambda t: t[2])

        cut = max(1, int(len(scored) * self.cutoff_fraction))
        if len(scored) - cut < 1:
            cut = len(scored) - 1
        viable = scored[cut:]

        weights = [s[2] for s in viable]
        total_w = sum(weights)
        if total_w <= 0:
            choice = random.choice(viable)
        else:
            choice = random.choices(viable, weights=weights, k=1)[0]

        return choice[0], choice[1]


# ============================================================
#  Concrete States
# ============================================================

spawn_rules = SpawnRules()


class StartState(GameState):
    """Attract / countdown screen before the game begins."""

    def __init__(self):
        self.timer = 0.0
        self.countdown = 3
        self.phase = "attract"

    def enter(self, engine: GameEngine):
        self.timer = 0.0
        self.phase = "attract"
        engine.entities.clear()
        spawn_rules.reset()

    def update(self, engine: GameEngine, dt: float):
        self.timer += dt
        engine.clear()

        if self.phase == "attract":
            pulse = abs((self.timer * 2) % 2.0 - 1.0)
            brightness = int(80 + 175 * pulse)
            title_color = (0, brightness, 0)
            engine.draw_text_large("KEEP", 0, 2, title_color)
            engine.draw_text_large("ALIVE", 0, 11, title_color)

            engine.draw_text_small("PRESS", 1, 22, WHITE)
            engine.draw_text_small("START", 1, 28, WHITE)

            if engine.any_pressed():
                self.phase = "countdown"
                self.countdown = 3
                self.timer = 0.0

        elif self.phase == "countdown":
            num = str(self.countdown)
            engine.draw_text_large(num, 5, 12, GREEN)
            if self.timer >= 1.0:
                self.timer = 0.0
                self.countdown -= 1
                if self.countdown < 0:
                    engine.change_state(SpawnState(round_num=1))

    def exit(self, engine: GameEngine):
        pass


class SpawnState(GameState):
    """Spawn a new platform, then transition to PlayState."""

    def __init__(self, round_num=1):
        self.round_num = round_num
        self.timer = 0.0
        self.spawned = False

    def enter(self, engine: GameEngine):
        self.timer = 0.0
        self.spawned = False

    def update(self, engine: GameEngine, dt: float):
        self.timer += dt
        engine.clear()

        if not self.spawned:
            pos = spawn_rules.pick(engine)
            if pos is None:
                engine.change_state(EndState(reason="board_full", round_num=self.round_num))
                return

            x, y = pos
            spawn_rules.update(x, y)

            keep_alive = max(3.0, 8.0 - (self.round_num - 1) * 0.4)
            color = PLATFORM_COLORS[(self.round_num - 1) % len(PLATFORM_COLORS)]
            plat = Platform(x, y, 2, 2, color, keep_alive)
            engine.spawn_entity(plat)
            self.spawned = True

        r_text = f"R{self.round_num}"
        engine.draw_text_small(r_text, 1, 1, YELLOW)

        for ent in engine.entities:
            if isinstance(ent, Platform):
                c = ent.color
                for tx, ty in ent.tile_indices():
                    engine.set_pixel(tx, ty, *c)

        if self.timer >= 1.5:
            engine.change_state(PlayState(round_num=self.round_num))

    def exit(self, engine: GameEngine):
        pass


class PlayState(GameState):
    """Main gameplay: keep all platforms alive by pressing them before timeout."""

    def __init__(self, round_num=1):
        self.round_num = round_num
        self.round_timer = 0.0
        self.round_duration = max(6.0, 15.0 - (round_num - 1) * 0.5)

    def enter(self, engine: GameEngine):
        self.round_timer = 0.0
        for ent in engine.entities:
            if isinstance(ent, Platform):
                ent.last_pressed_time = time.time()

    def update(self, engine: GameEngine, dt: float):
        self.round_timer += dt
        engine.clear()

        pressed_xy = engine.get_pressed_xy()

        for ent in engine.entities:
            if isinstance(ent, Platform) and ent.alive:
                for px, py in pressed_xy:
                    if ent.contains_tile(px, py):
                        ent.press()
                        break

        for ent in engine.entities:
            if isinstance(ent, Platform) and ent.alive:
                if ent.timed_out:
                    ent.alive = False
                    engine.change_state(EndState(reason="timeout", round_num=self.round_num))
                    return

        for ent in engine.entities:
            if isinstance(ent, Platform) and ent.alive:
                c = ent.render_color()
                for tx, ty in ent.tile_indices():
                    engine.set_pixel(tx, ty, *c)

        r_text = f"R{self.round_num}"
        engine.draw_text_small(r_text, 10, 0, WHITE)

        round_frac = min(1.0, self.round_timer / self.round_duration)
        engine.draw_progress_bar(0, 27, 16, 1.0 - round_frac, GREEN, (20, 20, 20))

        if self.round_timer >= self.round_duration:
            engine.change_state(SpawnState(round_num=self.round_num + 1))

    def exit(self, engine: GameEngine):
        pass


class EndState(GameState):
    """Game over screen."""

    def __init__(self, reason="timeout", round_num=1):
        self.reason = reason
        self.round_num = round_num
        self.timer = 0.0

    def enter(self, engine: GameEngine):
        self.timer = 0.0

    def update(self, engine: GameEngine, dt: float):
        self.timer += dt
        engine.clear()

        on = (int(self.timer * 3) % 2) == 0
        if on:
            engine.draw_text_small("GAME", 2, 4, RED)
            engine.draw_text_small("OVER", 2, 10, RED)

        score_text = str(self.round_num)
        engine.draw_text_large(score_text, 4, 18, YELLOW)

        if self.timer > 2.0:
            if engine.any_pressed():
                engine.entities.clear()
                engine.change_state(StartState())

    def exit(self, engine: GameEngine):
        engine.entities.clear()


# ============================================================
#  Main
# ============================================================

if __name__ == "__main__":
    config = load_config(_CFG_FILE)
    game = GameMaster(initial_state_factory=StartState)
    run_game(game, config=config, title="Game 1 - Keep Alive!")
