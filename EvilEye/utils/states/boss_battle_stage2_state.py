import os
import math
import random
from ._abs_state import GameEngine, GameState
from ..ui.colors import RED, BLUE, GREEN, YELLOW, WHITE, PURPLE, CYAN, ORANGE
from ..data.audio_manager import get_audio_manager

class BossBattleStage2State(GameState):
    """Stage 2: Orbital Strike (Hot Potato).
    Pass the energy between walls in sequence. Success after 3 full laps.
    """
    CHARGE_COLOR = YELLOW
    FAIL_COLOR = RED

    def __init__(self, settings, players):
        self.settings = settings
        self.players = players
        self._t = 0.0
        
        # Sort players by wall number to ensure a consistent circular sequence
        self.sorted_players = sorted(players, key=lambda p: p.wall)
        self.num_players = len(self.sorted_players)
        
        self._active_idx = 0
        self._success_count = 0
        self._target_success = self.num_players * 3 # 3 laps
        
        self._base_time = 3.0 # Starts generous (3s)
        self._timer = self._base_time
        self._state = "active" # "active", "fail_pause"
        self._pause_t = 0.0

    def enter(self, engine: GameEngine):
        engine.clear()
        path = os.path.join(os.path.dirname(__file__), "..", "..", "assets", "music", "boss_battle_middle.wav")
        get_audio_manager().play_music(path)

    def update(self, engine: GameEngine, dt: float):
        self._t += dt
        
        if self._state == "fail_pause":
            self._pause_t -= dt
            if self._pause_t <= 0:
                self._state = "active"
                # Reset to start of current lap
                self._success_count = (self._success_count // self.num_players) * self.num_players
                self._active_idx = 0
                self._timer = self._base_time
            
            # Show red on all eyes during fail
            for p in self.players:
                engine.set_eye(p.wall, *self.FAIL_COLOR)
            return

        # Decrease timer
        self._timer -= dt
        if self._timer <= 0:
            # FAIL - reset current lap
            self._state = "fail_pause"
            self._pause_t = 1.5
            return

        active_p = self.sorted_players[self._active_idx]

        # Draw
        engine.clear_buttons()
        for p in self.players:
            if p.wall == active_p.wall:
                # Active wall: Eye flashes, buttons pulse
                flash = int(self._t * 10) % 2 == 0
                engine.set_eye(p.wall, *(self.CHARGE_COLOR if flash else WHITE))
                
                btn_pulse = (math.sin(self._t * 10.0) + 1.2) / 2.2
                pulse_color = (int(self.CHARGE_COLOR[0] * btn_pulse),
                               int(self.CHARGE_COLOR[1] * btn_pulse),
                               int(self.CHARGE_COLOR[2] * btn_pulse))
                for b in range(1, 11):
                    engine.set_button(p.wall, b, *pulse_color)
            else:
                # Idle walls
                engine.set_eye(p.wall, 40, 40, 40) # Dim white

        # Input
        pressed = engine.get_pressed()
        for (wall, led) in pressed:
            if wall == active_p.wall:
                # SUCCESS PASS!
                self._success_count += 1
                self._active_idx = (self._active_idx + 1) % self.num_players
                
                # Speed up: reduce time for next pass (min 0.8s)
                progress = self._success_count / self._target_success
                self._timer = max(0.8, self._base_time * (1.0 - progress * 0.6))
                
                # Visual pop on pass
                engine.set_eye(wall, *WHITE)
                break

        # Check Transition
        if self._success_count >= self._target_success:
            return ("stage3", {"players": self.players, "hp": 100})

    def exit(self, engine: GameEngine):
        engine.clear()
