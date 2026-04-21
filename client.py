"""
Pithon Arena - Client v4  |  Bold Neon Redesign
"""
import sys, socket, threading, queue, time, math, random
import pygame, pygame.gfxdraw
from protocol import *

# ── Layout ─────────────────────────────────────────────────────────────────────
CELL    = 26
SIDEBAR = 330
TOP_H   = 80
WIN_W   = GRID_W * CELL + SIDEBAR
WIN_H   = GRID_H * CELL + TOP_H
FPS     = 60

# ── Neon palette ───────────────────────────────────────────────────────────────
BG        = (  6,   7,  14)   # near-black
PANEL     = ( 10,  12,  22)
PANEL2    = ( 14,  17,  32)
BORDER    = ( 35,  40,  80)
BORDER_HI = ( 70,  90, 200)

# Neon player colors
P0        = ( 0,  255, 140)   # neon green
P0_D      = ( 0,  160,  88)
P0_GLOW   = (80,  255, 180)
P1        = (255,  50,  90)   # neon red/pink
P1_D      = (160,  30,  55)
P1_GLOW   = (255, 120, 150)
DEAD      = ( 45,  48,  62)

PIE_G     = (255, 210,  40)
PIE_N     = (255, 130,  30)
PIE_R     = ( 70, 180,  60)
OBS_R     = ( 80,  85, 110)
OBS_S     = (130, 140, 190)

# UI text — HIGH CONTRAST
WHITE     = (255, 255, 255)
OFFWHITE  = (230, 235, 255)
GRAY      = (150, 155, 185)
DIMGRAY   = ( 80,  85, 115)
ACCENT    = ( 60, 180, 255)   # neon blue
GOLD      = (255, 200,  30)
GREEN_C   = ( 50, 220, 110)
RED_C     = (255,  55,  75)
CHEER_C   = (255, 200,  40)

HP_G      = ( 40, 220,  90)
HP_Y      = (220, 185,  35)
HP_R      = (220,  45,  60)

CHAT_COLORS = [
    ( 80, 200, 255), (80, 255, 160), (255, 160, 50),
    (200, 100, 255), (255, 90, 140), (50, 220, 200),
    (255, 220, 60),  (160, 255, 90),
]

GRID_A    = ( 11,  13,  23)
GRID_B    = (  9,  11,  19)
GRID_LINE = ( 17,  19,  33)
WALL_C    = ( 50,  55, 100)

S_CONNECT="connect"; S_LOBBY="lobby"; S_GAME="game"; S_OVER="over"

# ── Math helpers ───────────────────────────────────────────────────────────────
def lrp(a,b,t):
    t=max(0.,min(1.,t))
    return tuple(int(a[i]+(b[i]-a[i])*t) for i in range(3))
def easeout(t): return 1-(1-min(1.,t))**3
def easeback(t): return 1-(1-min(1.,t))**2
def hpcol(r):
    if r>.5: return lrp(HP_Y,HP_G,(r-.5)*2)
    return lrp(HP_R,HP_Y,r*2)
def aac(surf,col,pos,r):
    if r<1: return
    x,y,r=int(pos[0]),int(pos[1]),int(r)
    try:
        pygame.gfxdraw.aacircle(surf,x,y,r,col)
        pygame.gfxdraw.filled_circle(surf,x,y,r,col)
    except: pass
def rr(surf,col,rect,r=8): pygame.draw.rect(surf,col,rect,border_radius=r)
def rrb(surf,col,rect,r=8,w=1): pygame.draw.rect(surf,col,rect,w,border_radius=r)
def glow_rect(surf, col, rect, radius=10, spread=12, alpha=40):
    g=pygame.Surface((rect.width+spread*2,rect.height+spread*2),pygame.SRCALPHA)
    pygame.draw.rect(g,(*col[:3],alpha),(spread//2,spread//2,rect.width+spread,rect.height+spread),border_radius=radius+spread//2)
    surf.blit(g,(rect.x-spread//2,rect.y-spread//2))
def glow_circle(surf, col, pos, r, spread=14, alpha=45):
    total=r+spread
    g=pygame.Surface((total*2+2,total*2+2),pygame.SRCALPHA)
    pygame.draw.circle(g,(*col[:3],alpha),(total+1,total+1),total)
    surf.blit(g,(int(pos[0])-total-1,int(pos[1])-total-1))

# ── Fonts ──────────────────────────────────────────────────────────────────────
def load_fonts():
    UI=["segoeui","calibri","arialrounded","arial","freesans","dejavusans"]
    MO=["consolas","cascadiacode","couriernew","monospace"]
    def g(n,s,b=False):
        for nm in n:
            p=pygame.font.match_font(nm,bold=b)
            if p: return pygame.font.Font(p,s)
        return pygame.font.SysFont("monospace",s,bold=b)
    return {
        "giant": g(UI,64,True),    # countdown, win screen
        "title": g(UI,42,True),    # screen titles
        "h1":    g(UI,30,True),    # section headers
        "h2":    g(UI,22,True),    # sub-headers, player names
        "body":  g(UI,18),         # normal UI text
        "sm":    g(UI,15),         # small labels
        "xs":    g(UI,12),         # hints, tiny labels
        "chat":  g(MO,16),         # chat messages
        "chatname": g(UI,13,True), # chat sender names
        "num":   g(UI,58,True),    # timer
    }

# ── Network ────────────────────────────────────────────────────────────────────
class Net(threading.Thread):
    def __init__(self,host,port,q):
        super().__init__(daemon=True)
        self.host,self.port,self.q=host,port,q
        self._sock=None; self._sq=queue.Queue(); self._buf=b""; self.ok=False
    def run(self):
        try:
            self._sock=socket.socket(); self._sock.connect((self.host,self.port))
            self.ok=True
            threading.Thread(target=self._sl,daemon=True).start()
            self._rl()
        except Exception as e: self.q.put({"type":"_ERR","reason":str(e)})
    def _rl(self):
        while True:
            try: chunk=self._sock.recv(4096)
            except: self.q.put({"type":"_ERR","reason":"Disconnected"}); return
            if not chunk: self.q.put({"type":"_ERR","reason":"Server closed"}); return
            self._buf+=chunk
            while b"\n" in self._buf:
                line,self._buf=self._buf.split(b"\n",1)
                try: self.q.put(decode(line+b"\n"))
                except: pass
    def _sl(self):
        while True:
            m=self._sq.get()
            if m is None: break
            try: self._sock.sendall(encode(m))
            except: break
    def send(self,m):
        if self.ok: self._sq.put(m)

# ── Input widget ──────────────────────────────────────────────────────────────
class Inp:
    def __init__(self,rect,F,hint="",maxlen=40):
        self.rect=pygame.Rect(rect); self.F=F; self.hint=hint
        self.maxlen=maxlen; self.text=""; self.active=False
        self._bl=True; self._bt=0
    def on_event(self,ev):
        if ev.type==pygame.MOUSEBUTTONDOWN: self.active=self.rect.collidepoint(ev.pos)
        if ev.type==pygame.KEYDOWN and self.active:
            if ev.key==pygame.K_BACKSPACE: self.text=self.text[:-1]
            elif ev.key not in(pygame.K_RETURN,pygame.K_KP_ENTER,pygame.K_TAB):
                if len(self.text)<self.maxlen and ev.unicode.isprintable():
                    self.text+=ev.unicode
            return ev.key in(pygame.K_RETURN,pygame.K_KP_ENTER)
        return False
    def draw(self,surf,label=None):
        now=pygame.time.get_ticks()
        if now-self._bt>500: self._bl=not self._bl; self._bt=now
        if self.active:
            glow_rect(surf,ACCENT,self.rect,10,18,35)
        bg=(18,22,42) if self.active else (12,14,26)
        bc=ACCENT if self.active else BORDER
        bw=2 if self.active else 1
        rr(surf,bg,self.rect,10)
        rrb(surf,bc,self.rect,10,bw)
        disp=self.text or self.hint
        col=WHITE if self.text else DIMGRAY
        ts=self.F["body"].render(disp,True,col)
        ty=self.rect.centery-ts.get_height()//2
        surf.blit(ts,(self.rect.x+16,ty))
        if self.active and self._bl:
            cx2=self.rect.x+16+self.F["body"].size(self.text)[0]+1
            pygame.draw.line(surf,ACCENT,(cx2,ty+3),(cx2,ty+ts.get_height()-3),2)
        if label:
            lt=self.F["sm"].render(label,True,GRAY)
            surf.blit(lt,(self.rect.x,self.rect.y-lt.get_height()-6))

# ── Button widget ─────────────────────────────────────────────────────────────
class Btn:
    def __init__(self,rect,text,F,bg=None,fg=None,outline=None):
        self.rect=pygame.Rect(rect); self.text=text; self.F=F
        self.bg=bg or ACCENT; self.fg=fg or BG; self.outline=outline
        self._hov=False; self._pt=0
    def on_event(self,ev):
        if ev.type==pygame.MOUSEMOTION: self._hov=self.rect.collidepoint(ev.pos)
        if ev.type==pygame.MOUSEBUTTONDOWN and self.rect.collidepoint(ev.pos):
            self._pt=pygame.time.get_ticks(); return True
        return False
    def draw(self,surf):
        pr=pygame.time.get_ticks()-self._pt<140
        col=lrp(self.bg,WHITE,0.18) if self._hov else self.bg
        if pr: col=lrp(col,BG,0.3)
        if self._hov: glow_rect(surf,col,self.rect,10,20,30)
        rr(surf,col,self.rect,10)
        if self.outline:
            rrb(surf,self.outline,self.rect,10,2)
        ts=self.F["h2"].render(self.text,True,self.fg)
        surf.blit(ts,(self.rect.centerx-ts.get_width()//2,self.rect.centery-ts.get_height()//2))

# ── Particles ─────────────────────────────────────────────────────────────────
class Spark:
    def __init__(self,x,y,col,spd=None,sz=None,gravity=0.1):
        a=random.uniform(0,math.tau); s=spd or random.uniform(2,6)
        self.x,self.y=float(x),float(y)
        self.vx,self.vy=math.cos(a)*s,math.sin(a)*s-random.uniform(0,2)
        self.col=col; self.life=1.0
        self.dec=random.uniform(0.022,0.055)
        self.sz=sz or random.randint(3,7)
        self.grav=gravity
    def tick(self):
        self.x+=self.vx; self.y+=self.vy; self.vy+=self.grav
        self.life-=self.dec; return self.life>0
    def draw(self,surf):
        s=max(1,int(self.sz*self.life))
        t=pygame.Surface((s*2+2,s*2+2),pygame.SRCALPHA)
        pygame.draw.circle(t,(*self.col[:3],int(230*self.life)),(s+1,s+1),s)
        surf.blit(t,(int(self.x)-s,int(self.y)-s))

def burst(sparks, x, y, col, n=18, spd_range=(1.5,6), sz_range=(2,7)):
    for _ in range(n):
        sparks.append(Spark(x,y,col,
            spd=random.uniform(*spd_range),
            sz=random.randint(*sz_range)))

# ── HP bar ─────────────────────────────────────────────────────────────────────
def draw_hp(surf,x,y,w,h,val,mx,glow_col=None):
    ratio=max(0.,min(1.,val/mx))
    rr(surf,(16,18,32),pygame.Rect(x,y,w,h),h//2)
    if ratio>0:
        col=hpcol(ratio)
        fw=max(h,int(w*ratio))
        rr(surf,col,pygame.Rect(x,y,fw,h),h//2)
        # Bright shimmer
        sx2=x+int(fw*0.5); sw2=max(4,int(fw*0.3))
        sh=pygame.Surface((sw2,h),pygame.SRCALPHA); sh.fill((*WHITE,45))
        surf.blit(sh,(sx2,y))
        if glow_col:
            glow_rect(surf,glow_col,pygame.Rect(x,y,fw,h),h//2,6,30)
    rrb(surf,BORDER,pygame.Rect(x,y,w,h),h//2,1)
    # HP text inside bar
    ht=pygame.font.SysFont("monospace",11,True).render(f"{int(val)}",True,WHITE)
    surf.blit(ht,(x+4,y+h//2-ht.get_height()//2))

# ── Scanline overlay ──────────────────────────────────────────────────────────
_scanline_surf = None
def get_scanlines(w,h):
    global _scanline_surf
    if _scanline_surf is None or _scanline_surf.get_size()!=(w,h):
        _scanline_surf=pygame.Surface((w,h),pygame.SRCALPHA)
        for y in range(0,h,3):
            pygame.draw.line(_scanline_surf,(0,0,0,18),(0,y),(w,y))
    return _scanline_surf

# ── Main arena ────────────────────────────────────────────────────────────────
class Arena:
    def __init__(self):
        pygame.init()
        self.screen=pygame.display.set_mode((WIN_W,WIN_H))
        pygame.display.set_caption("Pithon Arena")
        self.clock=pygame.time.Clock()
        self.F=load_fonts()

        self.net=None; self.q=queue.Queue()
        self.state=S_CONNECT
        self.username=None; self.pid=None; self.is_fan=False
        self.gdata=None; self.gover=None
        self.lobby_list=[]; self.ready_list=[]
        self.i_ready=False
        self.chat_log=[]; self._ucols={}
        self.cheers=[]
        self.sparks=[]
        self._t=0.
        self.countdown=None; self._cd_t=0.
        self.conn_msg=""; self.conn_ok=False
        self._dmg_flash=[0.,0.]
        self._prev_hp=[None,None]
        self._shake=0.; self._shake_off=(0,0)
        self._score_anim=[0.,0.]

        self.key_map={
            pygame.K_UP:"UP",pygame.K_DOWN:"DOWN",
            pygame.K_LEFT:"LEFT",pygame.K_RIGHT:"RIGHT",
            pygame.K_w:"UP",pygame.K_s:"DOWN",
            pygame.K_a:"LEFT",pygame.K_d:"RIGHT",
        }
        self._build()

    def _build(self):
        cx=WIN_W//2
        self.inp_host=Inp(pygame.Rect(cx-190,308,380,48),self.F,"Server IP  (e.g. 127.0.0.1)",64)
        self.inp_port=Inp(pygame.Rect(cx-190,388,170,48),self.F,"Port",6)
        self.inp_user=Inp(pygame.Rect(cx-190,468,380,48),self.F,"Username",20)
        self.inp_host.text="127.0.0.1"; self.inp_port.text="5555"
        self._cinp=[self.inp_host,self.inp_port,self.inp_user]
        self.btn_conn=Btn(pygame.Rect(cx-120,542,240,52),"Connect",self.F,ACCENT,BG)
        sx=GRID_W*CELL
        self.chat_inp=Inp(pygame.Rect(sx+10,WIN_H-50,SIDEBAR-20,40),self.F,"Send a message...",150)
        self.btn_ready=Btn(pygame.Rect(100,100,240,54),"Ready Up",self.F,P0,BG)
        self.btn_watch=Btn(pygame.Rect(100,100,210,44),"Watch as Fan",self.F,PANEL2,GRAY,BORDER)
        self.btn_rematch=Btn(pygame.Rect(100,100,220,54),"Rematch",self.F,P0,BG)
        self.btn_lobby=Btn(pygame.Rect(100,100,220,54),"Back to Lobby",self.F,PANEL2,OFFWHITE,BORDER)

    # ── Loop ──────────────────────────────────────────────────────────────────
    def run(self):
        while True:
            dt=self.clock.tick(FPS)/1000.
            self._t+=dt
            # Decay effects
            self._shake=max(0.,self._shake-dt*8)
            for i in range(2): self._dmg_flash[i]=max(0.,self._dmg_flash[i]-dt*3)
            if self._shake>0:
                ang=random.uniform(0,math.tau)
                amp=self._shake*7
                self._shake_off=(int(math.cos(ang)*amp),int(math.sin(ang)*amp))
            else: self._shake_off=(0,0)

            while not self.q.empty(): self._on(self.q.get_nowait())
            self._events()
            self.sparks=[s for s in self.sparks if s.tick()]
            self._draw()
            pygame.display.flip()

    # ── Messages ──────────────────────────────────────────────────────────────
    def _on(self,msg):
        t=msg.get("type")
        if t=="_ERR":
            self.conn_msg=msg.get("reason","Error"); self.conn_ok=False; self.state=S_CONNECT
        elif t==MSG_JOIN_OK:
            self.username=msg["username"]; self.state=S_LOBBY
        elif t==MSG_JOIN_ERR:
            self.conn_msg=msg.get("reason","Error"); self.conn_ok=False
        elif t==MSG_PLAYER_LIST:
            self.lobby_list=msg.get("players",[])
        elif t==MSG_READY_STATUS:
            self.ready_list=msg.get("ready",[]); self.i_ready=self.username in self.ready_list
        elif t==MSG_GAME_START:
            self.pid=msg.get("your_id"); self.is_fan=False
            self.state=S_GAME; self.gover=None; self.gdata=None
            self.countdown=None; self._prev_hp=[None,None]
        elif t==MSG_WATCH_OK:
            self.is_fan=True; self.state=S_GAME; self.gover=None
        elif t==MSG_GAME_STATE:
            if self.gdata:
                for i,sn in enumerate(msg.get("snakes",[])):
                    old=self._prev_hp[i]; new=sn.get("health",0)
                    if old is not None and new<old:
                        self._dmg_flash[i]=1.0; self._shake=min(1.,self._shake+0.6)
                        body=sn.get("body",[])
                        if body:
                            hx,hy=body[0]
                            sx2=hx*CELL+CELL//2; sy2=hy*CELL+TOP_H+CELL//2
                            col=[P0,P1][i]
                            burst(self.sparks,sx2,sy2,col,n=16,spd_range=(2,5),sz_range=(3,6))
                            burst(self.sparks,sx2,sy2,WHITE,n=6,spd_range=(1,3),sz_range=(2,4))
                    self._prev_hp[i]=new
            self.gdata=msg
        elif t==MSG_COUNTDOWN:
            self.countdown=msg.get("count"); self._cd_t=self._t
        elif t==MSG_GAME_OVER:
            self.gover=msg; self.state=S_OVER
            winner=msg.get("winner","")
            gcx=(GRID_W*CELL)//2
            if winner==self.username:
                for _ in range(80):
                    burst(self.sparks,
                        gcx+random.randint(-200,200),
                        WIN_H//2+random.randint(-120,120),
                        random.choice([P0,GOLD,GREEN_C,ACCENT,WHITE]),
                        n=1,spd_range=(2,7),sz_range=(3,9))
        elif t==MSG_CHAT_RECV:
            s=msg.get("from","?"); tx=msg.get("text",""); prv=msg.get("private",False)
            if s not in self._ucols:
                self._ucols[s]=CHAT_COLORS[len(self._ucols)%len(CHAT_COLORS)]
            self.chat_log.append((s,("[PM] " if prv else "")+tx,self._ucols[s]))
            if len(self.chat_log)>100: self.chat_log.pop(0)
        elif t==MSG_CHEER_RECV:
            self.cheers.append((
                f"{msg.get('from','?')}: {msg.get('emoji','!')} for {msg.get('player','')}!",
                time.time()+4))

    # ── Events ────────────────────────────────────────────────────────────────
    def _events(self):
        for ev in pygame.event.get():
            if ev.type==pygame.QUIT: pygame.quit(); sys.exit()
            if self.state==S_CONNECT:
                for inp in self._cinp:
                    if inp.on_event(ev): self._connect()
                if self.btn_conn.on_event(ev): self._connect()
            elif self.state==S_LOBBY:
                if self.btn_watch.on_event(ev) and self.net: self.net.send({"type":MSG_WATCH})
                if self.btn_ready.on_event(ev) and self.net:
                    if self.i_ready: self.net.send({"type":MSG_UNREADY}); self.i_ready=False
                    else: self.net.send({"type":MSG_READY}); self.i_ready=True
            elif self.state==S_GAME:
                if self.chat_inp.on_event(ev): self._chat()
                if ev.type==pygame.KEYDOWN and not self.is_fan and not self.chat_inp.active:
                    d=self.key_map.get(ev.key)
                    if d and self.net: self.net.send({"type":MSG_INPUT,"direction":d})
            elif self.state==S_OVER:
                self.chat_inp.on_event(ev)
                if ev.type==pygame.KEYDOWN and ev.key==pygame.K_RETURN: self._chat()
                if self.btn_rematch.on_event(ev) and self.net: self.net.send({"type":MSG_REMATCH})
                if self.btn_lobby.on_event(ev) and self.net:
                    self.net.send({"type":MSG_LEAVE}); self._to_lobby()

    def _chat(self):
        txt=self.chat_inp.text.strip()
        if txt and self.net:
            if txt.startswith("/pm "):
                p=txt[4:].split(" ",1)
                if len(p)==2: self.net.send({"type":MSG_CHAT,"to":p[0],"text":p[1]})
            else: self.net.send({"type":MSG_CHAT,"to":None,"text":txt})
        self.chat_inp.text=""

    def _connect(self):
        host=self.inp_host.text.strip(); port=self.inp_port.text.strip(); user=self.inp_user.text.strip()
        if not host or not port or not user: self.conn_msg="Fill in all fields."; self.conn_ok=False; return
        try: pn=int(port)
        except: self.conn_msg="Invalid port."; self.conn_ok=False; return
        self.conn_msg="Connecting..."; self.conn_ok=True
        self.net=Net(host,pn,self.q); self.net.start()
        def _j(): time.sleep(0.35); self.net.send({"type":MSG_JOIN,"username":user})
        threading.Thread(target=_j,daemon=True).start()

    def _to_lobby(self):
        self.state=S_LOBBY; self.gdata=None; self.gover=None
        self.pid=None; self.is_fan=False; self.countdown=None
        self.i_ready=False; self.ready_list=[]

    # ── Draw ──────────────────────────────────────────────────────────────────
    def _draw(self):
        surf=self.screen
        surf.fill(BG)
        off=self._shake_off

        if self.state==S_CONNECT:   self._d_connect(surf)
        elif self.state==S_LOBBY:   self._d_lobby(surf)
        elif self.state in(S_GAME,S_OVER):
            # Apply shake offset to game area only
            if off!=(0,0):
                tmp=pygame.Surface((GRID_W*CELL,WIN_H))
                tmp.fill(BG)
                self._d_game(tmp,0,0)
                surf.blit(tmp,off)
            else:
                self._d_game(surf,0,0)
            self._d_sidebar(surf)
            self._d_topbar(surf)
            if self.countdown is not None and self.countdown>0:
                self._d_countdown(surf)
            elif self.state==S_OVER:
                self._d_over(surf)

        # Particles always on top
        for s in self.sparks: s.draw(surf)

        # Scanlines for CRT feel
        surf.blit(get_scanlines(WIN_W,WIN_H),(0,0))

    # ── Connect screen ─────────────────────────────────────────────────────────
    def _d_connect(self,surf):
        t=self._t; cx=WIN_W//2

        # Animated hex grid background
        hex_size=40
        for row in range(-1, WIN_H//hex_size+2):
            for col2 in range(-1, WIN_W//(hex_size)+2):
                hx=col2*hex_size*1.15+(row%2)*hex_size*0.575
                hy=row*hex_size*0.95
                dist=math.sqrt((hx-cx)**2+(hy-WIN_H//2)**2)
                pulse=math.sin(t*1.2-dist*0.025)
                a=max(0,int(12+10*pulse))
                pts=[(hx+hex_size*0.5*math.cos(math.radians(60*i+30)),
                      hy+hex_size*0.5*math.sin(math.radians(60*i+30))) for i in range(6)]
                pts=[(int(x),int(y)) for x,y in pts]
                try: pygame.draw.polygon(surf,(*BORDER,a),pts,1)
                except: pass

        # Neon snake decorations
        for side in range(2):
            col2=P0 if side==0 else P1
            glw=P0_GLOW if side==0 else P1_GLOW
            for i in range(12):
                frac=i/12
                px=(55+i*28) if side==0 else (WIN_W-55-i*28)
                py=int(WIN_H//2+55*math.sin(t*1.6+i*0.6+side*math.pi))
                a=max(0,240-i*20); sz=max(4,22-i*2)
                if i==0:
                    glow_circle(surf,glw,(px,py),sz//2+2,10,50)
                s2=pygame.Surface((sz,sz),pygame.SRCALPHA)
                s2.fill((*col2,a)); surf.blit(s2,(px-sz//2,py-sz//2))

        # Card
        cw,ch=460,400
        card=pygame.Rect(cx-cw//2,230,cw,ch)
        cs=pygame.Surface((cw,ch),pygame.SRCALPHA); cs.fill((8,10,20,245))
        surf.blit(cs,card.topleft)
        # Animated neon border
        pulse=0.5+0.5*math.sin(t*2.0)
        top_col=lrp(ACCENT,P0,pulse)
        pygame.draw.rect(surf,top_col,(card.x,card.y,cw,3),border_radius=14)
        pygame.draw.rect(surf,(*BORDER,160),card,1,border_radius=14)
        # Corner accents
        for corner_x,corner_y in[(card.x,card.y),(card.right-20,card.y),(card.x,card.bottom-3),(card.right-20,card.bottom-3)]:
            pygame.draw.line(surf,top_col,(corner_x,card.y),(corner_x+18,card.y),2)

        # Title
        title=self.F["title"].render("PITHON  ARENA",True,WHITE)
        glow_rect(surf,P0,pygame.Rect(cx-title.get_width()//2-10,152,title.get_width()+20,title.get_height()+4),8,16,20)
        surf.blit(title,(cx-title.get_width()//2,154))
        sub=self.F["sm"].render("Real-time Online Snake Battle  |  EECE 350",True,GRAY)
        surf.blit(sub,(cx-sub.get_width()//2,204))

        self.inp_host.draw(surf,"Server IP Address")
        self.inp_port.draw(surf,"Port")
        self.inp_user.draw(surf,"Username")
        self.btn_conn.draw(surf)

        if self.conn_msg:
            col2=GREEN_C if self.conn_ok else RED_C
            dots="."*(int(t*3)%4) if self.conn_ok else ""
            mt=self.F["body"].render(self.conn_msg+dots,True,col2)
            surf.blit(mt,(cx-mt.get_width()//2,606))

        hint=self.F["xs"].render("WASD or Arrow Keys to move   |   /pm username message for private chat",True,DIMGRAY)
        surf.blit(hint,(cx-hint.get_width()//2,WIN_H-22))

    # ── Lobby screen ───────────────────────────────────────────────────────────
    def _d_lobby(self,surf):
        t=self._t; cx=WIN_W//2

        # Animated background — slow moving dots
        for i in range(30):
            random.seed(i*997)
            bx=random.randint(0,WIN_W); by=random.randint(0,WIN_H)
            spd=random.uniform(0.2,0.8); phase=random.uniform(0,math.tau)
            a=int(25+20*math.sin(t*spd+phase))
            aac(surf,(*DIMGRAY,a),(bx,by),2)
        random.seed(int(t*1000))  # re-seed to random for game logic

        # Header bar
        hbar=pygame.Surface((WIN_W,72),pygame.SRCALPHA); hbar.fill((8,10,20,255))
        surf.blit(hbar,(0,0))
        # Neon accent line at bottom of header
        for px2 in range(WIN_W):
            a=int(120*(0.5+0.5*math.sin(px2*0.015+t*2.0)))
            c=lrp(ACCENT,P0,px2/WIN_W)
            pygame.draw.line(surf,(*c,a),(px2,71),(px2,72))

        title=self.F["h1"].render("PITHON  ARENA",True,WHITE)
        surf.blit(title,(22,20))
        if self.username:
            u=self.F["body"].render(f"Signed in as  {self.username}",True,ACCENT)
            surf.blit(u,(WIN_W-u.get_width()-22,26))

        # Players panel
        pw,ph=520,290
        panel=pygame.Rect(cx-pw//2,88,pw,ph)
        ps=pygame.Surface((pw,ph),pygame.SRCALPHA); ps.fill((8,10,20,240))
        surf.blit(ps,panel.topleft)
        rrb(surf,BORDER,panel,12,1)

        ht=self.F["h2"].render("Online Players",True,WHITE)
        surf.blit(ht,(panel.x+20,panel.y+16))
        pygame.draw.line(surf,BORDER,(panel.x+14,panel.y+50),(panel.right-14,panel.y+50),1)

        if not self.lobby_list:
            wt=self.F["body"].render("No players connected yet...",True,DIMGRAY)
            surf.blit(wt,(panel.centerx-wt.get_width()//2,panel.y+100))
        else:
            for i,name in enumerate(self.lobby_list[:6]):
                ry=panel.y+58+i*38; is_me=name==self.username; is_rdy=name in self.ready_list
                # Row
                rbg=(20,26,55) if is_me else (12,14,28)
                rr(surf,rbg,pygame.Rect(panel.x+8,ry,pw-16,32),7)
                if is_me: rrb(surf,P0,pygame.Rect(panel.x+8,ry,pw-16,32),7,1)
                # Status dot
                dc=P0 if is_rdy else ACCENT
                aac(surf,dc,(panel.x+26,ry+16),6)
                if is_rdy: glow_circle(surf,dc,(panel.x+26,ry+16),6,8,40)
                # Name
                nc=WHITE if is_me else OFFWHITE
                nt=self.F["body"].render(name+("  (you)" if is_me else ""),True,nc)
                surf.blit(nt,(panel.x+44,ry+6))
                # Ready badge
                if is_rdy:
                    rb=self.F["xs"].render("READY",True,GOLD)
                    rbr=pygame.Rect(panel.right-70,ry+7,58,18)
                    rr(surf,(40,32,0),rbr,4); rrb(surf,GOLD,rbr,4,1)
                    surf.blit(rb,(rbr.centerx-rb.get_width()//2,rbr.centery-rb.get_height()//2))

        # Status
        rc=len(self.ready_list); dots="."*(int(t*2)%4)
        if self.i_ready:   st=self.F["body"].render(f"You are ready!  ({rc}/2 ready{dots})",True,GREEN_C)
        elif rc>0:         st=self.F["body"].render(f"{rc}/2 ready - click Ready Up to join!",True,GOLD)
        else:              st=self.F["body"].render(f"Waiting for players to ready up{dots}",True,GRAY)
        surf.blit(st,(cx-st.get_width()//2,panel.bottom+18))

        # Ready button
        self.btn_ready.rect=pygame.Rect(cx-120,panel.bottom+52,240,54)
        if self.i_ready:
            self.btn_ready.text="Cancel Ready"; self.btn_ready.bg=(50,14,20); self.btn_ready.fg=RED_C; self.btn_ready.outline=RED_C
        else:
            self.btn_ready.text="Ready Up"; self.btn_ready.bg=P0; self.btn_ready.fg=BG; self.btn_ready.outline=None
        self.btn_ready.draw(surf)

        # Who is ready
        for i,name in enumerate(self.ready_list[:2]):
            col2=[P0,P1][i]
            glow_rect(surf,col2,pygame.Rect(cx-130,panel.bottom+118+i*30,260,26),6,8,18)
            rt=self.F["sm"].render(f"{name} is ready!",True,col2)
            surf.blit(rt,(cx-rt.get_width()//2,panel.bottom+120+i*30))

        # Watch button
        self.btn_watch.rect=pygame.Rect(cx-100,panel.bottom+186,200,42)
        self.btn_watch.draw(surf)
        wh=self.F["xs"].render("Watch an ongoing match as spectator",True,DIMGRAY)
        surf.blit(wh,(cx-wh.get_width()//2,panel.bottom+236))

        hint=self.F["xs"].render("Move: WASD or Arrow Keys     Private: /pm username message",True,DIMGRAY)
        surf.blit(hint,(cx-hint.get_width()//2,WIN_H-22))

    # ── Game screen ───────────────────────────────────────────────────────────
    def _d_game(self,surf,ox,oy):
        gd=self.gdata
        # Grid
        for x in range(GRID_W):
            for y in range(GRID_H):
                c=GRID_A if(x+y)%2==0 else GRID_B
                pygame.draw.rect(surf,c,(x*CELL+ox,y*CELL+TOP_H+oy,CELL,CELL))
        for x in range(GRID_W+1):
            pygame.draw.line(surf,GRID_LINE,(x*CELL+ox,TOP_H+oy),(x*CELL+ox,TOP_H+GRID_H*CELL+oy))
        for y in range(GRID_H+1):
            pygame.draw.line(surf,GRID_LINE,(ox,y*CELL+TOP_H+oy),(GRID_W*CELL+ox,y*CELL+TOP_H+oy))
        # Damage flash
        for i,fl in enumerate(self._dmg_flash):
            if fl>0:
                col=[P0,P1][i]
                ov=pygame.Surface((GRID_W*CELL,GRID_H*CELL),pygame.SRCALPHA)
                ov.fill((*col,int(50*fl))); surf.blit(ov,(ox,TOP_H+oy))
        # Wall — glowing
        wc=lrp(WALL_C,WHITE,0.1)
        pygame.draw.rect(surf,wc,(ox,TOP_H+oy,GRID_W*CELL,GRID_H*CELL),3)
        glow_rect(surf,ACCENT,pygame.Rect(ox,TOP_H+oy,GRID_W*CELL,GRID_H*CELL),0,4,15)

        if gd:
            self._d_obs(surf,gd,ox,oy)
            self._d_pies(surf,gd,ox,oy)
            self._d_snakes(surf,gd,ox,oy)

        # Cheer toasts
        now=time.time()
        self.cheers=[(tx,ex) for tx,ex in self.cheers if ex>now]
        for i,(tx,ex) in enumerate(self.cheers[-4:]):
            fade=min(1.,(ex-now)/1.5)
            br=pygame.Rect(8,WIN_H-130-i*36,len(tx)*9+20,30)
            ts=pygame.Surface((br.width,br.height),pygame.SRCALPHA)
            ts.fill((*PANEL2,int(210*fade))); surf.blit(ts,br.topleft)
            ct=self.F["sm"].render(tx,True,(*CHEER_C[:3],int(255*fade)))
            surf.blit(ct,(br.x+10,br.y+6))

    def _d_obs(self,surf,gd,ox,oy):
        for obs in gd.get("obstacles",[]):
            x,y=obs["pos"]; k=obs.get("kind","rock")
            col=OBS_R if k=="rock" else OBS_S
            r=pygame.Rect(x*CELL+2+ox,y*CELL+TOP_H+2+oy,CELL-4,CELL-4)
            rr(surf,col,r,4)
            cx2,cy2=r.centerx,r.centery
            if k=="rock":
                aac(surf,lrp(col,WHITE,0.3),(cx2,cy2),CELL//2-5)
                aac(surf,col,(cx2,cy2),CELL//2-8)
            else:
                pts=[(cx2,cy2-9),(cx2-6,cy2+7),(cx2+6,cy2+7)]
                pygame.draw.polygon(surf,lrp(OBS_S,WHITE,0.55),pts)

    def _d_pies(self,surf,gd,ox,oy):
        t=self._t
        for pie in gd.get("pies",[]):
            px,py=pie["pos"]; k=pie.get("kind","normal")
            col=PIE_G if k=="golden" else PIE_N if k=="normal" else PIE_R
            cx2=px*CELL+CELL//2+ox; cy2=py*CELL+TOP_H+CELL//2+oy
            bob=int(2.5*math.sin(t*3.5+px*0.9+py*0.7))
            cy2+=bob; rad=CELL//2-4
            if k=="golden":
                pls=0.5+0.5*math.sin(t*4+px+py)
                glow_circle(surf,col,(cx2,cy2),rad,int(6+4*pls),int(55*pls))
            elif k=="rotten":
                glow_circle(surf,col,(cx2,cy2),rad,5,30)
            aac(surf,col,(cx2,cy2),rad)
            aac(surf,lrp(col,WHITE,0.65),(cx2-2,cy2-2),rad//3)

    def _d_snakes(self,surf,gd,ox,oy):
        for snake in gd.get("snakes",[]):
            pid2=snake["pid"] if "pid" in snake else snake.get("player_id",0)
            body=snake["body"]; alive=snake.get("alive",True)
            hc=[P0,P1][pid2] if alive else DEAD
            bc=[P0_D,P1_D][pid2] if alive else (38,40,52)
            gl=[P0_GLOW,P1_GLOW][pid2]
            for i,(bx,by) in enumerate(reversed(body)):
                idx=len(body)-1-i; is_hd=idx==0
                fade=max(0.28,1.-idx*0.05)
                col=lrp(DEAD,hc if is_hd else bc,fade)
                r=pygame.Rect(bx*CELL+1+ox,by*CELL+TOP_H+1+oy,CELL-2,CELL-2)
                br=8 if is_hd else 4
                rr(surf,col,r,br)
                if is_hd and alive:
                    glow_rect(surf,gl,r,br,6,35)
                    rrb(surf,gl,r,br,1)
                    self._eyes(surf,r,snake["direction"],gl)

    def _eyes(self,surf,r,d,glow):
        offs={"RIGHT":[(r.right-7,r.top+6),(r.right-7,r.bottom-9)],
              "LEFT": [(r.left+4, r.top+6),(r.left+4, r.bottom-9)],
              "UP":   [(r.left+6, r.top+4),(r.right-9,r.top+4)],
              "DOWN": [(r.left+6, r.bottom-7),(r.right-9,r.bottom-7)]}
        for ex,ey in offs.get(d,[]):
            aac(surf,BG,(ex,ey),3); aac(surf,glow,(ex,ey),2)

    # ── Top bar ───────────────────────────────────────────────────────────────
    def _d_topbar(self,surf):
        t=self._t
        # Background
        tb=pygame.Surface((GRID_W*CELL,TOP_H),pygame.SRCALPHA); tb.fill((6,7,14,250))
        surf.blit(tb,(0,0))
        # Animated bottom edge glow
        for px2 in range(GRID_W*CELL):
            a=int(80*(0.5+0.5*math.sin(px2*0.018+t*1.5)))
            c=lrp(ACCENT,P0,px2/(GRID_W*CELL))
            pygame.draw.line(surf,(*c,a),(px2,TOP_H-1),(px2,TOP_H))
        pygame.draw.line(surf,BORDER,(0,TOP_H),(WIN_W,TOP_H))

        gd=self.gdata
        if not gd: return
        unames=gd.get("usernames",["P1","P2"])
        snakes=gd.get("snakes",[])
        time_left=gd.get("time_left",0)

        for i in range(min(2,len(snakes))):
            sn=snakes[i]; name=unames[i] if i<len(unames) else f"P{i+1}"
            hp=sn.get("health",0); alive=sn.get("alive",True)
            col=[P0,P1][i] if alive else DEAD; is_me=self.pid==i
            bx=12 if i==0 else GRID_W*CELL-12-240

            # Name with glow if alive
            if alive: glow_rect(surf,col,pygame.Rect(bx,4,240,26),6,8,15)
            tag="YOU" if is_me else f"P{i+1}"
            tr=pygame.Rect(bx,6,38,22)
            rr(surf,(*col[:3],60),tr,4); rrb(surf,col,tr,4,1)
            tt=self.F["xs"].render(tag,True,WHITE)
            surf.blit(tt,(tr.centerx-tt.get_width()//2,tr.centery-tt.get_height()//2))
            nt=self.F["h2"].render(name+(" [dead]" if not alive else ""),True,col if alive else DEAD)
            surf.blit(nt,(bx+46,6))
            draw_hp(surf,bx,38,240,18,hp,MAX_HEALTH,col if alive else None)

        # Timer
        tcx=GRID_W*CELL//2; urgent=time_left<20
        tc=RED_C if urgent else WHITE
        if urgent and int(t*2)%2==0: tc=lrp(RED_C,WHITE,0.5)
        tm=self.F["num"].render(str(int(time_left)),True,tc)
        if urgent: glow_rect(surf,RED_C,pygame.Rect(tcx-tm.get_width()//2-6,2,tm.get_width()+12,tm.get_height()),6,10,20)
        surf.blit(tm,(tcx-tm.get_width()//2,2))
        sl=self.F["xs"].render("SEC",True,DIMGRAY)
        surf.blit(sl,(tcx-sl.get_width()//2,62))

    # ── Sidebar ───────────────────────────────────────────────────────────────
    def _d_sidebar(self,surf):
        sx=GRID_W*CELL; sw=SIDEBAR
        # Background
        sb=pygame.Surface((sw,WIN_H),pygame.SRCALPHA); sb.fill((7,8,16,255))
        surf.blit(sb,(sx,0))
        pygame.draw.line(surf,BORDER,(sx,0),(sx,WIN_H),1)

        # Header showing role
        hh=TOP_H
        rr(surf,(8,9,18),pygame.Rect(sx,0,sw,hh))
        pygame.draw.line(surf,BORDER,(sx,hh),(sx+sw,hh),1)
        if self.is_fan:   rlbl,rcol="SPECTATOR",CHEER_C
        elif self.pid is not None: rlbl,rcol=f"PLAYER {self.pid+1}",[P0,P1][self.pid]
        else:              rlbl,rcol="CHAT",GRAY
        rl=self.F["h2"].render(rlbl,True,rcol)
        glow_rect(surf,rcol,pygame.Rect(sx+sw//2-rl.get_width()//2-8,hh//2-rl.get_height()//2-4,rl.get_width()+16,rl.get_height()+8),6,10,20)
        surf.blit(rl,(sx+sw//2-rl.get_width()//2,hh//2-rl.get_height()//2))

        # Chat area
        PAD=10; INP_H=46; HNT_H=22
        ctop=hh+PAD; cbot=WIN_H-INP_H-HNT_H-PAD*2; ch=cbot-ctop
        cr=pygame.Rect(sx+PAD,ctop,sw-PAD*2,ch)
        rr(surf,(5,6,14),cr,8); rrb(surf,BORDER,cr,8,1)

        MSG_H=50; MSG_PAD=6; maxm=ch//(MSG_H+MSG_PAD)
        visible=self.chat_log[-maxm:]

        old_clip=surf.get_clip()
        surf.set_clip(cr.inflate(-2,-2))
        for j,(sender,text,col) in enumerate(visible):
            is_me=sender==self.username
            bx2=sx+PAD+6; bw2=sw-PAD*2-12
            by2=ctop+PAD+j*(MSG_H+MSG_PAD)
            br2=pygame.Rect(bx2,by2,bw2,MSG_H)
            # Bubble
            bg2=lrp((6,7,16),col,0.09) if is_me else (9,10,22)
            rr(surf,bg2,br2,8)
            if is_me: rrb(surf,(*col[:3],80),br2,8,1)
            # Left accent
            pygame.draw.rect(surf,col,(bx2,by2+8,4,MSG_H-16),border_radius=2)
            # Sender name — bold, colored
            ns=self.F["chatname"].render(sender,True,col)
            surf.blit(ns,(bx2+14,by2+5))
            # Message text — large, high contrast
            mc=max(0,(bw2-18)//9)
            ms=self.F["chat"].render(text[:mc],True,OFFWHITE)
            surf.blit(ms,(bx2+14,by2+24))
        surf.set_clip(old_clip)

        # Input
        iy=WIN_H-INP_H-HNT_H-PAD
        self.chat_inp.rect=pygame.Rect(sx+PAD,iy,sw-PAD*2,INP_H-2)
        self.chat_inp.draw(surf)
        ht=self.F["xs"].render("/pm username  for private message",True,DIMGRAY)
        surf.blit(ht,(sx+sw//2-ht.get_width()//2,WIN_H-HNT_H+2))

    # ── Countdown ─────────────────────────────────────────────────────────────
    def _d_countdown(self,surf):
        n=self.countdown; gcx=(GRID_W*CELL)//2; gcy=WIN_H//2
        phase=min(1.,self._t-self._cd_t)
        cols={3:(220,50,70),2:(220,160,30),1:(40,210,90)}
        col=cols.get(n,GREEN_C)

        # Full overlay
        ov=pygame.Surface((GRID_W*CELL,WIN_H),pygame.SRCALPHA)
        ov.fill((3,4,10,int(200*min(1.,phase/0.1))))
        surf.blit(ov,(0,0))

        # Rings
        for ri in range(4):
            delay=ri*0.1; rph=max(0.,phase-delay)
            if rph<=0: continue
            rr2=int(10+rph*(200+ri*35)); ra=max(0,int(150*(1.-rph)*(1.-ri*0.22)))
            if ra>0 and rr2>0:
                rs=pygame.Surface((rr2*2+4,rr2*2+4),pygame.SRCALPHA)
                pygame.gfxdraw.aacircle(rs,rr2+2,rr2+2,rr2,(*col,ra))
                surf.blit(rs,(gcx-rr2-2,gcy-rr2-2))

        # Number
        ease=easeout(min(1.,phase/0.28)); scale=2.8-ease*1.8
        al=min(255,int(255*min(1.,phase/0.15)))
        base=self.F["giant"].render(str(n),True,col)
        tw=max(1,int(base.get_width()*scale*2)); th=max(1,int(base.get_height()*scale*2))
        big=pygame.transform.smoothscale(base,(tw,th)); big.set_alpha(al)
        # Glow
        gr=max(tw,th)//2+40
        gs=pygame.Surface((gr*2,gr*2),pygame.SRCALPHA)
        ga=int(80*(1.-phase*0.5)*(al/255))
        pygame.gfxdraw.filled_circle(gs,gr,gr,gr,(*col,ga))
        surf.blit(gs,(gcx-gr,gcy-gr-28))
        surf.blit(big,(gcx-tw//2,gcy-th//2-28))

        # GET READY
        la=min(255,int(255*min(1.,phase/0.3)))
        ly=gcy+th//2+8+int(18*(1.-min(1.,phase/0.3)))
        lst=self.F["h2"].render("GET  READY",True,GRAY); lst.set_alpha(la)
        surf.blit(lst,(gcx-lst.get_width()//2,ly))

        # Matchup names
        unames=self.gdata.get("usernames",[]) if self.gdata else []
        if len(unames)==2:
            va=min(255,int(255*min(1.,phase/0.22)))
            n0=self.F["h1"].render(unames[0],True,P0); n0.set_alpha(va)
            vs=self.F["h1"].render("VS",True,DIMGRAY);  vs.set_alpha(va)
            n1=self.F["h1"].render(unames[1],True,P1); n1.set_alpha(va)
            tw2=n0.get_width()+vs.get_width()+n1.get_width()+32
            x0=gcx-tw2//2; vy=gcy-th//2-72
            surf.blit(n0,(x0,vy))
            surf.blit(vs,(x0+n0.get_width()+14,vy))
            surf.blit(n1,(x0+n0.get_width()+vs.get_width()+28,vy))

        # Expanding lines
        lw=int(200*min(1.,phase/0.4)); la2=int(160*min(1.,phase/0.25))
        for sgn in(-1,1):
            lx1=gcx+sgn*(tw//2+16); lx2=gcx+sgn*(tw//2+16+lw)
            pygame.draw.line(surf,(*col,la2),(min(lx1,lx2),gcy-28),(max(lx1,lx2),gcy-28),2)
            pygame.draw.line(surf,(*col,la2//2),(min(lx1,lx2),gcy+th//2),(max(lx1,lx2),gcy+th//2),1)

    # ── Game over ─────────────────────────────────────────────────────────────
    def _d_over(self,surf):
        t=self._t; gcx=(GRID_W*CELL)//2; gcy=WIN_H//2
        go=self.gover or {}; winner=go.get("winner","draw"); scores=go.get("scores",{})

        if winner=="draw":            wcol,wtxt=ACCENT,"DRAW!"
        elif winner==self.username:   wcol,wtxt=P0,"YOU WIN!"
        else:                         wcol,wtxt=P1,f"{winner} WINS!"

        # Overlay
        ov=pygame.Surface((WIN_W,WIN_H),pygame.SRCALPHA); ov.fill((3,4,10,215))
        surf.blit(ov,(0,0))

        # Card
        cw,ch=520,360; card=pygame.Rect(gcx-cw//2,gcy-ch//2-10,cw,ch)
        cs=pygame.Surface((cw,ch),pygame.SRCALPHA); cs.fill((7,8,18,250))
        surf.blit(cs,card.topleft)
        # Animated neon border
        pulse=0.5+0.5*math.sin(t*2.2)
        bc=lrp(wcol,WHITE,pulse*0.25)
        glow_rect(surf,wcol,card,14,10,20)
        rrb(surf,bc,card,14,2)
        pygame.draw.rect(surf,wcol,(card.x,card.y,cw,4),border_radius=14)

        # Winner text
        wt=self.F["title"].render(wtxt,True,wcol)
        glow_rect(surf,wcol,pygame.Rect(gcx-wt.get_width()//2-12,card.y+18,wt.get_width()+24,wt.get_height()+8),8,14,25)
        surf.blit(wt,(gcx-wt.get_width()//2,card.y+22))
        pygame.draw.line(surf,BORDER,(card.x+28,card.y+86),(card.right-28,card.y+86))

        # Scores
        for i,(name,hp) in enumerate(list(scores.items())[:2]):
            col=[P0,P1][i]; ys=card.y+96+i*50
            nt=self.F["h2"].render(name,True,col); surf.blit(nt,(gcx-240,ys))
            draw_hp(surf,gcx-240,ys+30,310,16,hp,MAX_HEALTH,col)

        # Buttons
        bw=220
        self.btn_rematch.rect=pygame.Rect(gcx-bw-12,card.bottom-76,bw,52)
        self.btn_lobby.rect=pygame.Rect(gcx+12,card.bottom-76,bw,52)
        self.btn_rematch.draw(surf); self.btn_lobby.draw(surf)

        hint=self.F["xs"].render("Rematch to play again   |   Back to Lobby to queue for a new game",True,DIMGRAY)
        surf.blit(hint,(gcx-hint.get_width()//2,card.bottom+16))
        self._d_sidebar(surf)


if __name__=="__main__":
    Arena().run()