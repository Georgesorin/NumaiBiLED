import random
from ._abs_state import GameState
from ..ui.colors import *
from ..data.network import BOARD_WIDTH, BOARD_HEIGHT
from ..ui.speed_build_ui import (
    PATTERNS_EASY, PATTERNS_MEDIUM, PLAYER_POSITIONS,
    get_mosaic_drawing, get_pattern_drawing
)

class SBShowState(GameState):
    def __init__(self, settings, spawn_rules, PlayerClass, tied_players=None, **kwargs):
        self.settings = settings
        self.PlayerClass = PlayerClass
        self.timer = 0.0
        self.difficulty = int(settings.difficulty)
        
        # Configure durations based on difficulty
        self.show_duration = 10.0
        self.colors_to_use = [RED, BLUE, GREEN]
        if self.difficulty == 1:
            self.show_duration, self.colors_to_use = 15.0, [RED, BLUE]
        elif self.difficulty >= 3:
            self.show_duration, self.colors_to_use = 5.0, [RED, BLUE, GREEN, YELLOW]
        random.shuffle(self.colors_to_use)

        # Build target drawing
        use_template = random.random() < 0.5
        if self.difficulty == 1:
            self.target_drawing = get_pattern_drawing(random.choice(PATTERNS_EASY), self.colors_to_use) if use_template else get_mosaic_drawing(6, self.colors_to_use)
        elif self.difficulty == 2:
            self.target_drawing = get_pattern_drawing(random.choice(PATTERNS_MEDIUM), self.colors_to_use) if use_template else get_mosaic_drawing(5, self.colors_to_use)
        else:
            self.target_drawing = get_mosaic_drawing(random.randint(1, 4), self.colors_to_use)

        # Setup players
        if tied_players:
            self.players = tied_players
        else:
            n = self.settings.player_count
            bases = PLAYER_POSITIONS[n]
            self.players = [self.PlayerClass(i+1, bases[i][0], bases[i][1]) for i in range(n)]
        
        for p in self.players:
            p.board = [[BLACK for _ in range(6)] for _ in range(6)]
            p.completion_time = None

    def enter(self, engine):
        self.timer = 0.0
        self.lobby_duration = 2.0

    def update(self, engine, dt: float):
        self.timer += dt
        engine.clear()

        if self.timer < self.lobby_duration:
            for p in self.players:
                engine.draw_rect_outline(p.base_x, p.base_y, 8, 8, WHITE)
            return

        draw_timer = self.timer - self.lobby_duration
        for p in self.players:
            engine.draw_rect_outline(p.base_x, p.base_y, 8, 8, WHITE)
            for y in range(6):
                for x in range(6):
                    engine.set_pixel(p.base_x + 1 + x, p.base_y + 1 + y, *self.target_drawing[y][x])

        time_frac = draw_timer / self.show_duration
        engine.draw_progress_bar(0, BOARD_HEIGHT - 1, BOARD_WIDTH, 1.0 - time_frac, YELLOW, BLACK)

        if draw_timer >= self.show_duration: 
            return ("play", {"players": self.players, "target_drawing": self.target_drawing, "colors_to_use": self.colors_to_use})

    def exit(self, engine): pass
