from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


# ==========================================
# Authentication Schemas
# ==========================================
class TokenResponse(BaseModel):
    """JWT response after successful login."""
    access_token: str
    token_type: str
    name: str


# ==========================================
# Alert Management Schemas
# ==========================================
class AlertUpdateRequest(BaseModel):
    """Frontend payload to update alert status."""
    status: str = Field(
        ...,
        description="Must be 'acknowledged', 'resolved', or 'false_alarm'"
    )
    notes: Optional[str] = Field(
        None,
        description="Optional resolution notes by the guard"
    )


class AlertResponse(BaseModel):
    """Alert response sent to dashboard."""
    id: int
    alert_type: str
    camera_id: str
    person_id: Optional[int] = None
    person_name: Optional[str] = None
    severity: Optional[str] = None
    threat_level: Optional[str] = None
    category: Optional[str] = None
    description: Optional[str] = None
    status: str
    resolved_by: Optional[str] = None
    notes: Optional[str] = None
    suspect_image_url: Optional[str] = None
    evidence_image_url: Optional[str] = None
    timestamp: datetime

    class Config:
        from_attributes = True


# ==========================================
# Watchlist Face Schemas
# ==========================================
class FaceIdentityCreate(BaseModel):
    """
    Payload to register a face identity
    into the live watchlist table.
    """
    name: str = Field(..., max_length=100)
    category: str = Field(default="suspect", max_length=50)


class FaceIdentityResponse(BaseModel):
    """Watchlist master profile response."""
    id: int
    name: str
    category: str
    registered_by: Optional[str] = None
    has_image: bool = False
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ==========================================
# Face Detection Logs
# ==========================================
class FaceLogResponse(BaseModel):
    """Single historical detection event."""
    id: int
    face_id: int
    camera_id: str
    confidence: float
    timestamp: datetime

    class Config:
        from_attributes = True
