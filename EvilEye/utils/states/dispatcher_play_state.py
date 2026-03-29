import random
from ._abs_state import GameEngine, GameState
from ..data.dispatcher_data import DISPATCHER_WALL_ID
from ..ui.dispatcher_ui import render_dispatcher_wall, render_active_wall, render_idle_wall
from ..ui.colors import BLACK

class DispatcherPlayState(GameState):
    """
    Main game loop for Dispatcher game.
    """

    def __init__(self, settings, **kwargs):
        self.settings = settings
        self.data = kwargs.get("data")
        self._t = 0.0

    def enter(self, engine: GameEngine):
        engine.clear()

    def update(self, engine: GameEngine, dt: float):
        self._t += dt
        self.data.game_timer -= dt
        
        if self.data.game_timer <= 0:
            return ("end", {"players": self.data.players, "score": self.data.score})

        # Update wall timer
        self.data.wall_timer -= dt
        if self.data.wall_timer <= 0:
            self.data.generate_sequence()
            self.data.pick_active_wall()
        
        # Handle Input
        pressed = engine.get_pressed()
        if pressed:
            self._handle_input(engine, pressed)

        # Rendering
        render_dispatcher_wall(engine, self.data.dispatcher_player, False, self._t)
        
        for w in range(1, 5):
            if w == DISPATCHER_WALL_ID:
                continue
            if w == self.data.active_wall_id:
                render_active_wall(engine, w, self.data.players, self._t, self.data.wall_timer, self.data.sequence_length)
            else:
                render_idle_wall(engine, w, self._t)

    def _handle_input(self, engine, pressed):
        for (wall, led) in pressed:
            # Active Wall Input
            if wall == self.data.active_wall_id:
                player = next((p for p in self.data.players if p.wall == wall and led in p.buttons), None)
                if not player:
                    continue
                
                expected_color = self.data.current_sequence[player.progress]
                pressed_color = player.color_map.get(led, BLACK)
                
                if pressed_color == expected_color:
                    player.progress += 1
                    if player.progress >= len(self.data.current_sequence):
                        # Success!
                        self.data.score += 1
                        self.data.game_timer += 5.0 # Bonus time
                        self.data.generate_sequence()
                        self.data.pick_active_wall()
                else:
                    # Wrong button, reset progress for this wall
                    player.reset_progress()

    def exit(self, engine: GameEngine):
        engine.clear()
