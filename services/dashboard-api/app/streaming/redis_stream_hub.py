from __future__ import annotations

import asyncio
import base64
import logging
import os
import time
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

POLL_INTERVAL_SECONDS = float(os.getenv("STREAM_POLL_INTERVAL_SEC", "0.015"))
IDLE_STOP_SECONDS = float(os.getenv("STREAM_IDLE_STOP_SEC", "20"))
STALE_FRAME_SECONDS = float(os.getenv("STREAM_STALE_FRAME_SEC", "3"))


@dataclass
class CameraStreamState:
    camera_id: str
    condition: asyncio.Condition = field(default_factory=asyncio.Condition)
    task: asyncio.Task | None = None
    latest_frame: bytes | None = None
    latest_raw_value: str | bytes | None = None
    latest_sequence: int = 0
    latest_frame_at: float = 0.0
    started_at: float = field(default_factory=time.monotonic)
    last_client_left_at: float = field(default_factory=time.monotonic)
    client_count: int = 0
    frames_received: int = 0
    decode_errors: int = 0
    redis_errors: int = 0
    last_error: str | None = None
    reconnecting: bool = False


class RedisStreamHub:
    """
    One Redis reader per camera, many HTTP MJPEG clients.

    The hub keeps only the newest decoded JPEG frame. Slow clients never build a
    queue; they simply wait for the next sequence number and receive the latest
    frame, which keeps playback close to real time under load.
    """

    def __init__(self):
        self._states: dict[str, CameraStreamState] = {}
        self._lock = asyncio.Lock()

    async def _get_state(self, camera_id: str) -> CameraStreamState:
        async with self._lock:
            state = self._states.get(camera_id)
            if state is None:
                state = CameraStreamState(camera_id=camera_id)
                self._states[camera_id] = state
            return state

    async def _ensure_worker(self, redis_client: Any, state: CameraStreamState) -> None:
        if state.task and not state.task.done():
            return
        state.task = asyncio.create_task(self._watch_camera(redis_client, state), name=f"stream-hub-{state.camera_id}")

    async def _watch_camera(self, redis_client: Any, state: CameraStreamState) -> None:
        key = f"video_feed:{state.camera_id}"
        logger.info("Stream hub started for camera=%s", state.camera_id)

        while True:
            try:
                if state.client_count <= 0 and time.monotonic() - state.last_client_left_at > IDLE_STOP_SECONDS:
                    logger.info("Stream hub idle stop for camera=%s", state.camera_id)
                    return

                frame_value = await redis_client.get(key)
                if frame_value and frame_value != state.latest_raw_value:
                    state.latest_raw_value = frame_value
                    try:
                        if isinstance(frame_value, str):
                            frame_bytes = base64.b64decode(frame_value)
                        else:
                            frame_bytes = base64.b64decode(frame_value)
                    except Exception as exc:
                        state.decode_errors += 1
                        state.last_error = f"decode: {exc}"
                        await asyncio.sleep(POLL_INTERVAL_SECONDS)
                        continue

                    async with state.condition:
                        state.latest_frame = frame_bytes
                        state.latest_sequence += 1
                        state.latest_frame_at = time.monotonic()
                        state.frames_received += 1
                        state.reconnecting = False
                        state.condition.notify_all()

                if state.latest_frame_at and time.monotonic() - state.latest_frame_at > STALE_FRAME_SECONDS:
                    state.reconnecting = True

                await asyncio.sleep(POLL_INTERVAL_SECONDS)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                state.redis_errors += 1
                state.last_error = f"redis: {exc}"
                state.reconnecting = True
                logger.warning("Stream hub read failed camera=%s error=%s", state.camera_id, exc)
                await asyncio.sleep(0.25)

    async def frame_generator(self, redis_client: Any, camera_id: str):
        state = await self._get_state(camera_id)
        state.client_count += 1
        await self._ensure_worker(redis_client, state)

        last_sequence = -1
        boundary_prefix = b"--frame\r\nContent-Type: image/jpeg\r\nCache-Control: no-store\r\n\r\n"

        try:
            if state.latest_frame is not None:
                last_sequence = state.latest_sequence
                yield boundary_prefix + state.latest_frame + b"\r\n"

            while True:
                async with state.condition:
                    await state.condition.wait_for(lambda: state.latest_sequence != last_sequence)
                    last_sequence = state.latest_sequence
                    frame = state.latest_frame

                if frame is not None:
                    yield boundary_prefix + frame + b"\r\n"
        finally:
            state.client_count = max(0, state.client_count - 1)
            if state.client_count == 0:
                state.last_client_left_at = time.monotonic()

    def diagnostics(self) -> list[dict[str, Any]]:
        now = time.monotonic()
        items = []
        for state in self._states.values():
            uptime = max(now - state.started_at, 0.001)
            frame_age_ms = None
            if state.latest_frame_at:
                frame_age_ms = round((now - state.latest_frame_at) * 1000, 1)
            items.append(
                {
                    "camera_id": state.camera_id,
                    "clients": state.client_count,
                    "frames_received": state.frames_received,
                    "fps_in": round(state.frames_received / uptime, 2),
                    "latest_sequence": state.latest_sequence,
                    "frame_age_ms": frame_age_ms,
                    "is_stale": bool(frame_age_ms is not None and frame_age_ms > STALE_FRAME_SECONDS * 1000),
                    "reconnecting": state.reconnecting,
                    "decode_errors": state.decode_errors,
                    "redis_errors": state.redis_errors,
                    "last_error": state.last_error,
                    "worker_running": bool(state.task and not state.task.done()),
                }
            )
        return items

    async def stop_all(self) -> None:
        async with self._lock:
            tasks = [state.task for state in self._states.values() if state.task and not state.task.done()]
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
            self._states.clear()


stream_hub = RedisStreamHub()
