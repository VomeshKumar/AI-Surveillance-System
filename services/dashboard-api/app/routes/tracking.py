from __future__ import annotations

import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import AlertModel, CameraModel, PersonModel, TrackingSessionModel, TrackingTransitionModel, UserModel
from app.database.postgres import get_db_session
from app.database.redis_cache import get_redis
from app.routes.auth import get_current_user
from app.schemas.tracking_schema import TrackingSessionResponse, TrackingStartRequest, TrackingTransitionResponse
from app.websocket.ws_manager import ws_manager

router = APIRouter(prefix="/api/v1/track", tags=["Tracking"])


async def _serialize_session(db: AsyncSession, session: TrackingSessionModel) -> TrackingSessionResponse:
    person = await db.get(PersonModel, session.person_id)
    alert = await db.get(AlertModel, session.alert_id) if session.alert_id else None
    current_camera = None
    if session.current_camera_id:
        camera_result = await db.execute(select(CameraModel).where(CameraModel.camera_id == session.current_camera_id))
        current_camera = camera_result.scalars().first()

    history_result = await db.execute(
        select(TrackingTransitionModel, CameraModel)
        .outerjoin(CameraModel, TrackingTransitionModel.camera_id == CameraModel.camera_id)
        .where(TrackingTransitionModel.session_id == session.id)
        .order_by(desc(TrackingTransitionModel.detected_at))
        .limit(50)
    )
    history = [
        TrackingTransitionResponse(
            id=transition.id,
            camera_id=transition.camera_id,
            camera_name=camera.camera_name if camera else None,
            camera_location=camera.location if camera else None,
            confidence=transition.confidence,
            detected_at=transition.detected_at,
        )
        for transition, camera in history_result.all()
    ]

    return TrackingSessionResponse(
        id=session.id,
        alert_id=session.alert_id,
        person_id=session.person_id,
        person_name=person.name if person else None,
        alert_type=alert.alert_type if alert else None,
        alert_description=alert.description if alert else None,
        status=session.status,
        current_camera_id=session.current_camera_id,
        current_camera_name=current_camera.camera_name if current_camera else None,
        current_camera_location=current_camera.location if current_camera else None,
        last_detection_at=session.last_detection_at,
        started_at=session.started_at,
        ended_at=session.ended_at,
        ended_reason=session.ended_reason,
        movement_history=history,
    )


@router.post("/sessions", response_model=TrackingSessionResponse)
async def start_tracking_session(
    payload: TrackingStartRequest,
    db: AsyncSession = Depends(get_db_session),
    current_user: UserModel = Depends(get_current_user),
):
    alert = await db.get(AlertModel, payload.alert_id)
    if not alert:
        raise HTTPException(status_code=404, detail="Active alert not found")
    if alert.person_id is None:
        raise HTTPException(status_code=400, detail="Alert is not linked to a person")
    if alert.status in {"resolved", "false_alarm"}:
        raise HTTPException(status_code=409, detail="Cannot track a closed alert")

    existing_result = await db.execute(
        select(TrackingSessionModel)
        .where(
            TrackingSessionModel.alert_id == alert.id,
            TrackingSessionModel.status == "active",
        )
        .order_by(desc(TrackingSessionModel.started_at))
        .limit(1)
    )
    session = existing_result.scalars().first()

    if not session:
        session = TrackingSessionModel(
            alert_id=alert.id,
            person_id=alert.person_id,
            status="active",
            current_camera_id=alert.camera_id,  # Initialize with the camera that triggered the alert
            last_detection_at=alert.timestamp,   # Use the alert timestamp as the first detection time
            started_by=current_user.username,
        )
        db.add(session)
        await db.flush()  # Get the session.id assigned by PostgreSQL

        # Now that we have the real session.id, record the initial camera in movement history
        db.add(TrackingTransitionModel(
            session_id=session.id,
            person_id=alert.person_id,
            camera_id=alert.camera_id,
            detected_at=alert.timestamp,
        ))

        await db.commit()
        await db.refresh(session)

    response = await _serialize_session(db, session)
    await ws_manager.broadcast(
        {
            "type": "TRACKING_STARTED",
            "data": {
                "session_id": session.id,
                "alert_id": session.alert_id,
                "person_id": session.person_id,
            },
        }
    )
    return response


@router.get("/sessions/{session_id}", response_model=TrackingSessionResponse)
async def get_tracking_session(
    session_id: int,
    db: AsyncSession = Depends(get_db_session),
    current_user: UserModel = Depends(get_current_user),
):
    del current_user

    session = await db.get(TrackingSessionModel, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Tracking session not found")
    return await _serialize_session(db, session)


@router.get("/alerts/{alert_id}", response_model=TrackingSessionResponse)
async def get_tracking_session_for_alert(
    alert_id: int,
    db: AsyncSession = Depends(get_db_session),
    current_user: UserModel = Depends(get_current_user),
):
    del current_user

    result = await db.execute(
        select(TrackingSessionModel)
        .where(TrackingSessionModel.alert_id == alert_id)
        .order_by(desc(TrackingSessionModel.started_at))
        .limit(1)
    )
    session = result.scalars().first()
    if not session:
        raise HTTPException(status_code=404, detail="Tracking session not found")
    return await _serialize_session(db, session)


@router.get("/people/{person_id}/last-seen")
async def get_person_last_seen(
    person_id: int,
    redis=Depends(get_redis),
    current_user: UserModel = Depends(get_current_user),
):
    del current_user

    if not redis:
        return {"person_id": person_id, "available": False}

    payload = await redis.get(f"last_seen:{person_id}")
    if not payload:
        return {"person_id": person_id, "available": False}

    try:
        data = json.loads(payload)
    except json.JSONDecodeError:
        return {"person_id": person_id, "available": False}

    return {
        "person_id": person_id,
        "available": True,
        "camera_id": data.get("camera_id"),
        "score": data.get("score"),
        "timestamp": datetime.fromtimestamp(float(data.get("timestamp", 0)), tz=timezone.utc),
    }
