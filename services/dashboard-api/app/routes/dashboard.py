from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import AlertArchiveModel, AlertModel, CameraModel, EventLogModel, PersonModel, UserModel
from app.database.postgres import get_db_session
from app.routes.auth import get_current_user
from app.schemas.dashboard_schema import (
    AnalyticsMetricItem,
    AnalyticsSummaryResponse,
    AnalyticsTrendPoint,
    DashboardActivityItem,
    DashboardMetricSummary,
    DashboardOperationPoint,
    DashboardSummaryResponse,
)

router = APIRouter(
    prefix="/api/v1/dashboard",
    tags=["Dashboard"],
)


def _camera_label(camera_name: str | None, camera_id: str | None) -> str:
    return camera_name or camera_id or "Unknown camera"


def _person_label(person_name: str | None) -> str:
    return person_name or "Unknown subject"


def _build_alert_message(
    status: str,
    person_name: str | None,
    camera_name: str | None,
    camera_id: str | None,
) -> str:
    subject = _person_label(person_name)
    camera = _camera_label(camera_name, camera_id)

    if status == "resolved":
        return f"Alert resolved for {subject} on {camera}"
    if status == "acknowledged":
        return f"Alert acknowledged for {subject} on {camera}"
    if status == "false_alarm":
        return f"False alarm marked for {subject} on {camera}"
    return f"Pending alert for {subject} on {camera}"


def _start_of_day_utc(now: datetime) -> datetime:
    return datetime.combine(now.date(), datetime.min.time(), tzinfo=timezone.utc)


@router.get("/summary", response_model=DashboardSummaryResponse)
async def get_dashboard_summary(
    db: AsyncSession = Depends(get_db_session),
    current_user: UserModel = Depends(get_current_user),
):
    del current_user

    active_alerts_result = await db.execute(
        select(func.count(AlertModel.id)).where(
            AlertModel.status.in_(("pending", "acknowledged", "active"))
        )
    )
    online_cameras_result = await db.execute(
        select(func.count(CameraModel.id)).where(CameraModel.status.ilike("online"))
    )
    resolved_cases_result = await db.execute(
        select(func.count(AlertArchiveModel.id)).where(AlertArchiveModel.final_status == "resolved")
    )
    face_data_records_result = await db.execute(
        select(func.count(PersonModel.id)).where(PersonModel.is_active.is_(True))
    )

    now = datetime.now(timezone.utc)
    start_day = (now - timedelta(days=7)).date()
    operations_result = await db.execute(
        select(EventLogModel.timestamp).where(EventLogModel.timestamp >= datetime.combine(start_day, datetime.min.time(), tzinfo=timezone.utc))
    )
    day_counts = Counter()
    for timestamp in operations_result.scalars():
        if timestamp is None:
            continue
        day_counts[timestamp.astimezone(timezone.utc).date()] += 1

    operations = [
        DashboardOperationPoint(
            label=(start_day + timedelta(days=offset)).strftime("%d %b"),
            value=day_counts.get(start_day + timedelta(days=offset), 0),
        )
        for offset in range(8)
    ]

    alerts_result = await db.execute(
        select(
            AlertModel.id,
            AlertModel.status,
            AlertModel.camera_id,
            AlertModel.timestamp,
            PersonModel.name,
            CameraModel.camera_name,
        )
        .outerjoin(PersonModel, AlertModel.person_id == PersonModel.id)
        .outerjoin(CameraModel, AlertModel.camera_id == CameraModel.camera_id)
        .order_by(desc(AlertModel.timestamp))
        .limit(5)
    )

    events_result = await db.execute(
        select(
            EventLogModel.id,
            EventLogModel.camera_id,
            EventLogModel.timestamp,
            EventLogModel.confidence,
            PersonModel.name,
            CameraModel.camera_name,
        )
        .outerjoin(PersonModel, EventLogModel.person_id == PersonModel.id)
        .outerjoin(CameraModel, EventLogModel.camera_id == CameraModel.camera_id)
        .order_by(desc(EventLogModel.timestamp))
        .limit(5)
    )

    archive_result = await db.execute(
        select(
            AlertArchiveModel.id,
            AlertArchiveModel.original_alert_id,
            AlertArchiveModel.final_status,
            AlertArchiveModel.camera_id,
            AlertArchiveModel.archived_at,
            AlertArchiveModel.person_name,
            CameraModel.camera_name,
        )
        .outerjoin(CameraModel, AlertArchiveModel.camera_id == CameraModel.camera_id)
        .order_by(desc(AlertArchiveModel.archived_at))
        .limit(5)
    )

    recent_activity: list[DashboardActivityItem] = []

    for alert_id, status, camera_id, timestamp, person_name, camera_name in alerts_result.all():
        recent_activity.append(
            DashboardActivityItem(
                id=f"alert-{alert_id}",
                message=_build_alert_message(status, person_name, camera_name, camera_id),
                timestamp=timestamp,
            )
        )

    for event_id, camera_id, timestamp, confidence, person_name, camera_name in events_result.all():
        subject = _person_label(person_name)
        camera = _camera_label(camera_name, camera_id)
        confidence_text = f" ({round(float(confidence) * 100)}%)" if confidence is not None else ""
        recent_activity.append(
            DashboardActivityItem(
                id=f"event-{event_id}",
                message=f"Detection logged for {subject} on {camera}{confidence_text}",
                timestamp=timestamp,
            )
        )

    for archive_id, original_alert_id, final_status, camera_id, timestamp, person_name, camera_name in archive_result.all():
        subject = _person_label(person_name)
        camera = _camera_label(camera_name, camera_id)
        status_text = "resolved" if final_status == "resolved" else "marked false alarm"
        recent_activity.append(
            DashboardActivityItem(
                id=f"archive-{archive_id}",
                message=f"Alert #{original_alert_id} {status_text} for {subject} on {camera}",
                timestamp=timestamp,
            )
        )

    recent_activity.sort(key=lambda item: item.timestamp, reverse=True)

    return DashboardSummaryResponse(
        metrics=DashboardMetricSummary(
            active_alerts=int(active_alerts_result.scalar() or 0),
            online_cameras=int(online_cameras_result.scalar() or 0),
            resolved_cases=int(resolved_cases_result.scalar() or 0),
            face_data_records=int(face_data_records_result.scalar() or 0),
        ),
        operations=operations,
        recent_activity=recent_activity[:4],
    )


@router.get("/analytics", response_model=AnalyticsSummaryResponse)
async def get_analytics_summary(
    db: AsyncSession = Depends(get_db_session),
    current_user: UserModel = Depends(get_current_user),
):
    del current_user

    now = datetime.now(timezone.utc)
    today_start = _start_of_day_utc(now)
    trend_start_day = (now - timedelta(days=9)).date()

    avg_confidence_result = await db.execute(
        select(func.avg(EventLogModel.confidence)).where(EventLogModel.confidence.is_not(None))
    )
    detections_today_result = await db.execute(
        select(func.count(EventLogModel.id)).where(EventLogModel.timestamp >= today_start)
    )
    alerts_today_result = await db.execute(
        select(func.count(AlertModel.id)).where(AlertModel.timestamp >= today_start)
    )
    archived_today_result = await db.execute(
        select(func.count(AlertArchiveModel.id)).where(AlertArchiveModel.alert_timestamp >= today_start)
    )

    trend_rows_result = await db.execute(
        select(EventLogModel.timestamp).where(
            EventLogModel.timestamp >= datetime.combine(trend_start_day, datetime.min.time(), tzinfo=timezone.utc)
        )
    )

    trend_counts = Counter()
    for timestamp in trend_rows_result.scalars():
        if timestamp is None:
            continue
        trend_counts[timestamp.astimezone(timezone.utc).date()] += 1

    avg_confidence = avg_confidence_result.scalar()
    metrics = [
        AnalyticsMetricItem(
            label="Average Match Confidence",
            value=f"{round(float(avg_confidence or 0) * 100, 1)}%",
        ),
        AnalyticsMetricItem(
            label="Detections Today",
            value=str(int(detections_today_result.scalar() or 0)),
        ),
        AnalyticsMetricItem(
            label="Alerts Today",
            value=str(int(alerts_today_result.scalar() or 0) + int(archived_today_result.scalar() or 0)),
        ),
    ]

    trend = [
        AnalyticsTrendPoint(
            label=(trend_start_day + timedelta(days=offset)).strftime("%d %b"),
            value=trend_counts.get(trend_start_day + timedelta(days=offset), 0),
        )
        for offset in range(10)
    ]

    return AnalyticsSummaryResponse(metrics=metrics, trend=trend)
