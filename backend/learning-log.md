Day 1

Uses of config:

For SyncBoard, our config is small, but in production apps config.py typically also handles things like:

Database pool settings — max connections, pool timeout, overflow limits. Important when your app scales and you need to control how many simultaneous DB connections exist.
Redis/cache URLs — if you had a caching layer or used Redis for WebSocket pub/sub across multiple server instances.
External service credentials — API keys for email providers (SendGrid), file storage (S3 bucket names + keys), OAuth client IDs/secrets.
App behavior toggles — debug mode, log level, rate limiting thresholds, max file upload size.
Environment detection — a field like environment: str = "development" so your code can branch behavior (e.g., skip email sending in dev, use stricter CORS in production).

The core principle is the same for all of these: configuration lives in the environment, not in your code. This is one of the Twelve-Factor App principles — your codebase should be identical across dev, staging, and production, with only environment variables changing. That's exactly what pydantic_settings.BaseSettings gives us: sensible defaults for dev, overridden by env vars in production.

.env mirrors the defaults in config.py — technically redundant for dev, but it's good practice to have the .env file as the explicit source of truth for your local setup. And since .env is in your .gitignore, credentials never end up in the repo.

Uses and setting up Database:

Key thing to understand about get_db(): This is a FastAPI "dependency." Later, when we write route functions, they'll declare db: Session = Depends(get_db) as a parameter. FastAPI sees that, calls get_db(), gives the route a fresh session, and after the response is sent, closes it automatically. This pattern ensures you never leak database connections — a common bug in web apps.

Mapped[type] annotation. This gives you proper type checking — your IDE knows that user.email is a str and user.id is a uuid.UUID. The old Column() approach returned Any, so you'd get no autocomplete or type errors. 


The Entity-Relationship Design

Let's start with why these tables exist and how they relate. The thinking process goes like this:
Start from the user stories: Users register, create rooms, join rooms, and manipulate cards on a board. That gives us our core entities: Users, Rooms, Cards. But cards need to live in columns, and users need to be linked to rooms — so we get Columns and RoomMembers.
The relationships:

User → Room is many-to-many. A user can be in multiple rooms, a room has multiple users. Whenever you have many-to-many in a relational database, you need a junction table — that's room_members. It holds pairs of (room_id, user_id) with the UniqueConstraint preventing duplicates. Without this table, you'd have to store arrays of user IDs in the room (which PostgreSQL can do, but it breaks normalization and makes queries painful).
Room → Column is one-to-many. Each room has exactly one board with multiple columns. A column belongs to one room. Simple foreign key on columns.room_id.
Column → Card is one-to-many. Same pattern — a card lives in one column, a column holds many cards. Foreign key on cards.column_id. When a card is "moved," we just update its column_id and position.
Room → User (creator) is many-to-one. We track who created the room separately from membership because only the creator can delete the room. This is rooms.created_by — a direct foreign key, not a junction table, because each room has exactly one creator.

Why position is an integer: Cards and columns need ordering. The simplest approach is an integer position field. When you move a card, you set its position and re-index the other cards in that column sequentially (0, 1, 2...). There are fancier approaches — fractional indexing (use floats like 1.5 to insert between 1 and 2) or linked lists — but integer re-indexing is easy to understand, easy to debug, and perfectly fine at our scale.
Why UUIDs instead of auto-incrementing integers for primary keys: Two reasons. First, they're generated client-side or application-side without hitting the database, which matters for distributed systems and real-time apps where you might want to create an ID before inserting. Second, they don't leak information — sequential IDs reveal how many users/rooms you have and are guessable. For a portfolio project, UUIDs also signal you've thought about this.

An index is a data structure the database maintains alongside your table to speed up lookups. Without an index on room_id, the query "get all members of this room" would scan every row in the table. With the index, PostgreSQL can jump directly to the matching rows. The tradeoff is that indexes use extra disk space and slow down inserts slightly (because the index must be updated too). For our use case, we read far more often than we write, so indexes are worth it.

Name constraints and indexes for error logging and handling purposes.

NOTE: For interviews, you should be able to explain: why you chose a junction table for room membership, why UUIDs over integers, what indexes do and when to add them, and the difference between database-level constraints and ORM-level relationships. For the build itself: this schema is intentionally simple. No soft deletes, no audit trails, no polymorphism. That's by design — the spec explicitly excludes features like roles, labels, and assignees that would complicate the schema. If an interviewer asks "what would you add?", you can talk about those extensions without having built them.

Alembic

Alembic is a migration tool for SQLAlchemy. Think of it as version control for your database schema — just like git tracks changes to your code, Alembic tracks changes to your tables. Each migration is a script that says "here's what changed and how to undo it." This matters because in production, you can't just drop and recreate tables — you need to evolve the schema without losing data.

First, in `alembic.ini`, find the line that starts with `sqlalchemy.url` and **clear its value** — we'll set it dynamically from our config instead, so leave blank temporarily.

The critical line is from app.models import User, Room, RoomMember, Column, Card. Alembic works by comparing Base.metadata (which knows about all models that inherit from Base) against what's actually in the database. If you forget this import, Alembic sees no models and generates an empty migration. This is the most common Alembic gotcha.

alembic revision --autogenerate -m "initial schema"
alembic upgrade head

Verify by:
psql -h localhost -U syncboard -d syncboard -c "\dt"

The concept you should be able to explain: Migrations exist because you can't just drop and recreate tables in production — real apps have data. Each migration is a versioned, reversible change to the schema. Alembic autogenerate compares your SQLAlchemy models to the live database and figures out the diff. The alembic_version table in your database tracks which migration you're currently on.
One gotcha to remember: Autogenerate doesn't catch everything. It handles adding/removing tables and columns well, but it can miss things like renaming a column (it sees a drop + add instead).

Authentication:

Auth utilities are the low-level building blocks for authentication — hashing passwords so you never store them in plain text, and creating/verifying JWT tokens so the frontend can prove who it is on every request.
Mental model for JWT: A JWT (JSON Web Token) is a signed string containing a payload (like {"user_id": "abc123"}). Your server creates it at login, the frontend stores it, and sends it back with every request. The server can verify the signature to confirm it hasn't been tampered with — no database lookup needed. That's what "stateless auth" means. The tradeoff is you can't easily revoke a token before it expires, but for SyncBoard that's fine.

Why bcrypt specifically: It's intentionally slow — each hash takes ~100ms. That sounds bad, but it's the point. If someone steals your database, they can't brute-force millions of passwords per second like they could with SHA-256. Bcrypt also automatically handles salting (adding random data before hashing), so two users with the same password get different hashes.

FastAPI sees Depends(get_current_user), which itself depends on Depends(bearer_scheme) and Depends(get_db). It resolves the whole chain automatically — extract token from header → verify JWT → get DB session → look up user → pass the User object to your route function. If any step fails, the request never reaches your route code. This is FastAPI's dependency injection system, and it's one of the framework's best features.
Interview check: If someone steals a JWT token, what can they do, and how would you mitigate it in a production system? (Hint: think about token expiration, refresh tokens, and token revocation lists.)

ANSWER: A stolen JWT gives full access as that user until expiration. For SyncBoard I set a 24-hour expiry, which limits the damage window. In a production system, I'd mitigate this in three ways:
First, short-lived access tokens — drop expiration from 24 hours to 15 minutes. This shrinks the window an attacker has.
Second, refresh tokens — when the access token expires, the frontend silently exchanges a longer-lived refresh token (stored in an httpOnly cookie) for a new access token. The user stays logged in without noticing, but any stolen access token becomes useless quickly.
Third, a token revocation list — if you detect a compromised account, you store the token's ID in a blocklist (usually Redis for speed) and check it on every request. This breaks the 'stateless' benefit of JWTs, but it's the only way to instantly invalidate a token before expiry.

In FastAPI, Depends() is magic — FastAPI intercepts it and says "don't use a default, instead call this function and inject the result." So credentials gets populated by FastAPI calling bearer_scheme(), which extracts the Bearer token from the request header.

Pydantic Schemas:

Pydantic schemas define the shape of data going in and out of your API. They're separate from your SQLAlchemy models — models define how data is stored in the database, schemas define how data looks in HTTP requests and responses. This separation matters because you never want to expose everything (like password hashes) and you often want the input shape to differ from the output shape.

EmailStr — this comes from the pydantic[email-validation] extra we installed. It rejects malformed emails before your code even runs. So if someone sends {"email": "notanemail"}, FastAPI returns a 422 validation error automatically.

model_config = {"from_attributes": True} — this is Pydantic v2 syntax (previously called orm_mode in v1). It lets you do UserResponse.model_validate(user) where user is a SQLAlchemy object. Without it, Pydantic would try to treat the SQLAlchemy model like a dictionary and fail.

Auth Router:

Why response_model=TokenResponse — this tells FastAPI to serialize the return value through that Pydantic schema. It strips out any extra fields and validates the response shape. It also generates accurate OpenAPI docs automatically.
Why the same error for "no user" and "wrong password" in the login endpoint — if you returned "user not found" vs "wrong password" separately, an attacker could probe your API to figure out which emails are registered. Using one generic message for both cases is a basic security practice called preventing user enumeration.
db.commit() then db.refresh(user) — commit() saves the new user to PostgreSQL. But the Python object doesn't yet have the auto-generated fields (id, created_at) because those were set by the database. refresh() re-reads the row from the database to populate those fields.

