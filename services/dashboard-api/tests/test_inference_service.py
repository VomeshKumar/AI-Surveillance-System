import asyncio
import unittest

from app.ai.gpu_guard import GPUMemoryGuard
from app.ai.inference_service import InferenceService


class FakeModel:
    def infer(self, payloads, device="gpu"):
        return [{**payload, "device": device} for payload in payloads]


class FakeGuard(GPUMemoryGuard):
    def __init__(self, forced_device: str):
        super().__init__(soft_limit_bytes=1)
        self.forced_device = forced_device

    def select_device(self, now=None):
        return self.forced_device


class InferenceServiceTests(unittest.IsolatedAsyncioTestCase):
    async def test_micro_batch_respects_device_selection(self):
        service = InferenceService(
            model=FakeModel(),
            batch_size=4,
            batch_timeout_ms=50,
            gpu_guard=FakeGuard("cpu"),
        )

        worker = asyncio.create_task(service.run())
        try:
            result = await service.submit({"camera_id": "cam-1"})
            self.assertEqual(result["device"], "cpu")
            self.assertEqual(result["camera_id"], "cam-1")
        finally:
            service.stop()
            worker.cancel()
            await asyncio.gather(worker, return_exceptions=True)


if __name__ == "__main__":
    unittest.main()

