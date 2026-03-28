"""
Pattern Memory Game for the Evil Eye room.

The eye (LED 0) on each wall shows a colour pattern that players must
reproduce by pressing their assigned buttons in the correct order.

Player configurations:
    2 players → 2 walls  (1 wall per player, 10 buttons each)
    3 players → 3 walls  (1 wall per player, 10 buttons each)
    4 players → 4 walls  (1 wall per player, 10 buttons each)
    6 players → 3 walls  (2 players per wall, 5 buttons each)
    8 players → 4 walls  (2 players per wall, 5 buttons each)

Difficulties:
    Easy   → 4 colours  (pattern length 4)
    Medium → 6 colours  (pattern length 6)
    Hard   → 10 colours (pattern length 10, all colours)

Game flow:
    1. Eye shows the pattern colour-by-colour with pauses.
    2. Buttons light up in their assigned colours; players reproduce the
       sequence by pressing buttons in order.
    3. First player to finish gets a one-time power-up choice:
       - Rainbow button: shuffles everyone else's button-colour mapping.
       - Flashing-white button: blacks out everyone else's buttons for 3 s.
    4. Game ends when only one player has not yet finished.
"""

import math
import sys
import os
import random
import colorsys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from game_engine import (
    GameEngine, GameState, GameMaster,
    run_game, load_config,
    NUM_WALLS, LEDS_PER_WALL,
    BLACK, WHITE, RED, YELLOW, GREEN, BLUE, CYAN, MAGENTA, ORANGE, PURPLE,
)

ALL_COLORS = [WHITE, RED, YELLOW, GREEN, BLUE, CYAN, MAGENTA, ORANGE, PURPLE, BLACK]

DIFFICULTY = {
    "easy":   4,
    "medium": 6,
    "hard":   10,
}

PLAYER_CONFIGS = {
    2: {"walls": 2, "per_wall": 1},
    3: {"walls": 3, "per_wall": 1},
    4: {"walls": 4, "per_wall": 1},
    6: {"walls": 3, "per_wall": 2},
    8: {"walls": 4, "per_wall": 2},
}

SHOW_COLOR_DURATION  = 1
SHOW_PAUSE_DURATION  = 0.1
LOOP_GAP_DURATION    = 5   # pause between pattern repeats on the eye
BLACKOUT_DEBUFF_DURATION    = 3.0
COUNTDOWN_DURATION   = 3   # seconds to wait before the game begins


# ============================================================
#  Player
# ============================================================
class Player:
    def __init__(self, player_id, wall, buttons):
        self.id = player_id
        self.wall = wall
        self.buttons = list(buttons)
        self.color_map = {}
        self.progress = 0
        self.finished = False
        self.used_powerup = False

    def reset_progress(self):
        self.progress = 0
        self.finished = False
        self.used_powerup = False


# ============================================================
#  build_players
# ============================================================
def build_players(num_players):
    cfg = PLAYER_CONFIGS[num_players]
    walls_used = cfg["walls"]
    per_wall = cfg["per_wall"]
    players = []
    pid = 0
    for w in range(1, walls_used + 1):
        if per_wall == 1:
            players.append(Player(pid, w, list(range(1, 11))))
            pid += 1
        else:
            players.append(Player(pid, w, list(range(1, 6))))
            pid += 1
            players.append(Player(pid, w, list(range(6, 11))))
            pid += 1
    return players


# ============================================================
#  assign_colors – map each player's buttons to pattern colours
# ============================================================
def assign_colors(players, pattern):
    for p in players:
        usable = min(len(pattern), len(p.buttons))
        mapping = {}
        shuffled_buttons = list(p.buttons)
        random.shuffle(shuffled_buttons)
        for i in range(usable):
            mapping[shuffled_buttons[i]] = pattern[i]
        for btn in p.buttons:
            if btn not in mapping:
                mapping[btn] = BLACK
        p.color_map = mapping


# ============================================================
#  States
# ============================================================

class SetupState(GameState):
    """Wait for any button press to start, showing idle animation."""

    def __init__(self, num_players, difficulty):
        self.num_players = num_players
        self.difficulty = difficulty
        self._t = 0.0

    def enter(self, engine: GameEngine):
        engine.clear()

    def update(self, engine: GameEngine, dt: float):
        self._t += dt
            
        hue = (self._t * 0.05) % 1.0
        r, g, b = colorsys.hsv_to_rgb(hue, 1.0, 0.8)
        engine.set_all(int(r * 255), int(g * 255), int(b * 255))

        if engine.any_pressed():
            n_colors = DIFFICULTY[self.difficulty]
            players = build_players(self.num_players)
            max_buttons = min(len(p.buttons) for p in players)
            n_colors = min(n_colors, max_buttons)

            palette = list(ALL_COLORS[:n_colors])
            random.shuffle(palette)
            pattern = palette[:n_colors]
            assign_colors(players, pattern)

            engine.change_state(
                CountdownState(self.num_players, self.difficulty, pattern, players)
            )

    def exit(self, engine: GameEngine):
        engine.clear()


class CountdownState(GameState):
    """Brief countdown (red → yellow → green) before gameplay begins."""

    PHASES = [RED, YELLOW, GREEN, BLACK]

    def __init__(self, num_players, difficulty, pattern, players):
        self.num_players = num_players
        self.difficulty = difficulty
        self.pattern = pattern
        self.players = players
        self._t = 0.0

    def enter(self, engine: GameEngine):
        engine.clear()
        walls_used = PLAYER_CONFIGS[self.num_players]["walls"]
        for w in range(1, walls_used + 1):
            engine.set_eye(w, *self.PHASES[0])

    def update(self, engine: GameEngine, dt: float):
        self._t += dt

        if self._t >= COUNTDOWN_DURATION:
            engine.change_state(
                PlayState(self.num_players, self.difficulty,
                          self.pattern, self.players)
            )
            return

        phase_dur = COUNTDOWN_DURATION / len(self.PHASES)
        phase_idx = min(int(self._t / phase_dur), len(self.PHASES) - 1)
        color = self.PHASES[phase_idx]

        walls_used = PLAYER_CONFIGS[self.num_players]["walls"]
        for w in range(1, walls_used + 1):
            engine.set_eye(w, *color)

    def exit(self, engine: GameEngine):
        engine.clear()


class PlayState(GameState):
    """Players reproduce the pattern by pressing buttons."""

    def __init__(self, num_players, difficulty, pattern, players):
        self.num_players = num_players
        self.difficulty = difficulty
        self.pattern = pattern
        self.players = players
        self._first_finisher = None
        self._powerup_active = False
        self._powerup_player = None
        self._blackout_timer = 0.0
        self._blackout_targets = []
        self._game_over = False
        self._t = 0.0

    def enter(self, engine: GameEngine):
        engine.clear()
        self._light_buttons(engine)

    def _light_buttons(self, engine):
        """Set each player's buttons to their assigned colours."""
        for p in self.players:
            if p.finished and p != self._powerup_player:
                for btn in p.buttons:
                    engine.set_button(p.wall, btn, *BLACK)
                continue
            if p in self._blackout_targets:
                continue
            for btn in p.buttons:
                engine.set_button(p.wall, btn, *p.color_map.get(btn, BLACK))

    def update(self, engine: GameEngine, dt: float):
        self._t += dt

        if self._blackout_timer > 0:
            self._blackout_timer -= dt
            if self._blackout_timer <= 0:
                self._blackout_targets.clear()
                self._light_buttons(engine)

        active_players = [p for p in self.players if not p.finished]
        if len(active_players) <= 1:
            engine.change_state(
                GameOverState(self.num_players, self.difficulty, self.players)
            )
            return

        self._animate_eyes(engine)
        if self._powerup_player is not None:
            self._animate_powerup_buttons(engine)

        pressed = engine.get_pressed()
        if not pressed:
            return

        for p in self.players:
            if p.finished:
                if self._powerup_player == p and not p.used_powerup:
                    self._handle_powerup_press(engine, p, pressed)
                continue

            if p in self._blackout_targets:
                continue

            for (wall, led) in pressed:
                if wall != p.wall or led not in p.buttons:
                    continue
                expected_color = self.pattern[p.progress]
                pressed_color = p.color_map.get(led, BLACK)

                if pressed_color == expected_color:
                    p.progress += 1
                    engine.set_button(p.wall, led, *BLACK)
                    if p.progress >= len(self.pattern):
                        p.finished = True
                        for btn in p.buttons:
                            engine.set_button(p.wall, btn, *BLACK)
                        engine.set_eye(p.wall, *GREEN)

                        if self._first_finisher is None:
                            self._first_finisher = p
                            self._powerup_player = p
                else:
                    p.progress = 0
                    self._light_buttons(engine)

        active_players = [p for p in self.players if not p.finished]
        if len(active_players) <= 1:
            engine.change_state(
                GameOverState(self.num_players, self.difficulty, self.players)
            )

    def _handle_powerup_press(self, engine, player, pressed):
        btn_rainbow = player.buttons[0]
        btn_flash = player.buttons[1]

        for (wall, led) in pressed:
            if wall != player.wall or led not in player.buttons:
                continue
            if led == btn_rainbow:
                player.used_powerup = True
                self._powerup_player = None
                others = [p for p in self.players if p != player and not p.finished]
                for op in others:
                    old_colors = list(op.color_map.values())
                    random.shuffle(old_colors)
                    new_map = {}
                    for i, btn in enumerate(op.buttons):
                        new_map[btn] = old_colors[i] if i < len(old_colors) else BLACK
                    op.color_map = new_map
                self._light_buttons(engine)
                for btn in player.buttons:
                    engine.set_button(player.wall, btn, *BLACK)
                break
            elif led == btn_flash:
                player.used_powerup = True
                self._powerup_player = None
                others = [p for p in self.players if p != player and not p.finished]
                self._blackout_targets = others
                self._blackout_timer = BLACKOUT_DEBUFF_DURATION
                for op in others:
                    op.progress = 0
                    for btn in op.buttons:
                        engine.set_button(op.wall, btn, *BLACK)
                for btn in player.buttons:
                    engine.set_button(player.wall, btn, *BLACK)
                break

    def _animate_eyes(self, engine):
        """Continuously loop the full pattern on the eye for active walls."""
        step_dur = SHOW_COLOR_DURATION + SHOW_PAUSE_DURATION
        cycle_dur = step_dur * len(self.pattern) + LOOP_GAP_DURATION
        pos = self._t % cycle_dur

        pattern_end = step_dur * len(self.pattern)
        if pos >= pattern_end:
            color = BLACK
        else:
            step_idx = int(pos / step_dur)
            within = pos - step_idx * step_dur
            color = self.pattern[step_idx] if within < SHOW_COLOR_DURATION else BLACK

        walls_used = PLAYER_CONFIGS[self.num_players]["walls"]
        for w in range(1, walls_used + 1):
            has_active = any(
                p.wall == w and not p.finished for p in self.players
            )
            if has_active:
                engine.set_eye(w, *color)
            else:
                engine.set_eye(w, *GREEN)

    def _animate_powerup_buttons(self, engine):
        """Rainbow cycle on button[0], flashing white on button[1]."""
        p = self._powerup_player
        if p is None or p.used_powerup:
            return
        btn_rainbow = p.buttons[0]
        btn_flash = p.buttons[1]

        hue = (self._t * 0.2) % 1.0
        r, g, b = colorsys.hsv_to_rgb(hue, 1.0, 1.0)
        engine.set_button(p.wall, btn_rainbow, int(r * 255), int(g * 255), int(b * 255))

        # Smooth black→white pulse for btn_flash
        # Sine wave: goes from 0→1→0 over 2 seconds
        brightness = 0.5 * (1 + math.sin(self._t * math.pi))
        intensity = int(brightness * 255)
        engine.set_button(p.wall, btn_flash, intensity, intensity, intensity)

        for btn in p.buttons:
            if btn != btn_rainbow and btn != btn_flash:
                engine.set_button(p.wall, btn, *BLACK)

    def exit(self, engine: GameEngine):
        pass


class GameOverState(GameState):
    """Flash the winner, wait for restart."""

    def __init__(self, num_players, difficulty, players):
        self.num_players = num_players
        self.difficulty = difficulty
        self.players = players
        self._t = 0.0
        self._loser = None

    def enter(self, engine: GameEngine):
        engine.clear()
        not_finished = [p for p in self.players if not p.finished]
        self._loser = not_finished[0] if not_finished else None

        for p in self.players:
            if p.finished:
                engine.set_eye(p.wall, *GREEN)
            else:
                engine.set_eye(p.wall, *RED)

    def update(self, engine: GameEngine, dt: float):
        self._t += dt

        if self._loser:
            flash = int(self._t * 3) % 2 == 0
            if flash:
                engine.set_eye(self._loser.wall, *RED)
            else:
                engine.set_eye(self._loser.wall, *BLACK)

        if engine.any_pressed():
            engine.change_state(SetupState(self.num_players, self.difficulty))

    def exit(self, engine: GameEngine):
        engine.clear()


# ============================================================
#  Entry point
# ============================================================
def main():
    num_players = 4
    difficulty = "medium"

    if len(sys.argv) > 1:
        try:
            np = int(sys.argv[1])
            if np in PLAYER_CONFIGS:
                num_players = np
        except ValueError:
            pass

    if len(sys.argv) > 2:
        d = sys.argv[2].lower()
        if d in DIFFICULTY:
            difficulty = d

    print(f"Pattern Game — {num_players} players, {difficulty} difficulty")
    print(f"  Pattern length: {DIFFICULTY[difficulty]} colours")

    cfg = load_config(
        os.path.join(os.path.dirname(__file__), "..", "eye_ctrl_config.json")
    )

    gm = GameMaster(lambda: SetupState(num_players, difficulty))
    run_game(gm, config=cfg, title="Pattern Memory Game")


if __name__ == "__main__":
    main()
