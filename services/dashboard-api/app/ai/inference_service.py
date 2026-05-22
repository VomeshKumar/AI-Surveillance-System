from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass
from typing import Any

from app.ai.gpu_guard import GPUMemoryGuard

logger = logging.getLogger(__name__)


@dataclass
class FrameJob:
    payload: dict[str, Any]
    future: asyncio.Future


class InferenceService:
    """
    Dedicated inference process skeleton:
    - timeout-driven micro-batching (2-4 recommended, default 4)
    - GPU memory guard with automatic CPU fallback
    """

    def __init__(
        self,
        model,
        batch_size: int = 4,
        batch_timeout_ms: int = 50,
        queue_maxsize: int = 200,
        gpu_guard: GPUMemoryGuard | None = None,
    ):
        self.model = model
        self.batch_size = max(2, min(4, batch_size))
        self.batch_timeout_ms = max(40, min(60, batch_timeout_ms))
        self.queue: asyncio.Queue[FrameJob] = asyncio.Queue(maxsize=queue_maxsize)
        self.gpu_guard = gpu_guard or GPUMemoryGuard()
        self._running = False

    async def submit(self, payload: dict[str, Any]) -> dict[str, Any]:
        loop = asyncio.get_running_loop()
        fut = loop.create_future()
        await self.queue.put(FrameJob(payload=payload, future=fut))
        return await fut

    async def _collect_batch(self) -> list[FrameJob]:
        timeout_s = self.batch_timeout_ms / 1000.0
        deadline = time.monotonic() + timeout_s
        batch: list[FrameJob] = []

        while len(batch) < self.batch_size:
            remaining = max(0.0, deadline - time.monotonic())
            try:
                job = await asyncio.wait_for(self.queue.get(), timeout=remaining)
                batch.append(job)
            except asyncio.TimeoutError:
                break

        return batch

    def _infer(self, batch_payloads: list[dict[str, Any]], device: str) -> list[dict[str, Any]]:
        # Model contract is intentionally simple for compatibility and testability.
        return self.model.infer(batch_payloads, device=device)

    async def run(self):
        self._running = True
        logger.info("Inference service started")

        while self._running:
            batch = await self._collect_batch()
            if not batch:
                continue

            payloads = [job.payload for job in batch]
            device = self.gpu_guard.select_device()

            try:
                results = await asyncio.to_thread(self._infer, payloads, device)
                for job, result in zip(batch, results):
                    if not job.future.done():
                        job.future.set_result(result)
            except Exception as exc:
                logger.error("Inference batch failed: %s", exc)
                for job in batch:
                    if not job.future.done():
                        job.future.set_exception(exc)

    def stop(self):
        self._running = False

