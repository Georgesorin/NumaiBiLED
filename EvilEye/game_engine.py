"""
Reusable game-engine framework for the Evil Eye room.

The Evil Eye room has 4 walls, each with 1 eye LED (index 0) and 10 button
LEDs (indices 1-10), for a total of 44 LEDs.  Hardware communicates via
UDP: light commands on port 4626, button triggers on port 7800.

Provides: configuration loading, UDP networking (4-packet protocol with
8 ms hardware delays), an LED buffer with input handling and drawing
helpers, an abstract state-machine, and a GameMaster that ties it all
together.

To build a new game, subclass GameState for your concrete states,
instantiate a GameMaster (passing your initial state factory), and run.
"""

import socket
import time
import threading
import random
import os
import json
import queue
from abc import ABC, abstractmethod

# ============================================================
#  Constants
# ============================================================

NUM_WALLS = 4
LEDS_PER_WALL = 11           # index 0 = Eye, 1-10 = Buttons
TOTAL_LEDS = NUM_WALLS * LEDS_PER_WALL
FRAME_DATA_LENGTH = LEDS_PER_WALL * NUM_WALLS * 3   # 132 bytes

BLACK   = (0, 0, 0)
WHITE   = (255, 255, 255)
RED     = (255, 0, 0)
YELLOW  = (255, 255, 0)
GREEN   = (0, 255, 0)
BLUE    = (0, 0, 255)
CYAN    = (0, 255, 255)
MAGENTA = (255, 0, 255)
ORANGE  = (255, 165, 0)
PURPLE  = (128, 0, 128)

PASSWORD_ARRAY = [
    35, 63, 187, 69, 107, 178, 92, 76, 39, 69, 205, 37, 223, 255, 165, 231,
    16, 220, 99, 61, 25, 203, 203, 155, 107, 30, 92, 144, 218, 194, 226, 88,
    196, 190, 67, 195, 159, 185, 209, 24, 163, 65, 25, 172, 126, 63, 224, 61,
    160, 80, 125, 91, 239, 144, 25, 141, 183, 204, 171, 188, 255, 162, 104, 225,
    186, 91, 232, 3, 100, 208, 49, 211, 37, 192, 20, 99, 27, 92, 147, 152,
    86, 177, 53, 153, 94, 177, 200, 33, 175, 195, 15, 228, 247, 18, 244, 150,
    165, 229, 212, 96, 84, 200, 168, 191, 38, 112, 171, 116, 121, 186, 147, 203,
    30, 118, 115, 159, 238, 139, 60, 57, 235, 213, 159, 198, 160, 50, 97, 201,
    253, 242, 240, 77, 102, 12, 183, 235, 243, 247, 75, 90, 13, 236, 56, 133,
    150, 128, 138, 190, 140, 13, 213, 18, 7, 117, 255, 45, 69, 214, 179, 50,
    28, 66, 123, 239, 190, 73, 142, 218, 253, 5, 212, 174, 152, 75, 226, 226,
    172, 78, 35, 93, 250, 238, 19, 32, 247, 223, 89, 123, 86, 138, 150, 146,
    214, 192, 93, 152, 156, 211, 67, 51, 195, 165, 66, 10, 10, 31, 1, 198,
    234, 135, 34, 128, 208, 200, 213, 169, 238, 74, 221, 208, 104, 170, 166, 36,
    76, 177, 196, 3, 141, 167, 127, 56, 177, 203, 45, 107, 46, 82, 217, 139,
    168, 45, 198, 6, 43, 11, 57, 88, 182, 84, 189, 29, 35, 143, 138, 171,
]


def calculate_checksum(data):
    idx = sum(data) & 0xFF
    return PASSWORD_ARRAY[idx] if idx < len(PASSWORD_ARRAY) else 0


# ============================================================
#  Configuration
# ============================================================

def load_config(cfg_file=None):
    defaults = {
        "device_ip": "255.255.255.255",
        "send_port": 50267,
        "recv_port": 50367,
        "bind_ip": "0.0.0.0",
        "polling_rate_ms": 100,
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


# ============================================================
#  Protocol helpers
# ============================================================

def _build_start_packet(seq):
    pkt = bytearray([
        0x75,
        random.randint(0, 127), random.randint(0, 127),
        0x00, 0x08,
        0x02, 0x00, 0x00,
        0x33, 0x44,
        (seq >> 8) & 0xFF, seq & 0xFF,
        0x00, 0x00,
    ])
    pkt.append(calculate_checksum(pkt))
    return bytes(pkt)


def _build_end_packet(seq):
    pkt = bytearray([
        0x75,
        random.randint(0, 127), random.randint(0, 127),
        0x00, 0x08,
        0x02, 0x00, 0x00,
        0x55, 0x66,
        (seq >> 8) & 0xFF, seq & 0xFF,
        0x00, 0x00,
    ])
    pkt.append(calculate_checksum(pkt))
    return bytes(pkt)


def _build_command_packet(data_id, msg_loc, payload, seq):
    internal = bytes([
        0x02, 0x00, 0x00,
        (data_id >> 8) & 0xFF, data_id & 0xFF,
        (msg_loc >> 8) & 0xFF, msg_loc & 0xFF,
        (len(payload) >> 8) & 0xFF, len(payload) & 0xFF,
    ]) + payload

    hdr = bytes([
        0x75,
        random.randint(0, 127), random.randint(0, 127),
        (len(internal) >> 8) & 0xFF, len(internal) & 0xFF,
    ])
    pkt = bytearray(hdr + internal)
    pkt[10] = (seq >> 8) & 0xFF
    pkt[11] = seq & 0xFF
    pkt.append(calculate_checksum(pkt))
    return bytes(pkt)


def _build_fff0_packet(seq):
    payload = bytearray()
    for _ in range(NUM_WALLS):
        payload += bytes([(LEDS_PER_WALL >> 8) & 0xFF, LEDS_PER_WALL & 0xFF])
    return _build_command_packet(0x8877, 0xFFF0, bytes(payload), seq)


def build_frame_data(led_states):
    """
    Build 132-byte frame from led_states dict.
    led_states: {(wall 1-4, led 0-10): (r, g, b)}

    Frame layout (matching hardware shift registers):
      frame[led * 12 + (wall-1)]     = Green
      frame[led * 12 + 4 + (wall-1)] = Red
      frame[led * 12 + 8 + (wall-1)] = Blue
    """
    frame = bytearray(FRAME_DATA_LENGTH)
    for (wall, led), (r, g, b) in led_states.items():
        wall_idx = wall - 1
        if 0 <= wall_idx < NUM_WALLS and 0 <= led < LEDS_PER_WALL:
            frame[led * 12 + wall_idx] = g
            frame[led * 12 + 4 + wall_idx] = r
            frame[led * 12 + 8 + wall_idx] = b
    return bytes(frame)


# ============================================================
#  NetworkManager
# ============================================================

DISCOVERY_SEND_IP   = "169.254.162.11"
DISCOVERY_SEND_PORT = 12345
DISCOVERY_RECV_PORT = 54321
DISCOVERY_DEADLINE  = 5.0


def _build_discovery_packet():
    """Build a 0x67 discovery packet matching the Controller protocol."""
    rand1 = random.randint(0, 127)
    rand2 = random.randint(0, 127)
    payload = bytes([
        0x0A, 0x02,
        0x4B, 0x58, 0x2D, 0x48, 0x43, 0x30, 0x34,   # "KX-HC04"
        0x03, 0x00, 0x00,
        0xFF, 0xFF,
        0x00, 0x00, 0x00, 0x14,
    ])
    pkt = bytearray([0x67, rand1, rand2, len(payload)] + list(payload))
    idx = sum(pkt) & 0xFF
    pkt.append(PASSWORD_ARRAY[idx] if idx < len(PASSWORD_ARRAY) else 0)
    return bytes(pkt), rand1, rand2


def discover_evil_eye(deadline=DISCOVERY_DEADLINE):
    """
    Send a 0x67 discovery packet to DISCOVERY_SEND_IP:DISCOVERY_SEND_PORT and
    listen for 0x68 responses on 255.255.255.255:DISCOVERY_RECV_PORT.

    Collects devices for *deadline* seconds.
    Returns a list of dicts: [{"ip": ..., "mac": ..., "model": ...}, ...]
    """
    pkt, rand1, rand2 = _build_discovery_packet()

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.settimeout(0.5)

    try:
        sock.bind(("255.255.255.255", DISCOVERY_RECV_PORT))
    except Exception as e:
        print(f"[Discovery] Bind error on 255.255.255.255:{DISCOVERY_RECV_PORT}: {e}")
        sock.close()
        return []

    print(f"[Discovery] Sending 0x67 to {DISCOVERY_SEND_IP}:{DISCOVERY_SEND_PORT}")
    try:
        sock.sendto(pkt, (DISCOVERY_SEND_IP, DISCOVERY_SEND_PORT))
    except Exception as e:
        print(f"[Discovery] Send error: {e}")
        sock.close()
        return []

    devices = []
    end_time = time.time() + deadline
    while time.time() < end_time:
        try:
            data, addr = sock.recvfrom(256)
        except socket.timeout:
            continue
        except Exception:
            break

        if len(data) >= 30 and data[0] == 0x68 and data[1] == rand1 and data[2] == rand2:
            model = data[6:13].rstrip(b'\x00').decode('ascii', errors='replace')
            mac = ":".join(f"{b:02X}" for b in data[13:19])
            dev_type = data[20] if len(data) > 20 else 0
            if not any(d["ip"] == addr[0] for d in devices):
                devices.append({
                    "ip": addr[0],
                    "mac": mac,
                    "model": model,
                    "type": dev_type,
                })
                print(f"[Discovery] Found {model} (HC0{dev_type}) at {addr[0]}  MAC: {mac}")

    sock.close()
    if not devices:
        print("[Discovery] No Evil Eye controllers found.")
    return devices


class NetworkManager:
    """
    Manages UDP communication with Evil Eye hardware.

    Uses a dedicated sender thread with a queue to avoid blocking the
    game thread.  A separate receiver thread listens for 687-byte
    button-trigger packets on the configured recv_port.
    """

    def __init__(self, game, config=None):
        if config is None:
            config = load_config()
        self.game = game
        self.config = config
        self.running = True
        self._seq = 0
        self._lock = threading.Lock()

        self.send_ip = config.get("device_ip", "255.255.255.255")
        self.send_port = config.get("send_port", 50267)
        self.recv_port = config.get("recv_port", 50367)
        self.bind_ip = config.get("bind_ip", "0.0.0.0")
        self.poll_rate_ms = config.get("polling_rate_ms", 100)

        self._send_q = queue.Queue(maxsize=4)

        self._sock_send = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._sock_send.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        if self.bind_ip != "0.0.0.0":
            try:
                self._sock_send.bind((self.bind_ip, 0))
            except Exception as e:
                print(f"Warning: Could not bind send socket to {self.bind_ip}: {e}")

        self._sock_recv = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._sock_recv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._sock_recv.settimeout(0.5)
        try:
            self._sock_recv.bind(("0.0.0.0", self.recv_port))
        except Exception as e:
            print(f"Critical Error: Could not bind receive socket to port {self.recv_port}: {e}")
            self.running = False

    def _next_seq(self):
        with self._lock:
            self._seq = (self._seq + 1) & 0xFFFF
            if self._seq == 0:
                self._seq = 1
            return self._seq

    def _do_send_sequence(self, frame_data):
        seq = self._next_seq()
        endpoints = [(self.send_ip, self.send_port)]
        if self.send_ip != "127.0.0.1":
            endpoints.append(("127.0.0.1", self.send_port))
        pkts = [
            _build_start_packet(seq),
            _build_fff0_packet(seq),
            _build_command_packet(0x8877, 0x0000, frame_data, seq),
            _build_end_packet(seq),
        ]
        for pkt in pkts:
            for ep in endpoints:
                try:
                    self._sock_send.sendto(pkt, ep)
                except Exception:
                    pass
            time.sleep(0.008)

    def send_loop(self):
        while self.running:
            frame = self.game.render()
            self._do_send_sequence(frame)
            interval = max(0.01, self.poll_rate_ms / 1000.0)
            time.sleep(interval)

    def recv_loop(self):
        EXPECTED_LEN = 687
        while self.running:
            try:
                data, _ = self._sock_recv.recvfrom(1024)
            except socket.timeout:
                continue
            except Exception:
                break

            if len(data) != EXPECTED_LEN or data[0] != 0x88:
                continue

            for wall in range(1, NUM_WALLS + 1):
                base = 2 + (wall - 1) * 171
                for led in range(LEDS_PER_WALL):
                    val = data[base + 1 + led]
                    is_pressed = (val == 0xCC)
                    flat_idx = (wall - 1) * LEDS_PER_WALL + led
                    self.game.button_states[flat_idx] = is_pressed

    def start_bg(self):
        t1 = threading.Thread(target=self.send_loop, daemon=True)
        t2 = threading.Thread(target=self.recv_loop, daemon=True)
        t1.start()
        t2.start()


# ============================================================
#  GameEngine – LED buffer, input, entity management
# ============================================================

class GameEngine:
    """
    Core engine managing the 4-wall × 11-LED pixel buffer, button
    state tracking, entity list, and a pluggable state machine.

    LEDs are addressed as (wall, led_index) where wall is 1-4 and
    led_index is 0 (eye) or 1-10 (buttons).
    """

    def __init__(self):
        self.led_states = {}
        for wall in range(1, NUM_WALLS + 1):
            for led in range(LEDS_PER_WALL):
                self.led_states[(wall, led)] = (0, 0, 0)

        self.entities = []
        self.button_states = [False] * TOTAL_LEDS
        self.prev_button_states = [False] * TOTAL_LEDS
        self._state = None

    # -- LED control --

    def set_led(self, wall, led, r, g, b):
        if 1 <= wall <= NUM_WALLS and 0 <= led < LEDS_PER_WALL:
            self.led_states[(wall, led)] = (r, g, b)

    def set_eye(self, wall, r, g, b):
        self.set_led(wall, 0, r, g, b)

    def set_button(self, wall, button, r, g, b):
        """Set button LED colour. button is 1-10."""
        self.set_led(wall, button, r, g, b)

    def set_wall(self, wall, r, g, b):
        for led in range(LEDS_PER_WALL):
            self.set_led(wall, led, r, g, b)

    def set_all_eyes(self, r, g, b):
        for wall in range(1, NUM_WALLS + 1):
            self.set_eye(wall, r, g, b)

    def set_all_buttons(self, r, g, b):
        for wall in range(1, NUM_WALLS + 1):
            for btn in range(1, LEDS_PER_WALL):
                self.set_led(wall, btn, r, g, b)

    def set_all(self, r, g, b):
        for wall in range(1, NUM_WALLS + 1):
            self.set_wall(wall, r, g, b)

    def clear(self):
        self.set_all(0, 0, 0)

    def render(self):
        return build_frame_data(self.led_states)

    # -- Input helpers --

    def _flat_to_wall_led(self, flat_idx):
        wall = flat_idx // LEDS_PER_WALL + 1
        led = flat_idx % LEDS_PER_WALL
        return wall, led

    def get_pressed(self):
        """Return set of (wall, led) just pressed this tick."""
        pressed = set()
        for i in range(TOTAL_LEDS):
            if self.button_states[i] and not self.prev_button_states[i]:
                pressed.add(self._flat_to_wall_led(i))
        return pressed

    def get_held(self):
        """Return set of (wall, led) currently held down."""
        held = set()
        for i in range(TOTAL_LEDS):
            if self.button_states[i]:
                held.add(self._flat_to_wall_led(i))
        return held

    def get_released(self):
        """Return set of (wall, led) just released this tick."""
        released = set()
        for i in range(TOTAL_LEDS):
            if not self.button_states[i] and self.prev_button_states[i]:
                released.add(self._flat_to_wall_led(i))
        return released

    def any_pressed(self):
        for i in range(TOTAL_LEDS):
            if self.button_states[i] and not self.prev_button_states[i]:
                return True
        return False

    def is_pressed(self, wall, led):
        flat = (wall - 1) * LEDS_PER_WALL + led
        return (self.button_states[flat]
                and not self.prev_button_states[flat])

    def is_held(self, wall, led):
        flat = (wall - 1) * LEDS_PER_WALL + led
        return self.button_states[flat]

    def snapshot_input(self):
        self.prev_button_states = list(self.button_states)

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

    # -- Drawing helpers --

    def fill_wall_buttons(self, wall, color):
        """Set all 10 buttons on a wall to the same colour (eye unchanged)."""
        for btn in range(1, LEDS_PER_WALL):
            self.set_led(wall, btn, *color)

    def set_button_ring(self, button_index, r, g, b):
        """Set the same button index across all 4 walls."""
        for wall in range(1, NUM_WALLS + 1):
            self.set_led(wall, button_index, r, g, b)

    def dim_led(self, wall, led, factor=0.8):
        """Dim an LED by a multiplicative factor (0-1)."""
        r, g, b = self.led_states.get((wall, led), (0, 0, 0))
        self.set_led(wall, led,
                     int(r * factor), int(g * factor), int(b * factor))

    def dim_all(self, factor=0.8):
        for wall in range(1, NUM_WALLS + 1):
            for led in range(LEDS_PER_WALL):
                self.dim_led(wall, led, factor)


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


# ============================================================
#  GameMaster – owns the engine, drives the state machine
# ============================================================

class GameMaster:
    """
    Instantiate with `initial_state_factory`, a callable that returns the
    first GameState to enter (e.g. ``lambda: MyStartState()``).
    """

    def __init__(self, initial_state_factory):
        self.engine = GameEngine()
        self.running = True
        self.button_states = self.engine.button_states
        self._initial_state_factory = initial_state_factory
        self.engine.change_state(initial_state_factory())

    def tick(self, dt: float):
        state = self.engine.state
        if state is not None:
            state.update(self.engine, dt)
        self.engine.snapshot_input()

    def render(self):
        return self.engine.render()

    def restart(self):
        self.engine.entities.clear()
        self.engine.change_state(self._initial_state_factory())


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


def run_game(game_master, config=None, title="Evil Eye Game",
             discover=True):
    """Standard main-loop: run discovery, start networking, game thread, and CLI."""
    if config is None:
        config = load_config()

    if discover:
        devices = discover_evil_eye()
        if devices:
            config["device_ip"] = devices[0]["ip"]
            print(f"Using discovered device at {devices[0]['ip']} "
                  f"({devices[0]['model']})")
        else:
            print("Continuing with configured device_ip...")

    net = NetworkManager(game_master, config=config)
    net.start_bg()

    gt = threading.Thread(
        target=game_thread_func, args=(game_master,), daemon=True
    )
    gt.start()

    print(f"{title}")
    print("Commands: 'start', 'restart', 'discover', 'quit'")

    try:
        while game_master.running:
            cmd = input("> ").strip().lower()
            if cmd in ("quit", "exit"):
                game_master.running = False
                break
            elif cmd.startswith("start"):
                game_master.restart()
                print("Game started.")
            elif cmd == "restart":
                game_master.restart()
                print("Restarted.")
            elif cmd == "discover":
                devices = discover_evil_eye()
                if devices:
                    net.send_ip = devices[0]["ip"]
                    print(f"Updated target to {devices[0]['ip']} "
                          f"({devices[0]['model']})")
                else:
                    print("No device found.")
            else:
                print("Unknown command.")
    except KeyboardInterrupt:
        game_master.running = False

    net.running = False
    print("Exiting...")
