import random
import math
from ._abs_state import GameEngine, GameState
from ..data.pattern_memory_data import BLACKOUT_DEBUFF_DURATION
from ..ui.colors import BLACK, GREEN
from ..ui.pattern_memory_ui import light_player_buttons, animate_eyes, animate_powerup_buttons

class PlayState(GameState):
    """Players reproduce the pattern by pressing buttons."""

    def __init__(self, settings, pattern, players):
        self.settings = settings
        self.pattern = pattern
        self.players = players
        self._first_finisher = None
        self._powerup_player = None
        self._blackout_timer = 0.0
        self._blackout_targets = []
        self._t = 0.0

    def enter(self, engine: GameEngine):
        engine.clear()
        light_player_buttons(engine, self.players, self.pattern, self._blackout_targets, self._powerup_player)

    def update(self, engine: GameEngine, dt: float):
        self._t += dt

        if self._blackout_timer > 0:
            self._blackout_timer -= dt
            if self._blackout_timer <= 0:
                self._blackout_targets.clear()
                light_player_buttons(engine, self.players, self.pattern, self._blackout_targets, self._powerup_player)

        active_players = [p for p in self.players if not p.finished]
        if len(active_players) <= 1:
            return ("end", {"players": self.players})

        animate_eyes(engine, self._t, self.settings.player_count, self.pattern, self.players)
        if self._powerup_player is not None:
            animate_powerup_buttons(engine, self._t, self._powerup_player)

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
                    light_player_buttons(engine, self.players, self.pattern, self._blackout_targets, self._powerup_player)

        active_players = [p for p in self.players if not p.finished]
        if len(active_players) <= 1:
            return ("end", {"players": self.players})

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
                light_player_buttons(engine, self.players, self.pattern, self._blackout_targets, self._powerup_player)
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

    def exit(self, engine: GameEngine):
        pass
