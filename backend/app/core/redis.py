"""
Redis connection and pub/sub management
Uses fakeredis when Redis is not available
"""

import json
import logging
from typing import Optional, Any

from app.config import settings

logger = logging.getLogger(__name__)

# Global Redis client
redis_client = None
using_fakeredis = False


async def init_redis():
    """Initialize Redis connection (or fakeredis fallback)"""
    global redis_client, using_fakeredis

    if settings.USE_FAKEREDIS or not settings.REDIS_URL:
        # Use fakeredis for development without Redis
        try:
            import fakeredis.aioredis
            redis_client = fakeredis.aioredis.FakeRedis(decode_responses=True)
            using_fakeredis = True
            logger.info("Using fakeredis (in-memory mock)")
            return
        except ImportError:
            logger.warning("fakeredis not installed, trying real Redis...")

    # Try real Redis
    try:
        import redis.asyncio as redis
        redis_client = redis.from_url(
            settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=True
        )
        # Test connection
        await redis_client.ping()
        logger.info("Redis connection established")
    except Exception as e:
        # Fall back to fakeredis
        logger.warning(f"Redis connection failed ({e}), using fakeredis fallback")
        try:
            import fakeredis.aioredis
            redis_client = fakeredis.aioredis.FakeRedis(decode_responses=True)
            using_fakeredis = True
            logger.info("Fallback to fakeredis successful")
        except ImportError:
            logger.error("Neither Redis nor fakeredis available!")
            raise


async def close_redis():
    """Close Redis connection"""
    global redis_client
    if redis_client:
        await redis_client.close()
        logger.info("Redis connection closed")


async def get_redis():
    """Get Redis client"""
    global redis_client
    if redis_client is None:
        await init_redis()
    return redis_client


class RedisPubSub:
    """Redis Pub/Sub helper for real-time events"""

    # Channel names
    CHANNEL_CASE_EVENTS = "infectioniq:case:{case_id}"
    CHANNEL_OR_EVENTS = "infectioniq:or:{or_number}"
    CHANNEL_ALERTS = "infectioniq:alerts"
    CHANNEL_DASHBOARD = "infectioniq:dashboard"
    CHANNEL_DISPENSERS = "infectioniq:dispensers"

    @staticmethod
    async def publish_event(channel: str, event_type: str, data: dict):
        """Publish event to a channel"""
        try:
            client = await get_redis()
            message = json.dumps({
                "type": event_type,
                "data": data
            })
            await client.publish(channel, message)
            logger.debug(f"Published {event_type} to {channel}")
        except Exception as e:
            # Don't fail if pub/sub doesn't work (fakeredis limitation)
            logger.debug(f"Pub/sub not available: {e}")

    @staticmethod
    async def publish_case_event(case_id: str, event_type: str, data: dict):
        """Publish event for a specific case"""
        channel = RedisPubSub.CHANNEL_CASE_EVENTS.format(case_id=case_id)
        await RedisPubSub.publish_event(channel, event_type, data)

    @staticmethod
    async def publish_or_event(or_number: str, event_type: str, data: dict):
        """Publish event for a specific OR"""
        channel = RedisPubSub.CHANNEL_OR_EVENTS.format(or_number=or_number)
        await RedisPubSub.publish_event(channel, event_type, data)

    @staticmethod
    async def publish_alert(data: dict):
        """Publish alert to alerts channel"""
        await RedisPubSub.publish_event(RedisPubSub.CHANNEL_ALERTS, "ALERT", data)

    @staticmethod
    async def publish_dashboard_update(data: dict):
        """Publish dashboard metrics update"""
        await RedisPubSub.publish_event(RedisPubSub.CHANNEL_DASHBOARD, "METRICS_UPDATE", data)


class RedisCache:
    """Redis caching helper"""

    @staticmethod
    async def get(key: str) -> Optional[Any]:
        """Get value from cache"""
        try:
            client = await get_redis()
            value = await client.get(key)
            if value:
                return json.loads(value)
        except Exception as e:
            logger.debug(f"Cache get failed: {e}")
        return None

    @staticmethod
    async def set(key: str, value: Any, expire_seconds: int = 300):
        """Set value in cache with expiration"""
        try:
            client = await get_redis()
            await client.setex(key, expire_seconds, json.dumps(value))
        except Exception as e:
            logger.debug(f"Cache set failed: {e}")

    @staticmethod
    async def delete(key: str):
        """Delete key from cache"""
        try:
            client = await get_redis()
            await client.delete(key)
        except Exception as e:
            logger.debug(f"Cache delete failed: {e}")

    @staticmethod
    async def get_person_state(case_id: str, person_id: int) -> Optional[dict]:
        """Get person's current state"""
        key = f"person_state:{case_id}:{person_id}"
        return await RedisCache.get(key)

    @staticmethod
    async def set_person_state(case_id: str, person_id: int, state: dict):
        """Set person's current state"""
        key = f"person_state:{case_id}:{person_id}"
        await RedisCache.set(key, state, expire_seconds=3600)  # 1 hour

    @staticmethod
    async def get_active_case(or_number: str) -> Optional[dict]:
        """Get active case for an OR"""
        key = f"active_case:{or_number}"
        return await RedisCache.get(key)

    @staticmethod
    async def set_active_case(or_number: str, case_data: dict):
        """Set active case for an OR"""
        key = f"active_case:{or_number}"
        await RedisCache.set(key, case_data, expire_seconds=86400)  # 24 hours
