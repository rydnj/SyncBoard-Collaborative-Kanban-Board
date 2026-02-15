import uuid
from datetime import datetime
from typing import Optional
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


# ---------- Cards ----------

class CreateCardRequest(BaseModel):
    column_id: uuid.UUID
    title: str
    description: str = ""


class UpdateCardRequest(BaseModel):
    # All fields optional — client sends only what changed.
    # This is what makes it a PATCH (partial update) rather than PUT (full replace).
    title: Optional[str] = None
    description: Optional[str] = None
    column_id: Optional[uuid.UUID] = None  # Moving to a different column
    position: Optional[int] = None         # Reordering within a column


class CardResponse(BaseModel):
    id: uuid.UUID
    column_id: uuid.UUID
    title: str
    description: str
    position: int
    created_by: uuid.UUID
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ---------- Columns ----------

class ColumnResponse(BaseModel):
    id: uuid.UUID
    title: str
    position: int
    # Nested cards — when we return a column, we include its cards sorted by position.
    # This avoids the client needing a separate request per column.
    cards: list[CardResponse] = []

    model_config = {"from_attributes": True}


# ---------- Rooms ----------

class CreateRoomRequest(BaseModel):
    name: str


class JoinRoomRequest(BaseModel):
    room_code: str


class RoomResponse(BaseModel):
    """Used in the dashboard room list — lightweight, no nested board data."""
    id: uuid.UUID
    name: str
    room_code: str
    created_by: uuid.UUID
    created_at: datetime

    model_config = {"from_attributes": True}


class RoomDetailResponse(BaseModel):
    """Used when loading a specific board — full nested structure.
    This is the single response that hydrates the entire kanban view."""
    id: uuid.UUID
    name: str
    room_code: str
    created_by: uuid.UUID
    created_at: datetime
    columns: list[ColumnResponse] = []

    model_config = {"from_attributes": True}

