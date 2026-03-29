import random
from .colors import *

ALL_COLORS = [RED, BLUE, GREEN, YELLOW, CYAN, MAGENTA, ORANGE]

PATTERNS_EASY = [
    [[0,0,1,1,0,0],[0,1,1,1,1,0],[1,1,1,1,1,1],[0,1,1,1,1,0],[0,0,2,2,0,0],[0,0,2,2,0,0]],
    [[0,0,0,0,0,0],[0,1,0,0,1,0],[0,1,0,0,1,0],[0,0,0,0,0,0],[2,0,0,0,0,2],[0,2,2,2,2,0]],
    [[0,0,2,2,0,0],[0,2,1,1,2,0],[2,1,1,1,1,2],[2,1,1,1,1,2],[0,2,1,1,2,0],[0,0,2,2,0,0]]
]

PATTERNS_MEDIUM = [
    [[0,0,1,1,0,0],[0,1,1,1,1,0],[1,1,1,1,1,1],[0,2,2,2,2,0],[0,2,3,3,2,0],[0,2,3,3,2,0]],
    [[0,0,0,1,0,0],[0,0,1,1,0,0],[0,1,1,1,0,0],[1,1,1,1,2,0],[3,3,3,3,3,3],[0,3,3,3,3,0]],
    [[0,0,0,0,0,0],[0,1,0,0,1,0],[0,1,0,0,1,0],[0,0,2,2,0,0],[3,0,0,0,0,3],[0,3,3,3,3,0]]
]

PATTERNS_HARD = [
    # Add your own hard templates here
]

DIFFICULTY_PATTERNS = {
    1: PATTERNS_EASY,
    2: PATTERNS_MEDIUM,
    3: PATTERNS_HARD,
}

DIFFICULTY_MAX_COLORS = {
    1: 3,
    2: 3,
    3: 4,
}

PLAYER_POSITIONS = {
    2: [(4, 4), (4, 20)],
    3: [(1,  2), (1, 22), (7, 12)],
    4: [(0,  0), (8,  8), (0, 16), (8, 24)],
    5: [(0,  0), (8,  0), (4, 12), (0, 24), (8, 24)],
    6: [(0,  0), (8,  0), (0, 12), (8, 12), (0, 24), (8, 24)],
}

def extract_colors(drawing):
    """Return the list of unique non-BLACK colors used in a 6x6 drawing."""
    colors = set()
    for row in drawing:
        for c in row:
            if c != BLACK:
                colors.add(c)
    return list(colors)

def get_mosaic_drawing(mosaic_type, colors):
    drawing = [[BLACK for _ in range(6)] for _ in range(6)]
    if mosaic_type == 1: # Checkerboard
        for y in range(6):
            for x in range(6): drawing[y][x] = colors[((x % 2) + (y % 2) * 2) % len(colors)]
    elif mosaic_type == 2: # Thin Diagonal
        for y in range(6):
            for x in range(6): drawing[y][x] = colors[(x - y) % len(colors)]
    elif mosaic_type == 3: # 4 Quadrants
        for y in range(6):
            for x in range(6):
                if y < 3 and x < 3: drawing[y][x] = colors[0]
                elif y < 3 and x >= 3: drawing[y][x] = colors[1 % len(colors)]
                elif y >= 3 and x < 3: drawing[y][x] = colors[2 % len(colors)]
                else: drawing[y][x] = colors[3 % len(colors)]
    elif mosaic_type == 4: # 2x2 Interlocking
        for y in range(6):
            for x in range(6): drawing[y][x] = colors[((x // 2) + (y // 2)) % len(colors)]
    elif mosaic_type == 5: # Concentric Squares
        for y in range(6):
            for x in range(6): drawing[y][x] = colors[min(x, y, 5-x, 5-y) % len(colors)]
    elif mosaic_type == 6: # Thick Vertical
        for y in range(6):
            for x in range(6): drawing[y][x] = colors[(x // 3) % len(colors)]
    return drawing

def get_pattern_drawing(template, colors):
    unique_regions = list(set(val for row in template for val in row if val != 0))
    assigned_colors = random.sample(colors, min(len(unique_regions), len(colors)))
    color_map = {region: assigned_colors[i] for i, region in enumerate(unique_regions)}
    drawing = [[BLACK for _ in range(6)] for _ in range(6)]
    for y in range(6):
        for x in range(6):
            val = template[y][x]
            if val != 0: drawing[y][x] = color_map[val]
    return drawing
