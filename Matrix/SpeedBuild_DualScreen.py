import time
import random
import os
import sys
import threading

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "utils/ui"))

from dual_screen import DualScreenManager

from utils.data import (
    NetworkManager, game_thread_func, load_config, FRAME_DATA_LENGTH, SpeedBuildSettings
)
from utils.states import *
from utils.master import GameMaster

_CFG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "matrix_config.json")

# ============================================================
#  Data Objects
# ============================================================



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

def run_speedbuild_with_dual_screen():
    """Run SpeedBuild with dual screen setup"""
    # Initialize dual screen manager
    screen_manager = DualScreenManager("Speed Build - Control", "Speed Build - Timer")

    print("Speed Build - Dual screen setup initialized.")
    print("Use main screen to select players/difficulty and start game.")
    print("Timer will display on secondary screen.")

    game = None
    game_thread = None
    net = None

    try:
        running = True
        while running:
            # Update screens and handle input
            running = screen_manager.update(game.settings if game else None)

            # Check if game should start
            if screen_manager.is_game_started() and game is None:
                # Get configuration from dual screen
                config = screen_manager.get_game_config()

                # Create game settings
                settings = SpeedBuildSettings(config['players'], config['difficulty'])
                settings.hide_timer = True
                settings.hide_status = True
                spawn_rules = DummySpawnRules()

                def make_start(): return SBInitState(settings, spawn_rules)
                game = GameMaster(make_start, settings, spawn_rules, transitions)

                config_data = load_config(_CFG_FILE)
                net = NetworkManager(game, config=config_data)
                net.start_bg()

                # Start game thread
                game_thread = threading.Thread(target=game_thread_func, args=(game,), daemon=True)
                game_thread.start()

                print(f"Speed Build started! Players: {config['players']}, Difficulty: {config['difficulty']}")

            # Handle game stop/cleanup
            if not screen_manager.is_game_started() and game is not None:
                # User pressed stop button or game ended
                game.running = False  # Signal game to stop
                if net:
                    # Clear the LED matrix
                    black_frame = b'\x00' * FRAME_DATA_LENGTH
                    net.send_packet(black_frame)
                    # Stop network loops
                    net.running = False
                game = None
                print("Game stopped. Select new settings to play again.")

            # If game exists, handle natural game completion
            if game and not game.running:
                # Game ended naturally
                if net:
                    # Clear the LED matrix
                    black_frame = b'\x00' * FRAME_DATA_LENGTH
                    net.send_packet(black_frame)
                    # Stop network loops
                    net.running = False
                screen_manager.game_started = False
                game = None
                print("Game ended. Select new settings to play again.")

            # Small delay to prevent excessive CPU usage
            time.sleep(0.05)

    except KeyboardInterrupt:
        print("Interrupted by user")

    finally:
        if game:
            game.running = False
        if net:
            net.running = False
        screen_manager.quit()
        print("Exiting...")

if __name__ == "__main__":
    run_speedbuild_with_dual_screen()