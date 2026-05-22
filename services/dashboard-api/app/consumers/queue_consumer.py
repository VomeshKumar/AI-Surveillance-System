from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from uuid import uuid4

from redis.asyncio import Redis

from app.consumers.backpressure import BackpressureThresholds, evaluate_backpressure
from app.consumers.deduplicator import DetectionDeduplicator
from app.consumers.runtime_state import runtime_state
from app.database.models import PersonModel
from app.database.postgres import AsyncSessionLocal
from app.ingestion.adaptive_sampler import AdaptiveFrameSampler
from app.services.alert_dispatcher import process_alert
from app.services.tracking_service import update_tracking_for_detection
from app.websocket.ws_manager import ws_manager

logger = logging.getLogger(__name__)


class FaceDetectionConsumer:
    def __init__(
        self,
        redis_client: Redis,
        stream_name: str = "face_events",
        group_name: str = "api_group",
        consumer_name: str | None = None,
    ):
        self.redis = redis_client
        self.stream_name = stream_name
        self.group_name = group_name
        self.consumer_name = consumer_name or f"api_worker_{uuid4()}"
        self.ws_semaphore = asyncio.Semaphore(50)
        self.deduplicator = DetectionDeduplicator(
            window_seconds=float(os.getenv("DETECTION_DEDUP_WINDOW_SEC", "2.0"))
        )
        self.sampler = AdaptiveFrameSampler(redis_client=self.redis)
        self.thresholds = BackpressureThresholds(
            soft_limit=int(os.getenv("STREAM_SOFT_LIMIT", "1000")),
            hard_limit=int(os.getenv("STREAM_HARD_LIMIT", "3000")),
            low_confidence_limit=float(os.getenv("LOW_CONFIDENCE_LIMIT", "0.75")),
            preserve_confidence=float(os.getenv("HIGH_CONFIDENCE_PRESERVE", "0.90")),
        )
        self._last_lag_refresh = 0.0
        self._cached_pending_lag = 0
        self._camera_policy_updated_at: dict[str, float] = {}

    async def setup_stream(self):
        try:
            await self.redis.xgroup_create(
                self.stream_name,
                self.group_name,
                id="$",
                mkstream=True,
            )
            logger.info("Stream %s + group %s ready", self.stream_name, self.group_name)
        except Exception as exc:
            if "BUSYGROUP" in str(exc):
                logger.info("Consumer group already exists for stream %s", self.stream_name)
            else:
                logger.error("Stream setup error for %s: %s", self.stream_name, exc)

    async def _fetch_pending_lag(self) -> int:
        now = time.monotonic()
        if now - self._last_lag_refresh < 1.0:
            return self._cached_pending_lag

        pending = 0
        try:
            groups = await self.redis.xinfo_groups(self.stream_name)
            for group in groups:
                name = group.get("name")
                if name == self.group_name:
                    pending = int(group.get("pending", 0))
                    break
        except Exception as exc:
            logger.warning("Lag check failed for %s: %s", self.stream_name, exc)

        self._cached_pending_lag = pending
        self._last_lag_refresh = now
        return pending

    async def start_consuming(self):
        logger.info("Consumer started stream=%s consumer=%s", self.stream_name, self.consumer_name)
        await self.setup_stream()

        while True:
            try:
                runtime_state.heartbeat(self.consumer_name, self.stream_name)

                messages = await self.redis.xreadgroup(
                    groupname=self.group_name,
                    consumername=self.consumer_name,
                    streams={self.stream_name: ">"},
                    count=10,
                    block=2000,
                )

                if not messages:
                    continue

                for _, stream_messages in messages:
                    for message_id, message in stream_messages:
                        try:
                            await self.process_event(message_id, message)
                            await self.redis.xack(self.stream_name, self.group_name, message_id)
                        except Exception as exc:
                            logger.error("Message failed stream=%s id=%s error=%s", self.stream_name, message_id, exc)

            except asyncio.CancelledError:
                logger.info("Consumer stopped stream=%s consumer=%s", self.stream_name, self.consumer_name)
                break
            except Exception as exc:
                logger.error("Consumer loop error stream=%s: %s", self.stream_name, exc)
                await asyncio.sleep(2)

    async def process_event(self, message_id, message):
        raw_data = message.get("alert") or message.get(b"alert")
        payload_data = message.get("payload") or message.get(b"payload")

        if raw_data is None and payload_data is not None:
            raw_data = payload_data

        if not raw_data:
            runtime_state.increment("invalid_empty_payload")
            return

        if isinstance(raw_data, bytes):
            raw_data = raw_data.decode()

        try:
            detection = json.loads(raw_data)
        except Exception:
            runtime_state.increment("invalid_json")
            return

        person_id = detection.get("person_id", detection.get("face_id"))
        score_value = detection.get("score", detection.get("confidence", 1.0))

        try:
            face_id = int(person_id)
        except (TypeError, ValueError):
            runtime_state.increment("invalid_missing_fields")
            return
        camera_id = detection.get("camera_id")
        try:
            confidence = float(score_value)
        except (TypeError, ValueError):
            runtime_state.increment("invalid_missing_fields")
            return

        # Re-inject mapped keys so downstream process_alert works
        detection["person_id"] = face_id
        detection["face_id"] = face_id
        detection["score"] = confidence
        detection["confidence"] = confidence

        if not face_id or not camera_id:
            runtime_state.increment("invalid_missing_fields")
            return

        pending_lag = await self._fetch_pending_lag()
        camera_key = str(camera_id)
        try:
            await self.redis.sadd("ai:cameras", camera_key)
        except Exception:
            pass

        last_update = self._camera_policy_updated_at.get(camera_key, 0.0)
        now = time.monotonic()
        if now - last_update >= 5.0:
            await self.sampler.update_from_metrics(
                camera_id=camera_key,
                stream_lag=pending_lag,
            )
            self._camera_policy_updated_at[camera_key] = now

        decision = evaluate_backpressure(
            pending_lag=pending_lag,
            confidence=confidence,
            thresholds=self.thresholds,
        )

        if decision.preserved_high_confidence:
            runtime_state.increment("high_conf_preserved")

        if decision.hard_limited:
            runtime_state.increment("hard_limited_ingestion")
            await self.sampler.force_emergency(camera_key)

        if decision.drop:
            runtime_state.increment("dropped_soft")
            return

        if self.deduplicator.is_duplicate(int(face_id), str(camera_id)):
            runtime_state.increment("duplicates_filtered")
            return

        async with AsyncSessionLocal() as db:
            identity = await db.get(PersonModel, face_id)
            if not identity:
                runtime_state.increment("unknown_face_skipped")
                return
            if not identity.is_active:
                runtime_state.increment("inactive_face_skipped")
                return

        # V2 MIGRATION: Dashboard no longer logs to DB. Engine does this directly.
        runtime_state.increment("processed")

        alert_status = await process_alert(detection)
        if alert_status is not None:
            runtime_state.increment("alert_created")

        async with AsyncSessionLocal() as db:
            await update_tracking_for_detection(
                db=db,
                person_id=face_id,
                camera_id=str(camera_id),
                confidence=confidence,
            )

        event_type = "ALERT_CREATED" if alert_status is not None else "NEW_DETECTION"
        ws_payload = {
            "type": event_type,
            "data": {
                "face_id": face_id,
                "camera_id": camera_id,
                "confidence": confidence,
                "watch_status": identity.category,
                "threat_level": identity.threat_level,
                "crime_type": identity.crime_type,
                "name": identity.name,
            },
            "alert": alert_status,
        }

        async with self.ws_semaphore:
            await ws_manager.broadcast(ws_payload)

        logger.info("Event processed stream=%s id=%s", self.stream_name, message_id)
