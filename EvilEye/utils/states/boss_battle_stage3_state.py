import random
from ._abs_state import GameEngine, GameState
from ..ui.boss_battle_ui import draw_stage3
from ..ui.colors import RED, GREEN, YELLOW, PURPLE, WHITE

class BossBattleStage3State(GameState):
    """Stage 3: Weakspots and Boss HP."""
    def __init__(self, settings, players, hp):
        self.settings = settings
        self.players = players
        self.hp = hp
        self._t = 0.0
        self._eye_states = {w: "idle" for w in range(1, settings.walls_used + 1)}
        self._weakspots = {w: [] for w in range(1, settings.walls_used + 1)}
        self._next_eye_t = 0.0
        self._next_ws_t = 0.0

    def enter(self, engine: GameEngine):
        engine.clear()

    def update(self, engine: GameEngine, dt: float):
        self._t += dt
        
        # Eye "looking" logic
        if self._t >= self._next_eye_t:
            self._next_eye_t = self._t + random.uniform(2.0, 5.0)
            target_wall = random.randint(1, self.settings.walls_used)
            for w in self._eye_states:
                self._eye_states[w] = "looking" if w == target_wall else "idle"
        
        # Weakspots logic
        if self._t >= self._next_ws_t:
            self._next_ws_t = self._t + 3.0
            for w in self._weakspots:
                self._weakspots[w] = [random.choice(p.buttons)] if (p := next((p for p in self.players if p.wall == w), None)) else []

        # Draw
        engine.clear()
        draw_stage3(engine, self._t, self.players, self._eye_states, self._weakspots, self.hp)
        
        # Input
        pressed = engine.get_pressed()
        for (wall, led) in pressed:
            if self._eye_states.get(wall) == "looking":
                # Penalty: Boss recovers HP
                self.hp = min(100, self.hp + 1)
                continue
            
            if led in self._weakspots.get(wall, []):
                self.hp -= self.settings.weakspot_damage
                self._weakspots[wall].remove(led)
        
        # Check transition
        if self.hp <= 0:
            return ("end", {"winner": True})

    def exit(self, engine: GameEngine):
        engine.clear()
