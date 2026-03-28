import os
import threading
import sys

# Add dual screen manager
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "utils/ui"))
from dual_screen import DualScreenManager

from utils.data import (
    NetworkManager,
    game_thread_func,
    BOARD_WIDTH,
    FRAME_DATA_LENGTH
)

from utils.scaling import SpawnRules

from utils.states import GameStartState, InitialTilePatternState, TileSpawnState, PlayState, GameOverState

from utils.master import GameMaster
from utils.ui import prompt_render

transitions = {
    "start": lambda settings, spawn_rules, **kwargs: GameStartState(settings, spawn_rules, **kwargs),
    "initial_spawn": lambda settings, spawn_rules, **kwargs: InitialTilePatternState(settings, spawn_rules, **kwargs),
    "spawn": lambda settings, spawn_rules, **kwargs: TileSpawnState(settings, spawn_rules, **kwargs),
    "play": lambda settings, spawn_rules, **kwargs: PlayState(settings, spawn_rules, **kwargs),
    "end": lambda settings, spawn_rules, **kwargs: GameOverState(settings, spawn_rules, **kwargs),
}

def run_game_with_dual_screen():
    """Run Game1 with dual screen setup"""
    # Initialize dual screen manager
    screen_manager = DualScreenManager("Keep Alive - Control", "Keep Alive - Timer")

    print("Dual screen setup initialized.")
    print("Use main screen to select players/difficulty and start game.")
    print("Timer will display on secondary screen.")

    game = None
    game_thread = None
    net = None

    try:
        running = True
        while running:
            # Update screens and handle input
            running = screen_manager.update()

            # Check if game should start
            if screen_manager.is_game_started() and game is None:
                # Get configuration from dual screen
                config = screen_manager.get_game_config()

                # Create game settings (convert to expected format)
                from utils.scaling import GameSettings
                # Convert integer difficulty to string key
                diff_names = ["easy", "medium", "hard"]  # Matches DIFFICULTIES keys
                difficulty_key = diff_names[config['difficulty'] - 1]  # 1->easy, 2->medium, 3->hard
                settings = GameSettings(config['players'], difficulty_key)

                # Create game
                spawn_rules = SpawnRules(settings, BOARD_WIDTH)

                def make_start():
                    return GameStartState(settings, spawn_rules)

                game = GameMaster(make_start, settings, spawn_rules, transitions)
                net = NetworkManager(game)
                net.start_bg()

                # Start game thread
                game_thread = threading.Thread(target=game_thread_func, args=(game,), daemon=True)
                game_thread.start()

                print(f"Game 1 started! Players: {config['players']}, Difficulty: {config['difficulty']}")

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
            import time
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
    run_game_with_dual_screen()