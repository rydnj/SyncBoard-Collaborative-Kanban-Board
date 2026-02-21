# SyncBoard — Real-Time Collaborative Kanban Workspace

A full-stack collaborative kanban board with live presence tracking, editing indicators, activity feeds, and instant synchronization across all connected users. Built to demonstrate real-time systems, WebSocket architecture, modern frontend development, and cloud deployment.

**Live Demo:** http://34.198.77.126:3000

---

## Demo

> Two users collaborating in real time — card moves, edits, and presence updates appear instantly across all connected sessions.

*(Add demo GIF here)*

---

## Features

### Core
- **Real-time collaboration** — all card operations (create, move, edit, delete) broadcast instantly to all connected room members via WebSockets
- **Live presence** — see who's currently in the room with color-coded avatar indicators and join/leave notifications
- **Kanban board** — drag-and-drop cards between columns (To Do, In Progress, Done) with smooth animations
- **Room system** — create rooms with shareable 8-character codes, join via code, delete rooms with cascading cleanup
- **Authentication** — JWT-based auth with registration and login
- **Persistent state** — full PostgreSQL backend, board state survives page refreshes and reconnections

### Real-Time Features
- **Editing indicators** — see which cards other users are currently editing with a colored border and "Alice is editing..." label (Figma-style)
- **Activity feed** — collapsible sidebar showing a live log of all actions: card creates, moves, edits, deletes, and user join/leave events with timestamps
- **Optimistic updates** — card creates and deletes update the UI instantly without waiting for server confirmation, with automatic correction on broadcast
- **Graceful reconnection** — exponential backoff on WebSocket disconnect with a visible "Reconnecting..." banner, automatic board state re-sync on reconnect, and "Back online!" confirmation

### UX Polish
- **Skeleton loading** — pulsing placeholder UI while board data loads instead of blank screens
- **Toast notifications** — contextual feedback for actions (room created, card deleted, code copied, connection status)
- **Column color accents** — blue (To Do), amber (In Progress), green (Done) top borders for visual clarity
- **Card metadata** — creator avatar and relative timestamps ("2m ago") on each card
- **Keyboard shortcuts** — press `N` to quickly add a card, `Escape` to close any modal
- **Delete confirmations** — safety dialog before permanently deleting cards or rooms
- **Room code copy** — one-click copy with checkmark feedback and toast notification
- **DnD drop zones** — dashed accent border placeholder when dragging cards between columns

---

## Tech Stack

| Layer | Technology | Reason |
|-------|-----------|--------|
| Frontend | SvelteKit | Modern, performant, SSR-capable |
| Backend | FastAPI (Python) | Native async WebSocket support |
| Database | PostgreSQL | Production-grade relational DB |
| ORM | SQLAlchemy 2.0 + Alembic | Industry-standard, clean migrations |
| Auth | JWT (python-jose + passlib/bcrypt) | Stateless, lightweight |
| Real-time | FastAPI WebSockets | No extra infrastructure needed |
| Drag & Drop | svelte-dnd-action | Mature Svelte DnD library |
| Deployment | Docker + Docker Compose + AWS EC2 (t3) | Containerized, production-like |

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Browser (SvelteKit)                   │
│                                                         │
│  ┌──────────┐  ┌──────────┐  ┌────────────────────┐    │
│  │ Auth     │  │Dashboard │  │  Board Page         │    │
│  │ Store    │  │          │  │  (DnD + WS client)  │    │
│  └──────────┘  └──────────┘  └────────────────────┘    │
│       │              │                  │               │
│       └──────────────┴──────────────────┘               │
│                      │                                  │
│           REST (fetch) + WebSocket                       │
└──────────────────────┼──────────────────────────────────┘
                       │
┌──────────────────────┼──────────────────────────────────┐
│              FastAPI Backend                            │
│                      │                                  │
│  ┌───────────┐  ┌─────────────┐  ┌──────────────────┐  │
│  │ Auth API  │  │ Rooms/Cards │  │  WebSocket Layer  │  │
│  │ /register │  │ REST API    │  │  /ws/{room_id}    │  │
│  │ /login    │  │             │  │                   │  │
│  │ /me       │  │             │  │  ConnectionManager│  │
│  └───────────┘  └─────────────┘  │  (in-memory       │  │
│                                  │   registry)       │  │
│                                  └──────────────────┘  │
│                      │                                  │
│              SQLAlchemy ORM                             │
└──────────────────────┼──────────────────────────────────┘
                       │
┌──────────────────────┼──────────────────────────────────┐
│              PostgreSQL Database                        │
│                                                         │
│  users  rooms  room_members  columns  cards             │
└─────────────────────────────────────────────────────────┘
```

### WebSocket Message Flow

```
Client A                    Server                    Client B
   │                           │                          │
   │── card_create ──────────► │                          │
   │                           │── persist to DB          │
   │                           │── broadcast ────────────►│
   │◄──────────────────────────│   card_created           │
   │        card_created       │                          │
```

### Connection Lifecycle

1. Client connects to `/ws/{room_id}?token={jwt}`
2. Server validates JWT and verifies room membership
3. Server evicts any stale connection for the same user (handles page reloads)
4. Server broadcasts `user_joined` to all other members
5. Server sends `presence` snapshot to the new client
6. Messages flow bidirectionally until disconnect
7. On disconnect, server broadcasts `user_left` (only if no other active connection for that user exists)
8. Client enters exponential backoff reconnection (1s → 2s → 4s → 8s → 16s, max 30s, 5 attempts)
9. On successful reconnect, client re-fetches full board state via REST for consistency
10. If room was deleted during disconnection, client detects 403/404 and redirects to dashboard

---

## Database Schema

```
users
  id            UUID PRIMARY KEY
  email         VARCHAR(255) UNIQUE
  display_name  VARCHAR(100)
  password_hash VARCHAR(255)
  created_at    TIMESTAMP

rooms
  id            UUID PRIMARY KEY
  name          VARCHAR(200)
  room_code     VARCHAR(8) UNIQUE
  created_by    UUID → users.id (CASCADE)
  created_at    TIMESTAMP

room_members
  id            UUID PRIMARY KEY
  room_id       UUID → rooms.id (CASCADE)
  user_id       UUID → users.id (CASCADE)
  joined_at     TIMESTAMP
  UNIQUE(room_id, user_id)

columns
  id            UUID PRIMARY KEY
  room_id       UUID → rooms.id (CASCADE)
  title         VARCHAR(100)
  position      INTEGER

cards
  id            UUID PRIMARY KEY
  column_id     UUID → columns.id (CASCADE)
  title         VARCHAR(300)
  description   TEXT
  position      INTEGER
  created_by    UUID → users.id
  created_at    TIMESTAMP
  updated_at    TIMESTAMP
```

---

## API Reference

### Auth
```
POST   /api/auth/register     — Register new user
POST   /api/auth/login        — Login, returns JWT
GET    /api/auth/me           — Get current user (protected)
```

### Rooms
```
POST   /api/rooms             — Create room (auto-generates code + 3 default columns)
GET    /api/rooms             — List user's rooms
GET    /api/rooms/{room_id}   — Get full board state (columns + cards)
POST   /api/rooms/join        — Join room via room_code
DELETE /api/rooms/{room_id}   — Delete room (creator only, cascading delete)
```

### Cards
```
POST   /api/rooms/{room_id}/cards             — Create card
PATCH  /api/rooms/{room_id}/cards/{card_id}   — Update card
DELETE /api/rooms/{room_id}/cards/{card_id}   — Delete card
```

### WebSocket
```
WS /ws/{room_id}?token={jwt}  — Real-time room channel
```

#### Client → Server Messages
```json
{ "type": "card_create", "column_id": "...", "title": "...", "description": "" }
{ "type": "card_move",   "card_id": "...", "to_column_id": "...", "to_position": 0 }
{ "type": "card_update", "card_id": "...", "title": "...", "description": "..." }
{ "type": "card_delete", "card_id": "..." }
{ "type": "card_focus",  "card_id": "..." }
{ "type": "card_blur",   "card_id": "..." }
{ "type": "ping" }
```

#### Server → Client Messages
```json
{ "type": "card_created",  "card": { ...card object... }, "by": "user_id" }
{ "type": "card_moved",    "card_id": "...", "to_column_id": "...", "to_position": 0 }
{ "type": "card_updated",  "card_id": "...", "title": "...", "description": "..." }
{ "type": "card_deleted",  "card_id": "..." }
{ "type": "card_focused",  "card_id": "...", "user_id": "...", "display_name": "..." }
{ "type": "card_blurred",  "card_id": "...", "user_id": "..." }
{ "type": "user_joined",   "user": { "id": "...", "display_name": "..." } }
{ "type": "user_left",     "user_id": "..." }
{ "type": "presence",      "users": [ ... ] }
{ "type": "pong" }
```

---

## Key Implementation Details

### Position Management
Cards use integer positions. On move, the backend temporarily sets the moved card's position to -1, reindexes the source column to close the gap, shifts target column cards to make room, then places the card at the exact requested position. This avoids conflicts from duplicate positions during concurrent operations.

### Optimistic Updates
Card creates and deletes update the UI immediately using temporary IDs. When the server broadcasts the confirmed state, the temp card is replaced with the real one (matched by title and column). Deletes are idempotent — if the broadcast arrives after the optimistic removal, the filter is a no-op.

### Editing Indicators
Focus/blur messages are relayed through the WebSocket without database persistence. When a user opens the edit modal, `card_focus` is sent. The server broadcasts `card_focused` to all other room members via `broadcast_except`, who display a colored border and label. On modal close, `card_blur` clears the indicator.

### Reconnection Strategy
Exponential backoff (1s, 2s, 4s, 8s, 16s, max 30s) with 5 attempts. On successful reconnect, the full board state is re-fetched via REST to catch any missed messages. If the room was deleted during disconnection, the client detects the 403/404 and redirects to the dashboard.

---

## Performance Metrics

| Metric | Target | Result |
|--------|--------|--------|
| WebSocket message latency | < 50ms | ~25ms avg |
| Concurrent users per room | 15+ stable | ✅ Verified |
| Board state consistency | 100% | ✅ Verified across concurrent sessions |
| REST API response time | < 200ms | 33-36ms avg (client → AWS EC2 t3) |

---

## Project Structure

```
syncboard/
├── docker-compose.yml
├── backend/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── alembic/
│   │   └── versions/
│   ├── alembic.ini
│   └── app/
│       ├── main.py              # FastAPI app, CORS, router mounts
│       ├── config.py            # Settings (env vars, JWT, CORS)
│       ├── database.py          # SQLAlchemy engine + session
│       ├── models.py            # ORM models (5 tables)
│       ├── schemas.py           # Pydantic request/response schemas
│       ├── auth/
│       │   ├── router.py        # register, login, me
│       │   ├── utils.py         # bcrypt hashing, JWT encode/decode
│       │   └── dependencies.py  # get_current_user dependency
│       ├── rooms/
│       │   └── router.py        # room CRUD + join
│       ├── cards/
│       │   └── router.py        # card CRUD + position reindexing
│       └── ws/
│           ├── router.py        # WebSocket endpoint + lifecycle
│           ├── manager.py       # ConnectionManager singleton
│           └── handlers.py      # message type handlers (incl. focus/blur)
└── frontend/
    ├── Dockerfile
    ├── package.json
    ├── svelte.config.js
    └── src/
        ├── app.css              # Global dark mode styles + design tokens
        ├── routes/
        │   ├── +layout.svelte   # Navbar, auth-aware layout, Toast mount
        │   ├── +page.svelte     # Landing redirect
        │   ├── login/
        │   ├── register/
        │   ├── dashboard/       # Room list, create/join/delete modals
        │   └── room/[room_id]/  # Kanban board, WS, DnD, activity feed
        └── lib/
            ├── api.js           # fetch wrapper with JWT headers
            ├── stores/
            │   ├── auth.js      # token + user store (localStorage)
            │   ├── toast.js     # toast notification store
            │   ├── board.js     # board state store
            │   └── websocket.js # WS connection lifecycle
            └── components/
                └── Toast.svelte # toast notification component
```

---

## Local Development Setup

### Prerequisites
- Docker + Docker Compose
- Node.js 20+
- Python 3.11+

### 1. Clone the repo
```bash
git clone https://github.com/rydnj/SyncBoard-Collaborative-Kanban-Board.git
cd SyncBoard-Collaborative-Kanban-Board
```

### 2. Start the full stack
```bash
docker-compose up --build
```

This starts:
- PostgreSQL on port 5432
- FastAPI backend on port 8000
- SvelteKit frontend on port 3000

### 3. Run database migrations
```bash
docker-compose exec backend alembic upgrade head
```

### 4. Open the app
- Frontend: http://localhost:3000
- API docs: http://localhost:8000/docs

### 5. Backend development (without Docker)
```bash
cd backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

### 6. Frontend development (without Docker)
```bash
cd frontend
npm install
npm run dev
```

Frontend dev server runs at `http://localhost:5173`, backend at `http://localhost:8000`.

---

## Deployment (AWS EC2)

### Infrastructure
- **Instance:** t3.micro
- **OS:** Ubuntu 24.04 LTS
- **Ports open:** 22 (SSH), 3000 (frontend), 8000 (backend)

### Deploy steps
```bash
# 1. SSH into instance
ssh -i ~/.ssh/your-key.pem ubuntu@YOUR_EC2_IP

# 2. Install Docker
sudo apt-get update
sudo apt-get install -y docker.io docker-compose
sudo systemctl enable docker
sudo usermod -aG docker ubuntu

# 3. Clone repo and configure
git clone https://github.com/rydnj/SyncBoard-Collaborative-Kanban-Board.git
cd SyncBoard-Collaborative-Kanban-Board

# 4. Build and run
docker-compose up --build -d

# 5. Run migrations
docker-compose exec backend alembic upgrade head
```

### Update deployment
```bash
git pull origin main
docker-compose up --build -d
```

---

## Known Limitations & Future Improvements

- **HTTP only** — HTTPS can be added via Nginx reverse proxy + Let's Encrypt SSL
- **Single server** — WebSocket ConnectionManager is in-memory; horizontal scaling would require Redis pub/sub for cross-instance broadcasts
- **Last-write-wins** — no conflict resolution beyond simple overwrite; CRDT-based merging would be needed for offline-first support
- **No rate limiting** — WebSocket messages are not rate-limited per user
- **JWT secret** — hardcoded default in config; should be injected via environment variable in production
- **No mobile responsiveness** — desktop-first design; responsive layout would require CSS media queries

---

## Resume Bullets

- "Built a real-time collaborative kanban workspace using SvelteKit and FastAPI WebSockets, supporting 15+ concurrent users with ~25ms synchronization latency"
- "Engineered WebSocket-based state synchronization protocol with live presence tracking, editing indicators, and optimistic updates, achieving 100% board consistency across concurrent sessions"
- "Implemented Figma-style editing indicators and real-time activity feeds using a custom WebSocket message protocol with 14 event types"
- "Deployed full-stack application with Docker on AWS EC2 (t3), serving a PostgreSQL-backed workspace with JWT authentication and persistent real-time collaboration"

---

## License

MIT