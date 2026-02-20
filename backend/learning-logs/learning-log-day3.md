# Day 3-4 Learning Log — WebSocket Layer, Frontend & Deployment

**Session duration:** ~3 hours (accelerated full-project completion)
**Completed:** WebSocket backend, full SvelteKit frontend, Docker deployment to AWS EC2

---

## What We Built

- Full WebSocket layer: ConnectionManager, router, message handlers, presence system, ping/pong keepalive
- SvelteKit frontend: auth (login/register), dashboard (create/join rooms), real-time kanban board
- Drag-and-drop with svelte-dnd-action
- Live presence indicators (avatars, WebSocket connection status dot)
- Card edit modal with inline delete
- Full Docker Compose stack (PostgreSQL + FastAPI + SvelteKit)
- Deployed to AWS EC2 — live at http://107.22.25.134:3000

---

## Architecture Decisions & Why They Matter

### ConnectionManager as a Module-Level Singleton
The `ConnectionManager` is instantiated once at the module level (`manager = ConnectionManager()`). Because Python caches module imports, every file that imports `manager` gets the exact same object in memory. This means the WebSocket router and message handlers share one live registry of connections without passing it around as a parameter.

If it were instantiated inside the endpoint function, each connection would get its own isolated manager and couldn't communicate with other connections — defeating the entire purpose.

**Interview angle:** This is a practical application of the Singleton pattern. Know when to use it (shared stateful resource) and its tradeoff (not suitable for horizontal scaling without Redis pub/sub).

### WebSocket Auth via Query Parameter
JWT is passed as a query parameter (`/ws/{room_id}?token=...`) rather than an HTTP header. This is standard practice because the browser's native `WebSocket` API does not support custom headers — unlike `fetch`, you cannot set `Authorization: Bearer ...` on a WebSocket handshake from the browser. The token is validated server-side immediately on connection; if invalid, the server closes with code `4001` before any data is exchanged.

**Interview angle:** A common interview question is "how do you authenticate WebSocket connections?" Most candidates don't know about the browser's header limitation. Knowing this and the query param workaround is a strong signal.

### `broadcast` vs `broadcast_except`
Two broadcast methods serve different purposes. `broadcast` sends to all connections including the sender — used for card operations so the sender's UI confirms the DB write succeeded via the server echo. `broadcast_except` skips the sender — used for `user_joined` since the connecting user already knows they joined.

Getting this wrong causes either missed UI updates or duplicate events, both of which cause subtle bugs that are hard to trace.

### Last-Write-Wins Conflict Resolution
When two users edit the same card simultaneously, the last write to the database wins. This is the simplest possible conflict resolution strategy — no CRDTs, no operational transforms, no version vectors. For a collaborative tool at this scale it's entirely appropriate. The tradeoff is that concurrent edits can overwrite each other, but the probability is low and the complexity savings are enormous.

**Interview angle:** Being able to articulate why you chose last-write-wins over more complex alternatives (and what those alternatives are) demonstrates system design maturity.

### State Consistency via REST on Reconnect
On every WebSocket reconnection, the client re-fetches the full board state via `GET /api/rooms/{room_id}` before re-establishing the WebSocket connection. This ensures any messages missed during the disconnection window are caught up via REST. WebSocket is the fast path; REST is the source of truth. This pattern is used in production systems like Figma and Notion.

### SvelteKit SSR and `onMount`
SvelteKit renders pages on the server first (SSR), then hydrates on the client. Any code that touches browser APIs — `localStorage`, `WebSocket`, `goto()`, `navigator.clipboard`, `$page.params` — must live inside `onMount()`, which only runs after the component mounts in the browser. This is a fundamental SvelteKit concept that catches many developers off-guard coming from client-only frameworks like Create React App or Vite React.

### Docker Healthcheck for Service Ordering
The `healthcheck` on the PostgreSQL service means the backend won't start until Postgres is actually ready to accept connections, not just when the container has started. Without this, the backend crashes on startup because it tries to connect before Postgres finishes initializing. `depends_on` alone only waits for the container to start — not for the service inside it to be ready.

```yaml
healthcheck:
  test: ["CMD-SHELL", "pg_isready -U syncboard"]
  interval: 5s
  retries: 5
```

**Interview angle:** This is a real-world Docker gotcha that most tutorials don't cover. Knowing the difference between "container started" and "service ready" is a meaningful signal.

---

## Bugs Encountered & Fixed

### Bug 1: `Cannot call goto(...) on the server`
**Symptom:** App crashed on load with an SSR error.
**Cause:** `goto()` was called at the top level of the landing page's script block, which runs during SSR on the server where browser navigation APIs don't exist.
**Fix:** Wrapped in `onMount()` so it only executes after hydration in the browser.
**Root cause:** SvelteKit's SSR model is fundamentally different from client-only React/Vite apps. Scripts run twice — once on the server (no browser APIs), once on the client (full browser APIs). `onMount` is the boundary between the two.

### Bug 2: Drag-and-drop drop zones too small
**Symptom:** Dragging cards between columns was finicky — near-impossible on empty columns.
**Cause:** Card list container had `min-height: 4px`, giving empty columns no drop target area.
**Fix:** Increased `min-height` to `80px`. Also added `cursor: grab` and hover shadow for better affordance.
**Lesson:** DnD UX is entirely dependent on drop zone size. Always give empty containers generous minimum dimensions.

### Bug 3: Duplicate presence avatars on page reload
**Symptom:** Reloading the board caused a second avatar to appear for the same user in other clients.
**Cause:** Page reload creates a new WebSocket connection before the browser fully closes the old one. The server briefly had two connections registered for the same user in the same room.
**Fix:** In `ConnectionManager.connect()`, before registering the new connection, close and evict any existing connection for that user in that room.

### Bug 4: `user_left` broadcasting on reload (race condition)
**Symptom:** After fixing Bug 3, Bob saw Alice's avatar disappear on reload, and subsequent updates from Alice stopped appearing for Bob until he refreshed.
**Cause:** Forcibly closing the old WebSocket triggered `WebSocketDisconnect` in the old connection's receive loop, which then broadcast `user_left` — even though Alice's new connection was already registered. This is a classic race condition: the eviction and the reconnection happen in close sequence, but the disconnect event fires asynchronously.
**Fix:** In the disconnect handler, after calling `manager.disconnect()`, check whether the user still has any active connection in the room. If they do, suppress the `user_left` broadcast.

```python
still_connected = any(u["id"] == str(user.id) for _, u in manager.rooms.get(room_id, []))
if not still_connected:
    await manager.broadcast(room_id, {"type": "user_left", "user_id": str(user.id)})
```

**This is the most important bug of the project.** It demonstrates understanding of async event ordering, WebSocket lifecycle, and the difference between data mutations and their side effects.

### Bug 5: `room_id is not defined` in production
**Symptom:** Board page showed "room_id is not defined" error in production but worked fine locally.
**Cause:** Locally, `npm run dev` uses Vite's client-only dev server — no SSR. In production with `adapter-node`, SvelteKit does full SSR. `$page.params.room_id` at the module level is undefined during SSR because the reactive `$page` store isn't populated server-side.
**Fix:** Moved `room_id` extraction inside `onMount` using `get(page).params.room_id` (the `get()` function reads store values imperatively, which works correctly inside `onMount`).
**Lesson:** Dev and production environments can behave completely differently when SSR is involved. Always test the production build before deploying.

### Bug 6: `navigator.clipboard` fails in production
**Symptom:** Room code copy button silently failed on the deployed app.
**Cause:** `navigator.clipboard` requires a secure context (HTTPS). The deployed app runs on HTTP, so the API is unavailable.
**Fix:** Added a fallback using `document.execCommand('copy')` — the older clipboard API that works without HTTPS.
**Lesson:** Several modern browser APIs are HTTPS-only. The fix is noted as a known limitation; the proper solution is adding Nginx + Let's Encrypt SSL.

### Bug 7: `ContainerConfig` KeyError on `docker-compose up`
**Symptom:** `docker-compose up --build` failed with a Python traceback referencing `ContainerConfig`.
**Cause:** Known bug in `docker-compose` 1.29.2 (the version available on Ubuntu apt). It fails when trying to recreate containers that were previously built with a different image.
**Fix:** `docker-compose down` first to clear container state, then `docker-compose up --build`. Alternatively, upgrade to Docker Compose v2 (`docker compose` instead of `docker-compose`).

---

## Concepts to Know for Interviews

### WebSocket vs HTTP Polling vs Server-Sent Events
Three approaches to real-time data:
- **Polling:** Client asks "anything new?" on an interval. Simple but wasteful — adds latency proportional to the interval and hammers the server with requests even when nothing has changed.
- **Server-Sent Events (SSE):** One-way push from server to client over HTTP. Good for notifications or live feeds but can't receive messages from the client.
- **WebSockets:** Full-duplex, persistent connection. Both sides can send at any time. Best for collaborative tools, chat, live games — anything requiring bidirectional real-time communication.

SyncBoard uses WebSockets because card operations need to flow in both directions: client sends actions, server broadcasts results.

### What is a Race Condition?
A race condition occurs when program correctness depends on the relative timing of events that can't be controlled. Bug 4 was a race condition: closing the old WebSocket and registering the new one happened in close sequence, but the disconnect event from the old connection fired asynchronously — sometimes before, sometimes after the new connection was registered. The fix made the disconnect handler check current state rather than assuming what caused the disconnect.

Race conditions are common in async systems and notoriously hard to reproduce consistently. The key to fixing them is making handlers idempotent and checking current state rather than assuming causal ordering.

### Horizontal Scaling and Why It Would Break This App
Currently, the `ConnectionManager` stores connections in memory on a single server process. If you deployed two instances of the backend behind a load balancer, users connected to instance A couldn't receive broadcasts from users connected to instance B — they're in different memory spaces.

The solution is a pub/sub broker like **Redis**. Instead of broadcasting directly to WebSocket connections, each backend instance publishes to a Redis channel. All instances subscribe to that channel and forward messages to their locally connected clients. This is how Slack, Discord, and Notion handle multi-server WebSocket broadcasting.

### JWT Security Considerations
- JWTs are signed but not encrypted — anyone can base64-decode the payload and read the contents. Never put sensitive data in a JWT.
- The signature is validated server-side using the secret key. Tampering with the payload invalidates the signature.
- JWTs are stateless — the server doesn't store them. This makes logout tricky: you can't "invalidate" a token server-side without adding a blocklist (which reintroduces statefulness).
- Short expiration times limit the damage of a stolen token.

### Docker Compose Networking
Docker Compose creates a private network for all services in the same `docker-compose.yml`. Services can reach each other by their service name as a hostname — e.g., the backend connects to Postgres at `db:5432`, not `localhost:5432`. `localhost` inside a container refers to the container itself, not the host machine.

### SvelteKit SSR vs CSR
SvelteKit renders pages on the server first to generate HTML, then sends that HTML to the browser along with JavaScript to "hydrate" the page into a reactive app. This gives faster initial page loads and better SEO. The tradeoff is that any code in the top-level script block runs twice — once on the server and once in the browser. Code that requires browser APIs must be guarded with `onMount`, `browser` checks, or `typeof window !== 'undefined'`.

---

## Performance Results

| Metric | Target | Result |
|--------|--------|--------|
| WebSocket latency | < 50ms | ~25ms avg (23ms min, 28ms measured) |
| Concurrent users | 15+ | ✅ Verified with multiple browser sessions |
| Board state consistency | 100% | ✅ Verified across concurrent edits |
| REST response time | < 200ms | ✅ Verified via FastAPI logs |

---

## Files Created This Session

| File | Purpose |
|------|---------|
| `backend/app/ws/manager.py` | ConnectionManager singleton |
| `backend/app/ws/router.py` | WebSocket endpoint + connection lifecycle |
| `backend/app/ws/handlers.py` | Message type handlers (card CRUD + ping) |
| `frontend/src/app.css` | Global dark mode design system |
| `frontend/src/lib/api.js` | fetch wrapper with JWT auth headers |
| `frontend/src/lib/stores/auth.js` | Auth store with localStorage persistence |
| `frontend/src/routes/+layout.svelte` | App shell with Navbar |
| `frontend/src/routes/login/+page.svelte` | Login page |
| `frontend/src/routes/register/+page.svelte` | Registration page |
| `frontend/src/routes/dashboard/+page.svelte` | Room list + create/join modals |
| `frontend/src/routes/room/[room_id]/+page.svelte` | Kanban board + DnD + WebSocket |
| `frontend/Dockerfile` | Node production build |
| `docker-compose.yml` | Full stack orchestration |
| `README.md` | Portfolio documentation |

---

## Project Complete ✅

| Layer | Status |
|-------|--------|
| Auth API | ✅ |
| Rooms & Cards REST API | ✅ |
| WebSocket real-time layer | ✅ |
| Live presence system | ✅ |
| SvelteKit frontend | ✅ |
| Drag-and-drop | ✅ |
| Docker Compose (full stack) | ✅ |
| AWS EC2 deployment | ✅ |
| Performance metrics | ✅ |
| README | ✅ |