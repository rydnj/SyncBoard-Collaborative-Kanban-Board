from collections import defaultdict
from fastapi import WebSocket
import json


class ConnectionManager:
    def __init__(self):
        # Maps room_id → list of (websocket, user_dict) tuples
        # defaultdict means we don't need to check if a room key exists before appending
        self.rooms: dict[str, list[tuple[WebSocket, dict]]] = defaultdict(list)

    async def connect(self, websocket: WebSocket, room_id: str, user: dict):
        """Accept the connection and register it under the given room."""
        await websocket.accept()
        # Close and evict any stale connection for this user before registering new one
        for ws, u in self.rooms[room_id]:
            if u["id"] == user["id"]:
                try:
                    await ws.close(code=1000)
                except Exception:
                    pass  # Already closed, ignore
        self.rooms[room_id] = [
            (ws, u) for ws, u in self.rooms[room_id] if u["id"] != user["id"]
        ]
        self.rooms[room_id].append((websocket, user))

    def disconnect(self, websocket: WebSocket, room_id: str):
        """Remove this connection from the room registry. Called on disconnect."""
        self.rooms[room_id] = [
            (ws, u) for ws, u in self.rooms[room_id] if ws != websocket
        ]
        # Clean up the room key if it's now empty
        if not self.rooms[room_id]:
            del self.rooms[room_id]

    def get_users(self, room_id: str) -> list[dict]:
        """Return the list of user dicts currently connected to a room."""
        return [user for _, user in self.rooms.get(room_id, [])]

    async def broadcast(self, room_id: str, message: dict):
        """Send a message to ALL connections in a room."""
        payload = json.dumps(message)
        for ws, _ in self.rooms.get(room_id, []):
            await ws.send_text(payload)

    async def broadcast_except(self, room_id: str, exclude: WebSocket, message: dict):
        """Send a message to all connections in a room EXCEPT the sender."""
        payload = json.dumps(message)
        for ws, _ in self.rooms.get(room_id, []):
            if ws != exclude:
                await ws.send_text(payload)

    async def send_personal(self, websocket: WebSocket, message: dict):
        """Send a message to a single connection (e.g. pong, presence snapshot)."""
        await websocket.send_text(json.dumps(message))


# Single shared instance — imported by the router and handlers
# This is a module-level singleton; all requests share the same manager object
manager = ConnectionManager()