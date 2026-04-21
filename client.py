"""
Pithon Arena - Client  (redesigned UI)
Usage: python client.py
"""

import sys, socket, threading, queue, time, math, random
import pygame, pygame.gfxdraw
from protocol import *

# ── Layout ─────────────────────────────────────────────────────────────────────
CELL    = 26
SIDEBAR = 310
TOP_H   = 68
WIN_W   = GRID_W * CELL + SIDEBAR
WIN_H   = GRID_H * CELL + TOP_H
FPS     = 60

# ── Palette ────────────────────────────────────────────────────────────────────
BG          = (10,  12,  20)
GRID_DARK   = (16,  18,  30)
GRID_LINE   = (22,  24,  40)
WALL_C      = (40,  44,  80)
PANEL_BG    = (14,  16,  26)
PANEL_DARK  = (10,  12,  20)
BORDER      = (45,  50,  90)
BORDER_HI   = (80, 100, 180)

P0_HEAD     = ( 50, 230, 120)
P0_BODY     = ( 30, 160,  85)
P0_GLOW     = ( 80, 255, 160)
P1_HEAD     = (240,  80,  60)
P1_BODY     = (180,  50,  35)
P1_GLOW     = (255, 120,  90)
DEAD_C      = ( 55,  55,  70)

PIE_GOLD    = (255, 210,  50)
PIE_NORM    = (255, 130,  40)
PIE_ROT     = ( 90, 130,  50)
OBS_ROCK    = (100, 105, 125)
OBS_SPIKE   = (160, 165, 200)

TEXT        = (122,251,255)
TEXT_DIM    = (255,225,0)
TEXT_BRIGHT = (138,255,156)
ACCENT      = ( 90, 185, 255)
GOLD        = (255, 200,  50)
GREEN_OK    = ( 60, 200, 110)
RED_ERR     = (220,  70,  70)
CHAT_ME     = ( 90, 170, 255)
CHAT_OTHER  = (170, 175, 200)
CHEER_C     = (255, 210,  60)

HP_GREEN    = ( 50, 210, 100)
HP_YELLOW   = (220, 190,  50)
HP_RED      = (210,  60,  60)

S_CONNECT   = "connect"
S_LOBBY     = "lobby"
S_GAME      = "game"
S_GAME_OVER = "game_over"

# ── Helpers ────────────────────────────────────────────────────────────────────
def lerp(a, b, t):
    return tuple(int(a[i]+(b[i]-a[i])*t) for i in range(3))

def hp_color(ratio):
    if ratio > 0.5: return lerp(HP_YELLOW, HP_GREEN, (ratio-0.5)*2)
    return lerp(HP_RED, HP_YELLOW, ratio*2)

def aa_circle(surf, color, center, r):
    if r < 1: return
    pygame.gfxdraw.aacircle(surf, int(center[0]), int(center[1]), int(r), color)
    pygame.gfxdraw.filled_circle(surf, int(center[0]), int(center[1]), int(r), color)

def rr(surf, color, rect, r=8):
    pygame.draw.rect(surf, color, rect, border_radius=r)

def rrb(surf, color, rect, r=8, w=1):
    pygame.draw.rect(surf, color, rect, w, border_radius=r)

# ── Fonts ──────────────────────────────────────────────────────────────────────
def load_fonts():
    ui_names   = ["segoeui","calibri","arial","helvetica","freesans","dejavusans"]
    mono_names = ["consolas","cascadiacode","couriernew","lucidaconsole","monospace"]
    def get(names, size, bold=False):
        for n in names:
            p = pygame.font.match_font(n, bold=bold)
            if p:
                return pygame.font.Font(p, size)
        return pygame.font.SysFont("monospace", size, bold=bold)
    return {
        "title":   get(ui_names, 46, True),
        "h1":      get(ui_names, 30, True),
        "h2":      get(ui_names, 21, True),
        "body":    get(ui_names, 16),
        "small":   get(ui_names, 13),
        "tiny":    get(ui_names, 11),
        "mono":    get(mono_names, 14),
        "mono_sm": get(mono_names, 12),
        "bignum":  get(ui_names, 50, True),
    }

# ── Network ────────────────────────────────────────────────────────────────────
class NetworkThread(threading.Thread):
    def __init__(self, host, port, recv_q):
        super().__init__(daemon=True)
        self.host, self.port, self.recv_q = host, port, recv_q
        self._sock = None
        self._send_q = queue.Queue()
        self._buf = b""
        self.connected = False

    def run(self):
        try:
            self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self._sock.connect((self.host, self.port))
            self.connected = True
            threading.Thread(target=self._sender, daemon=True).start()
            self._receiver()
        except Exception as e:
            self.recv_q.put({"type": "_NET_ERROR", "reason": str(e)})

    def _receiver(self):
        while True:
            try:
                chunk = self._sock.recv(4096)
            except Exception:
                self.recv_q.put({"type": "_NET_ERROR", "reason": "Disconnected"})
                return
            if not chunk:
                self.recv_q.put({"type": "_NET_ERROR", "reason": "Server closed"})
                return
            self._buf += chunk
            while b"\n" in self._buf:
                line, self._buf = self._buf.split(b"\n", 1)
                try:
                    self.recv_q.put(decode(line + b"\n"))
                except Exception:
                    pass

    def _sender(self):
        while True:
            msg = self._send_q.get()
            if msg is None: break
            try:
                self._sock.sendall(encode(msg))
            except Exception:
                break

    def send(self, msg):
        if self.connected:
            self._send_q.put(msg)

# ── Text Input ─────────────────────────────────────────────────────────────────
class TextInput:
    def __init__(self, rect, F, placeholder="", max_len=40):
        self.rect = rect
        self.F = F
        self.placeholder = placeholder
        self.max_len = max_len
        self.text = ""
        self.active = False
        self._blink = True
        self._bt = 0

    def handle_event(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN:
            self.active = self.rect.collidepoint(event.pos)
        if event.type == pygame.KEYDOWN and self.active:
            if event.key == pygame.K_BACKSPACE:
                self.text = self.text[:-1]
            elif event.key not in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_TAB):
                if len(self.text) < self.max_len and event.unicode.isprintable():
                    self.text += event.unicode
            return event.key in (pygame.K_RETURN, pygame.K_KP_ENTER)
        return False

    def draw(self, surf, label=None):
        now = pygame.time.get_ticks()
        if now - self._bt > 530:
            self._blink = not self._blink
            self._bt = now
        bg = (22, 26, 42) if self.active else (16, 18, 30)
        rr(surf, bg, self.rect, 8)
        rrb(surf, ACCENT if self.active else BORDER, self.rect, 8, 2 if self.active else 1)
        disp = self.text or self.placeholder
        col  = TEXT if self.text else TEXT_DIM
        ts   = self.F["body"].render(disp, True, col)
        ty   = self.rect.centery - ts.get_height()//2
        surf.blit(ts, (self.rect.x+12, ty))
        if self.active and self._blink:
            cx = self.rect.x + 12 + self.F["body"].size(self.text)[0] + 1
            pygame.draw.line(surf, ACCENT, (cx, ty+2), (cx, ty+ts.get_height()-2), 2)
        if label:
            lt = self.F["small"].render(label, True, TEXT_DIM)
            surf.blit(lt, (self.rect.x, self.rect.y - lt.get_height() - 4))

# ── Button ─────────────────────────────────────────────────────────────────────
class Button:
    def __init__(self, rect, text, F, bg=None, fg=None):
        self.rect = pygame.Rect(rect)
        self.text = text
        self.F = F
        self.bg = bg or ACCENT
        self.fg = fg or BG
        self._hover = False
        self._pt = 0

    def handle_event(self, event):
        if event.type == pygame.MOUSEMOTION:
            self._hover = self.rect.collidepoint(event.pos)
        if event.type == pygame.MOUSEBUTTONDOWN and self.rect.collidepoint(event.pos):
            self._pt = pygame.time.get_ticks()
            return True
        return False

    def draw(self, surf):
        pressed = pygame.time.get_ticks() - self._pt < 120
        col = lerp(self.bg, TEXT_BRIGHT, 0.18) if self._hover else self.bg
        if pressed: col = lerp(col, BG, 0.3)
        r = self.rect
        if self._hover:
            g = pygame.Surface((r.w+16, r.h+16), pygame.SRCALPHA)
            pygame.draw.rect(g, (*col, 35), (8, 8, r.w, r.h), border_radius=10)
            surf.blit(g, (r.x-8, r.y-8))
        rr(surf, col, r, 9)
        ts = self.F["h2"].render(self.text, True, self.fg)
        surf.blit(ts, (r.centerx - ts.get_width()//2, r.centery - ts.get_height()//2))

# ── Health Bar ─────────────────────────────────────────────────────────────────
def draw_hp(surf, x, y, w, h, val, mx):
    ratio = max(0.0, min(1.0, val/mx))
    rr(surf, (25, 28, 45), pygame.Rect(x, y, w, h), h//2)
    if ratio > 0:
        col = hp_color(ratio)
        fw  = max(h, int(w*ratio))
        rr(surf, col, pygame.Rect(x, y, fw, h), h//2)
    rrb(surf, BORDER, pygame.Rect(x, y, w, h), h//2, 1)

# ── Particle ───────────────────────────────────────────────────────────────────
class Particle:
    def __init__(self, x, y, color):
        a = random.uniform(0, math.tau)
        s = random.uniform(1.5, 4.5)
        self.x, self.y = float(x), float(y)
        self.vx, self.vy = math.cos(a)*s, math.sin(a)*s - 1.5
        self.color = color
        self.life  = 1.0
        self.decay = random.uniform(0.03, 0.07)
        self.size  = random.randint(3, 7)

    def update(self):
        self.x += self.vx; self.y += self.vy; self.vy += 0.12
        self.life -= self.decay
        return self.life > 0

    def draw(self, surf):
        s = max(1, int(self.size * self.life))
        tmp = pygame.Surface((s*2+2, s*2+2), pygame.SRCALPHA)
        pygame.draw.circle(tmp, (*self.color[:3], int(255*self.life)), (s+1, s+1), s)
        surf.blit(tmp, (int(self.x)-s, int(self.y)-s))

# ── Client ─────────────────────────────────────────────────────────────────────
class PithonArenaClient:
    def __init__(self):
        pygame.init()
        self.screen = pygame.display.set_mode((WIN_W, WIN_H), pygame.RESIZABLE)
        pygame.display.set_caption("Pithon Arena")
        self.clock = pygame.time.Clock()
        self.F     = load_fonts()

        self.net         = None
        self.recv_q      = queue.Queue()
        self.state       = S_CONNECT
        self.username    = None
        self.player_id   = None
        self.is_fan      = False
        self.game_cfg    = {}
        self.game_data   = None
        self.game_over   = None
        self.online_list = []
        self.chat_log    = []
        self.cheers      = []
        self.particles   = []
        self.conn_msg    = ""
        self.conn_ok     = False
        self.last_dir    = None
        self._t          = 0.0

        self.key_map = {
            pygame.K_UP:"UP", pygame.K_DOWN:"DOWN",
            pygame.K_LEFT:"LEFT", pygame.K_RIGHT:"RIGHT",
            pygame.K_w:"UP", pygame.K_s:"DOWN",
            pygame.K_a:"LEFT", pygame.K_d:"RIGHT",
        }

        self._build_ui()

    def _build_ui(self):
        cx = WIN_W//2
        self.inp_host = TextInput(pygame.Rect(cx-170, 292, 340, 42), self.F, "Server IP  e.g. 127.0.0.1", 64)
        self.inp_port = TextInput(pygame.Rect(cx-170, 370, 150, 42), self.F, "Port", 6)
        self.inp_user = TextInput(pygame.Rect(cx-170, 448, 340, 42), self.F, "Username", 20)
        self.inp_host.text = "127.0.0.1"
        self.inp_port.text = "5555"
        self.btn_connect = Button(pygame.Rect(cx-105, 518, 210, 46), "Connect", self.F, ACCENT)
        self._cinputs = [self.inp_host, self.inp_port, self.inp_user]

        sx = GRID_W*CELL
        self.chat_inp    = TextInput(pygame.Rect(sx+6, WIN_H-44, SIDEBAR-12, 36), self.F, "Chat  (/pm user msg)", 150)
        self.btn_rematch = Button(pygame.Rect(100, 100, 210, 48), "Rematch",      self.F, P0_HEAD, BG)
        self.btn_lobby   = Button(pygame.Rect(100, 100, 210, 48), "Back to Lobby",self.F, PANEL_BG, TEXT)
        self.btn_watch   = Button(pygame.Rect(100, 100, 220, 42), "Watch as Fan", self.F, (45,50,80), TEXT)

        self.cheer_labels = ["Fire", "Skull", "Crown", "GG", "Hype"]
        self.cheer_colors = [(220,90,40),(150,50,200),(220,180,30),(50,180,120),(80,150,255)]

    # ── Loop ──────────────────────────────────────────────────────────────────
    def run(self):
        while True:
            dt = self.clock.tick(FPS)/1000.0
            self._t += dt
            while not self.recv_q.empty():
                self._on_msg(self.recv_q.get_nowait())
            self._handle_events()
            self.particles = [p for p in self.particles if p.update()]
            self._draw()
            pygame.display.flip()

    # ── Messages ──────────────────────────────────────────────────────────────
    def _on_msg(self, msg):
        t = msg.get("type")
        if t == "_NET_ERROR":
            self.conn_msg = msg.get("reason","Network error")
            self.conn_ok  = False
            self.state    = S_CONNECT
        elif t == MSG_JOIN_OK:
            self.username = msg["username"]
            self.state    = S_LOBBY
        elif t == MSG_JOIN_ERR:
            self.conn_msg = msg.get("reason","Error")
            self.conn_ok  = False
        elif t == MSG_PLAYER_LIST:
            self.online_list = msg.get("players",[])
            if self.state == S_GAME_OVER and self.username in self.online_list:
                self._to_lobby()
        elif t == MSG_GAME_START:
            self.player_id = msg.get("your_id")
            self.is_fan    = False
            self.state     = S_GAME
            self.game_over = None
            self.game_data = None
        elif t == MSG_WATCH_OK:
            self.is_fan = True
            self.state  = S_GAME
            self.game_over = None
        elif t == MSG_GAME_STATE:
            self.game_data = msg
        elif t == MSG_GAME_OVER:
            self.game_over = msg
            self.state     = S_GAME_OVER
            if msg.get("winner") == self.username:
                gcx = (GRID_W*CELL)//2
                for _ in range(50):
                    self.particles.append(Particle(
                        gcx + random.randint(-120,120),
                        WIN_H//2 + random.randint(-80,80),
                        P0_HEAD if self.player_id==0 else P1_HEAD))
        elif t == MSG_CHAT_RECV:
            s   = msg.get("from","?")
            tx  = msg.get("text","")
            prv = msg.get("private",False)
            col = CHAT_ME if s==self.username else CHAT_OTHER
            self.chat_log.append((s, ("[PM] " if prv else "")+tx, col))
            if len(self.chat_log) > 80: self.chat_log.pop(0)
        elif t == MSG_CHEER_RECV:
            self.cheers.append((
                f"{msg.get('from','?')}: {msg.get('emoji','!')} for {msg.get('player','')}!",
                time.time()+3.5))

    # ── Events ────────────────────────────────────────────────────────────────
    def _handle_events(self):
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                pygame.quit(); sys.exit()
            if self.state == S_CONNECT:
                for inp in self._cinputs:
                    if inp.handle_event(ev): self._do_connect()
                if self.btn_connect.handle_event(ev): self._do_connect()
            elif self.state == S_LOBBY:
                if self.btn_watch.handle_event(ev) and self.net:
                    self.net.send({"type": MSG_WATCH})
            elif self.state == S_GAME:
                if self.chat_inp.handle_event(ev):
                    self._send_chat()
                if ev.type == pygame.MOUSEBUTTONDOWN and self.is_fan:
                    for i in range(len(self.cheer_labels)):
                        if self._cheer_rect(i).collidepoint(ev.pos) and self.game_data:
                            unames = self.game_data.get("usernames",[])
                            if unames:
                                self.net.send({"type":MSG_CHEER,"emoji":self.cheer_labels[i],"player":unames[0]})
                if ev.type == pygame.KEYDOWN and not self.is_fan and not self.chat_inp.active:
                    d = self.key_map.get(ev.key)
                    if d and self.net:
                        self.net.send({"type":MSG_INPUT,"direction":d})
            elif self.state == S_GAME_OVER:
                self.chat_inp.handle_event(ev)
                if ev.type == pygame.KEYDOWN and ev.key == pygame.K_RETURN:
                    self._send_chat()
                if self.btn_rematch.handle_event(ev) and self.net:
                    self.net.send({"type":MSG_REMATCH})
                if self.btn_lobby.handle_event(ev) and self.net:
                    self.net.send({"type":MSG_LEAVE})
                    self._to_lobby()

    def _send_chat(self):
        txt = self.chat_inp.text.strip()
        if txt and self.net:
            if txt.startswith("/pm "):
                parts = txt[4:].split(" ",1)
                if len(parts)==2:
                    self.net.send({"type":MSG_CHAT,"to":parts[0],"text":parts[1]})
            else:
                self.net.send({"type":MSG_CHAT,"to":None,"text":txt})
        self.chat_inp.text = ""

    def _do_connect(self):
        host  = self.inp_host.text.strip()
        port  = self.inp_port.text.strip()
        uname = self.inp_user.text.strip()
        if not host or not port or not uname:
            self.conn_msg = "Please fill in all fields."; self.conn_ok = False; return
        try: port_n = int(port)
        except ValueError:
            self.conn_msg = "Port must be a number."; self.conn_ok = False; return
        self.conn_msg = "Connecting..."; self.conn_ok = True
        self.net = NetworkThread(host, port_n, self.recv_q)
        self.net.start()
        def _join():
            time.sleep(0.35)
            self.net.send({"type":MSG_JOIN,"username":uname})
        threading.Thread(target=_join, daemon=True).start()

    def _to_lobby(self):
        self.state = S_LOBBY; self.game_data = None
        self.game_over = None; self.player_id = None; self.is_fan = False

    # ── Draw ──────────────────────────────────────────────────────────────────
    def _draw(self):
        self.screen.fill(BG)
        if   self.state == S_CONNECT:   self._draw_connect()
        elif self.state == S_LOBBY:     self._draw_lobby()
        elif self.state in (S_GAME, S_GAME_OVER):
            self._draw_game()
            if self.state == S_GAME_OVER: self._draw_gameover()
        for p in self.particles: p.draw(self.screen)

    # ── Connect ───────────────────────────────────────────────────────────────
    def _draw_connect(self):
        cx = WIN_W//2
        t  = self._t

        # Animated background grid
        for gx in range(0, WIN_W+40, 40):
            a = int(14 + 7*math.sin(t*0.5 + gx*0.04))
            pygame.draw.line(self.screen, (GRID_LINE[0], GRID_LINE[1], GRID_LINE[2]), (gx, 0), (gx, WIN_H))
        for gy in range(0, WIN_H+40, 40):
            a = int(14 + 7*math.sin(t*0.5 + gy*0.04))
            pygame.draw.line(self.screen, GRID_LINE, (0, gy), (WIN_W, gy))

        # Animated snake decorations
        for side in range(2):
            col = P0_HEAD if side==0 else P1_HEAD
            for i in range(8):
                px = (80 + i*30) if side==0 else (WIN_W - 80 - i*30)
                py = int(WIN_H//2 + 55*math.sin(t*1.6 + i*0.7 + side*math.pi))
                a  = max(0, 220 - i*26)
                sz = max(4, 22 - i*2)
                s  = pygame.Surface((sz, sz), pygame.SRCALPHA)
                s.fill((*col, a))
                self.screen.blit(s, (px-sz//2, py-sz//2))

        # Card
        card = pygame.Rect(cx-210, 230, 420, 360)
        cs = pygame.Surface((card.w, card.h), pygame.SRCALPHA)
        cs.fill((14, 16, 28, 235))
        self.screen.blit(cs, card.topleft)
        rrb(self.screen, BORDER, card, 14, 1)
        # Top accent line
        pulse = int(128 + 120*math.sin(t*1.5))
        acc_col = (int(ACCENT[0]*pulse/255), int(ACCENT[1]*pulse/255), int(ACCENT[2]*pulse/255))
        pygame.draw.rect(self.screen, acc_col, (card.x+2, card.y, card.w-4, 3), border_radius=14)

        # Title
        title = self.F["title"].render("PITHON ARENA", True, P0_HEAD)
        self.screen.blit(title, (cx - title.get_width()//2, 148))
        sub = self.F["small"].render("Real-time Online Snake Battle  |  EECE 350", True, TEXT_DIM)
        self.screen.blit(sub, (cx - sub.get_width()//2, 200))

        self.inp_host.draw(self.screen, "Server IP Address")
        self.inp_port.draw(self.screen, "Port")
        self.inp_user.draw(self.screen, "Username")
        self.btn_connect.draw(self.screen)

        if self.conn_msg:
            col = GREEN_OK if self.conn_ok else RED_ERR
            mt = self.F["small"].render(self.conn_msg, True, col)
            self.screen.blit(mt, (cx - mt.get_width()//2, 574))

        hint = self.F["tiny"].render("Controls: WASD or Arrow Keys   |   Private chat: /pm username message", True, TEXT_DIM)
        self.screen.blit(hint, (cx - hint.get_width()//2, WIN_H-20))

    # ── Lobby ─────────────────────────────────────────────────────────────────
    def _draw_lobby(self):
        cx = WIN_W//2

        # Header
        pygame.draw.rect(self.screen, PANEL_BG, (0,0,WIN_W,64))
        pygame.draw.line(self.screen, BORDER, (0,64),(WIN_W,64))
        t1 = self.F["h1"].render("PITHON ARENA", True, P0_HEAD)
        self.screen.blit(t1, (20, 16))
        u = self.F["body"].render(f"Logged in as   {self.username}", True, ACCENT)
        self.screen.blit(u, (WIN_W - u.get_width()-20, 20))

        # Players panel
        panel = pygame.Rect(cx-240, 84, 480, 300)
        rr(self.screen, PANEL_BG, panel, 12)
        rrb(self.screen, BORDER, panel, 12, 1)

        hdr = self.F["h2"].render("Online Players", True, TEXT_BRIGHT)
        self.screen.blit(hdr, (panel.x+18, panel.y+14))
        pygame.draw.line(self.screen, BORDER, (panel.x+14, panel.y+46),(panel.right-14, panel.y+46))

        if not self.online_list:
            wt = self.F["body"].render("No other players yet...", True, TEXT_DIM)
            self.screen.blit(wt, (panel.centerx - wt.get_width()//2, panel.y+90))
        else:
            for i, name in enumerate(self.online_list[:7]):
                ry = panel.y + 54 + i*33
                is_me = name == self.username
                if is_me:
                    rr(self.screen, (28,33,60), pygame.Rect(panel.x+10, ry, panel.w-20, 28), 6)
                aa_circle(self.screen, P0_HEAD if is_me else GREEN_OK, (panel.x+28, ry+14), 5)
                nt = self.F["body"].render(name + ("  (you)" if is_me else ""), True, P0_HEAD if is_me else TEXT)
                self.screen.blit(nt, (panel.x+44, ry+4))

        # Status + Watch button
        dots = "." * (int(self._t*2)%4)
        wt = self.F["body"].render(f"Waiting for an opponent to join{dots}", True, TEXT_DIM)
        self.screen.blit(wt, (cx - wt.get_width()//2, panel.bottom+14))

        self.btn_watch.rect = pygame.Rect(cx-110, panel.bottom+46, 220, 42)
        self.btn_watch.draw(self.screen)
        ht = self.F["small"].render("Spectate an ongoing match", True, TEXT_DIM)
        self.screen.blit(ht, (cx - ht.get_width()//2, panel.bottom+96))

        k = self.F["small"].render("Move: WASD or Arrow Keys     Private chat: /pm username message", True, TEXT_DIM)
        self.screen.blit(k, (cx - k.get_width()//2, WIN_H-20))

    # ── Game ──────────────────────────────────────────────────────────────────
    def _draw_game(self):
        gd = self.game_data

        # Checkerboard grid
        for x in range(GRID_W):
            for y in range(GRID_H):
                col = GRID_DARK if (x+y)%2==0 else (18,20,34)
                pygame.draw.rect(self.screen, col, (x*CELL, y*CELL+TOP_H, CELL, CELL))
        for x in range(GRID_W+1):
            pygame.draw.line(self.screen, GRID_LINE, (x*CELL,TOP_H),(x*CELL,TOP_H+GRID_H*CELL))
        for y in range(GRID_H+1):
            pygame.draw.line(self.screen, GRID_LINE, (0,y*CELL+TOP_H),(GRID_W*CELL,y*CELL+TOP_H))
        pygame.draw.rect(self.screen, WALL_C, (0,TOP_H,GRID_W*CELL,GRID_H*CELL), 3)

        if gd:
            self._draw_obstacles(gd)
            self._draw_pies(gd)
            self._draw_snakes(gd)

        self._draw_topbar(gd)
        self._draw_sidebar(gd)

        # Cheer toasts
        now = time.time()
        self.cheers = [(tx,ex) for tx,ex in self.cheers if ex>now]
        for i,(tx,ex) in enumerate(self.cheers[-5:]):
            fade = min(1.0,(ex-now)/1.0)
            col  = lerp(BG, CHEER_C, fade)
            ct   = self.F["body"].render(tx, True, col)
            self.screen.blit(ct, (14, WIN_H-115-i*28))

    def _draw_obstacles(self, gd):
        for obs in gd.get("obstacles",[]):
            ox,oy = obs["pos"]
            kind  = obs.get("kind","rock")
            col   = OBS_ROCK if kind=="rock" else OBS_SPIKE
            r = pygame.Rect(ox*CELL+2, oy*CELL+TOP_H+2, CELL-4, CELL-4)
            rr(self.screen, col, r, 4)
            cx2, cy2 = r.centerx, r.centery
            if kind == "rock":
                aa_circle(self.screen, lerp(col, TEXT_BRIGHT, 0.25), (cx2, cy2), CELL//2-5)
                aa_circle(self.screen, col, (cx2, cy2), CELL//2-8)
            else:
                pts = [(cx2, cy2-8),(cx2-5, cy2+6),(cx2+5, cy2+6)]
                pygame.draw.polygon(self.screen, lerp(OBS_SPIKE, TEXT_BRIGHT, 0.5), pts)
                # Label below shape
                lbl = self.F["tiny"].render("spk", True, OBS_SPIKE)
                self.screen.blit(lbl, (r.x+1, r.bottom-12))

    def _draw_pies(self, gd):
        t = self._t
        for pie in gd.get("pies",[]):
            px,py = pie["pos"]
            kind  = pie.get("kind","normal")
            col   = PIE_GOLD if kind=="golden" else PIE_NORM if kind=="normal" else PIE_ROT
            cx2   = px*CELL + CELL//2
            cy2   = py*CELL + TOP_H + CELL//2 + int(2*math.sin(t*3+px*0.7+py*0.5))
            rad   = CELL//2 - 4
            aa_circle(self.screen, col, (cx2, cy2), rad)
            aa_circle(self.screen, lerp(col, TEXT_BRIGHT, 0.55), (cx2-2, cy2-2), rad//3)
            if kind == "golden":
                pygame.gfxdraw.aacircle(self.screen, cx2, cy2, rad+2, (*col, 160))
            # Small label
            lbl_map = {"golden":"G","normal":"N","rotten":"R"}
            lt = self.F["tiny"].render(lbl_map[kind], True, lerp(col, TEXT_BRIGHT, 0.6))
            self.screen.blit(lt, (cx2 - lt.get_width()//2, cy2 - lt.get_height()//2))

    def _draw_snakes(self, gd):
        for snake in gd.get("snakes",[]):
            pid   = snake["player_id"]
            body  = snake["body"]
            alive = snake.get("alive",True)
            h_col = [P0_HEAD,P1_HEAD][pid] if alive else DEAD_C
            b_col = [P0_BODY,P1_BODY][pid] if alive else (45,45,58)
            glow  = [P0_GLOW,P1_GLOW][pid]

            for i,(bx,by) in enumerate(reversed(body)):
                idx    = len(body)-1-i
                is_hd  = idx==0
                col    = h_col if is_hd else b_col
                fade   = max(0.35, 1.0 - idx*0.04)
                col    = lerp(DEAD_C, col, fade)
                r      = pygame.Rect(bx*CELL+1, by*CELL+TOP_H+1, CELL-2, CELL-2)
                rr(self.screen, col, r, 6 if is_hd else 3)
                if is_hd and alive:
                    rrb(self.screen, glow, r, 6, 1)
                    self._draw_eyes(r, snake["direction"], glow)

    def _draw_eyes(self, r, direction, glow):
        offs = {
            "RIGHT":[(r.right-7, r.top+6),(r.right-7, r.bottom-9)],
            "LEFT": [(r.left+4,  r.top+6),(r.left+4,  r.bottom-9)],
            "UP":   [(r.left+6,  r.top+4),(r.right-9, r.top+4)],
            "DOWN": [(r.left+6,  r.bottom-7),(r.right-9, r.bottom-7)],
        }
        for ex,ey in offs.get(direction,[]):
            aa_circle(self.screen, BG,   (ex, ey), 3)
            aa_circle(self.screen, glow, (ex, ey), 2)

    def _draw_topbar(self, gd):
        pygame.draw.rect(self.screen, PANEL_BG, (0,0,WIN_W,TOP_H))
        pygame.draw.line(self.screen, BORDER, (0,TOP_H),(WIN_W,TOP_H))
        if not gd: return

        unames    = gd.get("usernames",["P1","P2"])
        snakes    = gd.get("snakes",[])
        time_left = gd.get("time_left",0)

        for i in range(min(2, len(snakes))):
            sn    = snakes[i]
            name  = unames[i] if i<len(unames) else f"P{i+1}"
            hp    = sn.get("health",0)
            alive = sn.get("alive",True)
            col   = [P0_HEAD,P1_HEAD][i] if alive else DEAD_C
            is_me = self.player_id==i

            bx = 12 if i==0 else GRID_W*CELL-12-220

            # Tag
            tag_txt = "YOU" if is_me else f"P{i+1}"
            rr(self.screen, (*col[:3],50), pygame.Rect(bx, 5, 44, 22), 4)
            tag = self.F["tiny"].render(tag_txt, True, col)
            self.screen.blit(tag, (bx+5, 10))

            # Name
            nt = self.F["h2"].render(name + (" [dead]" if not alive else ""), True, col)
            self.screen.blit(nt, (bx+52, 5))
            # HP bar
            draw_hp(self.screen, bx, 36, 220, 14, hp, MAX_HEALTH)
            ht = self.F["tiny"].render(f"{hp} HP", True, TEXT_DIM)
            self.screen.blit(ht, (bx+224, 37))

        # Timer
        tcx  = GRID_W*CELL//2
        urgent = time_left < 20
        t_col  = RED_ERR if urgent else ACCENT
        if urgent and int(self._t*2)%2==0:
            t_col = lerp(RED_ERR, TEXT_BRIGHT, 0.3)
        tm  = self.F["bignum"].render(str(int(time_left)), True, t_col)
        self.screen.blit(tm, (tcx-tm.get_width()//2, 2))
        sl  = self.F["tiny"].render("sec", True, TEXT_DIM)
        self.screen.blit(sl, (tcx-sl.get_width()//2, 52))

        # Role badge
        sx = GRID_W*CELL+10
        if self.is_fan:
            badge = self.F["small"].render("SPECTATOR", True, CHEER_C)
        elif self.player_id is not None:
            badge = self.F["small"].render(f"PLAYER {self.player_id+1}", True, [P0_HEAD,P1_HEAD][self.player_id])
        else:
            return
        self.screen.blit(badge, (sx, 8))

    def _draw_sidebar(self, gd):
        sx = GRID_W*CELL
        pygame.draw.rect(self.screen, PANEL_BG, (sx,0,SIDEBAR,WIN_H))
        pygame.draw.line(self.screen, BORDER, (sx,0),(sx,WIN_H))

        y = TOP_H+8
        ch = self.F["small"].render("CHAT", True, TEXT_DIM)
        self.screen.blit(ch, (sx+12, y))
        pygame.draw.line(self.screen, BORDER, (sx+8,y+18),(sx+SIDEBAR-8,y+18))
        y += 24

        log_bot = WIN_H-92 if self.is_fan else WIN_H-52
        log_h   = log_bot - y
        lr = pygame.Rect(sx+4, y, SIDEBAR-8, log_h)
        rr(self.screen, PANEL_DARK, lr, 6)
        rrb(self.screen, BORDER, lr, 6, 1)

        visible = self.chat_log[-(log_h//19):]
        for j,(sender,text,col) in enumerate(visible):
            my = y + 4 + j*19
            if my+18 > log_bot: break
            st = self.F["mono_sm"].render(sender+":", True, col)
            self.screen.blit(st, (sx+8, my))
            avail = SIDEBAR - 16 - st.get_width()
            chars = max(0, avail//7)
            tt = self.F["mono_sm"].render(text[:chars], True, TEXT)
            self.screen.blit(tt, (sx+8+st.get_width()+4, my))

        if self.is_fan:
            cy2 = WIN_H-88
            cl  = self.F["small"].render("CHEER", True, CHEER_C)
            self.screen.blit(cl, (sx+12, cy2))
            for i,lbl in enumerate(self.cheer_labels):
                btn = self._cheer_rect(i)
                col = self.cheer_colors[i]
                rr(self.screen, (*col, 55), btn, 5)
                rrb(self.screen, col, btn, 5, 1)
                lt = self.F["tiny"].render(lbl, True, TEXT_BRIGHT)
                self.screen.blit(lt, (btn.centerx-lt.get_width()//2, btn.centery-lt.get_height()//2))

        self.chat_inp.rect = pygame.Rect(sx+6, WIN_H-44, SIDEBAR-12, 36)
        self.chat_inp.draw(self.screen)
        h_t = self.F["tiny"].render("/pm user  for private", True, TEXT_DIM)
        self.screen.blit(h_t, (sx+8, WIN_H-58))

    def _cheer_rect(self, i):
        sx = GRID_W*CELL
        bw = (SIDEBAR-28)//len(self.cheer_labels)
        return pygame.Rect(sx+8+i*(bw+2), WIN_H-68, bw, 22)

    # ── Game Over ─────────────────────────────────────────────────────────────
    def _draw_gameover(self):
        ov = pygame.Surface((WIN_W,WIN_H), pygame.SRCALPHA)
        ov.fill((4,6,14,205))
        self.screen.blit(ov,(0,0))

        gcx = (GRID_W*CELL)//2
        gcy = (TOP_H+GRID_H*CELL)//2

        go     = self.game_over or {}
        winner = go.get("winner","draw")
        scores = go.get("scores",{})

        # Card
        card = pygame.Rect(gcx-240, gcy-145, 480, 320)
        rr(self.screen, (12,14,26), card, 16)
        w_col = P0_HEAD if winner==self.username else P1_HEAD if winner!="draw" else ACCENT
        rrb(self.screen, w_col, card, 16, 2)

        # Glow bar at top of card
        pygame.draw.rect(self.screen, w_col, (card.x+2, card.y, card.w-4, 4), border_radius=16)

        # Title
        if winner=="draw":   w_txt,w_col = "DRAW!", ACCENT
        elif winner==self.username: w_txt,w_col = "YOU WIN!", P0_HEAD
        else:                w_txt,w_col = f"{winner} WINS!", P1_HEAD
        wt = self.F["title"].render(w_txt, True, w_col)
        gs = pygame.Surface((wt.get_width()+60, wt.get_height()+20), pygame.SRCALPHA)
        gs.fill((*w_col[:3], 28))
        self.screen.blit(gs, (gcx-gs.get_width()//2, gcy-125))
        self.screen.blit(wt, (gcx-wt.get_width()//2, gcy-122))

        pygame.draw.line(self.screen, BORDER, (card.x+24,gcy-65),(card.right-24,gcy-65))

        # Scores
        items = list(scores.items())
        for i,(name,hp) in enumerate(items):
            col = [P0_HEAD,P1_HEAD][i]
            ys  = gcy-50+i*40
            nt  = self.F["h2"].render(name, True, col)
            self.screen.blit(nt, (gcx-220, ys))
            draw_hp(self.screen, gcx-220, ys+26, 290, 12, hp, MAX_HEALTH)
            ht  = self.F["small"].render(f"{hp} HP", True, col)
            self.screen.blit(ht, (gcx+80, ys+24))

        # Buttons
        self.btn_rematch.rect = pygame.Rect(gcx-232, gcy+90, 215, 48)
        self.btn_lobby.rect   = pygame.Rect(gcx+17,  gcy+90, 215, 48)
        self.btn_rematch.draw(self.screen)
        self.btn_lobby.draw(self.screen)

        hint = self.F["tiny"].render("Rematch to play again   |   Back to Lobby to wait for a new game", True, TEXT_DIM)
        self.screen.blit(hint, (gcx-hint.get_width()//2, gcy+150))

        self._draw_sidebar(self.game_data)


if __name__ == "__main__":
    client = PithonArenaClient()
    client.run()