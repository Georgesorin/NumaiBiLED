from ._abs_state import GameEngine, GameState
from ..ui.colors import GREEN, RED

class BossBattleGameOverState(GameState):
    def __init__(self, settings, winner=True):
        self.settings = settings
        self.winner = winner
        self._t = 0.0

    def enter(self, engine: GameEngine):
        engine.clear()
        color = GREEN if self.winner else RED
        for w in range(1, self.settings.walls_used + 1):
            engine.set_eye(w, *color)

    def update(self, engine: GameEngine, dt: float):
        self._t += dt
        if self._t > 5.0:
            return ("setup", {})
        
        # Flash buttons
        if int(self._t * 2) % 2 == 0:
            for w in range(1, self.settings.walls_used + 1):
                for b in range(1, 11):
                    engine.set_button(w, b, *(GREEN if self.winner else RED))
        else:
            engine.clear_buttons()

    def exit(self, engine: GameEngine):
        engine.clear()
