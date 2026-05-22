# Detailed Integration Implementation Plan

This plan outlines the complete strategy for integrating the AI Surveillance Engine with the external software specification (as detailed in the Word document) **without** breaking the existing frontend or core AI functionality. 

## Proposed Changes

---

### 1. Real-Time Output: WebSocket Bridge
**Goal:** The external software expects real-time alerts via WebSockets (`/api/v1/ws/alerts`), but our system natively outputs to a Redis Stream (`alerts.global`). We must build a bridge.

#### [MODIFY] `app/api/main.py`
- Add a `ConnectionManager` class to handle connected WebSocket clients.
- Add an `asyncio` background task `redis_listener()` that continuously reads the `alerts.global` stream.
- Register this task in the FastAPI `lifespan` context manager so it starts and stops cleanly.
- Create a new endpoint `@app.websocket("/api/v1/ws/alerts")` that accepts connections and broadcasts the alerts received from the background task.

---

### 2. Real-Time Output: Pub/Sub Relay
**Goal:** The external software also expects alerts on a Redis Pub/Sub channel (`security_alerts`).

#### [MODIFY] `app/workers/recognition_worker.py`
- Locate the `_process_face` method where matches are found.
- Directly after the `self.redis_client.xadd("alerts.global", ...)` line, add a new line to publish the exact same JSON payload to the Pub/Sub channel:
  `self.redis_client.publish("security_alerts", alert_json)`
- This fulfills the external contract instantly with zero overhead.

---

### 3. API Versioning (The `/v1/` Alias)
**Goal:** The external software expects API endpoints under `/api/v1/faces`, but our frontend relies on `/api/admin/*`.

#### [MODIFY] `app/api/main.py`
- Include the existing `admin.router` twice.
- Keep the current `app.include_router(admin.router, prefix="/api/admin")`.
- Add an alias: `app.include_router(admin.router, prefix="/api/v1/faces")`.
- This ensures the external system can call `POST /api/v1/faces/upload-suspect` while the existing frontend continues calling `POST /api/admin/upload-suspect` seamlessly.

---

### 4. Hardware-Aware Backpressure
**Goal:** The integration document mandates that the system must signal producers (cameras) to skip frames if the consumer (recognition worker) falls behind, to protect the constrained 8GB RAM hardware.

#### [MODIFY] `app/workers/recognition_worker.py`
- Inside the main `while self.running:` loop, measure the queue depth: `q_len = self.redis_client.xlen('faces.queue')`.
- If `q_len > 100`, set a Redis flag `self.redis_client.set('ai:stop_ingest', '1', ex=5)`.

#### [MODIFY] `app/workers/camera_worker.py`
- Inside the main `while self.running:` loop, right after fetching the frame (`cap.read()`), check the flag: `stop = self.redis_client.get('ai:stop_ingest')`.
- If `stop == '1'`, skip the `YuNetDetector` and `ByteTracker` logic for that frame.
- **Why?** We still call `cap.read()` to drain the camera buffer (preventing video lag), but skipping the heavy AI inference saves CPU and stops pushing new frames to the overloaded Redis queue.

---

## Verification Plan

### Automated/Manual Tests
- **WebSocket Verification:** Run a simple python script connecting to `ws://localhost:8000/api/v1/ws/alerts` to ensure connection acceptance and message streaming.
- **Pub/Sub Verification:** Run `redis-cli subscribe security_alerts` to ensure messages appear.
- **Backpressure Verification:** Manually push 150 dummy items into `faces.queue` via `redis-cli` and observe if the Camera Worker's logs indicate it is skipping AI processing.
- **API Alias Verification:** Ensure `curl POST http://localhost:8000/api/v1/faces/upload-suspect` hits the correct logic.
