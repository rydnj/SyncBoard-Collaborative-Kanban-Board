# Day 2: Rooms & Cards API

## Pydantic Schemas — Response Design

**Multiple response schemas for the same resource.** We have `RoomResponse` (lightweight — just name, code, timestamps) and `RoomDetailResponse` (full nested structure — room → columns → cards). The dashboard listing uses `RoomResponse` because it only needs names and codes. The board view uses `RoomDetailResponse` because it needs everything to render. This avoids wastefully loading every card in every room just to show a list of room names.

**Nesting pattern.** `RoomDetailResponse` contains a list of `ColumnResponse`, which each contain a list of `CardResponse`. This means a single `GET /api/rooms/{room_id}` call returns everything the frontend needs to render the full board. One request, one response, full state — this becomes important on Day 5 when the frontend loads a board and also on WebSocket reconnection when we need to re-sync.

## PUT vs PATCH

**PUT** = replace the entire resource. All fields required. You're saying "here is the complete new version."

**PATCH** = partial update. Only send what changed. Fields you don't include stay as they were.

We use PATCH for card updates — `UpdateCardRequest` has all optional fields. If a field is `None`, we skip it; if it has a value, we update it. This lets the client send `{"title": "new name"}` to rename, or `{"column_id": "...", "position": 2}` to move, without needing to resend everything.

## Room ID vs Room Code

- **`room_id`** (UUID) — internal system identifier, used in API paths like `/api/rooms/{room_id}`. The database and code reference this.
- **`room_code`** (8-char string like `"X7KN3P9W"`) — human-friendly code for sharing. Only used in the `/join` endpoint.

Like a Zoom meeting — there's an internal meeting ID in Zoom's database, but you share the short code with people.

The code character set excludes visually ambiguous characters (`O`/`0`, `I`/`1`/`L`) so people don't mistype when entering manually.

## Room Creation — Multiple Operations in One Transaction

Creating a room actually does three things: creates the room record, creates 3 default columns (To Do, In Progress, Done), and adds the creator as a room member. These all need to succeed or fail together.

**`flush()` vs `commit()`** — `flush()` sends SQL to the database and generates IDs (like the room's UUID) but doesn't finalize the transaction. This lets us use `room.id` when creating columns and the membership row. `commit()` makes everything permanent. If anything fails after a flush but before commit, the entire transaction rolls back — no partial state. This is how you keep multiple related inserts **atomic** (all-or-nothing).

## The N+1 Query Problem

One of the most common database performance issues in web apps.

**The problem:** You load a room (1 query). Then you access its columns — SQLAlchemy lazily fires 1 query per column. Then for each column, accessing its cards fires another query per column. For 3 columns: 1 + 3 + 3 = 7 queries. For 20 columns: 1 + 20 + 20 = 41 queries. That's "N+1" — 1 initial query + N follow-ups.

**The fix:** `joinedload` in SQLAlchemy. It tells the ORM to fetch everything in one SQL JOIN:

```python
db.query(Room).options(
    joinedload(Room.columns).joinedload(Column.cards)
).filter(Room.id == room_id).first()
```

One query instead of many. This is a very common interview question — interviewers want to know you understand lazy vs eager loading and can spot N+1 in the wild.

## Position Management for Cards

Every column's cards have sequential integer positions (0, 1, 2...). When cards are created, moved, or deleted, positions need to stay clean — no gaps, no duplicates.

**The approach:** A `reindex_column` helper that grabs all cards in a column ordered by position and renumbers them sequentially. It runs after every change:

- **Create** — new card gets position = count of existing cards (appended to bottom)
- **Move** — set the card's new column/position, then reindex both the source column (close the gap) and target column (absorb the arrival)
- **Delete** — remove the card, reindex the column to close the gap

We `flush()` before reindexing so the query sees the updated state, then `commit()` only after everything is consistent. Simple and reliable — no fractional positions or gap-based schemes needed.

## Membership Validation

Every card and room-detail endpoint checks that the current user is a member of the room before proceeding. This is a `verify_membership` helper that queries `room_members` and raises 403 if the user isn't found. Room deletion has an additional check — only the `created_by` user can delete.

This pattern matters because on Day 3, the WebSocket layer will use the same membership check on connection. If you're not a room member, you can't read or write anything — REST or WebSocket.

## Idempotent Join

If a user tries to join a room they're already in, we silently return the room instead of throwing an error. This is **idempotent** behavior — performing the same operation multiple times produces the same result. It avoids issues like double-clicking a join button causing an error, or race conditions from multiple requests.

## Files Created/Modified Today

| File | Purpose |
|------|---------|
| `backend/app/schemas.py` | Added room and card request/response schemas |
| `backend/app/rooms/router.py` | Room CRUD: create, list, get detail, join, delete |
| `backend/app/cards/router.py` | Card CRUD: create, update/move, delete with position reindexing |
| `backend/app/main.py` | Mounted room and card routers |
