"""
Πthon Arena - Game Logic (runs on server)
"""

import random
import time
from protocol import (
    GRID_W, GRID_H, INITIAL_HEALTH, MAX_HEALTH, GAME_DURATION,
    PIE_TYPES, OBSTACLE_TYPES, MAX_PIES, NUM_OBSTACLES, TICK_RATE,
)


class Snake:
    def __init__(self, player_id: int, start_pos: tuple, start_dir: str):
        self.player_id = player_id
        self.body = [start_pos]        # list of (x,y), head first
        self.direction = start_dir     # "UP","DOWN","LEFT","RIGHT"
        self.pending_dir = start_dir
        self.health = INITIAL_HEALTH
        self.alive = True
        self.grow = 2                  # start with length 3

    def set_direction(self, new_dir: str):
        opposites = {"UP": "DOWN", "DOWN": "UP", "LEFT": "RIGHT", "RIGHT": "LEFT"}
        if new_dir != opposites.get(self.direction):
            self.pending_dir = new_dir

    def step(self):
        """Advance one cell. Returns new head position."""
        self.direction = self.pending_dir
        hx, hy = self.body[0]
        dx, dy = {"UP": (0,-1), "DOWN": (0,1), "LEFT": (-1,0), "RIGHT": (1,0)}[self.direction]
        new_head = (hx + dx, hy + dy)
        self.body.insert(0, new_head)
        if self.grow > 0:
            self.grow -= 1
        else:
            self.body.pop()
        return new_head

    def to_dict(self):
        return {
            "player_id": self.player_id,
            "body": self.body,
            "direction": self.direction,
            "health": self.health,
            "alive": self.alive,
        }


class GameState:
    def __init__(self, usernames: list):
        self.usernames = usernames           # [p0_name, p1_name]
        self.start_time = time.time()
        self.running = True
        self.winner = None
        self.tick_count = 0

        # Spawn snakes far apart
        s0 = Snake(0, (5, GRID_H // 2), "RIGHT")
        s1 = Snake(1, (GRID_W - 6, GRID_H // 2), "LEFT")
        self.snakes = [s0, s1]

        # Generate obstacles (avoid snake start areas)
        self.obstacles = self._gen_obstacles()

        # Pies: list of {"pos":(x,y),"kind":str}
        self.pies = []
        for _ in range(MAX_PIES):
            self._spawn_pie()

    # ── internal helpers ────────────────────────────────────────────────────────
    def _occupied(self):
        cells = set()
        for s in self.snakes:
            cells.update(s.body)
        cells.update(o["pos"] for o in self.obstacles)
        cells.update(p["pos"] for p in self.pies)
        return cells

    def _rand_free(self):
        occupied = self._occupied()
        attempts = 0
        while attempts < 500:
            pos = (random.randint(1, GRID_W - 2), random.randint(1, GRID_H - 2))
            if pos not in occupied:
                return pos
            attempts += 1
        return None

    def _gen_obstacles(self):
        obstacles = []
        kinds = list(OBSTACLE_TYPES.keys())
        safe = {(x, y) for x in range(3, 9) for y in range(GRID_H // 2 - 2, GRID_H // 2 + 3)}
        safe |= {(x, y) for x in range(GRID_W - 9, GRID_W - 2) for y in range(GRID_H // 2 - 2, GRID_H // 2 + 3)}
        attempts = 0
        while len(obstacles) < NUM_OBSTACLES and attempts < 1000:
            pos = (random.randint(1, GRID_W - 2), random.randint(1, GRID_H - 2))
            if pos not in safe:
                obstacles.append({"pos": pos, "kind": random.choice(kinds)})
                safe.add(pos)
            attempts += 1
        return obstacles

    def _spawn_pie(self):
        pos = self._rand_free()
        if pos:
            kind = random.choices(
                list(PIE_TYPES.keys()),
                weights=[1, 3, 1],   # golden:normal:rotten = 1:3:1
            )[0]
            self.pies.append({"pos": pos, "kind": kind})

    # ── main tick ───────────────────────────────────────────────────────────────
    def tick(self):
        """Advance game by one tick. Returns list of events."""
        if not self.running:
            return []

        self.tick_count += 1
        events = []

        # Check time limit
        elapsed = time.time() - self.start_time
        if elapsed >= GAME_DURATION:
            self._end_by_time()
            events.append({"kind": "time_up"})
            return events

        obstacle_cells = {o["pos"] for o in self.obstacles}
        pie_map = {p["pos"]: p for p in self.pies}

        new_heads = []
        for snake in self.snakes:
            if snake.alive:
                new_heads.append(snake.step())
            else:
                new_heads.append(None)

        # Collision detection
        all_bodies = []
        for snake in self.snakes:
            all_bodies.extend(snake.body)

        for i, snake in enumerate(self.snakes):
            if not snake.alive:
                continue

            # Wall wrap-around — teleport to opposite side, no damage
            hx, hy = snake.body[0]
            wx, wy = hx % GRID_W, hy % GRID_H
            if (wx, wy) != (hx, hy):
                snake.body[0] = (wx, wy)
                events.append({"kind": "wrap", "player": i})

            # Re-read after potential wrap
            hx, hy = snake.body[0]

            # Obstacle collision
            if snake.body[0] in obstacle_cells:
                snake.health -= 20
                snake.body[0] = snake.body[1] if len(snake.body) > 1 else snake.body[0]
                events.append({"kind": "collision", "player": i, "type": "obstacle"})

            # Self collision
            elif snake.body[0] in snake.body[1:]:
                snake.health -= 10
                events.append({"kind": "collision", "player": i, "type": "self"})

            # Snake vs snake collision
            other = self.snakes[1 - i]
            if other.alive and snake.body[0] in other.body:
                snake.health -= 25
                events.append({"kind": "collision", "player": i, "type": "snake"})

            # Pie collection
            if snake.body[0] in pie_map:
                pie = pie_map[snake.body[0]]
                delta = PIE_TYPES[pie["kind"]]["delta"]
                snake.health = max(0, min(MAX_HEALTH, snake.health + delta))
                self.pies.remove(pie)
                self._spawn_pie()
                snake.grow += 1
                events.append({"kind": "pie", "player": i, "pie_kind": pie["kind"], "delta": delta})

            # Death check
            if snake.health <= 0:
                snake.health = 0
                snake.alive = False
                winner_idx = 1 - i
                self.winner = self.usernames[winner_idx]
                self.running = False
                events.append({"kind": "death", "player": i})

        return events

    def _end_by_time(self):
        self.running = False
        h0 = self.snakes[0].health
        h1 = self.snakes[1].health
        if h0 > h1:
            self.winner = self.usernames[0]
        elif h1 > h0:
            self.winner = self.usernames[1]
        else:
            self.winner = "draw"

    def time_left(self):
        return max(0, GAME_DURATION - (time.time() - self.start_time))

    def to_dict(self):
        return {
            "type": "GAME_STATE",
            "snakes": [s.to_dict() for s in self.snakes],
            "pies": self.pies,
            "obstacles": self.obstacles,
            "usernames": self.usernames,
            "time_left": round(self.time_left(), 1),
            "running": self.running,
            "winner": self.winner,
            "tick": self.tick_count,
        }