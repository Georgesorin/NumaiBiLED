"""
Game 3 – Snake
===============
AI snake hunts fruits on the board.  Players stomp fruits to destroy them
and starve the snake, but touching the snake costs HP.

Fruit types (player stomps to destroy):
  apple  → 1 stomp  (red)
  banana → 2 stomps (yellow)
  melon  → 3 stomps (bright green)

The snake uses adapted A* pathfinding: it normally pursues the nearest
fruit, but will chase nearby players for a limited window before
returning to fruit-seeking.  This prevents players from indefinitely
distracting the snake away from eating.
"""

import time
import random
from collections import deque

from utils.data.game_engine import (
    BOARD_WIDTH, BOARD_HEIGHT, load_config, run_game,
)
from utils.master import GameMaster
from utils.states._abs_state import GameState
from utils.ui.colors import BLACK, WHITE, RED, YELLOW, GREEN, MAGENTA

# ============================================================
#  Constants
# ============================================================

PLAY_Y_MIN = 0
PLAY_Y_MAX = BOARD_HEIGHT

MIN_LENGTH = 3

SHRINK_TIMEOUT = 3.0

DAMAGE = 10
MAX_HP = 100
DMG_COOLDOWN = 1.0

CHASE_RADIUS = 4
CHASE_MAX_SEC = 3.0
CHASE_CD_SEC = 2.0
CHASE_PROB = 0.5

BASE_MIN_FRUITS = 2
BASE_SPAWN_INTERVAL = 5.0

HEAD_COL = (200, 255, 200)
BODY_COL = (0, 200, 50)
TAIL_COL = (0, 60, 15)

FRUIT_DEFS = [
    {"name": "apple",  "hp": 1, "color": RED,           "weight": 5},
    {"name": "banana", "hp": 2, "color": YELLOW,        "weight": 3},
    {"name": "melon",  "hp": 3, "color": MAGENTA,       "weight": 2},
]

# ============================================================
#  Snake-specific settings (player count + difficulty)
# ============================================================

SNAKE_DIFFICULTIES = {
    "easy":      dict(base_interval=0.2,  min_interval=0.16, fruit_weights=(8, 2, 1), wrap=False),
    "medium":    dict(base_interval=0.16, min_interval=0.11, fruit_weights=(5, 3, 2), wrap=False),
    "hard":      dict(base_interval=0.2, min_interval=0.08, fruit_weights=(3, 4, 3), wrap=True),
    "nightmare": dict(base_interval=0.16, min_interval=0.02, fruit_weights=(2, 4, 4), wrap=True),
}

PLAYER_LENGTH = {
    2: 6,
    3: 8,
    4: 10,
    5: 12,
    6: 14,
}


class SnakeSettings:
    def __init__(self, player_count, difficulty):
        self.player_count = max(2, min(6, player_count))
        diff = SNAKE_DIFFICULTIES[difficulty]
        self.difficulty_name = difficulty
        self.base_interval = diff["base_interval"]
        self.min_interval = diff["min_interval"]
        self.initial_length = PLAYER_LENGTH[self.player_count]
        self.fruit_weights = diff["fruit_weights"]
        self.wrap = diff["wrap"]
        self.min_fruits = BASE_MIN_FRUITS + (self.player_count - 2) // 2
        self.spawn_interval = BASE_SPAWN_INTERVAL - 0.5 * (self.player_count - 2)


def _prompt_snake_settings():
    print("\n=== SNAKE - Setup ===\n")

    while True:
        try:
            n = int(input("Number of players (2-6): ").strip())
            if 2 <= n <= 6:
                break
            print("  Please enter a number between 2 and 6.")
        except ValueError:
            print("  Invalid input.")

    diff_names = list(SNAKE_DIFFICULTIES.keys())
    print("\nDifficulty:")
    for i, name in enumerate(diff_names, 1):
        print(f"  {i}. {name}")

    while True:
        try:
            choice = input(f"Choose difficulty (1-{len(diff_names)}): ").strip()
            idx = int(choice) - 1
            if 0 <= idx < len(diff_names):
                break
            print(f"  Please enter a number between 1 and {len(diff_names)}.")
        except ValueError:
            print("  Invalid input.")

    settings = SnakeSettings(n, diff_names[idx])
    print(f"\n  Players: {settings.player_count}")
    print(f"  Difficulty: {settings.difficulty_name}")
    print(f"  Snake length: {settings.initial_length}")
    print(f"  Speed: base={settings.base_interval:.2f}s  min={settings.min_interval:.2f}s")
    print(f"  Fruits: min={settings.min_fruits}  spawn every {settings.spawn_interval:.1f}s\n")
    return settings


# ============================================================
#  Pathfinding helpers
# ============================================================

_DIRS = ((0, 1), (0, -1), (1, 0), (-1, 0))

def _wrap(p):
    """Wrap coordinates toroidally so the snake passes through walls."""
    return (p[0] % BOARD_WIDTH,
            PLAY_Y_MIN + (p[1] - PLAY_Y_MIN) % (PLAY_Y_MAX - PLAY_Y_MIN))

def _inbounds(p):
    return 0 <= p[0] < BOARD_WIDTH and PLAY_Y_MIN <= p[1] < PLAY_Y_MAX


def _neighbours(pos, wrap=True):
    """Return the four neighbours of *pos*.
    When *wrap* is True the board is toroidal; when False, out-of-bounds
    neighbours are discarded."""
    x, y = pos
    if wrap:
        return [_wrap((x + dx, y + dy)) for dx, dy in _DIRS]
    out = []
    for dx, dy in _DIRS:
        nx, ny = x + dx, y + dy
        if _inbounds((nx, ny)):
            out.append((nx, ny))
    return out


def _bfs(start, goal, walls, wrap=True):
    """Shortest path from *start* to *goal*.
    Returns list of cells [first_step, ..., goal] or []."""
    if start == goal:
        return []
    visited = {start}
    prev = {}
    queue = deque([start])
    while queue:
        cur = queue.popleft()
        for nb in _neighbours(cur, wrap):
            if nb in visited:
                continue
            if nb in walls and nb != goal:
                continue
            prev[nb] = cur
            if nb == goal:
                path = []
                c = nb
                while c in prev:
                    path.append(c)
                    c = prev[c]
                path.reverse()
                return path
            visited.add(nb)
            queue.append(nb)
    return []


def _longest_toward(start, goal, walls, wrap=True):
    """A* that maximises path cost to *goal* (picks the farthest / most
    winding route).  Uses max-F selection so the snake takes the longest
    safe path when following its own tail, buying time.
    Returns first step or None."""
    if start == goal:
        return None
    open_list = [start]
    closed = set()
    g_cost = {start: 0}
    parent = {}
    w, h = BOARD_WIDTH, PLAY_Y_MAX - PLAY_Y_MIN
    def _h(a):
        if wrap:
            dx = min(abs(a[0] - goal[0]), w - abs(a[0] - goal[0]))
            dy = min(abs(a[1] - goal[1]), h - abs(a[1] - goal[1]))
        else:
            dx = abs(a[0] - goal[0])
            dy = abs(a[1] - goal[1])
        return dx + dy

    while open_list:
        best = None
        best_f = -1
        for n in open_list:
            f = g_cost[n] + _h(n)
            if f >= best_f:
                best_f = f
                best = n

        open_list.remove(best)
        closed.add(best)

        for nb in _neighbours(best, wrap):
            if nb in closed:
                continue
            if nb in walls and nb != goal:
                continue
            ng = g_cost[best] + 1
            if nb not in g_cost or ng > g_cost[nb]:
                g_cost[nb] = ng
                parent[nb] = best
            if nb == goal:
                c = nb
                while parent.get(c) != start:
                    c = parent[c]
                return c
            if nb not in open_list:
                open_list.append(nb)
    return None


def _flood_area(head, walls, wrap=True):
    """Count reachable cells from *head*."""
    visited = {head}
    queue = deque([head])
    while queue:
        cur = queue.popleft()
        for nb in _neighbours(cur, wrap):
            if nb not in walls and nb not in visited:
                visited.add(nb)
                queue.append(nb)
    return len(visited)


# ============================================================
#  Fruit
# ============================================================

class Fruit:
    __slots__ = ("x", "y", "hp", "max_hp", "color", "alive")

    def __init__(self, x, y, fdef):
        self.x, self.y = x, y
        self.hp = self.max_hp = fdef["hp"]
        self.color = fdef["color"]
        self.alive = True

    def stomp(self):
        self.hp -= 1
        if self.hp <= 0:
            self.alive = False

    def draw_color(self):
        f = self.hp / self.max_hp
        return tuple(max(0, int(c * (0.3 + 0.7 * f))) for c in self.color)


# ============================================================
#  Snake
# ============================================================

class Snake:
    def __init__(self, cx, cy, length, base_interval, min_interval, wrap=True):
        self.wrap = wrap
        init_fn = _wrap if wrap else lambda p: p
        self.body = [init_fn((cx, cy - i)) for i in range(length)]
        self.grow = 0
        self._evt = time.time()
        self._next_shrink = self._evt + SHRINK_TIMEOUT
        self.move_acc = 0.0
        self._initial_length = length
        self._base_interval = base_interval
        self._min_interval = min_interval

        self._chasing = False
        self._chase_tgt = None
        self._chase_t0 = 0.0
        self._chase_cd = 0.0

    @property
    def head(self):
        return self.body[0]

    def body_set(self):
        return set(self.body)

    @property
    def interval(self):
        t = max(0.0, min(1.0,
            (len(self.body) - MIN_LENGTH) / max(1, self._initial_length - MIN_LENGTH)))
        return self._min_interval + t * (self._base_interval - self._min_interval)

    def _reset_timer(self):
        self._evt = time.time()
        self._next_shrink = self._evt + SHRINK_TIMEOUT

    def feed(self, amount):
        self.grow += amount
        self._reset_timer()

    def touch(self):
        self._reset_timer()

    def try_shrink(self):
        """Shrink by one for every elapsed SHRINK_TIMEOUT.
        Returns True when the snake is too small and should respawn."""
        now = time.time()
        while now >= self._next_shrink:
            self._next_shrink += SHRINK_TIMEOUT
            if len(self.body) > MIN_LENGTH:
                self.body.pop()
            else:
                return True
        return False

    def advance(self, nxt):
        """Move head to *nxt* (already wrapped).
        Returns 'ok', 'self_collide', or 'refused'."""
        will_pop = self.grow <= 0
        for i, seg in enumerate(self.body):
            if seg == nxt:
                if will_pop and i == len(self.body) - 1:
                    break  # tail is about to vacate — ok
                return "self_collide"
        self.body.insert(0, nxt)
        if self.grow > 0:
            self.grow -= 1
        else:
            self.body.pop()
        return "ok"

    def seg_color(self, idx):
        if idx == 0:
            return HEAD_COL
        f = idx / max(1, len(self.body) - 1)
        return tuple(
            int(BODY_COL[c] + (TAIL_COL[c] - BODY_COL[c]) * f) for c in range(3)
        )


# ============================================================
#  Fruit spawner  –  prefers spots far from players
# ============================================================

def _pick_spawn(players, blocked, bw, ylo, yhi):
    cands = []
    for y in range(ylo, yhi):
        for x in range(bw):
            if (x, y) in blocked:
                continue
            d = min((abs(x - px) + abs(y - py) for px, py in players),
                    default=bw + yhi)
            cands.append((x, y, d))
    if not cands:
        return None
    cands.sort(key=lambda c: c[2], reverse=True)
    pool = cands[:max(1, len(cands) // 4)]
    wts = [c[2] for c in pool]
    if sum(wts) > 0:
        ch = random.choices(pool, weights=wts, k=1)[0]
    else:
        ch = random.choice(pool)
    return ch[0], ch[1]


def _rand_fruit_type(settings):
    max_hp = 1 if settings.player_count <= 2 else 2 if settings.player_count <= 4 else 3
    pool = [(d, w) for d, w in zip(FRUIT_DEFS, settings.fruit_weights) if d["hp"] <= max_hp]
    defs, wts = zip(*pool)
    return random.choices(defs, weights=wts, k=1)[0]


# ============================================================
#  States
# ============================================================

class _Start(GameState):
    def __init__(self, **_kw):
        self.t = 0.0

    def enter(self, engine):
        self.t = 0.0
        engine.entities.clear()

    def update(self, engine, dt):
        self.t += dt
        engine.clear()
        if int(self.t * 3) % 2 == 0:
            engine.draw_text_large("S", 1, 2, GREEN)
            engine.draw_text_large("N", 1, 10, GREEN)
            engine.draw_text_large("K", 1, 18, GREEN)
        engine.draw_text_small("STEP", 1, 27, WHITE)
        if engine.any_pressed():
            return ("play", {})

    def exit(self, engine):
        pass


class _Play(GameState):
    """Main gameplay: snake hunts fruits, players stomp fruits & dodge."""

    def __init__(self, settings=None, **_kw):
        self.settings = settings
        self.hp = MAX_HP
        self.snake = None
        self.fruits = []
        self.dmg_cd = {}
        self.last_spawn = 0.0
        self.elapsed = 0.0
        self.flash = {}
        self.snake_ate = 0
        self.players_destroyed = 0

    def _end_stats(self, reason):
        return {
            "play_time": self.elapsed,
            "snake_ate": self.snake_ate,
            "players_destroyed": self.players_destroyed,
            "reason": reason,
        }

    def _make_snake(self):
        cx = BOARD_WIDTH // 2
        cy = (PLAY_Y_MIN + PLAY_Y_MAX) // 2
        s = self.settings
        return Snake(cx, cy, s.initial_length, s.base_interval, s.min_interval,
                     wrap=s.wrap)

    def enter(self, engine):
        engine.entities.clear()
        self.snake = self._make_snake()
        self.fruits = []
        self.hp = MAX_HP
        self.dmg_cd = {}
        self.last_spawn = time.time()
        self.elapsed = 0.0
        self.flash = {}
        self.snake_ate = 0
        self.players_destroyed = 0
        self._spawn(engine, self.settings.min_fruits + 1)

    # ── helpers ───────────────────────────────────────────

    def _spawn(self, engine, n):
        players = engine.get_held_xy()
        blocked = self.snake.body_set() | {(f.x, f.y) for f in self.fruits}
        for _ in range(n):
            pos = _pick_spawn(players, blocked,
                              BOARD_WIDTH, PLAY_Y_MIN, PLAY_Y_MAX)
            if pos is None:
                break
            self.fruits.append(Fruit(pos[0], pos[1], _rand_fruit_type(self.settings)))
            blocked.add(pos)

    def _target(self, engine):
        """Decide what the snake should pursue.
        Returns (pos, kind) where kind is 'player' or 'fruit', or (None, None)."""
        head = self.snake.head
        now = time.time()
        players = engine.get_held_xy()

        # ── active chase bookkeeping ──
        if self.snake._chasing:
            if now - self.snake._chase_t0 > CHASE_MAX_SEC:
                self.snake._chasing = False
                self.snake._chase_tgt = None
                self.snake._chase_cd = now + CHASE_CD_SEC
            elif players:
                near = [
                    (p, abs(p[0] - head[0]) + abs(p[1] - head[1]))
                    for p in players
                    if abs(p[0] - head[0]) + abs(p[1] - head[1]) <= CHASE_RADIUS * 2
                ]
                if near:
                    self.snake._chase_tgt = min(near, key=lambda t: t[1])[0]
                    return self.snake._chase_tgt, "player"
                self.snake._chasing = False
                self.snake._chase_tgt = None
                self.snake._chase_cd = now + CHASE_CD_SEC
            else:
                self.snake._chasing = False
                self.snake._chase_tgt = None
                self.snake._chase_cd = now + CHASE_CD_SEC

        # ── maybe start a new chase ──
        if not self.snake._chasing and players and now >= self.snake._chase_cd:
            near = [p for p in players
                    if abs(p[0] - head[0]) + abs(p[1] - head[1]) <= CHASE_RADIUS]
            if near and random.random() < CHASE_PROB:
                tgt = min(near,
                          key=lambda p: abs(p[0] - head[0]) + abs(p[1] - head[1]))
                self.snake._chasing = True
                self.snake._chase_tgt = tgt
                self.snake._chase_t0 = now
                return tgt, "player"

        # ── default: nearest fruit ──
        alive = [f for f in self.fruits if f.alive]
        if alive:
            best = min(alive,
                       key=lambda f: abs(f.x - head[0]) + abs(f.y - head[1]))
            return (best.x, best.y), "fruit"
        return None, None

    def _walls(self):
        """Current wall set for pathfinding (body minus tail when not growing)."""
        bs = self.snake.body_set()
        if self.snake.grow == 0:
            bs.discard(self.snake.body[-1])
        return bs

    def _sim_walk(self, path, grow_bonus):
        """Clone the snake, walk it along *path*, then add *grow_bonus*.
        Returns (vbody, vgrow, ok) — ok is False if any step would
        self-collide (making the path physically impossible)."""
        vbody = list(self.snake.body)
        vgrow = self.snake.grow
        for step in path:
            will_pop = vgrow <= 0
            occupied = set(vbody)
            if will_pop:
                occupied.discard(vbody[-1])
            if step in occupied:
                return vbody, vgrow, False
            vbody.insert(0, step)
            if vgrow > 0:
                vgrow -= 1
            else:
                vbody.pop()
        vgrow += grow_bonus
        return vbody, vgrow, True

    def _vsnake_is_safe(self, vbody, vgrow):
        """After a simulated journey, check TWO conditions:
        1. The virtual snake can BFS-reach its own tail.
        2. The flood-fill area from the head >= future body length * 1.5
           (the extra margin prevents gradual self-boxing).
        Both must pass."""
        future_len = len(vbody) + vgrow
        if future_len < 2:
            return True
        vhead = vbody[0]
        vtail = vbody[-1]
        vwalls = set(vbody)
        if vgrow == 0:
            vwalls.discard(vtail)
        wrap = self.snake.wrap
        if not _bfs(vhead, vtail, vwalls, wrap):
            return False
        area = _flood_area(vhead, vwalls, wrap)
        return area >= int(future_len * 1.5)

    def _safe_step_toward(self, goal, walls):
        """BFS toward *goal*; simulate the walk and check the virtual snake
        can still reach its tail.  Returns the first step or None."""
        path = _bfs(self.snake.head, goal, walls, self.snake.wrap)
        if not path:
            return None
        vbody, vgrow, ok = self._sim_walk(path, 0)
        if ok and self._vsnake_is_safe(vbody, vgrow):
            return path[0]
        return None

    def _flood_pick(self):
        """Emergency fallback: among all neighbours that advance()
        would accept, pick the one with the most flood-fill room."""
        head = self.snake.head
        body = self.snake.body
        will_pop = self.snake.grow <= 0
        wrap = self.snake.wrap

        best = None
        best_area = -1
        for nxt in _neighbours(head, wrap):
            ok = True
            for i, seg in enumerate(body):
                if seg == nxt:
                    if will_pop and i == len(body) - 1:
                        break
                    ok = False
                    break
            if not ok:
                continue
            sim_body = [nxt] + list(body)
            if will_pop:
                sim_body.pop()
            sim_walls = set(sim_body)
            sim_walls.discard(sim_body[-1])
            area = _flood_area(nxt, sim_walls, wrap)
            if area > best_area:
                best_area = area
                best = nxt
        return best

    def _try_move(self, nxt):
        """Try to advance to wrapped *nxt*; verify with a 1-step
        virtual-walk safety check before committing.
        Returns 'ok', 'self_collide', or False."""
        vbody, vgrow, ok = self._sim_walk([nxt], 0)
        if not ok:
            return False
        if not self._vsnake_is_safe(vbody, vgrow):
            return False
        return self.snake.advance(nxt)

    def _step(self, engine):
        """Virtual-snake algorithm — every candidate move is verified
        safe (can reach tail + enough flood area) before committing.
        Returns True if the snake self-collided (game over).

        Priority:
          1. Pursue target (fruit or player).
          2. Follow own tail (BFS shortest, then longest).
          3. Pick neighbour with most room (flood-fill).
        """
        tgt, kind = self._target(engine)
        head = self.snake.head
        walls = self._walls()
        tail = self.snake.body[-1]

        wrap = self.snake.wrap

        # ── 1. pursue target ──
        if tgt is not None:
            if kind == "fruit":
                path = _bfs(head, tgt, walls, wrap)
                if path:
                    grow_bonus = 0
                    for fr in self.fruits:
                        if fr.alive and (fr.x, fr.y) == tgt:
                            grow_bonus = fr.max_hp
                            break
                    vbody, vgrow, ok = self._sim_walk(path, grow_bonus)
                    if ok and self._vsnake_is_safe(vbody, vgrow):
                        result = self._try_move(path[0])
                        if result == "self_collide":
                            return True
                        if result == "ok":
                            return False

            elif kind == "player":
                step = self._safe_step_toward(tgt, walls)
                if step is not None:
                    result = self._try_move(step)
                    if result == "self_collide":
                        return True
                    if result == "ok":
                        return False

        # ── 2. follow own tail ──
        tail_path = _bfs(head, tail, walls, wrap)
        if tail_path:
            result = self._try_move(tail_path[0])
            if result == "self_collide":
                return True
            if result == "ok":
                return False
        longest_step = _longest_toward(head, tail, walls, wrap)
        if longest_step is not None:
            result = self._try_move(longest_step)
            if result == "self_collide":
                return True
            if result == "ok":
                return False

        # ── 3. flood-pick (already does its own safety ranking) ──
        pick = self._flood_pick()
        if pick is not None:
            result = self.snake.advance(pick)
            if result == "self_collide":
                return True
        return False

    # ── main tick ─────────────────────────────────────────

    def update(self, engine, dt):
        self.elapsed += dt
        engine.clear()
        now = time.time()

        # player stomps on fruits
        before = sum(1 for f in self.fruits if f.alive)
        for px, py in engine.get_pressed_xy():
            for fr in self.fruits:
                if fr.alive and fr.x == px and fr.y == py:
                    fr.stomp()
        self.fruits = [f for f in self.fruits if f.alive]
        self.players_destroyed += before - len(self.fruits)

        # snake movement (frame-rate independent)
        self.snake.move_acc += dt
        while self.snake.move_acc >= self.snake.interval:
            self.snake.move_acc -= self.snake.interval
            if self._step(engine):
                return ("end", self._end_stats("self_collide"))

            hx, hy = self.snake.head
            for fr in self.fruits:
                if fr.alive and fr.x == hx and fr.y == hy:
                    self.snake.feed(fr.max_hp)
                    fr.alive = False
                    self.snake_ate += 1
            self.fruits = [f for f in self.fruits if f.alive]

        # damage from touching the snake (per-position cooldown so
        # multiple simultaneous player contacts each register)
        sset = self.snake.body_set()
        touched = False
        for px, py in engine.get_held_xy():
            if (px, py) in sset:
                last = self.dmg_cd.get((px, py), 0.0)
                if now - last > DMG_COOLDOWN:
                    self.hp -= DAMAGE
                    self.dmg_cd[(px, py)] = now
                    self.flash[(px, py)] = 0.4
                    touched = True
        if touched:
            self.snake.touch()
        self.dmg_cd = {k: v for k, v in self.dmg_cd.items()
                       if now - v < DMG_COOLDOWN * 3}

        if self.hp <= 0:
            return ("end", self._end_stats("hp_lost"))

        # starvation — snake shrunk below minimum
        if self.snake.try_shrink():
            return ("end", self._end_stats("starved"))

        # fruit maintenance
        mf = self.settings.min_fruits
        if len(self.fruits) < mf or now - self.last_spawn > self.settings.spawn_interval:
            self._spawn(engine, max(1, mf - len(self.fruits)))
            self.last_spawn = now

        # ── draw ──────────────────────────────────────────

        for fr in self.fruits:
            engine.set_pixel(fr.x, fr.y, *fr.draw_color())

        for i, (sx, sy) in enumerate(self.snake.body):
            engine.set_pixel(sx, sy, *self.snake.seg_color(i))

        for k in list(self.flash):
            self.flash[k] -= dt
            if self.flash[k] > 0:
                if int(self.elapsed * 10) % 2 == 0:
                    engine.set_pixel(k[0], k[1], *RED)
            else:
                del self.flash[k]

    def exit(self, engine):
        pass


class _End(GameState):
    def __init__(self, play_time=0, snake_ate=0, players_destroyed=0,
                 reason="hp_lost", **_kw):
        self.play_time = play_time
        self.snake_ate = snake_ate
        self.players_destroyed = players_destroyed
        self.reason = reason
        self.win = reason == "starved" or players_destroyed > snake_ate
        self.t = 0.0

    def enter(self, engine):
        self.t = 0.0
        engine.entities.clear()

    def update(self, engine, dt):
        self.t += dt
        engine.clear()

        # header — WIN or LOSE, blinking
        if self.win:
            if int(self.t * 3) % 2 == 0:
                engine.draw_text_small("YOU", 3, 0, GREEN)
                engine.draw_text_small("WIN!", 2, 6, GREEN)
        else:
            if int(self.t * 3) % 2 == 0:
                engine.draw_text_small("YOU", 3, 0, RED)
                engine.draw_text_small("LOSE", 2, 6, RED)

        # snake ate  (snake icon = green square + count)
        engine.set_pixel(1, 15, *BODY_COL)
        engine.set_pixel(2, 15, *BODY_COL)
        engine.set_pixel(3, 15, *HEAD_COL)
        sa = str(self.snake_ate)
        engine.draw_text_small(sa, 6, 13, RED)

        # players destroyed  (foot icon = white square + count)
        engine.set_pixel(1, 20, *WHITE)
        engine.set_pixel(1, 21, *WHITE)
        engine.set_pixel(2, 20, *WHITE)
        engine.set_pixel(2, 21, *WHITE)
        engine.set_pixel(3, 19, *WHITE)
        engine.set_pixel(3, 22, *WHITE)
        pd = str(self.players_destroyed)
        engine.draw_text_small(pd, 6, 19, GREEN)

        # time
        secs = str(int(self.play_time))
        engine.draw_text_small(secs + "S", 1, 26, YELLOW)

        if self.t > 8.0 and engine.any_pressed():
            return ("start", {})

    def exit(self, engine):
        engine.entities.clear()


# ============================================================
#  Wiring
# ============================================================

_TRANSITIONS = {
    "start": lambda s, _r, **kw: _Start(**kw),
    "play":  lambda s, _r, **kw: _Play(settings=s, **kw),
    "end":   lambda s, _r, **kw: _End(**kw),
}

if __name__ == "__main__":
    settings = _prompt_snake_settings()
    game = GameMaster(lambda: _Start(), settings, None, _TRANSITIONS)
    run_game(game, config=load_config(), title="Game 3 - Snake!")
