import os
import json
import asyncio
import logging
from typing import Optional, Any

import redis.asyncio as redis

logger = logging.getLogger(__name__)

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

# Config
IDENTITY_CACHE_TTL = 3600
DEFAULT_TIMEOUT = 5


class RedisCacheManager:
    """
    Production-ready async Redis manager for:
    - Identity caching
    - Alert cooldown (anti-spam)
    - Generic cache
    """

    def __init__(self):
        self.redis_client: Optional[redis.Redis] = None

    # ---------------------------------------------------
    # CONNECTION MANAGEMENT
    # ---------------------------------------------------
    async def connect(self):
        """Initialize Redis connection with retry logic."""
        for attempt in range(5):
            try:
                self.redis_client = redis.from_url(
                    REDIS_URL,
                    decode_responses=True,
                    socket_connect_timeout=DEFAULT_TIMEOUT,
                )
                await self.redis_client.ping()
                logger.info(f"✅ Connected to Redis at {REDIS_URL}")
                return
            except Exception as e:
                logger.warning(f"Redis connection failed (attempt {attempt+1}): {e}")
                await asyncio.sleep(2)

        logger.error("❌ Could not connect to Redis after retries")
        self.redis_client = None

    async def disconnect(self):
        """Close Redis connection safely."""
        if self.redis_client:
            await self.redis_client.close()
            logger.info("Redis connection closed.")

    # ---------------------------------------------------
    # GENERIC CACHE METHODS
    # ---------------------------------------------------
    async def set_cache(self, key: str, value: Any, expire_seconds: int = 3600):
        if not self.redis_client:
            return
        try:
            payload = json.dumps(value) if isinstance(value, (dict, list)) else value
            await self.redis_client.set(key, payload, ex=expire_seconds)
        except Exception as e:
            logger.error(f"Redis SET error [{key}]: {e}")

    async def get_cache(self, key: str) -> Optional[Any]:
        if not self.redis_client:
            return None
        try:
            data = await self.redis_client.get(key)
            if not data:
                return None
            try:
                return json.loads(data)
            except json.JSONDecodeError:
                return data
        except Exception as e:
            logger.error(f"Redis GET error [{key}]: {e}")
            return None

    async def delete_key(self, key: str):
        if not self.redis_client:
            return
        try:
            await self.redis_client.delete(key)
        except Exception as e:
            logger.error(f"Redis DELETE error [{key}]: {e}")

    async def get_stream_pending(self, stream_name: str, group_name: str = "api_group") -> int:
        if not self.redis_client:
            return -1
        try:
            groups = await self.redis_client.xinfo_groups(stream_name)
            for group in groups:
                if group.get("name") == group_name:
                    return int(group.get("pending", 0))
        except Exception as e:
            logger.error(f"Redis stream pending error [{stream_name}]: {e}")
            return -1
        return 0

    # ---------------------------------------------------
    # IDENTITY CACHE (PersonModel)
    # ---------------------------------------------------
    async def get_identity(self, face_id: int):
        key = f"ai:identity:{face_id}"
        return await self.get_cache(key)

    async def set_identity(self, face_id: int, identity):
        """
        Stores minimal identity data (NOT full SQLAlchemy object)
        """
        key = f"ai:identity:{face_id}"

        try:
            data = {
                "id": identity.id,
                "name": identity.name,
                "category": identity.category,       # watch_status equivalent
                "threat_level": identity.threat_level,
                "crime_type": identity.crime_type,
                "is_active": identity.is_active,
            }
            await self.set_cache(key, data, IDENTITY_CACHE_TTL)
        except Exception as e:
            logger.error(f"Identity cache error for {face_id}: {e}")

    async def invalidate_identity(self, face_id: int):
        key = f"ai:identity:{face_id}"
        await self.delete_key(key)

    # ---------------------------------------------------
    # ALERT COOLDOWN (ANTI-SPAM)
    # ---------------------------------------------------
    async def is_alert_on_cooldown(
        self,
        face_id: int,
        camera_id: str,
        cooldown_seconds: int = 60,
    ) -> bool:
        """
        Atomic cooldown using Redis SET NX
        Returns:
            True  → on cooldown (block alert)
            False → safe to send alert
        """
        if not self.redis_client:
            logger.warning("Redis offline → skipping cooldown")
            return False

        key = f"ai:alert_lock:{camera_id}:{face_id}"

        try:
            is_new = await self.redis_client.set(
                key,
                "1",
                ex=cooldown_seconds,
                nx=True,
            )
            return not bool(is_new)
        except Exception as e:
            logger.error(f"Cooldown error [{key}]: {e}")
            return False

    async def set_alert_cooldown(
        self,
        face_id: int,
        camera_id: str,
        ttl: int = 60,
    ):
        """
        Optional explicit cooldown setter (if needed separately)
        """
        if not self.redis_client:
            return

        key = f"ai:alert_lock:{camera_id}:{face_id}"

        try:
            await self.redis_client.set(key, "1", ex=ttl)
        except Exception as e:
            logger.error(f"Set cooldown error [{key}]: {e}")


# Singleton instance
redis_manager = RedisCacheManager()

async def get_redis() -> Optional[redis.Redis]:
    return redis_manager.redis_client
