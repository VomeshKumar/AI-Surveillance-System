from fastapi import APIRouter, UploadFile, File, Form, Depends, Query, Request
from fastapi import HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import or_
from app.database.connection import get_db
from app.database.models import Person, FaceEmbedding, EventLog
from app.detection.yunet_detector import YuNetDetector
from app.detection.alignment import align_face
from app.recognition.ghostfacenet import GhostFaceNet

import cv2
import uuid
import numpy as np
import os
import json
import gc
from datetime import datetime
from typing import Optional

router = APIRouter()


def _generate_suspect_code(person_id: int, dt: datetime) -> str:
    """Generate industry-standard human-readable code: SUS-YYYYMMDD-XXXX"""
    date_str = dt.strftime("%Y%m%d")
    return f"SUS-{date_str}-{person_id:04d}"


# ─────────────────────────────────────────────────────────────────────────────
# POST /upload-suspect
# ─────────────────────────────────────────────────────────────────────────────
@router.post("/upload-suspect")
async def upload_suspect(
    request: Request,
    id: Optional[int] = Form(None),
    name: str = Form(...),
    category: str = Form("suspect"),
    aliases: str = Form(None),         # e.g., "Atul K, AK"
    metadata_json: str = Form(None),   # e.g., '{"height":"5ft9","marks":"Scar"}'
    file: UploadFile = File(...),
    force: bool = Form(False),          # Override deduplication check
    db: Session = Depends(get_db)
):
    contents = await file.read()
    nparr = np.frombuffer(contents, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

    if img is None:
        raise HTTPException(status_code=400, detail="Invalid image file")

    # Detect and align face
    detector = request.app.state.detector
    faces = detector.detect(img)
    if len(faces) == 0:
        raise HTTPException(status_code=400, detail="No faces detected in the image")

    face = faces[0]
    landmarks = face[4:14].astype(np.float32).reshape((5, 2))
    aligned = align_face(img, landmarks)
    if aligned is None:
        raise HTTPException(status_code=400, detail="Face alignment failed")

    # Load recognizer + get initial embedding
    recognizer = request.app.state.recognizer
    initial_emb = recognizer.get_embedding(aligned)

    # ── SMART DEDUPLICATION CHECK ─────────────────────────────────────────
    if not force:
        faiss_idx = request.app.state.faiss_idx
        with request.app.state.faiss_lock:
            faiss_idx.check_for_updates()
            search_results = faiss_idx.search(
                np.expand_dims(initial_emb, axis=0), k=1, threshold=0.85
            )
        if search_results and search_results[0]:
            match = search_results[0][0]
    # ── FETCH OR CREATE PERSON RECORD ──────────────────────────────────────────────
    if id is not None:
        person = db.query(Person).filter(Person.id == id).first()
        if not person:
            raise HTTPException(status_code=404, detail="Person not found in database")
    else:
        # Fallback if called directly without Dashboard
        person = Person(
            name=name,
            category=category,
            uuid=str(uuid.uuid4()),
            aliases=aliases,
            metadata_json=metadata_json,
        )
        db.add(person)
        db.commit()
        db.refresh(person)

    # Auto-generate suspect_code if missing
    if not person.suspect_code:
        person.suspect_code = _generate_suspect_code(person.id, person.created_at)
        db.commit()

    # ── GENERATE AUGMENTED EMBEDDINGS (4 variants) ────────────────────────
    embeddings = []

    # 1. Original
    embeddings.append(initial_emb)

    # 2. Horizontal flip
    embeddings.append(recognizer.get_embedding(cv2.flip(aligned, 1)))

    # 3. Rotated +10°
    h, w = aligned.shape[:2]
    M_pos = cv2.getRotationMatrix2D((w / 2, h / 2), 10, 1.0)
    embeddings.append(recognizer.get_embedding(cv2.warpAffine(aligned, M_pos, (w, h))))

    # 4. Rotated -10°
    M_neg = cv2.getRotationMatrix2D((w / 2, h / 2), -10, 1.0)
    embeddings.append(recognizer.get_embedding(cv2.warpAffine(aligned, M_neg, (w, h))))

    # 5. [NEW] Side-view Simulation (Horizontal compression)
    # This helps when the face is slightly turned
    side_view = cv2.resize(aligned, (int(w * 0.8), h))
    side_view_padded = np.zeros_like(aligned)
    start_x = (w - side_view.shape[1]) // 2
    side_view_padded[:, start_x:start_x + side_view.shape[1]] = side_view
    embeddings.append(recognizer.get_embedding(side_view_padded))

    # 6. [NEW] Extreme Tilt (+15°)
    M_tilt = cv2.getRotationMatrix2D((w / 2, h / 2), 15, 1.0)
    embeddings.append(recognizer.get_embedding(cv2.warpAffine(aligned, M_tilt, (w, h))))

    for emb in embeddings:
        db.add(FaceEmbedding(person_id=person.id, embedding=emb.tolist()))
    db.commit()

    # Sync FAISS
    from app.recognition.faiss_sync import sync_faiss_from_db
    sync_faiss_from_db()
    with request.app.state.faiss_lock:
        request.app.state.faiss_idx.check_for_updates()
    
    # Reload the in-memory index immediately after syncing
    with request.app.state.faiss_lock:
        request.app.state.faiss_idx.check_for_updates()

    return {
        "status": "success",
        "message": f"Successfully enrolled {name}",
        "person": {
            "id": person.id,
            "uuid": person.uuid,
            "suspect_code": person.suspect_code,
            "name": person.name,
            "category": person.category,
            "embeddings_count": len(embeddings)
        }
    }


# ─────────────────────────────────────────────────────────────────────────────
# GET /suspects/search?q=...
# Intelligent multi-mode search:
#   q=SUS-... → Exact suspect_code match
#   q=<text>  → Fuzzy name / alias match
# ─────────────────────────────────────────────────────────────────────────────
@router.get("/suspects/search")
async def search_suspects(
    q: str = Query(..., description="Suspect code (SUS-...), name, or alias"),
    db: Session = Depends(get_db)
):
    query_lower = q.strip().lower()

    # Mode 1: Exact suspect_code match
    if q.upper().startswith("SUS-"):
        person = db.query(Person).filter(Person.suspect_code == q.upper()).first()
        if person:
            return {"mode": "suspect_code", "results": [_person_to_dict(person)]}
        return {"mode": "suspect_code", "results": [], "message": "No match found"}

    # Mode 2: Fuzzy name / alias match
    results = db.query(Person).filter(
        or_(
            Person.name.ilike(f"%{query_lower}%"),
            Person.aliases.ilike(f"%{query_lower}%")
        )
    ).limit(20).all()

    return {
        "mode": "text_search",
        "query": q,
        "count": len(results),
        "results": [_person_to_dict(p) for p in results]
    }


# ─────────────────────────────────────────────────────────────────────────────
# GET /suspects — List all
# ─────────────────────────────────────────────────────────────────────────────
@router.get("/suspects")
async def list_suspects(
    category: Optional[str] = None,
    db: Session = Depends(get_db)
):
    query = db.query(Person)
    if category:
        query = query.filter(Person.category == category)
    people = query.order_by(Person.created_at.desc()).limit(100).all()
    return {"count": len(people), "results": [_person_to_dict(p) for p in people]}


# ─────────────────────────────────────────────────────────────────────────────
# GET /suspects/{suspect_code_or_id}
# ─────────────────────────────────────────────────────────────────────────────
@router.get("/suspects/{identifier}")
async def get_suspect(identifier: str, db: Session = Depends(get_db)):
    # Try suspect_code first
    person = db.query(Person).filter(Person.suspect_code == identifier.upper()).first()
    # Try integer ID
    if not person and identifier.isdigit():
        person = db.query(Person).filter(Person.id == int(identifier)).first()
    # Try UUID
    if not person:
        person = db.query(Person).filter(Person.uuid == identifier).first()
    if not person:
        raise HTTPException(status_code=404, detail="Suspect not found")
    return _person_to_dict(person)


# ─────────────────────────────────────────────────────────────────────────────
# POST /mark-caught/{person_id}
# Marks a suspect as "Caught". After 30 days, auto-cleanup will archive + remove.
# ─────────────────────────────────────────────────────────────────────────────
@router.post("/mark-caught/{person_id}")
async def mark_caught(request: Request, person_id: int, db: Session = Depends(get_db)):
    person = db.query(Person).filter(Person.id == person_id).first()
    if not person:
        raise HTTPException(status_code=404, detail="Suspect not found")

    if person.is_caught:
        return {
            "status": "already_caught",
            "message": f"{person.name} ({person.suspect_code}) was already marked as caught on {person.caught_at}",
        }

    person.is_caught = True
    person.caught_at = datetime.now()
    db.commit()

    # Sync FAISS — remove this person from live scanning immediately
    from app.recognition.faiss_sync import sync_faiss_from_db
    sync_faiss_from_db()
    with request.app.state.faiss_lock:
        request.app.state.faiss_idx.check_for_updates()
    with request.app.state.faiss_lock:
        request.app.state.faiss_idx.check_for_updates()

    return {
        "status": "success",
        "message": f"{person.name} ({person.suspect_code}) marked as CAUGHT. Will be archived after 30 days.",
        "person": {
            "id": person.id,
            "suspect_code": person.suspect_code,
            "name": person.name,
            "caught_at": str(person.caught_at),
            "auto_archive_after": "30 days"
        }
    }


# ─────────────────────────────────────────────────────────────────────────────
# POST /unmark-caught/{person_id}
# In case of mistake — puts suspect back into active scanning
# ─────────────────────────────────────────────────────────────────────────────
@router.post("/unmark-caught/{person_id}")
async def unmark_caught(request: Request, person_id: int, db: Session = Depends(get_db)):
    person = db.query(Person).filter(Person.id == person_id).first()
    if not person:
        raise HTTPException(status_code=404, detail="Suspect not found")

    if not person.is_caught:
        return {"status": "not_caught", "message": f"{person.name} is already in active scanning."}

    person.is_caught = False
    person.caught_at = None
    db.commit()

    from app.recognition.faiss_sync import sync_faiss_from_db
    sync_faiss_from_db()
    with request.app.state.faiss_lock:
        request.app.state.faiss_idx.check_for_updates()

    return {
        "status": "success",
        "message": f"{person.name} ({person.suspect_code}) is back in ACTIVE scanning.",
    }


# ─────────────────────────────────────────────────────────────────────────────
# DELETE /delete-suspect/{person_id}
# ─────────────────────────────────────────────────────────────────────────────
@router.delete("/delete-suspect/{person_id}")
async def delete_suspect(request: Request, person_id: int, db: Session = Depends(get_db)):
    person = db.query(Person).filter(Person.id == person_id).first()
    if not person:
        raise HTTPException(status_code=404, detail="Suspect not found")

    deleted_name = person.name
    deleted_code = person.suspect_code

    # Archive to remove/ folder
    archive_dir = "d:/Projects/vision ai/storage/archive"
    os.makedirs(archive_dir, exist_ok=True)
    timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_name = "".join([c if c.isalnum() else "_" for c in deleted_name])
    archive_path = os.path.join(archive_dir, f"{deleted_code}_{safe_name}_{timestamp_str}.json")

    archive_data = {
        "id": person.id,
        "uuid": person.uuid,
        "suspect_code": person.suspect_code,
        "name": person.name,
        "aliases": person.aliases,
        "category": person.category,
        "metadata_json": person.metadata_json,
        "created_at": str(person.created_at),
        "deleted_at": str(datetime.now())
    }
    with open(archive_path, "w", encoding="utf-8") as f:
        json.dump(archive_data, f, indent=4)

    # Delete from DB
    db.query(FaceEmbedding).filter(FaceEmbedding.person_id == person_id).delete()
    db.query(EventLog).filter(EventLog.person_id == person_id).delete()
    db.delete(person)
    db.commit()

    # Sync FAISS
    from app.recognition.faiss_sync import sync_faiss_from_db
    sync_faiss_from_db()
    with request.app.state.faiss_lock:
        request.app.state.faiss_idx.check_for_updates()

    return {
        "status": "success",
        "message": "Suspect permanently deleted and archived",
        "deleted": {"id": person_id, "suspect_code": deleted_code, "name": deleted_name},
        "archive_path": archive_path
    }


# ─────────────────────────────────────────────────────────────────────────────
# Helper
# ─────────────────────────────────────────────────────────────────────────────
def _person_to_dict(p: Person) -> dict:
    meta = {}
    if p.metadata_json:
        try:
            meta = json.loads(p.metadata_json)
        except Exception:
            meta = {"raw": p.metadata_json}
    return {
        "id": p.id,
        "uuid": p.uuid,
        "suspect_code": p.suspect_code,
        "name": p.name,
        "aliases": p.aliases,
        "category": p.category,
        "metadata": meta,
        "is_caught": p.is_caught or False,
        "caught_at": str(p.caught_at) if p.caught_at else None,
        "created_at": str(p.created_at)
    }
