import random

from .game_settings import GameSettings
from ..tile.tile import Tile

class SpawnRules:
    """
    Heat map over the grid of valid 2x2 spawn positions.

    `cutoff_fraction` is the fraction of candidates discarded for being
    too "hot" (closest to existing platforms).  Higher values keep a
    smaller, colder pool so spawns stay farther apart on hard modes.

    Within that pool we pick among the lowest-heat cells only (the
    coldest), so spawns hug the "far away" side of the cutoff instead
    of sampling randomly toward hotter (closer) tiles.

    `heat_spread` scales how much heat a placement radiates.
    Lower values make the heat map more local, so consecutive spawns
    can land further apart.
    """

    PLAY_H = 26
    PW = 2
    PH = 2
    # Margin in pixels to avoid spawning on the outer border (2 tiles)
    MARGIN_X = 2
    MARGIN_Y = 2

    def __init__(self, settings: GameSettings, size):
        self.board_w = size
        self.play_h = self.PLAY_H
        self.cutoff_fraction = settings.heat_search_area
        self.heat_spread = settings.heat_spread
        # Compute grid dimensions inside the margins so spawned 2x2 tiles
        # never overlap the 2-tile border on any side.
        usable_w = max(0, self.board_w - 2 * self.MARGIN_X)
        usable_h = max(0, self.play_h - 2 * self.MARGIN_Y)
        self._grid_w = usable_w // self.PW
        self._grid_h = usable_h // self.PH
        self.heat = [[1.0] * self._grid_w for _ in range(self._grid_h)]

    def reset(self):
        for gy in range(self._grid_h):
            for gx in range(self._grid_w):
                self.heat[gy][gx] = 1.0

    def _pos_to_grid(self, x, y):
        return x // self.PW, y // self.PH

    def _grid_to_pos(self, gx, gy):
        return gx * self.PW + self.MARGIN_X, gy * self.PH + self.MARGIN_Y

    def _distance(self, gx1, gy1, gx2, gy2):
        return ((gx1 - gx2) ** 2 + (gy1 - gy2) ** 2) ** 0.5

    def update(self, placed_x, placed_y):
        pgx, pgy = self._pos_to_grid(placed_x, placed_y)
        max_dist = self._distance(0, 0, self._grid_w - 1, self._grid_h - 1)

        for gy in range(self._grid_h):
            for gx in range(self._grid_w):
                dist = self._distance(gx, gy, pgx, pgy)
                proximity = 1.0 - (dist / max_dist)
                self.heat[gy][gx] += proximity * self.heat_spread

    def pick(self, engine):
        occupied = set()
        for ent in engine.entities:
            if isinstance(ent, Tile):
                for pos in ent.get_position():
                    occupied.add(pos)

        scored = []
        for gy in range(self._grid_h):
            for gx in range(self._grid_w):
                x, y = self._grid_to_pos(gx, gy)
                cells = [(x + dx, y + dy) for dx in range(self.PW) for dy in range(self.PH)]
                if any(c in occupied for c in cells):
                    continue
                scored.append((x, y, self.heat[gy][gx]))

        if not scored:
            return None

        # Lower heat = farther from prior placements (see update()).
        scored.sort(key=lambda t: t[2])

        discard = int(len(scored) * self.cutoff_fraction)
        discard = min(max(0, discard), len(scored) - 1)
        keep = len(scored) - discard
        viable = scored[:keep]

        min_h = viable[0][2]
        best = [s for s in viable if s[2] == min_h]
        choice = random.choice(best)

        return choice[0], choice[1]


# ============================================================
#  Helper: spawn N platforms at once
# ============================================================

def spawn_platforms(engine, spawn_rules, settings, count, round_num, colors):
    """Spawn `count` new platforms. Returns list of newly created Tile objects."""
    spawned = []
    for i in range(count):
        pos = spawn_rules.pick(engine)
        if pos is None:
            break
        x, y = pos
        spawn_rules.update(x, y)

        keep_alive = settings.get_tile_timeout(round_num)
        color_idx = (len(engine.entities) - 1) % len(colors)
        color = colors[color_idx]
        plat = Tile((x, y), (2, 2), color, keep_alive)
        engine.spawn_entity(plat)
        spawned.append(plat)
    return spawned