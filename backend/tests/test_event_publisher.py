"""Tests for CV module event publisher with SQLite buffering and retry"""

import pytest
import asyncio
import sqlite3
import os
import tempfile
import json
from unittest.mock import AsyncMock, patch, MagicMock

# We need to set up the path so we can import cv_module code
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "cv_module"))

from src.events.event_publisher import EventPublisher, MAX_RETRIES, BACKOFF_DELAYS


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def tmp_db_path(tmp_path):
    """Provide a temporary SQLite DB path for each test."""
    return str(tmp_path / "test_buffer.db")


@pytest.fixture
def publisher(tmp_db_path):
    """Create an EventPublisher with a temp buffer DB."""
    pub = EventPublisher(backend_url="http://test-backend:8000", db_path=tmp_db_path)
    return pub


# ---------------------------------------------------------------------------
# Initialization
# ---------------------------------------------------------------------------

class TestEventPublisherInit:
    def test_creates_buffer_db(self, tmp_db_path):
        publisher = EventPublisher(db_path=tmp_db_path)
        assert os.path.exists(tmp_db_path)

        conn = sqlite3.connect(tmp_db_path)
        cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='buffered_events'")
        assert cursor.fetchone() is not None
        conn.close()

    def test_buffer_count_starts_at_zero(self, publisher):
        assert publisher.get_buffer_count() == 0


# ---------------------------------------------------------------------------
# Buffering
# ---------------------------------------------------------------------------

class TestBuffering:
    def test_buffer_event_inserts_row(self, publisher):
        publisher._buffer_event({"type": "ENTRY", "data": {"case_id": "c1"}})
        assert publisher.get_buffer_count() == 1

    def test_buffer_multiple_events(self, publisher):
        for i in range(5):
            publisher._buffer_event({"type": "ENTRY", "data": {"case_id": f"c{i}"}})
        assert publisher.get_buffer_count() == 5

    def test_buffer_stores_correct_data(self, publisher, tmp_db_path):
        publisher._buffer_event({"type": "TOUCH", "data": {"zone": "CRITICAL", "case_id": "c1"}})

        conn = sqlite3.connect(tmp_db_path)
        row = conn.execute("SELECT event_type, event_data, retry_count FROM buffered_events").fetchone()
        conn.close()

        assert row[0] == "TOUCH"
        data = json.loads(row[1])
        assert data["zone"] == "CRITICAL"
        assert row[2] == 0  # initial retry count


# ---------------------------------------------------------------------------
# Publish with retry
# ---------------------------------------------------------------------------

class TestPublishWithRetry:
    @pytest.mark.asyncio
    async def test_success_on_first_try(self, publisher):
        fn = AsyncMock()
        result = await publisher._publish_with_retry("ENTRY", {}, fn)
        assert result is True
        fn.assert_called_once()

    @pytest.mark.asyncio
    async def test_success_on_second_try(self, publisher):
        fn = AsyncMock(side_effect=[Exception("fail"), None])
        with patch("src.events.event_publisher.asyncio.sleep", new_callable=AsyncMock):
            result = await publisher._publish_with_retry("ENTRY", {}, fn)
        assert result is True
        assert fn.call_count == 2

    @pytest.mark.asyncio
    async def test_all_retries_exhausted(self, publisher):
        fn = AsyncMock(side_effect=Exception("always fail"))
        with patch("src.events.event_publisher.asyncio.sleep", new_callable=AsyncMock):
            result = await publisher._publish_with_retry("ENTRY", {}, fn)
        assert result is False
        assert fn.call_count == MAX_RETRIES + 1

    @pytest.mark.asyncio
    async def test_backoff_delays_used(self, publisher):
        fn = AsyncMock(side_effect=[Exception("e1"), Exception("e2"), Exception("e3"), None])
        sleep_mock = AsyncMock()
        with patch("src.events.event_publisher.asyncio.sleep", sleep_mock):
            await publisher._publish_with_retry("ENTRY", {}, fn)

        # Check that delays match BACKOFF_DELAYS
        sleep_calls = [c[0][0] for c in sleep_mock.call_args_list]
        assert sleep_calls == BACKOFF_DELAYS[:3]


# ---------------------------------------------------------------------------
# publish() end-to-end
# ---------------------------------------------------------------------------

class TestPublish:
    @pytest.mark.asyncio
    async def test_publish_entry_success(self, publisher):
        publisher._publish_entry = AsyncMock()
        await publisher.publish({"type": "ENTRY", "data": {"case_id": "c1"}})
        publisher._publish_entry.assert_called_once()
        assert publisher.get_buffer_count() == 0

    @pytest.mark.asyncio
    async def test_publish_buffers_on_failure(self, publisher):
        publisher._publish_entry = AsyncMock(side_effect=Exception("network down"))
        with patch("src.events.event_publisher.asyncio.sleep", new_callable=AsyncMock):
            await publisher.publish({"type": "ENTRY", "data": {"case_id": "c1"}})
        assert publisher.get_buffer_count() == 1

    @pytest.mark.asyncio
    async def test_publish_unknown_type_ignored(self, publisher):
        await publisher.publish({"type": "UNKNOWN_TYPE", "data": {}})
        assert publisher.get_buffer_count() == 0

    @pytest.mark.asyncio
    async def test_publish_exit_calls_correct_fn(self, publisher):
        publisher._publish_exit = AsyncMock()
        await publisher.publish({"type": "EXIT", "data": {"case_id": "c1"}})
        publisher._publish_exit.assert_called_once()

    @pytest.mark.asyncio
    async def test_publish_touch_calls_correct_fn(self, publisher):
        publisher._publish_touch = AsyncMock()
        await publisher.publish({"type": "TOUCH", "data": {"zone": "CRITICAL"}})
        publisher._publish_touch.assert_called_once()

    @pytest.mark.asyncio
    async def test_publish_sanitize_calls_correct_fn(self, publisher):
        publisher._publish_sanitize = AsyncMock()
        await publisher.publish({"type": "SANITIZE", "data": {"case_id": "c1"}})
        publisher._publish_sanitize.assert_called_once()


# ---------------------------------------------------------------------------
# flush_buffer
# ---------------------------------------------------------------------------

class TestFlushBuffer:
    @pytest.mark.asyncio
    async def test_flush_empty_buffer(self, publisher):
        await publisher.flush_buffer()  # Should not raise
        assert publisher.get_buffer_count() == 0

    @pytest.mark.asyncio
    async def test_flush_succeeds_removes_events(self, publisher):
        publisher._buffer_event({"type": "ENTRY", "data": {"case_id": "c1"}})
        publisher._buffer_event({"type": "EXIT", "data": {"case_id": "c2"}})
        assert publisher.get_buffer_count() == 2

        publisher._publish_entry = AsyncMock()
        publisher._publish_exit = AsyncMock()

        await publisher.flush_buffer()
        assert publisher.get_buffer_count() == 0

    @pytest.mark.asyncio
    async def test_flush_keeps_failed_events(self, publisher):
        publisher._buffer_event({"type": "ENTRY", "data": {"case_id": "c1"}})
        publisher._publish_entry = AsyncMock(side_effect=Exception("still down"))

        await publisher.flush_buffer()
        # Event should still be in buffer with incremented retry count
        assert publisher.get_buffer_count() == 1

    @pytest.mark.asyncio
    async def test_flush_discards_after_max_retries(self, publisher, tmp_db_path):
        # Manually insert event with retry_count at MAX_RETRIES - 1
        conn = sqlite3.connect(tmp_db_path)
        import time
        conn.execute(
            "INSERT INTO buffered_events (event_type, event_data, retry_count, created_at) VALUES (?, ?, ?, ?)",
            ("ENTRY", '{"case_id":"c1"}', MAX_RETRIES - 1, time.time()),
        )
        conn.commit()
        conn.close()

        publisher._publish_entry = AsyncMock(side_effect=Exception("still failing"))
        await publisher.flush_buffer()
        # Should be removed because retry_count now == MAX_RETRIES
        assert publisher.get_buffer_count() == 0

    @pytest.mark.asyncio
    async def test_flush_unknown_type_discarded(self, publisher, tmp_db_path):
        conn = sqlite3.connect(tmp_db_path)
        import time
        conn.execute(
            "INSERT INTO buffered_events (event_type, event_data, retry_count, created_at) VALUES (?, ?, ?, ?)",
            ("UNKNOWN_TYPE", '{}', 0, time.time()),
        )
        conn.commit()
        conn.close()

        await publisher.flush_buffer()
        assert publisher.get_buffer_count() == 0


# ---------------------------------------------------------------------------
# close
# ---------------------------------------------------------------------------

class TestEventPublisherClose:
    @pytest.mark.asyncio
    async def test_close_flushes_and_closes_client(self, publisher):
        publisher._buffer_event({"type": "ENTRY", "data": {"case_id": "c1"}})
        publisher._publish_entry = AsyncMock()

        await publisher.close()

        # Buffer should have been flushed
        assert publisher.get_buffer_count() == 0

    @pytest.mark.asyncio
    async def test_close_handles_flush_error(self, publisher):
        publisher.flush_buffer = AsyncMock(side_effect=Exception("flush error"))
        publisher.get_buffer_count = MagicMock(return_value=0)
        # Should not raise
        await publisher.close()
