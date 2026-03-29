import time
from ._abs_state import GameState
from ..game_engine.snake_logic import (
    Snake, Fruit, SnakeAI, _pick_spawn, _rand_fruit_type,
    MAX_HP, DAMAGE, DMG_COOLDOWN, BOARD_WIDTH, 
    PLAY_Y_MIN, PLAY_Y_MAX, RED
)

class SnakePlayState(GameState):
    def __init__(self, settings=None, **_kw):
        self.settings = settings
        self.hp, self.snake, self.fruits = MAX_HP, None, []
        self.dmg_cd, self.last_spawn, self.elapsed = {}, 0.0, 0.0
        self.flash, self.snake_ate, self.players_destroyed = {}, 0, 0
        self.ai = None

    def enter(self, engine):
        engine.entities.clear()
        cx, cy = BOARD_WIDTH // 2, (PLAY_Y_MIN + PLAY_Y_MAX) // 2
        self.snake = Snake(cx, cy, self.settings.initial_length, self.settings.base_interval, self.settings.min_interval, wrap=self.settings.wrap)
        self.ai = SnakeAI(self.snake, self.settings)
        self.fruits, self.hp, self.dmg_cd, self.last_spawn, self.elapsed = [], MAX_HP, {}, time.time(), 0.0
        self.flash, self.snake_ate, self.players_destroyed = {}, 0, 0
        self._spawn(engine, self.settings.min_fruits + 1)

    def _spawn(self, engine, n):
        players = engine.get_held_xy()
        blocked = self.snake.body_set() | {(f.x, f.y) for f in self.fruits}
        for _ in range(n):
            pos = _pick_spawn(players, blocked, BOARD_WIDTH, PLAY_Y_MIN, PLAY_Y_MAX)
            if not pos: break
            self.fruits.append(Fruit(pos[0], pos[1], _rand_fruit_type(self.settings)))
            blocked.add(pos)

    def update(self, engine, dt):
        self.elapsed += dt
        engine.clear()
        now = time.time()

        # Input: stomping fruits
        before = sum(1 for f in self.fruits if f.alive)
        for px, py in engine.get_pressed_xy():
            for fr in self.fruits:
                if fr.alive and fr.x == px and fr.y == py: fr.stomp()
        self.fruits = [f for f in self.fruits if f.alive]
        self.players_destroyed += before - len(self.fruits)

        # Snake movement
        self.snake.move_acc += dt
        while self.snake.move_acc >= self.snake.interval:
            self.snake.move_acc -= self.snake.interval
            nxt = self.ai.get_step(engine, self.fruits)
            if not nxt or self.snake.advance(nxt) == "self_collide":
                return ("end", {"play_time": self.elapsed, "snake_ate": self.snake_ate, "players_destroyed": self.players_destroyed, "reason": "self_collide"})

            for fr in self.fruits:
                if fr.alive and fr.x == self.snake.head[0] and fr.y == self.snake.head[1]:
                    self.snake.feed(fr.max_hp)
                    fr.alive, self.snake_ate = False, self.snake_ate + 1
            self.fruits = [f for f in self.fruits if f.alive]

        # Player damage
        sset, touched = self.snake.body_set(), False
        for px, py in engine.get_held_xy():
            if (px, py) in sset:
                if now - self.dmg_cd.get((px, py), 0.0) > DMG_COOLDOWN:
                    self.hp, self.dmg_cd[(px, py)], self.flash[(px, py)], touched = self.hp - DAMAGE, now, 0.4, True
        if touched: self.snake.touch()
        self.settings.hp = self.hp
        if self.hp <= 0: return ("end", {"play_time": self.elapsed, "snake_ate": self.snake_ate, "players_destroyed": self.players_destroyed, "reason": "hp_lost"})
        if self.snake.try_shrink(): return ("end", {"play_time": self.elapsed, "snake_ate": self.snake_ate, "players_destroyed": self.players_destroyed, "reason": "starved"})

        # Spawn maintenance
        if len(self.fruits) < self.settings.min_fruits or now - self.last_spawn > self.settings.spawn_interval:
            self._spawn(engine, max(1, self.settings.min_fruits - len(self.fruits)))
            self.last_spawn = now

        # Draw
        for fr in self.fruits: engine.set_pixel(fr.x, fr.y, *fr.draw_color())
        for i, (sx, sy) in enumerate(self.snake.body): engine.set_pixel(sx, sy, *self.snake.seg_color(i))
        for k, v in list(self.flash.items()):
            if v > 0:
                self.flash[k] -= dt
                if int(self.elapsed * 10) % 2 == 0: engine.set_pixel(k[0], k[1], *RED)
            else: del self.flash[k]

    def exit(self, engine): pass
