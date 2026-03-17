"""Event Publisher - Sends events to backend API with SQLite buffering and retry"""
import httpx
import asyncio
import logging
import sqlite3
import json
import time
import os
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

# Retry configuration
MAX_RETRIES = 3
BACKOFF_DELAYS = [2, 4, 8]  # seconds: 2s, 4s, 8s exponential backoff
BUFFER_DB_NAME = "cv_events_buffer.db"


class EventPublisher:
    """Publishes CV events to backend API with local SQLite buffering and retry."""

    def __init__(self, backend_url: str = None, db_path: Optional[str] = None, service_key: str = None):
        self.backend_url = backend_url or os.environ.get("INFECTIONIQ_BACKEND_URL", "http://localhost:8000")
        self._service_key = service_key or os.environ.get("INFECTIONIQ_SERVICE_KEY", "dev-internal-key")
        self.client = httpx.AsyncClient(
            timeout=10.0,
            headers={"X-Service-Key": self._service_key},
        )
        self._db_path = db_path or os.path.join(os.path.dirname(__file__), BUFFER_DB_NAME)
        self._init_buffer_db()
        logger.info(f"EventPublisher initialized (backend={backend_url}, buffer={self._db_path})")

    def _init_buffer_db(self):
        """Initialize the SQLite database used to buffer failed events."""
        conn = sqlite3.connect(self._db_path)
        try:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS buffered_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_type TEXT NOT NULL,
                    event_data TEXT NOT NULL,
                    retry_count INTEGER NOT NULL DEFAULT 0,
                    created_at REAL NOT NULL,
                    last_retry_at REAL
                )
            """)
            conn.commit()
        finally:
            conn.close()

    def _buffer_event(self, event: Dict[str, Any]):
        """Save a failed event to the SQLite buffer for later retry."""
        event_type = event.get("type", "UNKNOWN")
        event_data = json.dumps(event.get("data", {}))
        now = time.time()

        conn = sqlite3.connect(self._db_path)
        try:
            conn.execute(
                "INSERT INTO buffered_events (event_type, event_data, retry_count, created_at) VALUES (?, ?, 0, ?)",
                (event_type, event_data, now)
            )
            conn.commit()
            logger.info(f"Buffered {event_type} event for later retry")
        finally:
            conn.close()

    async def _publish_with_retry(self, event_type: str, data: Dict, publish_fn) -> bool:
        """Attempt to publish an event with exponential backoff retry.

        Args:
            event_type: The event type string (ENTRY, EXIT, TOUCH, SANITIZE).
            data: The event data payload.
            publish_fn: An async callable that performs the actual HTTP request.

        Returns:
            True if publish succeeded, False if all retries exhausted.
        """
        last_exception = None
        for attempt in range(MAX_RETRIES + 1):
            try:
                await publish_fn(data)
                return True
            except Exception as e:
                last_exception = e
                if attempt < MAX_RETRIES:
                    delay = BACKOFF_DELAYS[attempt]
                    logger.warning(
                        f"Publish {event_type} failed (attempt {attempt + 1}/{MAX_RETRIES + 1}): {e}. "
                        f"Retrying in {delay}s..."
                    )
                    await asyncio.sleep(delay)
                else:
                    logger.error(
                        f"Publish {event_type} failed after {MAX_RETRIES + 1} attempts: {last_exception}"
                    )
        return False

    def _get_publish_fn(self, event_type: str):
        """Return the appropriate publish function for the given event type."""
        dispatch = {
            "ENTRY": self._publish_entry,
            "EXIT": self._publish_exit,
            "TOUCH": self._publish_touch,
            "SANITIZE": self._publish_sanitize,
        }
        return dispatch.get(event_type)

    async def publish(self, event: Dict[str, Any]):
        """Publish event to backend with retry and local buffering on failure."""
        event_type = event.get("type", "UNKNOWN")
        data = event.get("data", {})

        publish_fn = self._get_publish_fn(event_type)
        if publish_fn is None:
            logger.warning(f"Unknown event type: {event_type}")
            return

        success = await self._publish_with_retry(event_type, data, publish_fn)
        if not success:
            self._buffer_event(event)

    async def flush_buffer(self):
        """Retry all buffered events. Successfully sent events are removed from the buffer.
        Events that still fail are updated with incremented retry count and removed if
        they have exceeded MAX_RETRIES total retries."""
        conn = sqlite3.connect(self._db_path)
        try:
            rows = conn.execute(
                "SELECT id, event_type, event_data, retry_count FROM buffered_events ORDER BY created_at ASC"
            ).fetchall()
        finally:
            conn.close()

        if not rows:
            return

        logger.info(f"Flushing {len(rows)} buffered events...")
        ids_to_delete = []
        ids_to_update = []

        for row_id, event_type, event_data_json, retry_count in rows:
            data = json.loads(event_data_json)
            publish_fn = self._get_publish_fn(event_type)

            if publish_fn is None:
                # Unknown type in buffer -- discard it
                ids_to_delete.append(row_id)
                continue

            try:
                await publish_fn(data)
                ids_to_delete.append(row_id)
                logger.info(f"Flushed buffered {event_type} event (id={row_id})")
            except Exception as e:
                new_retry_count = retry_count + 1
                if new_retry_count >= MAX_RETRIES:
                    logger.error(
                        f"Buffered {event_type} event (id={row_id}) exceeded max retries, discarding: {e}"
                    )
                    ids_to_delete.append(row_id)
                else:
                    logger.warning(
                        f"Buffered {event_type} event (id={row_id}) retry failed "
                        f"({new_retry_count}/{MAX_RETRIES}): {e}"
                    )
                    ids_to_update.append((new_retry_count, time.time(), row_id))

        # Apply database changes
        conn = sqlite3.connect(self._db_path)
        try:
            if ids_to_delete:
                placeholders = ",".join("?" for _ in ids_to_delete)
                conn.execute(
                    f"DELETE FROM buffered_events WHERE id IN ({placeholders})",
                    ids_to_delete
                )
            if ids_to_update:
                conn.executemany(
                    "UPDATE buffered_events SET retry_count = ?, last_retry_at = ? WHERE id = ?",
                    ids_to_update
                )
            conn.commit()
        finally:
            conn.close()

        flushed = len(ids_to_delete)
        remaining = len(ids_to_update)
        logger.info(f"Buffer flush complete: {flushed} sent, {remaining} still pending")

    def get_buffer_count(self) -> int:
        """Return the number of events currently in the buffer."""
        conn = sqlite3.connect(self._db_path)
        try:
            count = conn.execute("SELECT COUNT(*) FROM buffered_events").fetchone()[0]
            return count
        finally:
            conn.close()

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
        """Flush any remaining buffered events and close the HTTP client."""
        logger.info("EventPublisher closing: flushing buffer...")
        try:
            await self.flush_buffer()
        except Exception as e:
            logger.error(f"Error flushing buffer during close: {e}")

        buffered = self.get_buffer_count()
        if buffered > 0:
            logger.warning(f"{buffered} events remain in local buffer after flush (will retry on next startup)")

        await self.client.aclose()
        logger.info("EventPublisher closed")
