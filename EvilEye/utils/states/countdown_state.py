from ._abs_state import GameEngine, GameState
from ..data.pattern_memory_data import COUNTDOWN_DURATION
from ..ui.colors import RED, YELLOW, GREEN, BLACK
from ..ui.pattern_memory_ui import draw_countdown

class CountdownState(GameState):
    """Brief countdown (red → yellow → green) before gameplay begins."""

    PHASES = [RED, YELLOW, GREEN, BLACK]

    def __init__(self, settings, pattern, players):
        self.settings = settings
        self.pattern = pattern
        self.players = players
        self._t = 0.0

    def enter(self, engine: GameEngine):
        engine.clear()
        walls_used = self.settings.walls_used
        for w in range(1, walls_used + 1):
            engine.set_eye(w, *self.PHASES[0])

    def update(self, engine: GameEngine, dt: float):
        self._t += dt

        if self._t >= COUNTDOWN_DURATION:
            return ("play", {"pattern": self.pattern, "players": self.players})

        draw_countdown(engine, self._t, self.settings.player_count, self.PHASES, COUNTDOWN_DURATION)

    def exit(self, engine: GameEngine):
        engine.clear()
