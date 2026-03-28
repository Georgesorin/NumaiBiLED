import random
from ._abs_state import GameState
from ..ui.colors import *
from ..ui.speed_build_ui import (
    PATTERNS_EASY, PATTERNS_MEDIUM, 
    get_mosaic_drawing, get_pattern_drawing
)

class SBInitState(GameState):
    def __init__(self, settings, spawn_rules, **kwargs):
        self.settings = settings
        self.display_timer = 0.0
        self.colors_pool = [RED, BLUE, GREEN, YELLOW, CYAN, MAGENTA, ORANGE]
        self.current_drawing = [[BLACK for _ in range(6)] for _ in range(6)]

    def enter(self, engine):
        self._new_drawing()
        
    def _new_drawing(self):
        random.shuffle(self.colors_pool)
        use_template = random.random() < 0.5
        if use_template:
            t = random.choice(PATTERNS_EASY + PATTERNS_MEDIUM)
            self.current_drawing = get_pattern_drawing(t, self.colors_pool)
        else:
            self.current_drawing = get_mosaic_drawing(random.randint(1, 6), self.colors_pool)

    def update(self, engine, dt: float):
        engine.clear()
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
