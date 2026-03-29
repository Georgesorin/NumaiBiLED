# Snake settings and constants

SNAKE_DIFFICULTIES = {
    "easy":      dict(base_interval=0.2,  min_interval=0.16, fruit_weights=(8, 2, 1), wrap=False),
    "medium":    dict(base_interval=0.16, min_interval=0.11, fruit_weights=(5, 3, 2), wrap=False),
    "hard":      dict(base_interval=0.2, min_interval=0.08, fruit_weights=(3, 4, 3), wrap=True),
    "nightmare": dict(base_interval=0.16, min_interval=0.02, fruit_weights=(2, 4, 4), wrap=True),
}

PLAYER_LENGTH = {
    2: 6,
    3: 8,
    4: 10,
    5: 12,
    6: 14,
}

BASE_MIN_FRUITS = 2
BASE_SPAWN_INTERVAL = 5.0

class SnakeSettings:
    def __init__(self, player_count, difficulty):
        self.player_count = max(2, min(6, player_count))
        diff = SNAKE_DIFFICULTIES[difficulty]
        self.difficulty_name = difficulty
        self.base_interval = diff["base_interval"]
        self.min_interval = diff["min_interval"]
        self.initial_length = PLAYER_LENGTH[self.player_count]
        self.fruit_weights = diff["fruit_weights"]
        self.wrap = diff["wrap"]
        self.min_fruits = BASE_MIN_FRUITS + (self.player_count - 2) // 2
        self.spawn_interval = BASE_SPAWN_INTERVAL - 0.5 * (self.player_count - 2)
        
        # Runtime sync data
        self.hp = 100
        self.max_hp = 100
        self.status_text = "LOBBY"
        self.time_left = 0 
        self.hide_timer = True
        self.hide_status = True
