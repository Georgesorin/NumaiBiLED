import math
import time
import random
import os
import sys
import threading

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from game_engine import (
    GameEngine, GameState, GameMaster, NetworkManager,
    load_config, game_thread_func,
    BOARD_WIDTH, BOARD_HEIGHT,
    BLACK, WHITE, RED, YELLOW, GREEN, BLUE, CYAN, MAGENTA, ORANGE,
)

PLATFORM_COLORS = [GREEN, CYAN, MAGENTA, YELLOW, BLUE, ORANGE, RED, WHITE]

_CFG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tetris_config.json")


# ============================================================
#  Difficulty presets
# ============================================================

DIFFICULTIES = {
    #                    cutoff  heat_spread  keep_alive_base  keep_alive_floor  round_dur_base  round_dur_floor
    "easy":       dict(cutoff=0.10, heat_spread=1.5, keep_alive_base=10.0, keep_alive_floor=5.0,
                       keep_alive_decay=0.3, round_dur_base=15.0, round_dur_floor=8.0, round_dur_decay=0.5),
    "medium":     dict(cutoff=0.25, heat_spread=1.0, keep_alive_base=8.0,  keep_alive_floor=3.5,
                       keep_alive_decay=0.4, round_dur_base=13.0, round_dur_floor=6.0, round_dur_decay=0.5),
    "hard":       dict(cutoff=0.45, heat_spread=0.6, keep_alive_base=6.0,  keep_alive_floor=2.5,
                       keep_alive_decay=0.5, round_dur_base=11.0, round_dur_floor=5.0, round_dur_decay=0.6),
    "nightmare":  dict(cutoff=0.65, heat_spread=0.3, keep_alive_base=5.0,  keep_alive_floor=2.0,
                       keep_alive_decay=0.5, round_dur_base=9.0,  round_dur_floor=4.0, round_dur_decay=0.7),
}


class GameSettings:
    def __init__(self, num_players, difficulty_name):
        self.num_players = num_players
        self.difficulty_name = difficulty_name
        diff = DIFFICULTIES[difficulty_name]
        self.cutoff = diff["cutoff"]
        self.heat_spread = diff["heat_spread"]
        self.keep_alive_base = diff["keep_alive_base"]
        self.keep_alive_floor = diff["keep_alive_floor"]
        self.keep_alive_decay = diff["keep_alive_decay"]
        self.round_dur_base = diff["round_dur_base"]
        self.round_dur_floor = diff["round_dur_floor"]
        self.round_dur_decay = diff["round_dur_decay"]

    @property
    def initial_spawn_count(self):
        return math.ceil(self.num_players / 2) + 1

    @property
    def spawn_per_round(self):
        return math.floor(self.num_players / 2)

    def keep_alive_for_round(self, round_num):
        return max(self.keep_alive_floor,
                   self.keep_alive_base - (round_num - 1) * self.keep_alive_decay)

    def round_duration_for_round(self, round_num):
        return max(self.round_dur_floor,
                   self.round_dur_base - (round_num - 1) * self.round_dur_decay)


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
        self.ever_pressed = False
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
        self.ever_pressed = True

    def tile_indices(self):
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
    Heat map over the grid of valid 2x2 spawn positions.

    `cutoff_fraction` controls how aggressively far-away spots are
    preferred.  Higher values (hard/nightmare) cut more of the "cold"
    (close) candidates, pushing new spawns further from existing ones.

    `heat_spread` scales how much heat a placement radiates.
    Lower values make the heat map more local, so consecutive spawns
    can land further apart.
    """

    PLAY_H = 26
    PW = 2
    PH = 2

    def __init__(self, settings: GameSettings):
        self.board_w = BOARD_WIDTH
        self.play_h = self.PLAY_H
        self.cutoff_fraction = settings.cutoff
        self.heat_spread = settings.heat_spread
        self._grid_w = self.board_w // self.PW
        self._grid_h = self.play_h // self.PH
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
        pgx, pgy = self._pos_to_grid(placed_x, placed_y)
        max_dist = self._distance(0, 0, self._grid_w - 1, self._grid_h - 1)

        for gy in range(self._grid_h):
            for gx in range(self._grid_w):
                dist = self._distance(gx, gy, pgx, pgy)
                proximity = 1.0 - (dist / max_dist)
                self.heat[gy][gx] += proximity * self.heat_spread

    def pick(self, engine):
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
#  Helper: spawn N platforms at once
# ============================================================

def _spawn_platforms(engine, spawn_rules, settings, count, round_num):
    """Spawn `count` new platforms. Returns list of newly created Platform objects."""
    spawned = []
    for i in range(count):
        pos = spawn_rules.pick(engine)
        if pos is None:
            break
        x, y = pos
        spawn_rules.update(x, y)

        keep_alive = settings.keep_alive_for_round(round_num)
        color_idx = (len(engine.entities) - 1) % len(PLATFORM_COLORS)
        color = PLATFORM_COLORS[color_idx]
        plat = Platform(x, y, 2, 2, color, keep_alive)
        engine.spawn_entity(plat)
        spawned.append(plat)
    return spawned


# ============================================================
#  Concrete States
# ============================================================

class StartState(GameState):
    """Attract / countdown screen. Transitions into InitialSpawnState."""

    def __init__(self, settings: GameSettings, spawn_rules: SpawnRules):
        self.settings = settings
        self.spawn_rules = spawn_rules
        self.timer = 0.0
        self.countdown = 3
        self.phase = "attract"

    def enter(self, engine: GameEngine):
        self.timer = 0.0
        self.phase = "attract"
        engine.entities.clear()
        self.spawn_rules.reset()

    def update(self, engine: GameEngine, dt: float):
        self.timer += dt
        engine.clear()

        if self.phase == "attract":
            pulse = abs((self.timer * 2) % 2.0 - 1.0)
            brightness = int(80 + 175 * pulse)
            title_color = (0, brightness, 0)
            engine.draw_text_large("KEEP", 0, 2, title_color)
            engine.draw_text_large("ALIVE", 0, 11, title_color)

            p = str(self.settings.num_players)
            d = self.settings.difficulty_name[0].upper()
            engine.draw_text_small(f"{p}P {d}", 1, 22, WHITE)
            engine.draw_text_small("PRESS", 1, 28, WHITE)

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
                    engine.change_state(InitialSpawnState(self.settings, self.spawn_rules))

    def exit(self, engine: GameEngine):
        pass


class InitialSpawnState(GameState):
    """
    Spawn the initial batch of platforms (ceil(players/2)+1).
    The game waits here until every platform has been touched at least once.
    """

    def __init__(self, settings: GameSettings, spawn_rules: SpawnRules):
        self.settings = settings
        self.spawn_rules = spawn_rules
        self.spawned = False
        self.timer = 0.0

    def enter(self, engine: GameEngine):
        self.timer = 0.0
        self.spawned = False

    def update(self, engine: GameEngine, dt: float):
        self.timer += dt
        engine.clear()

        if not self.spawned:
            count = self.settings.initial_spawn_count
            _spawn_platforms(engine, self.spawn_rules, self.settings, count, round_num=1)
            for ent in engine.entities:
                if isinstance(ent, Platform):
                    ent.last_pressed_time = time.time() + 9999
                    ent.ever_pressed = False
            self.spawned = True

        pressed_xy = engine.get_pressed_xy()
        platforms = [e for e in engine.entities if isinstance(e, Platform)]

        for plat in platforms:
            for px, py in pressed_xy:
                if plat.contains_tile(px, py):
                    plat.ever_pressed = True
                    break

        all_touched = all(p.ever_pressed for p in platforms)

        for plat in platforms:
            if plat.ever_pressed:
                engine.draw_rect(plat.x, plat.y, plat.w, plat.h, plat.color)
            else:
                blink = (int(self.timer * 4) % 2) == 0
                c = plat.color if blink else self._dim(plat.color, 0.25)
                engine.draw_rect(plat.x, plat.y, plat.w, plat.h, c)

        touched = sum(1 for p in platforms if p.ever_pressed)
        engine.draw_text_small(f"{touched}/{len(platforms)}", 1, 0, WHITE)

        if all_touched:
            engine.change_state(PlayState(self.settings, self.spawn_rules, round_num=1))

    def exit(self, engine: GameEngine):
        for ent in engine.entities:
            if isinstance(ent, Platform):
                ent.last_pressed_time = time.time()

    @staticmethod
    def _dim(color, factor):
        return tuple(max(0, int(c * factor)) for c in color)


class SpawnState(GameState):
    """Spawn floor(players/2) new platforms, then transition to PlayState."""

    def __init__(self, settings: GameSettings, spawn_rules: SpawnRules, round_num=1):
        self.settings = settings
        self.spawn_rules = spawn_rules
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
            count = self.settings.spawn_per_round
            new = _spawn_platforms(engine, self.spawn_rules, self.settings,
                                   count, self.round_num)
            if not new and count > 0:
                engine.change_state(EndState(self.settings, self.spawn_rules,
                                             reason="board_full", round_num=self.round_num))
                return
            self.spawned = True

        r_text = f"R{self.round_num}"
        engine.draw_text_small(r_text, 1, 1, YELLOW)

        for ent in engine.entities:
            if isinstance(ent, Platform) and ent.alive:
                c = ent.color
                for tx, ty in ent.tile_indices():
                    engine.set_pixel(tx, ty, *c)

        if self.timer >= 1.5:
            engine.change_state(PlayState(self.settings, self.spawn_rules,
                                          round_num=self.round_num))

    def exit(self, engine: GameEngine):
        pass


class PlayState(GameState):
    """Main gameplay: keep all platforms alive by pressing them before timeout."""

    def __init__(self, settings: GameSettings, spawn_rules: SpawnRules, round_num=1):
        self.settings = settings
        self.spawn_rules = spawn_rules
        self.round_num = round_num
        self.round_timer = 0.0
        self.round_duration = settings.round_duration_for_round(round_num)

    def enter(self, engine: GameEngine):
        self.round_timer = 0.0
        keep_alive = self.settings.keep_alive_for_round(self.round_num)
        for ent in engine.entities:
            if isinstance(ent, Platform):
                ent.keep_alive_sec = keep_alive
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
                    engine.change_state(EndState(self.settings, self.spawn_rules,
                                                 reason="timeout", round_num=self.round_num))
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
            engine.change_state(SpawnState(self.settings, self.spawn_rules,
                                           round_num=self.round_num + 1))

    def exit(self, engine: GameEngine):
        pass


class EndState(GameState):
    """Game over screen."""

    def __init__(self, settings: GameSettings, spawn_rules: SpawnRules,
                 reason="timeout", round_num=1):
        self.settings = settings
        self.spawn_rules = spawn_rules
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
                engine.change_state(StartState(self.settings, self.spawn_rules))

    def exit(self, engine: GameEngine):
        engine.entities.clear()


# ============================================================
#  CLI setup + Main
# ============================================================

def _prompt_settings():
    print("\n=== KEEP ALIVE - Setup ===\n")

    while True:
        try:
            n = int(input("Number of players (2-6): ").strip())
            if 2 <= n <= 6:
                break
            print("  Please enter a number between 2 and 6.")
        except ValueError:
            print("  Invalid input.")

    diff_names = list(DIFFICULTIES.keys())
    print("\nDifficulty:")
    for i, name in enumerate(diff_names, 1):
        print(f"  {i}. {name}")

    while True:
        try:
            choice = input(f"Choose difficulty (1-{len(diff_names)}): ").strip()
            idx = int(choice) - 1
            if 0 <= idx < len(diff_names):
                break
            print(f"  Please enter a number between 1 and {len(diff_names)}.")
        except ValueError:
            print("  Invalid input.")

    diff_name = diff_names[idx]
    settings = GameSettings(n, diff_name)

    print(f"\n  Players: {settings.num_players}")
    print(f"  Difficulty: {settings.difficulty_name}")
    print(f"  Initial platforms: {settings.initial_spawn_count}")
    print(f"  Platforms per round: {settings.spawn_per_round}")
    print()
    return settings


if __name__ == "__main__":
    config = load_config(_CFG_FILE)
    settings = _prompt_settings()
    spawn_rules = SpawnRules(settings)

    def make_start():
        return StartState(settings, spawn_rules)

    game = GameMaster(initial_state_factory=make_start)
    net = NetworkManager(game, config=config)
    net.start_bg()

    gt = threading.Thread(target=game_thread_func, args=(game,), daemon=True)
    gt.start()

    print("Game 1 - Keep Alive!")
    print("Commands: 'restart', 'setup', 'quit'")

    try:
        while game.running:
            cmd = input("> ").strip().lower()
            if cmd in ('quit', 'exit'):
                game.running = False
                break
            elif cmd == 'restart':
                spawn_rules.reset()
                game.restart()
                print("Restarted.")
            elif cmd == 'setup':
                settings = _prompt_settings()
                spawn_rules = SpawnRules(settings)
                def make_start_new(s=settings, sr=spawn_rules):
                    return StartState(s, sr)
                game._initial_state_factory = make_start_new
                game.restart()
                print("Settings applied, game restarted.")
            else:
                print("Unknown command. Try: restart, setup, quit")
    except KeyboardInterrupt:
        game.running = False

    net.running = False
    print("Exiting...")
