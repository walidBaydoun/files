"""
Πthon Arena - Client
Usage: python client.py
"""

import sys
import socket
import threading
import queue
import time

import pygame
import pygame.font

from protocol import *

# ── Display constants ──────────────────────────────────────────────────────────
CELL      = 24
SIDEBAR   = 300
WIN_W     = GRID_W * CELL + SIDEBAR
WIN_H     = GRID_H * CELL + 60          # +60 for top bar
TOP_H     = 60
FPS       = 60

# Color palette
C_BG      = (15,  15,  25)
C_GRID    = (25,  25,  40)
C_WALL    = (50,  50,  80)
C_P0      = (0,   255, 127)   # spring green
C_P1      = (255, 99,  71)    # tomato red
C_P0_D    = (0,   180, 90)
C_P1_D    = (200, 60,  40)
C_GOLDEN  = (255, 215, 0)
C_NORMAL  = (255, 140, 0)
C_ROTTEN  = (85,  107, 47)
C_ROCK    = (120, 120, 130)
C_SPIKE   = (180, 180, 200)
C_TEXT    = (220, 220, 240)
C_ACCENT  = (100, 200, 255)
C_PANEL   = (20,  20,  35)
C_INPUT   = (30,  30,  50)
C_BORDER  = (60,  60,  100)
C_CHAT_MY = (80,  160, 255)
C_CHAT_OT = (180, 180, 200)
C_CHEER   = (255, 220, 80)
C_ERR     = (255, 80,  80)
C_OK      = (80,  220, 80)
C_HEALTH0 = (0,   220, 100)
C_HEALTH1 = (255, 80,  80)
C_DEAD    = (80,  80,  80)

PIE_COLORS = {
    "golden": C_GOLDEN,
    "normal": C_NORMAL,
    "rotten": C_ROTTEN,
}
OBS_COLORS = {
    "rock":  C_ROCK,
    "spike": C_SPIKE,
}
PIE_SYMBOLS  = {"golden": "G", "normal": "●", "rotten": "✗"}
OBS_SYMBOLS  = {"rock": "▣", "spike": "⚡"}


# ── Screen states ──────────────────────────────────────────────────────────────
S_CONNECT   = "connect"
S_LOBBY     = "lobby"
S_GAME      = "game"
S_GAME_OVER = "game_over"


class NetworkThread(threading.Thread):
    def __init__(self, host, port, recv_q: queue.Queue):
        super().__init__(daemon=True)
        self.host = host
        self.port = port
        self.recv_q = recv_q
        self._sock: socket.socket | None = None
        self._send_q: queue.Queue = queue.Queue()
        self._buf = b""
        self._connected = False
        self._error: str | None = None

    def run(self):
        try:
            self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self._sock.connect((self.host, self.port))
            self._connected = True
            # Start sender thread
            sender = threading.Thread(target=self._sender, daemon=True)
            sender.start()
            self._receiver()
        except Exception as e:
            self._error = str(e)
            self.recv_q.put({"type": "_NET_ERROR", "reason": str(e)})

    def _receiver(self):
        while True:
            try:
                chunk = self._sock.recv(4096)
            except Exception:
                self.recv_q.put({"type": "_NET_ERROR", "reason": "Disconnected"})
                return
            if not chunk:
                self.recv_q.put({"type": "_NET_ERROR", "reason": "Server closed connection"})
                return
            self._buf += chunk
            while b"\n" in self._buf:
                line, self._buf = self._buf.split(b"\n", 1)
                try:
                    msg = decode(line + b"\n")
                    self.recv_q.put(msg)
                except Exception:
                    pass

    def _sender(self):
        while True:
            msg = self._send_q.get()
            if msg is None:
                break
            try:
                self._sock.sendall(encode(msg))
            except Exception:
                break

    def send(self, msg: dict):
        if self._connected:
            self._send_q.put(msg)


class TextInput:
    def __init__(self, rect, font, placeholder="", max_len=40, password=False):
        self.rect = rect
        self.font = font
        self.placeholder = placeholder
        self.max_len = max_len
        self.password = password
        self.text = ""
        self.active = False
        self.cursor_vis = True
        self._cursor_t = 0

    def handle_event(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN:
            self.active = self.rect.collidepoint(event.pos)
        if event.type == pygame.KEYDOWN and self.active:
            if event.key == pygame.K_BACKSPACE:
                self.text = self.text[:-1]
            elif event.key not in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_TAB):
                if len(self.text) < self.max_len:
                    self.text += event.unicode
            return event.key in (pygame.K_RETURN, pygame.K_KP_ENTER)
        return False

    def draw(self, surf):
        now = pygame.time.get_ticks()
        if now - self._cursor_t > 500:
            self.cursor_vis = not self.cursor_vis
            self._cursor_t = now

        border_c = C_ACCENT if self.active else C_BORDER
        pygame.draw.rect(surf, C_INPUT, self.rect, border_radius=6)
        pygame.draw.rect(surf, border_c, self.rect, 2, border_radius=6)

        display = ("*" * len(self.text)) if self.password else self.text
        if display:
            ts = self.font.render(display, True, C_TEXT)
        else:
            ts = self.font.render(self.placeholder, True, (80, 80, 120))

        surf.blit(ts, (self.rect.x + 10, self.rect.centery - ts.get_height() // 2))

        if self.active and self.cursor_vis and display is not None:
            cx = self.rect.x + 10 + self.font.size(display)[0]
            pygame.draw.line(surf, C_TEXT, (cx, self.rect.y + 6), (cx, self.rect.bottom - 6), 2)


def draw_rounded_rect(surf, color, rect, radius=8, border=0, border_color=None):
    pygame.draw.rect(surf, color, rect, border_radius=radius)
    if border and border_color:
        pygame.draw.rect(surf, border_color, rect, border, border_radius=radius)


def health_bar(surf, x, y, w, h, value, max_val, color):
    ratio = max(0, min(1, value / max_val))
    pygame.draw.rect(surf, (40, 40, 60), (x, y, w, h), border_radius=4)
    if ratio > 0:
        bar_color = color if ratio > 0.3 else C_ERR
        pygame.draw.rect(surf, bar_color, (x, y, int(w * ratio), h), border_radius=4)
    pygame.draw.rect(surf, C_BORDER, (x, y, w, h), 1, border_radius=4)


class PithonArenaClient:
    def __init__(self):
        pygame.init()
        pygame.display.set_caption("Πthon Arena")
        self.screen = pygame.display.set_mode((WIN_W, WIN_H), pygame.RESIZABLE)
        self.clock = pygame.time.Clock()

        # Fonts
        self.font_lg  = pygame.font.SysFont("monospace", 28, bold=True)
        self.font_md  = pygame.font.SysFont("monospace", 18)
        self.font_sm  = pygame.font.SysFont("monospace", 14)
        self.font_xs  = pygame.font.SysFont("monospace", 12)
        self.font_xl  = pygame.font.SysFont("monospace", 48, bold=True)

        # Network
        self.net: NetworkThread | None = None
        self.recv_q: queue.Queue = queue.Queue()

        # State
        self.state       = S_CONNECT
        self.username    = None
        self.player_id   = None        # 0 or 1 or None (fan)
        self.is_fan      = False
        self.game_cfg    = {}
        self.game_data   = None        # last GAME_STATE dict
        self.game_over   = None        # GAME_OVER dict
        self.online_list = []
        self.chat_log    = []          # list of (sender, text, private, color)
        self.cheers      = []          # list of (text, expire_time)
        self.net_error   = None

        # Key bindings (player uses arrow keys; configurable)
        self.key_map = {
            pygame.K_UP:    "UP",
            pygame.K_DOWN:  "DOWN",
            pygame.K_LEFT:  "LEFT",
            pygame.K_RIGHT: "RIGHT",
            pygame.K_w:     "UP",
            pygame.K_s:     "DOWN",
            pygame.K_a:     "LEFT",
            pygame.K_d:     "RIGHT",
        }
        self.last_dir = None

        # UI inputs
        self._init_connect_ui()
        self._init_lobby_ui()
        self._init_game_ui()

    # ── UI init helpers ────────────────────────────────────────────────────────
    def _init_connect_ui(self):
        cx = WIN_W // 2
        self.ui_host  = TextInput(pygame.Rect(cx - 160, 260, 320, 38), self.font_md, "Server IP", 64)
        self.ui_port  = TextInput(pygame.Rect(cx - 160, 320, 150, 38), self.font_md, "Port", 6)
        self.ui_uname = TextInput(pygame.Rect(cx - 160, 380, 320, 38), self.font_md, "Username", 20)
        self.ui_host.text  = "127.0.0.1"
        self.ui_port.text  = "5555"
        self.conn_err = ""
        self.conn_btn = pygame.Rect(cx - 80, 440, 160, 42)
        self._active_inputs = [self.ui_host, self.ui_port, self.ui_uname]

    def _init_lobby_ui(self):
        self.fan_btn     = pygame.Rect(WIN_W - SIDEBAR + 20, WIN_H - 100, SIDEBAR - 40, 36)
        self.rematch_btn = pygame.Rect(WIN_W // 2 - SIDEBAR // 2 - 110, WIN_H // 2 + 80, 200, 44)
        self.lobby_btn   = pygame.Rect(WIN_W // 2 - SIDEBAR // 2 + 110, WIN_H // 2 + 80, 200, 44)

    def _init_game_ui(self):
        sx = GRID_W * CELL + 10
        self.chat_input = TextInput(
            pygame.Rect(sx, WIN_H - 42, SIDEBAR - 20, 34),
            self.font_sm, "Chat... (Enter to send)", 150
        )
        # Cheer buttons
        self.cheer_emojis = ["🐍", "🔥", "💀", "👑", "🎉"]

    # ── Main loop ──────────────────────────────────────────────────────────────
    def run(self):
        while True:
            dt = self.clock.tick(FPS)
            self._process_net()
            self._handle_events()
            self._draw()
            pygame.display.flip()

    def _process_net(self):
        while not self.recv_q.empty():
            msg = self.recv_q.get_nowait()
            self._on_message(msg)

    def _on_message(self, msg: dict):
        t = msg.get("type")
        if t == "_NET_ERROR":
            self.net_error = msg.get("reason", "Network error")
            self.state = S_CONNECT
            self.conn_err = self.net_error

        elif t == MSG_JOIN_OK:
            self.username = msg["username"]
            self.state = S_LOBBY

        elif t == MSG_JOIN_ERR:
            self.conn_err = msg.get("reason", "Error")

        elif t == MSG_PLAYER_LIST:
            self.online_list = msg.get("players", [])
            # If server put us back in lobby (e.g. after leaving), switch screen
            if self.state == S_GAME_OVER and self.username in self.online_list:
                self._go_to_lobby()

        elif t == MSG_GAME_START:
            self.player_id = msg.get("your_id")
            self.game_cfg  = msg.get("config", {})
            self.is_fan    = False
            self.state     = S_GAME
            self.game_over = None
            self.game_data = None

        elif t == MSG_WATCH_OK:
            self.is_fan    = True
            self.state     = S_GAME
            self.game_over = None

        elif t == MSG_GAME_STATE:
            self.game_data = msg

        elif t == MSG_GAME_OVER:
            self.game_over = msg
            self.state     = S_GAME_OVER

        elif t == MSG_CHAT_RECV:
            sender  = msg.get("from", "?")
            text    = msg.get("text", "")
            private = msg.get("private", False)
            color   = C_CHAT_MY if sender == self.username else C_CHAT_OT
            tag     = "[PM] " if private else ""
            self.chat_log.append((sender, f"{tag}{text}", color))
            if len(self.chat_log) > 60:
                self.chat_log.pop(0)

        elif t == MSG_CHEER_RECV:
            frm   = msg.get("from", "?")
            emoji = msg.get("emoji", "🐍")
            player= msg.get("player", "")
            self.cheers.append((f"{frm}: {emoji} for {player}", time.time() + 3))

    # ── Event handling ─────────────────────────────────────────────────────────
    def _handle_events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()

            if self.state == S_CONNECT:
                self._handle_connect_event(event)
            elif self.state == S_LOBBY:
                self._handle_lobby_event(event)
            elif self.state == S_GAME:
                self._handle_game_event(event)
            elif self.state == S_GAME_OVER:
                self._handle_gameover_event(event)

    def _handle_connect_event(self, event):
        for inp in self._active_inputs:
            if inp.handle_event(event):
                # Enter pressed → connect
                self._do_connect()
        if event.type == pygame.MOUSEBUTTONDOWN:
            if self.conn_btn.collidepoint(event.pos):
                self._do_connect()

    def _handle_lobby_event(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN:
            if self.fan_btn.collidepoint(event.pos) and self.net:
                self.net.send({"type": MSG_WATCH})

    def _handle_game_event(self, event):
        # Chat input
        if self.chat_input.handle_event(event):
            txt = self.chat_input.text.strip()
            if txt and self.net:
                # Check if private: /pm username message
                if txt.startswith("/pm "):
                    parts = txt[4:].split(" ", 1)
                    if len(parts) == 2:
                        self.net.send({"type": MSG_CHAT, "to": parts[0], "text": parts[1]})
                else:
                    self.net.send({"type": MSG_CHAT, "to": None, "text": txt})
            self.chat_input.text = ""

        if event.type == pygame.MOUSEBUTTONDOWN:
            # Cheer buttons (fans only)
            if self.is_fan and self.game_data:
                usernames = self.game_data.get("usernames", [])
                for i, emoji in enumerate(self.cheer_emojis):
                    btn = self._cheer_btn_rect(i)
                    if btn.collidepoint(event.pos) and usernames:
                        # Cheer for whichever player index 0
                        self.net.send({
                            "type": MSG_CHEER,
                            "emoji": emoji,
                            "player": usernames[0],
                        })

        # Movement (players only)
        if event.type == pygame.KEYDOWN and not self.is_fan:
            if not self.chat_input.active:
                direction = self.key_map.get(event.key)
                if direction and direction != self.last_dir and self.net:
                    self.net.send({"type": MSG_INPUT, "direction": direction})
                    self.last_dir = direction

    def _handle_gameover_event(self, event):
        self.chat_input.handle_event(event)
        if event.type == pygame.KEYDOWN and event.key == pygame.K_RETURN:
            txt = self.chat_input.text.strip()
            if txt and self.net:
                self.net.send({"type": MSG_CHAT, "to": None, "text": txt})
            self.chat_input.text = ""
        if event.type == pygame.MOUSEBUTTONDOWN:
            if self.rematch_btn.collidepoint(event.pos) and self.net:
                self.net.send({"type": MSG_REMATCH})
            if self.lobby_btn.collidepoint(event.pos) and self.net:
                self.net.send({"type": MSG_LEAVE})
                self._go_to_lobby()

    # ── Networking ─────────────────────────────────────────────────────────────
    def _go_to_lobby(self):
        self.state     = S_LOBBY
        self.game_data = None
        self.game_over = None
        self.player_id = None
        self.is_fan    = False

    def _do_connect(self):
        host  = self.ui_host.text.strip()
        port  = self.ui_port.text.strip()
        uname = self.ui_uname.text.strip()
        if not host or not port or not uname:
            self.conn_err = "Fill in all fields."
            return
        try:
            port_n = int(port)
        except ValueError:
            self.conn_err = "Invalid port."
            return
        self.conn_err = "Connecting…"
        self.net = NetworkThread(host, port_n, self.recv_q)
        self.net.start()
        # Wait briefly then send join
        def _send_join():
            time.sleep(0.3)
            self.net.send({"type": MSG_JOIN, "username": uname})
        threading.Thread(target=_send_join, daemon=True).start()

    # ── Drawing ────────────────────────────────────────────────────────────────
    def _draw(self):
        self.screen.fill(C_BG)
        if self.state == S_CONNECT:
            self._draw_connect()
        elif self.state == S_LOBBY:
            self._draw_lobby()
        elif self.state == S_GAME:
            self._draw_game()
        elif self.state == S_GAME_OVER:
            self._draw_game()
            self._draw_game_over_overlay()

    # ── Connect screen ─────────────────────────────────────────────────────────
    def _draw_connect(self):
        cx = WIN_W // 2
        # Title
        title = self.font_xl.render("Πthon Arena", True, C_P0)
        self.screen.blit(title, (cx - title.get_width() // 2, 140))
        sub = self.font_md.render("Online Snake Battle", True, C_ACCENT)
        self.screen.blit(sub, (cx - sub.get_width() // 2, 200))

        # Decorative snakes
        self._draw_deco_snake(60, 350, C_P0, 6)
        self._draw_deco_snake(WIN_W - 120, 250, C_P1, 5)

        # Labels
        for label, y in [("Host / IP", 240), ("Port", 300), ("Username", 360)]:
            t = self.font_sm.render(label, True, C_TEXT)
            self.screen.blit(t, (cx - 160, y))

        for inp in self._active_inputs:
            inp.draw(self.screen)

        # Connect button
        draw_rounded_rect(self.screen, C_P0, self.conn_btn, 8)
        bt = self.font_md.render("Connect", True, C_BG)
        self.screen.blit(bt, (self.conn_btn.centerx - bt.get_width() // 2,
                               self.conn_btn.centery - bt.get_height() // 2))

        if self.conn_err:
            color = C_ERR if "Error" in self.conn_err or "taken" in self.conn_err or "Fill" in self.conn_err or "Invalid" in self.conn_err else C_ACCENT
            et = self.font_sm.render(self.conn_err, True, color)
            self.screen.blit(et, (cx - et.get_width() // 2, 498))

    def _draw_deco_snake(self, x, y, color, length):
        positions = [(x + i * CELL, y + int(10 * __import__("math").sin(i))) for i in range(length)]
        for i, (px, py) in enumerate(positions):
            alpha = 180 - i * 20
            size  = CELL - 4 if i > 0 else CELL
            pygame.draw.rect(self.screen, color, (px, py, size, size), border_radius=4)

    # ── Lobby screen ───────────────────────────────────────────────────────────
    def _draw_lobby(self):
        cx = WIN_W // 2
        title = self.font_lg.render("🐍 Lobby", True, C_P0)
        self.screen.blit(title, (cx - title.get_width() // 2, 60))

        user_t = self.font_md.render(f"Logged in as: {self.username}", True, C_ACCENT)
        self.screen.blit(user_t, (cx - user_t.get_width() // 2, 100))

        wait_t = self.font_sm.render("Waiting for a second player…", True, C_TEXT)
        self.screen.blit(wait_t, (cx - wait_t.get_width() // 2, 140))

        # Player list
        panel = pygame.Rect(cx - 200, 180, 400, 300)
        draw_rounded_rect(self.screen, C_PANEL, panel, 10, 2, C_BORDER)
        pt = self.font_md.render("Online Players", True, C_ACCENT)
        self.screen.blit(pt, (panel.x + 16, panel.y + 12))
        for i, name in enumerate(self.online_list):
            color = C_P0 if name == self.username else C_TEXT
            nt = self.font_sm.render(f"  {'►' if name == self.username else ' '}  {name}", True, color)
            self.screen.blit(nt, (panel.x + 16, panel.y + 44 + i * 24))

        # Watch button
        draw_rounded_rect(self.screen, C_PANEL, self.fan_btn, 8, 2, C_BORDER)
        ft = self.font_sm.render("👁  Watch ongoing game (Fan mode)", True, C_CHEER)
        self.screen.blit(ft, (self.fan_btn.x + 10, self.fan_btn.centery - ft.get_height() // 2))

        # Animated dots
        dots = "." * (int(time.time() * 2) % 4)
        wt = self.font_sm.render(f"Waiting{dots}", True, C_BORDER)
        self.screen.blit(wt, (cx - wt.get_width() // 2, 510))

    # ── Game screen ───────────────────────────────────────────────────────────
    def _draw_game(self):
        gd = self.game_data
        # Draw grid
        for x in range(GRID_W):
            for y in range(GRID_H):
                rect = pygame.Rect(x * CELL, y * CELL + TOP_H, CELL, CELL)
                pygame.draw.rect(self.screen, C_GRID, rect)
                pygame.draw.rect(self.screen, C_BG, rect, 1)

        # Wall border
        pygame.draw.rect(self.screen, C_WALL,
                         (0, TOP_H, GRID_W * CELL, GRID_H * CELL), 3)

        if gd:
            self._draw_obstacles(gd)
            self._draw_pies(gd)
            self._draw_snakes(gd)

        self._draw_topbar(gd)
        self._draw_sidebar(gd)
        self._draw_cheers()

    def _draw_obstacles(self, gd):
        for obs in gd.get("obstacles", []):
            ox, oy = obs["pos"]
            kind   = obs.get("kind", "rock")
            color  = OBS_COLORS.get(kind, C_ROCK)
            rect   = pygame.Rect(ox * CELL + 1, oy * CELL + TOP_H + 1, CELL - 2, CELL - 2)
            pygame.draw.rect(self.screen, color, rect, border_radius=4)
            sym = self.font_xs.render(OBS_SYMBOLS.get(kind, "?"), True, C_BG)
            self.screen.blit(sym, (rect.centerx - sym.get_width() // 2,
                                    rect.centery - sym.get_height() // 2))

    def _draw_pies(self, gd):
        for pie in gd.get("pies", []):
            px, py = pie["pos"]
            kind   = pie.get("kind", "normal")
            color  = PIE_COLORS.get(kind, C_NORMAL)
            rect   = pygame.Rect(px * CELL + 3, py * CELL + TOP_H + 3, CELL - 6, CELL - 6)
            pygame.draw.ellipse(self.screen, color, rect)
            if kind == "golden":
                pygame.draw.ellipse(self.screen, (255, 255, 200), rect, 2)

    def _draw_snakes(self, gd):
        snake_colors = [(C_P0, C_P0_D), (C_P1, C_P1_D)]
        for snake in gd.get("snakes", []):
            pid    = snake["player_id"]
            body   = snake["body"]
            alive  = snake.get("alive", True)
            hcolor, bcolor = snake_colors[pid] if alive else (C_DEAD, C_DEAD)
            for i, (bx, by) in enumerate(body):
                rect = pygame.Rect(bx * CELL + 1, by * CELL + TOP_H + 1, CELL - 2, CELL - 2)
                color = hcolor if i == 0 else bcolor
                pygame.draw.rect(self.screen, color, rect, border_radius=5 if i == 0 else 3)
                # Eyes on head
                if i == 0 and alive:
                    self._draw_eyes(rect, snake["direction"], pid)

    def _draw_eyes(self, rect, direction, pid):
        eye_color = C_BG
        offsets = {
            "RIGHT": [(rect.right - 7, rect.top + 5),    (rect.right - 7, rect.bottom - 9)],
            "LEFT":  [(rect.left + 4,  rect.top + 5),    (rect.left + 4,  rect.bottom - 9)],
            "UP":    [(rect.left + 5,  rect.top + 4),     (rect.right - 9, rect.top + 4)],
            "DOWN":  [(rect.left + 5,  rect.bottom - 8),  (rect.right - 9, rect.bottom - 8)],
        }
        for ex, ey in offsets.get(direction, []):
            pygame.draw.circle(self.screen, eye_color, (ex, ey), 3)
            pygame.draw.circle(self.screen, C_TEXT,    (ex, ey), 1)

    def _draw_topbar(self, gd):
        pygame.draw.rect(self.screen, C_PANEL, (0, 0, WIN_W, TOP_H))
        pygame.draw.line(self.screen, C_BORDER, (0, TOP_H), (WIN_W, TOP_H), 2)

        if gd:
            usernames = gd.get("usernames", ["P1", "P2"])
            snakes    = gd.get("snakes",    [])
            time_left = gd.get("time_left", 0)

            for i in range(min(2, len(snakes))):
                sn    = snakes[i]
                name  = usernames[i] if i < len(usernames) else f"P{i+1}"
                hp    = sn.get("health", 0)
                alive = sn.get("alive", True)
                color = [C_P0, C_P1][i]
                label = f"{'YOU' if self.player_id == i else name}"
                if not alive:
                    label += " ☠"

                if i == 0:
                    bx = 20
                else:
                    bx = WIN_W - SIDEBAR - 20 - 200

                nt = self.font_md.render(label, True, color)
                self.screen.blit(nt, (bx, 10))
                health_bar(self.screen, bx, 34, 200, 14, hp, MAX_HEALTH,
                           C_HEALTH0 if i == 0 else C_HEALTH1)
                ht = self.font_xs.render(f"HP: {hp}", True, C_TEXT)
                self.screen.blit(ht, (bx + 210, 36))

            # Timer
            tm = self.font_lg.render(f"{int(time_left)}s", True, C_ACCENT if time_left > 20 else C_ERR)
            self.screen.blit(tm, (WIN_W // 2 - SIDEBAR // 2 - tm.get_width() // 2, 10))

            # Fan/role indicator
            role_t = self.font_xs.render(
                "👁 Watching" if self.is_fan else f"🎮 Player {self.player_id + 1}" if self.player_id is not None else "",
                True, C_CHEER if self.is_fan else C_TEXT
            )
            self.screen.blit(role_t, (WIN_W - SIDEBAR + 10, 4))

    def _draw_sidebar(self, gd):
        sx = GRID_W * CELL
        panel = pygame.Rect(sx, 0, SIDEBAR, WIN_H)
        pygame.draw.rect(self.screen, C_PANEL, panel)
        pygame.draw.line(self.screen, C_BORDER, (sx, 0), (sx, WIN_H), 2)

        y = TOP_H + 8
        ct = self.font_sm.render("── Chat ──", True, C_ACCENT)
        self.screen.blit(ct, (sx + 10, y)); y += 22

        # Chat log area
        log_h = WIN_H - TOP_H - 80
        chat_area = pygame.Rect(sx + 4, y, SIDEBAR - 8, log_h)
        pygame.draw.rect(self.screen, C_BG, chat_area, border_radius=4)

        visible = self.chat_log[-(log_h // 18):]
        for j, (sender, text, color) in enumerate(visible):
            msg_t = self.font_xs.render(f"{sender}: {text}"[:42], True, color)
            self.screen.blit(msg_t, (sx + 8, y + j * 17))

        # Chat input
        self.chat_input.rect.y = WIN_H - 42
        self.chat_input.rect.x = sx + 5
        self.chat_input.rect.width = SIDEBAR - 10
        self.chat_input.draw(self.screen)

        # Fan cheer buttons
        if self.is_fan:
            by = WIN_H - 80
            ct2 = self.font_xs.render("Cheer:", True, C_CHEER)
            self.screen.blit(ct2, (sx + 8, by - 18))
            for i, emoji in enumerate(self.cheer_emojis):
                btn = self._cheer_btn_rect(i)
                draw_rounded_rect(self.screen, (40, 40, 60), btn, 6, 1, C_BORDER)
                et = self.font_sm.render(emoji, True, C_CHEER)
                self.screen.blit(et, (btn.centerx - et.get_width() // 2,
                                       btn.centery - et.get_height() // 2))

        # Controls hint
        hint = self.font_xs.render("/pm user msg  for private", True, C_BORDER)
        self.screen.blit(hint, (sx + 6, WIN_H - 60))

    def _cheer_btn_rect(self, i):
        sx = GRID_W * CELL
        return pygame.Rect(sx + 5 + i * 56, WIN_H - 78, 50, 26)

    def _draw_cheers(self):
        now = time.time()
        self.cheers = [(txt, exp) for txt, exp in self.cheers if exp > now]
        for i, (txt, exp) in enumerate(self.cheers):
            alpha = min(255, int((exp - now) * 255))
            ct = self.font_md.render(txt, True, C_CHEER)
            self.screen.blit(ct, (20, WIN_H - 80 - i * 28))

    # ── Game over overlay ──────────────────────────────────────────────────────
    def _draw_game_over_overlay(self):
        ov = pygame.Surface((WIN_W, WIN_H), pygame.SRCALPHA)
        ov.fill((0, 0, 0, 180))
        self.screen.blit(ov, (0, 0))

        cx = (GRID_W * CELL) // 2
        cy = (TOP_H + GRID_H * CELL) // 2

        go = self.game_over or {}
        winner = go.get("winner", "draw")
        scores = go.get("scores", {})

        if winner == "draw":
            title_t = self.font_xl.render("DRAW!", True, C_ACCENT)
        elif winner == self.username:
            title_t = self.font_xl.render("YOU WIN! 🏆", True, C_P0)
        else:
            title_t = self.font_xl.render(f"{winner} WINS!", True, C_P1)

        self.screen.blit(title_t, (cx - title_t.get_width() // 2, cy - 80))

        for i, (name, hp) in enumerate(scores.items()):
            st = self.font_md.render(f"{name}: {hp} HP", True, [C_P0, C_P1][i])
            self.screen.blit(st, (cx - st.get_width() // 2, cy + i * 32))

        draw_rounded_rect(self.screen, C_P0, self.rematch_btn, 10)
        rt = self.font_md.render("🔄  Rematch", True, C_BG)
        self.screen.blit(rt, (self.rematch_btn.centerx - rt.get_width() // 2,
                                self.rematch_btn.centery - rt.get_height() // 2))

        draw_rounded_rect(self.screen, C_PANEL, self.lobby_btn, 10, 2, C_BORDER)
        lt = self.font_md.render("🏠  Lobby", True, C_TEXT)
        self.screen.blit(lt, (self.lobby_btn.centerx - lt.get_width() // 2,
                               self.lobby_btn.centery - lt.get_height() // 2))

        hint = self.font_sm.render("Press Enter to chat  •  Rematch or return to Lobby", True, C_BORDER)
        self.screen.blit(hint, (cx - hint.get_width() // 2, cy + 140))

        # Still show chat sidebar during game over
        self._draw_sidebar(self.game_data)


if __name__ == "__main__":
    client = PithonArenaClient()
    client.run()