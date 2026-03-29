import json
import os
import random
import socket
import threading
import time

try:
    import psutil
except ImportError:
    psutil = None

from .game_engine import FRAME_DATA_LENGTH, LEDS_PER_WALL, NUM_WALLS

# --- Evil Eye constants ---
UDP_SEND_PORT = 4626
UDP_LISTEN_PORT = 7800
ROUND_DURATION = 60.0  # 1 minute per round (for games that use timed rounds)

EVIL_EYE_SEND_PORT = UDP_SEND_PORT
EVIL_EYE_RECV_PORT = UDP_LISTEN_PORT

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


def _calc_sum(data: bytes | bytearray) -> int:
    return PASSWORD_ARRAY[sum(data) & 0xFF]


def calculate_checksum(data):
    return _calc_sum(data)


def load_config(cfg_file=None):
    defaults = {
        "device_ip": "255.255.255.255",
        "send_port": UDP_SEND_PORT,
        "recv_port": UDP_LISTEN_PORT,
        "bind_ip": "0.0.0.0",
        "polling_rate_ms": 20,
    }
    if cfg_file is None:
        return dict(defaults)
    try:
        if os.path.exists(cfg_file):
            with open(cfg_file, encoding="utf-8") as f:
                raw = json.load(f)
            return {**defaults, **raw}
    except Exception:
        pass
    return dict(defaults)


def save_config(cfg, cfg_file):
    try:
        parent = os.path.dirname(os.path.abspath(cfg_file))
        if parent:
            os.makedirs(parent, exist_ok=True)
        with open(cfg_file, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2)
        return True
    except Exception:
        return False


def get_local_interfaces():
    """Non-loopback IPv4 interfaces for interactive discovery."""
    interfaces = []
    if psutil is None:
        return interfaces
    for iface_name, addrs in psutil.net_if_addrs().items():
        for addr in addrs:
            if addr.family == socket.AF_INET and not addr.address.startswith("127."):
                interfaces.append(
                    (iface_name, addr.address, addr.broadcast or "255.255.255.255")
                )
    return interfaces


def _get_local_interfaces():
    """All interfaces including loopback, for automatic discovery retries."""
    results = list(get_local_interfaces())
    results.append(("loopback (simulator)", "127.0.0.1", "127.0.0.1"))
    return results


def build_discovery_packet():
    r1, r2 = random.randint(0, 127), random.randint(0, 127)
    payload = bytearray(
        [0x0A, 0x02, *b"KX-HC04", 0x03, 0x00, 0x00, 0xFF, 0xFF, 0x00, 0x00, 0x00, 0x14]
    )
    pkt = bytearray([0x67, r1, r2, len(payload)]) + payload
    pkt.append(calculate_checksum(pkt))
    return pkt, r1, r2


def _run_discovery(bind_ip: str, broadcast_ip: str, timeout: float = 3.0):
    pkt, rand1, rand2 = build_discovery_packet()
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.settimeout(0.5)
    try:
        sock.bind((bind_ip if bind_ip != "127.0.0.1" else "0.0.0.0", UDP_LISTEN_PORT))
    except OSError:
        try:
            sock.bind(("0.0.0.0", UDP_LISTEN_PORT))
        except OSError:
            sock.close()
            return None

    try:
        sock.sendto(pkt, (broadcast_ip, UDP_SEND_PORT))
    except OSError:
        sock.close()
        return None

    found = None
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            data, addr = sock.recvfrom(1024)
            if (
                len(data) >= 30
                and data[0] == 0x68
                and data[1] == rand1
                and data[2] == rand2
            ):
                found = addr[0]
                break
        except socket.timeout:
            continue
        except OSError:
            break
    sock.close()
    return found


def discover_device_ip(timeout_per_iface: float = 3.0):
    for _iface, local_ip, bcast in _get_local_interfaces():
        found = _run_discovery(local_ip, bcast, timeout=timeout_per_iface)
        if found:
            return found
    return None


def configure_from_discovery(cfg: dict, cfg_file: str | None = None):
    found = discover_device_ip()
    if found:
        cfg["device_ip"] = found
        cfg["send_port"] = UDP_SEND_PORT
        cfg["recv_port"] = UDP_LISTEN_PORT
        if cfg_file:
            save_config(cfg, cfg_file)
        return cfg, True
    return cfg, False


def run_discovery_flow():
    interfaces = get_local_interfaces()
    if not interfaces:
        return None
    print("\n--- Network Selection ---")
    for i, (iface, ip, _) in enumerate(interfaces):
        print(f"[{i}] {iface} - {ip}")
    try:
        sel = interfaces[int(input("\nSelect interface number: "))]
    except Exception:
        sel = interfaces[0]

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    try:
        sock.bind((sel[1], UDP_LISTEN_PORT))
    except OSError:
        pass

    pkt, r1, r2 = build_discovery_packet()
    try:
        sock.sendto(pkt, (sel[2], UDP_SEND_PORT))
    except OSError:
        return None

    sock.settimeout(0.5)
    end_time = time.time() + 3
    devices = []
    while time.time() < end_time:
        try:
            data, addr = sock.recvfrom(1024)
            if len(data) >= 30 and data[0] == 0x68 and data[1] == r1 and data[2] == r2:
                devices.append(addr[0])
                print(f"Found Evil Eye at {addr[0]}")
        except Exception:
            pass
    sock.close()
    return devices[0] if devices else "127.0.0.1"


def build_frame_data(led_states):
    frame = bytearray(FRAME_DATA_LENGTH)
    for (wall, led), (r, g, b) in led_states.items():
        wall_idx = wall - 1
        if 0 <= wall_idx < NUM_WALLS and 0 <= led < LEDS_PER_WALL:
            frame[led * 12 + wall_idx] = g
            frame[led * 12 + 4 + wall_idx] = r
            frame[led * 12 + 8 + wall_idx] = b
    return bytes(frame)


class NetworkManager:
    def __init__(self, game, config=None):
        if config is None:
            config = load_config()
        self.game = game
        self.running = True
        self.sequence_number = 0

        if config.get("device_ip") and config.get("device_ip") not in (
            None,
            "",
            "255.255.255.255",
        ):
            self.target_ip = config["device_ip"]
        else:
            self.target_ip = run_discovery_flow() or "127.0.0.1"

        self.send_port = int(config.get("send_port", UDP_SEND_PORT))
        self.recv_port = int(config.get("recv_port", UDP_LISTEN_PORT))
        self.poll_rate_ms = float(config.get("polling_rate_ms", 20))

        self.sock_send = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock_recv = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            self.sock_recv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.sock_recv.bind(("0.0.0.0", self.recv_port))
        except Exception:
            self.running = False

    def send_loop(self):
        interval = max(0.01, self.poll_rate_ms / 1000.0)
        while self.running:
            self.send_packet(self.game.render())
            time.sleep(interval)

    def build_packet(self, cmd_h, cmd_l, payload=b""):
        internal = bytearray([0x02, 0x00, 0x00, cmd_h, cmd_l]) + payload
        length = len(internal) - 1
        r1, r2 = random.randint(0, 127), random.randint(0, 127)
        pkt = bytearray([0x75, r1, r2, (length >> 8) & 0xFF, length & 0xFF]) + internal
        pkt.append(calculate_checksum(pkt))
        return pkt

    def send_packet(self, frame_data):
        self.sequence_number = (self.sequence_number + 1) & 0xFFFF
        if self.sequence_number == 0:
            self.sequence_number = 1
        seq_h = (self.sequence_number >> 8) & 0xFF
        seq_l = self.sequence_number & 0xFF

        p1 = self.build_packet(0x33, 0x44, bytearray([seq_h, seq_l, 0x00, 0x00, 0x00]))
        p2 = self.build_packet(0xFF, 0xF0, b"\x00\x0B" * 4)
        p3 = self.build_packet(
            0x88,
            0x77,
            bytearray(
                [
                    0x00,
                    0x01,
                    (len(frame_data) >> 8) & 0xFF,
                    len(frame_data) & 0xFF,
                ]
            )
            + frame_data,
        )
        p4 = self.build_packet(0x55, 0x66, bytearray([seq_h, seq_l, 0x00, 0x00, 0x00]))

        try:
            target = (self.target_ip, self.send_port)
            for p in (p1, p2, p3, p4):
                self.sock_send.sendto(p, target)
                time.sleep(0.008)
        except Exception:
            pass

    def recv_loop(self):
        while self.running:
            try:
                data, _ = self.sock_recv.recvfrom(2048)
                if len(data) == 687 and data[0] == 0x88:
                    with self.game.lock:
                        for ch in range(1, 5):
                            base = 2 + (ch - 1) * 171
                            for led in range(11):
                                idx = (ch - 1) * LEDS_PER_WALL + led
                                self.game.button_states[idx] = (
                                    data[base + 1 + led] == 0xCC
                                )
            except Exception:
                pass

    def start_bg(self):
        threading.Thread(target=self.send_loop, daemon=True).start()
        threading.Thread(target=self.recv_loop, daemon=True).start()
