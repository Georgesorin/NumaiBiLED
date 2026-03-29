from ._abs_state import GameEngine, GameState
from ..ui.colors import RED, BLUE, GREEN, YELLOW, WHITE, PURPLE, CYAN, ORANGE

class BossBattleStage2State(GameState):
    """Stage 2: Color Resonance.
    Each wall is assigned a sub-color. All must hit their sub-color simultaneously.
    """
    RESONANCE_MAP = [
        (PURPLE, [RED, RED, BLUE, BLUE]),
        (CYAN,   [GREEN, GREEN, BLUE, BLUE]),
        (ORANGE, [RED, RED, YELLOW, YELLOW]),
        (WHITE,  [RED, GREEN, BLUE, YELLOW]),
    ]

    def __init__(self, settings, players):
        self.settings = settings
        self.players = players
        self._t = 0.0
        self._next_color_t = 0.0
        self._resonance_idx = 0
        self._current_resonance = self.RESONANCE_MAP[0] # (eye_color, wall_colors)
        
        self._completed_pulses = 0
        self._wall_hits = {} # wall: timestamp

    def enter(self, engine: GameEngine):
        engine.clear()

    def update(self, engine: GameEngine, dt: float):
        self._t += dt
        
        # Cycle Resonance Mode
        if self._t >= self._next_color_t:
            self._next_color_t = self._t + self.settings.cycle_speed
            self._resonance_idx = (self._resonance_idx + 1) % len(self.RESONANCE_MAP)
            self._current_resonance = self.RESONANCE_MAP[self._resonance_idx]

        eye_color, wall_colors = self._current_resonance

        # Input
        pressed = engine.get_pressed()
        for (wall, led) in pressed:
            # Mark hit for this wall
            self._wall_hits[wall] = self._t

        # Draw
        engine.clear_buttons()
        active_walls = set(p.wall for p in self.players)
        
        # Check if all walls are currently within their sync window
        all_synced = all(w in self._wall_hits and (self._t - self._wall_hits[w]) < self.settings.sync_window for w in active_walls)

        for i, p in enumerate(self.players):
            sub_color = wall_colors[i % len(wall_colors)]
            
            # Buttons always show the color you need to press
            for b in p.buttons:
                engine.set_button(p.wall, b, *sub_color)
            
            # Eye behavior:
            if all_synced:
                # SUCCESS RESONANCE: flash the combined color
                engine.set_eye(p.wall, *eye_color)
            elif p.wall in self._wall_hits and (self._t - self._wall_hits[p.wall]) < self.settings.sync_window:
                # INDIVIDUAL HIT: eye shows the sub-color
                engine.set_eye(p.wall, *sub_color)
            else:
                # NEUTRAL: eye is white or dim
                engine.set_eye(p.wall, *WHITE)

        # Handle State Transition on Success
        if all_synced:
            self._completed_pulses += 1
            self._wall_hits.clear() # Clear to avoid double-counting the same pulse
            
            if self._completed_pulses >= self.settings.sync_count:
                return ("stage3", {"players": self.players, "hp": 100})

    def exit(self, engine: GameEngine):
        engine.clear()
