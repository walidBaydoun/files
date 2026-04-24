"""
Πthon Arena - Server
Usage: python server.py <port>
"""

import sys
import socket
import threading
import time
import traceback
import json

from protocol import *
from game import GameState, TICK_RATE


class ClientHandler:
    def __init__(self, conn: socket.socket, addr, server):
        self.conn = conn
        self.addr = addr
        self.server: "ArenaServer" = server
        self.username: str | None = None
        self.role: str = "lobby"  # "lobby" | "player" | "fan"
        self.player_id: int | None = None  # 0 or 1 if player
        self.color: list = [0, 220, 120]  # default green
        self.stats: dict = {"wins": 0, "losses": 0, "streak": 0}
        self._buf = b""
        self._lock = threading.Lock()

    # ── I/O ────────────────────────────────────────────────────────────────────
    def send(self, msg: dict):
        try:
            with self._lock:
                self.conn.sendall((json.dumps(msg) + "\n").encode("utf-8"))
        except Exception:
            self.server.remove_client(self)

    def _readline(self) -> bytes | None:
        """Read until newline from buffer."""
        while b"\n" not in self._buf:
            try:
                chunk = self.conn.recv(4096)
            except Exception:
                return None
            if not chunk:
                return None
            self._buf += chunk
        line, self._buf = self._buf.split(b"\n", 1)
        return line

    # ── Main loop ──────────────────────────────────────────────────────────────
    def run(self):
        try:
            self._handle()
        except Exception:
            traceback.print_exc()
        finally:
            self.server.remove_client(self)
            try:
                self.conn.close()
            except Exception:
                pass

    def _handle(self):
        while True:
            line = self._readline()
            if line is None:
                break
            try:
                msg = json.loads(line.decode("utf-8"))
            except Exception:
                continue
            self._dispatch(msg)

    def _dispatch(self, msg: dict):
        t = msg.get("type")
        if t == MSG_PING:
            self.send({"type": MSG_PONG})
        elif t == MSG_JOIN:
            self._on_join(msg)
        elif t == MSG_WATCH:
            self._on_watch()
        elif t == MSG_INPUT:
            self._on_input(msg)
        elif t == MSG_CHAT:
            self._on_chat(msg)
        elif t == MSG_CHEER:
            self._on_cheer(msg)
        elif t == MSG_REMATCH:
            self.server.handle_rematch(self)
        elif t == MSG_LEAVE:
            self._on_leave()
        elif t == MSG_READY:
            self.server.handle_ready(self, True)
        elif t == MSG_UNREADY:
            self.server.handle_ready(self, False)
        elif t == MSG_SET_COLOR:
            col = msg.get("color", [0, 220, 120])
            if isinstance(col, list) and len(col) == 3:
                self.color = [max(0, min(255, int(c))) for c in col]
        elif t == MSG_SHARE_STATS:
            self.stats = {
                "wins": int(msg.get("wins", 0)),
                "losses": int(msg.get("losses", 0)),
                "streak": int(msg.get("streak", 0)),
            }
            self.server.broadcast_player_list()

    # ── Handlers ───────────────────────────────────────────────────────────────
    def _on_join(self, msg: dict):
        name = str(msg.get("username", "")).strip()
        if not name:
            self.send({"type": MSG_JOIN_ERR, "reason": "Username cannot be empty."})
            return
        if not self.server.register_username(name, self):
            self.send(
                {"type": MSG_JOIN_ERR, "reason": f"Username '{name}' is already taken."}
            )
            return
        self.username = name
        self.role = "lobby"
        self.send({"type": MSG_JOIN_OK, "username": name})
        self.server.broadcast_player_list()

    def _on_watch(self):
        if self.username and self.role == "lobby":
            self.role = "fan"
            self.send({"type": MSG_WATCH_OK})
            # Send current game state snapshot if game is running
            gs = self.server.game_state
            if gs:
                self.send(gs.to_dict())

    def _on_input(self, msg: dict):
        if self.role != "player" or self.player_id is None:
            return
        direction = msg.get("direction", "")
        if direction in ("UP", "DOWN", "LEFT", "RIGHT"):
            gs = self.server.game_state
            if gs and gs.running:
                gs.snakes[self.player_id].set_direction(direction)

    def _on_chat(self, msg: dict):
        if not self.username:
            return
        text = str(msg.get("text", "")).strip()[:300]
        if not text:
            return
        to = msg.get("to")  # None = public, str = private username
        payload = {"type": MSG_CHAT_RECV, "from": self.username, "text": text}
        if to:
            # P2P: deliver to target only
            payload["private"] = True
            target = self.server.get_client_by_name(to)
            if target:
                target.send(payload)
            self.send(payload)  # echo to self
        else:
            payload["private"] = False
            self.server.broadcast(payload)

    def _on_leave(self):
        """Player or fan voluntarily returns to lobby."""
        if self.role in ("player", "fan"):
            self.role = "lobby"
            self.player_id = None
            self.server.handle_ready(self, False)
            self.server.broadcast_player_list()

    def _on_cheer(self, msg: dict):
        if not self.username or self.role != "fan":
            return
        emoji = str(msg.get("emoji", "🐍"))[:4]
        player = str(msg.get("player", ""))
        payload = {
            "type": MSG_CHEER_RECV,
            "from": self.username,
            "player": player,
            "emoji": emoji,
        }
        self.server.broadcast(payload)


class ArenaServer:
    def __init__(self, port: int):
        self.port = port
        self._clients: list[ClientHandler] = []
        self._lock = threading.Lock()
        self._usernames: dict[str, ClientHandler] = {}
        self.game_state: GameState | None = None
        self._game_thread: threading.Thread | None = None
        self._rematch_votes: set = set()
        self._ready_queue: list[ClientHandler] = []  # ordered — first two get matched

    # ── Client registry ────────────────────────────────────────────────────────
    def register_username(self, name: str, client: ClientHandler) -> bool:
        with self._lock:
            if name in self._usernames:
                return False
            self._usernames[name] = client
            if client not in self._clients:
                self._clients.append(client)
            return True

    def remove_client(self, client: ClientHandler):
        with self._lock:
            if client in self._clients:
                self._clients.remove(client)
            if client.username and self._usernames.get(client.username) is client:
                del self._usernames[client.username]
        self.handle_ready(client, False)
        print(f"[server] {client.username or client.addr} disconnected.")
        self.broadcast_player_list()

    def get_client_by_name(self, name: str) -> ClientHandler | None:
        with self._lock:
            return self._usernames.get(name)

    # ── Broadcast helpers ──────────────────────────────────────────────────────
    def broadcast(self, msg: dict, targets=None):
        with self._lock:
            clients = list(self._clients) if targets is None else targets
        for c in clients:
            c.send(msg)

    def broadcast_player_list(self):
        with self._lock:
            players = [
                {
                    "name": c.username,
                    "wins": c.stats.get("wins", 0),
                    "losses": c.stats.get("losses", 0),
                    "streak": c.stats.get("streak", 0),
                    "color": c.color,
                }
                for c in self._clients
                if c.username and c.role == "lobby"
            ]
        self.broadcast({"type": MSG_PLAYER_LIST, "players": players})

    def broadcast_game_state(self):
        if self.game_state:
            msg = self.game_state.to_dict()
            with self._lock:
                targets = [c for c in self._clients if c.role in ("player", "fan")]
                fan_count = sum(1 for c in self._clients if c.role == "fan")
            msg["fan_count"] = fan_count
            for c in targets:
                c.send(msg)

    # ── Game lifecycle ─────────────────────────────────────────────────────────
    def try_start_game(self):
        """Start a game with the first two ready players."""
        if self.game_state and self.game_state.running:
            return
        with self._lock:
            ready = [c for c in self._ready_queue if c.role == "lobby" and c.username]
        if len(ready) < 2:
            return
        p0, p1 = ready[0], ready[1]
        # Remove them from ready queue
        with self._lock:
            for p in (p0, p1):
                if p in self._ready_queue:
                    self._ready_queue.remove(p)
        p0.role, p1.role = "player", "player"
        p0.player_id, p1.player_id = 0, 1
        self._rematch_votes.clear()
        self.game_state = GameState([p0.username, p1.username], [p0.color, p1.color])
        config = {
            "grid_w": 30,
            "grid_h": 22,
            "usernames": [p0.username, p1.username],
            "colors": [p0.color, p1.color],
        }
        p0.send({"type": MSG_GAME_START, "your_id": 0, "config": config})
        p1.send({"type": MSG_GAME_START, "your_id": 1, "config": config})
        print(f"[server] Game starting: {p0.username} vs {p1.username}")
        # Broadcast updated ready status (those two are no longer ready)
        with self._lock:
            names = [c.username for c in self._ready_queue if c.username]
        payload = {"type": MSG_READY_STATUS, "ready": names, "count": len(names)}
        with self._lock:
            targets = list(self._clients)
        for c in targets:
            c.send(payload)
        self._game_thread = threading.Thread(target=self._game_loop, daemon=True)
        self._game_thread.start()

    def _broadcast_countdown(self, count: int):
        msg = {"type": MSG_COUNTDOWN, "count": count}
        with self._lock:
            targets = [c for c in self._clients if c.role in ("player", "fan")]
        for c in targets:
            c.send(msg)

    def _game_loop(self):
        interval = 1.0 / TICK_RATE
        gs = self.game_state

        # 3-second countdown
        for i in (3, 2, 1, 0):
            self._broadcast_countdown(i)
            if i > 0:
                time.sleep(1)

        while gs.running:
            t0 = time.time()
            gs.tick()
            self.broadcast_game_state()
            elapsed = time.time() - t0
            time.sleep(max(0, interval - elapsed))

        # Game over
        self.broadcast_game_state()
        over_msg = {
            "type": MSG_GAME_OVER,
            "winner": gs.winner,
            "scores": {
                gs.usernames[0]: gs.snakes[0].health,
                gs.usernames[1]: gs.snakes[1].health,
            },
            "stats": gs.stats_dict(),
        }
        self.broadcast(over_msg)
        print(f"[server] Game over. Winner: {gs.winner}")

        # Reset roles for players AND fans so everyone returns to lobby
        with self._lock:
            for c in self._clients:
                if c.role in ("player", "fan"):
                    c.role = "lobby"
                    c.player_id = None
            self._ready_queue.clear()
        self.broadcast_player_list()

    def handle_ready(self, client: ClientHandler, ready: bool):
        """Add or remove a client from the ready queue and broadcast status."""
        with self._lock:
            if ready:
                if (
                    client not in self._ready_queue
                    and client.role == "lobby"
                    and client.username
                ):
                    self._ready_queue.append(client)
            else:
                if client in self._ready_queue:
                    self._ready_queue.remove(client)
            queue_snapshot = list(self._ready_queue)

        # Broadcast ready status to everyone in lobby
        names = [c.username for c in queue_snapshot if c.username]
        payload = {"type": MSG_READY_STATUS, "ready": names, "count": len(names)}
        with self._lock:
            targets = [c for c in self._clients if c.username]
        for c in targets:
            c.send(payload)

        # If 2+ players are ready, start a game with the first two
        if len(queue_snapshot) >= 2:
            self.try_start_game()

    def handle_rematch(self, client: ClientHandler):
        if client.username:
            self._rematch_votes.add(client.username)
            gs = self.game_state
            if gs and len(self._rematch_votes) >= 2:
                if all(n in self._rematch_votes for n in gs.usernames):
                    # Reset both players' roles to "lobby" and add to ready queue
                    with self._lock:
                        for c in self._clients:
                            if c.username in gs.usernames:
                                c.role = "lobby"
                                c.player_id = None
                                if c not in self._ready_queue:
                                    self._ready_queue.append(c)
                    self.try_start_game()

    # ── Main server loop ───────────────────────────────────────────────────────
    def start(self):
        srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        srv.bind(("", self.port))
        srv.listen(16)
        print(f"[server] Πthon Arena listening on port {self.port}")
        while True:
            conn, addr = srv.accept()
            print(f"[server] Connection from {addr}")
            handler = ClientHandler(conn, addr, self)
            with self._lock:
                self._clients.append(handler)
            t = threading.Thread(target=handler.run, daemon=True)
            t.start()


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python server.py <port>")
        sys.exit(1)
    port = int(sys.argv[1])
    ArenaServer(port).start()
