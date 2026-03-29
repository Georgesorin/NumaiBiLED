from ._abs_state import GameEngine, GameState
from ..ui.colors import GREEN, RED, BLACK
from ..ui.pattern_memory_ui import draw_game_over

class GameOverState(GameState):
    """Flash the winner, wait for restart."""

    def __init__(self, settings, players, **kwargs):
        self.settings = settings
        self.players = players
        self.score = kwargs.get("score")
        self._t = 0.0
        self._loser = None
        self._announced = False

    def enter(self, engine: GameEngine):
        engine.clear()
        not_finished = [p for p in self.players if not p.finished]
        self._loser = not_finished[0] if not_finished else None

    def update(self, engine: GameEngine, dt: float):
        self._t += dt
        draw_game_over(engine, self.players, self._loser, self._t)

        if not self._announced:
            print("\n" + "="*30)
            print("       GAME OVER")
            if self.score is not None:
                print(f"       SCORE: {self.score}")
            print("="*30 + "\n")
            self._announced = True

        if engine.any_pressed():
            return ("setup", {})

    def exit(self, engine: GameEngine):
        engine.clear()
