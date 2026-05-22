import json
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from app.consumers.queue_consumer import FaceDetectionConsumer


class FakeRedis:
    async def sadd(self, *args, **kwargs):
        return 1

    async def xinfo_groups(self, *args, **kwargs):
        return []

    async def hget(self, *args, **kwargs):
        return None

    async def hset(self, *args, **kwargs):
        return 1

    async def expire(self, *args, **kwargs):
        return True


class FakeDbSession:
    async def get(self, model, face_id):
        return SimpleNamespace(
            id=face_id,
            is_active=True,
            category="suspect",
            threat_level="HIGH",
            crime_type="fraud",
            name="Vomesh",
        )


class FakeSessionFactory:
    def __call__(self):
        return self

    async def __aenter__(self):
        return FakeDbSession()

    async def __aexit__(self, exc_type, exc, tb):
        return False


class QueueConsumerContractTests(unittest.IsolatedAsyncioTestCase):
    async def test_process_event_accepts_engine_alert_format(self):
        consumer = FaceDetectionConsumer(redis_client=FakeRedis(), stream_name="face_events")
        message = {
            "alert": json.dumps(
                {
                    "person_id": 7,
                    "camera_id": "cam-1",
                    "score": 0.91,
                    "name": "Vomesh",
                }
            )
        }

        with (
            patch("app.consumers.queue_consumer.AsyncSessionLocal", new=FakeSessionFactory()),
            patch("app.consumers.queue_consumer.process_alert", new=AsyncMock(return_value={"alert_id": 1})),
            patch("app.consumers.queue_consumer.update_tracking_for_detection", new=AsyncMock()),
            patch("app.consumers.queue_consumer.ws_manager.broadcast", new=AsyncMock()),
        ):
            await consumer.process_event("1-0", message)

        self.assertEqual(consumer._cached_pending_lag, 0)

    async def test_process_event_accepts_legacy_payload_format(self):
        consumer = FaceDetectionConsumer(redis_client=FakeRedis(), stream_name="face_events")
        message = {
            "payload": json.dumps(
                {
                    "face_id": 9,
                    "camera_id": "cam-2",
                    "confidence": 0.88,
                }
            )
        }

        with (
            patch("app.consumers.queue_consumer.AsyncSessionLocal", new=FakeSessionFactory()),
            patch("app.consumers.queue_consumer.process_alert", new=AsyncMock(return_value={"alert_id": 2})),
            patch("app.consumers.queue_consumer.update_tracking_for_detection", new=AsyncMock()),
            patch("app.consumers.queue_consumer.ws_manager.broadcast", new=AsyncMock()),
        ):
            await consumer.process_event("2-0", message)

        self.assertEqual(consumer._cached_pending_lag, 0)


if __name__ == "__main__":
    unittest.main()
