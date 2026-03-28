from ._abs_state import GameState
from ..ui.colors import *
from ..data.network import BOARD_WIDTH, BOARD_HEIGHT
import math

GRAY = (100, 100, 100)

class SBPlayState(GameState):
    def __init__(self, settings, spawn_rules, players, target_drawing, colors_to_use, **kwargs):
        self.settings = settings
        self.players = players
        self.target_drawing = target_drawing
        # Paint and background cycle: only colors actually in the drawing
        self.draw_colors = list(colors_to_use)
        self.timer = 0.0
        self.color_index = 0
        self.active_color = self.draw_colors[0] if self.draw_colors else GRAY
        self.color_timer = 0.0
        
        diff = int(settings.difficulty)
        self.play_duration, self.cycle_time = 45.0, 3.0
        if diff == 1: self.play_duration, self.cycle_time = 60.0, 4.0
        elif diff >= 3: self.play_duration, self.cycle_time = 30.0, 2.0

        # Keep each color active longer for slower cycling
        self.cycle_time *= 1.5
        
        self.settings.total_time = self.play_duration
        self.settings.status_text = "BUILD"

    def enter(self, engine): pass

    def _blend_color(self, color, factor):
        """Blend color with black based on factor (0.0 to 1.0) for darker shades"""
        return tuple(int(c * factor) for c in color)

    def _wave_gradient(self, timer, diagonal_pos, wave_width=3):
        """Calculate wave gradient intensity based on diagonal position"""
        # wave_width is how many pixels wide the gradient is
        distance = diagonal_pos - timer * 5
        normalized = (distance % (2 * wave_width)) / wave_width
        if normalized > 1:
            normalized = 2 - normalized
        return normalized

    def _get_brightness_level(self, intensity):
        """Convert intensity (0-1) to one of 3 brightness levels"""
        if intensity < 0.33:
            return 0.55  # lighter dark variant
        elif intensity < 0.66:
            return 0.75  # lighter medium variant
        else:
            return 1.0

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
                    # Paint with the current color; do not toggle/delete
                    p.board[cy][cx] = self.active_color

        for p in self.players:
            match = all(p.board[y][x] == self.target_drawing[y][x] for y in range(6) for x in range(6))
            p.completion_time = self.timer if match and p.completion_time is None else (None if not match else p.completion_time)

        # Draw gray background
        engine.draw_rect((0, 0), (BOARD_WIDTH, BOARD_HEIGHT), GRAY)
        
        # Draw diagonal wave gradient across the entire dead space
        for y in range(BOARD_HEIGHT):
            for x in range(BOARD_WIDTH):
                # Check if this pixel is in a player's board area
                in_player_area = False
                for p in self.players:
                    if p.base_x <= x < p.base_x + 8 and p.base_y <= y < p.base_y + 8:
                        in_player_area = True
                        break
                
                # If not in player area, draw the diagonal gradient
                if not in_player_area:
                    diagonal_pos = x + y
                    intensity = self._wave_gradient(self.timer, diagonal_pos)
                    brightness = self._get_brightness_level(intensity)
                    color = self._blend_color(self.active_color, brightness)
                    engine.set_pixel(x, y, *color)
        
        for p in self.players:
            engine.draw_rect((p.base_x, p.base_y), (8, 8), GRAY)
            engine.draw_rect_outline(p.base_x, p.base_y, 8, 8, DARKER_WHITE)
            for cy in range(6):
                for cx in range(6):
                    engine.set_pixel(p.base_x + 1 + cx, p.base_y + 1 + cy, *p.board[cy][cx])

        self.settings.time_left = max(0.0, self.play_duration - self.timer)
        
        # Check if all players have perfect scores
        if all(p.completion_time is not None for p in self.players):
            return ("review", {"players": self.players, "target_drawing": self.target_drawing})
        
        if self.timer >= self.play_duration:
            return ("review", {"players": self.players, "target_drawing": self.target_drawing})

    def exit(self, engine): pass
