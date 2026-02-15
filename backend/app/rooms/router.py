import uuid
import string
import random
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.auth.dependencies import get_current_user
from app.models import User, Room, RoomMember, Column
from app.schemas import (
    CreateRoomRequest,
    JoinRoomRequest,
    RoomResponse,
    RoomDetailResponse,
)

router = APIRouter(prefix="/api/rooms", tags=["rooms"])

# Characters for room code generation — uppercase + digits, no ambiguous chars (0/O, 1/I/L)
CODE_CHARS = string.ascii_uppercase.replace("O", "").replace("I", "").replace("L", "") + "23456789"
CODE_LENGTH = 8

DEFAULT_COLUMNS = ["To Do", "In Progress", "Done"]


def generate_room_code(db: Session) -> str:
    """Generate a unique 8-char room code. Retry if collision occurs."""
    for _ in range(10):  # 10 attempts max — collision is astronomically unlikely
        code = "".join(random.choices(CODE_CHARS, k=CODE_LENGTH))
        existing = db.query(Room).filter(Room.room_code == code).first()
        if not existing:
            return code
    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="Failed to generate unique room code",
    )


# ---------- Create Room ----------

@router.post("", response_model=RoomResponse, status_code=status.HTTP_201_CREATED)
def create_room(
    body: CreateRoomRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    room_code = generate_room_code(db)

    room = Room(
        name=body.name,
        room_code=room_code,
        created_by=current_user.id,
    )
    db.add(room)
    db.flush()  # Flush to get room.id without committing — we need it for columns and membership

    # Auto-create the 3 default columns
    for i, title in enumerate(DEFAULT_COLUMNS):
        col = Column(room_id=room.id, title=title, position=i)
        db.add(col)

    # Add creator as a room member automatically
    membership = RoomMember(room_id=room.id, user_id=current_user.id)
    db.add(membership)

    db.commit()
    db.refresh(room)
    return room


# ---------- List User's Rooms ----------

@router.get("", response_model=list[RoomResponse])
def list_rooms(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Join through room_members to find all rooms this user belongs to
    rooms = (
        db.query(Room)
        .join(RoomMember, Room.id == RoomMember.room_id)
        .filter(RoomMember.user_id == current_user.id)
        .order_by(Room.created_at.desc())
        .all()
    )
    return rooms


# ---------- Get Room Detail (Full Board State) ----------

@router.get("/{room_id}", response_model=RoomDetailResponse)
def get_room(
    room_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Verify membership first
    member = (
        db.query(RoomMember)
        .filter(RoomMember.room_id == room_id, RoomMember.user_id == current_user.id)
        .first()
    )
    if not member:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not a member of this room")

    # Eager-load columns and their cards in one query to avoid N+1 problem.
    # Without joinedload, accessing room.columns would trigger a separate query,
    # and then each column.cards would trigger yet another — that's N+1.
    room = (
        db.query(Room)
        .options(
            joinedload(Room.columns).joinedload(Column.cards)
        )
        .filter(Room.id == room_id)
        .first()
    )
    if not room:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Room not found")

    # Sort columns and cards by position before returning.
    # SQLAlchemy loads them in arbitrary order, so we sort in Python.
    room.columns.sort(key=lambda c: c.position)
    for col in room.columns:
        col.cards.sort(key=lambda card: card.position)

    return room


# ---------- Join Room ----------

@router.post("/join", response_model=RoomResponse)
def join_room(
    body: JoinRoomRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    room = db.query(Room).filter(Room.room_code == body.room_code).first()
    if not room:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invalid room code")

    # Check if already a member — don't create duplicate membership
    existing = (
        db.query(RoomMember)
        .filter(RoomMember.room_id == room.id, RoomMember.user_id == current_user.id)
        .first()
    )
    if existing:
        return room  # Silently return the room — idempotent behavior

    membership = RoomMember(room_id=room.id, user_id=current_user.id)
    db.add(membership)
    db.commit()
    return room


# ---------- Delete Room ----------

@router.delete("/{room_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_room(
    room_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    room = db.query(Room).filter(Room.id == room_id).first()
    if not room:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Room not found")

    # Only the room creator can delete it
    if room.created_by != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only the room creator can delete this room")

    db.delete(room)
    db.commit()
    # No return body for 204