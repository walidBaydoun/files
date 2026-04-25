# Πthon Arena 🐍

Online two-player snake battle game built with Python + Pygame.

## Requirements

```
pip install pygame
```

Python 3.10+ recommended .

## How To Run

### 1. Start the server

```bash
python server.py 5555
```

The server accepts a port number as a command-line argument.

### 2. Start clients (on any machine on the network)

```bash
python client.py
```

Each client opens a GUI where you enter:
- **Host / IP** – server IP address (`127.0.0.1` for local)
- **Port** – must match server port (`5555`)
- **Username** – unique nickname

## How to Play

| Key | Action |
|-----|--------|
| Arrow Keys / WASD | Move your snake |
| Enter (chat box) | Send a message |
| `/pm username message` | Private message |

### Game Rules
- Collect **pies** to gain health and different mutations
- Avoid **walls**, **obstacles**, and the **other snake** (causes health loss)
- The player with more health when the timer runs out **wins**
- A player reaching **0 HP** loses immediately

## Features

### Basic
- [x] Client-server architecture (TCP sockets)
- [x] Username verification (no duplicates)
- [x] Lobby with online player list
- [x] Real-time snake movement (10 ticks/sec)
- [x] Server-side game logic and collision detection
- [x] Pie collection (3 types with different effects)
- [x] Static obstacles (rocks and spikes)
- [x] Health scoring system
- [x] Game timer (180 seconds)
- [x] Winner announcement
- [x] Game state broadcast to all clients

### Advanced
- [x] **Text Chat** – public and private (`/pm`) messaging
- [x] **Fan / Spectator mode** – watch ongoing games
- [x] **Cheer system** – fans send emoji cheers displayed in-game
- [x] **Rematch** – both players can vote to play again
- [x] **Snake customization** – animated eyes facing direction of travel
- [x] **Music** – Ingame music which can be muted

## Architecture

```

  Server                                Client
  │   ←  {"type":"JOIN","username":"Alice"}   │
  │   {"type":"JOIN_OK","username":"Alice"} → │
  │   {"type":"PLAYER_LIST",...}           →  │

  │   ←  {"type":"READY"}                   │
  │   {"type":"READY_STATUS",
  │        "ready":["Alice"],
  │        "count":1
  │     } →                                 │

  │   (another player joins & ready)        │
  │   {"type":"GAME_START",
  │        "your_id":0,
  │        "config":{...}
  │     } →                                 │

  │   ←  {"type":"INPUT","direction":"RIGHT"} │
  │   ←  {"type":"INPUT","direction":"UP"}    │

  │   {"type":"GAME_STATE",...} →   (≈10/sec) │

  │   {"type":"GAME_OVER",
  │        "winner":"Alice",
  │        "scores":{...},
  │        "stats":{...}
  │     } →                                  │
  # Spectator
Server                                Client
  │   ←  {"type":"WATCH"}             │
  │   {"type":"WATCH_OK"} →           │
  │   {"type":"GAME_STATE",...} →     │

  # Chat / Cheer
Server                                Client
  │   ←  {"type":"CHAT","text":"hi"}  │
  │   {"type":"CHAT_RECV",...} →      │

  │   ←  {"type":"CHEER","emoji":"🔥"} │
  │   {"type":"CHEER_RECV",...} →      │
server.py        – TCP server, manages clients & game loop
  └── game.py    – Pure game logic (GameState, Snake)
  
client.py        – Pygame GUI + network thread
  
protocol.py      – Shared message types & constants
server.py        – TCP server, manages clients & game loop
  └── game.py    – Pure game logic (GameState, Snake)
  
```

All communication uses plain TCP sockets with newline-delimited UTF-8 JSON messages.
The server runs the game loop at ~10 ticks per second and broadcasts the game state to both players and spectators.
Clients act as rendering endpoints for gameplay (sending only input commands like direction), but also handle additional interactions such as lobby control, chat, and reactions.

## 🛠️ Tech Stack
* **Frontend:** Pygame library for graphics and event handling
* **Backend:** Python with socket library for networking and json library for message serialization
* **Game Logic:** Python with protocol file for message type definitions and game constants
* **Dependencies:** socket, threading, json, and pygame libraries

