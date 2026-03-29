import random
import colorsys
from ._abs_state import GameEngine, GameState
from ..data.pattern_memory_data import DIFFICULTY, build_players, assign_colors, ALL_COLORS
from ..ui.pattern_memory_ui import draw_idle_animation

class SetupState(GameState):
    """Wait for any button press to start, showing idle animation."""

    def __init__(self, settings):
        self.settings = settings
        self._t = 0.0

    def enter(self, engine: GameEngine):
        engine.clear()

    def update(self, engine: GameEngine, dt: float):
        self._t += dt
        draw_idle_animation(engine, self._t)

        if engine.any_pressed():
            from ..data.pattern_memory_data import build_players, assign_colors, ALL_COLORS
            
            # Use settings to determine pattern and players
            n_colors = self.settings.pattern_length
            players = build_players(self.settings.player_count)
            # Ensure n_colors doesn't exceed button count
            max_buttons = min(len(p.buttons) for p in players)
            n_colors = min(n_colors, max_buttons)

            palette = list(ALL_COLORS[:n_colors])
            random.shuffle(palette)
            pattern = palette[:n_colors]
            assign_colors(players, pattern)

            return ("countdown", {"pattern": pattern, "players": players})

    def exit(self, engine: GameEngine):
        engine.clear()
