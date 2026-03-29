"""
Core game-engine buffer and base classes for the Evil Eye room.
"""

from abc import ABC, abstractmethod

# ============================================================
#  Constants
# ============================================================

NUM_WALLS = 4
LEDS_PER_WALL = 11           # index 0 = Eye, 1-10 = Buttons
TOTAL_LEDS = NUM_WALLS * LEDS_PER_WALL
FRAME_DATA_LENGTH = LEDS_PER_WALL * NUM_WALLS * 3   # 132 bytes

# ============================================================
#  GameEngine – LED buffer, input, entity management
# ============================================================

class GameEngine:
    def __init__(self):
        self.led_states = {}
        for wall in range(1, NUM_WALLS + 1):
            for led in range(LEDS_PER_WALL):
                self.led_states[(wall, led)] = (0, 0, 0)

        self.entities = []
        self.button_states = [False] * TOTAL_LEDS
        self.prev_button_states = [False] * TOTAL_LEDS
        self._state = None

    def set_led(self, wall, led, r, g, b):
        if 1 <= wall <= NUM_WALLS and 0 <= led < LEDS_PER_WALL:
            self.led_states[(wall, led)] = (r, g, b)

    def set_eye(self, wall, r, g, b):
        self.set_led(wall, 0, r, g, b)

    def set_button(self, wall, button, r, g, b):
        self.set_led(wall, button, r, g, b)

    def set_wall(self, wall, r, g, b):
        for led in range(LEDS_PER_WALL):
            self.set_led(wall, led, r, g, b)

    def set_all(self, r, g, b):
        for wall in range(1, NUM_WALLS + 1):
            self.set_wall(wall, r, g, b)

    def clear(self):
        self.set_all(0, 0, 0)

    def render(self):
        # build_frame_data is now in network.py, but we'll import it if needed
        # or just keep the core buffer rendering here if preferred.
        # Matrix project usually puts build_frame_data in network.py.
        from .network import build_frame_data
        return build_frame_data(self.led_states)

    def snapshot_input(self):
        self.prev_button_states = list(self.button_states)

    def get_pressed(self):
        pressed = set()
        for i in range(TOTAL_LEDS):
            if self.button_states[i] and not self.prev_button_states[i]:
                wall = i // LEDS_PER_WALL + 1
                led = i % LEDS_PER_WALL
                pressed.add((wall, led))
        return pressed

    def any_pressed(self):
        for i in range(TOTAL_LEDS):
            if self.button_states[i] and not self.prev_button_states[i]:
                return True
        return False

    def change_state(self, new_state):
        if self._state is not None:
            self._state.exit(self)
        self._state = new_state
        if self._state is not None:
            self._state.enter(self)

    @property
    def state(self):
        return self._state

# ============================================================
#  Abstract GameState
# ============================================================

class GameState(ABC):
    @abstractmethod
    def enter(self, engine: GameEngine):
        pass

    @abstractmethod
    def update(self, engine: GameEngine, dt: float):
        pass

    @abstractmethod
    def exit(self, engine: GameEngine):
        pass
