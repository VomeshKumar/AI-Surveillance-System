import logging
import json
import redis
import time
import cv2
import numpy as np
import base64
import signal
import sys
from app.core.config import settings
from app.recognition.ghostfacenet import GhostFaceNet
from app.recognition.faiss_index import WatchlistIndex
from app.database.connection import SessionLocal
from app.database.models import Person
from app.storage.evidence_store import EvidenceStore

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("RecognitionWorker")

class RecognitionWorker:
    """The Brain: Processes aligned face crops from Redis queue and performs matching."""
    def __init__(self):
        logger.info("Initializing Recognition Worker...")
        self.redis_client = redis.Redis(
            host=settings.REDIS_HOST, 
            port=settings.REDIS_PORT, 
            db=settings.REDIS_DB,
            decode_responses=True
        )
        
        # Load heavy AI models once
        self.recognizer = GhostFaceNet()
        self.faiss_idx = WatchlistIndex()
        
        logger.info("Models loaded. Connecting to DB...")
        self.db = SessionLocal()
        self.evidence_store = EvidenceStore()
        
        # Cache for ID -> Name to avoid frequent DB hits
        self.id_to_name = {}
        self._refresh_names()
        self.running = True

        # Register signal handlers
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

    def _signal_handler(self, sig, frame):
        logger.info("Received shutdown signal. Stopping Recognition Worker...")
        self.running = False

    def _refresh_names(self):
        people = self.db.query(Person).all()
        for p in people:
            self.id_to_name[p.id] = p.name

    def run(self):
        logger.info("Recognition Worker is LIVE. Listening to 'faces.queue'...")
        last_id = '$' # Start reading only new messages
        
        # Ensure stream exists
        try:
            self.redis_client.xgroup_create('faces.queue', 'recognizers', id='0', mkstream=True)
        except redis.exceptions.ResponseError:
            pass # Group already exists

        while self.running:
            try:
                # [NEW] Hardware-Aware Backpressure
                q_len = self.redis_client.xlen('faces.queue')
                if q_len > 100:
                    self.redis_client.set('ai:stop_ingest', '1', ex=5)
                else:
                    self.redis_client.set('ai:stop_ingest', '0', ex=5)

                # Read from queue using consumer group to allow scaling later
                streams = self.redis_client.xreadgroup('recognizers', 'worker1', {'faces.queue': '>'}, count=5, block=100)
                if not streams:
                    # Sync FAISS if needed during idle time
                    if self.faiss_idx.check_for_updates():
                        self._refresh_names()
                    continue
                    
                stream_name, messages = streams[0]
                for msg_id, msg_data in messages:
                    if not self.running:
                        break
                    self._process_face(msg_data)
                    self.redis_client.xack('faces.queue', 'recognizers', msg_id)
                    self.redis_client.xdel('faces.queue', msg_id)  # Remove from stream to prevent xlen from growing infinitely
                    
            except redis.RedisError as e:
                if self.running:
                    logger.error(f"Redis error: {e}")
                    time.sleep(1)
            except Exception as e:
                logger.error(f"Error processing face: {e}")

        logger.info("Recognition Worker shutting down gracefully...")
        try:
            self.faiss_idx.save()
        except Exception as e:
            logger.error(f"Error saving FAISS index on shutdown: {e}")
        
        self.db.close()
        self.redis_client.close()
        logger.info("Recognition Worker shutdown complete.")

    def _process_face(self, msg_data: dict):
        camera_id = msg_data.get("camera_id")
        track_id = msg_data.get("track_id")
        threshold = float(msg_data.get("threshold", 0.40))
        img_b64 = msg_data.get("image_b64")
        full_frame_b64 = msg_data.get("full_frame_b64")
        bbox = msg_data.get("bbox", None)  # [x, y, w, h] from camera_worker
        try:
            bbox_value = json.loads(bbox) if isinstance(bbox, str) else bbox
        except Exception:
            bbox_value = None
        
        if not img_b64:
            return

        # Decode Base64 to cv2 image
        img_data = base64.b64decode(img_b64)
        np_arr = np.frombuffer(img_data, np.uint8)
        aligned_face = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)

        if aligned_face is None:
            return

        full_frame = None
        if full_frame_b64:
            try:
                full_frame_data = base64.b64decode(full_frame_b64)
                full_frame_arr = np.frombuffer(full_frame_data, np.uint8)
                full_frame = cv2.imdecode(full_frame_arr, cv2.IMREAD_COLOR)
            except Exception:
                full_frame = None

        # 1. Generate Embedding
        embedding = self.recognizer.get_embedding(aligned_face)
        embedding_batch = np.expand_dims(embedding, axis=0)

        # 2. FAISS Search
        results = self.faiss_idx.search(embedding_batch, k=1, threshold=threshold)
        
        if results and results[0]:
            match = results[0][0]
            person_id = match["person_id"]
            score = match["confidence"]
            person_obj = self.db.query(Person).filter(Person.id == person_id).first()
            matched_name = person_obj.name if person_obj else f"ID:{person_id}"
            suspect_code = person_obj.suspect_code if person_obj else "N/A"
            
            # ── TIER 1: Live Alert (ALWAYS — for monitor green box) ──
            alert_payload = {
                "camera_id": camera_id,
                "track_id": track_id,
                "person_id": person_id,
                "name": matched_name,
                "suspect_code": suspect_code,
                "score": score,
                "bbox": bbox_value
            }
            alert_json = json.dumps(alert_payload)
            self.redis_client.xadd("alerts.global", {"alert": alert_json}, maxlen=1000)
            
            # [NEW] Pub/Sub Relay for external software integration
            self.redis_client.publish("security_alerts", alert_json)
            
            # ── [NEW] RECOGNITION FEEDBACK LOOP ──
            # Tell the Camera Worker to stop sending this track to the queue, and provide the name for UI rendering
            feedback_key = f"recognized_tracks:{camera_id}"
            feedback_payload = json.dumps({
                "person_id": person_id,
                "name": matched_name,
                "bbox": bbox_value,
                "score": round(score, 3),
                "timestamp": time.time(),
            })
            self.redis_client.hset(feedback_key, track_id, feedback_payload)
            self.redis_client.expire(feedback_key, 8)

            tracking_presence_payload = json.dumps({
                "person_id": person_id,
                "name": matched_name,
                "camera_id": camera_id,
                "track_id": track_id,
                "bbox": bbox_value,
                "confidence": round(score, 3),
                "detected_at": time.time(),
            })
            self.redis_client.publish("tracking_presence", tracking_presence_payload)
            
            # ── TIER 2: Evidence + DB Log (COOLDOWN — per Person per Camera) ──
            # Composite key: ensures Camera 1 and Camera 2 have INDEPENDENT cooldowns
            cooldown_key = f"evidence_cooldown:{person_id}:{camera_id}"
            
            if not self.redis_client.exists(cooldown_key):
                # First sighting on this camera (or cooldown expired) — SAVE!
                self.evidence_store.save_evidence(
                    full_frame if full_frame is not None else aligned_face,
                    person_id,
                    matched_name,
                    camera_id,
                    score,
                )
                # Lock this Person+Camera combo for 5 minutes (300 seconds)
                self.redis_client.set(cooldown_key, "1", ex=300)
                logger.info(f"[NEW ALERT] {matched_name} ({score:.2f}) on {camera_id} — Evidence saved!")
            else:
                logger.debug(f"[COOLDOWN] {matched_name} on {camera_id} — skipping evidence (already logged)")
            
            # ── TIER 3: Real-time Location Tracker (ALWAYS updated) ──
            # "Where is this person RIGHT NOW?" — useful for dashboard
            location_data = json.dumps({
                "camera_id": camera_id,
                "score": round(score, 3),
                "timestamp": time.time()
            })
            self.redis_client.set(f"last_seen:{person_id}", location_data, ex=60)

if __name__ == "__main__":
    worker = RecognitionWorker()
    worker.run()
