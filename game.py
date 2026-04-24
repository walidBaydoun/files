"""
Pithon Arena - Game Logic (server-side)
Mutation pies: Hot Sauce, Whipped Cream, Blueberry
"""

import random
import time
from protocol import (
    GRID_W, GRID_H, INITIAL_HEALTH, MAX_HEALTH, GAME_DURATION,
    PIE_TYPES, OBSTACLE_TYPES, MAX_PIES, NUM_OBSTACLES, TICK_RATE,
)

# ── Mutation constants ─────────────────────────────────────────────────────────
FIRE_DURATION     = 50      # ticks fire trail stays alive (~5s at 10 tps)
FIRE_DAMAGE       = 15      # HP lost when stepping on fire
INVIS_DURATION    = 30      # ticks of invisibility (~3s)
SPLOTCH_DURATION  = 40      # ticks a splotch lasts
SPLOTCH_SLOW_TICKS= 20      # ticks of slow applied when stepping on splotch
SHIELD_ABSORBS    = 1       # hits absorbed by blueberry shield


class Snake:
    def __init__(self, player_id: int, start_pos: tuple, start_dir: str, color: list = None):
        self.player_id    = player_id
        self.body         = [start_pos]
        self.direction    = start_dir
        self.pending_dir  = start_dir
        self.health       = INITIAL_HEALTH
        self.alive        = True
        self.grow         = 2
        self.color        = color or ([0,220,120] if player_id==0 else [255,50,90])

        # ── Mutations ──────────────────────────────────────────────────────────
        self.fire_active  = False   # leaving fire trail this turn?
        self.fire_ticks   = 0       # ticks of fire trail remaining
        self.invisible    = False
        self.invis_ticks  = 0
        self.shield       = False
        self.slow_ticks   = 0
        self._slow_skip   = False   # alternates each tick while slowed
        self.active_mutation = None  # "hotsauce"|"whipped"|"blueberry"|None

        # ── Stats ──────────────────────────────────────────────────────────────
        self.stat_pies      = 0   # pies collected
        self.stat_mutations = 0   # mutations activated
        self.stat_dmg_dealt = 0   # damage dealt to opponent
        self.stat_max_len   = 1   # longest body length

    def set_direction(self, new_dir: str):
        opposites = {"UP":"DOWN","DOWN":"UP","LEFT":"RIGHT","RIGHT":"LEFT"}
        if new_dir != opposites.get(self.direction):
            self.pending_dir = new_dir

    def step(self):
        """Advance one cell. Returns (moved: bool, new_head: tuple)."""
        # Slow: skip every other tick
        if self.slow_ticks > 0:
            self.slow_ticks -= 1
            self._slow_skip = not self._slow_skip
            if self._slow_skip:
                return False, self.body[0]   # skip this tick

        self.direction = self.pending_dir
        hx, hy = self.body[0]
        dx, dy = {"UP":(0,-1),"DOWN":(0,1),"LEFT":(-1,0),"RIGHT":(1,0)}[self.direction]
        new_head = ((hx+dx) % GRID_W, (hy+dy) % GRID_H)
        self.body.insert(0, new_head)
        if self.grow > 0:
            self.grow -= 1
        else:
            self.body.pop()

        # Tick down mutations
        if self.invis_ticks > 0:
            self.invis_ticks -= 1
            self.invisible = self.invis_ticks > 0
        if self.fire_ticks > 0:
            self.fire_ticks -= 1
            self.fire_active = self.fire_ticks > 0

        return True, new_head

    def apply_damage(self, amount: int) -> bool:
        """Apply damage. If shielded, absorb it. Returns True if damage landed."""
        if self.shield:
            self.shield = False
            return False   # absorbed
        self.health = max(0, self.health - amount)
        return True

    def to_dict(self):
        return {
            "player_id":  self.player_id,
            "body":       self.body,
            "direction":  self.direction,
            "health":     self.health,
            "alive":      self.alive,
            "shield":     self.shield,
            "invisible":  self.invisible,
            "slow":       self.slow_ticks > 0,
            "mutation":   self.active_mutation,
            "color":      self.color,
        }


class GameState:
    def __init__(self, usernames: list, colors: list = None):
        self.usernames  = usernames
        self.start_time = time.time()
        self.running    = True
        self.winner     = None
        self.tick_count = 0

        colors = colors or [[0,220,120],[255,50,90]]
        s0 = Snake(0, (5, GRID_H//2), "RIGHT", colors[0])
        s1 = Snake(1, (GRID_W-6, GRID_H//2), "LEFT", colors[1])
        self.snakes = [s0, s1]

        # ── Effect cells ──────────────────────────────────────────────────────
        self.fire_cells    = []
        self.splotch_cells = []

        self.obstacles = self._gen_obstacles()
        self.pies      = []
        for _ in range(MAX_PIES):
            self._spawn_pie()

    # ── helpers ───────────────────────────────────────────────────────────────
    def _occupied(self):
        cells = set()
        for s in self.snakes:     cells.update(s.body)
        for o in self.obstacles:  cells.add(o["pos"])
        for p in self.pies:       cells.add(p["pos"])
        for f in self.fire_cells: cells.add(f["pos"])
        return cells

    def _rand_free(self):
        occ = self._occupied()
        for _ in range(500):
            pos = (random.randint(1, GRID_W-2), random.randint(1, GRID_H-2))
            if pos not in occ:
                return pos
        return None

    def _gen_obstacles(self):
        obstacles = []
        kinds = list(OBSTACLE_TYPES.keys())
        safe  = {(x,y) for x in range(3,9)       for y in range(GRID_H//2-2, GRID_H//2+3)}
        safe |= {(x,y) for x in range(GRID_W-9,GRID_W-2) for y in range(GRID_H//2-2, GRID_H//2+3)}
        attempts = 0
        while len(obstacles) < NUM_OBSTACLES and attempts < 1000:
            pos = (random.randint(1,GRID_W-2), random.randint(1,GRID_H-2))
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
                weights=[2, 2, 2],   # equal weight
            )[0]
            self.pies.append({"pos": pos, "kind": kind})

    # ── main tick ─────────────────────────────────────────────────────────────
    def tick(self):
        if not self.running:
            return []

        self.tick_count += 1
        events = []

        # Time limit
        if time.time() - self.start_time >= GAME_DURATION:
            self._end_by_time()
            events.append({"kind":"time_up"})
            return events

        # Age effect cells
        self.fire_cells    = [f for f in self.fire_cells    if f["ticks"] > 0]
        self.splotch_cells = [s for s in self.splotch_cells if s["ticks"] > 0]
        for f in self.fire_cells:    f["ticks"] -= 1
        for s in self.splotch_cells: s["ticks"] -= 1

        obstacle_cells = {o["pos"] for o in self.obstacles}
        pie_map        = {p["pos"]: p for p in self.pies}
        fire_map       = {}   # pos -> owner pid
        for f in self.fire_cells:
            fire_map[f["pos"]] = f["owner"]
        splotch_set    = {s["pos"] for s in self.splotch_cells}

        # ── Move snakes ───────────────────────────────────────────────────────
        prev_tails = []
        for snake in self.snakes:
            prev_tails.append(snake.body[-1] if snake.body else None)

        moved_flags = []
        for snake in self.snakes:
            if snake.alive:
                moved, _ = snake.step()
                moved_flags.append(moved)
                # Deposit fire trail at new head if active
                if moved and snake.fire_active:
                    # Leave fire at the cell just vacated (second segment)
                    if len(snake.body) > 1:
                        trail_pos = snake.body[1]
                        if not any(f["pos"]==trail_pos for f in self.fire_cells):
                            self.fire_cells.append({"pos":trail_pos,"owner":snake.player_id,"ticks":FIRE_DURATION})
                # Deposit splotch while invisible
                if moved and snake.invisible and self.tick_count % 3 == 0:
                    if not any(s["pos"]==snake.body[0] for s in self.splotch_cells):
                        self.splotch_cells.append({"pos":snake.body[0],"ticks":SPLOTCH_DURATION})
            else:
                moved_flags.append(False)

        # Rebuild fire_map after deposition
        fire_map = {}
        for f in self.fire_cells:
            fire_map[f["pos"]] = f["owner"]

        # ── Collision detection ───────────────────────────────────────────────
        for i, snake in enumerate(self.snakes):
            if not snake.alive or not moved_flags[i]:
                continue

            head = snake.body[0]

            # Splotch — apply slow
            if head in splotch_set:
                snake.slow_ticks = max(snake.slow_ticks, SPLOTCH_SLOW_TICKS)
                # Remove hit splotch
                self.splotch_cells = [s for s in self.splotch_cells if s["pos"] != head]
                events.append({"kind":"splotch","player":i})

            # Fire trail — only damages opponent
            if head in fire_map and fire_map[head] != i:
                landed = snake.apply_damage(FIRE_DAMAGE)
                if landed:
                    # Credit damage to the fire owner
                    self.snakes[fire_map[head]].stat_dmg_dealt += FIRE_DAMAGE
                    events.append({"kind":"fire_damage","player":i,"damage":FIRE_DAMAGE})

            # Obstacle collision
            if head in obstacle_cells:
                landed = snake.apply_damage(20)
                if landed:
                    events.append({"kind":"collision","player":i,"type":"obstacle"})
                else:
                    events.append({"kind":"shield_block","player":i,"type":"obstacle"})
                snake.body[0] = snake.body[1] if len(snake.body)>1 else head

            # Self collision
            elif head in snake.body[1:]:
                snake.apply_damage(10)
                events.append({"kind":"collision","player":i,"type":"self"})

            # Snake vs snake
            other = self.snakes[1-i]
            if other.alive and head in other.body:
                landed = snake.apply_damage(25)
                if landed:
                    other.stat_dmg_dealt += 25
                    events.append({"kind":"collision","player":i,"type":"snake"})
                else:
                    events.append({"kind":"shield_block","player":i,"type":"snake"})

            # Pie collection
            if head in pie_map:
                pie  = pie_map[head]
                kind = pie["kind"]
                self._apply_mutation(snake, kind, events, i)
                self.pies.remove(pie)
                self._spawn_pie()
                snake.grow += 1
                snake.stat_pies += 1
                snake.stat_max_len = max(snake.stat_max_len, len(snake.body))

            # Death check
            if snake.health <= 0:
                snake.health = 0
                snake.alive  = False
                self.winner  = self.usernames[1-i]
                self.running = False
                events.append({"kind":"death","player":i})

        return events

    def _apply_mutation(self, snake: Snake, kind: str, events: list, pid: int):
        snake.active_mutation = kind
        snake.stat_mutations += 1
        if kind == "hotsauce":
            snake.fire_ticks  = FIRE_DURATION
            snake.fire_active = True
            events.append({"kind":"mutation","player":pid,"mutation":"hotsauce"})
        elif kind == "whipped":
            snake.invis_ticks = INVIS_DURATION
            snake.invisible   = True
            events.append({"kind":"mutation","player":pid,"mutation":"whipped"})
        elif kind == "blueberry":
            snake.shield = True
            events.append({"kind":"mutation","player":pid,"mutation":"blueberry"})

    def stats_dict(self):
        result = {}
        for sn in self.snakes:
            result[self.usernames[sn.player_id]] = {
                "pies":      sn.stat_pies,
                "mutations": sn.stat_mutations,
                "dmg_dealt": sn.stat_dmg_dealt,
                "max_len":   sn.stat_max_len,
            }
        return result

    def _end_by_time(self):
        self.running = False
        h0 = self.snakes[0].health
        h1 = self.snakes[1].health
        if h0 > h1:   self.winner = self.usernames[0]
        elif h1 > h0: self.winner = self.usernames[1]
        else:         self.winner = "draw"

    def time_left(self):
        return max(0, GAME_DURATION - (time.time()-self.start_time))

    def to_dict(self):
        return {
            "type":        "GAME_STATE",
            "snakes":      [s.to_dict() for s in self.snakes],
            "pies":        self.pies,
            "obstacles":   self.obstacles,
            "fire_cells":  [{"pos":f["pos"],"owner":f["owner"],"ticks":f["ticks"]} for f in self.fire_cells],
            "splotches":   [{"pos":s["pos"],"ticks":s["ticks"]} for s in self.splotch_cells],
            "usernames":   self.usernames,
            "time_left":   round(self.time_left(),1),
            "running":     self.running,
            "winner":      self.winner,
            "tick":        self.tick_count,
        }