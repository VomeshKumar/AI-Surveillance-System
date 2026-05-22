import cv2
import time
import argparse
import base64
import json
import redis
import numpy as np
import logging
import signal
import sys
import ipaddress
import ssl
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from app.core.config import settings
from app.detection.yunet_detector import YuNetDetector
from app.detection.alignment import align_face
from app.detection.tracker.byte_tracker import ByteTracker
from app.detection.quality_gate import estimate_face_pose_from_landmarks, dynamic_threshold_from_pose

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("CameraWorker")

MATCH_THRESHOLD = 0.40
RECOGNITION_FEEDBACK_MAX_AGE = 2.0
RECOGNITION_FEEDBACK_MIN_IOU = 0.35
TRACKING_PRESENCE_INTERVAL = 0.35


def _bbox_iou(box_a, box_b) -> float:
    ax, ay, aw, ah = [float(v) for v in box_a]
    bx, by, bw, bh = [float(v) for v in box_b]

    ax2, ay2 = ax + aw, ay + ah
    bx2, by2 = bx + bw, by + bh
    inter_w = max(0.0, min(ax2, bx2) - max(ax, bx))
    inter_h = max(0.0, min(ay2, by2) - max(ay, by))
    inter_area = inter_w * inter_h
    if inter_area <= 0:
        return 0.0

    area_a = max(0.0, aw) * max(0.0, ah)
    area_b = max(0.0, bw) * max(0.0, bh)
    union = area_a + area_b - inter_area
    return inter_area / union if union > 0 else 0.0

import threading

class VideoCaptureThreaded:
    def __init__(self, src):
        self.src = src
        self.src_text = str(src)
        parsed_src = urlparse(self.src_text)
        self.is_http_stream = parsed_src.scheme in {"http", "https"}
        self.is_local_camera = self.src_text.isdigit()
        self.fast_grab_skips = 0
        self.cap = None
        self.response = None
        self.opened = False
        self.created_at = time.time()

        self.ret = False
        self.frame = None
        self.last_frame_at = 0.0
        self.consecutive_failures = 0
        self.running = True
        self.lock = threading.Lock()

        if self.is_http_stream:
            self.opened = True
            self.thread = threading.Thread(target=self._update_http_mjpeg, daemon=True)
            self.thread.start()
            return

        # Optimize for RTSP
        import os
        os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = (
            "rtsp_transport;tcp|"  # Reverted back to TCP
            "fflags;nobuffer|"
            "flags;low_delay|"
            "probesize;32|"
            "analyzeduration;0|"
            "max_delay;0|"
            "reorder_queue_size;0"
        )

        if self.is_local_camera:
            idx = int(src)
            # On Windows, try DirectShow first (finds external USB cameras reliably)
            # then fall back to default backend (MSMF) if DSHOW fails
            self.cap = cv2.VideoCapture(idx, cv2.CAP_DSHOW)
            if not self.cap.isOpened():
                logger.warning(f"DSHOW failed for index {idx}, trying default backend...")
                self.cap = cv2.VideoCapture(idx)
        else:
            # RTSP or network stream
            self.cap = cv2.VideoCapture(src, cv2.CAP_FFMPEG)
            
        self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1) # Limit buffer to drop old frames
        self.cap.set(cv2.CAP_PROP_FPS, 30)
        self.opened = self.cap.isOpened()
        
        if self.opened:
            self.ret, self.frame = self.cap.read()
            if self.ret:
                self.last_frame_at = time.time()
            self.thread = threading.Thread(target=self._update, daemon=True)
            self.thread.start()

    def _update_http_mjpeg(self):
        parsed = urlparse(self.src_text)
        stream_urls = [self.src_text]
        try:
            host_ip = ipaddress.ip_address(parsed.hostname or "")
            if parsed.scheme == "https" and host_ip.is_private:
                # Local IP camera apps are usually lower-latency on plain HTTP.
                stream_urls = [self.src_text.replace("https://", "http://", 1), self.src_text]
        except ValueError:
            pass

        headers = {
            "User-Agent": "AI-Surveillance-LowLatency/1.0",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
            "Connection": "keep-alive",
        }
        ssl_context = ssl._create_unverified_context()

        while self.running:
            for stream_url in stream_urls:
                if not self.running:
                    break

                buffer = bytearray()
                try:
                    logger.info(f"Opening HTTP/MJPEG stream {stream_url}")
                    request = Request(stream_url, headers=headers)
                    response = urlopen(
                        request,
                        timeout=5.0,
                        context=ssl_context if stream_url.startswith("https://") else None,
                    )
                    with response:
                        self.response = response
                        status = getattr(response, "status", 200)
                        if status >= 400:
                            raise ConnectionError(f"HTTP {status}")

                        self.opened = True
                        self.consecutive_failures = 0
                        stream_started_at = time.time()

                        while self.running:
                            chunk = response.read(4096)
                            if not chunk:
                                raise ConnectionError("HTTP/MJPEG stream ended")

                            buffer.extend(chunk)
                            if self.last_frame_at == 0 and time.time() - stream_started_at > 8.0:
                                raise TimeoutError("No JPEG frames received from HTTP/MJPEG stream")

                            if len(buffer) > 2_000_000:
                                del buffer[:-512_000]

                            while True:
                                start = buffer.find(b"\xff\xd8")
                                end = buffer.find(b"\xff\xd9", start + 2)
                                if start < 0 or end < 0:
                                    break

                                jpg = bytes(buffer[start:end + 2])
                                del buffer[:end + 2]

                                np_arr = np.frombuffer(jpg, np.uint8)
                                frame = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
                                if frame is None:
                                    self.consecutive_failures += 1
                                    continue

                                with self.lock:
                                    self.ret = True
                                    self.frame = frame
                                    self.last_frame_at = time.time()
                                    self.consecutive_failures = 0
                except Exception as exc:
                    self.opened = False
                    self.ret = False
                    self.consecutive_failures += 1
                    logger.warning(f"HTTP/MJPEG stream error for {stream_url}: {exc}")

            time.sleep(min(0.5 + self.consecutive_failures * 0.25, 5.0))

    def _update(self):
        while self.running and self.cap.isOpened():
            t0 = time.time()
            grabbed = self.cap.grab()
            grab_time = time.time() - t0
            
            if not grabbed:
                self.consecutive_failures += 1
                time.sleep(0.01)
                continue
            
            # For RTSP, a burst of instant grabs usually means buffered packets.
            # Drop a few without decoding, but force periodic retrieve so a fast
            # network stream cannot starve the UI. Never apply this to webcams.
            if not self.is_local_camera and grab_time < 0.003 and self.fast_grab_skips < 4:
                self.fast_grab_skips += 1
                continue

            self.fast_grab_skips = 0
                
            ret, frame = self.cap.retrieve()
            with self.lock:
                self.ret = ret
                if ret:
                    self.frame = frame
                    self.last_frame_at = time.time()
                    self.consecutive_failures = 0
                else:
                    self.consecutive_failures += 1

    def read(self):
        with self.lock:
            if not self.ret or self.frame is None:
                return False, None
            return True, self.frame.copy()

    def release(self):
        self.running = False
        if self.response is not None:
            try:
                self.response.close()
            except Exception:
                pass
        if hasattr(self, 'thread'):
            self.thread.join(timeout=1.0)
        if self.cap is not None:
            self.cap.release()

    def isOpened(self):
        if self.is_http_stream:
            return self.opened
        return bool(self.cap and self.cap.isOpened())

    def waiting_for_first_frame(self, max_wait_seconds: float = 8.0):
        return (
            self.is_http_stream
            and self.last_frame_at == 0
            and time.time() - self.created_at < max_wait_seconds
        )

    def is_stale(self, max_age_seconds: float = 2.0):
        return self.last_frame_at > 0 and time.time() - self.last_frame_at > max_age_seconds

class CameraWorker:
    def __init__(self, cam_id: str, name: str, src: str):
        self.cam_id = cam_id
        self.name = name
        self.src = int(src) if src.isdigit() else src
        self.redis_client = redis.Redis(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            db=settings.REDIS_DB,
            decode_responses=True
        )
        self.detector = YuNetDetector()
        self.tracker = ByteTracker(
            track_thresh=0.4,   # [OPT] Lowered from 0.5 to keep distant/small faces tracked longer
            match_thresh=0.3,   # Min IoU to accept a track-detection match
            max_time_lost=30    # Frames to keep a lost track alive (~2s at 15fps)
        )
        self.last_sent = {}       # track_key -> last send time
        self.recognized = {}   # track_key -> structured recognition payload
        self.last_presence_sent = {}  # track_key -> last tracking presence publish time
        self.last_ui_publish = 0.0
        self.running = True

        # Register signal handlers
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

    def _signal_handler(self, sig, frame):
        logger.info(f"[{self.name}] Received shutdown signal. Stopping...")
        self.running = False

    def _publish_ui_frame(self, frame, quality: int = 48, min_interval: float = 0.066) -> bool:
        now = time.time()
        if now - self.last_ui_publish < min_interval:
            return False

        ui_frame = frame
        if ui_frame.shape[1] > 1280:
            h_ui, w_ui = ui_frame.shape[:2]
            ui_frame = cv2.resize(ui_frame, (1280, int(1280 * h_ui / w_ui)))

        encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), quality]
        ok, buffer = cv2.imencode('.jpg', ui_frame, encode_param)
        if not ok:
            return False

        frame_b64 = base64.b64encode(buffer).decode('utf-8')
        try:
            pipe = self.redis_client.pipeline(transaction=False)
            pipe.set(f"video_feed:{self.cam_id}", frame_b64, ex=2)
            pipe.hset(
                f"video_feed_meta:{self.cam_id}",
                mapping={
                    "published_at": str(now),
                    "quality": str(quality),
                    "width": str(ui_frame.shape[1]),
                    "height": str(ui_frame.shape[0]),
                },
            )
            pipe.expire(f"video_feed_meta:{self.cam_id}", 5)
            pipe.execute()
            self.last_ui_publish = now
        except Exception:
            return False
        return True

    def _fresh_recognition_for_track(self, track_key: str, bbox: list[int], now: float) -> dict | None:
        cached = self.recognized.get(track_key)
        if not isinstance(cached, dict):
            return None

        cached_at = float(cached.get("timestamp", 0) or 0)
        cached_bbox = cached.get("bbox")
        if not cached_bbox or now - cached_at > RECOGNITION_FEEDBACK_MAX_AGE:
            self.recognized.pop(track_key, None)
            return None

        if _bbox_iou(bbox, cached_bbox) < RECOGNITION_FEEDBACK_MIN_IOU:
            self.recognized.pop(track_key, None)
            return None

        return cached

    def _publish_tracking_presence(self, track_id: int, recognition: dict, bbox: list[int], now: float) -> None:
        track_key = f"{self.name}_{track_id}"
        if now - self.last_presence_sent.get(track_key, 0) < TRACKING_PRESENCE_INTERVAL:
            return

        person_id = recognition.get("person_id")
        if person_id is None:
            return

        payload = {
            "person_id": person_id,
            "name": recognition.get("name"),
            "camera_id": self.cam_id,
            "track_id": str(track_id),
            "bbox": bbox,
            "confidence": recognition.get("score"),
            "detected_at": now,
        }
        try:
            self.redis_client.publish("tracking_presence", json.dumps(payload))
            self.last_presence_sent[track_key] = now
        except Exception as exc:
            logger.debug(f"Tracking presence publish failed: {exc}")

    def run(self):
        logger.info(f"Starting Camera Worker for [{self.name}] on src [{self.src}]")
        cap = VideoCaptureThreaded(self.src)

        if not cap.isOpened():
            logger.error(f"Failed to open camera {self.name} (src={self.src}). "
                         f"Check if the device is connected and not used by another app.")
            # Tell the UI this camera is offline
            try:
                self.redis_client.set(f"camera_status:{self.cam_id}", "Offline", ex=60)
            except Exception:
                pass
            return

        last_frame_time = 0
        reconnect_delay = 1.0
        while self.running:
            ret, frame = cap.read()
            if not ret or frame is None:
                if cap.waiting_for_first_frame():
                    time.sleep(0.05)
                    continue

                if self.running:
                    logger.warning(f"Frame grab failed on {self.name}. Reconnecting...")
                    time.sleep(reconnect_delay)
                    cap.release()
                    cap = VideoCaptureThreaded(self.src)
                    reconnect_delay = min(reconnect_delay * 1.5, 5.0)
                continue

            if cap.is_stale():
                if self.running:
                    logger.warning(f"Frame stream stale on {self.name}. Reconnecting...")
                    time.sleep(reconnect_delay)
                    cap.release()
                    cap = VideoCaptureThreaded(self.src)
                    reconnect_delay = min(reconnect_delay * 1.5, 5.0)
                continue

            reconnect_delay = 1.0
                
            # Limit AI processing to ~30 FPS max
            current_time = time.time()
            if current_time - last_frame_time < 0.033:
                time.sleep(0.005)
                continue
            last_frame_time = current_time

            current_time = time.time()

            h, w = frame.shape[:2]
            if w > 1920:
                frame = cv2.resize(frame, (1920, int(1920 * h / w)))

            # Keep an untouched frame for recognition crops and evidence capture.
            raw_frame = frame.copy()

            # If AI processing is falling behind, keep UI close to the live edge.
            self._publish_ui_frame(frame, quality=45, min_interval=0.20)

            # [NEW] Hardware-Aware Backpressure Check
            try:
                stop_ingest = self.redis_client.get('ai:stop_ingest')
                if stop_ingest == '1':
                    # Skip heavy AI processing but keep publishing raw frame for UI
                    self._publish_ui_frame(frame, quality=45, min_interval=0.033)
                    continue
            except Exception:
                pass

            faces = self.detector.detect(raw_frame)
            tracked_faces = self.tracker.update(faces)

            # --- FETCH RECOGNITION FEEDBACK FROM REDIS ---
            tracking_list = []
            feedback_key = f"recognized_tracks:{self.cam_id}"
            feedback_by_track = {}
            stale_feedback_ids = []
            try:
                ext_recognized = self.redis_client.hgetall(feedback_key)
                if ext_recognized:
                    for tid, payload in ext_recognized.items():
                        try:
                            data = json.loads(payload)
                            if current_time - float(data.get("timestamp", 0)) <= RECOGNITION_FEEDBACK_MAX_AGE:
                                feedback_by_track[str(tid)] = data
                            else:
                                stale_feedback_ids.append(str(tid))
                        except Exception:
                            # Ignore legacy/stale plain-name feedback to avoid labeling a recycled track incorrectly.
                            stale_feedback_ids.append(str(tid))
                            continue
                    if stale_feedback_ids:
                        self.redis_client.hdel(feedback_key, *stale_feedback_ids)
            except Exception:
                pass

            for track_id, face in tracked_faces:
                x, y, w_f, h_f = face[:4].astype(int)
                global_track_key = f"{self.name}_{track_id}"
                current_bbox = [int(x), int(y), int(w_f), int(h_f)]
                
                recognition = self._fresh_recognition_for_track(global_track_key, current_bbox, current_time)
                if recognition is None:
                    feedback = feedback_by_track.get(str(track_id))
                    if feedback:
                        feedback_bbox = feedback.get("bbox")
                        if feedback_bbox and _bbox_iou(current_bbox, feedback_bbox) >= RECOGNITION_FEEDBACK_MIN_IOU:
                            recognition = {
                                "person_id": feedback.get("person_id"),
                                "name": feedback.get("name"),
                                "bbox": current_bbox,
                                "score": feedback.get("score"),
                                "timestamp": current_time,
                            }
                            if recognition.get("name") and recognition.get("person_id") is not None:
                                self.recognized[global_track_key] = recognition
                name = recognition.get("name") if recognition else None
                if recognition:
                    recognition["bbox"] = current_bbox
                    recognition["timestamp"] = current_time
                    self._publish_tracking_presence(track_id, recognition, current_bbox, current_time)
                
                # DRAW BOUNDING BOXES AND LABELS FOR LIVE FEED
                color = (0, 255, 0) if name else (0, 0, 255)
                label = f"{name}" if name else f"Scanning..."
                cv2.rectangle(frame, (x, y), (x + w_f, y + h_f), color, 2)
                # Draw label background for better visibility
                text_size = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.7, 2)[0]
                cv2.rectangle(frame, (x, y - text_size[1] - 10), (x + text_size[0], y), color, cv2.FILLED)
                cv2.putText(frame, label, (x, y - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255) if name else (255, 255, 255), 2)

                tracking_list.append({
                    "track_id": int(track_id),
                    "bbox": current_bbox
                })

                # If already recognized, skip sending to queue again
                if name:
                    continue
                    
                # [NEW] Minimum face-size protection
                # Skip recognition for extremely tiny faces to avoid junk embeddings
                if w_f < 20 or h_f < 20:
                    continue

                # [OPT] Increased padding from 0.15 to 0.20 for small-face scaling to 112x112
                px, py = int(w_f * 0.20), int(h_f * 0.20)
                nx, ny = max(0, x - px), max(0, y - py)
                nw = min(frame.shape[1] - nx, w_f + 2 * px)
                nh = min(frame.shape[0] - ny, h_f + 2 * py)

                if nw > 0 and nh > 0:
                    face_crop = raw_frame[ny:ny + nh, nx:nx + nw]
                    lmks = face[4:14].astype(np.float32).reshape((5, 2))
                    shifted_lmks = lmks - np.array([nx, ny], dtype=np.float32)

                    yaw, pitch = estimate_face_pose_from_landmarks(lmks)
                    dynamic_threshold = dynamic_threshold_from_pose(yaw, pitch, MATCH_THRESHOLD)

                    # Skip extreme angles to avoid false positives
                    if dynamic_threshold is None:
                        continue

                    # --- OPTIMIZATION: Faster Sampling for Side Faces ---
                    sampling_rate = 0.1 if abs(yaw) > 20 else 0.2

                    aligned = align_face(face_crop, shifted_lmks)

                    if aligned is not None:
                        last = self.last_sent.get(global_track_key, 0)
                        if current_time - last > sampling_rate:
                            _, crop_buf = cv2.imencode('.jpg', aligned)
                            crop_b64 = base64.b64encode(crop_buf).decode('utf-8')
                            full_encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), 75]
                            _, full_frame_buf = cv2.imencode('.jpg', raw_frame, full_encode_param)
                            full_frame_b64 = base64.b64encode(full_frame_buf).decode('utf-8')

                            payload = {
                                "camera_id": self.cam_id,
                                "track_id": str(track_id),
                                "threshold": str(dynamic_threshold),
                                "image_b64": crop_b64,
                                "full_frame_b64": full_frame_b64,
                                "bbox": json.dumps([int(x), int(y), int(w_f), int(h_f)])
                            }
                            try:
                                self.redis_client.xadd("faces.queue", payload, maxlen=2000)
                                self.last_sent[global_track_key] = current_time
                            except Exception as e:
                                logger.error(f"Redis error: {e}")

            # Cleanup recognized dict — remove tracks no longer visible
            active_keys = {f"{self.name}_{t}" for t, _ in tracked_faces}
            active_track_ids = {str(t) for t, _ in tracked_faces}
            self.recognized = {k: v for k, v in self.recognized.items() if k in active_keys}
            
            # If a track was recognized but now is lost, clean up Redis feedback as well
            # (Wait for auto-expire is fine, but local sync is better)
            
            old_sent = {k: v for k, v in self.last_sent.items() if k in active_keys}
            self.last_sent = old_sent
            self.last_presence_sent = {k: v for k, v in self.last_presence_sent.items() if k in active_keys}
            try:
                stale_track_ids = [tid for tid in feedback_by_track.keys() if tid not in active_track_ids]
                if stale_track_ids:
                    self.redis_client.hdel(feedback_key, *stale_track_ids)
            except Exception:
                pass

            # Publish tracking metadata for local_monitor (no drawing on frame)
            try:
                self.redis_client.set(
                    f"tracking:{self.cam_id}",
                    json.dumps(tracking_list),
                    ex=2
                )
            except Exception:
                pass

            # Publish annotated frame (with bounding boxes + labels) for UI live feed.
            self._publish_ui_frame(frame, quality=48, min_interval=0.066)

        logger.info(f"[{self.name}] Releasing camera resources and closing Redis...")
        cap.release()
        self.redis_client.close()
        logger.info(f"[{self.name}] Shutdown complete.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Headless Camera Worker")
    parser.add_argument("--id", required=True, help="Camera UUID")
    parser.add_argument("--name", required=True, help="Camera Name")
    parser.add_argument("--src", required=True, help="Camera Source (0, RTSP link, etc.)")
    args = parser.parse_args()

    worker = CameraWorker(args.id, args.name, args.src)
    worker.run()
