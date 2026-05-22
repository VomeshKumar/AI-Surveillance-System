from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

class CameraCreate(BaseModel):
    camera_id: str = Field(..., description="Unique string ID for the camera, e.g., CAM_P01")
    camera_name: str = Field(..., description="Human-readable name")
    location: Optional[str] = None
    status: str = Field(default="Offline")
    rtsp_url: Optional[str] = None

class CameraResponse(BaseModel):
    id: int
    camera_id: str
    camera_name: str
    location: Optional[str] = None
    status: str
    rtsp_url: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
