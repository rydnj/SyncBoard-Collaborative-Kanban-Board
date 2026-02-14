# Day 1: Backend Foundation

## Docker & Docker Compose

**What we did:** Created a `docker-compose.yml` to run PostgreSQL 16 in a container, rather than installing it directly on the machine.

**Key concepts:**
- **Image** — a read-only template/recipe for a piece of software (e.g., `postgres:16`)
- **Container** — a running instance of an image. Isolated process with its own filesystem and networking. Disposable by design.
- **Volume** — persistent storage that survives container restarts. Without the `pgdata` volume, all database data would vanish when the container stops.
- **Port mapping** (`5432:5432`) — bridges your machine's port to the container's port, allowing local apps to connect to the containerized database.
- **`-d` flag** — runs containers in detached (background) mode.

**Why Docker for the database?**
- **Isolation** — no conflicts with other software; clean removal with `docker-compose down -v`
- **Reproducibility** — anyone cloning the repo gets an identical setup with one command
- **Production parity** — the same Compose file (with different credentials) works in deployment

---

## Configuration (`config.py` + `.env`)

**Core principle:** Configuration lives in the environment, not in code — a [Twelve-Factor App](https://12factor.net/config) principle. Your codebase should be identical across dev, staging, and production, with only environment variables changing.

**How it works:** `pydantic_settings.BaseSettings` reads environment variables matching the field names (case-insensitive). Sensible defaults for dev, overridden by env vars in production. The `.env` file (gitignored) is the local source of truth.

**What config typically handles in production apps:**
- Database pool settings (max connections, timeouts)
- Redis/cache URLs
- External service credentials (API keys, OAuth secrets)
- App behavior toggles (debug mode, log level, rate limits)
- Environment detection (`development` vs `production`)

---

## Database Layer (`database.py`)

**SQLAlchemy's two pieces:**
- **Engine** — the connection to your database. Manages a pool of connections and handles low-level communication. Think of it as the *highway* between your app and PostgreSQL.
- **Session** — a conversation with the database. You query, insert, update, then commit or rollback. Each API request gets its own session. Think of it as a *shopping cart* — you add changes, then either checkout (commit) or abandon (rollback).

**`get_db()` dependency:** FastAPI calls this per-request via `Depends(get_db)`, gives the route a fresh session, and guarantees cleanup in the `finally` block. This prevents connection leaks.

---

## ORM Models (`models.py`)

### Entity-Relationship Design

Start from user stories → derive entities → define relationships:

| Relationship | Type | Implementation |
|---|---|---|
| User ↔ Room | Many-to-many | `room_members` junction table with `UniqueConstraint` |
| Room → Column | One-to-many | `columns.room_id` foreign key |
| Column → Card | One-to-many | `cards.column_id` foreign key |
| Room → Creator | Many-to-one | `rooms.created_by` direct foreign key |

### SQLAlchemy 2.0 Syntax

Modern style uses `Mapped[type]` + `mapped_column()` for proper type checking. Old `Column()` style returns `Any` — no autocomplete, no type errors. Functionally identical at the database level.

### Key Design Decisions

- **UUIDs over auto-increment IDs** — generated application-side (no DB round-trip needed), don't leak info (sequential IDs reveal user count and are guessable)
- **Integer positions for ordering** — simple re-indexing (0, 1, 2...) on move. Fancier alternatives (fractional indexing, linked lists) aren't worth the complexity at our scale.

### Table Args, Indexes & Constraints

- **`__table_args__`** — table-level config for things involving multiple columns (composite constraints, indexes)
- **Indexes** — data structures that speed up lookups at the cost of extra disk space and slightly slower inserts. Worth it when you read more than you write. *Think of an index like a book's index — instead of scanning every page, you jump directly to what you need.*
- **`UniqueConstraint("room_id", "user_id")`** — enforced at the database level, so even buggy application code can't create duplicate room memberships
- **Name your constraints** — `name="uq_room_user"` gives readable error messages instead of auto-generated gibberish

### Relationships vs Foreign Keys

| | Foreign Keys | Relationships |
|---|---|---|
| Where | Database level | Python/ORM level |
| Purpose | Enforces referential integrity | Convenience for traversing related objects |
| Example | `ForeignKey("rooms.id")` | `relationship(back_populates="room")` |

**`back_populates`** links both sides — setting `card.column = some_column` automatically adds the card to `some_column.cards`.

### Cascade Behavior (Belt and Suspenders)

- **`ondelete="CASCADE"` on ForeignKey** — database-level, works even from raw SQL or other services
- **`cascade="all, delete-orphan"` on relationship** — ORM-level, handles deletions within Python code. "delete-orphan" means removing a column from `room.columns` in Python also deletes it from the DB.

Having both ensures data integrity regardless of how deletions happen.

### Interview Essentials
> Be able to explain: junction tables for many-to-many, UUIDs vs integers, what indexes do and when to add them, database constraints vs ORM relationships. If asked "what would you add?" — discuss roles, labels, soft deletes, audit trails (all intentionally out of scope).

---

## Alembic (Database Migrations)

**Concept:** Version control for your database schema. Each migration is a versioned, reversible script. *Like git commits, but for your tables.* In production, you can't drop and recreate — you evolve the schema without losing data.

**Commands to know:**
- `alembic revision --autogenerate -m "description"` — generate migration by diffing models vs database
- `alembic upgrade head` — apply all pending migrations
- `alembic downgrade -1` — rollback last migration
- `alembic history` — show migration chain

**Critical gotcha:** You must import all models in `alembic/env.py` so Alembic can see them in `Base.metadata`. Missing imports = empty migration.

**Limitation:** Autogenerate handles adding/removing tables and columns well, but can miss renames (sees drop + add instead).

---

## Authentication

### JWT (JSON Web Tokens)

**Mental model:** A JWT is a signed envelope. The payload inside says who you are (`{"sub": "user_id"}`), and the signature proves the server created it. The server doesn't need to store anything — it just verifies the signature on each request. That's "stateless auth."

**Tradeoff:** You can't easily revoke a token before it expires. For SyncBoard (24-hour expiry), this is acceptable.

### Password Hashing (bcrypt)

**Why bcrypt:** Intentionally slow (~100ms per hash). If someone steals your database, they can't brute-force millions of passwords per second like they could with SHA-256. Also auto-salts, so identical passwords produce different hashes.

### FastAPI Dependency Injection Chain

The `get_current_user` dependency triggers an automatic pipeline:

```
Request → Extract Bearer token (bearer_scheme)
        → Decode & verify JWT (verify_access_token)
        → Get DB session (get_db)
        → Look up user in database
        → Return User object to route function
```

If any step fails, the request is rejected before reaching route code. Dependencies are composable — `get_current_user` itself becomes a `Depends()` for protected routes.

### Interview Q&A: Stolen JWT Mitigation

**Q:** If someone steals a JWT token, what can they do and how would you mitigate it?

**A:** Full access as that user until expiration. Three production mitigations:
1. **Short-lived access tokens** (15 min instead of 24 hrs) — shrinks the attack window
2. **Refresh tokens** — longer-lived token (httpOnly cookie) silently exchanges for new access tokens. Stolen access tokens expire quickly.
3. **Token revocation list** — store invalidated token IDs in Redis, check on every request. Breaks statelessness but is the only way to instantly revoke.

*For SyncBoard:* 24-hour expiry without refresh tokens is the right call — the threat model doesn't justify the complexity.

---

## Pydantic Schemas

**Purpose:** Define the shape of HTTP request/response data, separate from database models. You never want to expose everything (e.g., `password_hash`), and input shapes often differ from output shapes. *Models are the blueprint of your warehouse; schemas are the packing slips for what goes in and out.*

**Key features:**
- **`EmailStr`** — auto-validates email format; malformed emails get a 422 before your code runs
- **`model_config = {"from_attributes": True}`** — lets Pydantic read SQLAlchemy model attributes directly (Pydantic v2 syntax, previously `orm_mode`)
- **`response_model=TokenResponse`** on routes — serializes through the schema, strips extra fields, validates output, and generates accurate API docs

---

## Auth Router Patterns

- **Preventing user enumeration** — login returns the same error for "no user" and "wrong password" so attackers can't probe which emails exist
- **`db.commit()` then `db.refresh(user)`** — commit saves to PostgreSQL, but auto-generated fields (`id`, `created_at`) aren't on the Python object yet. `refresh()` re-reads the row to populate them.
- **Register returns a token** — user is immediately logged in after registration (no redirect to login page)

---

## Compatibility Notes

- `psycopg` v3 (not `psycopg2`) — modern PostgreSQL driver with Python 3.13 support. Only difference: connection string uses `postgresql+psycopg://`
- `bcrypt` pinned to 4.0.1 — `passlib` is unmaintained and breaks with newer bcrypt versions
- `pydantic[email]` — the extra for email validation (not `email-validation`)
