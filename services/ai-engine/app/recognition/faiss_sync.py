import logging
from sqlalchemy.orm import Session
from app.database.connection import SessionLocal
from app.database.models import FaceEmbedding
from app.recognition.faiss_index import WatchlistIndex
import numpy as np

logger = logging.getLogger(__name__)

def sync_faiss_from_db():
    """Builds the FAISS index from the PostgreSQL pgvector data."""
    logger.info("Syncing FAISS index from PostgreSQL...")
    db: Session = SessionLocal()
    try:
        from app.database.models import Person
        from sqlalchemy import or_
        
        # Only load faces of ACTIVE (not caught) suspects
        active_person_ids = [
            p.id for p in db.query(Person).filter(
                or_(Person.is_caught == False, Person.is_caught.is_(None))
            ).all()
        ]
        
        if active_person_ids:
            faces = db.query(FaceEmbedding).filter(
                FaceEmbedding.person_id.in_(active_person_ids)
            ).all()
        else:
            faces = []
        index = WatchlistIndex()
        
        # Always clear existing in-memory index
        if index.index.ntotal > 0:
            index.index.reset()
            
        if not faces:
            logger.info("No faces found in DB. Clearing FAISS index on disk.")
            index.save()
            return
            
        embeddings = []
        person_ids = []
        for face in faces:
            if face.embedding is not None:
                # pgvector returns a list/numpy array depending on setup
                emb = np.array(face.embedding, dtype=np.float32)
                embeddings.append(emb)
                person_ids.append(face.person_id)
                
        if embeddings:
            embeddings_np = np.vstack(embeddings)
            person_ids_np = np.array(person_ids, dtype=np.int64)
            
            index.add_faces(embeddings_np, person_ids_np)
            logger.info(f"FAISS sync complete. Loaded {len(embeddings)} vectors.")
    except Exception as e:
        logger.error(f"Failed to sync FAISS from DB: {e}")
    finally:
        db.close()
        
if __name__ == "__main__":
    sync_faiss_from_db()
