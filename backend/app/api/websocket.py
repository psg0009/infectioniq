"""
WebSocket Handler for Real-time Events
"""

from typing import Dict, Set
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
import asyncio
import json
import logging

from app.core.redis import get_redis, RedisPubSub

logger = logging.getLogger(__name__)

websocket_router = APIRouter()


class ConnectionManager:
    """Manages WebSocket connections"""

    def __init__(self):
        self.connections: Dict[str, Set[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, channel: str):
        """Accept connection and add to channel"""
        await websocket.accept()
        if channel not in self.connections:
            self.connections[channel] = set()
        self.connections[channel].add(websocket)
        logger.info(f"WebSocket connected to channel: {channel}")

    def disconnect(self, websocket: WebSocket, channel: str):
        """Remove connection from channel"""
        if channel in self.connections:
            self.connections[channel].discard(websocket)
            if not self.connections[channel]:
                del self.connections[channel]
        logger.info(f"WebSocket disconnected from channel: {channel}")

    async def broadcast(self, channel: str, message: dict):
        """Broadcast message to all connections in channel"""
        if channel in self.connections:
            disconnected = set()
            for websocket in self.connections[channel]:
                try:
                    await websocket.send_json(message)
                except Exception:
                    disconnected.add(websocket)

            for ws in disconnected:
                self.connections[channel].discard(ws)


manager = ConnectionManager()


async def redis_listener(channel: str):
    """Listen to Redis pub/sub and broadcast to WebSocket clients"""
    redis = await get_redis()
    pubsub = redis.pubsub()
    await pubsub.subscribe(channel)

    try:
        async for message in pubsub.listen():
            if message["type"] == "message":
                data = json.loads(message["data"])
                await manager.broadcast(channel, data)
    except asyncio.CancelledError:
        pass
    finally:
        await pubsub.unsubscribe(channel)


async def _handle_websocket(websocket: WebSocket, channel: str):
    """Generic WebSocket handler with JWT authentication (Supabase + legacy)."""
    from app.core.security import decode_token
    from app.core.auth_deps import _decode_supabase_jwt

    # Extract token from query params
    token = websocket.query_params.get("token")
    if not token:
        await websocket.close(code=1008, reason="Missing authentication token")
        return

    # Try Supabase JWT first, then legacy
    payload = _decode_supabase_jwt(token)
    if not payload:
        payload = decode_token(token)
        if not payload or payload.get("type") != "access":
            await websocket.close(code=1008, reason="Invalid or expired token")
            return

    user_id = payload.get("sub", "unknown")
    logger.info(f"WebSocket authenticated: user={user_id}, channel={channel}")

    await manager.connect(websocket, channel)
    listener_task = asyncio.create_task(redis_listener(channel))

    try:
        while True:
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        pass
    finally:
        manager.disconnect(websocket, channel)
        listener_task.cancel()
        logger.info(f"WebSocket disconnected: user={user_id}, channel={channel}")


@websocket_router.websocket("/case/{case_id}/live")
async def websocket_case_events(websocket: WebSocket, case_id: str):
    """WebSocket endpoint for case-specific events"""
    channel = RedisPubSub.CHANNEL_CASE_EVENTS.format(case_id=case_id)
    await _handle_websocket(websocket, channel)


@websocket_router.websocket("/or/{or_number}/live")
async def websocket_or_events(websocket: WebSocket, or_number: str):
    """WebSocket endpoint for OR-specific events"""
    channel = RedisPubSub.CHANNEL_OR_EVENTS.format(or_number=or_number)
    await _handle_websocket(websocket, channel)


@websocket_router.websocket("/alerts")
async def websocket_alerts(websocket: WebSocket):
    """WebSocket endpoint for all alerts"""
    await _handle_websocket(websocket, RedisPubSub.CHANNEL_ALERTS)


@websocket_router.websocket("/dashboard")
async def websocket_dashboard(websocket: WebSocket):
    """WebSocket endpoint for dashboard metrics"""
    await _handle_websocket(websocket, RedisPubSub.CHANNEL_DASHBOARD)


@websocket_router.websocket("/camera/stream")
async def websocket_camera_stream(websocket: WebSocket):
    """WebSocket endpoint for live camera frame streaming.

    The browser captures frames as JPEG base64 and sends them here.
    Each frame is decoded and processed through the CV pipeline
    (person detection, hand tracking, gesture classification, zone detection).
    Detection results are returned in real-time.
    """
    from app.core.security import decode_token as legacy_decode
    from app.core.auth_deps import _decode_supabase_jwt
    import base64 as _b64

    token = websocket.query_params.get("token")
    if not token:
        await websocket.close(code=1008, reason="Missing authentication token")
        return

    # Try Supabase JWT first, then legacy
    payload = _decode_supabase_jwt(token)
    if not payload:
        payload = legacy_decode(token)
        if not payload or payload.get("type") != "access":
            await websocket.close(code=1008, reason="Invalid or expired token")
            return

    await websocket.accept()
    logger.info("Camera stream WebSocket connected")

    # Initialize CV frame processor
    processor = None
    try:
        from app.services.cv_frame_processor import FrameProcessor

        # Auto-pick an active case for event publishing
        case_id = websocket.query_params.get("case_id")
        if not case_id:
            try:
                import sqlite3
                from pathlib import Path
                db_path = Path(__file__).resolve().parents[2] / "infectioniq.db"
                conn = sqlite3.connect(str(db_path))
                row = conn.execute(
                    "SELECT id FROM surgical_cases WHERE status='IN_PROGRESS' ORDER BY start_time DESC LIMIT 1"
                ).fetchone()
                conn.close()
                if row:
                    case_id = row[0]
            except Exception:
                pass

        processor = FrameProcessor(case_id=case_id)
        logger.info(f"Frame processor created (case_id={case_id})")
    except Exception as e:
        logger.warning(f"Could not create frame processor: {e}")

    frame_count = 0
    try:
        while True:
            data = await websocket.receive_json()
            msg_type = data.get("type", "")

            if msg_type == "frame":
                frame_count += 1
                frame_b64 = data.get("data", "")

                if processor and frame_b64:
                    try:
                        jpeg_bytes = _b64.b64decode(frame_b64)
                        result = await processor.process_frame_async(jpeg_bytes)
                        result["frame"] = frame_count
                        await websocket.send_json(result)
                    except Exception as e:
                        await websocket.send_json({
                            "type": "error",
                            "frame": frame_count,
                            "message": str(e),
                        })
                else:
                    # Fallback: ack without CV processing
                    await websocket.send_json({
                        "type": "ack",
                        "frame": frame_count,
                        "status": "received (no CV pipeline)",
                    })

            elif msg_type == "ping":
                await websocket.send_json({"type": "pong"})

            elif msg_type == "config":
                # Allow client to set case_id mid-stream
                new_case_id = data.get("case_id")
                if new_case_id and processor:
                    processor.case_id = new_case_id
                    await websocket.send_json({
                        "type": "config_ack",
                        "case_id": new_case_id,
                    })

    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.error(f"Camera stream error: {e}")
    finally:
        logger.info(f"Camera stream disconnected after {frame_count} frames")
