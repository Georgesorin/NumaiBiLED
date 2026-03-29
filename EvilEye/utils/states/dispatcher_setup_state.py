import random
from ._abs_state import GameEngine, GameState
from ..data.pattern_memory_data import build_players, ALL_COLORS
from ..data.dispatcher_data import DispatcherGameData
from ..ui.pattern_memory_ui import draw_idle_animation

class DispatcherSetupState(GameState):
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
            # Initialise players
            players = build_players(self.settings.player_count)
            
            # Initialise dispatcher game data
            data = DispatcherGameData(self.settings, players)
            data.generate_sequence()
            data.pick_active_wall()
            
            # We reuse CountdownState from Game1 if possible, or define our own.
            # Let's assume we can reuse it or just transition to play.
            # Reusing "countdown" transition from Game1 configuration.
            return ("countdown", {"data": data})

    def exit(self, engine: GameEngine):
        engine.clear()
