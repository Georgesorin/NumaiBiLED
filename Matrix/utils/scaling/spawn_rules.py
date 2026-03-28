import random

from .game_settings import GameSettings
from ..tile.tile import Tile

class SpawnRules:
    """
    Heat map over the grid of valid 2x2 spawn positions.

    `cutoff_fraction` controls how aggressively far-away spots are
    preferred.  Higher values (hard/nightmare) cut more of the "cold"
    (close) candidates, pushing new spawns further from existing ones.

    `heat_spread` scales how much heat a placement radiates.
    Lower values make the heat map more local, so consecutive spawns
    can land further apart.
    """

    PLAY_H = 26
    PW = 2
    PH = 2

    def __init__(self, settings: GameSettings, size):
        self.board_w = size
        self.play_h = self.PLAY_H
        self.cutoff_fraction = settings.heat_search_area
        self.heat_spread = settings.heat_spread
        self._grid_w = self.board_w // self.PW
        self._grid_h = self.play_h // self.PH
        self.heat = [[1.0] * self._grid_w for _ in range(self._grid_h)]

    def reset(self):
        for gy in range(self._grid_h):
            for gx in range(self._grid_w):
                self.heat[gy][gx] = 1.0

    def _pos_to_grid(self, x, y):
        return x // self.PW, y // self.PH

    def _grid_to_pos(self, gx, gy):
        return gx * self.PW, gy * self.PH

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

        scored.sort(key=lambda t: t[2])

        cut = max(1, int(len(scored) * self.cutoff_fraction))
        if len(scored) - cut < 1:
            cut = len(scored) - 1
        viable = scored[cut:]

        weights = [s[2] for s in viable]
        total_w = sum(weights)
        if total_w <= 0:
            choice = random.choice(viable)
        else:
            choice = random.choices(viable, weights=weights, k=1)[0]

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