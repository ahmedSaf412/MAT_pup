# backend/app/routers/live_session.py
# WebSocket endpoint for coach real-time monitoring
#
# Flow:
#   Coach connects: ws://host/ws/live/{session_id}?token=<JWT>
#   Trainee does reps → classify.py broadcasts each Detection event
#   Coach receives JSON with move, confidence, corrections in real-time

import json
import asyncio
from typing import Dict, List

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query, HTTPException
from jose import JWTError

from app.config import SECRET_KEY, ALGORITHM
from app.schemas.session import LiveDetectionEvent

router = APIRouter(tags=["live_session"])


# ── In-memory connection registry ─────────────────────────────────────────────
# { session_id: [WebSocket, ...] }
class LiveSessionManager:
    def __init__(self):
        self._connections: Dict[int, List[WebSocket]] = {}

    async def connect(self, session_id: int, ws: WebSocket):
        await ws.accept()
        self._connections.setdefault(session_id, []).append(ws)
        print(f"[WS] Coach connected to session {session_id}. "
              f"Total: {len(self._connections[session_id])}")

    def disconnect(self, session_id: int, ws: WebSocket):
        conns = self._connections.get(session_id, [])
        if ws in conns:
            conns.remove(ws)
        print(f"[WS] Coach disconnected from session {session_id}.")

    async def broadcast(self, session_id: int, event: dict):
        """Send a JSON event to every coach watching this session."""
        dead = []
        for ws in self._connections.get(session_id, []):
            try:
                await ws.send_json(event)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(session_id, ws)

    def session_has_coaches(self, session_id: int) -> bool:
        return bool(self._connections.get(session_id))


# Singleton used by both this router AND classify.py
manager = LiveSessionManager()


# ── WebSocket route ───────────────────────────────────────────────────────────
@router.websocket("/ws/live/{session_id}")
async def live_session_ws(
    websocket:  WebSocket,
    session_id: int,
    token:      str = Query(..., description="JWT Bearer token (no 'Bearer ' prefix)"),
):
    """
    Coach connects here to receive real-time detections for a session.
    Authenticate via ?token=<jwt>
    """
    # ── Validate JWT ──────────────────────────────────────────────────────────
    from jose import jwt as _jwt
    try:
        payload = _jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        role    = payload.get("role", "")
    except JWTError:
        await websocket.close(code=4001, reason="Invalid token")
        return

    if role != "coach":
        await websocket.close(code=4003, reason="Coach role required")
        return

    await manager.connect(session_id, websocket)

    try:
        # Keep alive — listen for pings or close
        while True:
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        manager.disconnect(session_id, websocket)
    except Exception as e:
        print(f"[WS] Session {session_id} error: {e}")
        manager.disconnect(session_id, websocket)
