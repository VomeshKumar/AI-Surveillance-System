import json
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.database.models import CameraModel
from app.database.postgres import get_db_session
from app.schemas.camera_schema import CameraCreate, CameraResponse
from app.routes.auth import get_current_user
from app.database.redis_cache import get_redis
from app.streaming.redis_stream_hub import stream_hub
import redis.asyncio as aioredis

router = APIRouter(prefix="/api/v1/cameras", tags=["cameras"])

@router.get("/stream")
async def stream_camera(
    camera_id: str,
    db: AsyncSession = Depends(get_db_session),
    redis: aioredis.Redis = Depends(get_redis)
):
    if not redis:
        raise HTTPException(status_code=503, detail="Redis unavailable")
        
    result = await db.execute(select(CameraModel).where(CameraModel.camera_id == camera_id))
    camera = result.scalars().first()
    if not camera:
        raise HTTPException(status_code=404, detail="Camera not found")

    return StreamingResponse(
        stream_hub.frame_generator(redis, camera.camera_id),
        media_type="multipart/x-mixed-replace; boundary=frame",
        headers={
            "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
            "Pragma": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


@router.get("/stream/diagnostics")
async def stream_diagnostics(
    current_user=Depends(get_current_user),
):
    return {"streams": stream_hub.diagnostics()}

@router.get("", response_model=list[CameraResponse])
async def get_cameras(
    db: AsyncSession = Depends(get_db_session),
    current_user=Depends(get_current_user),
):
    result = await db.execute(select(CameraModel).order_by(CameraModel.id))
    cameras = result.scalars().all()
    return cameras

@router.post("", response_model=CameraResponse, status_code=status.HTTP_201_CREATED)
async def create_camera(
    camera_in: CameraCreate,
    db: AsyncSession = Depends(get_db_session),
    current_user=Depends(get_current_user),
    redis: aioredis.Redis = Depends(get_redis),
):
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators can add cameras.",
        )

    # Check if camera exists
    result = await db.execute(select(CameraModel).where(CameraModel.camera_id == camera_in.camera_id))
    if result.scalars().first():
        raise HTTPException(status_code=400, detail="Camera ID already exists.")

    new_camera = CameraModel(**camera_in.model_dump())
    db.add(new_camera)
    await db.commit()
    await db.refresh(new_camera)

    # Also add to redis set so adaptive sampler picks it up immediately
    try:
        if redis:
            await redis.sadd("ai:cameras", new_camera.camera_id)
            # Publish to AI Engine to start worker
            await redis.publish("system_control", json.dumps({
                "command": "start_camera",
                "camera_id": new_camera.camera_id,
                "camera_name": new_camera.camera_name,
                "rtsp_url": new_camera.rtsp_url or "0"
            }))
    except Exception:
        pass

    return new_camera

@router.delete("", status_code=status.HTTP_204_NO_CONTENT)
async def delete_camera(
    camera_id: str,
    db: AsyncSession = Depends(get_db_session),
    current_user=Depends(get_current_user),
    redis: aioredis.Redis = Depends(get_redis),
):
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators can delete cameras.",
        )

    result = await db.execute(select(CameraModel).where(CameraModel.camera_id == camera_id))
    camera = result.scalars().first()
    if not camera:
        raise HTTPException(status_code=404, detail="Camera not found.")

    await db.delete(camera)
    await db.commit()

    try:
        if redis:
            await redis.srem("ai:cameras", camera_id)
            await redis.delete(f"ai:camera_policy:{camera_id}")
            # Publish to AI Engine to stop worker
            await redis.publish("system_control", json.dumps({
                "command": "stop_camera",
                "camera_id": camera_id
            }))
    except Exception:
        pass

    return None
