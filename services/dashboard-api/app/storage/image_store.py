from __future__ import annotations

import asyncio
import hashlib
import os
import shutil
from dataclasses import dataclass
from pathlib import Path


def _detect_extension(image_bytes: bytes) -> str:
    if image_bytes.startswith(b"\xff\xd8\xff"):
        return ".jpg"
    if image_bytes.startswith(b"\x89PNG\r\n\x1a\n"):
        return ".png"
    if image_bytes.startswith((b"GIF87a", b"GIF89a")):
        return ".gif"
    if image_bytes.startswith(b"RIFF") and image_bytes[8:12] == b"WEBP":
        return ".webp"
    if image_bytes.startswith(b"BM"):
        return ".bmp"
    return ".bin"


def sharded_relative_path(face_id: int, image_bytes: bytes) -> str:
    digest = hashlib.sha1(f"{face_id}:{len(image_bytes)}".encode("utf-8")).hexdigest()
    shard_a = digest[:2]
    shard_b = digest[2:4]
    extension = _detect_extension(image_bytes)
    filename = f"{face_id}_{digest}{extension}"
    return str(Path(shard_a) / shard_b / filename)


@dataclass
class ImageWriteTask:
    face_id: int
    image_bytes: bytes
    future: asyncio.Future


class ImageStorageManager:
    def __init__(
        self,
        root_dir: str | None = None,
        worker_count: int = 2,
        queue_maxsize: int = 200,
        disk_warn_threshold: float = 0.80,
        throttle_seconds: float = 0.10,
        fsync_enabled: bool = False,
    ):
        self.root_dir = Path(root_dir or os.getenv("FACE_IMAGE_ROOT", "face_images"))
        self.worker_count = max(1, worker_count)
        self.queue: asyncio.Queue[ImageWriteTask] = asyncio.Queue(maxsize=queue_maxsize)
        self.disk_warn_threshold = disk_warn_threshold
        self.throttle_seconds = throttle_seconds
        self.fsync_enabled = fsync_enabled
        self._workers: list[asyncio.Task] = []
        self._stop = asyncio.Event()

    async def start(self) -> None:
        if self._workers:
            return

        self.root_dir.mkdir(parents=True, exist_ok=True)
        self._stop.clear()
        for index in range(self.worker_count):
            worker = asyncio.create_task(self._worker(index), name=f"image-writer-{index}")
            self._workers.append(worker)

    async def stop(self) -> None:
        if not self._workers:
            return

        self._stop.set()
        for worker in self._workers:
            worker.cancel()
        await asyncio.gather(*self._workers, return_exceptions=True)
        self._workers.clear()

    def _disk_pressure(self) -> float:
        usage = shutil.disk_usage(self.root_dir)
        if usage.total == 0:
            return 0.0
        return usage.used / usage.total

    async def _write_file(self, relative_path: str, image_bytes: bytes) -> str:
        full_path = self.root_dir / relative_path
        full_path.parent.mkdir(parents=True, exist_ok=True)

        def _sync_write():
            with open(full_path, "wb") as handle:
                handle.write(image_bytes)
                if self.fsync_enabled:
                    handle.flush()
                    os.fsync(handle.fileno())
            return str(full_path)

        return await asyncio.to_thread(_sync_write)

    async def _worker(self, _: int) -> None:
        while not self._stop.is_set():
            task = await self.queue.get()
            try:
                if self._disk_pressure() >= self.disk_warn_threshold:
                    await asyncio.sleep(self.throttle_seconds)

                relative_path = sharded_relative_path(task.face_id, task.image_bytes)
                absolute_path = await self._write_file(relative_path, task.image_bytes)
                if not task.future.done():
                    task.future.set_result(absolute_path)
            except Exception as exc:
                if not task.future.done():
                    task.future.set_exception(exc)
            finally:
                self.queue.task_done()

    async def enqueue_write(self, face_id: int, image_bytes: bytes) -> str:
        if not self._workers:
            await self.start()

        loop = asyncio.get_running_loop()
        future = loop.create_future()
        await self.queue.put(ImageWriteTask(face_id=face_id, image_bytes=image_bytes, future=future))
        return await future

    def relative_from_absolute(self, absolute_path: str) -> str:
        return str(Path(absolute_path).resolve().relative_to(self.root_dir.resolve()))

    def resolve_relative(self, relative_path: str) -> Path:
        return self.root_dir / relative_path


image_store = ImageStorageManager(
    worker_count=int(os.getenv("FACE_IMAGE_WORKERS", "2")),
    queue_maxsize=int(os.getenv("FACE_IMAGE_QUEUE_SIZE", "200")),
    disk_warn_threshold=float(os.getenv("FACE_IMAGE_DISK_WARN_THRESHOLD", "0.80")),
    throttle_seconds=float(os.getenv("FACE_IMAGE_THROTTLE_SEC", "0.10")),
    fsync_enabled=os.getenv("FACE_IMAGE_FSYNC", "false").lower() == "true",
)
