"""Event Publisher - Sends events to backend API"""
import httpx
import asyncio
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

class EventPublisher:
    """Publishes CV events to backend API"""
    
    def __init__(self, backend_url: str = "http://localhost:8000"):
        self.backend_url = backend_url
        self.client = httpx.AsyncClient(timeout=10.0)
    
    async def publish(self, event: Dict[str, Any]):
        """Publish event to backend"""
        event_type = event.get("type", "UNKNOWN")
        data = event.get("data", {})
        
        try:
            if event_type == "ENTRY":
                await self._publish_entry(data)
            elif event_type == "EXIT":
                await self._publish_exit(data)
            elif event_type == "TOUCH":
                await self._publish_touch(data)
            elif event_type == "SANITIZE":
                await self._publish_sanitize(data)
            else:
                logger.warning(f"Unknown event type: {event_type}")
        except Exception as e:
            logger.error(f"Failed to publish {event_type} event: {e}")
    
    async def _publish_entry(self, data: Dict):
        response = await self.client.post(
            f"{self.backend_url}/api/v1/compliance/entry",
            json=data
        )
        response.raise_for_status()
        logger.info(f"Published entry event: {data.get('person_track_id')}")
    
    async def _publish_exit(self, data: Dict):
        response = await self.client.post(
            f"{self.backend_url}/api/v1/compliance/exit",
            params={
                "case_id": data.get("case_id"),
                "person_track_id": data.get("person_track_id"),
                "timestamp": data.get("timestamp")
            }
        )
        response.raise_for_status()
        logger.info(f"Published exit event: {data.get('person_track_id')}")
    
    async def _publish_touch(self, data: Dict):
        response = await self.client.post(
            f"{self.backend_url}/api/v1/compliance/touch",
            json=data
        )
        response.raise_for_status()
        logger.info(f"Published touch event: zone={data.get('zone')}")
    
    async def _publish_sanitize(self, data: Dict):
        response = await self.client.post(
            f"{self.backend_url}/api/v1/compliance/sanitize",
            params={
                "case_id": data.get("case_id"),
                "person_track_id": data.get("person_track_id"),
                "timestamp": data.get("timestamp")
            }
        )
        response.raise_for_status()
        logger.info(f"Published sanitize event")
    
    async def close(self):
        await self.client.aclose()
