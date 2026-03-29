from ..ui.colors import ALL_COLORS, RED, GREEN, BLUE, YELLOW
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
        return ALL_COLORS[:self.pattern_length]

class BossBattleSettings:
    def __init__(self, player_count, difficulty):
        self.player_count = player_count
        self.difficulty_name = difficulty # "easy", "medium", "hard"
        
        # Stage 1: Synchronized Pulse
        if difficulty == "easy":
            self.sync_window = 1.0
            self.sync_count = 2
            self.cycle_speed = 3.0
            self.weakspot_damage = 20
            self.color_count = 2
        elif difficulty == "medium":
            self.sync_window = 0.5
            self.sync_count = 3
            self.cycle_speed = 2.0
            self.weakspot_damage = 15
            self.color_count = 3
        else: # hard
            self.sync_window = 0.25
            self.sync_count = 5
            self.cycle_speed = 1.0
            self.weakspot_damage = 10
            self.color_count = 4

        self.boss_max_hp = 100
        
        cfg = PLAYER_CONFIGS.get(player_count, {"walls": 4, "per_wall": 2})
        self.walls_used = cfg["walls"]
        self.per_wall = cfg["per_wall"]

    def get_stage2_pattern(self):
        import random
        # Returns a dict of {color: count}
        # Counts could be between 2 and 5
        pattern = {}
        colors = [RED, GREEN, BLUE, YELLOW][:self.color_count]
        for c in colors:
            pattern[c] = random.randint(2, 5)
        return pattern

class DispatcherSettings:
    def __init__(self, player_count, difficulty):
        self.player_count = player_count
        self.difficulty_name = difficulty
        
        # Balancing based on user feedback (Phase 7 & 10)
        if difficulty == "easy":
            self.wall_timeout = 20.0 # Increased from 12.0
            self.bonus_time = 10.0
            self.pattern_length = 3
        elif difficulty == "medium":
            self.wall_timeout = 15.0 # Increased from 9.0
            self.bonus_time = 8.0
            self.pattern_length = 5
        else: # hard
            self.wall_timeout = 10.0 # Increased from 6.0
            self.bonus_time = 5.0
            self.pattern_length = 8
            
        cfg = PLAYER_CONFIGS.get(player_count, {"walls": 4, "per_wall": 2})
        self.walls_used = cfg["walls"]
        self.per_wall = cfg["per_wall"]
