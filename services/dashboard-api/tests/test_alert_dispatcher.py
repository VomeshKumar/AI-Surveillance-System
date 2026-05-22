import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from app.services import alert_dispatcher


class FakeDbSession:
    def __init__(self, recent_alert_id=None):
        self.added = []
        self.recent_alert_id = recent_alert_id

    async def get(self, model, face_id):
        return SimpleNamespace(
            id=face_id,
            category="suspect",
            threat_level="HIGH",
            name="Atul",
            is_active=True,
            crime_type="fraud",
        )

    def add(self, item):
        item.id = 1
        item.timestamp = SimpleNamespace(isoformat=lambda: "2026-05-06T16:00:00+00:00")
        self.added.append(item)

    async def execute(self, statement):
        del statement

        class Result:
            def __init__(self, value):
                self.value = value

            def scalar_one_or_none(self):
                return self.value

        return Result(self.recent_alert_id)

    async def commit(self):
        return None

    async def refresh(self, item):
        return None

    async def rollback(self):
        return None


class FakeSessionFactory:
    def __init__(self, recent_alert_id=None):
        self.session = FakeDbSession(recent_alert_id=recent_alert_id)

    def __call__(self):
        return self

    async def __aenter__(self):
        return self.session

    async def __aexit__(self, exc_type, exc, tb):
        return False


class AlertDispatcherTests(unittest.IsolatedAsyncioTestCase):
    async def test_process_alert_allows_engine_level_match_confidence(self):
        session_factory = FakeSessionFactory()
        detection = {
            "face_id": 1,
            "camera_id": "vgf",
            "confidence": 0.46,
            "match": True,
        }

        with (
            patch.object(alert_dispatcher, "AsyncSessionLocal", new=session_factory),
            patch.object(alert_dispatcher.redis_manager, "get_identity", new=AsyncMock(return_value=None)),
            patch.object(alert_dispatcher.redis_manager, "set_identity", new=AsyncMock()),
            patch.object(alert_dispatcher.redis_manager, "is_alert_on_cooldown", new=AsyncMock(return_value=False)),
            patch.object(alert_dispatcher.redis_manager, "set_alert_cooldown", new=AsyncMock()),
        ):
            result = await alert_dispatcher.process_alert(detection)

        self.assertIsNotNone(result)
        self.assertEqual(result["camera_id"], "vgf")
        self.assertEqual(result["person_id"], 1)

    async def test_process_alert_uses_db_cooldown_when_redis_allows(self):
        session_factory = FakeSessionFactory(recent_alert_id=99)
        detection = {
            "face_id": 1,
            "camera_id": "vgf",
            "confidence": 0.46,
            "match": True,
        }

        with (
            patch.object(alert_dispatcher, "AsyncSessionLocal", new=session_factory),
            patch.object(alert_dispatcher.redis_manager, "get_identity", new=AsyncMock(return_value=None)),
            patch.object(alert_dispatcher.redis_manager, "set_identity", new=AsyncMock()),
            patch.object(alert_dispatcher.redis_manager, "is_alert_on_cooldown", new=AsyncMock(return_value=False)),
            patch.object(alert_dispatcher.redis_manager, "set_alert_cooldown", new=AsyncMock()),
        ):
            result = await alert_dispatcher.process_alert(detection)

        self.assertIsNone(result)
        self.assertEqual(session_factory.session.added, [])


if __name__ == "__main__":
    unittest.main()
