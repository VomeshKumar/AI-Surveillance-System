from __future__ import annotations

import logging
import os
import time

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.consumers.runtime_state import runtime_state
from app.database.postgres import get_db_session, get_pooling_diagnostics
from app.database.redis_cache import redis_manager

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/v1/health",
    tags=["System Health"],
)

START_TIME = time.time()


async def _get_stream_lag(stream_name: str, group_name: str = "api_group") -> int:
    if not redis_manager.redis_client:
        return -1

    try:
        groups = await redis_manager.redis_client.xinfo_groups(stream_name)
        for group in groups:
            if group.get("name") == group_name:
                return int(group.get("pending", 0))
    except Exception:
        return -1

    return 0


@router.get("/", status_code=status.HTTP_200_OK)
async def health_check(db: AsyncSession = Depends(get_db_session)):
    health_status = {
        "status": "healthy",
        "uptime_seconds": round(time.time() - START_TIME, 2),
        "version": "1.0.0",
        "services": {
            "api": "online",
            "postgres": "unknown",
            "redis": "unknown",
        },
        "stream_lag": {},
        "consumer_runtime": runtime_state.snapshot(),
        "database_pooling": get_pooling_diagnostics(),
    }

    try:
        await db.execute(text("SELECT 1"))
        health_status["services"]["postgres"] = "online"
    except Exception as exc:
        logger.error("PostgreSQL health check failed: %s", exc)
        health_status["services"]["postgres"] = "offline"
        health_status["status"] = "unhealthy"

    redis_client = redis_manager.redis_client
    if redis_client is None:
        health_status["services"]["redis"] = "offline"
        health_status["status"] = "degraded"
    else:
        try:
            await redis_client.ping()
            health_status["services"]["redis"] = "online"
        except Exception as exc:
            logger.error("Redis health check failed: %s", exc)
            health_status["services"]["redis"] = "offline"
            health_status["status"] = "degraded"

        mode = os.getenv("STREAM_MODE", "dual").strip().lower()
        shards = max(1, int(os.getenv("STREAM_SHARDS", "6")))
        streams = []
        if mode in {"legacy", "dual"}:
            streams.append("face_events")
        if mode in {"sharded", "dual"}:
            streams.extend([f"face_events_{idx}" for idx in range(shards)])

        for stream_name in streams:
            health_status["stream_lag"][stream_name] = await _get_stream_lag(stream_name)

    if health_status["status"] == "unhealthy":
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=health_status,
        )

    return health_status

