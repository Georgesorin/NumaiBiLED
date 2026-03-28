import sys
import os
import random
import socket
import json
import threading
import time

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