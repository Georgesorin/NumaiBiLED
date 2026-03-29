from ..ui.colors import ALL_COLORS
from ..data.pattern_memory_data import PLAYER_CONFIGS, DIFFICULTY

class PatternMemorySettings:
    def __init__(self, player_count, difficulty):
        self.player_count = player_count
        self.difficulty_name = difficulty
        self.pattern_length = DIFFICULTY.get(difficulty, 4)
        
        cfg = PLAYER_CONFIGS.get(player_count, {"walls": 4, "per_wall": 2})
        self.walls_used = cfg["walls"]
        self.per_wall = cfg["per_wall"]

    @property
    def palette(self):
        # We could add logic here if difficulty affects the color pool
        return ALL_COLORS[:self.pattern_length]
