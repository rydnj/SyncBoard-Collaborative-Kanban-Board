import uuid
from datetime import datetime
from pydantic import BaseModel, EmailStr


# ---------- Auth ----------

class RegisterRequest(BaseModel):
    email: EmailStr  # Validates proper email format automatically
    display_name: str
    password: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    id: uuid.UUID
    email: str
    display_name: str
    created_at: datetime

    # Tells Pydantic to read data from SQLAlchemy model attributes,
    # not just dictionaries. Without this, UserResponse(user) would fail
    # because SQLAlchemy models aren't dicts.
    model_config = {"from_attributes": True}