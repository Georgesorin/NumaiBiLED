from ._abs_state import GameState
from ..ui.colors import WHITE, RED, GREEN, YELLOW
from ..game_engine.snake_logic import HEAD_COL, BODY_COL

class SnakeEndState(GameState):
    def __init__(self, play_time=0, snake_ate=0, players_destroyed=0,
                 reason="hp_lost", **_kw):
        self.play_time = play_time
        self.snake_ate = snake_ate
        self.players_destroyed = players_destroyed
        self.reason = reason
        self.win = reason == "starved" or players_destroyed > snake_ate
        self.t = 0.0

    def enter(self, engine):
        self.t = 0.0
        engine.entities.clear()

    def update(self, engine, dt):
        self.t += dt
        engine.clear()

        # header — WIN or LOSE, blinking
        if self.win:
            if int(self.t * 3) % 2 == 0:
                engine.draw_text_small("YOU", 3, 0, GREEN)
                engine.draw_text_small("WIN!", 2, 6, GREEN)
        else:
            if int(self.t * 3) % 2 == 0:
                engine.draw_text_small("YOU", 3, 0, RED)
                engine.draw_text_small("LOSE", 2, 6, RED)

        # snake ate  (snake icon = green square + count)
        engine.set_pixel(1, 15, *BODY_COL)
        engine.set_pixel(2, 15, *BODY_COL)
        engine.set_pixel(3, 15, *HEAD_COL)
        sa = str(self.snake_ate)
        engine.draw_text_small(sa, 6, 13, RED)

        # players destroyed  (foot icon = white square + count)
        engine.set_pixel(1, 20, *WHITE)
        engine.set_pixel(1, 21, *WHITE)
        engine.set_pixel(2, 20, *WHITE)
        engine.set_pixel(2, 21, *WHITE)
        engine.set_pixel(3, 19, *WHITE)
        engine.set_pixel(3, 22, *WHITE)
        pd = str(self.players_destroyed)
        engine.draw_text_small(pd, 6, 19, GREEN)

        # time
        secs = str(int(self.play_time))
        engine.draw_text_small(secs + "S", 1, 26, YELLOW)

        # wait 7s then any press to restart
        if self.t > 7.0 and engine.any_pressed():
            return ("start", {})

    def exit(self, engine):
        engine.entities.clear()
