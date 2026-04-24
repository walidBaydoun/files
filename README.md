# Pithon Arena 🐍

A real-time two-player snake battle game built with Python and Pygame over raw TCP sockets.
Players connect to a central server and compete in live matches with mutation power-ups,
spectator support, live chat, and a full post-game stats screen.

---

## Requirements

```
Python 3.10+
pygame
```

Install pygame:
```bash
python -m pip install pygame
```

---

## Project Structure

```
pithon_arena/
├── server.py              # TCP server — game logic host
├── client.py              # Pygame GUI client
├── game.py                # Server-side game state and mutation logic
├── protocol.py            # Shared message types, constants, encode/decode
├── Before_The_Timer_Ends.mp3   # Lobby/in-game background music
├── munch_sfx.m4a          # Sound effect: pie collected
├── collsion_sfx.m4a       # Sound effect: collision
└── README.md
```

---

## Running the Game

### Step 1 — Start the server

Open a terminal and run:
```bash
python server.py 5555
```
The server listens on the given port. Keep this terminal open.

### Step 2 — Start clients

Open a separate terminal for each player:
```bash
python client.py
```

In the client window, enter:
- **Server IP** — `127.0.0.1` for local, or your LAN IP (run `ipconfig` on Windows / `ifconfig` on Mac/Linux)
- **Port** — `5555`
- **Username** — any unique name

### Step 3 — Play

Both players click **Ready Up** in the lobby. A 3-second countdown starts, then the match begins.

---

## Controls

| Key | Action |
|-----|--------|
| `W` / `↑` | Move Up |
| `S` / `↓` | Move Down |
| `A` / `←` | Move Left |
| `D` / `→` | Move Right |
| `Enter` | Send chat message |

Private message: type `/pm username your message` in the chat box.

---

## Network Setup (Multiplayer over LAN)

1. Find the server machine's local IP:
   - **Windows:** `ipconfig` → look for IPv4 Address
   - **Mac/Linux:** `ifconfig` → look for `inet`
2. Make sure both machines are on the **same Wi-Fi network**
3. The second player enters the server's IP in the Host field instead of `127.0.0.1`
4. If connection is refused, allow Python through Windows Firewall:
   ```powershell
   # Run as Administrator
   netsh advfirewall firewall add rule name="Pithon Arena" dir=in action=allow protocol=TCP localport=5555
   ```

---

## Gameplay Rules

- The grid wraps — hitting a wall teleports you to the opposite side with no damage
- Collecting a **Mutation Pie** grants a temporary ability (see below)
- Hitting an obstacle costs **20 HP**
- Hitting the other snake costs **25 HP**
- Self-collision costs **10 HP**
- The match ends when a player reaches **0 HP** or the **120-second timer** expires
- If time runs out, the player with more HP wins. Equal HP is a draw.

---

## Mutation Pies

| Pie | Label | Effect |
|-----|-------|--------|
| **Hot Sauce Pie** | `H` | Leaves a fire trail behind your snake. Opponent crossing fire takes 15 damage. Lasts 5 seconds. |
| **Whipped Cream Pie** | `W` | Makes you invisible for 3 seconds. While invisible, leaves cream splotches that slow the opponent for 2 seconds. |
| **Blueberry Pie** | `B` | Grants a one-hit shield that absorbs the next collision (obstacle, other snake, or wall) with no damage. |

---

## Lobby Features

| Button | Description |
|--------|-------------|
| **Ready Up** | Queue yourself for the next match. First two ready players are matched. |
| **Cancel Ready** | Remove yourself from the queue. |
| **Customize** | Choose your snake color from 12 options. |
| **Chat** | Open a lobby chat window to talk with connected players. |
| **?** | Open the mutation guide showing all pie abilities. |
| **Mute Music** | Toggle the background music on/off. |
| **Watch as Fan** | Spectate an ongoing match without playing. |

---

## Spectator (Fan) Mode

- Click **Watch as Fan** in the lobby to observe any ongoing match
- Fans see the full game board, both snakes, health bars, and chat
- Fans can chat with players during the match
- Fans can click **Back to Lobby** at any time from the sidebar
- When a match ends, spectators see the full post-game stats card

---

## Post-Game Stats Screen

After every match, all connected clients (players, spectators, lobby players) see a stats card showing:

- Winner announcement with their color
- Both players' final HP bars
- **Pies Collected** — with comparison bars
- **Mutations Used** — total power-ups activated
- **Damage Dealt** — to the opponent
- **Max Snake Length** — longest body reached during the match

A gold `*` highlights whichever player led each stat.

---

## Player Profiles (Session-based)

Each session tracks wins, losses, and current win streak per client.
Stats are visible to all players in the lobby player list:
- `5W  2L` — win/loss record in green or red
- `W3` pill — current win streak (gold for 3+)
- `NEW` — first match of the session

Stats reset when the client is closed. They are not saved to disk.

---

## Protocol Overview

All communication uses **TCP** with **line-delimited JSON** messages over a persistent socket connection.

```
Client → Server:   JOIN, INPUT, CHAT, WATCH, CHEER, REMATCH,
                   LEAVE, READY, UNREADY, SET_COLOR, SHARE_STATS

Server → Client:   JOIN_OK, JOIN_ERR, PLAYER_LIST, GAME_START,
                   GAME_STATE, GAME_OVER, CHAT_RECV, CHEER_RECV,
                   READY_STATUS, COUNTDOWN, WATCH_OK
```

Every message is a JSON object terminated by `\n`. The server runs the game loop at
10 ticks/second and broadcasts the full game state to all players and spectators each tick.
Clients are **thin** — they only send direction inputs and render whatever the server sends.

### Example Flow

```
Client                          Server
  │  {"type":"JOIN","username":"Alice"}  →    │
  │  ←  {"type":"JOIN_OK","username":"Alice"} │
  │  {"type":"READY"}              →          │
  │  ←  {"type":"READY_STATUS","ready":["Alice"],...}
  │  ←  {"type":"GAME_START","your_id":0,...} │
  │  {"type":"INPUT","direction":"RIGHT"} →   │
  │  ←  {"type":"GAME_STATE",...} (10/sec)    │
  │  ←  {"type":"GAME_OVER","winner":"Alice"} │
```

---

## Architecture

```
┌─────────────────────────────────────────────────────┐
│                      server.py                      │
│  ┌─────────────┐   ┌──────────────┐   ┌──────────┐ │
│  │ClientHandler│   │  ArenaServer │   │ game.py  │ │
│  │ (per client)│ → │  (TCP host)  │ → │GameState │ │
│  └─────────────┘   └──────────────┘   └──────────┘ │
└─────────────────────────────────────────────────────┘
          ↑ TCP (JSON + \n)  ↓
┌─────────────────────────────────────────────────────┐
│                      client.py                      │
│  ┌────────────┐   ┌────────────────────────────┐   │
│  │ NetThread  │ → │  Arena (Pygame renderer)   │   │
│  │ (recv loop)│   │  Connect / Lobby / Game /  │   │
│  └────────────┘   │  GameOver screens          │   │
│                   └────────────────────────────┘   │
└─────────────────────────────────────────────────────┘
```

- **server.py** — accepts TCP connections, one thread per client, runs the game loop
- **game.py** — pure game logic: snake movement, collision detection, mutation effects, stat tracking
- **client.py** — Pygame GUI with screen-transition tweens, particle effects, and per-snake color rendering
- **protocol.py** — shared constants, `encode()` / `decode()` helpers

---

## Known Limitations

- One active match at a time per server instance
- Stats are session-only (reset on client restart)
- Sound effects require a pygame version with mixer support for m4a files