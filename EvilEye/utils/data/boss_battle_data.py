import random
from enum import IntEnum
from .game_engine import NUM_WALLS, LEDS_PER_WALL
from ..ui.colors import BLACK, RED, GREEN, BLUE, YELLOW, ALL_COLORS

# Default stage colors
STAGE2_COLORS = [RED, GREEN, BLUE, YELLOW]

class BossBattleStage(IntEnum):
    STAGE1 = 1
    STAGE2 = 2
    STAGE3 = 3

class BossBattlePlayer:
    def __init__(self, player_id, wall, buttons):
        self.id = player_id
        self.wall = wall
        self.buttons = list(buttons)
        
        # Stage 1: Match eye color
        self.s1_matched = [False] * len(self.buttons)
        
        # Stage 2: Pattern presses
        self.s2_presses = {c: 0 for c in STAGE2_COLORS}
        
        # Stage 3: General
        self.hits = 0
        self.is_hidden = True

    def reset(self):
        self.s1_matched = [False] * len(self.buttons)
        self.s2_presses = {c: 0 for c in STAGE2_COLORS}
        self.hits = 0
        self.is_hidden = True

def build_boss_players(settings):
    players = []
    pid = 0
    for w in range(1, settings.walls_used + 1):
        if settings.per_wall == 1:
            players.append(BossBattlePlayer(pid, w, list(range(1, 11))))
            pid += 1
        else:
            players.append(BossBattlePlayer(pid, w, list(range(1, 6))))
            pid += 1
            players.append(BossBattlePlayer(pid, w, list(range(6, 11))))
            pid += 1
    return players
