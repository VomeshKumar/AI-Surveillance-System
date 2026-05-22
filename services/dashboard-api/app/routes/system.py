import json
import logging
import secrets
import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from app.routes.auth import require_admin
from app.database.models import UserModel
from app.database.redis_cache import get_redis
import redis.asyncio as aioredis

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/system", tags=["System Control"])

class ShutdownRequest(BaseModel):
    token: str

@router.post("/shutdown-token")
async def get_shutdown_token(
    current_user: UserModel = Depends(require_admin),
    redis: aioredis.Redis = Depends(get_redis)
):
    if not redis:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Redis is not available, cannot issue shutdown token."
        )

    # Generate a secure short-lived token
    token = secrets.token_hex(16)
    
    # Store token in Redis with 30 second expiration
    key = f"system:shutdown_token:{token}"
    await redis.setex(key, 30, current_user.username)
    
    logger.info(f"Shutdown token issued to admin {current_user.username}")
    
    return {"token": token, "expires_in_seconds": 30}


class RestartRequest(BaseModel):
    token: str

@router.post("/restart-token")
async def get_restart_token(
    current_user: UserModel = Depends(require_admin),
    redis: aioredis.Redis = Depends(get_redis)
):
    if not redis:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Redis is not available, cannot issue restart token."
        )

    token = secrets.token_hex(16)
    key = f"system:restart_token:{token}"
    await redis.setex(key, 30, current_user.username)
    
    logger.info(f"Restart token issued to admin {current_user.username}")
    
    return {"token": token, "expires_in_seconds": 30}


@router.post("/shutdown", status_code=status.HTTP_202_ACCEPTED)
async def initiate_shutdown(
    request: ShutdownRequest,
    current_user: UserModel = Depends(require_admin),
    redis: aioredis.Redis = Depends(get_redis)
):
    if not redis:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Redis is not available, cannot initiate shutdown."
        )

    # Validate token
    key = f"system:shutdown_token:{request.token}"
    token_user = await redis.get(key)
    
    if not token_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired shutdown token."
        )
        
    if token_user != current_user.username:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Token does not belong to the current user."
        )

    # Delete token so it can't be reused
    await redis.delete(key)

    # Check lock to prevent multiple commands
    lock_key = "system:control_lock"
    is_locked = await redis.set(lock_key, "locked", nx=True, ex=60)
    if not is_locked:
        return {"message": "Shutdown already in progress."}

    # Publish shutdown command to orchestrator
    message = json.dumps({
        "command": "shutdown",
        "requested_by": current_user.username,
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat()
    })
    
    await redis.publish("system_control", message)
    
    logger.critical(f"System shutdown initiated by UI (User: {current_user.username})")

    return {"message": "Shutdown command accepted. System will halt shortly."}


@router.post("/restart", status_code=status.HTTP_202_ACCEPTED)
async def initiate_restart(
    request: RestartRequest,
    current_user: UserModel = Depends(require_admin),
    redis: aioredis.Redis = Depends(get_redis)
):
    if not redis:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Redis is not available, cannot initiate restart."
        )

    # Validate token
    key = f"system:restart_token:{request.token}"
    token_user = await redis.get(key)
    
    if not token_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired restart token."
        )
        
    if token_user != current_user.username:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Token does not belong to the current user."
        )

    # Delete token so it can't be reused
    await redis.delete(key)

    # Check lock to prevent multiple control commands
    lock_key = "system:control_lock"
    is_locked = await redis.set(lock_key, "locked", nx=True, ex=60)
    if not is_locked:
        return {"message": "Control command already in progress."}

    # Publish restart command to orchestrator
    message = json.dumps({
        "command": "restart",
        "requested_by": current_user.username,
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat()
    })
    
    await redis.publish("system_control", message)
    
    logger.critical(f"System restart initiated by UI (User: {current_user.username})")

    return {"message": "Restart command accepted. System will restart shortly."}
