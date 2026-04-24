# Πthon Arena 🐍

Online two-player snake battle game built with Python + Pygame.

## Requirements

```
pip install pygame
```

Python 3.10+ recommended (uses `X | Y` type union syntax).

## Running

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
- Collect **pies** to gain health 🥧 (golden +15, normal +8, rotten -10)
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
- [x] Game timer (120 seconds)
- [x] Winner announcement
- [x] Game state broadcast to all clients

### Advanced
- [x] **Text Chat** – public and private (`/pm`) messaging
- [x] **Fan / Spectator mode** – watch ongoing games
- [x] **Cheer system** – fans send emoji cheers displayed in-game
- [x] **Rematch** – both players can vote to play again
- [x] **Snake customization** – animated eyes facing direction of travel

## Architecture

```
server.py        – TCP server, manages clients & game loop
  └── game.py    – Pure game logic (GameState, Snake)
  
client.py        – Pygame GUI + network thread
  
protocol.py      – Shared message types & constants
```

All communication uses plain TCP sockets with one UTF-8 JSON message per line.
The server runs the game at 10 ticks/second and broadcasts state to players and fans.
Clients only send **direction inputs** and render the received state (thin client).

### Message Flow

```
Client                        Server
  |  JOIN {username}   →        |
  |  ←  JOIN_OK / ERR           |
  |  ←  PLAYER_LIST             |
  |  ←  GAME_START              |
  |  INPUT {direction} →        |
  |  ←  GAME_STATE (10/s)       |
  |  ←  GAME_OVER               |
  |  CHAT {text}       →        |
  |  ←  CHAT_RECV               |
  |  WATCH             →        |  (fan)
  |  CHEER {emoji}     →        |  (fan)
  |  ←  CHEER_RECV              |
```
