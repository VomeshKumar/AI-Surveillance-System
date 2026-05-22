from fastapi import APIRouter
from app.core.config import settings

router = APIRouter()

@router.get("/")
def get_health():
    return {"status": "ok", "node_id": settings.NODE_ID}
    
@router.get("/metrics")
def get_metrics():
    # Will integrate with Prometheus in Phase 3
    return {"fps": settings.SAMPLING_FPS, "status": "healthy"}
