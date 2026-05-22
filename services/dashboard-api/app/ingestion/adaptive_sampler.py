from __future__ import annotations

import os
import time
from typing import Optional


def _safe_cpu_percent() -> float:
    try:
        import psutil  # type: ignore

        return float(psutil.cpu_percent(interval=0.1))
    except Exception:
        # Portable fallback: use system load when available.
        try:
            load_avg = os.getloadavg()[0]
            cpu_cores = max(1, os.cpu_count() or 1)
            return min(100.0, (load_avg / cpu_cores) * 100.0)
        except Exception:
            return 0.0


def compute_next_skip(
    current_skip: int,
    cpu_percent: float,
    stream_lag: int,
    min_skip: int = 2,
    max_skip: int = 10,
) -> int:
    skip = max(min_skip, min(max_skip, current_skip))

    if cpu_percent > 90.0 or stream_lag > 3000:
        return max(skip, 8)

    if cpu_percent > 75.0 or stream_lag > 1000:
        return min(max_skip, skip + 1)

    if cpu_percent < 60.0 and stream_lag < 500:
        return max(min_skip, skip - 1)

    return skip


class AdaptiveFrameSampler:
    """
    Stores per-camera frame sampling policy in Redis so ingestion and inference
    workers share one source of truth.
    """

    def __init__(
        self,
        redis_client=None,
        key_prefix: str = "ai:camera_policy",
        min_skip: int = 2,
        max_skip: int = 10,
        default_skip: int = 3,
    ):
        self.redis = redis_client
        self.key_prefix = key_prefix
        self.min_skip = min_skip
        self.max_skip = max_skip
        self.default_skip = max(min_skip, min(max_skip, default_skip))

    def _camera_key(self, camera_id: str) -> str:
        return f"{self.key_prefix}:{camera_id}"

    async def get_skip(self, camera_id: str) -> int:
        if not self.redis:
            return self.default_skip

        raw = await self.redis.hget(self._camera_key(camera_id), "skip_n")
        if raw is None:
            return self.default_skip

        try:
            return max(self.min_skip, min(self.max_skip, int(raw)))
        except Exception:
            return self.default_skip

    async def set_skip(self, camera_id: str, skip_n: int) -> int:
        value = max(self.min_skip, min(self.max_skip, skip_n))

        if self.redis:
            key = self._camera_key(camera_id)
            await self.redis.hset(
                key,
                mapping={
                    "skip_n": value,
                    "updated_at": f"{time.time():.3f}",
                },
            )
            await self.redis.expire(key, 3600)

        return value

    async def update_from_metrics(
        self,
        camera_id: str,
        stream_lag: int,
        cpu_percent: Optional[float] = None,
    ) -> int:
        cpu = _safe_cpu_percent() if cpu_percent is None else cpu_percent
        current = await self.get_skip(camera_id)
        nxt = compute_next_skip(
            current_skip=current,
            cpu_percent=cpu,
            stream_lag=stream_lag,
            min_skip=self.min_skip,
            max_skip=self.max_skip,
        )
        return await self.set_skip(camera_id, nxt)

    async def force_emergency(self, camera_id: str) -> int:
        return await self.set_skip(camera_id, max(8, self.default_skip))

