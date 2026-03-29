import math
import colorsys
from .colors import BLACK, GREEN, RED, WHITE, BLUE, YELLOW
from ..data.game_engine import NUM_WALLS

def render_dispatcher_wall(engine, dispatcher_player, is_broken, t, target_btn=None):
    """
    Lights up the dispatcher wall. 
    Shows the assigned color map or a broken glitch effect.
    """
    if not dispatcher_player:
        return

    if is_broken:
        # Glitch effect: static and red eyes
        for btn in dispatcher_player.buttons:
            if btn == target_btn:
                # Target button for reboot pulses WHITE
                val = int(127 + 127 * math.sin(t * 10))
                engine.set_button(dispatcher_player.wall, btn, val, val, val)
            else:
                # Static: dim red flickering
                if (int(t * 15) + btn) % 3 == 0:
                    engine.set_button(dispatcher_player.wall, btn, 50, 0, 0)
                else:
                    engine.set_button(dispatcher_player.wall, btn, 0, 0, 0)
        
        # Eye flashes RED
        eye_val = int(127 + 127 * math.sin(t * 20))
        engine.set_eye(dispatcher_player.wall, eye_val, 0, 0)
    else:
        # Show regular color map
        for btn in dispatcher_player.buttons:
            engine.set_button(dispatcher_player.wall, btn, *dispatcher_player.color_map.get(btn, BLACK))
        
        # Eye pulse YELLOW to indicate "control"
        intensity = int(150 + 50 * math.sin(t * 2))
        engine.set_eye(dispatcher_player.wall, intensity, intensity, 0)

def render_active_wall(engine, wall_id, players, t, timer, sequence_length):
    """
    Highlights the currently active wall.
    """
    # Pulse Eye specifically for active wall
    intensity = int(100 + 155 * (math.sin(t * 5) * 0.5 + 0.5))
    engine.set_eye(wall_id, 0, 0, intensity) # Pulse BLUE

    # Light up player buttons for this wall
    for p in players:
        if p.wall == wall_id:
            for btn in p.buttons:
                # Only show colors that are part of the player's map
                engine.set_button(p.wall, btn, *p.color_map.get(btn, BLACK))

def render_idle_wall(engine, wall_id, t):
    """
    Slowly pulse or dim idle walls.
    """
    # Slow dim white pulse for the eye
    intensity = int(20 + 20 * math.sin(t * 0.5))
    engine.set_eye(wall_id, intensity, intensity, intensity)
    
    # Buttons are off
    for btn in range(1, 11):
        engine.set_button(wall_id, btn, *BLACK)

def draw_dispatcher_game_over(engine, players, t, winner=True):
    """
    Show all green if success, red if failure.
    """
    color = GREEN if winner else RED
    flash = int(t * 2) % 2 == 0
    
    for w in range(1, NUM_WALLS + 1):
        if flash:
            engine.set_wall(w, *color)
        else:
            engine.set_wall(w, *BLACK)
