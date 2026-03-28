import random
from ._abs_state import GameState
from ..ui.colors import *
from ..ui.speed_build_ui import (
    DIFFICULTY_PATTERNS, DIFFICULTY_MAX_COLORS, ALL_COLORS,
    get_mosaic_drawing, get_pattern_drawing
)

class SBInitState(GameState):
    def __init__(self, settings, spawn_rules, **kwargs):
        self.settings = settings
        self.settings.status_text = "LOBBY"
        self.settings.time_left = 0.0
        self.settings.total_time = 0.0
        self.display_timer = 0.0
        self.current_drawing = [[BLACK for _ in range(6)] for _ in range(6)]

    def enter(self, engine):
        self._new_drawing()
        
    def _new_drawing(self):
        colors = list(ALL_COLORS)
        random.shuffle(colors)
        difficulty = int(self.settings.difficulty)
        max_colors = DIFFICULTY_MAX_COLORS.get(difficulty, len(colors))
        colors = colors[:max_colors]
        patterns = DIFFICULTY_PATTERNS.get(difficulty, [])
        use_template = random.random() < 0.5 and len(patterns) > 0
        if use_template:
            t = random.choice(patterns)
            self.current_drawing = get_pattern_drawing(t, colors)
        else:
            self.current_drawing = get_mosaic_drawing(random.randint(1, 6), colors)

    def update(self, engine, dt: float):
        engine.clear()
        pressed = engine.get_pressed_xy()
        if any(1 <= x <= 17 and 12 <= y <= 18 for x, y in pressed):
            return ("show", {})

        self.display_timer += dt
        if self.display_timer >= 2.0:
            self.display_timer = 0.0
            self._new_drawing()
            
        for ox, oy in [(5, 2), (5, 24)]:
            for y in range(6):
                for x in range(6):
                    c = self.current_drawing[y][x]
                    if c != BLACK: engine.set_pixel(ox+x, oy+y, *c)
        engine.draw_text_large("GO!", 1, 12, WHITE)

    def exit(self, engine): pass
