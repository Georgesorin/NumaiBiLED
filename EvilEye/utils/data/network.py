import socket
import time
import threading
import random
import os
import json
import queue

from .game_engine import NUM_WALLS, LEDS_PER_WALL, FRAME_DATA_LENGTH

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

def _build_start_packet(seq):
    pkt = bytearray([0x75, random.randint(0, 127), random.randint(0, 127), 0x00, 0x08, 0x02, 0x00, 0x00, 0x33, 0x44, (seq >> 8) & 0xFF, seq & 0xFF, 0x00, 0x00])
    pkt.append(calculate_checksum(pkt))
    return bytes(pkt)

def _build_end_packet(seq):
    pkt = bytearray([0x75, random.randint(0, 127), random.randint(0, 127), 0x00, 0x08, 0x02, 0x00, 0x00, 0x55, 0x66, (seq >> 8) & 0xFF, seq & 0xFF, 0x00, 0x00])
    pkt.append(calculate_checksum(pkt))
    return bytes(pkt)

def _build_command_packet(data_id, msg_loc, payload, seq):
    internal = bytes([0x02, 0x00, 0x00, (data_id >> 8) & 0xFF, data_id & 0xFF, (msg_loc >> 8) & 0xFF, msg_loc & 0xFF, (len(payload) >> 8) & 0xFF, len(payload) & 0xFF]) + payload
    hdr = bytes([0x75, random.randint(0, 127), random.randint(0, 127), (len(internal) >> 8) & 0xFF, len(internal) & 0xFF])
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
    frame = bytearray(FRAME_DATA_LENGTH)
    for (wall, led), (r, g, b) in led_states.items():
        wall_idx = wall - 1
        if 0 <= wall_idx < NUM_WALLS and 0 <= led < LEDS_PER_WALL:
            frame[led * 12 + wall_idx] = g
            frame[led * 12 + 4 + wall_idx] = r
            frame[led * 12 + 8 + wall_idx] = b
    return bytes(frame)

def get_local_interfaces():
    results = []
    try:
        import psutil
        for iface, addrs in psutil.net_if_addrs().items():
            for addr in addrs:
                if addr.family == socket.AF_INET and addr.address != "127.0.0.1":
                    bcast = addr.broadcast if addr.broadcast else "255.255.255.255"
                    results.append((iface, addr.address, bcast))
    except ImportError:
        hostname = socket.gethostname()
        for info in socket.getaddrinfo(hostname, None, socket.AF_INET):
            ip = info[4][0]
            if ip != "127.0.0.1":
                results.append(("?", ip, "255.255.255.255"))
    return results

def build_discovery_packet():
    rand1, rand2 = random.randint(0, 127), random.randint(0, 127)
    payload = bytearray([0x0A, 0x02, *b"KX-HC04", 0x03, 0x00, 0x00, 0xFF, 0xFF, 0x00, 0x00, 0x00, 0x14])
    pkt = bytearray([0x67, rand1, rand2, len(payload)]) + payload
    pkt.append(calculate_checksum(pkt))
    return pkt, rand1, rand2

def run_discovery_flow():
    interfaces = get_local_interfaces()
    if not interfaces:
        return None
    print("\n--- Network Selection ---")
    for i, (iface, ip, bcast) in enumerate(interfaces):
        print(f"[{i}] {iface} - {ip}")
    try:
        choice = int(input("\nSelect interface number: "))
        sel = interfaces[choice]
    except Exception:
        sel = interfaces[0]
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    pkt, r1, r2 = build_discovery_packet()
    try:
        sock.sendto(pkt, (sel[2], 4626))
    except Exception:
        return None
    sock.settimeout(0.5)
    end_time = time.time() + 3
    devices = []
    while time.time() < end_time:
        try:
            data, addr = sock.recvfrom(1024)
            if len(data) >= 30 and data[0] == 0x68 and data[1] == r1 and data[2] == r2:
                if addr[0] not in [d['ip'] for d in devices]:
                    devices.append({'ip': addr[0]})
        except Exception:
            continue
    sock.close()
    return devices[0]['ip'] if devices else None

class NetworkManager:
    def __init__(self, game, config=None):
        if config is None:
            config = load_config()
        self.game = game
        self.running = True
        self._seq = 0
        self._lock = threading.Lock()
        self.send_ip = config.get("device_ip", "169.254.182.44")
        self.send_port = config.get("send_port", 4626)
        self.recv_port = config.get("recv_port", 7800)
        self.poll_rate_ms = config.get("polling_rate_ms", 100)
        self._sock_send = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._sock_send.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        self._sock_recv = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._sock_recv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._sock_recv.settimeout(0.5)
        try:
            self._sock_recv.bind(("0.0.0.0", self.recv_port))
        except Exception:
            self.running = False

    def _next_seq(self):
        with self._lock:
            self._seq = (self._seq + 1) & 0xFFFF
            return self._seq or 1

    def _do_send_sequence(self, frame_data):
        seq = self._next_seq()
        endpoints = [(self.send_ip, self.send_port), ("127.0.0.1", self.send_port)]
        pkts = [_build_start_packet(seq), _build_fff0_packet(seq), _build_command_packet(0x8877, 0x0000, frame_data, seq), _build_end_packet(seq)]
        for pkt in pkts:
            for ep in endpoints:
                try: self._sock_send.sendto(pkt, ep)
                except: pass
            time.sleep(0.008)

    def send_loop(self):
        while self.running:
            frame = self.game.render()
            self._do_send_sequence(frame)
            time.sleep(max(0.01, self.poll_rate_ms / 1000.0))

    def recv_loop(self):
        while self.running:
            try:
                data, _ = self._sock_recv.recvfrom(1024)
                if len(data) == 687 and data[0] == 0x88:
                    for wall in range(1, NUM_WALLS + 1):
                        base = 2 + (wall - 1) * 171
                        for led in range(LEDS_PER_WALL):
                            self.game.button_states[(wall - 1) * LEDS_PER_WALL + led] = (data[base + 1 + led] == 0xCC)
            except: continue

    def start_bg(self):
        threading.Thread(target=self.send_loop, daemon=True).start()
        threading.Thread(target=self.recv_loop, daemon=True).start()
