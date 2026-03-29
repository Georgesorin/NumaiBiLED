from ._abs_state import GameEngine, GameState
from ..ui.colors import GREEN, RED, BLACK
from ..ui.pattern_memory_ui import draw_game_over

class GameOverState(GameState):
    """Flash the winner, wait for restart."""

    def __init__(self, settings, players):
        self.settings = settings
        self.players = players
        self._t = 0.0
        self._loser = None

    def enter(self, engine: GameEngine):
        engine.clear()
        not_finished = [p for p in self.players if not p.finished]
        self._loser = not_finished[0] if not_finished else None

    def update(self, engine: GameEngine, dt: float):
        self._t += dt
        draw_game_over(engine, self.players, self._loser, self._t)

        if engine.any_pressed():
            return ("setup", {})

    def exit(self, engine: GameEngine):
        engine.clear()
