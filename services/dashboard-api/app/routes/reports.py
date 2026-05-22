from __future__ import annotations

import csv
from datetime import datetime, timedelta, timezone
from io import StringIO

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import AlertArchiveModel, AlertModel, CameraModel, EventLogModel, PersonModel, UserModel
from app.database.postgres import get_db_session
from app.routes.auth import get_current_user
from app.schemas.dashboard_schema import ReportItem, ReportMetricSummary, ReportsSummaryResponse

router = APIRouter(
    prefix="/api/v1/reports",
    tags=["Reports"],
)


REPORT_DEFINITIONS = {
    "daily-incident-log": {
        "name": "Daily Incident Log",
        "type": "PDF",
        "description": "Shift-ready incident summary with detection overview and operator notes.",
    },
    "weekly-watchlist-summary": {
        "name": "Weekly Watchlist Summary",
        "type": "CSV",
        "description": "Exportable weekly watchlist activity summary for audit and review.",
    },
    "monthly-analytics-pack": {
        "name": "Monthly Analytics Pack",
        "type": "CSV",
        "description": "Dashboard performance pack compiled from alert, camera, and detection trends.",
    },
}


def _format_generated_at(value: datetime | None) -> str:
    if value is None:
        return "Generated on demand"
    return value.astimezone(timezone.utc).strftime("%d %b %Y, %I:%M %p UTC")


def _detect_image_media_type(image_bytes: bytes | None) -> str:
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
    return "application/octet-stream"


def _csv_response(filename: str, rows: list[list[object]]) -> Response:
    buffer = StringIO()
    writer = csv.writer(buffer)
    writer.writerows(rows)
    return Response(
        content=buffer.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def _escape_pdf_text(value: object) -> str:
    return str(value).replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _simple_pdf_response(filename: str, title: str, lines: list[object]) -> Response:
    pdf_lines = [title, "", *[str(line) for line in lines]]
    text_commands = "\n".join(
        f"BT /F1 11 Tf 50 {760 - index * 18} Td ({_escape_pdf_text(line)}) Tj ET"
        for index, line in enumerate(pdf_lines[:38])
    )
    stream = f"{text_commands}\n"
    objects = [
        "1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n",
        "2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n",
        "3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>\nendobj\n",
        f"4 0 obj\n<< /Length {len(stream)} >>\nstream\n{stream}endstream\nendobj\n",
        "5 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\n",
    ]

    pdf = "%PDF-1.4\n"
    offsets = [0]
    for obj in objects:
        offsets.append(len(pdf))
        pdf += obj

    xref_start = len(pdf)
    pdf += (
        "xref\n0 6\n0000000000 65535 f \n"
        + "\n".join(f"{offset:010d} 00000 n " for offset in offsets[1:])
        + f"\ntrailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n{xref_start}\n%%EOF"
    )

    return Response(
        content=pdf.encode("latin-1", errors="replace"),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


async def _latest_report_timestamp(db: AsyncSession) -> datetime | None:
    latest_alert_result = await db.execute(select(func.max(AlertModel.timestamp)))
    latest_archive_result = await db.execute(select(func.max(AlertArchiveModel.archived_at)))
    latest_event_result = await db.execute(select(func.max(EventLogModel.timestamp)))
    values = [
        value
        for value in (
            latest_alert_result.scalar(),
            latest_archive_result.scalar(),
            latest_event_result.scalar(),
        )
        if value is not None
    ]
    return max(values) if values else None


@router.get("", response_model=ReportsSummaryResponse)
@router.get("/", response_model=ReportsSummaryResponse)
async def get_reports(
    db: AsyncSession = Depends(get_db_session),
    current_user: UserModel = Depends(get_current_user),
):
    del current_user

    generated_at = _format_generated_at(await _latest_report_timestamp(db))
    reports = [
        ReportItem(
            id=report_id,
            name=definition["name"],
            type=definition["type"],
            status="Ready",
            description=definition["description"],
            generated_at=generated_at,
        )
        for report_id, definition in REPORT_DEFINITIONS.items()
    ]

    return ReportsSummaryResponse(
        metrics=ReportMetricSummary(
            available_reports=len(reports),
            ready_to_download=len(reports),
            pending_generation=0,
        ),
        reports=reports,
    )


@router.get("/{report_id}/download")
async def download_report(
    report_id: str,
    db: AsyncSession = Depends(get_db_session),
    current_user: UserModel = Depends(get_current_user),
):
    del current_user

    if report_id not in REPORT_DEFINITIONS:
        raise HTTPException(status_code=404, detail="Report not found")

    now = datetime.now(timezone.utc)
    today_start = datetime.combine(now.date(), datetime.min.time(), tzinfo=timezone.utc)
    week_start = now - timedelta(days=7)
    month_start = now - timedelta(days=30)

    if report_id == "daily-incident-log":
        rows_result = await db.execute(
            select(
                AlertModel.id,
                AlertModel.status,
                AlertModel.alert_type,
                AlertModel.camera_id,
                AlertModel.timestamp,
                AlertModel.description,
                PersonModel.name,
                CameraModel.camera_name,
            )
            .outerjoin(PersonModel, AlertModel.person_id == PersonModel.id)
            .outerjoin(CameraModel, AlertModel.camera_id == CameraModel.camera_id)
            .where(AlertModel.timestamp >= today_start)
            .order_by(desc(AlertModel.timestamp))
            .limit(28)
        )
        archived_count_result = await db.execute(
            select(func.count(AlertArchiveModel.id)).where(AlertArchiveModel.alert_timestamp >= today_start)
        )
        lines = [
            f"Generated: {now.strftime('%d %b %Y, %I:%M %p UTC')}",
            f"Active alerts today: {len(rows_result.all())}",
            f"Archived alerts today: {int(archived_count_result.scalar() or 0)}",
            "",
        ]

        rows_result = await db.execute(
            select(
                AlertModel.id,
                AlertModel.status,
                AlertModel.alert_type,
                AlertModel.camera_id,
                AlertModel.timestamp,
                AlertModel.description,
                PersonModel.name,
                CameraModel.camera_name,
            )
            .outerjoin(PersonModel, AlertModel.person_id == PersonModel.id)
            .outerjoin(CameraModel, AlertModel.camera_id == CameraModel.camera_id)
            .where(AlertModel.timestamp >= today_start)
            .order_by(desc(AlertModel.timestamp))
            .limit(28)
        )
        for alert_id, status, alert_type, camera_id, timestamp, description, person_name, camera_name in rows_result.all():
            camera = camera_name or camera_id
            person = person_name or "Unknown"
            lines.append(f"#{alert_id} | {timestamp:%H:%M} | {status} | {alert_type} | {person} | {camera}")
            if description:
                lines.append(f"  {description[:110]}")

        archive_result = await db.execute(
            select(
                AlertArchiveModel.original_alert_id,
                AlertArchiveModel.final_status,
                AlertArchiveModel.alert_type,
                AlertArchiveModel.camera_id,
                AlertArchiveModel.alert_timestamp,
                AlertArchiveModel.description,
                AlertArchiveModel.person_name,
            )
            .where(AlertArchiveModel.alert_timestamp >= today_start)
            .order_by(desc(AlertArchiveModel.alert_timestamp))
            .limit(12)
        )
        for alert_id, status, alert_type, camera_id, timestamp, description, person_name in archive_result.all():
            lines.append(f"#{alert_id} | {timestamp:%H:%M} | {status} | {alert_type} | {person_name or 'Unknown'} | {camera_id}")
            if description:
                lines.append(f"  {description[:110]}")

        return _simple_pdf_response("daily-incident-log.pdf", "Daily Incident Log", lines)

    if report_id == "weekly-watchlist-summary":
        rows_result = await db.execute(
            select(
                EventLogModel.timestamp,
                PersonModel.name,
                PersonModel.suspect_code,
                PersonModel.category,
                PersonModel.threat_level,
                CameraModel.camera_name,
                EventLogModel.camera_id,
                EventLogModel.confidence,
            )
            .outerjoin(PersonModel, EventLogModel.person_id == PersonModel.id)
            .outerjoin(CameraModel, EventLogModel.camera_id == CameraModel.camera_id)
            .where(EventLogModel.timestamp >= week_start)
            .order_by(desc(EventLogModel.timestamp))
        )
        rows = [["Timestamp", "Person", "Suspect Code", "Category", "Threat Level", "Camera", "Confidence"]]
        for timestamp, name, code, category, threat, camera_name, camera_id, confidence in rows_result.all():
            rows.append([
                timestamp.isoformat() if timestamp else "",
                name or "Unknown",
                code or "",
                category or "",
                threat or "",
                camera_name or camera_id,
                round(float(confidence) * 100, 2) if confidence is not None else "",
            ])
        archive_result = await db.execute(
            select(
                AlertArchiveModel.alert_timestamp,
                AlertArchiveModel.person_name,
                AlertArchiveModel.category,
                AlertArchiveModel.threat_level,
                AlertArchiveModel.camera_id,
                AlertArchiveModel.final_status,
                AlertArchiveModel.suspect_image_path,
                AlertArchiveModel.evidence_path,
            )
            .where(AlertArchiveModel.alert_timestamp >= week_start)
            .order_by(desc(AlertArchiveModel.alert_timestamp))
        )
        rows.append([])
        rows.append(["Archived Alert Timestamp", "Person", "Category", "Threat Level", "Camera", "Final Status", "Suspect Image", "Evidence Image"])
        for timestamp, name, category, threat, camera_id, final_status, suspect_image, evidence_image in archive_result.all():
            rows.append([
                timestamp.isoformat() if timestamp else "",
                name or "Unknown",
                category or "",
                threat or "",
                camera_id,
                final_status,
                suspect_image or "",
                evidence_image or "",
            ])
        return _csv_response("weekly-watchlist-summary.csv", rows)

    counts_result = await db.execute(
        select(
            func.count(AlertModel.id),
            func.count().filter(AlertModel.status == "pending"),
            func.count().filter(AlertModel.status == "acknowledged"),
        ).where(AlertModel.timestamp >= month_start)
    )
    archive_counts_result = await db.execute(
        select(
            func.count(AlertArchiveModel.id),
            func.count().filter(AlertArchiveModel.final_status == "resolved"),
            func.count().filter(AlertArchiveModel.final_status == "false_alarm"),
        ).where(AlertArchiveModel.alert_timestamp >= month_start)
    )
    detections_result = await db.execute(
        select(func.count(EventLogModel.id), func.avg(EventLogModel.confidence)).where(EventLogModel.timestamp >= month_start)
    )
    cameras_result = await db.execute(select(func.count(CameraModel.id), func.count().filter(CameraModel.status.ilike("online"))))
    people_result = await db.execute(select(func.count(PersonModel.id)).where(PersonModel.is_active.is_(True)))

    total, pending, acknowledged = counts_result.one()
    archived_total, resolved, false_alarm = archive_counts_result.one()
    detections, avg_confidence = detections_result.one()
    total_cameras, online_cameras = cameras_result.one()

    rows = [
        ["Metric", "Value"],
        ["Report Window", "Last 30 days"],
        ["Active Alerts", int(total or 0)],
        ["Archived Alerts", int(archived_total or 0)],
        ["Pending Alerts", int(pending or 0)],
        ["Acknowledged Alerts", int(acknowledged or 0)],
        ["Resolved Alerts", int(resolved or 0)],
        ["False Alarms", int(false_alarm or 0)],
        ["Detections", int(detections or 0)],
        ["Average Match Confidence", f"{round(float(avg_confidence or 0) * 100, 2)}%"],
        ["Total Cameras", int(total_cameras or 0)],
        ["Online Cameras", int(online_cameras or 0)],
        ["Active Face Records", int(people_result.scalar() or 0)],
    ]
    return _csv_response("monthly-analytics-pack.csv", rows)


@router.get("/history/alerts")
async def get_report_history(
    limit: int = 100,
    db: AsyncSession = Depends(get_db_session),
    current_user: UserModel = Depends(get_current_user),
):
    del current_user

    result = await db.execute(
        select(AlertArchiveModel)
        .order_by(desc(AlertArchiveModel.archived_at))
        .limit(max(1, min(limit, 500)))
    )
    archives = result.scalars().all()
    return [
        {
            "id": archive.id,
            "original_alert_id": archive.original_alert_id,
            "person_id": archive.person_id,
            "person_name": archive.person_name,
            "camera_id": archive.camera_id,
            "alert_type": archive.alert_type,
            "severity": archive.severity,
            "threat_level": archive.threat_level,
            "category": archive.category,
            "description": archive.description,
            "final_status": archive.final_status,
            "resolved_by": archive.resolved_by,
            "notes": archive.notes,
            "alert_timestamp": archive.alert_timestamp,
            "archived_at": archive.archived_at,
            "suspect_image_url": f"/api/v1/reports/history/{archive.id}/suspect-image" if archive.suspect_image_path else None,
            "evidence_image_url": f"/api/v1/reports/history/{archive.id}/evidence-image" if archive.evidence_path else None,
        }
        for archive in archives
    ]


async def _history_image_response(db: AsyncSession, archive_id: int, field_name: str) -> Response:
    archive = await db.get(AlertArchiveModel, archive_id)
    if not archive:
        raise HTTPException(status_code=404, detail="Archived alert not found")

    path = getattr(archive, field_name)
    if not path:
        raise HTTPException(status_code=404, detail="Archived image not available")

    try:
        with open(path, "rb") as handle:
            file_bytes = handle.read()
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Archived image missing on disk")

    return Response(content=file_bytes, media_type=_detect_image_media_type(file_bytes))


@router.get("/history/{archive_id}/suspect-image")
async def get_history_suspect_image(
    archive_id: int,
    db: AsyncSession = Depends(get_db_session),
    current_user: UserModel = Depends(get_current_user),
):
    del current_user
    return await _history_image_response(db, archive_id, "suspect_image_path")


@router.get("/history/{archive_id}/evidence-image")
async def get_history_evidence_image(
    archive_id: int,
    db: AsyncSession = Depends(get_db_session),
    current_user: UserModel = Depends(get_current_user),
):
    del current_user
    return await _history_image_response(db, archive_id, "evidence_path")
