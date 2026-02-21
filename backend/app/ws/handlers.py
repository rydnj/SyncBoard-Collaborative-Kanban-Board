from fastapi import WebSocket
from sqlalchemy.orm import Session
from app.models import Card, Column
from app.ws.manager import manager
import uuid


async def handle_message(ws: WebSocket, room_id: str, user: dict, data: dict, db: Session):
    """Route incoming WebSocket messages to the appropriate handler."""
    t = data.get("type")
    if t == "card_create":
        await handle_card_create(ws, room_id, user, data, db)
    elif t == "card_move":
        await handle_card_move(ws, room_id, user, data, db)
    elif t == "card_update":
        await handle_card_update(ws, room_id, user, data, db)
    elif t == "card_delete":
        await handle_card_delete(ws, room_id, user, data, db)
    elif t == "card_focus":
        await handle_card_focus(ws, room_id, user, data)
    elif t == "card_blur":
        await handle_card_blur(ws, room_id, user, data)
    elif t == "ping":
        await manager.send_personal(ws, {"type": "pong", "sentAt": data.get("sentAt", 0)})


def reindex_column(db: Session, column_id: str):
    """Re-assign sequential positions (0,1,2...) to all cards in a column."""
    cards = db.query(Card).filter(Card.column_id == column_id).order_by(Card.position).all()
    for i, card in enumerate(cards):
        card.position = i
    db.flush()


async def handle_card_create(ws: WebSocket, room_id: str, user: dict, data: dict, db: Session):
    column_id = data.get("column_id")
    title = data.get("title", "").strip()
    if not column_id or not title:
        return

    count = db.query(Card).filter(Card.column_id == column_id).count()
    card = Card(
        id=uuid.uuid4(),
        column_id=column_id,
        title=title,
        description=data.get("description", ""),
        position=count,
        created_by=user["id"]
    )
    db.add(card)
    db.commit()
    db.refresh(card)

    await manager.broadcast(room_id, {
        "type": "card_created",
        "card": {
            "id": str(card.id),
            "column_id": str(card.column_id),
            "title": card.title,
            "description": card.description,
            "position": card.position,
            "created_by": str(card.created_by)
        },
        "by": user["id"]
    })


async def handle_card_move(ws: WebSocket, room_id: str, user: dict, data: dict, db: Session):
    card_id = data.get("card_id")
    to_column_id = data.get("to_column_id")
    to_position = data.get("to_position", 0)

    card = db.query(Card).filter(Card.id == card_id).first()
    if not card:
        return

    old_column_id = str(card.column_id)

    card.column_id = to_column_id
    card.position = -1
    db.flush()

    if old_column_id != to_column_id:
        reindex_column(db, old_column_id)

    target_cards = (
        db.query(Card)
        .filter(Card.column_id == to_column_id, Card.id != card.id)
        .order_by(Card.position)
        .all()
    )
    for i, c in enumerate(target_cards):
        if i >= to_position:
            c.position = i + 1
        else:
            c.position = i
    db.flush()

    card.position = to_position
    db.commit()

    await manager.broadcast(room_id, {
        "type": "card_moved",
        "card_id": card_id,
        "to_column_id": to_column_id,
        "to_position": to_position,
        "by": user["id"]
    })


async def handle_card_update(ws: WebSocket, room_id: str, user: dict, data: dict, db: Session):
    card_id = data.get("card_id")
    card = db.query(Card).filter(Card.id == card_id).first()
    if not card:
        return

    if "title" in data:
        card.title = data["title"]
    if "description" in data:
        card.description = data["description"]

    db.commit()

    await manager.broadcast(room_id, {
        "type": "card_updated",
        "card_id": card_id,
        "title": card.title,
        "description": card.description,
        "by": user["id"]
    })


async def handle_card_delete(ws: WebSocket, room_id: str, user: dict, data: dict, db: Session):
    card_id = data.get("card_id")
    card = db.query(Card).filter(Card.id == card_id).first()
    if not card:
        return

    column_id = str(card.column_id)
    db.delete(card)
    db.flush()
    reindex_column(db, column_id)
    db.commit()

    await manager.broadcast(room_id, {
        "type": "card_deleted",
        "card_id": card_id,
        "by": user["id"]
    })


# ---------- Focus/Blur (no DB, just relay to other clients) ----------

async def handle_card_focus(ws: WebSocket, room_id: str, user: dict, data: dict):
    """User opened edit modal on a card — tell everyone else."""
    await manager.broadcast_except(room_id, ws, {
        "type": "card_focused",
        "card_id": data.get("card_id"),
        "user_id": user["id"],
        "display_name": user["display_name"]
    })


async def handle_card_blur(ws: WebSocket, room_id: str, user: dict, data: dict):
    """User closed edit modal — tell everyone else to clear the indicator."""
    await manager.broadcast_except(room_id, ws, {
        "type": "card_blurred",
        "card_id": data.get("card_id"),
        "user_id": user["id"]
    })