from ._abs_state import GameEngine, GameState
from ..data.boss_battle_data import build_boss_players
from ..ui.boss_battle_ui import draw_idle_animation

class BossBattleSetupState(GameState):
    def __init__(self, settings):
        self.settings = settings
        self._t = 0.0

    def enter(self, engine: GameEngine):
        engine.clear()

    def update(self, engine: GameEngine, dt: float):
        self._t += dt
        draw_idle_animation(engine, self._t)

        if engine.any_pressed():
            players = build_boss_players(self.settings)
            return ("countdown", {"players": players})

    def exit(self, engine: GameEngine):
        engine.clear()
