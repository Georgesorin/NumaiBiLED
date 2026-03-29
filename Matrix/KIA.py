import os
import threading

from utils.data import (
    NetworkManager,
    game_thread_func,
    BOARD_WIDTH
)

from utils.scaling import SpawnRules

from utils.states import GameStartState, InitialTilePatternState, TileSpawnState, PlayState, GameOverState

from utils.master import GameMaster
from utils.ui import prompt_settings, prompt_render

transitions = {
    "start": lambda settings, spawn_rules, **kwargs: GameStartState(settings, spawn_rules, **kwargs),
    "initial_spawn": lambda settings, spawn_rules, **kwargs: InitialTilePatternState(settings, spawn_rules, **kwargs),
    "spawn": lambda settings, spawn_rules, **kwargs: TileSpawnState(settings, spawn_rules, **kwargs),
    "play": lambda settings, spawn_rules, **kwargs: PlayState(settings, spawn_rules, **kwargs),
    "end": lambda settings, spawn_rules, **kwargs: GameOverState(settings, spawn_rules, **kwargs),
}

if __name__ == "__main__":
    settings = prompt_settings()
    spawn_rules = SpawnRules(settings, BOARD_WIDTH)

    def make_start():
        return GameStartState(settings, spawn_rules)

    game = GameMaster(make_start, settings, spawn_rules, transitions)
    net = NetworkManager(game)
    net.start_bg()

    gt = threading.Thread(target=game_thread_func, args=(game,), daemon=True)
    gt.start()

    print("Game 1 - Keep Alive!")
    print("Commands: 'restart', 'setup', 'quit'")

    try:
        while game.running:
            prompt_render(game, BOARD_WIDTH)
    except KeyboardInterrupt:
        game.running = False

    net.running = False
    print("Exiting...")
