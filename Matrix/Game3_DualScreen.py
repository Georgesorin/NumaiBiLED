import os
import threading
import sys
import time

# Add dual screen manager path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "utils/ui"))
from dual_screen import DualScreenManager

from utils.data import (
    NetworkManager, game_thread_func, load_config, FRAME_DATA_LENGTH, SnakeSettings
)
from utils.master import GameMaster
from utils.states import SnakeStartState, SnakePlayState, SnakeEndState

_TRANSITIONS = {
    "start": lambda s, _r, **kw: SnakeStartState(**kw),
    "play":  lambda s, _r, **kw: SnakePlayState(settings=s, **kw),
    "end":   lambda s, _r, **kw: SnakeEndState(**kw),
}

def run_snake_dual_screen():
    screen_manager = DualScreenManager("Snake - Control", "Snake - Timer")
    
    game = None
    net = None

    class DummySettings:
        hide_timer = True
        hide_status = True
    dummy_s = DummySettings()

    try:
        running = True
        while running:
            s_to_pass = game.settings if game else dummy_s
            running = screen_manager.update(s_to_pass)

            if screen_manager.is_game_started() and game is None:
                config = screen_manager.get_game_config()
                
                # Map 1,2,3 to difficulty names
                diff_map = {1: "easy", 2: "medium", 3: "hard"}
                diff_name = diff_map.get(config['difficulty'], "medium")
                
                settings = SnakeSettings(config['players'], diff_name)
                
                game = GameMaster(lambda: SnakeStartState(), settings, None, _TRANSITIONS)
                net = NetworkManager(game, config=load_config())
                net.start_bg()

                gt = threading.Thread(target=game_thread_func, args=(game,), daemon=True)
                gt.start()
                print(f"Snake started! Players: {config['players']}, Difficulty: {diff_name}")

            if not screen_manager.is_game_started() and game is not None:
                game.running = False
                if net:
                    net.send_packet(b'\x00' * FRAME_DATA_LENGTH)
                    net.running = False
                game = None
                print("Game stopped.")

            if game and not game.running:
                if net:
                    net.send_packet(b'\x00' * FRAME_DATA_LENGTH)
                    net.running = False
                screen_manager.game_started = False
                game = None
                print("Game ended.")

            time.sleep(0.05)

    except KeyboardInterrupt:
        pass
    finally:
        if game: game.running = False
        if net: net.running = False
        screen_manager.quit()

if __name__ == "__main__":
    run_snake_dual_screen()
