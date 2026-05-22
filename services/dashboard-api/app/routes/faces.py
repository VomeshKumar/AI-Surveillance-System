from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Response, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
import logging
import json
import base64
import os
from datetime import datetime

from app.database.postgres import get_db_session
from app.database.models import PersonModel, EventLogModel
from app.schemas.detection_schema import FaceIdentityResponse, FaceLogResponse
from app.routes.auth import get_current_user, require_admin
from app.database.redis_cache import redis_manager
from app.storage.image_store import image_store
import httpx

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/v1/faces",
    tags=["Watchlist Face Management"],
    responses={404: {"description": "Not found"}},
)


def serialize_face_identity(identity: PersonModel) -> FaceIdentityResponse:
    return FaceIdentityResponse(
        id=identity.id,
        name=identity.name,
        category=identity.category,
        registered_by=None, # field deprecated in V2, logic can be updated later if needed
        has_image=bool(identity.image_path),
        is_active=identity.is_active,
        created_at=identity.created_at,
        updated_at=identity.updated_at,
    )


def detect_image_media_type(image_bytes: bytes | None) -> str:
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
    if image_bytes.startswith(b"BM"):
        return "image/bmp"

    return "application/octet-stream"


async def persist_face_image_to_storage(face_id: int, image_bytes: bytes) -> str:
    absolute_path = await image_store.enqueue_write(face_id=face_id, image_bytes=image_bytes)
    return image_store.relative_from_absolute(absolute_path)


# ---------------------------------------------------
# GET ALL WATCHLIST FACES (ALL AUTHORIZED USERS)
# ---------------------------------------------------
@router.get("/", response_model=List[FaceIdentityResponse])
async def get_all_faces(
    category: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db_session),
    current_user=Depends(get_current_user)
):
    try:
        from sqlalchemy import desc, select

        query = select(PersonModel)

        if category:
            query = query.where(
                PersonModel.category == category
            )

        query = query.order_by(desc(PersonModel.updated_at), desc(PersonModel.id))
        query = query.offset(offset).limit(limit)

        result = await db.execute(query)
        identities = result.scalars().all()
        return [serialize_face_identity(identity) for identity in identities]

    except Exception as e:
        logger.error(f"Error fetching watchlist faces: {e}")
        raise HTTPException(
            status_code=500,
            detail="Database error while fetching watchlist identities."
        )


@router.get("/{face_id}/image")
async def get_face_image(
    face_id: int,
    db: AsyncSession = Depends(get_db_session),
    current_user=Depends(get_current_user)
):
    try:
        identity = await db.get(PersonModel, face_id)

        if not identity:
            raise HTTPException(
                status_code=404,
                detail="Face identity not found"
            )

        if identity.image_path:
            full_path = image_store.resolve_relative(identity.image_path)
            if full_path.exists():
                with open(full_path, "rb") as handle:
                    file_bytes = handle.read()
                return Response(content=file_bytes, media_type=detect_image_media_type(file_bytes))
        
        raise HTTPException(
            status_code=404,
            detail="Face image not found"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to fetch face image: {e}")
        raise HTTPException(
            status_code=500,
            detail="Could not fetch face image."
        )


# ---------------------------------------------------
# ENROLL NEW FACE (ADMIN ONLY)
# ---------------------------------------------------
@router.post(
    "/enroll",
    response_model=FaceIdentityResponse,
    status_code=status.HTTP_201_CREATED
)
async def enroll_new_face(
    name: str = Form(...),
    category: str = Form("suspect"),
    image: UploadFile = File(...),
    db: AsyncSession = Depends(get_db_session),
    current_user=Depends(require_admin)
):
    try:
        image_bytes = await image.read()
        if not image_bytes:
            raise HTTPException(
                status_code=400,
                detail="Image file is required"
            )
        import uuid
        new_identity = PersonModel(
            uuid=str(uuid.uuid4()),
            name=name.strip(),
            category=category.strip().lower(),
            is_active=True
        )

        db.add(new_identity)
        await db.commit()
        await db.refresh(new_identity)

        try:
            new_identity.image_path = await persist_face_image_to_storage(new_identity.id, image_bytes)
            await db.commit()
            await db.refresh(new_identity)
        except Exception as exc:
            logger.warning("Image storage write failed for face_id %s: %s", new_identity.id, exc)

        # FAISS SYNC — Direct call to Engine API (no bridge needed)
        try:
            import httpx
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(
                    "http://127.0.0.1:8000/api/v1/faces/upload-suspect",
                    data={"id": new_identity.id, "name": new_identity.name, "category": new_identity.category},
                    files={"file": ("face.jpg", image_bytes, "image/jpeg")},
                )
                if resp.status_code == 200:
                    logger.info(f"FAISS sync: Engine enrolled face_id {new_identity.id}")
                else:
                    logger.warning(f"FAISS sync: Engine returned {resp.status_code}")
        except Exception as exc:
            logger.warning(f"FAISS sync: Engine offline or unreachable: {exc}")

        return serialize_face_identity(new_identity)

    except Exception as e:
        await db.rollback()
        logger.error(f"Failed to enroll face: {e}")
        raise HTTPException(
            status_code=500,
            detail="Could not save identity to database."
        )


# ---------------------------------------------------
# UPDATE WATCHLIST FACE (ADMIN ONLY)
# ---------------------------------------------------
@router.patch("/{face_id}", response_model=FaceIdentityResponse)
async def update_face(
    face_id: int,
    name: str = Form(...),
    category: str = Form("suspect"),
    image: UploadFile | None = File(default=None),
    db: AsyncSession = Depends(get_db_session),
    current_user=Depends(require_admin)
):
    try:
        identity = await db.get(PersonModel, face_id)

        if not identity:
            raise HTTPException(
                status_code=404,
                detail="Face identity not found"
            )

        identity.name = name.strip()
        identity.category = category.strip().lower()

        image_changed = False
        image_bytes = None
        if image is not None:
            image_bytes = await image.read()
            if image_bytes:
                image_changed = True

        await db.commit()
        await db.refresh(identity)

        if image_changed and image_bytes:
            try:
                identity.image_path = await persist_face_image_to_storage(identity.id, image_bytes)
                await db.commit()
                await db.refresh(identity)
            except Exception as exc:
                logger.warning("Image storage update failed for face_id %s: %s", identity.id, exc)
        
        await redis_manager.invalidate_identity(face_id)

        # FAISS SYNC — Direct Engine API call
        if image_changed and image_bytes:
            try:
                import httpx
                async with httpx.AsyncClient(timeout=30.0) as client:
                    resp = await client.post(
                        "http://127.0.0.1:8000/api/v1/faces/upload-suspect",
                        data={"id": identity.id, "name": identity.name, "category": identity.category, "force": "true"},
                        files={"file": ("face.jpg", image_bytes, "image/jpeg")},
                    )
                    if resp.status_code == 200:
                        logger.info(f"FAISS sync: Engine updated face_id {identity.id}")
                    else:
                        logger.warning(f"FAISS sync: Engine returned {resp.status_code}")
            except Exception as exc:
                logger.warning(f"FAISS sync: Engine unreachable: {exc}")

        logger.warning(f"Admin {current_user.username} updated identity '{identity.name}'")

        return serialize_face_identity(identity)

    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"Failed to update face: {e}")
        raise HTTPException(
            status_code=500,
            detail="Could not update identity."
        )


# ---------------------------------------------------
# SOFT DELETE (ADMIN ONLY)
# ---------------------------------------------------
@router.delete("/{face_id}", status_code=status.HTTP_200_OK)
async def deactivate_face(
    face_id: int,
    db: AsyncSession = Depends(get_db_session),
    current_user=Depends(require_admin)
):
    try:
        identity = await db.get(PersonModel, face_id)

        if not identity:
            raise HTTPException(
                status_code=404,
                detail="Face identity not found"
            )

        identity.is_active = False
        await db.commit()
        await redis_manager.invalidate_identity(face_id)

        logger.warning(
            f"Admin {current_user.username} deactivated "
            f"identity '{identity.name}'"
        )

        return {
            "message": "Face identity deactivated successfully",
            "face_id": face_id
        }

    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"Failed to deactivate face: {e}")
        raise HTTPException(
            status_code=500,
            detail="Could not deactivate identity."
        )


@router.patch("/{face_id}/activate", status_code=status.HTTP_200_OK)
async def activate_face(
    face_id: int,
    db: AsyncSession = Depends(get_db_session),
    current_user=Depends(require_admin)
):
    try:
        identity = await db.get(PersonModel, face_id)

        if not identity:
            raise HTTPException(
                status_code=404,
                detail="Face identity not found"
            )

        identity.is_active = True
        await db.commit()
        await redis_manager.invalidate_identity(face_id)

        logger.warning(
            f"Admin {current_user.username} activated "
            f"identity '{identity.name}'"
        )

        return {
            "message": "Face identity activated successfully",
            "face_id": face_id
        }

    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"Failed to activate face: {e}")
        raise HTTPException(
            status_code=500,
            detail="Could not activate identity."
        )


# ---------------------------------------------------
# PERMANENT DELETE (ADMIN ONLY) WITH ARCHIVE & SYNC
# ---------------------------------------------------
@router.delete("/{face_id}/permanent", status_code=status.HTTP_200_OK)
async def permanently_delete_face(
    face_id: int,
    db: AsyncSession = Depends(get_db_session),
    current_user=Depends(require_admin)
):
    try:
        identity = await db.get(PersonModel, face_id)

        if not identity:
            raise HTTPException(
                status_code=404,
                detail="Face identity not found"
            )

        deleted_name = identity.name
        
        # 1. Archive details to 'remove' folder
        import os
        from datetime import datetime
        archive_dir = "d:/Projects/vision ai/storage/archive"
        os.makedirs(archive_dir, exist_ok=True)
        
        timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_name = "".join([c if c.isalnum() else "_" for c in deleted_name])
        base_filename = f"{face_id}_{safe_name}_{timestamp_str}"
        
        # Save JSON details
        details_path = os.path.join(archive_dir, f"{base_filename}_details.json")
        details = {
            "id": identity.id,
            "name": identity.name,
            "category": identity.category,
            "created_at": str(identity.created_at),
            "deleted_at": str(datetime.now()),
            "deleted_by": current_user.username
        }
        with open(details_path, "w", encoding="utf-8") as f:
            json.dump(details, f, indent=4)
            
        # Save image (if exists)
        if identity.image_path:
            source_path = image_store.resolve_relative(identity.image_path)
            if source_path.exists():
                with open(source_path, "rb") as src, open(
                    os.path.join(archive_dir, f"{base_filename}_image.bin"), "wb"
                ) as dst:
                    dst.write(src.read())

        # 2. Clear API Redis Cache
        await redis_manager.invalidate_identity(face_id)
        
        # 3. Synchronize with AI Engine (Delete FAISS Vector via HTTP API)
        try:
            import httpx
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.delete(f"http://127.0.0.1:8000/api/admin/delete-suspect/{face_id}")
                if resp.status_code == 200:
                    logger.info(f"FAISS sync: Engine deleted face_id {face_id}")
                else:
                    logger.warning(f"FAISS sync: Engine delete returned {resp.status_code}")
        except Exception as exc:
            logger.warning(f"FAISS sync: Engine delete unreachable: {exc}")

        await db.delete(identity)
        await db.commit()

        if identity.image_path:
            try:
                file_path = image_store.resolve_relative(identity.image_path)
                if file_path.exists():
                    file_path.unlink()
            except Exception as exc:
                logger.warning("Failed to remove image file for face_id %s: %s", face_id, exc)

        logger.warning(
            f"Admin {current_user.username} permanently deleted "
            f"'{deleted_name}'"
        )

        return {
            "message": "Face identity permanently deleted and archived",
            "face_id": face_id,
            "deleted_name": deleted_name
        }

    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"Permanent delete failed: {e}")
        raise HTTPException(
            status_code=500,
            detail="Could not permanently delete identity."
        )


# ---------------------------------------------------
# DETECTION HISTORY (ALL AUTHORIZED USERS)
# ---------------------------------------------------
@router.get("/{face_id}/history", response_model=List[FaceLogResponse])
async def get_face_detection_history(
    face_id: int,
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db_session),
    current_user=Depends(get_current_user)
):
    try:
        from sqlalchemy import select, desc

        identity = await db.get(PersonModel, face_id)
        if not identity:
            raise HTTPException(
                status_code=404,
                detail="Watchlist identity not found."
            )

        query = (
            select(EventLogModel)
            .where(EventLogModel.person_id == face_id)
            .order_by(desc(EventLogModel.timestamp))
            .limit(limit)
        )

        result = await db.execute(query)
        logs = result.scalars().all()
        
        return [
            FaceLogResponse(
                id=log.id,
                face_id=log.person_id,
                camera_id=log.camera_id,
                confidence=log.confidence,
                timestamp=log.timestamp
            ) for log in logs
        ]

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching history for face {face_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail="Error retrieving detection history."
        )
