import math

# heat_search_area: fraction of hottest spawn slots discarded (higher = farther apart).
# heat_spread: heat added per placement (lower = sharper peaks near tiles, far reads clearer).
DIFFICULTIES = {
    "easy":       dict(heat_search_area=0.15, heat_spread=2.2, tile_timeout_curr=6.2, tile_timeout_minimum=3.8,
                       tile_timeout_decay=0.2, round_timer_curr=10.0, round_timer_minimum=7.0, round_timer_decay=0.5),
    "medium":     dict(heat_search_area=0.42, heat_spread=1.0, tile_timeout_curr=5.7,  tile_timeout_minimum=3.0,
                       tile_timeout_decay=0.35, round_timer_curr=9.0, round_timer_minimum=6.0, round_timer_decay=0.5),
    "hard":       dict(heat_search_area=0.72, heat_spread=0.45, tile_timeout_curr=5.0,  tile_timeout_minimum=2.7,
                       tile_timeout_decay=0.4, round_timer_curr=8.0, round_timer_minimum=5.0, round_timer_decay=0.5),
    "nightmare":  dict(heat_search_area=0.94, heat_spread=0.15, tile_timeout_curr=4.8,  tile_timeout_minimum=2.3,
                       tile_timeout_decay=0.2, round_timer_curr=7.0,  round_timer_minimum=4.7, round_timer_decay=0.3),
}

class GameSettings:
    def __init__(self, player_count, difficulty):
        self.player_count = player_count
        self.difficulty = DIFFICULTIES[difficulty]

        self.heat_search_area = self.difficulty["heat_search_area"]
        self.heat_spread = self.difficulty["heat_spread"]

        self.tile_timeout_curr = self.difficulty["tile_timeout_curr"]
        self.tile_timeout_minimum = self.difficulty["tile_timeout_minimum"]
        self.tile_timeout_decay = self.difficulty["tile_timeout_decay"]

        self.round_timer_curr = self.difficulty["round_timer_curr"]
        self.round_timer_minimum = self.difficulty["round_timer_minimum"]
        self.round_timer_decay = self.difficulty["round_timer_decay"]

    @property
    def tile_spawn_initial(self):
        return math.ceil(self.player_count / 2) + 1

    @property
    def tile_spawn_per_round(self):
        return math.floor(self.player_count / 2)

    def get_tile_timeout(self, round_num):
        return max(self.tile_timeout_minimum,
                   self.tile_timeout_curr - (round_num - 1) * self.tile_timeout_decay)

    def get_round_timer(self, round_num):
        return max(self.round_timer_minimum,
                   self.round_timer_curr - (round_num - 1) * self.round_timer_decay)