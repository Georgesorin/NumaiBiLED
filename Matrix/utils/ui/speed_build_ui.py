from ..ui.colors import *
import random

ALL_COLORS = [RED, BLUE, GREEN, YELLOW, CYAN, MAGENTA, ORANGE]

PATTERNS_EASY = [
    # Original patterns
    [[0,0,1,1,0,0], [0,1,1,1,1,0], [1,1,1,1,1,1], [0,1,1,1,1,0], [0,0,2,2,0,0], [0,0,2,2,0,0]],
    [[0,0,0,0,0,0], [0,1,0,0,1,0], [0,1,0,0,1,0], [0,0,0,0,0,0], [2,0,0,0,0,2], [0,2,2,2,2,0]],
    [[0,0,2,2,0,0], [0,2,1,1,2,0], [2,1,1,1,1,2], [2,1,1,1,1,2], [0,2,1,1,2,0], [0,0,2,2,0,0]],
    [[0,1,0,0,2,0], [1,1,1,2,2,2], [1,1,1,2,2,2], [1,1,1,2,2,2], [0,1,1,2,2,0], [0,0,1,2,0,0]],

    # Mosaic 3: 4 Quadrants
    [[1,1,1,2,2,2], [1,1,1,2,2,2], [1,1,1,2,2,2], [3,3,3,4,4,4], [3,3,3,4,4,4], [3,3,3,4,4,4]],
    # Mosaic 6: Thick Vertical
    [[1,1,1,2,2,2], [1,1,1,2,2,2], [1,1,1,2,2,2], [1,1,1,2,2,2], [1,1,1,2,2,2], [1,1,1,2,2,2]],
]

PATTERNS_MEDIUM = [
    # Original patterns
    [[0,0,1,1,0,0], [0,1,1,1,1,0], [1,1,1,1,1,1], [0,2,2,2,2,0], [0,2,3,3,2,0], [0,2,3,3,2,0]],
    [[0,0,0,1,0,0], [0,0,1,1,0,0], [0,1,1,1,0,0], [1,1,1,1,2,0], [3,3,3,3,3,3], [0,3,3,3,3,0]],
    [[0,0,0,0,0,0], [0,1,0,0,1,0], [0,1,0,0,1,0], [0,0,2,2,0,0], [3,0,0,0,0,3], [0,3,3,3,3,0]],
    [[0,0,0,0,0,0], [0,1,0,0,1,0], [0,2,2,2,2,0], [0,2,2,2,2,0], [0,0,3,3,0,0], [0,0,3,3,0,0]],

    # Mosaic 1: Checkerboard
    [[1,2,1,2,1,2], [2,1,2,1,2,1], [1,2,1,2,1,2], [2,1,2,1,2,1], [1,2,1,2,1,2], [2,1,2,1,2,1]],
    # Mosaic 4: 2x2 Interlocking
    [[1,1,2,2,3,3], [1,1,2,2,3,3], [2,2,3,3,1,1], [2,2,3,3,1,1], [3,3,1,1,2,2], [3,3,1,1,2,2]],
]

PATTERNS_HARD = [
    # Mosaics
    [[1,2,3,4,1,2], [4,1,2,3,4,1], [3,4,1,2,3,4], [2,3,4,1,2,3], [1,2,3,4,1,2], [4,1,2,3,4,1]], # Mosaic 2: Thin Diagonal
    [[1,1,1,1,1,1], [1,2,2,2,2,1], [1,2,3,3,2,1], [1,2,3,3,2,1], [1,2,2,2,2,1], [1,1,1,1,1,1]], # Mosaic 5: Concentric Squares
    
    # User suggested + Hard templates
    [[1,1,0,0,2,2], [0,1,1,2,2,0], [0,0,1,2,0,0], [3,3,0,0,4,4], [0,3,3,4,4,0], [0,0,3,4,0,0]],
    [[1,1,1,1,1,1], [1,0,2,2,0,0], [1,0,2,2,0,3], [1,0,0,0,0,3], [1,4,4,4,4,3], [1,1,1,1,1,3]],
]

DIFFICULTY_PATTERNS = { 1: PATTERNS_EASY, 2: PATTERNS_MEDIUM, 3: PATTERNS_HARD }
DIFFICULTY_MAX_COLORS = { 1: 3, 2: 3, 3: 4 }

PLAYER_POSITIONS = {
    2: [(4, 4), (4, 20)],
    3: [(1, 2), (1, 22), (7, 12)],
    4: [(0, 0), (8, 8), (0, 16), (8, 24)],
    5: [(0, 0), (8, 0), (4, 12), (0, 24), (8, 24)],
    6: [(0, 0), (8, 0), (0, 12), (8, 12), (0, 24), (8, 24)],
}

def extract_colors(drawing):
    colors = set()
    for row in drawing:
        for c in row:
            if c != BLACK: colors.add(c)
    return list(colors)

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
