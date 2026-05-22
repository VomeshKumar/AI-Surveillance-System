import logging
import os
from typing import Optional, Dict, Any
from datetime import datetime, timedelta, timezone

from app.database.postgres import AsyncSessionLocal
from app.database.models import AlertSuppressionModel, PersonModel, AlertModel
from app.database.redis_cache import redis_manager
from sqlalchemy import desc, select

logger = logging.getLogger(__name__)

ALERT_COOLDOWN_SECONDS = int(os.getenv("ALERT_COOLDOWN_SECONDS", "300"))
# The AI engine has already decided this is a valid match before publishing
# the event. Keep the dashboard-side threshold configurable and aligned with
# the engine instead of silently filtering lower-confidence engine alerts.
MIN_CONFIDENCE_THRESHOLD = float(os.getenv("ALERT_MIN_CONFIDENCE_THRESHOLD", "0.40"))


# --------------------------------------------
# Severity mapping based on watchlist category
# --------------------------------------------
SEVERITY_MAP = {
    "suspect": "MEDIUM",
    "wanted": "HIGH",
    "confirmed_criminal": "CRITICAL",
    "high_risk": "CRITICAL"
}


async def _has_recent_db_alert(db, face_id: int, camera_id: str, cooldown_seconds: int) -> bool:
    cooldown_since = datetime.now(timezone.utc) - timedelta(seconds=cooldown_seconds)
    result = await db.execute(
        select(AlertModel.id)
        .where(
            AlertModel.person_id == face_id,
            AlertModel.camera_id == camera_id,
            AlertModel.timestamp >= cooldown_since,
            AlertModel.status.in_(("pending", "acknowledged")),
        )
        .order_by(desc(AlertModel.timestamp))
        .limit(1)
    )
    return result.scalar_one_or_none() is not None


async def _is_person_suppressed(db, face_id: int, camera_id: str) -> bool:
    now = datetime.now(timezone.utc)
    result = await db.execute(
        select(AlertSuppressionModel.id)
        .where(
            AlertSuppressionModel.person_id == face_id,
            AlertSuppressionModel.suppress_until > now,
            (
                (AlertSuppressionModel.camera_id == camera_id)
                | AlertSuppressionModel.camera_id.is_(None)
            ),
        )
        .order_by(desc(AlertSuppressionModel.suppress_until))
        .limit(1)
    )
    return result.scalar_one_or_none() is not None


async def process_alert(
    detection_data: Dict[str, Any]
) -> Optional[Dict[str, Any]]:
    """
    Process matched watchlist detections
    and create intelligent alerts.
    """

    face_id = detection_data.get("face_id")
    camera_id = detection_data.get("camera_id")
    confidence = detection_data.get("confidence", 1.0)
    is_match = detection_data.get("match", True)

    # -------------------------------
    # 1) Basic validation
    # -------------------------------
    if not face_id or not camera_id:
        return None

    # Ignore unmatched / unknown
    if not is_match:
        return None

    # confidence threshold
    if confidence < MIN_CONFIDENCE_THRESHOLD:
        logger.info(
            "Skipping alert creation for face_id=%s camera_id=%s confidence=%.3f below threshold=%.3f",
            face_id,
            camera_id,
            confidence,
            MIN_CONFIDENCE_THRESHOLD,
        )
        return None

    async with AsyncSessionLocal() as db:
        try:
            # -------------------------------
            # 2) Fetch identity (cache first)
            # -------------------------------
            identity = await redis_manager.get_identity(face_id)

            if not identity:
                identity = await db.get(PersonModel, face_id)

                if not identity:
                    return None

                await redis_manager.set_identity(face_id, identity)

            # support dict (from cache) + ORM object
            if isinstance(identity, dict):
                category = identity.get("category")
                threat_level = identity.get("threat_level")
                name = identity.get("name")
                is_active = identity.get("is_active", True)
                crime_type = identity.get("crime_type")
            else:
                category = identity.category
                threat_level = identity.threat_level
                name = identity.name
                is_active = identity.is_active
                crime_type = identity.crime_type

            # -------------------------------
            # 3) inactive watchlist skip
            # -------------------------------
            if not is_active:
                return None

            # -------------------------------
            # 4) Alert eligibility
            # -------------------------------
            # Allow all categories. If not in map, default to LOW.
            severity = SEVERITY_MAP.get(category, "LOW")
            alert_type = f"{category or 'person'}_detected"

            # threat escalation override
            if threat_level == "CRITICAL":
                severity = "CRITICAL"

            # -------------------------------
            # 5) Cooldown / debounce
            # -------------------------------
            if await _is_person_suppressed(db, face_id, camera_id):
                logger.info(
                    "Skipping alert creation for face_id=%s camera_id=%s because acknowledge suppression is active",
                    face_id,
                    camera_id,
                )
                return None

            is_cooldown = await redis_manager.is_alert_on_cooldown(
                face_id=face_id,
                camera_id=camera_id,
                cooldown_seconds=ALERT_COOLDOWN_SECONDS
            )

            if is_cooldown or await _has_recent_db_alert(db, face_id, camera_id, ALERT_COOLDOWN_SECONDS):
                return None

            # -------------------------------
            # 6) Create DB alert
            # -------------------------------
            description = (
                f"🚨 {category.upper()} DETECTED: {name}"
            )

            if crime_type:
                description += f" | Crime: {crime_type}"

            new_alert = AlertModel(
                alert_type=alert_type,
                camera_id=camera_id,
                person_id=face_id,
                description=description,
                status="pending",
                severity=severity,
                threat_level=threat_level,
                category=category
            )

            db.add(new_alert)
            await db.commit()
            await db.refresh(new_alert)

            # -------------------------------
            # 7) Set cooldown
            # -------------------------------
            await redis_manager.set_alert_cooldown(
                face_id=face_id,
                camera_id=camera_id,
                ttl=ALERT_COOLDOWN_SECONDS
            )

            logger.warning(
                f"🚨 ALERT: {name} ({category}) detected on {camera_id}"
            )

            return {
                "alert_id": new_alert.id,
                "person_id": face_id,
                "alert_type": new_alert.alert_type,
                "camera_id": new_alert.camera_id,
                "description": new_alert.description,
                "severity": new_alert.severity,
                "threat_level": new_alert.threat_level,
                "status": new_alert.status,
                "timestamp": new_alert.timestamp.isoformat()
            }

        except Exception as e:
            await db.rollback()
            logger.error(f"Error processing alert for face {face_id}: {e}")
            return None
