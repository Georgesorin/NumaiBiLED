"""
Reusable game-engine framework for the NumaiBiLED matrix.

Provides: configuration loading, UDP networking, pixel buffer with
input handling and drawing primitives, an abstract state-machine,
and a GameMaster that ties everything together.

To build a new game, subclass GameState for your concrete states,
instantiate a GameMaster (passing your initial state factory), and run.
"""

import socket
import struct
import time
import threading
import random
import os
import json
import sys
from abc import ABC, abstractmethod

from ..ui.colors import *

sys.path.insert(0, os.path.join(os.path.dirname(__file__)))
from small_font import FONT_3x5
from matrix_font import FONT_5x7

try:
    import pygame
    PYGAME_AVAILABLE = True
except ImportError:
    PYGAME_AVAILABLE = False

# ============================================================
#  Configuration
# ============================================================

def load_config(cfg_file=None):
    defaults = {
        "device_ip": "255.255.255.255",
        "send_port": 50067,
        "recv_port": 50167,
        "bind_ip": "0.0.0.0"
    }
    if cfg_file is None:
        return defaults
    try:
        if os.path.exists(cfg_file):
            with open(cfg_file, encoding="utf-8") as f:
                return {**defaults, **json.load(f)}
    except Exception:
        pass
    return defaults


NUM_CHANNELS = 8
LEDS_PER_CHANNEL = 64
FRAME_DATA_LENGTH = NUM_CHANNELS * LEDS_PER_CHANNEL * 3

BOARD_WIDTH = 16
BOARD_HEIGHT = 32

PASSWORD_ARRAY = [
    35, 63, 187, 69, 107, 178, 92, 76, 39, 69, 205, 37, 223, 255, 165, 231, 16, 220, 99, 61, 25, 203, 203,
    155, 107, 30, 92, 144, 218, 194, 226, 88, 196, 190, 67, 195, 159, 185, 209, 24, 163, 65, 25, 172, 126,
    63, 224, 61, 160, 80, 125, 91, 239, 144, 25, 141, 183, 204, 171, 188, 255, 162, 104, 225, 186, 91, 232,
    3, 100, 208, 49, 211, 37, 192, 20, 99, 27, 92, 147, 152, 86, 177, 53, 153, 94, 177, 200, 33, 175, 195,
    15, 228, 247, 18, 244, 150, 165, 229, 212, 96, 84, 200, 168, 191, 38, 112, 171, 116, 121, 186, 147, 203,
    30, 118, 115, 159, 238, 139, 60, 57, 235, 213, 159, 198, 160, 50, 97, 201, 242, 240, 77, 102, 12,
    183, 235, 243, 247, 75, 90, 13, 236, 56, 133, 150, 128, 138, 190, 140, 13, 213, 18, 7, 117, 255, 45, 69,
    214, 179, 50, 28, 66, 123, 239, 190, 73, 142, 218, 253, 5, 212, 174, 152, 75, 226, 226, 172, 78, 35, 93,
    250, 238, 19, 32, 247, 233, 89, 123, 86, 138, 150, 146, 214, 192, 93, 152, 156, 211, 67, 51, 195, 165,
    66, 10, 10, 31, 1, 198, 234, 135, 34, 128, 208, 200, 213, 169, 238, 74, 221, 208, 104, 170, 166, 36, 76,
    177, 196, 3, 141, 167, 127, 56, 177, 203, 45, 107, 46, 82, 217, 139, 168, 45, 198, 6, 43, 11, 57, 88,
    182, 84, 189, 29, 35, 143, 138, 171
]

def calculate_checksum(data):
    acc = sum(data)
    idx = acc & 0xFF
    return PASSWORD_ARRAY[idx] if idx < len(PASSWORD_ARRAY) else 0


# ============================================================
#  NetworkManager
# ============================================================

class NetworkManager:
    def __init__(self, game, config=None):
        if config is None:
            config = load_config()
        self.game = game
        self.config = config
        self.sock_send = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock_send.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        self.sock_recv = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.running = True
        self.sequence_number = 0
        self.prev_button_states = [False] * 64

        self.send_ip = config.get("device_ip", "255.255.255.255")
        self.send_port = config.get("send_port", 50067)
        listen_port = config.get("recv_port", 50167)

        bind_ip = config.get("bind_ip", "0.0.0.0")
        if bind_ip != "0.0.0.0":
            try:
                self.sock_send.bind((bind_ip, 0))
            except Exception as e:
                print(f"Warning: Could not bind send socket to {bind_ip}: {e}")

        try:
            self.sock_recv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.sock_recv.bind(("0.0.0.0", listen_port))
        except Exception as e:
            print(f"Critical Error: Could not bind receive socket to port {listen_port}: {e}")
            self.running = False

    def send_loop(self):
        while self.running:
            frame = self.game.render()
            self.send_packet(frame)
            time.sleep(0.05)

    def send_packet(self, frame_data):
        self.sequence_number = (self.sequence_number + 1) & 0xFFFF
        if self.sequence_number == 0:
            self.sequence_number = 1

        target_ip = self.send_ip
        port = self.send_port

        rand1 = random.randint(0, 127)
        rand2 = random.randint(0, 127)
        start_packet = bytearray([
            0x75, rand1, rand2, 0x00, 0x08,
            0x02, 0x00, 0x00, 0x33, 0x44,
            (self.sequence_number >> 8) & 0xFF,
            self.sequence_number & 0xFF,
            0x00, 0x00, 0x00
        ])
        start_packet.append(0x0E)
        start_packet.append(0x00)
        try:
            self.sock_send.sendto(start_packet, (target_ip, port))
            self.sock_send.sendto(start_packet, ("127.0.0.1", port))
        except Exception:
            pass

        rand1 = random.randint(0, 127)
        rand2 = random.randint(0, 127)
        fff0_payload = bytearray()
        for _ in range(NUM_CHANNELS):
            fff0_payload += bytes([(LEDS_PER_CHANNEL >> 8) & 0xFF, LEDS_PER_CHANNEL & 0xFF])

        fff0_internal = bytearray([
            0x02, 0x00, 0x00,
            0x88, 0x77,
            0xFF, 0xF0,
            (len(fff0_payload) >> 8) & 0xFF, (len(fff0_payload) & 0xFF)
        ]) + fff0_payload

        fff0_len = len(fff0_internal) - 1
        fff0_packet = bytearray([
            0x75, rand1, rand2,
            (fff0_len >> 8) & 0xFF, (fff0_len & 0xFF)
        ]) + fff0_internal
        fff0_packet.append(0x1E)
        fff0_packet.append(0x00)

        try:
            self.sock_send.sendto(fff0_packet, (target_ip, port))
            self.sock_send.sendto(fff0_packet, ("127.0.0.1", port))
        except Exception:
            pass

        chunk_size = 984
        data_packet_index = 1
        for i in range(0, len(frame_data), chunk_size):
            rand1 = random.randint(0, 127)
            rand2 = random.randint(0, 127)
            chunk = frame_data[i:i+chunk_size]

            internal_data = bytearray([
                0x02, 0x00, 0x00,
                (0x8877 >> 8) & 0xFF, (0x8877 & 0xFF),
                (data_packet_index >> 8) & 0xFF, (data_packet_index & 0xFF),
                (len(chunk) >> 8) & 0xFF, (len(chunk) & 0xFF)
            ])
            internal_data += chunk
            payload_len = len(internal_data) - 1

            packet = bytearray([
                0x75, rand1, rand2,
                (payload_len >> 8) & 0xFF, (payload_len & 0xFF)
            ]) + internal_data

            if len(chunk) == 984:
                packet.append(0x1E)
            else:
                packet.append(0x36)
            packet.append(0x00)

            try:
                self.sock_send.sendto(packet, (target_ip, port))
                self.sock_send.sendto(packet, ("127.0.0.1", port))
            except Exception:
                pass
            data_packet_index += 1
            time.sleep(0.005)

        rand1 = random.randint(0, 127)
        rand2 = random.randint(0, 127)
        end_packet = bytearray([
            0x75, rand1, rand2, 0x00, 0x08,
            0x02, 0x00, 0x00, 0x55, 0x66,
            (self.sequence_number >> 8) & 0xFF,
            self.sequence_number & 0xFF,
            0x00, 0x00, 0x00
        ])
        end_packet.append(0x0E)
        end_packet.append(0x00)
        try:
            self.sock_send.sendto(end_packet, (target_ip, port))
            self.sock_send.sendto(end_packet, ("127.0.0.1", port))
        except Exception:
            pass

    def recv_loop(self):
        while self.running:
            try:
                data, _ = self.sock_recv.recvfrom(2048)
                if len(data) >= 1373 and data[0] == 0x88:
                    for ch in range(NUM_CHANNELS):
                        base = 2 + ch * 171 + 1
                        for led_idx in range(LEDS_PER_CHANNEL):
                            if base + led_idx < len(data):
                                is_pressed = (data[base + led_idx] == 0xCC)
                                self.game.button_states[ch * LEDS_PER_CHANNEL + led_idx] = is_pressed
            except Exception:
                pass

    def start_bg(self):
        t1 = threading.Thread(target=self.send_loop, daemon=True)
        t2 = threading.Thread(target=self.recv_loop, daemon=True)
        t1.start()
        t2.start()


# ============================================================
#  GameEngine – pixel buffer, input, entity management, drawing
# ============================================================

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

    def clear(self):
        for i in range(len(self.buffer)):
            self.buffer[i] = 0

    def render(self):
        return bytes(self.buffer)

    def get_pressed_xy(self):
        """Return set of (x, y) board coordinates that were just pressed this tick."""
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
        """Return set of (x, y) board coordinates currently held down."""
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
        """Return True if any tile was just pressed this tick."""
        total = NUM_CHANNELS * LEDS_PER_CHANNEL
        for i in range(total):
            if self.button_states[i] and not self.prev_button_states[i]:
                return True
        return False

    def snapshot_input(self):
        self.prev_button_states = list(self.button_states)

    @staticmethod
    def _ch_led_to_xy(ch, led):
        """Convert (channel, led_index) back to board (x, y)."""
        row_in_ch = led // 16
        col = led % 16
        x = col if row_in_ch % 2 == 0 else (15 - col)
        y = ch * 4 + row_in_ch
        return x, y

    # -- Entity management --

    def spawn_entity(self, entity):
        self.entities.append(entity)

    def remove_entity(self, entity):
        if entity in self.entities:
            self.entities.remove(entity)

    # -- State machine --

    def change_state(self, new_state):
        if self._state is not None:
            self._state.exit(self)
        self._state = new_state
        if self._state is not None:
            self._state.enter(self)

    @property
    def state(self):
        return self._state

    # -- Drawing primitives --

    def draw_text_small(self, text, start_x, start_y, color):
        """Draw text using 3x5 font. Each char is 3 wide + 1 gap."""
        cx = start_x
        for ch in text.upper():
            cols = FONT_3x5.get(ch, FONT_3x5.get(ch.lower(), [0, 0, 0]))
            for col_idx, col_bits in enumerate(cols):
                for row in range(5):
                    if col_bits & (1 << row):
                        self.set_pixel(cx + col_idx, start_y + row, *color)
            cx += len(cols) + 1

    def draw_text_large(self, text, start_x, start_y, color):
        """Draw text using 5x7 font."""
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

    def draw_progress_bar(self, x, y, w, fraction, fg_color, bg_color):
        filled = int(w * fraction)
        for dx in range(w):
            c = fg_color if dx < filled else bg_color
            self.set_pixel(x + dx, y, *c)

# ============================================================
#  Game-loop helper
# ============================================================

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
