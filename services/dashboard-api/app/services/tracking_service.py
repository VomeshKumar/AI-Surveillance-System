from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import AlertModel, CameraModel, TrackingSessionModel, TrackingTransitionModel
from app.websocket.ws_manager import ws_manager


async def get_active_sessions_for_person(db: AsyncSession, person_id: int) -> list[TrackingSessionModel]:
    result = await db.execute(
        select(TrackingSessionModel)
        .where(
            TrackingSessionModel.person_id == person_id,
            TrackingSessionModel.status == "active",
        )
        .order_by(desc(TrackingSessionModel.started_at))
    )
    return list(result.scalars().all())


async def update_tracking_for_detection(
    db: AsyncSession,
    person_id: int,
    camera_id: str,
    confidence: float | None = None,
    detected_at: datetime | None = None,
    bbox: list[int] | None = None,
) -> None:
    sessions = await get_active_sessions_for_person(db, person_id)
    if not sessions:
        return

    detected_at = detected_at or datetime.now(timezone.utc)
    if detected_at.tzinfo is None:
        detected_at = detected_at.replace(tzinfo=timezone.utc)

    camera_result = await db.execute(select(CameraModel).where(CameraModel.camera_id == camera_id))
    camera = camera_result.scalars().first()
    updated_sessions: list[tuple[TrackingSessionModel, bool]] = []

    for session in sessions:
        last_detection_at = session.last_detection_at
        if last_detection_at and last_detection_at.tzinfo is None:
            last_detection_at = last_detection_at.replace(tzinfo=timezone.utc)
        if last_detection_at and detected_at < last_detection_at:
            continue

        camera_changed = session.current_camera_id != camera_id
        should_log = camera_changed or session.last_detection_at is None

        session.current_camera_id = camera_id
        session.last_detection_at = detected_at

        if should_log:
            db.add(
                TrackingTransitionModel(
                    session_id=session.id,
                    person_id=person_id,
                    camera_id=camera_id,
                    confidence=confidence,
                    detected_at=detected_at,
                )
            )

        updated_sessions.append((session, camera_changed))

    if not updated_sessions:
        return

    await db.commit()

    for session, camera_changed in updated_sessions:
        await ws_manager.broadcast(
            {
                "type": "TRACKING_UPDATED",
                "data": {
                    "session_id": session.id,
                    "alert_id": session.alert_id,
                    "person_id": person_id,
                    "camera_id": camera_id,
                    "confidence": confidence,
                    "detected_at": detected_at.isoformat(),
                    "camera_changed": camera_changed,
                    "camera_name": camera.camera_name if camera else None,
                    "camera_location": camera.location if camera else None,
                    "bbox": bbox,
                },
            }
        )


async def stop_tracking_for_alert(
    db: AsyncSession,
    alert_id: int,
    reason: str,
) -> None:
    result = await db.execute(
        select(TrackingSessionModel).where(
            TrackingSessionModel.alert_id == alert_id,
            TrackingSessionModel.status == "active",
        )
    )
    sessions = result.scalars().all()
    if not sessions:
        return

    ended_at = datetime.now(timezone.utc)
    for session in sessions:
        session.status = "ended"
        session.ended_at = ended_at
        session.ended_reason = reason

    await db.commit()

    for session in sessions:
        await ws_manager.broadcast(
            {
                "type": "TRACKING_ENDED",
                "data": {
                    "session_id": session.id,
                    "alert_id": session.alert_id,
                    "person_id": session.person_id,
                    "reason": reason,
                    "ended_at": ended_at.isoformat(),
                },
            }
        )


async def stop_tracking_for_alert_model(
    db: AsyncSession,
    alert: AlertModel,
    reason: str,
) -> None:
    await stop_tracking_for_alert(db, alert.id, reason)
