from ._abs_state import GameEngine, GameState
from ..ui.colors import RED, BLUE, GREEN, YELLOW, WHITE

class BossBattleStage1State(GameState):
    """Stage 1: Synchronized Pulse.
    All players must hit buttons simultaneously when the eye is WHITE.
    """
    TARGET_COLOR = WHITE
    PALETTE = [RED, BLUE, GREEN, YELLOW, WHITE]

    def __init__(self, settings, players):
        self.settings = settings
        self.players = players
        self._t = 0.0
        self._next_color_t = 0.0
        self._current_color = self.PALETTE[0]
        self._color_idx = 0
        
        self._completed_pulses = 0
        self._wall_hits = {} # wall: timestamp

    def enter(self, engine: GameEngine):
        engine.clear()

    def update(self, engine: GameEngine, dt: float):
        self._t += dt
        
        # Cycle Eye Color
        if self._t >= self._next_color_t:
            self._next_color_t = self._t + self.settings.cycle_speed
            self._color_idx = (self._color_idx + 1) % len(self.PALETTE)
            self._current_color = self.PALETTE[self._color_idx]

        # Draw
        engine.clear_buttons()
        for w in range(1, self.settings.walls_used + 1):
            engine.set_eye(w, *self._current_color)
            
            # Visual feedback for hits in the current window
            if w in self._wall_hits and (self._t - self._wall_hits[w]) < self.settings.sync_window:
                for b in range(1, 11):
                    engine.set_button(w, b, *self.TARGET_COLOR)

        # Input
        pressed = engine.get_pressed()
        for (wall, led) in pressed:
            # Only count hits when current color is TARGET_COLOR
            if self._current_color == self.TARGET_COLOR:
                self._wall_hits[wall] = self._t
        
        # Check Synchronization
        # We need all Walls to have a hit within the sync_window
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
