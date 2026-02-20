from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.auth.utils import verify_access_token
from app.models import User, RoomMember
from app.ws.manager import manager
from app.ws.handlers import handle_message

router = APIRouter()


def get_db():
    db = SessionLocal()
    try:
        return db
    finally:
        pass  # We'll close manually below to keep session alive for async scope


@router.websocket("/ws/{room_id}")
async def websocket_endpoint(websocket: WebSocket, room_id: str):
    db: Session = SessionLocal()
    user = None
    try:
        # --- Auth: validate JWT from query param ---
        token = websocket.query_params.get("token")
        if not token:
            await websocket.close(code=4001)
            return

        user_id = verify_access_token(token)
        if not user_id:
            await websocket.close(code=4001)
            return
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            await websocket.close(code=4001)
            return

        # --- Authorization: verify room membership ---
        member = db.query(RoomMember).filter(
            RoomMember.room_id == room_id,
            RoomMember.user_id == user_id
        ).first()
        if not member:
            await websocket.close(code=4003)
            return

        # --- Connect and broadcast presence ---
        user_dict = {"id": str(user.id), "display_name": user.display_name}
        await manager.connect(websocket, room_id, user_dict)

        # Tell everyone else this user joined
        await manager.broadcast_except(room_id, websocket, {
            "type": "user_joined",
            "user": user_dict
        })

        # Send current presence snapshot to the newly connected client
        await manager.send_personal(websocket, {
            "type": "presence",
            "users": manager.get_users(room_id)
        })

        # --- Main receive loop ---
        while True:
            data = await websocket.receive_json()
            await handle_message(websocket, room_id, user_dict, data, db)

    except WebSocketDisconnect:
        if user:
            manager.disconnect(websocket, room_id)
            # Only broadcast user_left if this user has no other active connection in the room
            still_connected = any(u["id"] == str(user.id) for _, u in manager.rooms.get(room_id, []))
            if not still_connected:
                await manager.broadcast(room_id, {
                    "type": "user_left",
                    "user_id": str(user.id)
                })
    finally:
        db.close()