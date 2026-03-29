class SpeedBuildSettings:
    def __init__(self, player_count, difficulty):
        self.player_count = player_count
        self.difficulty = difficulty
        
        # Runtime sync data for dual-screen timer
        self.time_left = 0.0
        self.total_time = 0.0
        self.status_text = "LOBBY"
        self.hide_timer = True
        self.hide_status = True
