from ._abs_state import GameState
from ..ui.colors import *
from ..data.network import BOARD_WIDTH, BOARD_HEIGHT

class SBPlayState(GameState):
    def __init__(self, settings, spawn_rules, players, target_drawing, colors_to_use, **kwargs):
        self.settings = settings
        self.players = players
        self.target_drawing = target_drawing
        self.draw_colors = colors_to_use
        self.timer = 0.0
        self.color_index = 0
        self.active_color = self.draw_colors[0]
        self.color_timer = 0.0
        
        diff = int(settings.difficulty)
        self.play_duration, self.cycle_time = 45.0, 3.0
        if diff == 1: self.play_duration, self.cycle_time = 60.0, 4.0
        elif diff >= 3: self.play_duration, self.cycle_time = 30.0, 2.0

    def enter(self, engine): pass

    def update(self, engine, dt: float):
        self.timer += dt
        self.color_timer += dt
        if self.color_timer >= self.cycle_time:
            self.color_timer, self.color_index = 0.0, (self.color_index + 1) % len(self.draw_colors)
            self.active_color = self.draw_colors[self.color_index]

        engine.clear()
        pressed = engine.get_pressed_xy()
        for x, y in pressed:
            for p in self.players:
                if p.base_x + 1 <= x <= p.base_x + 6 and p.base_y + 1 <= y <= p.base_y + 6:
                    cy, cx = y - p.base_y - 1, x - p.base_x - 1
                    p.board[cy][cx] = BLACK if p.board[cy][cx] == self.active_color else self.active_color

        for p in self.players:
            match = all(p.board[y][x] == self.target_drawing[y][x] for y in range(6) for x in range(6))
            p.completion_time = self.timer if match and p.completion_time is None else (None if not match else p.completion_time)

        engine.draw_rect((0, 0), (BOARD_WIDTH, BOARD_HEIGHT), self.active_color)
        for p in self.players:
            engine.draw_rect((p.base_x, p.base_y), (8, 8), BLACK)
            engine.draw_rect_outline(p.base_x, p.base_y, 8, 8, WHITE)
            for cy in range(6):
                for cx in range(6): engine.set_pixel(p.base_x + 1 + cx, p.base_y + 1 + cy, *p.board[cy][cx])

        engine.draw_progress_bar(0, BOARD_HEIGHT - 1, BOARD_WIDTH, 1.0 - self.timer / self.play_duration, YELLOW, BLACK)
        
        # Check if all players have perfect scores
        if all(p.completion_time is not None for p in self.players):
            return ("review", {"players": self.players, "target_drawing": self.target_drawing})
        
        if self.timer >= self.play_duration:
            return ("review", {"players": self.players, "target_drawing": self.target_drawing})

    def exit(self, engine): pass
