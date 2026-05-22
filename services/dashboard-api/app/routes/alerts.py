from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
import logging
import json
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, desc, func

from app.database.postgres import get_db_session
from app.database.models import AlertArchiveModel, AlertModel, AlertSuppressionModel, EventLogModel, PersonModel, UserModel
from app.schemas.detection_schema import AlertResponse, AlertUpdateRequest
from app.routes.auth import get_current_user
from app.services.tracking_service import stop_tracking_for_alert_model
from app.websocket.ws_manager import ws_manager

logger = logging.getLogger(__name__)

ACK_SUPPRESSION_SECONDS = 60 * 60

router = APIRouter(
    prefix="/api/v1/alerts",
    tags=["Alert Management"]
)


def detect_image_media_type(image_bytes: bytes | None) -> str:
    if not image_bytes:
        return "application/octet-stream"

    if image_bytes.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if image_bytes.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if image_bytes.startswith((b"GIF87a", b"GIF89a")):
        return "image/gif"
    if image_bytes.startswith(b"RIFF") and image_bytes[8:12] == b"WEBP":
        return "image/webp"
    if image_bytes.startswith(b"BM"):
        return "image/bmp"

    return "application/octet-stream"


def serialize_alert(
    alert: AlertModel,
    person_name: str | None = None,
    suspect_image_url: str | None = None,
    evidence_image_url: str | None = None,
) -> AlertResponse:
    return AlertResponse(
        id=alert.id,
        alert_type=alert.alert_type,
        camera_id=alert.camera_id,
        person_id=alert.person_id,
        person_name=person_name,
        severity=alert.severity,
        threat_level=alert.threat_level,
        category=alert.category,
        description=alert.description,
        status=alert.status,
        resolved_by=alert.resolved_by,
        notes=alert.notes,
        suspect_image_url=suspect_image_url,
        evidence_image_url=evidence_image_url,
        timestamp=alert.timestamp,
    )


async def get_latest_evidence_event_id(db: AsyncSession, alert: AlertModel) -> int | None:
    if alert.person_id is None:
        return None

    result = await db.execute(
        select(EventLogModel.id)
        .where(
            EventLogModel.person_id == alert.person_id,
            EventLogModel.camera_id == alert.camera_id,
            EventLogModel.evidence_path.is_not(None),
            EventLogModel.timestamp <= alert.timestamp,
        )
        .order_by(desc(EventLogModel.timestamp), desc(EventLogModel.id))
        .limit(1)
    )
    return result.scalar_one_or_none()


async def get_latest_evidence_path(db: AsyncSession, alert: AlertModel) -> str | None:
    event_id = await get_latest_evidence_event_id(db, alert)
    if event_id is None:
        return None

    event_log = await db.get(EventLogModel, event_id)
    return event_log.evidence_path if event_log else None


async def get_active_alert_count(db: AsyncSession) -> int:
    result = await db.execute(
        select(func.count(AlertModel.id)).where(
            AlertModel.status.in_(("pending", "acknowledged", "active"))
        )
    )
    return int(result.scalar() or 0)


async def broadcast_alert_count(db: AsyncSession, event_type: str, alert_id: int) -> None:
    await ws_manager.broadcast(
        {
            "type": event_type,
            "data": {
                "alert_id": alert_id,
                "active_count": await get_active_alert_count(db),
            },
        }
    )


async def archive_alert(
    db: AsyncSession,
    alert: AlertModel,
    final_status: str,
    resolved_by: str,
    notes: str | None,
) -> AlertArchiveModel:
    person = await db.get(PersonModel, alert.person_id) if alert.person_id is not None else None
    evidence_path = await get_latest_evidence_path(db, alert)
    archive = AlertArchiveModel(
        original_alert_id=alert.id,
        alert_type=alert.alert_type,
        camera_id=alert.camera_id,
        person_id=alert.person_id,
        person_name=person.name if person else None,
        severity=alert.severity,
        threat_level=alert.threat_level,
        category=alert.category,
        description=alert.description,
        final_status=final_status,
        resolved_by=resolved_by,
        notes=notes,
        suspect_image_path=person.image_path if person else None,
        evidence_path=evidence_path,
        metadata_json=json.dumps(
            {
                "active_alert_id": alert.id,
                "person_id": alert.person_id,
                "camera_id": alert.camera_id,
                "alert_type": alert.alert_type,
            }
        ),
        alert_timestamp=alert.timestamp,
    )
    db.add(archive)
    return archive


async def serialize_alert_with_person(db: AsyncSession, alert: AlertModel) -> AlertResponse:
    person_name: str | None = None
    suspect_image_url: str | None = None
    evidence_image_url: str | None = None

    if alert.person_id is not None:
        person = await db.get(PersonModel, alert.person_id)
        if person:
            person_name = person.name
            if person.image_path:
                suspect_image_url = f"/api/v1/faces/{alert.person_id}/image"

        event_id = await get_latest_evidence_event_id(db, alert)
        if event_id is not None:
            evidence_image_url = f"/api/v1/alerts/{alert.id}/evidence"

    return serialize_alert(
        alert,
        person_name=person_name,
        suspect_image_url=suspect_image_url,
        evidence_image_url=evidence_image_url,
    )

def serialize_archive(archive: AlertArchiveModel) -> AlertResponse:
    return AlertResponse(
        id=archive.original_alert_id,  # Use original ID for UI consistency
        alert_type=archive.alert_type,
        camera_id=archive.camera_id,
        person_id=archive.person_id,
        person_name=archive.person_name,
        severity=archive.severity,
        threat_level=archive.threat_level,
        category=archive.category,
        description=archive.description,
        status=archive.final_status,
        resolved_by=archive.resolved_by,
        notes=archive.notes,
        suspect_image_url=f"/api/v1/reports/history/{archive.id}/suspect-image" if archive.suspect_image_path else None,
        evidence_image_url=f"/api/v1/reports/history/{archive.id}/evidence-image" if archive.evidence_path else None,
        timestamp=archive.alert_timestamp,
    )


# ---------------------------------------------------
# GET ALERTS
# ---------------------------------------------------

@router.get("/", response_model=List[AlertResponse])
async def get_alerts(
    status: Optional[str] = Query(None),
    camera_id: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db_session),
    current_user: UserModel = Depends(get_current_user)
):
    try:
        # If looking for resolved/false_alarm, we must query the archive table
        if status in ("resolved", "false_alarm"):
            query = select(AlertArchiveModel).order_by(desc(AlertArchiveModel.archived_at))
            if status:
                query = query.where(AlertArchiveModel.final_status == status)
            if camera_id:
                query = query.where(AlertArchiveModel.camera_id == camera_id)
            
            query = query.offset(offset).limit(limit)
            result = await db.execute(query)
            archives = result.scalars().all()
            return [serialize_archive(a) for a in archives]

        # Otherwise query the active alerts table
        query = select(AlertModel).order_by(desc(AlertModel.timestamp))

        if status:
            query = query.where(AlertModel.status == status)
        else:
            query = query.where(AlertModel.status.in_(("pending", "acknowledged", "active")))

        if camera_id:
            query = query.where(AlertModel.camera_id == camera_id)

        query = query.offset(offset).limit(limit)

        result = await db.execute(query)
        alerts = result.scalars().all()

        serialized_alerts: list[AlertResponse] = []
        for alert in alerts:
            serialized_alerts.append(await serialize_alert_with_person(db, alert))

        return serialized_alerts

    except Exception as e:
        logger.error(f"Fetch alerts failed: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch alerts")


@router.get("/stats")
async def get_alert_stats(
    db: AsyncSession = Depends(get_db_session),
    current_user: UserModel = Depends(get_current_user),
):
    # Query active alert counts
    active_res = await db.execute(
        select(AlertModel.status, func.count(AlertModel.id))
        .group_by(AlertModel.status)
    )
    active_counts = {row[0]: row[1] for row in active_res.all()}

    # Query archive alert counts
    archive_res = await db.execute(
        select(AlertArchiveModel.final_status, func.count(AlertArchiveModel.id))
        .group_by(AlertArchiveModel.final_status)
    )
    archive_counts = {row[0]: row[1] for row in archive_res.all()}

    return {
        "pending": active_counts.get("pending", 0) + active_counts.get("active", 0),
        "acknowledged": active_counts.get("acknowledged", 0),
        "resolved": archive_counts.get("resolved", 0),
        "false_alarm": archive_counts.get("false_alarm", 0),
    }


@router.get("/active-count")
async def get_active_count(
    db: AsyncSession = Depends(get_db_session),
    current_user: UserModel = Depends(get_current_user),
):
    del current_user
    return {"active_count": await get_active_alert_count(db)}


@router.get("/{alert_id}/evidence")
async def get_alert_evidence(
    alert_id: int,
    db: AsyncSession = Depends(get_db_session),
    current_user: UserModel = Depends(get_current_user),
):
    del current_user

    alert = await db.get(AlertModel, alert_id)
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")

    event_id = await get_latest_evidence_event_id(db, alert)
    if event_id is None:
        raise HTTPException(status_code=404, detail="Evidence image not found")

    event_log = await db.get(EventLogModel, event_id)
    if event_log is None or not event_log.evidence_path:
        raise HTTPException(status_code=404, detail="Evidence image not found")

    try:
        with open(event_log.evidence_path, "rb") as handle:
            file_bytes = handle.read()
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Evidence file missing on disk")
    except Exception as exc:
        logger.error("Failed to read evidence image for alert %s: %s", alert_id, exc)
        raise HTTPException(status_code=500, detail="Could not fetch evidence image")

    return Response(content=file_bytes, media_type=detect_image_media_type(file_bytes))


# ---------------------------------------------------
# ACKNOWLEDGE
# ---------------------------------------------------

@router.patch("/{alert_id}/acknowledge", response_model=AlertResponse)
async def acknowledge_alert(
    alert_id: int,
    payload: AlertUpdateRequest,
    db: AsyncSession = Depends(get_db_session),
    current_user: UserModel = Depends(get_current_user)
):
    try:

        alert = await db.get(AlertModel, alert_id)

        if not alert:
            raise HTTPException(404, "Alert not found")

        alert.status = "acknowledged"
        alert.notes = payload.notes
        alert.resolved_by = current_user.username

        if alert.person_id is not None:
            db.add(
                AlertSuppressionModel(
                    person_id=alert.person_id,
                    camera_id=None,
                    source_alert_id=alert.id,
                    reason="acknowledged",
                    suppressed_by=current_user.username,
                    suppress_until=datetime.now(timezone.utc) + timedelta(seconds=ACK_SUPPRESSION_SECONDS),
                )
            )

        await db.commit()
        await db.refresh(alert)

        await broadcast_alert_count(db, "ALERT_ACKNOWLEDGED", alert.id)

        return await serialize_alert_with_person(db, alert)

    except Exception as e:
        await db.rollback()
        logger.error(f"Acknowledge failed: {e}")
        raise HTTPException(500, "DB error")


# ---------------------------------------------------
# RESOLVE
# ---------------------------------------------------

@router.patch("/{alert_id}/resolve", response_model=AlertResponse)
async def resolve_alert(
    alert_id: int,
    payload: AlertUpdateRequest,
    db: AsyncSession = Depends(get_db_session),
    current_user: UserModel = Depends(get_current_user)
):
    try:

        alert = await db.get(AlertModel, alert_id)

        if not alert:
            raise HTTPException(404, "Alert not found")

        person = await db.get(PersonModel, alert.person_id) if alert.person_id else None
        response_alert = serialize_alert(
            alert,
            person_name=person.name if person else None,
        )
        response_alert.status = "resolved"
        response_alert.resolved_by = current_user.username
        response_alert.notes = payload.notes

        alert.status = "resolved"
        alert.notes = payload.notes
        alert.resolved_by = current_user.username
        await stop_tracking_for_alert_model(db, alert, "resolved")
        await archive_alert(db, alert, "resolved", current_user.username, payload.notes)
        await db.delete(alert)
        await db.commit()

        await broadcast_alert_count(db, "ALERT_RESOLVED", alert_id)

        return response_alert

    except Exception as e:
        await db.rollback()
        logger.error(f"Resolve failed: {e}")
        raise HTTPException(500, "DB error")


# ---------------------------------------------------
# FALSE ALARM
# ---------------------------------------------------

@router.patch("/{alert_id}/false-alarm", response_model=AlertResponse)
async def false_alarm(
    alert_id: int,
    payload: AlertUpdateRequest,
    db: AsyncSession = Depends(get_db_session),
    current_user: UserModel = Depends(get_current_user)
):
    try:

        alert = await db.get(AlertModel, alert_id)

        if not alert:
            raise HTTPException(404, "Alert not found")

        person = await db.get(PersonModel, alert.person_id) if alert.person_id else None
        response_alert = serialize_alert(
            alert,
            person_name=person.name if person else None,
        )
        response_alert.status = "false_alarm"
        response_alert.resolved_by = current_user.username
        response_alert.notes = payload.notes

        alert.status = "false_alarm"
        alert.notes = payload.notes
        alert.resolved_by = current_user.username
        await stop_tracking_for_alert_model(db, alert, "false_alarm")
        await archive_alert(db, alert, "false_alarm", current_user.username, payload.notes)
        await db.delete(alert)
        await db.commit()

        await broadcast_alert_count(db, "ALERT_FALSE_ALARM", alert_id)

        return response_alert

    except Exception as e:
        await db.rollback()
        logger.error(f"False alarm failed: {e}")
        raise HTTPException(500, "DB error")
