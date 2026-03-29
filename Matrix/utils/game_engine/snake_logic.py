import time
import random
from collections import deque
from ..data.network import BOARD_WIDTH, BOARD_HEIGHT
from ..ui.colors import RED, YELLOW, MAGENTA

# Constants
PLAY_Y_MIN, PLAY_Y_MAX = 0, BOARD_HEIGHT
MIN_LENGTH, SHRINK_TIMEOUT = 3, 3.0
DAMAGE, MAX_HP, DMG_COOLDOWN = 10, 100, 1.0
CHASE_RADIUS, CHASE_MAX_SEC, CHASE_CD_SEC, CHASE_PROB = 4, 3.0, 2.0, 0.5
HEAD_COL, BODY_COL, TAIL_COL = (200, 255, 200), (0, 200, 50), (0, 60, 15)

FRUIT_DEFS = [
    {"name": "apple",  "hp": 1, "color": RED,           "weight": 5},
    {"name": "banana", "hp": 2, "color": YELLOW,        "weight": 3},
    {"name": "melon",  "hp": 3, "color": MAGENTA,       "weight": 2},
]

# Helpers
_DIRS = ((0, 1), (0, -1), (1, 0), (-1, 0))

def _wrap(p):
    return (p[0] % BOARD_WIDTH, PLAY_Y_MIN + (p[1] - PLAY_Y_MIN) % (PLAY_Y_MAX - PLAY_Y_MIN))

def _neighbours(pos, wrap=True):
    x, y = pos
    if wrap: return [_wrap((x + dx, y + dy)) for dx, dy in _DIRS]
    return [(x+dx, y+dy) for dx, dy in _DIRS if 0 <= x+dx < BOARD_WIDTH and PLAY_Y_MIN <= y+dy < PLAY_Y_MAX]

def _bfs(start, goal, walls, wrap=True):
    if start == goal: return []
    visited, prev, queue = {start}, {}, deque([start])
    while queue:
        cur = queue.popleft()
        for nb in _neighbours(cur, wrap):
            if nb in visited or (nb in walls and nb != goal): continue
            prev[nb] = cur
            if nb == goal:
                path, c = [], nb
                while c in prev:
                    path.append(c)
                    c = prev[c]
                return path[::-1]
            visited.add(nb)
            queue.append(nb)
    return []

def _longest_toward(start, goal, walls, wrap=True):
    if start == goal: return None
    open_list, closed, g_cost, parent = [start], set(), {start: 0}, {}
    w, h = BOARD_WIDTH, PLAY_Y_MAX - PLAY_Y_MIN
    def _h(a):
        dx = min(abs(a[0]-goal[0]), w-abs(a[0]-goal[0])) if wrap else abs(a[0]-goal[0])
        dy = min(abs(a[1]-goal[1]), h-abs(a[1]-goal[1])) if wrap else abs(a[1]-goal[1])
        return dx + dy
    while open_list:
        best = max(open_list, key=lambda n: g_cost[n] + _h(n))
        open_list.remove(best)
        closed.add(best)
        for nb in _neighbours(best, wrap):
            if nb in closed or (nb in walls and nb != goal): continue
            if nb not in g_cost or g_cost[best] + 1 > g_cost[nb]:
                g_cost[nb], parent[nb] = g_cost[best] + 1, best
            if nb == goal:
                c = nb
                while parent.get(c) != start: c = parent[c]
                return c
            if nb not in open_list: open_list.append(nb)
    return None

def _flood_area(head, walls, wrap=True):
    visited, queue = {head}, deque([head])
    while queue:
        cur = queue.popleft()
        for nb in _neighbours(cur, wrap):
            if nb not in walls and nb not in visited:
                visited.add(nb)
                queue.append(nb)
    return len(visited)

class Fruit:
    def __init__(self, x, y, fdef):
        self.x, self.y, self.hp = x, y, fdef["hp"]
        self.max_hp, self.color, self.alive = self.hp, fdef["color"], True
    def stomp(self):
        self.hp -= 1
        if self.hp <= 0: self.alive = False
    def draw_color(self):
        f = self.hp / self.max_hp
        return tuple(max(0, int(c * (0.3 + 0.7 * f))) for c in self.color)

class Snake:
    def __init__(self, cx, cy, length, b_int, m_int, wrap=True):
        self.wrap = wrap
        self.body = [(_wrap((cx, cy-i)) if wrap else (cx, cy-i)) for i in range(length)]
        self.grow, self.move_acc = 0, 0.0
        self._evt = time.time()
        self._next_shrink = self._evt + SHRINK_TIMEOUT
        self._init_len, self._b_int, self._m_int = length, b_int, m_int
        self._chasing, self._chase_tgt, self._chase_t0, self._chase_cd = False, None, 0.0, 0.0

    @property
    def head(self): return self.body[0]
    def body_set(self): return set(self.body)
    @property
    def interval(self):
        t = max(0.0, min(1.0, (len(self.body) - MIN_LENGTH) / max(1, self._init_len - MIN_LENGTH)))
        return self._m_int + t * (self._b_int - self._m_int)
    def feed(self, amount):
        self.grow += amount
        self._evt, self._next_shrink = time.time(), time.time() + SHRINK_TIMEOUT
    def touch(self):
        self._evt, self._next_shrink = time.time(), time.time() + SHRINK_TIMEOUT
    def try_shrink(self):
        now = time.time()
        while now >= self._next_shrink:
            self._next_shrink += SHRINK_TIMEOUT
            if len(self.body) > MIN_LENGTH: self.body.pop()
            else: return True
        return False
    def advance(self, nxt):
        will_pop = self.grow <= 0
        for i, seg in enumerate(self.body):
            if seg == nxt:
                if will_pop and i == len(self.body) - 1: break
                return "self_collide"
        self.body.insert(0, nxt)
        if self.grow > 0: self.grow -= 1
        else: self.body.pop()
        return "ok"
    def seg_color(self, idx):
        if idx == 0: return HEAD_COL
        f = idx / max(1, len(self.body) - 1)
        return tuple(int(BODY_COL[c] + (TAIL_COL[c] - BODY_COL[c]) * f) for c in range(3))

def _pick_spawn(players, blocked, bw, ylo, yhi):
    cands = []
    for y in range(ylo, yhi):
        for x in range(bw):
            if (x, y) in blocked: continue
            d = min((abs(x-px) + abs(y-py) for px, py in players), default=bw+yhi)
            cands.append((x, y, d))
    if not cands: return None
    cands.sort(key=lambda c: c[2], reverse=True)
    pool = cands[:max(1, len(cands)//4)]
    return random.choices(pool, weights=[c[2] for c in pool] if sum(c[2] for c in pool) > 0 else None, k=1)[0][:2]

def _rand_fruit_type(settings):
    max_h = 1 if settings.player_count <= 2 else 2 if settings.player_count <= 4 else 3
    pool = [(d, w) for d, w in zip(FRUIT_DEFS, settings.fruit_weights) if d["hp"] <= max_h]
    defs, wts = zip(*pool)
    return random.choices(defs, weights=wts, k=1)[0]

class SnakeAI:
    def __init__(self, snake, settings):
        self.snake, self.settings = snake, settings

    def _vsnake_safe(self, vbody, vgrow):
        flen = len(vbody) + vgrow
        if flen < 2: return True
        vh, vt, vw = vbody[0], vbody[-1], set(vbody)
        if vgrow == 0: vw.discard(vt)
        return _bfs(vh, vt, vw, self.snake.wrap) and _flood_area(vh, vw, self.snake.wrap) >= int(flen * 1.5)

    def _sim_walk(self, path, grow_bonus):
        vbody, vgrow = list(self.snake.body), self.snake.grow
        for step in path:
            occ = set(vbody)
            if vgrow <= 0: occ.discard(vbody[-1])
            if step in occ: return vbody, vgrow, False
            vbody.insert(0, step)
            if vgrow > 0: vgrow -= 1
            else: vbody.pop()
        return vbody, vgrow + grow_bonus, True

    def _decide_target(self, engine, fruits):
        head, now, players = self.snake.head, time.time(), engine.get_held_xy()
        if self.snake._chasing:
            if now - self.snake._chase_t0 > CHASE_MAX_SEC: self.snake._chasing = False
            elif players:
                near = [(p, abs(p[0]-head[0])+abs(p[1]-head[1])) for p in players if abs(p[0]-head[0])+abs(p[1]-head[1]) <= CHASE_RADIUS*2]
                if near:
                    self.snake._chase_tgt = min(near, key=lambda t: t[1])[0]
                    return self.snake._chase_tgt, "player"
            self.snake._chasing, self.snake._chase_cd = False, now + CHASE_CD_SEC
        if not self.snake._chasing and players and now >= self.snake._chase_cd:
            near = [p for p in players if abs(p[0]-head[0])+abs(p[1]-head[1]) <= CHASE_RADIUS]
            if near and random.random() < CHASE_PROB:
                self.snake._chasing, self.snake._chase_tgt, self.snake._chase_t0 = True, min(near, key=lambda p: abs(p[0]-head[0])+abs(p[1]-head[1])), now
                return self.snake._chase_tgt, "player"
        alive = [f for f in fruits if f.alive]
        if alive:
            best = min(alive, key=lambda f: abs(f.x-head[0])+abs(f.y-head[1]))
            return (best.x, best.y), "fruit"
        return None, None

    def get_step(self, engine, fruits):
        tgt, kind = self._decide_target(engine, fruits)
        head, walls, wrap = self.snake.head, self.snake.body_set(), self.snake.wrap
        if self.snake.grow == 0: walls.discard(self.snake.body[-1])

        if tgt:
            path = _bfs(head, tgt, walls, wrap)
            if path:
                gb = next((f.max_hp for f in fruits if f.alive and (f.x, f.y) == tgt), 0) if kind == "fruit" else 0
                vb, vg, ok = self._sim_walk(path, gb)
                if ok and self._vsnake_safe(vb, vg): return path[0]
        
        tp = _bfs(head, self.snake.body[-1], walls, wrap)
        if tp:
            vb, vg, ok = self._sim_walk([tp[0]], 0)
            if ok and self._vsnake_safe(vb, vg): return tp[0]
            
        ls = _longest_toward(head, self.snake.body[-1], walls, wrap)
        if ls:
            vb, vg, ok = self._sim_walk([ls], 0)
            if ok and self._vsnake_safe(vb, vg): return ls

        best, b_area = None, -1
        for nxt in _neighbours(head, wrap):
            vb, vg, ok = self._sim_walk([nxt], 0)
            if not ok: continue
            vw = set(vb)
            if vg == 0: vw.discard(vb[-1])
            area = _flood_area(nxt, vw, wrap)
            if area > b_area: b_area, best = area, nxt
        return best
