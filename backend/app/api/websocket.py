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
        # Channel -> Set of WebSocket connections
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
            
            # Clean up disconnected
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


@websocket_router.websocket("/case/{case_id}/live")
async def websocket_case_events(websocket: WebSocket, case_id: str):
    """WebSocket endpoint for case-specific events"""
    channel = RedisPubSub.CHANNEL_CASE_EVENTS.format(case_id=case_id)
    
    await manager.connect(websocket, channel)
    
    # Start Redis listener task
    listener_task = asyncio.create_task(redis_listener(channel))
    
    try:
        while True:
            # Keep connection alive, handle client messages
            data = await websocket.receive_text()
            # Client can send ping/pong or other messages
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        pass
    finally:
        manager.disconnect(websocket, channel)
        listener_task.cancel()


@websocket_router.websocket("/or/{or_number}/live")
async def websocket_or_events(websocket: WebSocket, or_number: str):
    """WebSocket endpoint for OR-specific events"""
    channel = RedisPubSub.CHANNEL_OR_EVENTS.format(or_number=or_number)
    
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


@websocket_router.websocket("/alerts")
async def websocket_alerts(websocket: WebSocket):
    """WebSocket endpoint for all alerts"""
    channel = RedisPubSub.CHANNEL_ALERTS
    
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


@websocket_router.websocket("/dashboard")
async def websocket_dashboard(websocket: WebSocket):
    """WebSocket endpoint for dashboard metrics"""
    channel = RedisPubSub.CHANNEL_DASHBOARD
    
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
