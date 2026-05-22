from __future__ import annotations

import asyncio
import logging
import os

from app.ingestion.adaptive_sampler import AdaptiveFrameSampler

logger = logging.getLogger(__name__)


class FramePolicyController:
    def __init__(
        self,
        redis_client,
        interval_seconds: float = 5.0,
    ):
        self.redis = redis_client
        self.interval_seconds = interval_seconds
        self.sampler = AdaptiveFrameSampler(redis_client=redis_client)
        self._stop = asyncio.Event()
        self.stream_mode = os.getenv("STREAM_MODE", "dual").strip().lower()
        self.stream_shards = max(1, int(os.getenv("STREAM_SHARDS", "6")))

    async def _aggregate_stream_lag(self) -> int:
        streams = []
        if self.stream_mode in {"legacy", "dual"}:
            streams.append("face_events")
        if self.stream_mode in {"sharded", "dual"}:
            streams.extend([f"face_events_{idx}" for idx in range(self.stream_shards)])

        max_lag = 0
        for stream in streams:
            try:
                groups = await self.redis.xinfo_groups(stream)
                for group in groups:
                    if group.get("name") == "api_group":
                        max_lag = max(max_lag, int(group.get("pending", 0)))
                        break
            except Exception:
                continue
        return max_lag

    async def run_once(self) -> None:
        if self.redis is None:
            return

        try:
            camera_ids = await self.redis.smembers("ai:cameras")
        except Exception:
            return

        if not camera_ids:
            return

        lag = await self._aggregate_stream_lag()
        for camera_id in camera_ids:
            try:
                await self.sampler.update_from_metrics(camera_id=str(camera_id), stream_lag=lag)
            except Exception as exc:
                logger.warning("Policy update failed for camera %s: %s", camera_id, exc)

    async def run_forever(self) -> None:
        while not self._stop.is_set():
            await self.run_once()
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=self.interval_seconds)
            except asyncio.TimeoutError:
                continue

    def stop(self) -> None:
        self._stop.set()

