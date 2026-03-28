import time
import random
import os
import sys
import threading

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from utils.data import (
    NetworkManager, game_thread_func, load_config
)
from utils.states import *
from utils.master import GameMaster

_CFG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "matrix_config.json")

# ============================================================
#  Data Objects
# ============================================================

class SpeedBuildSettings:
    def __init__(self, player_count, difficulty):
        self.player_count = player_count
        self.difficulty = difficulty

class DummySpawnRules:
    def reset(self): pass

class Player:
    def __init__(self, pid, base_x, base_y):
        self.id = pid
        self.base_x = base_x
        self.base_y = base_y
        self.board = [[(0,0,0) for _ in range(6)] for _ in range(6)]
        self.score = 0
        self.completion_time = None

# ============================================================
#  Main Loop & Transitions
# ============================================================

transitions = {
    "init":   lambda s, sr, **k: SBInitState(s, sr, **k),
    "show":   lambda s, sr, **k: SBShowState(s, sr, PlayerClass=Player, **k),
    "play":   lambda s, sr, **k: SBPlayState(s, sr, **k),
    "review": lambda s, sr, **k: SBReviewState(s, sr, **k),
}

def _prompt_settings():
    print("\n=== Memory Matrix - Setup ===\n")
    while True:
        try:
            n = int(input("Number of players (2-6): ").strip())
            if 1 <= n <= 6: break
            print("  Please enter a number between 1 and 6.")
        except ValueError: print("  Invalid input.")
    while True:
        try:
            d = int(input("Difficulty (1: Easy, 2: Medium, 3: Hard): ").strip())
            if 1 <= d <= 3: break
            print("  Please enter 1, 2, or 3.")
        except ValueError: print("  Invalid input.")
    return SpeedBuildSettings(n, d)

if __name__ == "__main__":
    config = load_config(_CFG_FILE)
    settings = _prompt_settings()
    spawn_rules = DummySpawnRules()
    
    def make_start(): return SBInitState(settings, spawn_rules)
    game = GameMaster(make_start, settings, spawn_rules, transitions)
    net = NetworkManager(game, config=config)
    net.start_bg()

    gt = threading.Thread(target=game_thread_func, args=(game,), daemon=True)
    gt.start()

    print("Memory Matrix Game - Speed Build!")
    print("Commands: 'start', 'restart', 'setup', 'quit'")

    try:
        while game.running:
            cmd = input("> ").strip().lower()
            if cmd in ('quit', 'exit'):
                game.running = False
            elif cmd == 'start':
                game.engine.change_state(transitions["show"](settings, spawn_rules))
                print(f"Game started! Players: {settings.player_count}, Difficulty: {settings.difficulty}")
            elif cmd == 'restart':
                game.restart()
                print("Game reset to Lobby.")
            elif cmd == 'setup':
                settings = _prompt_settings()
                game.settings = settings
                game.restart()
                print("Settings applied.")
            else:
                print("Unknown command. Try: start, restart, setup, quit")
    except KeyboardInterrupt:
        game.running = False

    net.running = False
    print("Exiting...")
