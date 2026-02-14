from datetime import datetime, timedelta, timezone
from jose import jwt, JWTError
from passlib.context import CryptContext
from app.config import settings

# bcrypt context — handles hashing and verification
# "deprecated='auto'" means if we switch algorithms later, old hashes still verify
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    """Hash a plain-text password. Never store the original."""
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Check a plain-text password against its hash. Used at login."""
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(user_id: str) -> str:
    """
    Create a signed JWT containing the user's ID and an expiration time.
    The 'sub' (subject) claim is the standard JWT field for identifying the user.
    """
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_expiration_minutes)
    payload = {
        "sub": user_id,
        "exp": expire,
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def verify_access_token(token: str) -> str | None:
    """
    Decode and validate a JWT. Returns the user_id if valid, None if not.
    python-jose automatically checks expiration — expired tokens raise JWTError.
    """
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        user_id: str | None = payload.get("sub")
        return user_id
    except JWTError:
        return None