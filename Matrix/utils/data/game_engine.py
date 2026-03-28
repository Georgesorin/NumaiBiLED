import time
import threading

from ..ui.colors import *
from .network import *

class GameEngine:
    def __init__(self):
        self.buffer = bytearray(FRAME_DATA_LENGTH)
        self.entities = []
        self.button_states = [False] * (NUM_CHANNELS * LEDS_PER_CHANNEL)
        self.prev_button_states = [False] * (NUM_CHANNELS * LEDS_PER_CHANNEL)
        self._state = None

    def set_pixel(self, x, y, r, g, b):
        if x < 0 or x >= BOARD_WIDTH or y < 0 or y >= BOARD_HEIGHT:
            return
        channel = y // 4
        row = y % 4
        idx = (row * 16 + x) if row % 2 == 0 else (row * 16 + (15 - x))
        offset = idx * 24 + channel
        if offset + 16 < len(self.buffer):
            self.buffer[offset] = g
            self.buffer[offset + 8] = r
            self.buffer[offset + 16] = b

    def get_pixel(self, x, y):
        """Return (r,g,b) for pixel at x,y. Returns (0,0,0) if out of bounds."""
        if x < 0 or x >= BOARD_WIDTH or y < 0 or y >= BOARD_HEIGHT:
            return (0, 0, 0)
        channel = y // 4
        row = y % 4
        idx = (row * 16 + x) if row % 2 == 0 else (row * 16 + (15 - x))
        offset = idx * 24 + channel
        if offset + 16 < len(self.buffer):
            g = self.buffer[offset]
            r = self.buffer[offset + 8]
            b = self.buffer[offset + 16]
            return (r, g, b)
        return (0, 0, 0)

    def brighten_region(self, x, y, w, h, factor):
        """Brighten pixels in region by multiplying RGB by factor (clamped 0..255)."""
        if factor <= 0:
            return
        for dy in range(h):
            for dx in range(w):
                px = x + dx
                py = y + dy
                r, g, b = self.get_pixel(px, py)
                nr = min(255, int(r * factor))
                ng = min(255, int(g * factor))
                nb = min(255, int(b * factor))
                self.set_pixel(px, py, nr, ng, nb)

    def clear(self):
        for i in range(len(self.buffer)):
            self.buffer[i] = 0

    def render(self):
        return bytes(self.buffer)

    def get_pressed_xy(self):
        pressed = set()
        total = NUM_CHANNELS * LEDS_PER_CHANNEL
        for i in range(total):
            if self.button_states[i] and not self.prev_button_states[i]:
                ch = i // LEDS_PER_CHANNEL
                led = i % LEDS_PER_CHANNEL
                x, y = self._ch_led_to_xy(ch, led)
                pressed.add((x, y))
        return pressed

    def get_held_xy(self):
        held = set()
        total = NUM_CHANNELS * LEDS_PER_CHANNEL
        for i in range(total):
            if self.button_states[i]:
                ch = i // LEDS_PER_CHANNEL
                led = i % LEDS_PER_CHANNEL
                x, y = self._ch_led_to_xy(ch, led)
                held.add((x, y))
        return held

    def any_pressed(self):
        total = NUM_CHANNELS * LEDS_PER_CHANNEL
        for i in range(total):
            if self.button_states[i] and not self.prev_button_states[i]:
                return True
        return False

    def snapshot_input(self):
        self.prev_button_states = list(self.button_states)

    @staticmethod
    def _ch_led_to_xy(ch, led):
        row_in_ch = led // 16
        col = led % 16
        x = col if row_in_ch % 2 == 0 else (15 - col)
        y = ch * 4 + row_in_ch
        return x, y

    def spawn_entity(self, entity):
        self.entities.append(entity)

    def remove_entity(self, entity):
        if entity in self.entities:
            self.entities.remove(entity)

    def change_state(self, new_state):
        if self._state is not None:
            self._state.exit(self)
        self._state = new_state
        if self._state is not None:
            self._state.enter(self)

    @property
    def state(self):
        return self._state

    def draw_text_small(self, text, start_x, start_y, color):
        cx = start_x
        for ch in text.upper():
            cols = FONT_3x5.get(ch, FONT_3x5.get(ch.lower(), [0, 0, 0]))
            for col_idx, col_bits in enumerate(cols):
                for row in range(5):
                    if col_bits & (1 << row):
                        self.set_pixel(cx + col_idx, start_y + row, *color)
            cx += len(cols) + 1

    def draw_text_large(self, text, start_x, start_y, color):
        cx = start_x
        for ch in text:
            cols = FONT_5x7.get(ch, FONT_5x7.get(' '))
            for col_idx, col_val in enumerate(cols):
                for row in range(7):
                    if col_val & (1 << row):
                        self.set_pixel(cx + col_idx, start_y + row, *color)
            cx += len(cols) + 1

    def draw_rect(self, position, dimensions, color):
        x, y = position
        w, h = dimensions
        for dy in range(h):
            for dx in range(w):
                self.set_pixel(x + dx, y + dy, *color)

    def draw_rect_outline(self, x, y, w, h, color):
        for dx in range(w):
            self.set_pixel(x + dx, y, *color)
            self.set_pixel(x + dx, y + h - 1, *color)
        for dy in range(h):
            self.set_pixel(x, y + dy, *color)
            self.set_pixel(x + w - 1, y + dy, *color)

    def draw_rect_outline_scaled(self, x, y, w, h, color, factor, thickness=1):
        """Draw an outline with the given thickness, scaling the base color by factor.

        `factor` multiplies RGB components (clamped to 255).
        """
        if factor <= 0:
            return
        r0, g0, b0 = color
        sr = lambda v: min(255, int(v * factor))
        for t in range(thickness):
            cx = x + t
            cy = y + t
            cw = w - 2 * t
            ch = h - 2 * t
            if cw <= 0 or ch <= 0:
                break
            r, g, b = sr(r0), sr(g0), sr(b0)
            for dx in range(cw):
                self.set_pixel(cx + dx, cy, r, g, b)
                self.set_pixel(cx + dx, cy + ch - 1, r, g, b)
            for dy in range(ch):
                self.set_pixel(cx, cy + dy, r, g, b)
                self.set_pixel(cx + cw - 1, cy + dy, r, g, b)

    def draw_progress_bar(self, x, y, w, fraction, fg_color, bg_color):
        filled = int(w * fraction)
        for dx in range(w):
            c = fg_color if dx < filled else bg_color
            self.set_pixel(x + dx, y, *c)


def game_thread_func(game, tick_interval=0.016):
    last = time.time()
    while game.running:
        now = time.time()
        dt = now - last
        last = now
        game.tick(dt)
        time.sleep(tick_interval)

def run_game(game_master, config=None, title="Game"):
    """Standard main-loop: start networking, game thread, and CLI."""
    net = NetworkManager(game_master, config=config)
    net.start_bg()

    gt = threading.Thread(target=game_thread_func, args=(game_master,), daemon=True)
    gt.start()

    print(f"{title}")
    print("Commands: 'start', 'restart', 'quit'")

    try:
        while game_master.running:
            cmd = input("> ").strip().lower()
            if cmd in ('quit', 'exit'):
                game_master.running = False
                break
            elif cmd.startswith('start'):
                game_master.restart()
                print("Game started.")
            elif cmd == 'restart':
                game_master.restart()
                print("Restarted.")
            else:
                print("Unknown command.")
    except KeyboardInterrupt:
        game_master.running = False

    net.running = False
    print("Exiting...")
