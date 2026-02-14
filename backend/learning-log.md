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

