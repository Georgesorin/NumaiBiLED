import random
from ._abs_state import GameState
from ..ui.colors import *
from ..data.network import BOARD_WIDTH, BOARD_HEIGHT
from ..ui.speed_build_ui import (
    DIFFICULTY_PATTERNS, DIFFICULTY_MAX_COLORS, ALL_COLORS, PLAYER_POSITIONS,
    get_mosaic_drawing, get_pattern_drawing, extract_colors
)

GRAY = (100, 100, 100)
import os
try:
    import pygame
except Exception:
    pygame = None

class SBShowState(GameState):
    def __init__(self, settings, spawn_rules, PlayerClass, tied_players=None, **kwargs):
        self.settings = settings
        self.PlayerClass = PlayerClass
        self.timer = 0.0
        self.difficulty = int(settings.difficulty)
        
        # Timing based on difficulty (colors are NOT)
        self.show_duration = 10.0
        if self.difficulty == 1:
            self.show_duration = 15.0
        elif self.difficulty >= 3:
            self.show_duration = 5.0
        
        self.settings.total_time = self.show_duration
        self.settings.status_text = "MEMORIZE"
        self.settings.time_left = self.show_duration
        self.settings.hide_timer = False
        self.settings.hide_status = False

        # Build target drawing — cap color pool by difficulty
        colors = list(ALL_COLORS)
        random.shuffle(colors)
        max_colors = DIFFICULTY_MAX_COLORS.get(self.difficulty, len(colors))
        colors = colors[:max_colors]
        patterns = DIFFICULTY_PATTERNS.get(self.difficulty, [])
        use_template = random.random() < 0.5 and len(patterns) > 0
        if use_template:
            self.target_drawing = get_pattern_drawing(random.choice(patterns), colors)
        else:
            self.target_drawing = get_mosaic_drawing(random.randint(1, 6), colors)

        # Extract only the colors actually used in this drawing
        self.colors_to_use = extract_colors(self.target_drawing)

        # Setup players
        if tied_players:
            self.players = tied_players
        else:
            n = self.settings.player_count
            bases = PLAYER_POSITIONS[n]
            self.players = [self.PlayerClass(i+1, bases[i][0], bases[i][1]) for i in range(n)]
        
        for p in self.players:
            p.board = [[GRAY for _ in range(6)] for _ in range(6)]
            p.completion_time = None

        # Audio state
        self._pygame = pygame
        self.start_music_loaded = False
        self.start_music_started = False
        self.start_music_volume = 0.7

    def _init_start_music(self):
        if not self._pygame:
            return
        try:
            if not self._pygame.mixer.get_init():
                self._pygame.mixer.init()
            base = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'assets'))
            music_path = os.path.join(base, 'music', 'speed_build_start.mp3')
            if os.path.exists(music_path):
                try:
                    self._pygame.mixer.music.load(music_path)
                    self._pygame.mixer.music.set_volume(self.start_music_volume)
                    self.start_music_loaded = True
                except Exception:
                    self.start_music_loaded = False
        except Exception:
            self.start_music_loaded = False

    def enter(self, engine):
        self.timer = 0.0
        self.lobby_duration = 2.0

    def update(self, engine, dt: float):
        self.timer += dt
        engine.clear()

        if self.timer < self.lobby_duration:
            for p in self.players:
                engine.draw_rect_outline(p.base_x, p.base_y, 8, 8, DARKER_WHITE)
            return

        draw_timer = self.timer - self.lobby_duration
        # Start the intro/start music when the drawings are first shown
        if not self.start_music_started:
            # Use central audio manager to play the start track with a gentle fade
            from ..data.audio_manager import get_audio_manager
            _audio = get_audio_manager()
            base = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'assets'))
            music_path = os.path.join(base, 'music', 'speed_build_start.mp3')
            _audio.play_music(music_path, loop=0, fade_ms=200)
            self.start_music_started = True

        self.settings.time_left = max(0.0, self.show_duration - draw_timer)
        
        for p in self.players:
            engine.draw_rect_outline(p.base_x, p.base_y, 8, 8, DARKER_WHITE)
            for y in range(6):
                for x in range(6):
                    engine.set_pixel(p.base_x + 1 + x, p.base_y + 1 + y, *self.target_drawing[y][x])

        if draw_timer >= self.show_duration: 
            return ("play", {"players": self.players, "target_drawing": self.target_drawing, "colors_to_use": self.colors_to_use})

    def exit(self, engine): pass
