from ._abs_state import GameState
from ..ui.colors import WHITE, GREEN

class SnakeStartState(GameState):
    def __init__(self, **_kw):
        self.t = 0.0

    def enter(self, engine):
        self.t = 0.0
        engine.entities.clear()

    def update(self, engine, dt):
        self.t += dt
        engine.clear()
        if int(self.t * 3) % 2 == 0:
            engine.draw_text_large("S", 1, 2, GREEN)
            engine.draw_text_large("N", 1, 10, GREEN)
            engine.draw_text_large("K", 1, 18, GREEN)
        if self.t >= 2.0:
            engine.draw_text_small("STEP", 1, 27, WHITE)
            for px, py in engine.get_pressed_xy():
                if 1 <= px <= 15 and 27 <= py <= 31:
                    return ("play", {})

    def exit(self, engine):
        pass
