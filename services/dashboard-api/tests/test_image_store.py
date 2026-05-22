import asyncio
import tempfile
import unittest
from pathlib import Path

from app.storage.image_store import ImageStorageManager, sharded_relative_path


class ImageStoreTests(unittest.IsolatedAsyncioTestCase):
    async def test_sharded_write_and_resolve(self):
        with tempfile.TemporaryDirectory() as tmp:
            manager = ImageStorageManager(root_dir=tmp, worker_count=1, queue_maxsize=10)
            await manager.start()
            try:
                image_bytes = b"\xff\xd8\xffsample-jpeg"
                absolute_path = await manager.enqueue_write(face_id=12, image_bytes=image_bytes)
                relative = manager.relative_from_absolute(absolute_path)
                resolved = manager.resolve_relative(relative)
                self.assertTrue(resolved.exists())
                self.assertEqual(resolved.read_bytes(), image_bytes)
            finally:
                await manager.stop()

    def test_sharded_path_format(self):
        path = sharded_relative_path(face_id=99, image_bytes=b"abc")
        self.assertGreaterEqual(len(Path(path).parts), 3)

    async def test_throttling_on_high_disk_pressure(self):
        with tempfile.TemporaryDirectory() as tmp:
            manager = ImageStorageManager(
                root_dir=tmp,
                worker_count=1,
                disk_warn_threshold=0.0,  # Always trigger throttle
                throttle_seconds=0.10,
            )
            # Mock _disk_pressure to always return 1.0 (100% usage)
            manager._disk_pressure = lambda: 1.0

            await manager.start()
            try:
                start_time = asyncio.get_event_loop().time()
                await manager.enqueue_write(face_id=1, image_bytes=b"throttled")
                end_time = asyncio.get_event_loop().time()

                # It should take at least the throttle duration
                self.assertGreaterEqual(end_time - start_time, 0.09)
            finally:
                await manager.stop()



if __name__ == "__main__":
    unittest.main()
