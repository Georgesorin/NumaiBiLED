from ._abs_state import GameEngine, GameState
from ..ui.colors import RED, YELLOW, GREEN, BLACK

class BossBattleCountdownState(GameState):
    PHASES = [RED, YELLOW, GREEN, BLACK]
    DURATION = 3.0

    def __init__(self, settings, players):
        self.settings = settings
        self.players = players
        self._t = 0.0

    def enter(self, engine: GameEngine):
        engine.clear()

    def update(self, engine: GameEngine, dt: float):
        self._t += dt
        if self._t >= self.DURATION:
            # Stage 1 starts
            return ("stage1", {"players": self.players})
            
        phase_idx = int((self._t / self.DURATION) * len(self.PHASES))
        color = self.PHASES[min(phase_idx, len(self.PHASES)-1)]
        for w in range(1, self.settings.walls_used + 1):
            engine.set_eye(w, *color)

    def exit(self, engine: GameEngine):
        engine.clear()
