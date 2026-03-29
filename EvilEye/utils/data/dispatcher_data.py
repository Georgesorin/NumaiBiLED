import random
from .game_engine import NUM_WALLS, LEDS_PER_WALL
from ..ui.colors import BLACK, ALL_COLORS
from .pattern_memory_data import Player

DISPATCHER_WALL_ID = 1

class DispatcherGameData:
    def __init__(self, settings, players):
        self.settings = settings
        self.players = players
        self.dispatcher_player = next((p for p in players if p.wall == DISPATCHER_WALL_ID), None)
        self.active_wall_id = None
        self.wall_timer = 0.0
        self.game_timer = 60.0 # Default 60 seconds
        self.score = 0
        self.current_sequence = []
        
        # Calibration from settings (Phase 7)
        self.sequence_length = settings.pattern_length
        self.wall_timeout = getattr(settings, "wall_timeout", 5.0)
        self.bonus_time = getattr(settings, "bonus_time", 5.0)
        
        # Crash Mechanic
        self.is_crashed = False
        self.crash_progress = 0
        self.crash_target_button = None
        self.next_crash_t = 20.0 # First crash around 20s

    def trigger_crash(self):
        self.is_crashed = True
        self.crash_progress = 0
        self.pick_random_minigame_button()

    def pick_random_minigame_button(self):
        if self.dispatcher_player:
            self.crash_target_button = random.choice(self.dispatcher_player.buttons)
        else:
            self.crash_target_button = 1

    def generate_sequence(self):
        palette = [c for c in ALL_COLORS if c != BLACK]
        self.current_sequence = [random.choice(palette) for _ in range(self.sequence_length)]
        
        # Reset progress for all players
        for p in self.players:
            p.reset_progress()

        # Assign colors to dispatcher buttons in sequence order (so they can be read easily)
        if self.dispatcher_player:
            mapping = {btn: BLACK for btn in self.dispatcher_player.buttons}
            for i, color in enumerate(self.current_sequence):
                if i < len(self.dispatcher_player.buttons):
                    mapping[self.dispatcher_player.buttons[i]] = color
            self.dispatcher_player.color_map = mapping
        
        # Assign colors to the currently active wall
        if self.active_wall_id:
            self.assign_colors_to_wall(self.active_wall_id)

    def pick_active_wall(self):
        # Only pick from walls that are actually in use by players (excluding dispatcher)
        used_walls = set(p.wall for p in self.players if p.wall != DISPATCHER_WALL_ID)
        possible_walls = sorted(list(used_walls))
        
        if not possible_walls:
            # Fallback (should not happen if there are at least 2 players)
            possible_walls = [2]

        # Try to pick a DIFFERENT wall if possible to avoid user confusion
        other_walls = [w for w in possible_walls if w != self.active_wall_id]
        if other_walls:
            self.active_wall_id = random.choice(other_walls)
        else:
            self.active_wall_id = random.choice(possible_walls)
            
        self.wall_timer = self.wall_timeout
        self.assign_colors_to_wall(self.active_wall_id)

    def assign_colors_to_wall(self, wall_id):
        # Ensure the wall has all colors needed for the sequence
        needed_colors = list(set(self.current_sequence))
        wall_players = [p for p in self.players if p.wall == wall_id]
        
        all_buttons = []
        for p in wall_players:
            all_buttons.extend(p.buttons)
        
        random.shuffle(all_buttons)
        
        # Map needed colors to random buttons
        mapping = {btn: BLACK for btn in all_buttons}
        for i, color in enumerate(needed_colors):
            if i < len(all_buttons):
                mapping[all_buttons[i]] = color
        
        # Fill remaining buttons with random colors from palette (not in sequence maybe?)
        palette = [c for c in ALL_COLORS if c != BLACK and c not in needed_colors]
        for btn in all_buttons:
            if mapping[btn] == BLACK and palette:
                mapping[btn] = random.choice(palette)
        
        for p in wall_players:
            p.color_map = {btn: mapping[btn] for btn in p.buttons}
