from fastapi import APIRouter

router = APIRouter()

@router.post("/assign-cameras")
def assign_cameras(camera_urls: list[str]):
    # Assign cameras to this node
    return {"status": "success", "count": len(camera_urls)}
