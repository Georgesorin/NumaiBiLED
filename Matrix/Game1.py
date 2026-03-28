import time
import os
import sys
import threading

# from utils.game_engine import GameEngine

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from utils.game_engine import (
    NetworkManager,
    load_config, game_thread_func,
    BOARD_WIDTH
)

from utils.tile import Tile
from utils.ui.colors import *
from utils.scaling import GameSettings, DIFFICULTIES
from utils.scaling import SpawnRules

from utils.states import *
from utils.master import GameMaster

_CFG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tetris_config.json")

transitions = {
    "start": lambda settings, spawn_rules, **kwargs: GameStartState(settings, spawn_rules, **kwargs),
    "initial_spawn": lambda settings, spawn_rules, **kwargs: InitialTilePatternState(settings, spawn_rules, **kwargs),
    "spawn": lambda settings, spawn_rules, **kwargs: TileSpawnState(settings, spawn_rules, **kwargs),
    "play": lambda settings, spawn_rules, **kwargs: PlayState(settings, spawn_rules, **kwargs),
    "end": lambda settings, spawn_rules, **kwargs: GameOverState(settings, spawn_rules, **kwargs),
}

def _prompt_settings():
    print("\n=== KEEP ALIVE - Setup ===\n")

    while True:
        try:
            n = int(input("Number of players (2-6): ").strip())
            if 2 <= n <= 6:
                break
            print("  Please enter a number between 2 and 6.")
        except ValueError:
            print("  Invalid input.")

    diff_names = list(DIFFICULTIES.keys())
    print("\nDifficulty:")
    for i, name in enumerate(diff_names, 1):
        print(f"  {i}. {name}")

    while True:
        try:
            choice = input(f"Choose difficulty (1-{len(diff_names)}): ").strip()
            idx = int(choice) - 1
            if 0 <= idx < len(diff_names):
                break
            print(f"  Please enter a number between 1 and {len(diff_names)}.")
        except ValueError:
            print("  Invalid input.")

    diff_name = diff_names[idx]
    settings = GameSettings(n, diff_name)

    print(f"\n  Players: {settings.player_count}")
    print(f"  Difficulty: {settings.difficulty}")
    print(f"  Initial platforms: {settings.tile_spawn_initial}")
    print(f"  Platforms per round: {settings.tile_spawn_per_round}")
    print()
    return settings


if __name__ == "__main__":
    config = load_config(_CFG_FILE)
    settings = _prompt_settings()
    spawn_rules = SpawnRules(settings, BOARD_WIDTH)

    def make_start():
        return GameStartState(settings, spawn_rules)

    game = GameMaster(make_start, settings, spawn_rules, transitions)
    net = NetworkManager(game, config=config)
    net.start_bg()

    gt = threading.Thread(target=game_thread_func, args=(game,), daemon=True)
    gt.start()

    print("Game 1 - Keep Alive!")
    print("Commands: 'restart', 'setup', 'quit'")

    try:
        while game.running:
            cmd = input("> ").strip().lower()
            if cmd in ('quit', 'exit'):
                game.running = False
                break
            elif cmd == 'restart':
                spawn_rules.reset()
                game.restart()
                print("Restarted.")
            elif cmd == 'setup':
                settings = _prompt_settings()
                spawn_rules = SpawnRules(settings, BOARD_WIDTH)
                def make_start_new(s=settings, sr=spawn_rules):
                    return GameStartState(s, sr)
                game._initial_state_factory = make_start_new
                game.restart()
                print("Settings applied, game restarted.")
            else:
                print("Unknown command. Try: restart, setup, quit")
    except KeyboardInterrupt:
        game.running = False

    net.running = False
    print("Exiting...")
