import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.auth.dependencies import get_current_user
from app.models import User, RoomMember, Column, Card
from app.schemas import CreateCardRequest, UpdateCardRequest, CardResponse

router = APIRouter(prefix="/api/rooms/{room_id}/cards", tags=["cards"])


def verify_membership(db: Session, room_id: uuid.UUID, user_id: uuid.UUID):
    """Reusable check — ensures the user belongs to the room."""
    member = (
        db.query(RoomMember)
        .filter(RoomMember.room_id == room_id, RoomMember.user_id == user_id)
        .first()
    )
    if not member:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not a member of this room")


def reindex_column(db: Session, column_id: uuid.UUID):
    """Re-assign positions 0, 1, 2, ... to all cards in a column.
    This is the simple approach from the spec — after any move/delete,
    we just renumber everything sequentially. No gaps, no fractional positions."""
    cards = (
        db.query(Card)
        .filter(Card.column_id == column_id)
        .order_by(Card.position)
        .all()
    )
    for i, card in enumerate(cards):
        card.position = i


# ---------- Create Card ----------

@router.post("", response_model=CardResponse, status_code=status.HTTP_201_CREATED)
def create_card(
    room_id: uuid.UUID,
    body: CreateCardRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    verify_membership(db, room_id, current_user.id)

    # Verify the target column belongs to this room
    column = db.query(Column).filter(Column.id == body.column_id, Column.room_id == room_id).first()
    if not column:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Column not found in this room")

    # New cards go at the bottom — position = count of existing cards
    card_count = db.query(Card).filter(Card.column_id == body.column_id).count()

    card = Card(
        column_id=body.column_id,
        title=body.title,
        description=body.description,
        position=card_count,
        created_by=current_user.id,
    )
    db.add(card)
    db.commit()
    db.refresh(card)
    return card


# ---------- Update Card (including moves) ----------

@router.patch("/{card_id}", response_model=CardResponse)
def update_card(
    room_id: uuid.UUID,
    card_id: uuid.UUID,
    body: UpdateCardRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    verify_membership(db, room_id, current_user.id)

    card = db.query(Card).filter(Card.id == card_id).first()
    if not card:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Card not found")

    # Verify card belongs to a column in this room
    column = db.query(Column).filter(Column.id == card.column_id, Column.room_id == room_id).first()
    if not column:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Card does not belong to this room")

    # Track whether we need to reindex columns
    source_column_id = card.column_id
    moving = body.column_id is not None and body.column_id != card.column_id

    # Apply simple field updates
    if body.title is not None:
        card.title = body.title
    if body.description is not None:
        card.description = body.description

    # Handle column move and/or position change
    if moving:
        # Verify target column belongs to this room
        target_col = db.query(Column).filter(Column.id == body.column_id, Column.room_id == room_id).first()
        if not target_col:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Target column not found in this room")

        card.column_id = body.column_id

        # Set position: use requested position, or default to end of target column
        if body.position is not None:
            card.position = body.position
        else:
            card_count = db.query(Card).filter(Card.column_id == body.column_id, Card.id != card.id).count()
            card.position = card_count

        db.flush()
        # Reindex both source (card left) and target (card arrived) columns
        reindex_column(db, source_column_id)
        reindex_column(db, body.column_id)

    elif body.position is not None:
        # Reordering within the same column
        card.position = body.position
        db.flush()
        reindex_column(db, card.column_id)

    card.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(card)
    return card


# ---------- Delete Card ----------

@router.delete("/{card_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_card(
    room_id: uuid.UUID,
    card_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    verify_membership(db, room_id, current_user.id)

    card = db.query(Card).filter(Card.id == card_id).first()
    if not card:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Card not found")

    # Verify card belongs to this room
    column = db.query(Column).filter(Column.id == card.column_id, Column.room_id == room_id).first()
    if not column:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Card does not belong to this room")

    column_id = card.column_id
    db.delete(card)
    db.flush()
    # Reindex to close the gap left by the deleted card
    reindex_column(db, column_id)
    db.commit()