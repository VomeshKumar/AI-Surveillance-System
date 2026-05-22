from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class TrackingStartRequest(BaseModel):
    alert_id: int


class TrackingTransitionResponse(BaseModel):
    id: int
    camera_id: str
    camera_name: str | None = None
    camera_location: str | None = None
    confidence: float | None = None
    detected_at: datetime


class TrackingSessionResponse(BaseModel):
    id: int
    alert_id: int | None
    person_id: int
    person_name: str | None = None
    alert_type: str | None = None
    alert_description: str | None = None
    status: str
    current_camera_id: str | None
    current_camera_name: str | None = None
    current_camera_location: str | None = None
    last_detection_at: datetime | None
    started_at: datetime
    ended_at: datetime | None
    ended_reason: str | None
    movement_history: list[TrackingTransitionResponse]
