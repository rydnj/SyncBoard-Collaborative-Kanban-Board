from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from app.config import settings

# Engine: manages the connection pool to PostgreSQL
engine = create_engine(settings.database_url)

# SessionLocal: factory that produces new database sessions
# autocommit=False means we control when changes are saved
# autoflush=False means we control when pending changes are sent to the DB
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


# Base class for all ORM models — every table class will inherit from this
class Base(DeclarativeBase):
    pass


def get_db():
    """
    FastAPI dependency that provides a database session per request.
    The `yield` makes this a generator — FastAPI calls next() to get the session,
    then after the request completes, execution continues past yield to close it.
    This guarantees the session is always cleaned up, even if the request errors.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()