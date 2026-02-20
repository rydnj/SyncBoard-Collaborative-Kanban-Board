# Day 3 Learning Log — WebSocket Layer & Frontend Foundation

## What We Built
- Full WebSocket layer: ConnectionManager, router, message handlers, presence system, ping/pong
- SvelteKit frontend: auth (login/register), dashboard (create/join rooms), real-time kanban board
- Drag-and-drop with svelte-dnd-action
- Live presence indicators (avatars, connection status dot)
- Card edit modal, add card inline form

---

## Architecture Decisions

### ConnectionManager as a Module-Level Singleton
The `ConnectionManager` is instantiated once at the module level (`manager = ConnectionManager()`). Because Python caches module imports, every file that imports `manager` gets the exact same object in memory. This means the WebSocket router and message handlers share one live registry of connections without passing it around as a parameter. If it were instantiated inside the endpoint function, each connection would get its own isolated manager and couldn't communicate with other connections.

### WebSocket Auth via Query Parameter
JWT is passed as a query parameter (`/ws/{room_id}?token=...`) rather than an HTTP header. This is standard practice because the browser's native `WebSocket` API does not support custom headers — unlike `fetch`, you cannot set `Authorization: Bearer ...` on a WebSocket handshake from the browser. The token is validated server-side immediately on connection; if invalid, the server closes with code `4001` before any data is exchanged.

### `broadcast` vs `broadcast_except`
Two broadcast methods serve different purposes. `broadcast` sends to all connections including the sender — used for card operations so the sender's UI confirms the DB write succeeded. `broadcast_except` skips the sender — used for `user_joined` since the connecting user already knows they joined. Getting this wrong causes either missed updates or duplicate UI events.

### `defaultdict(list)` for Room Registry
Using `collections.defaultdict(list)` means accessing a room key that doesn't exist yet automatically creates an empty list. This avoids defensive `if room_id not in self.rooms` checks throughout the codebase and makes the connection logic cleaner.

### Svelte `onMount` for Browser-Only Code
SvelteKit renders pages on the server first (SSR), then hydrates on the client. Any code that touches browser APIs — `localStorage`, `WebSocket`, `goto()`, `navigator.clipboard` — must live inside `onMount()`, which only runs after the component mounts in the browser. Running `goto()` outside `onMount` caused the first bug of the day.

### svelte-dnd-action `items` Pattern
The library requires each drop zone to have an `items` array it controls. Columns needed to be transformed from the API's `cards` array into an `items` array on load. The `consider` event fires during drag (for visual feedback) and `finalize` fires on drop (when we send the WebSocket message). Only `finalize` triggers a DB write — `consider` is purely local UI state.

---

## Bugs Encountered & Fixed

### Bug 1: `Cannot call goto(...) on the server`
**Symptom:** App crashed on load with a server-side rendering error.
**Cause:** `goto()` was called at the top level of the landing page's `<script>` block, which runs during SSR on the server where browser navigation APIs don't exist.
**Fix:** Wrapped in `onMount()` so it only executes after hydration in the browser.
**Lesson:** In SvelteKit, anything that requires a browser environment must be inside `onMount`. This is a common gotcha when coming from client-only frameworks like Create React App.

### Bug 2: Drag-and-drop drop zones too small to hit
**Symptom:** Dragging cards between columns was finicky — hard to find the target area, especially on empty columns.
**Cause:** The card list container had `min-height: 4px`, making empty columns nearly impossible to drop into.
**Fix:** Increased `min-height` to `80px` so empty columns always present a large enough drop target. Also added `cursor: grab` and a box shadow on hover for better affordance.
**Lesson:** DnD UX depends heavily on drop zone size. Always give empty containers generous minimum dimensions.

### Bug 3: Duplicate presence avatars on page reload
**Symptom:** Reloading the board page caused a second avatar for the same user to appear for other room members.
**Cause:** When the page reloads, a new WebSocket connection is established before the browser fully closes the old one. The server briefly had two connections for the same user registered under the same room.
**Fix:** In `ConnectionManager.connect()`, before registering the new connection, we close any existing connection for that user and evict it from the registry.

### Bug 4: `user_left` firing on reload, breaking sync
**Symptom:** After fixing Bug 3, Bob saw Alice's avatar disappear when she reloaded, and subsequent card updates from Alice didn't appear for Bob until he refreshed.
**Cause:** Forcibly closing the old WebSocket in `connect()` triggered `WebSocketDisconnect` in the old connection's receive loop, which then broadcast `user_left` — even though Alice's new connection was already registered. Bob's frontend removed Alice from `activeUsers`, and the stale disconnect handler was racing with the new connection.
**Fix:** In the disconnect handler in the router, after calling `manager.disconnect()`, check whether the user still has any active connection in the room before broadcasting `user_left`. If they do (because a new connection was just registered), suppress the broadcast.
**Lesson:** WebSocket lifecycle events can race. Evicting a connection isn't purely a data structure operation — it has side effects (disconnect events) that need to be accounted for. The fix required coordinating between the manager (data) and the router (event handling).

---

## Key Concepts to Know for Interviews

**Q: Why use WebSockets instead of polling for this use case?**
Polling requires the client to repeatedly ask "anything new?" on an interval — wasteful and adds latency proportional to the poll interval. WebSockets establish a persistent, full-duplex connection so the server can push updates to clients instantly with no repeated handshakes. For a collaborative tool where sub-second latency matters, WebSockets are the right tool.

**Q: What is a race condition and where did you encounter one?**
A race condition is when the correctness of a program depends on the relative timing of events that can't be controlled. Bug 4 was a race condition: closing the old WebSocket and registering the new one happened in close sequence, but the disconnect event from the old connection could fire at any point — including after the new connection was registered — causing incorrect `user_left` broadcasts. Fixed by making the disconnect handler check current state rather than assuming it knows what caused the disconnect.

**Q: How does the frontend stay consistent if a WebSocket message is missed during a brief disconnect?**
On every reconnection, the client re-fetches the full board state via `GET /api/rooms/{room_id}` before re-establishing the WebSocket. This ensures any messages missed during the disconnection window are caught up via REST. WebSocket is the fast path; REST is the source of truth.

**Q: Why is the `ConnectionManager` a singleton and not a database table?**
Active WebSocket connections are in-memory, ephemeral objects — they can't be serialized to a database. The manager needs to hold live references to open socket connections to send messages to them. A database could store presence metadata (who's online) but not the actual connection handles. In a multi-server deployment, you'd need a pub/sub system like Redis to coordinate broadcasts across instances — but for a single-server portfolio deployment, an in-memory singleton is correct and sufficient.

---

## Progress Summary
| Layer | Status |
|-------|--------|
| Auth API | ✅ Complete |
| Rooms & Cards API | ✅ Complete |
| WebSocket layer | ✅ Complete |
| SvelteKit auth pages | ✅ Complete |
| Dashboard | ✅ Complete |
| Kanban board + DnD | ✅ Complete |
| Real-time sync | ✅ Complete |
| Live presence | ✅ Complete |
| Production env config | 🔜 Next |
| Docker + deployment | 🔜 Next |
