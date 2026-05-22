import cv2
import os
import time
import logging
from datetime import datetime
from app.database.connection import SessionLocal
from app.database.models import EventLog

logger = logging.getLogger(__name__)

class EvidenceStore:
    """Handles saving evidence frames and logging events to the database."""
    
    def __init__(self, base_path: str = "d:/Projects/vision ai/storage/evidence"):
        self.base_path = base_path
        os.makedirs(self.base_path, exist_ok=True)
        
    def save_evidence(self, frame, person_id: int, person_name: str, camera_id: str, confidence: float) -> str:
        """
        Saves a JPEG evidence frame and logs the event to PostgreSQL.
        The caller may pass a full camera frame or a processed crop.
        Returns the path to the saved image.
        """
        timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        # Sanitize name to avoid invalid filename characters
        safe_name = "".join([c for c in person_name if c.isalpha() or c.isdigit() or c==' ']).rstrip()
        safe_name = safe_name.replace(" ", "_")
        
        filename = f"{safe_name}_{timestamp_str}.jpg"
        filepath = os.path.join(self.base_path, filename)
        
        # Save image to disk
        try:
            cv2.imwrite(filepath, frame)
        except Exception as e:
            logger.error(f"Failed to save evidence image: {e}")
            return ""
            
        # Log to Database
        db = SessionLocal()
        try:
            log_entry = EventLog(
                camera_id=camera_id,
                person_id=person_id,
                confidence=confidence,
                evidence_path=filepath
            )
            db.add(log_entry)
            db.commit()
            logger.info(f"Evidence logged for person {person_id} at {filepath}")
        except Exception as e:
            logger.error(f"Failed to log evidence to database: {e}")
            db.rollback()
        finally:
            db.close()
            
        return filepath
