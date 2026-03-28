from ._abs_state import GameState
from ..ui.colors import *

class GameOverState(GameState):
    """Game over screen."""

    def __init__(self, settings, spawn_rules,
                 reason="timeout", round_num=1):
        self.settings = settings
        self.spawn_rules = spawn_rules
        self.reason = reason
        self.round_num = round_num
        self.timer = 0.0

    def enter(self, engine):
        self.timer = 0.0

    def update(self, engine, dt: float):
        self.timer += dt
        engine.clear()

        on = (int(self.timer * 3) % 2) == 0
        if on:
            engine.draw_text_small("GAME", 2, 4, RED)
            engine.draw_text_small("OVER", 2, 10, RED)

        score_text = str(self.round_num)
        engine.draw_text_large(score_text, 4, 18, YELLOW)

        if self.timer > 2.0:
            if engine.any_pressed():
                engine.entities.clear()
                return ("start", {})

    def exit(self, engine):
        engine.entities.clear()