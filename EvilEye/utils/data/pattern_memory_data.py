from .game_engine import NUM_WALLS, LEDS_PER_WALL
from ..ui.colors import (
    BLACK, WHITE, RED, YELLOW, GREEN, BLUE, CYAN, MAGENTA, ORANGE, PURPLE,
)

ALL_COLORS = [WHITE, RED, YELLOW, GREEN, BLUE, CYAN, MAGENTA, ORANGE, PURPLE, BLACK]

DIFFICULTY = {
    "easy":   4,
    "medium": 6,
    "hard":   10,
}

PLAYER_CONFIGS = {
    2: {"walls": 2, "per_wall": 1},
    3: {"walls": 3, "per_wall": 1},
    4: {"walls": 4, "per_wall": 1},
    6: {"walls": 3, "per_wall": 2},
    8: {"walls": 4, "per_wall": 2},
}

SHOW_COLOR_DURATION  = 1
SHOW_PAUSE_DURATION  = 0.1
LOOP_GAP_DURATION    = 5   # pause between pattern repeats on the eye
BLACKOUT_DEBUFF_DURATION    = 3.0
COUNTDOWN_DURATION   = 3   # seconds to wait before the game begins


class Player:
    def __init__(self, player_id, wall, buttons):
        self.id = player_id
        self.wall = wall
        self.buttons = list(buttons)
        self.color_map = {}
        self.progress = 0
        self.finished = False
        self.used_powerup = False

    def reset_progress(self):
        self.progress = 0
        self.finished = False
        self.used_powerup = False


def build_players(num_players):
    cfg = PLAYER_CONFIGS[num_players]
    walls_used = cfg["walls"]
    per_wall = cfg["per_wall"]
    players = []
    pid = 0
    for w in range(1, walls_used + 1):
        if per_wall == 1:
            players.append(Player(pid, w, list(range(1, 11))))
            pid += 1
        else:
            players.append(Player(pid, w, list(range(1, 6))))
            pid += 1
            players.append(Player(pid, w, list(range(6, 11))))
            pid += 1
    return players


def _centered_buttons(buttons, count):
    """Contiguous slice of `count` buttons from the middle of the row (shorter patterns stay centered)."""
    n = len(buttons)
    k = min(count, n)
    if k <= 0:
        return []
    start = (n - k) // 2
    return buttons[start : start + k]


def powerup_button_pair(buttons):
    """The two centre physical buttons: rainbow effect, then flash (same order as before)."""
    pair = _centered_buttons(buttons, 2)
    return pair[0], pair[1]


def assign_colors(players, pattern):
    for p in players:
        usable = min(len(pattern), len(p.buttons))
        mapping = {}
        for btn, color in zip(_centered_buttons(p.buttons, usable), pattern):
            mapping[btn] = color
        for btn in p.buttons:
            if btn not in mapping:
                mapping[btn] = BLACK
        p.color_map = mapping
