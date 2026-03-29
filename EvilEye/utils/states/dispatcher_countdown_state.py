from ._abs_state import GameEngine, GameState
from ..data.pattern_memory_data import COUNTDOWN_DURATION
from ..ui.colors import RED, YELLOW, GREEN, BLACK
from ..ui.pattern_memory_ui import draw_countdown

class DispatcherCountdownState(GameState):
    """Brief countdown (red → yellow → green) before gameplay begins."""

    PHASES = [RED, YELLOW, GREEN, BLACK]

    def __init__(self, settings, **kwargs):
        self.settings = settings
        self.data = kwargs.get("data")
        self.pattern = kwargs.get("pattern") # For compatibility if someone passes it
        self.players = kwargs.get("players") # For compatibility
        self._t = 0.0

    def enter(self, engine: GameEngine):
        engine.clear()
        # Initial flash of red
        for w in range(1, 5):
            engine.set_eye(w, *self.PHASES[0])

    def update(self, engine: GameEngine, dt: float):
        self._t += dt

        if self._t >= COUNTDOWN_DURATION:
            return ("play", {"data": self.data})

        draw_countdown(engine, self._t, self.settings.player_count, self.PHASES, COUNTDOWN_DURATION)

    def exit(self, engine: GameEngine):
        engine.clear()
