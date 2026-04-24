"""
Πthon Arena - Shared Constants
Message types and game constants shared between client and server.
"""

# ── Message Types ──────────────────────────────────────────────────────────────
# Client → Server
MSG_JOIN        = "JOIN"         # {"type":"JOIN","username":"..."}
MSG_INPUT       = "INPUT"        # {"type":"INPUT","direction":"UP"|"DOWN"|"LEFT"|"RIGHT"}
MSG_CHAT        = "CHAT"         # {"type":"CHAT","to":"username"|None,"text":"..."}
MSG_WATCH       = "WATCH"        # {"type":"WATCH"}  — fan request
MSG_CHEER       = "CHEER"        # {"type":"CHEER","player":"username","emoji":"🐍"}
MSG_REMATCH     = "REMATCH"      # {"type":"REMATCH"}
MSG_LEAVE       = "LEAVE"        # {"type":"LEAVE"}  — return to lobby
MSG_SET_COLOR   = "SET_COLOR"    # {"type":"SET_COLOR","color":[r,g,b]}
MSG_SHARE_STATS = "SHARE_STATS"  # {"type":"SHARE_STATS","wins":n,"losses":n,"streak":n}
MSG_START_REQ   = "START_REQ"    # {"type":"START_REQ"}  — player requests to start
MSG_COUNTDOWN   = "COUNTDOWN"    # {"type":"COUNTDOWN","count":3|2|1|0}
MSG_READY       = "READY"        # {"type":"READY"}   — player readies up
MSG_UNREADY     = "UNREADY"      # {"type":"UNREADY"} — player cancels ready
MSG_READY_STATUS= "READY_STATUS" # {"type":"READY_STATUS","ready":["alice",...], "count":1}
MSG_PING        = "PING"

# Server → Client
MSG_JOIN_OK     = "JOIN_OK"      # {"type":"JOIN_OK","username":"..."}
MSG_JOIN_ERR    = "JOIN_ERR"     # {"type":"JOIN_ERR","reason":"..."}
MSG_PLAYER_LIST = "PLAYER_LIST"  # {"type":"PLAYER_LIST","players":[...]}
MSG_GAME_START  = "GAME_START"   # {"type":"GAME_START","your_id":0|1,"config":{...}}
MSG_GAME_STATE  = "GAME_STATE"   # full state snapshot
MSG_GAME_OVER   = "GAME_OVER"    # {"type":"GAME_OVER","winner":"username","scores":{...}}
MSG_CHAT_RECV   = "CHAT_RECV"    # {"type":"CHAT_RECV","from":"...","text":"...","private":bool}
MSG_CHEER_RECV  = "CHEER_RECV"   # {"type":"CHEER_RECV","from":"...","player":"...","emoji":"..."}
MSG_PONG        = "PONG"
MSG_WATCH_OK    = "WATCH_OK"

# ── Game Constants ─────────────────────────────────────────────────────────────
GRID_W          = 30
GRID_H          = 22
TICK_RATE       = 10          # game ticks per second
INITIAL_HEALTH  = 100
MAX_HEALTH      = 150
GAME_DURATION   = 120         # seconds

# Mutation Pie types: key -> {delta, color, name}
PIE_TYPES = {
    "hotsauce":  {"delta":  0, "color": "#FF4500", "name": "Hot Sauce Pie"},
    "whipped":   {"delta":  0, "color": "#FFFAFA", "name": "Whipped Cream Pie"},
    "blueberry": {"delta":  0, "color": "#4169E1", "name": "Blueberry Pie"},
}

# Obstacle types
OBSTACLE_TYPES = {
    "rock":  {"color": "#808080", "symbol": "🪨"},
    "spike": {"color": "#C0C0C0", "symbol": "⚡"},
}

MAX_PIES        = 6
NUM_OBSTACLES   = 8

# Snake colors for player 0 and player 1
SNAKE_COLORS    = ["#00FF7F", "#FF6347"]

