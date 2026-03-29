import math
import colorsys
from .colors import BLACK, GREEN, RED, WHITE
from ..data.pattern_memory_data import (
    PLAYER_CONFIGS, SHOW_COLOR_DURATION, SHOW_PAUSE_DURATION, LOOP_GAP_DURATION
)

def light_player_buttons(engine, players, pattern, blackout_targets, powerup_player):
    """Set each player's buttons to their assigned colours."""
    for p in players:
        if p.finished and p != powerup_player:
            for btn in p.buttons:
                engine.set_button(p.wall, btn, *BLACK)
            continue
        if p in blackout_targets:
            continue
        for btn in p.buttons:
            engine.set_button(p.wall, btn, *p.color_map.get(btn, BLACK))

def animate_eyes(engine, t, num_players, pattern, players):
    """Continuously loop the full pattern on the eye for active walls."""
    step_dur = SHOW_COLOR_DURATION + SHOW_PAUSE_DURATION
    cycle_dur = step_dur * len(pattern) + LOOP_GAP_DURATION
    pos = t % cycle_dur

    pattern_end = step_dur * len(pattern)
    if pos >= pattern_end:
        color = BLACK
    else:
        step_idx = int(pos / step_dur)
        within = pos - step_idx * step_dur
        color = pattern[step_idx] if within < SHOW_COLOR_DURATION else BLACK

    walls_used = PLAYER_CONFIGS[num_players]["walls"]
    for w in range(1, walls_used + 1):
        has_active = any(
            p.wall == w and not p.finished for p in players
        )
        if has_active:
            engine.set_eye(w, *color)
        else:
            engine.set_eye(w, *GREEN)

def animate_powerup_buttons(engine, t, powerup_player):
    """Rainbow cycle on button[0], flashing white on button[1]."""
    if powerup_player is None or powerup_player.used_powerup:
        return
    btn_rainbow = powerup_player.buttons[0]
    btn_flash = powerup_player.buttons[1]

    hue = (t * 0.2) % 1.0
    r, g, b = colorsys.hsv_to_rgb(hue, 1.0, 1.0)
    engine.set_button(powerup_player.wall, btn_rainbow, int(r * 255), int(g * 255), int(b * 255))

    # Smooth black→white pulse for btn_flash
    brightness = 0.5 * (1 + math.sin(t * math.pi))
    intensity = int(brightness * 255)
    engine.set_button(powerup_player.wall, btn_flash, intensity, intensity, intensity)

    for btn in powerup_player.buttons:
        if btn != btn_rainbow and btn != btn_flash:
            engine.set_button(powerup_player.wall, btn, *BLACK)

def draw_idle_animation(engine, t):
    hue = (t * 0.05) % 1.0
    r, g, b = colorsys.hsv_to_rgb(hue, 1.0, 0.8)
    engine.set_all(int(r * 255), int(g * 255), int(b * 255))

def draw_countdown(engine, t, num_players, phases, duration):
    phase_dur = duration / len(phases)
    phase_idx = min(int(t / phase_dur), len(phases) - 1)
    color = phases[phase_idx]

    walls_used = PLAYER_CONFIGS[num_players]["walls"]
    for w in range(1, walls_used + 1):
        engine.set_eye(w, *color)

def draw_game_over(engine, players, loser, t):
    for p in players:
        if p.finished:
            engine.set_eye(p.wall, *GREEN)
        else:
            engine.set_eye(p.wall, *RED)

    if loser:
        flash = int(t * 3) % 2 == 0
        if flash:
            engine.set_eye(loser.wall, *RED)
        else:
            engine.set_eye(loser.wall, *BLACK)
