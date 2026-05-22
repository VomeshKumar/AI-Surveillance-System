import cv2
import time
import base64
import json
import redis
import numpy as np
import threading

from app.core.config import settings
from app.storage.camera_manager import CameraManager
from app.storage.evidence_store import EvidenceStore

print("==========================================")
print("   Enterprise AI Local Monitor (Popups)")
print("==========================================")

redis_client = redis.Redis(
    host=settings.REDIS_HOST, port=settings.REDIS_PORT,
    db=settings.REDIS_DB, decode_responses=True
)
camera_manager = CameraManager()
evidence_store = EvidenceStore()

# Sticky recognition cache: key = "{cam}_{track_id}" → {name, score, time, saved}
identified_tracks = {}
lock = threading.Lock()

def alert_listener():
    """Background thread: reads recognition matches from alerts.global"""
    # Changed from '$' to '0' to read history (catch alerts sent before monitor started)
    last_id = '0' 
    while True:
        try:
            streams = redis_client.xread({'alerts.global': last_id}, count=20, block=100)
            if streams:
                for msg_id, msg_data in streams[0][1]:
                    last_id = msg_id
                    alert = json.loads(msg_data['alert'])
                    # Force cast to string to prevent type-mismatch bugs
                    key = f"{str(alert['camera_id'])}_{str(alert['track_id'])}"
                    bbox = None
                    if alert.get('bbox'):
                        try:
                            bbox = json.loads(alert['bbox']) if isinstance(alert['bbox'], str) else alert['bbox']
                        except Exception:
                            bbox = None
                    with lock:
                        # Sticky: only update if not already matched, or refresh time
                        identified_tracks[key] = {
                            "name": alert['name'],
                            "score": float(alert['score']),
                            "suspect_code": alert.get('suspect_code', 'N/A'),
                            "bbox": bbox,
                            "time": time.time(),
                            "saved": identified_tracks.get(key, {}).get("saved", False)
                        }
        except Exception:
            time.sleep(1)

alert_thread = threading.Thread(target=alert_listener, daemon=True)
alert_thread.start()

print(">>> Local Monitor LIVE. Press 'q' to quit.")

prev_time = time.time()
fps = 0.0

# Colors
COLOR_TRACK   = (0, 255, 255)  # Yellow — tracking / scanning
COLOR_MATCH   = (0, 255, 0)    # Green  — recognized suspect
COLOR_SKIP    = (0, 0, 255)    # Red    — extreme angle skipped

def draw_label(frame, text, x, y, color):
    """Draw text with a filled background bar for readability."""
    (tw, th), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 0.65, 2)
    cv2.rectangle(frame, (x, y - th - 10), (x + tw + 6, y + 2), color, -1)
    cv2.putText(frame, text, (x + 3, y - 3),
                cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 0, 0), 2)

while True:
    cameras = camera_manager.get_all()
    frames_valid = False
    current_time = time.time()

    for cam in cameras:
        cam_name = cam['name']

        frame_b64 = redis_client.get(f"video_feed:{cam_name}")
        if not frame_b64:
            continue

        frames_valid = True
        img_data = base64.b64decode(frame_b64)
        np_arr   = np.frombuffer(img_data, np.uint8)
        frame    = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
        if frame is None:
            continue

        # Read tracking metadata published by camera_worker
        tracking_raw = redis_client.get(f"tracking:{cam_name}")
        tracking_list = json.loads(tracking_raw) if tracking_raw else []

        with lock:
            # Drawing logic handles persistence — as long as the track is in tracking_list,
            # it will show the last known identity from identified_tracks.
            # We only remove keys if they are REALLY old (e.g., 30 mins) to prevent memory leak.
            to_remove = [k for k, v in identified_tracks.items()
                         if current_time - v["time"] > 1800.0]
            for k in to_remove:
                del identified_tracks[k]

            # --- ANTI-DOUBLE IDENTITY LOGIC ---
            # Ensure each name is only assigned to ONE track (the one with the highest confidence)
            name_to_best_track = {}
            for item in tracking_list:
                track_id = item["track_id"]
                key = f"{str(cam_name)}_{str(track_id)}"
                if key in identified_tracks:
                    data = identified_tracks[key]
                    name = data["name"]
                    score = data["score"]
                    if name not in name_to_best_track or score > name_to_best_track[name]["score"]:
                        name_to_best_track[name] = {"track_id": track_id, "score": score}

            # Draw one box per tracked face — GREEN if recognized as the BEST match, YELLOW if not
            for item in tracking_list:
                track_id = item["track_id"]
                bbox     = item["bbox"]
                x, y, w, h = int(bbox[0]), int(bbox[1]), int(bbox[2]), int(bbox[3])
                key = f"{str(cam_name)}_{str(track_id)}"

                is_best_match = False
                if key in identified_tracks:
                    data = identified_tracks[key]
                    if name_to_best_track.get(data["name"], {}).get("track_id") == track_id:
                        is_best_match = True

                if is_best_match:
                    # --- RECOGNIZED: green box ---
                    data  = identified_tracks[key]
                    name  = data["name"]
                    score = data["score"]
                    code  = data.get("suspect_code", "N/A")
                    label = f"{name} [{code}] ({score:.2f})"

                    cv2.rectangle(frame, (x, y), (x + w, y + h), COLOR_MATCH, 2)
                    draw_label(frame, label, x, y, COLOR_MATCH)

                    if not data["saved"]:
                        print(f"[!] ALERT on {cam_name}: {name} (score={score:.2f})")
                        data["saved"] = True
                else:
                    # --- UNKNOWN or Duplicate: yellow box ---
                    cv2.rectangle(frame, (x, y), (x + w, y + h), COLOR_TRACK, 2)
                    draw_label(frame, f"Scanning... [#{track_id}]", x, y, COLOR_TRACK)

        # FPS + cam label
        now = time.time()
        fps = 0.9 * fps + 0.1 * (1.0 / max(now - prev_time, 1e-6))
        prev_time = now
        cv2.putText(frame, f"Cam: {cam_name} | FPS: {fps:.1f}",
                    (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)

        cv2.imshow(cam_name, frame)

    if not frames_valid:
        time.sleep(0.02)

    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cv2.destroyAllWindows()
