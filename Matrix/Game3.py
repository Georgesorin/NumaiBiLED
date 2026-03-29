"""
Game 3 – Snake
===============
AI snake hunts fruits on the board.  Players stomp fruits to destroy them
and starve the snake, but touching the snake costs HP.
"""

from utils.data import (
    load_config, SnakeSettings
)
from utils.data.game_engine import run_game
from utils.master import GameMaster
from utils.states import SnakeStartState, SnakePlayState, SnakeEndState
from utils.ui.snake_ui import prompt_snake_settings

# ============================================================
#  Wiring
# ============================================================

_TRANSITIONS = {
    "start": lambda s, _r, **kw: SnakeStartState(**kw),
    "play":  lambda s, _r, **kw: SnakePlayState(settings=s, **kw),
    "end":   lambda s, _r, **kw: SnakeEndState(**kw),
}

if __name__ == "__main__":
    settings = prompt_snake_settings()
    game = GameMaster(lambda: SnakeStartState(), settings, None, _TRANSITIONS)
    run_game(game, config=load_config(), title="Game 3 - Snake!")
