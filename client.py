"""
Pithon Arena  |  Professional Client
"""
import sys, socket, threading, queue, time, math, random
import pygame, pygame.gfxdraw
from protocol import *

# ── Constants ──────────────────────────────────────────────────────────────────
CELL    = 26
SIDEBAR = 340
TOP_H   = 84
WIN_W   = GRID_W * CELL + SIDEBAR
WIN_H   = GRID_H * CELL + TOP_H
FPS     = 60

# Grid center (game area only, no sidebar)
GCX     = (GRID_W * CELL) // 2
GCY     = TOP_H + (GRID_H * CELL) // 2

# ── Design tokens ──────────────────────────────────────────────────────────────
BG          = (  5,   6,  12)
SURFACE     = (  9,  11,  20)
SURFACE2    = ( 13,  16,  28)
SURFACE3    = ( 18,  22,  38)
OUTLINE     = ( 32,  38,  72)
OUTLINE2    = ( 52,  60, 110)

P0          = ( 20, 240, 120)    # Mint green
P0_DIM      = ( 12, 148,  74)
P0_GLOW     = ( 80, 255, 170)
P1          = (255,  48,  96)    # Vivid red
P1_DIM      = (158,  28,  58)
P1_GLOW     = (255, 120, 155)
DEAD_C      = ( 44,  47,  62)

PIE_GOLD    = (255, 208,  32)
PIE_NORM    = (255, 122,  24)
PIE_ROT     = ( 64, 192,  64)
OBS_ROCK    = ( 76,  82, 108)
OBS_SPIKE   = (120, 130, 175)

TEXT_PRI    = (255, 255, 255)
TEXT_SEC    = (185, 190, 215)
TEXT_TER    = ( 95, 100, 138)
TEXT_DIS    = ( 52,  56,  82)
ACCENT_BLU  = ( 48, 172, 255)
ACCENT_PUR  = (140,  80, 255)
GOLD_C      = (255, 192,  24)
SUCCESS     = ( 40, 210,  96)
DANGER      = (255,  48,  72)
CHEER_C     = (255, 196,  32)

HP_HI       = ( 36, 208,  88)
HP_MID      = (212, 180,  28)
HP_LO       = (212,  44,  56)

GRID_EVEN   = (  9,  11,  21)
GRID_ODD    = (  7,   9,  17)
GRID_LINE_C = ( 15,  17,  31)
WALL_COL    = ( 44,  50,  96)

CHAT_PALETTE = [
    ( 64, 196, 255), ( 64, 255, 152), (255, 152,  48),
    (196,  80, 255), (255,  80, 144), ( 48, 212, 196),
    (255, 212,  48), (152, 255,  80),
]

S_CONNECT = "connect"
S_LOBBY   = "lobby"
S_GAME    = "game"
S_OVER    = "over"

FONT_REG  = "/usr/share/fonts/truetype/google-fonts/Poppins-Regular.ttf"
FONT_MED  = "/usr/share/fonts/truetype/google-fonts/Poppins-Medium.ttf"
FONT_BOLD = "/usr/share/fonts/truetype/google-fonts/Poppins-Bold.ttf"
FONT_MONO = None  # will use system monospace

# ── Helpers ────────────────────────────────────────────────────────────────────
def lerp(a, b, t):
    t = max(0.0, min(1.0, t))
    return tuple(int(a[i] + (b[i]-a[i])*t) for i in range(3))

def easeout3(t): return 1-(1-min(1.,t))**3
def easeout5(t): return 1-(1-min(1.,t))**5
def easein2(t):  return min(1.,t)**2
def spring(t):   return 1 - math.exp(-12*t)*math.cos(8*t) if t<1 else 1

def hp_col(ratio):
    if ratio > 0.5: return lerp(HP_MID, HP_HI, (ratio-0.5)*2)
    return lerp(HP_LO, HP_MID, ratio*2)

def aacircle(surf, col, pos, r):
    if r < 1: return
    x, y, r = int(pos[0]), int(pos[1]), max(1, int(r))
    try:
        pygame.gfxdraw.aacircle(surf, x, y, r, (*col[:3], col[3] if len(col)>3 else 255))
        pygame.gfxdraw.filled_circle(surf, x, y, r, (*col[:3], col[3] if len(col)>3 else 255))
    except: pass

def rrect(surf, col, rect, r=8):
    pygame.draw.rect(surf, col, rect, border_radius=r)

def rrect_border(surf, col, rect, r=8, w=1):
    pygame.draw.rect(surf, col, rect, w, border_radius=r)

def make_glow_surf(w, h, col, alpha=60, radius=16):
    """Create a blurred glow surface."""
    s = pygame.Surface((w, h), pygame.SRCALPHA)
    for i in range(3):
        a = alpha // (i+1)
        inflate = (i+1) * 4
        r = pygame.Rect(inflate, inflate, w-inflate*2, h-inflate*2)
        if r.width > 0 and r.height > 0:
            pygame.draw.rect(s, (*col[:3], a), r, border_radius=radius+inflate)
    return s

def glow_behind(surf, col, rect, spread=16, alpha=50, r=10):
    g = make_glow_surf(rect.width+spread*2, rect.height+spread*2, col, alpha, r+spread//2)
    surf.blit(g, (rect.x-spread, rect.y-spread))

def circle_glow(surf, col, pos, radius, spread=20, alpha=50):
    total = radius + spread
    g = pygame.Surface((total*2, total*2), pygame.SRCALPHA)
    for i in range(4):
        a = alpha // (i+1)
        r2 = total - i*spread//4
        if r2 > 0:
            pygame.draw.circle(g, (*col[:3], a), (total, total), r2)
    surf.blit(g, (int(pos[0])-total, int(pos[1])-total))

# ── Font system ────────────────────────────────────────────────────────────────
def load_fonts():
    import os
    def poppins(size, weight="regular"):
        paths = {
            "regular": FONT_REG,
            "medium":  FONT_MED,
            "bold":    FONT_BOLD,
        }
        p = paths.get(weight, FONT_REG)
        if p and os.path.exists(p):
            return pygame.font.Font(p, size)
        return pygame.font.SysFont("freesans", size, bold=(weight=="bold"))

    mono_path = None
    for name in ["consolas","cascadiacode","couriernew","dejavusansmono"]:
        p = pygame.font.match_font(name)
        if p: mono_path = p; break

    def mono(size):
        if mono_path: return pygame.font.Font(mono_path, size)
        return pygame.font.SysFont("monospace", size)

    return {
        # Display
        "display":    poppins(52, "bold"),
        "title":      poppins(38, "bold"),
        "h1":         poppins(28, "bold"),
        "h2":         poppins(21, "bold"),
        "h3":         poppins(17, "medium"),
        # Body
        "body_lg":    poppins(18, "regular"),
        "body":       poppins(16, "regular"),
        "body_med":   poppins(16, "medium"),
        "sm":         poppins(13, "medium"),
        "xs":         poppins(11, "regular"),
        # Special
        "timer":      poppins(56, "bold"),
        "countdown":  poppins(120, "bold"),
        # Mono
        "chat_name":  poppins(13, "bold"),
        "chat_msg":   mono(15),
        "mono_sm":    mono(12),
    }

# ── Tweening ───────────────────────────────────────────────────────────────────
class Tween:
    def __init__(self, start=0., end=1., duration=0.3, ease=easeout3, delay=0.):
        self.start = start; self.end = end
        self.duration = duration; self.ease = ease; self.delay = delay
        self._t = 0.; self._elapsed = 0.

    def update(self, dt):
        self._elapsed = min(self._elapsed+dt, self.delay+self.duration)
        t = max(0., self._elapsed - self.delay)
        self._t = self.ease(t / self.duration) if self.duration > 0 else 1.
        return self.value

    @property
    def value(self):
        return self.start + (self.end-self.start)*self._t

    @property
    def done(self): return self._elapsed >= self.delay+self.duration

    def reset(self):
        self._elapsed = 0.; self._t = 0.

# ── Particle system ────────────────────────────────────────────────────────────
class Particle:
    __slots__ = ['x','y','vx','vy','col','life','decay','sz','grav']
    def __init__(self, x, y, col, spd=None, sz=None, grav=0.09, life_range=(0.6,1.0)):
        a = random.uniform(0, math.tau)
        s = spd if spd is not None else random.uniform(2, 6)
        self.x, self.y = float(x), float(y)
        self.vx, self.vy = math.cos(a)*s, math.sin(a)*s - random.uniform(0.5,2)
        self.col = col
        self.life = random.uniform(*life_range)
        self.decay = random.uniform(0.018, 0.045)
        self.sz = sz if sz is not None else random.uniform(2.5, 6.5)
        self.grav = grav

    def tick(self, dt):
        self.x += self.vx; self.y += self.vy
        self.vy += self.grav; self.life -= self.decay
        return self.life > 0

    def draw(self, surf):
        s = max(1, int(self.sz * self.life))
        a = min(255, int(240 * self.life))
        t = pygame.Surface((s*2+2, s*2+2), pygame.SRCALPHA)
        pygame.draw.circle(t, (*self.col[:3], a), (s+1, s+1), s)
        surf.blit(t, (int(self.x)-s, int(self.y)-s))

def emit(particles, x, y, col, n=20, spd=(1.5,6), sz=(2,8)):
    for _ in range(n):
        particles.append(Particle(x, y, col,
            spd=random.uniform(*spd),
            sz=random.uniform(*sz)))

def confetti_burst(particles, cx, cy, n=80):
    colors = [P0, P1, GOLD_C, ACCENT_BLU, TEXT_PRI, SUCCESS]
    for _ in range(n):
        x = cx + random.randint(-180, 180)
        y = cy + random.randint(-100, 100)
        emit(particles, x, y, random.choice(colors), n=1, spd=(2,8), sz=(3,9))

# ── HP bar component ───────────────────────────────────────────────────────────
def draw_hp_bar(surf, x, y, w, h, val, mx, accent=None):
    ratio = max(0., min(1., val/mx))
    # Track
    rrect(surf, SURFACE, pygame.Rect(x, y, w, h), h//2)
    if ratio > 0:
        col = hp_col(ratio)
        fw = max(h, int(w * ratio))
        rrect(surf, col, pygame.Rect(x, y, fw, h), h//2)
        # Shine
        if fw > 12:
            shine = pygame.Surface((fw//3, h), pygame.SRCALPHA)
            shine.fill((*TEXT_PRI, 30))
            surf.blit(shine, (x + fw//3, y))
        # Glow when low
        if ratio < 0.3 and accent:
            glow_behind(surf, col, pygame.Rect(x,y,fw,h), 4, 40, h//2)
    rrect_border(surf, OUTLINE, pygame.Rect(x, y, w, h), h//2, 1)

# ── Network ────────────────────────────────────────────────────────────────────
class NetThread(threading.Thread):
    def __init__(self, host, port, q):
        super().__init__(daemon=True)
        self.host, self.port, self.q = host, port, q
        self._sock = None; self._sq = queue.Queue()
        self._buf = b""; self.ok = False

    def run(self):
        try:
            self._sock = socket.socket()
            self._sock.connect((self.host, self.port))
            self.ok = True
            threading.Thread(target=self._send_loop, daemon=True).start()
            self._recv_loop()
        except Exception as e:
            self.q.put({"type": "_ERR", "reason": str(e)})

    def _recv_loop(self):
        while True:
            try:    chunk = self._sock.recv(4096)
            except: self.q.put({"type":"_ERR","reason":"Disconnected"}); return
            if not chunk: self.q.put({"type":"_ERR","reason":"Server closed"}); return
            self._buf += chunk
            while b"\n" in self._buf:
                line, self._buf = self._buf.split(b"\n", 1)
                try: self.q.put(decode(line+b"\n"))
                except: pass

    def _send_loop(self):
        while True:
            m = self._sq.get()
            if m is None: break
            try: self._sock.sendall(encode(m))
            except: break

    def send(self, m):
        if self.ok: self._sq.put(m)

# ── Input field ────────────────────────────────────────────────────────────────
class TextField:
    def __init__(self, rect, F, placeholder="", maxlen=40):
        self.rect = pygame.Rect(rect); self.F = F
        self.placeholder = placeholder; self.maxlen = maxlen
        self.text = ""; self.focused = False
        self._cursor = True; self._cursor_t = 0
        self._focus_tween = Tween(0, 1, 0.2, easeout3)

    def handle(self, ev):
        if ev.type == pygame.MOUSEBUTTONDOWN:
            prev = self.focused
            self.focused = self.rect.collidepoint(ev.pos)
            if self.focused and not prev:
                self._focus_tween = Tween(0, 1, 0.2, easeout3)
        if ev.type == pygame.KEYDOWN and self.focused:
            if ev.key == pygame.K_BACKSPACE: self.text = self.text[:-1]
            elif ev.key not in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_TAB):
                if len(self.text) < self.maxlen and ev.unicode.isprintable():
                    self.text += ev.unicode
            return ev.key in (pygame.K_RETURN, pygame.K_KP_ENTER)
        return False

    def draw(self, surf, dt, label=None):
        fv = self._focus_tween.update(dt)

        # Label
        if label:
            lc = lerp(TEXT_TER, TEXT_SEC, fv)
            lt = self.F["sm"].render(label, True, lc)
            surf.blit(lt, (self.rect.x, self.rect.y - lt.get_height() - 7))

        # Glow
        if fv > 0.05:
            glow_behind(surf, ACCENT_BLU, self.rect, int(20*fv), int(45*fv), 10)

        # Background
        bg = lerp(SURFACE, SURFACE3, fv)
        rrect(surf, bg, self.rect, 10)

        # Border — animates from dim to accent
        border_col = lerp(OUTLINE, ACCENT_BLU, fv)
        rrect_border(surf, border_col, self.rect, 10, 2)

        # Text or placeholder
        if self.text:
            ts = self.F["body"].render(self.text, True, TEXT_PRI)
            surf.blit(ts, (self.rect.x+16, self.rect.centery - ts.get_height()//2))
        else:
            ph = self.F["body"].render(self.placeholder, True, TEXT_DIS)
            surf.blit(ph, (self.rect.x+16, self.rect.centery - ph.get_height()//2))

        # Cursor
        if self.focused:
            now = pygame.time.get_ticks()
            if now - self._cursor_t > 530:
                self._cursor = not self._cursor; self._cursor_t = now
            if self._cursor:
                cx2 = self.rect.x + 16 + self.F["body"].size(self.text)[0] + 1
                cy2 = self.rect.centery
                pygame.draw.line(surf, ACCENT_BLU, (cx2, cy2-10), (cx2, cy2+10), 2)

# ── Button ─────────────────────────────────────────────────────────────────────
class Button:
    def __init__(self, rect, text, F, variant="primary"):
        self.rect = pygame.Rect(rect); self.text = text; self.F = F
        self.variant = variant
        self._hover_t = Tween(0, 1, 0.15, easeout3)
        self._press_t = 0
        self._hovered = False

    def _colors(self):
        v = self.variant
        if v == "primary":   return P0, BG, P0_GLOW
        if v == "danger":    return P1, TEXT_PRI, P1_GLOW
        if v == "secondary": return SURFACE3, TEXT_SEC, ACCENT_BLU
        if v == "accent":    return ACCENT_BLU, BG, ACCENT_BLU
        if v == "cancel":    return (50, 14, 20), DANGER, DANGER
        return SURFACE3, TEXT_SEC, OUTLINE2

    def handle(self, ev):
        if ev.type == pygame.MOUSEMOTION:
            prev = self._hovered
            self._hovered = self.rect.collidepoint(ev.pos)
            if self._hovered != prev:
                self._hover_t = Tween(0 if self._hovered else 1,
                                      1 if self._hovered else 0, 0.15, easeout3)
        if ev.type == pygame.MOUSEBUTTONDOWN and self.rect.collidepoint(ev.pos):
            self._press_t = pygame.time.get_ticks(); return True
        return False

    def draw(self, surf, dt):
        hv = self._hover_t.update(dt)
        pressed = pygame.time.get_ticks() - self._press_t < 130
        bg, fg, glow_c = self._colors()

        col = lerp(bg, lerp(bg, TEXT_PRI, 0.15), hv)
        if pressed: col = lerp(col, BG, 0.35)

        if hv > 0.05:
            glow_behind(surf, glow_c, self.rect, int(18*hv), int(40*hv), 10)

        rrect(surf, col, self.rect, 10)

        if self.variant == "secondary":
            rrect_border(surf, lerp(OUTLINE, OUTLINE2, hv), self.rect, 10, 1)
        if self.variant == "cancel":
            rrect_border(surf, DANGER, self.rect, 10, 1)

        ts = self.F["h2"].render(self.text, True, fg)
        surf.blit(ts, (self.rect.centerx - ts.get_width()//2,
                       self.rect.centery - ts.get_height()//2))

# ── Scanlines (subtle CRT effect) ─────────────────────────────────────────────
_SL = None
def scanlines(surf):
    global _SL
    w, h = surf.get_size()
    if _SL is None or _SL.get_size() != (w, h):
        _SL = pygame.Surface((w, h), pygame.SRCALPHA)
        for y in range(0, h, 4):
            pygame.draw.line(_SL, (0,0,0,12), (0,y), (w,y))
    surf.blit(_SL, (0,0))

# ── Main client ────────────────────────────────────────────────────────────────
class Arena:
    def __init__(self):
        pygame.init()
        pygame.mixer.init()
        self.screen = pygame.display.set_mode((WIN_W, WIN_H))
        pygame.display.set_caption("Pithon Arena")
        self.clock  = pygame.time.Clock()
        self.F      = load_fonts()
        self._music_playing = False
        self._load_music()
        self._dt    = 0.
        self._t     = 0.

        # Net
        self.net    = None
        self.q      = queue.Queue()

        # State
        self.state      = S_CONNECT
        self.username   = None
        self.pid        = None
        self.is_fan     = False
        self.gdata      = None
        self.gover      = None
        self.lobby_list = []
        self.ready_list = []
        self.i_ready    = False
        self.chat_log   = []
        self._ucols     = {}
        self.cheers     = []
        self.particles  = []
        self.countdown  = None
        self._cd_t      = 0.
        self.conn_msg   = ""
        self.conn_ok    = False
        self._dmg_flash = [0., 0.]
        self._prev_hp   = [None, None]
        self._shake     = 0.
        self._shake_off = (0, 0)
        self._screen_alpha = Tween(0, 1, 0.4, easeout3)

        self.key_map = {
            pygame.K_UP:"UP", pygame.K_DOWN:"DOWN",
            pygame.K_LEFT:"LEFT", pygame.K_RIGHT:"RIGHT",
            pygame.K_w:"UP", pygame.K_s:"DOWN",
            pygame.K_a:"LEFT", pygame.K_d:"RIGHT",
        }
        self._build()

    def _load_music(self):
        import os
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Before_The_Timer_Ends.mp3")
        try:
            pygame.mixer.music.load(path)
            pygame.mixer.music.set_volume(0.45)
        except Exception as e:
            print(f"[music] Could not load: {e}")

    def _start_music(self):
        if not self._music_playing:
            try:
                pygame.mixer.music.play(-1)  # -1 = loop forever
                self._music_playing = True
            except Exception as e:
                print(f"[music] Could not play: {e}")

    def _build(self):
        cx = WIN_W // 2
        self.tf_host = TextField(pygame.Rect(cx-190,316,380,50),self.F,"e.g.  127.0.0.1",64)
        self.tf_port = TextField(pygame.Rect(cx-190,400,170,50),self.F,"Port",6)
        self.tf_user = TextField(pygame.Rect(cx-190,484,380,50),self.F,"Username",20)
        self.tf_host.text = "127.0.0.1"; self.tf_port.text = "5555"
        self._cfields = [self.tf_host, self.tf_port, self.tf_user]

        sx = GRID_W * CELL
        self.tf_chat = TextField(pygame.Rect(sx+10, WIN_H-52, SIDEBAR-20, 42), self.F, "Send a message...", 150)
        self.btn_connect = Button(pygame.Rect(cx-120,556,240,54),"Connect",self.F,"primary")
        self.btn_ready   = Button(pygame.Rect(100,100,240,54),"Ready Up",self.F,"primary")
        self.btn_watch   = Button(pygame.Rect(100,100,210,44),"Watch as Fan",self.F,"secondary")
        self.btn_rematch = Button(pygame.Rect(100,100,220,54),"Rematch",self.F,"primary")
        self.btn_lobby   = Button(pygame.Rect(100,100,220,54),"Back to Lobby",self.F,"secondary")

    # ── Loop ──────────────────────────────────────────────────────────────────
    def run(self):
        while True:
            self._dt = self.clock.tick(FPS) / 1000.
            self._t += self._dt

            # Shake decay
            self._shake = max(0., self._shake - self._dt * 9.)
            if self._shake > 0:
                a = random.uniform(0, math.tau); amp = self._shake * 8
                self._shake_off = (int(math.cos(a)*amp), int(math.sin(a)*amp))
            else: self._shake_off = (0, 0)

            # Damage flash decay
            for i in range(2):
                self._dmg_flash[i] = max(0., self._dmg_flash[i] - self._dt*2.8)

            while not self.q.empty(): self._on(self.q.get_nowait())
            self._events()
            self.particles = [p for p in self.particles if p.tick(self._dt)]
            self._draw()
            pygame.display.flip()

    # ── Messages ──────────────────────────────────────────────────────────────
    def _on(self, msg):
        t = msg.get("type")
        if t == "_ERR":
            self.conn_msg = msg.get("reason","Error"); self.conn_ok = False
            self.state = S_CONNECT; self._fade_in()
        elif t == MSG_JOIN_OK:
            self.username = msg["username"]; self.state = S_LOBBY; self._fade_in()
            self._start_music()
        elif t == MSG_JOIN_ERR:
            self.conn_msg = msg.get("reason","Error"); self.conn_ok = False
        elif t == MSG_PLAYER_LIST:
            self.lobby_list = msg.get("players",[])
        elif t == MSG_READY_STATUS:
            self.ready_list = msg.get("ready",[])
            self.i_ready = self.username in self.ready_list
        elif t == MSG_GAME_START:
            self.pid = msg.get("your_id"); self.is_fan = False
            self.state = S_GAME; self.gover = None; self.gdata = None
            self.countdown = None; self._prev_hp = [None,None]
            self._fade_in()
        elif t == MSG_WATCH_OK:
            self.is_fan = True; self.state = S_GAME; self.gover = None; self._fade_in()
        elif t == MSG_GAME_STATE:
            if self.gdata:
                for i, sn in enumerate(msg.get("snakes",[])):
                    old = self._prev_hp[i]; new = sn.get("health",0)
                    if old is not None and new < old:
                        self._dmg_flash[i] = 1.0
                        self._shake = min(1., self._shake + 0.55)
                        body = sn.get("body",[])
                        if body:
                            hx,hy = body[0]
                            sx2 = hx*CELL+CELL//2; sy2 = hy*CELL+TOP_H+CELL//2
                            col = [P0,P1][i]
                            emit(self.particles,sx2,sy2,col,n=14,spd=(2,5),sz=(3,6))
                            emit(self.particles,sx2,sy2,TEXT_PRI,n=5,spd=(1,3),sz=(2,4))
                    self._prev_hp[i] = new
            self.gdata = msg
        elif t == MSG_COUNTDOWN:
            self.countdown = msg.get("count"); self._cd_t = self._t
        elif t == MSG_GAME_OVER:
            self.gover = msg; self.state = S_OVER; self._fade_in()
            if msg.get("winner") == self.username:
                confetti_burst(self.particles, GCX, GCY)
        elif t == MSG_CHAT_RECV:
            s = msg.get("from","?"); tx = msg.get("text","")
            prv = msg.get("private",False)
            if s not in self._ucols:
                self._ucols[s] = CHAT_PALETTE[len(self._ucols)%len(CHAT_PALETTE)]
            self.chat_log.append((s, ("[PM] " if prv else "")+tx, self._ucols[s]))
            if len(self.chat_log) > 120: self.chat_log.pop(0)
        elif t == MSG_CHEER_RECV:
            self.cheers.append((
                f"{msg.get('from','?')}: {msg.get('emoji','!')} for {msg.get('player','')}!",
                time.time()+4.))

    def _fade_in(self):
        self._screen_alpha = Tween(0, 1, 0.35, easeout3)

    # ── Events ────────────────────────────────────────────────────────────────
    def _events(self):
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT: pygame.quit(); sys.exit()

            if self.state == S_CONNECT:
                for f in self._cfields:
                    if f.handle(ev): self._connect()
                if self.btn_connect.handle(ev): self._connect()

            elif self.state == S_LOBBY:
                if self.btn_watch.handle(ev) and self.net:
                    self.net.send({"type":MSG_WATCH})
                if self.btn_ready.handle(ev) and self.net:
                    if self.i_ready:
                        self.net.send({"type":MSG_UNREADY}); self.i_ready=False
                    else:
                        self.net.send({"type":MSG_READY}); self.i_ready=True

            elif self.state == S_GAME:
                if self.tf_chat.handle(ev): self._send_chat()
                if ev.type == pygame.KEYDOWN and not self.is_fan and not self.tf_chat.focused:
                    d = self.key_map.get(ev.key)
                    if d and self.net: self.net.send({"type":MSG_INPUT,"direction":d})

            elif self.state == S_OVER:
                self.tf_chat.handle(ev)
                if ev.type == pygame.KEYDOWN and ev.key == pygame.K_RETURN:
                    self._send_chat()
                if self.btn_rematch.handle(ev) and self.net:
                    self.net.send({"type":MSG_REMATCH})
                if self.btn_lobby.handle(ev) and self.net:
                    self.net.send({"type":MSG_LEAVE}); self._to_lobby()

    def _send_chat(self):
        txt = self.tf_chat.text.strip()
        if txt and self.net:
            if txt.startswith("/pm "):
                p = txt[4:].split(" ",1)
                if len(p)==2: self.net.send({"type":MSG_CHAT,"to":p[0],"text":p[1]})
            else: self.net.send({"type":MSG_CHAT,"to":None,"text":txt})
        self.tf_chat.text = ""

    def _connect(self):
        host=self.tf_host.text.strip(); port=self.tf_port.text.strip(); user=self.tf_user.text.strip()
        if not host or not port or not user:
            self.conn_msg="Please fill in all fields."; self.conn_ok=False; return
        try: pn=int(port)
        except: self.conn_msg="Port must be a number."; self.conn_ok=False; return
        self.conn_msg="Connecting..."; self.conn_ok=True
        self.net=NetThread(host,pn,self.q); self.net.start()
        def _j(): time.sleep(0.35); self.net.send({"type":MSG_JOIN,"username":user})
        threading.Thread(target=_j,daemon=True).start()

    def _to_lobby(self):
        self.state=S_LOBBY; self.gdata=None; self.gover=None
        self.pid=None; self.is_fan=False; self.countdown=None
        self.i_ready=False; self.ready_list=[]
        self._fade_in()

    # ── Draw ──────────────────────────────────────────────────────────────────
    def _draw(self):
        dt = self._dt
        self.screen.fill(BG)

        if self.state == S_CONNECT:
            self._draw_connect()
        elif self.state == S_LOBBY:
            self._draw_lobby()
        elif self.state in (S_GAME, S_OVER):
            off = self._shake_off
            if off != (0,0):
                tmp = pygame.Surface((GRID_W*CELL, WIN_H))
                tmp.fill(BG)
                self._draw_grid(tmp, -off[0], -off[1])
                self.screen.blit(tmp, off)
            else:
                self._draw_grid(self.screen, 0, 0)
            self._draw_topbar()
            self._draw_sidebar()
            if self.countdown is not None and self.countdown > 0:
                self._draw_countdown()
            elif self.state == S_OVER:
                self._draw_over()

        # Particles
        for p in self.particles: p.draw(self.screen)

        # Scanlines
        scanlines(self.screen)

        # Fade-in overlay
        alpha = self._screen_alpha.update(dt)
        if alpha < 0.999:
            ov = pygame.Surface((WIN_W,WIN_H))
            ov.fill(BG)
            ov.set_alpha(int(255*(1-alpha)))
            self.screen.blit(ov,(0,0))

    # ── Connect screen ─────────────────────────────────────────────────────────
    def _draw_connect(self):
        t = self._t; cx = WIN_W//2; dt = self._dt

        # Subtle animated dot field
        for i in range(40):
            random.seed(i * 7919)
            bx = random.randint(0,WIN_W); by = random.randint(0,WIN_H)
            spd = random.uniform(0.3,1.1); ph = random.uniform(0,math.tau)
            random.seed()
            a = int(20+15*math.sin(t*spd+ph))
            r2 = 1 if random.random()<0.7 else 2
            aacircle(self.screen, (*TEXT_TER,a), (bx,by), r2)

        # Vertical gradient lines (subtle)
        for x in range(0, WIN_W, 80):
            a = int(8+5*math.sin(t*0.5+x*0.02))
            pygame.draw.line(self.screen, (*OUTLINE,a), (x,0),(x,WIN_H))

        # Snakes
        for side in range(2):
            c = P0 if side==0 else P1; g = P0_GLOW if side==0 else P1_GLOW
            for i in range(10):
                px = (60+i*28) if side==0 else (WIN_W-60-i*28)
                py = int(WIN_H//2+60*math.sin(t*1.5+i*0.65+side*math.pi))
                a2 = max(0, 230-i*23); sz = max(5,22-i*2)
                if i==0: circle_glow(self.screen, g, (px,py), sz//2, 14, 50)
                s = pygame.Surface((sz,sz),pygame.SRCALPHA); s.fill((*c,a2))
                self.screen.blit(s,(px-sz//2,py-sz//2))

        # Card
        cw,ch = 460,415
        card = pygame.Rect(cx-cw//2, 230, cw, ch)
        cs = pygame.Surface((cw,ch),pygame.SRCALPHA); cs.fill((6,7,14,250))
        self.screen.blit(cs, card.topleft)
        # Animated top accent bar
        pulse = 0.5+0.5*math.sin(t*2.2)
        tc = lerp(ACCENT_BLU, P0, pulse)
        pygame.draw.rect(self.screen, tc, (card.x,card.y,cw,3), border_radius=14)
        rrect_border(self.screen, OUTLINE, card, 14, 1)

        # Title
        title = self.F["title"].render("PITHON  ARENA", True, TEXT_PRI)
        glow_behind(self.screen, P0, pygame.Rect(cx-title.get_width()//2-10,160,title.get_width()+20,title.get_height()),8,14,20)
        self.screen.blit(title,(cx-title.get_width()//2,162))
        sub = self.F["body"].render("Real-time Online Snake Battle  |  EECE 350", True, TEXT_TER)
        self.screen.blit(sub,(cx-sub.get_width()//2,212))

        for f,lbl in [(self.tf_host,"Server IP Address"),(self.tf_port,"Port"),(self.tf_user,"Username")]:
            f.draw(self.screen, dt, lbl)
        self.btn_connect.draw(self.screen, dt)

        if self.conn_msg:
            col = SUCCESS if self.conn_ok else DANGER
            dots = "."*(int(t*3)%4) if self.conn_ok else ""
            mt = self.F["body_med"].render(self.conn_msg+dots, True, col)
            self.screen.blit(mt,(cx-mt.get_width()//2,620))

        hint = self.F["xs"].render("WASD / Arrow Keys to move   |   /pm username message for private chat", True, TEXT_DIS)
        self.screen.blit(hint,(cx-hint.get_width()//2,WIN_H-20))

    # ── Lobby ─────────────────────────────────────────────────────────────────
    def _draw_lobby(self):
        t = self._t; cx = WIN_W//2; dt = self._dt

        # Ambient particle field (static seed)
        for i in range(25):
            random.seed(i*6271)
            bx=random.randint(0,WIN_W); by=random.randint(0,WIN_H)
            sp=random.uniform(0.2,0.8); ph=random.uniform(0,math.tau)
            random.seed()
            a=int(18+12*math.sin(t*sp+ph))
            aacircle(self.screen,(*TEXT_DIS,a),(bx,by),1)

        # Header
        hb = pygame.Surface((WIN_W,76),pygame.SRCALPHA); hb.fill((5,6,12,255))
        self.screen.blit(hb,(0,0))
        # Animated color line at bottom of header
        for px2 in range(WIN_W):
            pv = px2/WIN_W
            a = int(100*(0.5+0.5*math.sin(pv*6+t*1.8)))
            c = lerp(ACCENT_BLU, P0, pv)
            pygame.draw.line(self.screen,(*c,a),(px2,75),(px2,76))
        pygame.draw.line(self.screen,OUTLINE,(0,76),(WIN_W,76))

        logo = self.F["h1"].render("PITHON  ARENA", True, TEXT_PRI)
        glow_behind(self.screen,P0,pygame.Rect(18,18,logo.get_width()+4,logo.get_height()),6,10,14)
        self.screen.blit(logo,(20,20))
        if self.username:
            u = self.F["body_med"].render(f"Signed in as  {self.username}", True, ACCENT_BLU)
            self.screen.blit(u,(WIN_W-u.get_width()-22,26))

        # Player list card
        pw,ph2 = 540,300
        panel = pygame.Rect(cx-pw//2, 94, pw, ph2)
        ps = pygame.Surface((pw,ph2),pygame.SRCALPHA); ps.fill((6,7,14,245))
        self.screen.blit(ps,panel.topleft)
        rrect_border(self.screen,OUTLINE,panel,12,1)

        ht = self.F["h2"].render("Players", True, TEXT_PRI)
        self.screen.blit(ht,(panel.x+20,panel.y+18))
        pygame.draw.line(self.screen,OUTLINE,(panel.x+16,panel.y+54),(panel.right-16,panel.y+54),1)

        if not self.lobby_list:
            wt = self.F["body"].render("Waiting for players...", True, TEXT_TER)
            self.screen.blit(wt,(panel.centerx-wt.get_width()//2,panel.y+110))
        else:
            for i,name in enumerate(self.lobby_list[:6]):
                ry=panel.y+62+i*38; is_me=name==self.username; is_rdy=name in self.ready_list
                row=pygame.Rect(panel.x+10,ry,pw-20,32)
                rbg=(18,24,48) if is_me else (10,12,24)
                rrect(self.screen,rbg,row,7)
                if is_me: rrect_border(self.screen,(*P0,80),row,7,1)
                # Dot
                dc=P0 if is_rdy else ACCENT_BLU
                if is_rdy: circle_glow(self.screen,dc,(panel.x+27,ry+16),6,8,45)
                aacircle(self.screen,dc,(panel.x+27,ry+16),6)
                # Name
                nc=TEXT_PRI if is_me else TEXT_SEC
                nt=self.F["body_med"].render(name+("  (you)" if is_me else ""),True,nc)
                self.screen.blit(nt,(panel.x+46,ry+6))
                if is_rdy:
                    rb=self.F["xs"].render("READY",True,GOLD_C)
                    rbr=pygame.Rect(panel.right-68,ry+8,56,16)
                    rrect(self.screen,(38,30,0),rbr,4)
                    rrect_border(self.screen,GOLD_C,rbr,4,1)
                    self.screen.blit(rb,(rbr.centerx-rb.get_width()//2,rbr.centery-rb.get_height()//2))

        # Status
        rc=len(self.ready_list); dots="."*(int(t*2)%4)
        if self.i_ready:
            st=self.F["body_med"].render(f"You are ready!  ({rc}/2){dots}",True,SUCCESS)
        elif rc>0:
            st=self.F["body_med"].render(f"{rc}/2 ready — join them!",True,GOLD_C)
        else:
            st=self.F["body"].render(f"Waiting for players{dots}",True,TEXT_TER)
        self.screen.blit(st,(cx-st.get_width()//2,panel.bottom+18))

        # Ready button
        self.btn_ready.rect=pygame.Rect(cx-120,panel.bottom+52,240,54)
        if self.i_ready:
            self.btn_ready.text="Cancel Ready"; self.btn_ready.variant="cancel"
        else:
            self.btn_ready.text="Ready Up"; self.btn_ready.variant="primary"
        self.btn_ready.draw(self.screen,dt)

        # Ready name pills
        for i,name in enumerate(self.ready_list[:2]):
            c=[P0,P1][i]
            pill_w=180; pill_r=pygame.Rect(cx-pill_w//2,panel.bottom+116+i*32,pill_w,26)
            glow_behind(self.screen,c,pill_r,4,20,13)
            rrect(self.screen,lerp(BG,c,0.12),pill_r,13)
            rrect_border(self.screen,(*c,130),pill_r,13,1)
            rt=self.F["sm"].render(f"{name}  is ready",True,c)
            self.screen.blit(rt,(pill_r.centerx-rt.get_width()//2,pill_r.centery-rt.get_height()//2))

        self.btn_watch.rect=pygame.Rect(cx-100,panel.bottom+190,200,42)
        self.btn_watch.draw(self.screen,dt)
        wh=self.F["xs"].render("Spectate an ongoing match",True,TEXT_DIS)
        self.screen.blit(wh,(cx-wh.get_width()//2,panel.bottom+238))

        hint=self.F["xs"].render("Move: WASD or Arrow Keys     Private chat: /pm username message",True,TEXT_DIS)
        self.screen.blit(hint,(cx-hint.get_width()//2,WIN_H-20))

    # ── Grid / game world ─────────────────────────────────────────────────────
    def _draw_grid(self, surf, ox, oy):
        gd = self.gdata
        for x in range(GRID_W):
            for y in range(GRID_H):
                c = GRID_EVEN if (x+y)%2==0 else GRID_ODD
                pygame.draw.rect(surf,c,(x*CELL+ox,y*CELL+TOP_H+oy,CELL,CELL))
        for x in range(GRID_W+1):
            pygame.draw.line(surf,GRID_LINE_C,(x*CELL+ox,TOP_H+oy),(x*CELL+ox,TOP_H+GRID_H*CELL+oy))
        for y in range(GRID_H+1):
            pygame.draw.line(surf,GRID_LINE_C,(ox,y*CELL+TOP_H+oy),(GRID_W*CELL+ox,y*CELL+TOP_H+oy))
        # Damage flash
        for i,fl in enumerate(self._dmg_flash):
            if fl>0.01:
                c=[P0,P1][i]
                ov=pygame.Surface((GRID_W*CELL,GRID_H*CELL),pygame.SRCALPHA)
                ov.fill((*c,int(60*fl))); surf.blit(ov,(ox,TOP_H+oy))
        # Wall with glow
        pygame.draw.rect(surf,WALL_COL,(ox,TOP_H+oy,GRID_W*CELL,GRID_H*CELL),3)
        glow_behind(surf,ACCENT_BLU,pygame.Rect(ox,TOP_H+oy,GRID_W*CELL,GRID_H*CELL),0,3,8)

        if gd:
            self._draw_obstacles(surf,gd,ox,oy)
            self._draw_pies(surf,gd,ox,oy)
            self._draw_snakes(surf,gd,ox,oy)

        # Cheer toasts
        now=time.time()
        self.cheers=[(tx,ex) for tx,ex in self.cheers if ex>now]
        for i,(tx,ex) in enumerate(self.cheers[-3:]):
            fade=min(1.,(ex-now)/1.5); a=int(210*fade)
            tw=self.F["sm"].size(tx)[0]+24
            tr=pygame.Rect(12,WIN_H-128-i*36,tw,28)
            ts=pygame.Surface((tw,28),pygame.SRCALPHA); ts.fill((*SURFACE2,a))
            surf.blit(ts,tr.topleft)
            rrect_border(surf,(*GOLD_C,int(a*0.6)),tr,6,1)
            ct=self.F["sm"].render(tx,True,(*CHEER_C[:3],a))
            surf.blit(ct,(tr.x+12,tr.y+5))

    def _draw_obstacles(self,surf,gd,ox,oy):
        for obs in gd.get("obstacles",[]):
            x,y=obs["pos"]; k=obs.get("kind","rock")
            c=OBS_ROCK if k=="rock" else OBS_SPIKE
            r=pygame.Rect(x*CELL+2+ox,y*CELL+TOP_H+2+oy,CELL-4,CELL-4)
            rrect(surf,c,r,4)
            cx2,cy2=r.centerx,r.centery
            if k=="rock":
                aacircle(surf,lerp(c,TEXT_PRI,0.28),(cx2,cy2),CELL//2-5)
                aacircle(surf,c,(cx2,cy2),CELL//2-8)
            else:
                pts=[(cx2,cy2-9),(cx2-6,cy2+7),(cx2+6,cy2+7)]
                pygame.draw.polygon(surf,lerp(OBS_SPIKE,TEXT_PRI,0.5),pts)

    def _draw_pies(self,surf,gd,ox,oy):
        t=self._t
        for pie in gd.get("pies",[]):
            px,py=pie["pos"]; k=pie.get("kind","normal")
            c=PIE_GOLD if k=="golden" else PIE_NORM if k=="normal" else PIE_ROT
            cx2=px*CELL+CELL//2+ox; cy2=py*CELL+TOP_H+CELL//2+oy+int(2.5*math.sin(t*3.2+px*0.9+py*0.7))
            rad=CELL//2-4
            if k=="golden":
                pls=0.5+0.5*math.sin(t*4+px+py)
                circle_glow(surf,c,(cx2,cy2),rad,int(7+4*pls),int(60*pls))
            aacircle(surf,c,(cx2,cy2),rad)
            aacircle(surf,lerp(c,TEXT_PRI,0.65),(cx2-2,cy2-2),max(1,rad//3))

    def _draw_snakes(self,surf,gd,ox,oy):
        for sn in gd.get("snakes",[]):
            pid=sn.get("player_id",0); body=sn["body"]; alive=sn.get("alive",True)
            hc=[P0,P1][pid] if alive else DEAD_C
            bc=[P0_DIM,P1_DIM][pid] if alive else (38,40,52)
            gl=[P0_GLOW,P1_GLOW][pid]
            for i,(bx,by) in enumerate(reversed(body)):
                idx=len(body)-1-i; is_hd=idx==0
                fade=max(0.25,1.-idx*0.05)
                c=lerp(DEAD_C,hc if is_hd else bc,fade)
                r=pygame.Rect(bx*CELL+1+ox,by*CELL+TOP_H+1+oy,CELL-2,CELL-2)
                br=9 if is_hd else 4
                rrect(surf,c,r,br)
                if is_hd and alive:
                    glow_behind(surf,gl,r,br,7,40)
                    rrect_border(surf,gl,r,br,1)
                    self._draw_eyes(surf,r,sn["direction"],gl)

    def _draw_eyes(self,surf,r,d,glow):
        offs={"RIGHT":[(r.right-7,r.top+6),(r.right-7,r.bottom-9)],
              "LEFT": [(r.left+4, r.top+6),(r.left+4, r.bottom-9)],
              "UP":   [(r.left+6, r.top+4),(r.right-9,r.top+4)],
              "DOWN": [(r.left+6, r.bottom-7),(r.right-9,r.bottom-7)]}
        for ex,ey in offs.get(d,[]):
            aacircle(surf,BG,(ex,ey),3); aacircle(surf,glow,(ex,ey),2)

    # ── Top bar ───────────────────────────────────────────────────────────────
    def _draw_topbar(self):
        t=self._t
        tb=pygame.Surface((GRID_W*CELL,TOP_H),pygame.SRCALPHA)
        tb.fill((4,5,10,252)); self.screen.blit(tb,(0,0))
        for px2 in range(GRID_W*CELL):
            a=int(70*(0.5+0.5*math.sin(px2*0.016+t*1.4)))
            c=lerp(ACCENT_BLU,P0,px2/(GRID_W*CELL))
            pygame.draw.line(self.screen,(*c,a),(px2,TOP_H-1),(px2,TOP_H))
        pygame.draw.line(self.screen,OUTLINE,(0,TOP_H),(GRID_W*CELL,TOP_H))

        gd=self.gdata
        if not gd: return
        unames=gd.get("usernames",["P1","P2"]); snakes=gd.get("snakes",[]); tl=gd.get("time_left",0)

        for i in range(min(2,len(snakes))):
            sn=snakes[i]; name=unames[i] if i<len(unames) else f"P{i+1}"
            hp=sn.get("health",0); alive=sn.get("alive",True)
            c=[P0,P1][i] if alive else DEAD_C; is_me=self.pid==i
            bx=14 if i==0 else GRID_W*CELL-14-245

            # Name
            if alive: glow_behind(self.screen,c,pygame.Rect(bx,4,245,28),6,10,16)
            tag="YOU" if is_me else f"P{i+1}"
            tr=pygame.Rect(bx,6,38,22)
            rrect(self.screen,(*c[:3],55),tr,4); rrect_border(self.screen,c,tr,4,1)
            tt=self.F["xs"].render(tag,True,TEXT_PRI)
            self.screen.blit(tt,(tr.centerx-tt.get_width()//2,tr.centery-tt.get_height()//2))
            nt=self.F["h2"].render(name+(" [dead]" if not alive else ""),True,c if alive else DEAD_C)
            self.screen.blit(nt,(bx+46,5))
            draw_hp_bar(self.screen,bx,40,245,20,hp,MAX_HEALTH,c if alive else None)

        # Timer
        tcx=GRID_W*CELL//2; urgent=tl<20
        tc=DANGER if urgent else TEXT_PRI
        if urgent and int(t*2)%2==0: tc=lerp(DANGER,TEXT_PRI,0.5)
        tm=self.F["timer"].render(str(int(tl)),True,tc)
        if urgent: glow_behind(self.screen,DANGER,pygame.Rect(tcx-tm.get_width()//2-8,0,tm.get_width()+16,TOP_H),8,20,10)
        self.screen.blit(tm,(tcx-tm.get_width()//2,4))
        sl=self.F["xs"].render("SEC",True,TEXT_TER)
        self.screen.blit(sl,(tcx-sl.get_width()//2,66))

    # ── Sidebar ───────────────────────────────────────────────────────────────
    def _draw_sidebar(self):
        dt=self._dt; sx=GRID_W*CELL; sw=SIDEBAR
        # Panel
        sb=pygame.Surface((sw,WIN_H),pygame.SRCALPHA); sb.fill((4,5,10,255))
        self.screen.blit(sb,(sx,0))
        pygame.draw.line(self.screen,OUTLINE,(sx,0),(sx,WIN_H),1)

        # Role header
        rrect(self.screen,SURFACE,pygame.Rect(sx,0,sw,TOP_H))
        pygame.draw.line(self.screen,OUTLINE,(sx,TOP_H),(sx+sw,TOP_H),1)
        if self.is_fan:   rl,rc="SPECTATOR",CHEER_C
        elif self.pid is not None: rl,rc=f"PLAYER  {self.pid+1}",[P0,P1][self.pid]
        else:              rl,rc="CHAT",TEXT_TER
        rs=self.F["h2"].render(rl,True,rc)
        glow_behind(self.screen,rc,pygame.Rect(sx+sw//2-rs.get_width()//2-10,TOP_H//2-rs.get_height()//2-3,rs.get_width()+20,rs.get_height()+6),6,12,18)
        self.screen.blit(rs,(sx+sw//2-rs.get_width()//2,TOP_H//2-rs.get_height()//2))

        # Chat area
        PAD=10; INP_H=48; HNT=22
        ctop=TOP_H+PAD; cbot=WIN_H-INP_H-HNT-PAD*2; ch=cbot-ctop
        cr=pygame.Rect(sx+PAD,ctop,sw-PAD*2,ch)
        rrect(self.screen,(3,4,9),cr,10)
        rrect_border(self.screen,OUTLINE,cr,10,1)

        MSG_H=52; MGAP=5; maxm=ch//(MSG_H+MGAP)
        visible=self.chat_log[-maxm:]
        old_clip=self.screen.get_clip(); self.screen.set_clip(cr.inflate(-2,-2))
        for j,(sender,text,col) in enumerate(visible):
            is_me=sender==self.username
            bx2=sx+PAD+6; bw2=sw-PAD*2-12; by2=ctop+PAD+j*(MSG_H+MGAP)
            br2=pygame.Rect(bx2,by2,bw2,MSG_H)
            bg2=lerp(SURFACE,col,0.08) if is_me else SURFACE
            rrect(self.screen,bg2,br2,8)
            if is_me: rrect_border(self.screen,(*col[:3],70),br2,8,1)
            # Accent bar
            pygame.draw.rect(self.screen,col,(bx2,by2+9,4,MSG_H-18),border_radius=2)
            # Sender
            ns=self.F["chat_name"].render(sender,True,col)
            self.screen.blit(ns,(bx2+14,by2+6))
            # Message
            mc=max(0,(bw2-20)//9)
            ms=self.F["chat_msg"].render(text[:mc],True,TEXT_PRI)
            self.screen.blit(ms,(bx2+14,by2+26))
        self.screen.set_clip(old_clip)

        # Input
        iy=WIN_H-INP_H-HNT-PAD
        self.tf_chat.rect=pygame.Rect(sx+PAD,iy,sw-PAD*2,INP_H-2)
        self.tf_chat.draw(self.screen,dt)
        ht=self.F["xs"].render("/pm username  for private message",True,TEXT_DIS)
        self.screen.blit(ht,(sx+sw//2-ht.get_width()//2,WIN_H-HNT+2))

    # ── Countdown ─────────────────────────────────────────────────────────────
    def _draw_countdown(self):
        n=self.countdown; phase=min(1.,self._t-self._cd_t)
        # Center exactly in the game grid
        gcx=GCX; gcy=GCY
        COLS={3:(220,44,68),2:(220,154,28),1:(32,204,84)}
        c=COLS.get(n,SUCCESS)

        # Overlay
        ov=pygame.Surface((GRID_W*CELL,GRID_H*CELL),pygame.SRCALPHA)
        a_ov=int(210*min(1.,phase/0.12)); ov.fill((3,4,10,a_ov))
        self.screen.blit(ov,(0,TOP_H))

        # Rings
        for ri in range(4):
            d=ri*0.09; rph=max(0.,phase-d)
            if rph<=0: continue
            rr2=int(8+rph*(210+ri*30)); ra=max(0,int(145*(1.-rph)*(1.-ri*0.2)))
            if ra>0 and rr2>0:
                rs=pygame.Surface((rr2*2+4,rr2*2+4),pygame.SRCALPHA)
                pygame.gfxdraw.aacircle(rs,rr2+2,rr2+2,rr2,(*c,ra))
                self.screen.blit(rs,(gcx-rr2-2,gcy-rr2-2))

        # Big number — zoom in with spring easing
        ease=easeout5(min(1.,phase/0.32)); scale=3.0-ease*2.0
        al=min(255,int(255*min(1.,phase/0.16)))
        base=self.F["countdown"].render(str(n),True,c)
        tw=max(1,int(base.get_width()*scale)); th=max(1,int(base.get_height()*scale))
        big=pygame.transform.smoothscale(base,(tw,th)); big.set_alpha(al)
        # Glow
        gr=max(tw,th)//2+50
        gs=pygame.Surface((gr*2,gr*2),pygame.SRCALPHA)
        ga=int(90*(1.-phase*0.6)*(al/255))
        pygame.gfxdraw.filled_circle(gs,gr,gr,gr,(*c,ga))
        self.screen.blit(gs,(gcx-gr,gcy-gr))
        # Number centered exactly
        self.screen.blit(big,(gcx-tw//2,gcy-th//2))

        # GET READY below
        la=min(255,int(255*min(1.,phase/0.3)))
        ly=gcy+th//2+10+int(20*(1.-min(1.,phase/0.3)))
        lst=self.F["h2"].render("GET  READY",True,TEXT_TER); lst.set_alpha(la)
        self.screen.blit(lst,(gcx-lst.get_width()//2,ly))

        # VS matchup above
        unames=self.gdata.get("usernames",[]) if self.gdata else []
        if len(unames)==2:
            va=min(255,int(255*min(1.,phase/0.22)))
            n0s=self.F["h1"].render(unames[0],True,P0); n0s.set_alpha(va)
            vss=self.F["h2"].render("VS",True,TEXT_DIS);  vss.set_alpha(va)
            n1s=self.F["h1"].render(unames[1],True,P1); n1s.set_alpha(va)
            tw2=n0s.get_width()+vss.get_width()+n1s.get_width()+32
            x0=gcx-tw2//2; vy=gcy-th//2-64
            self.screen.blit(n0s,(x0,vy))
            self.screen.blit(vss,(x0+n0s.get_width()+14,vy+2))
            self.screen.blit(n1s,(x0+n0s.get_width()+vss.get_width()+28,vy))

        # Lines
        lw=int(220*min(1.,phase/0.42)); la2=int(150*min(1.,phase/0.26))
        for sgn in(-1,1):
            lx1=gcx+sgn*(tw//2+18); lx2=gcx+sgn*(tw//2+18+lw)
            pygame.draw.line(self.screen,(*c,la2),(min(lx1,lx2),gcy),(max(lx1,lx2),gcy),2)

    # ── Game over ─────────────────────────────────────────────────────────────
    def _draw_over(self):
        t=self._t; dt=self._dt
        gcx=(GRID_W*CELL)//2; gcy=WIN_H//2
        go=self.gover or {}; winner=go.get("winner","draw"); scores=go.get("scores",{})

        if winner=="draw":          wcol,wtxt=ACCENT_BLU,"DRAW!"
        elif winner==self.username: wcol,wtxt=P0,"YOU WIN!"
        else:                       wcol,wtxt=P1,f"{winner} WINS!"

        # Backdrop
        ov=pygame.Surface((WIN_W,WIN_H),pygame.SRCALPHA); ov.fill((3,4,9,220))
        self.screen.blit(ov,(0,0))

        # Card
        cw,ch=540,370; card=pygame.Rect(gcx-cw//2,gcy-ch//2-8,cw,ch)
        cs=pygame.Surface((cw,ch),pygame.SRCALPHA); cs.fill((5,6,12,252))
        self.screen.blit(cs,card.topleft)
        pulse=0.5+0.5*math.sin(t*2.4)
        glow_behind(self.screen,wcol,card,12,int(20+15*pulse),14)
        rrect_border(self.screen,lerp(wcol,TEXT_PRI,pulse*0.3),card,14,2)
        pygame.draw.rect(self.screen,wcol,(card.x,card.y,cw,4),border_radius=14)

        # Title
        wt=self.F["title"].render(wtxt,True,wcol)
        glow_behind(self.screen,wcol,pygame.Rect(gcx-wt.get_width()//2-14,card.y+16,wt.get_width()+28,wt.get_height()+8),8,18,26)
        self.screen.blit(wt,(gcx-wt.get_width()//2,card.y+20))
        pygame.draw.line(self.screen,OUTLINE,(card.x+28,card.y+88),(card.right-28,card.y+88),1)

        # Scores
        for i,(name,hp) in enumerate(list(scores.items())[:2]):
            c=[P0,P1][i]; ys=card.y+96+i*54
            nt=self.F["h2"].render(name,True,c); self.screen.blit(nt,(gcx-240,ys))
            draw_hp_bar(self.screen,gcx-240,ys+32,320,18,hp,MAX_HEALTH,c)
            ht=self.F["sm"].render(f"{hp} HP",True,TEXT_SEC); self.screen.blit(ht,(gcx+88,ys+30))

        # Buttons
        bw=220
        self.btn_rematch.rect=pygame.Rect(gcx-bw-12,card.bottom-78,bw,52)
        self.btn_lobby.rect=pygame.Rect(gcx+12,card.bottom-78,bw,52)
        self.btn_rematch.draw(self.screen,dt); self.btn_lobby.draw(self.screen,dt)

        hint=self.F["xs"].render("Rematch to play again   |   Back to Lobby to queue for a new game",True,TEXT_DIS)
        self.screen.blit(hint,(gcx-hint.get_width()//2,card.bottom+16))
        self._draw_sidebar()


if __name__ == "__main__":
    Arena().run()