import os
import random
import math
from ._abs_state import GameEngine, GameState
from ..ui.colors import RED, BLUE, GREEN, YELLOW, WHITE
from ..data.audio_manager import get_audio_manager

class BossBattleStage1State(GameState):
    """Stage 1: Synchronized Pulse.
    All players must hit buttons simultaneously when the eye matches the target color.
    """
    PALETTE = [RED, BLUE, GREEN, YELLOW, WHITE]

    def __init__(self, settings, players):
        self.settings = settings
        self.players = players
        self._t = 0.0
        self._next_color_t = 0.0
        self._color_idx = 0
        self._current_color = self.PALETTE[0]
        
        # Pick a random target color for this session
        self.target_color = random.choice(self.PALETTE)
        
        self._completed_pulses = 0
        self._wall_hits = {} # wall: timestamp

    def enter(self, engine: GameEngine):
        engine.clear()
        path = os.path.join(os.path.dirname(__file__), "..", "..", "assets", "music", "boss_battle_start.wav")
        get_audio_manager().play_music(path)

    def update(self, engine: GameEngine, dt: float):
        self._t += dt
        
        # Cycle Eye Color
        if self._t >= self._next_color_t:
            self._next_color_t = self._t + self.settings.cycle_speed
            self._color_idx = (self._color_idx + 1) % len(self.PALETTE)
            self._current_color = self.PALETTE[self._color_idx]

        # Draw
        engine.clear_buttons()
        
        # Determine the "Tell" (dim glow of the target color on buttons)
        breath = (math.sin(self._t * 2.0) + 1.2) / 2.2 # 0.1 to 1.0
        dim_target = (int(self.target_color[0] * 0.15 * breath), 
                      int(self.target_color[1] * 0.15 * breath), 
                      int(self.target_color[2] * 0.15 * breath))

        for w in range(1, self.settings.walls_used + 1):
            engine.set_eye(w, *self._current_color)
            
            # If hit in the current window, show bright target color
            if w in self._wall_hits and (self._t - self._wall_hits[w]) < self.settings.sync_window:
                for b in range(1, 11):
                    engine.set_button(w, b, *self.target_color)
            else:
                # Otherwise, show the "tell" hint
                for b in range(1, 11):
                    engine.set_button(w, b, *dim_target)

        # Input
        pressed = engine.get_pressed()
        for (wall, led) in pressed:
            # Only count hits when current eye color matches target_color
            if self._current_color == self.target_color:
                self._wall_hits[wall] = self._t
        
        # Check Synchronization
        active_walls = set(p.wall for p in self.players)
        if all(w in self._wall_hits and (self._t - self._wall_hits[w]) < self.settings.sync_window for w in active_walls):
            # SUCCESS!
            self._completed_pulses += 1
            self._wall_hits.clear()
            # Briefly flash all eyes GREEN
            for w in active_walls:
                engine.set_eye(w, *GREEN)
            
            if self._completed_pulses >= self.settings.sync_count:
                return ("stage2", {"players": self.players})

    def exit(self, engine: GameEngine):
        engine.clear()
