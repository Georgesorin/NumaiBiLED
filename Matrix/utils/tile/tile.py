import time

from ..ui.colors import *

class Tile:
    def __init__(self, position, dimensions, color, timeout_duration):
        self.position = position
        self.dimensions = dimensions
        self.color = color
        self.timeout_duration = timeout_duration

        self.last_pressed_time = time.time()
        self.alive = True
        self.ever_pressed = False
        self.flash_phase = 0.0

    @property
    def should_kill(self):
        return (time.time() - self.last_pressed_time) > self.timeout_duration

    @property
    def get_timeout(self):
        return max(0.0, self.timeout_duration - (time.time() - self.last_pressed_time))

    @property
    def get_urgency(self):
        """0.0 = just pressed, 1.0 = about to expire."""
        elapsed = time.time() - self.last_pressed_time
        return min(1.0, elapsed / self.timeout_duration)

    def contains_tile(self, tx, ty):
        x, y = self.position
        w, h = self.dimensions
        return x <= tx < x + w and y <= ty < y + h

    def press(self):
        self.last_pressed_time = time.time()
        self.ever_pressed = True

    def get_position(self):
        w, h = self.dimensions
        for dy in range(h):
            for dx in range(w):
                x, y = self.position
                yield (x + dx, y + dy)

    def get_color(self):
        u = self.get_urgency
        if u < 0.5:
            return self.color
        freq = 2 + int(u * 10)
        self.flash_phase += 0.05
        on = (int(self.flash_phase * freq) % 2) == 0
        if u > 0.85:
            return RED if on else BLACK
        return self.color if on else self._dim(self.color, 0.3)

    @staticmethod
    def _dim(color, factor):
        return tuple(max(0, int(c * factor)) for c in color)
