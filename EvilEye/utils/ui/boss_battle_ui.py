from ..ui.colors import BLACK, RED, GREEN, BLUE, YELLOW, WHITE, PURPLE
import math

def draw_boss_hp_eye(engine, hp_percent, walls_used):
    # Use the EYE to show Boss HP (Green -> Yellow -> Red)
    if hp_percent > 50:
        color = GREEN
    elif hp_percent > 20:
        color = YELLOW
    else:
        color = RED
    
    # Optional: Make the eye pulse faster as HP gets lower
    for w in range(1, walls_used + 1):
        engine.set_eye(w, *color)

def draw_stage1(engine, players, eye_colors):
    # eye_colors is a dict {wall: color}
    for p in players:
        target_color = eye_colors.get(p.wall, BLACK)
        engine.set_eye(p.wall, *target_color)
        
        for i, matched in enumerate(p.s1_matched):
            btn_id = p.buttons[i]
            if matched:
                engine.set_button(p.wall, btn_id, *target_color)
            else:
                # Maybe a dim version of the target color?
                engine.set_button(p.wall, btn_id, *BLACK)

def draw_stage2(engine, players, pattern):
    # pattern is {color: count}
    # We need to distribute these colors on the buttons
    # Let's assign each button a color from the pattern
    # For now, let's just rotate the 4 colors on the buttons
    colors = list(pattern.keys())
    if not colors:
        return
        
    for p in players:
        for i, btn_id in enumerate(p.buttons):
            color = colors[i % len(colors)]
            engine.set_button(p.wall, btn_id, *color)
        
        # Display the eye as white to indicate Stage 2?
        engine.set_eye(p.wall, *WHITE)

def draw_stage3(engine, t, players, eye_states, weakspots, boss_hp):
    # eye_states is {wall: "looking" | "idle"}
    # weakspots is {wall: [btn_ids]}
    
    # HP-based eye color (if not looking)
    if boss_hp > 50:
        hp_color = GREEN
    elif boss_hp > 20:
        hp_color = YELLOW
    else:
        hp_color = RED

    for p in players:
        state = eye_states.get(p.wall, "idle")
        if state == "looking":
            # Very aggressive flashing RED for "Looking"
            if int(t * 8) % 2 == 0:
                engine.set_eye(p.wall, *RED)
            else:
                engine.set_eye(p.wall, 50, 0, 0) # Dim red
        else:
            # Show boss health on the eye
            engine.set_eye(p.wall, *hp_color)
            
        wall_weakspots = weakspots.get(p.wall, [])
        for i, btn_id in enumerate(p.buttons):
            if btn_id in wall_weakspots:
                # Rapidly FLASHING MAGENTA/WHITE for weakspots to make them POP
                if int(t * 10) % 2 == 0:
                    engine.set_button(p.wall, btn_id, *PURPLE)
                else:
                    engine.set_button(p.wall, btn_id, *WHITE)
            else:
                engine.set_button(p.wall, btn_id, *BLACK)

def draw_idle_animation(engine, t):
    # Fancy idle animation
    for w in range(1, 5):
        hue = (t + w * 0.2) % 1.0
        # Simple color cycle for eye
        color = (int(math.sin(t + w) * 127 + 128), 
                 int(math.cos(t + w) * 127 + 128), 
                 int(math.sin(t * 0.5 + w) * 127 + 128))
        engine.set_eye(w, *color)
        
        for b in range(1, 11):
            if (int(t * 5) + b + w) % 5 == 0:
                engine.set_button(w, b, *color)
            else:
                engine.set_button(w, b, *BLACK)
