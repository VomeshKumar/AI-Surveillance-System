# AI Surveillance Engine: Comprehensive Codebase & Architecture Overview

## 1. Introduction
The AI Surveillance Engine is a high-performance, multi-process intelligence layer designed for video ingestion, real-time face detection, and biometric matching. It serves as a standalone backend that processes camera streams, detects faces, extracts embeddings, matches them against a known watchlist, and broadcasts real-time alerts to downstream applications (e.g., React dashboards).

## 2. Key Features
* **Real-time Video Ingestion:** Connects to multiple IP cameras (RTSP/HTTP) or local video files via dedicated camera worker processes.
* **Advanced Face Detection & Tracking:** Utilizes highly optimized ONNX models (e.g., YuNet) for face detection and custom tracking algorithms (e.g., ByteTracker) to follow subjects across frames.
* **Biometric Recognition:** Extracts facial embeddings using state-of-the-art models (like GhostFaceNet/ArcFace) and compares them against a database of suspects.
* **High-Speed Matching:** Employs FAISS (Facebook AI Similarity Search) for sub-millisecond similarity search against thousands of known faces.
* **Real-Time Alerting:** Broadcasts matches and system events instantly using Redis Streams (Pub/Sub) to external applications.
* **Persistent Storage:** Stores event logs, suspect profiles, and vector embeddings in PostgreSQL using the `pgvector` extension for historical querying.
* **Evidence Management:** Captures and stores high-resolution crops of matched faces for auditing and review.

## 3. Technology Stack
* **Language:** Python 3.11+
* **Web Framework:** FastAPI (with Uvicorn)
* **Database:** PostgreSQL (with `pgvector` for vector similarity search) and SQLAlchemy (ORM)
* **Messaging / Pub-Sub:** Redis (Memurai for Windows environments)
* **AI & Computer Vision:**
  * OpenCV (`opencv-python-headless`) for video frame processing.
  * ONNXRuntime (`onnxruntime`) for running deep learning models efficiently.
  * FAISS (`faiss-cpu`) for fast in-memory vector search.
* **Data Validation:** Pydantic & Pydantic Settings
* **Dependency Management:** Poetry

## 4. Architecture Overview
The system employs a distributed, multi-process architecture to decouple heavy computer vision workloads from the web API.

1. **FastAPI Web Server:** Handles HTTP requests (enrolling suspects, querying logs, adding cameras). Runs on the main thread/process.
2. **Camera Workers (`app.workers.camera_worker`):** Independent processes that ingest RTSP/video streams, decode frames, run face detection (YuNet), and crop faces. They push cropped faces and metadata to a Redis queue.
3. **Recognition Workers (`app.workers.recognition_worker`):** Independent processes that consume cropped faces from Redis, extract 512-dimensional vector embeddings using an ONNX recognition model, and perform FAISS similarity matching against the loaded watchlist.
4. **Redis Message Broker:** Acts as the central nervous system connecting workers and broadcasting `matches.alert` to frontends.
5. **PostgreSQL Database:** The ultimate source of truth, holding the `people` table, `watchlist_faces` (vector embeddings), and `event_logs`.

## 5. Directory Structure & Key Components

* **`app/`**: Core application logic.
  * **`api/`**: FastAPI REST endpoints.
    * `routes/admin.py`: Endpoints for managing suspects, uploading faces, and managing evidence.
    * `routes/cameras.py`: Endpoints for camera CRUD operations.
  * **`core/`**: Central configuration (`config.py`) loading variables from `.env`.
  * **`database/`**: SQLAlchemy setup, DB sessions, and table models (`models.py`).
  * **`detection/`**: Computer vision logic.
    * `quality_gate.py`: Ensures captured faces meet minimum resolution and clarity before processing.
    * `tracker/byte_tracker.py`: Tracks identical faces across consecutive video frames to prevent duplicate alerts.
  * **`recognition/`**: Face embedding extraction and FAISS integration (`faiss_sync.py`).
  * **`services/`**: Business logic connecting DB and API.
  * **`storage/`**: Local file management for saving evidence images.
  * **`workers/`**: Long-running background processes (`camera_worker.py`, `recognition_worker.py`).
* **`database/` & `alembic.ini`**: Alembic migration scripts for managing DB schema changes.
* **`data/`**: Local persistent data.
  * **`evidence/`**: Stored images of recognized suspects.
* **`documents/` & `docs/`**: Project documentation (e.g., `INTEGRATION_GUIDE.md`).
* **`scripts/` & Root scripts**: Utility scripts like `run_all.py` (main entry point), `download_yunet.py`, `migrate_schema.py`, and `local_monitor.py`.

## 6. Data & Work Flow

### Flow 1: Enrolling a Suspect
1. External UI sends a `POST /api/admin/upload-suspect` with an image and metadata.
2. FastAPI receives the request and saves the image to the disk.
3. The recognition module extracts the face embedding.
4. Data is saved to PostgreSQL (`people` and `watchlist_faces` tables).
5. FAISS index is instantly rebuilt/updated in-memory to include the new embedding.

### Flow 2: Live Video Recognition (The Pipeline)
1. **Ingestion:** `camera_worker` grabs a frame from an RTSP stream.
2. **Detection:** The worker runs the face detection model. If a face is found, it calculates a bounding box.
3. **Quality & Tracking:** The system checks if the face meets quality standards (size, blurriness) and uses ByteTracker to assign it a unique tracking ID.
4. **Queuing:** The cropped face image is serialized and pushed to a Redis queue.
5. **Extraction:** `recognition_worker` pops the image from Redis and runs the recognition ONNX model to generate a 512D vector.
6. **Matching:** The worker compares this vector against the in-memory FAISS index.
7. **Alerting:** If the similarity score is above the `RECOGNITION_THRESHOLD` (e.g., > 0.40):
   * The event is logged in PostgreSQL (`event_logs`).
   * The evidence image is saved to `data/evidence/`.
   * A JSON alert payload is published to the Redis stream `matches.alert`.
8. **Frontend Update:** External applications listening via WebSockets to Redis receive the alert and immediately display it to the user.

## 7. Integration Summary
External systems interact with the engine via:
* **REST API (`http://localhost:8000`)**: Setup and configuration.
* **Redis Streams (`matches.alert`)**: Real-time events and WebSocket bridging.
* **PostgreSQL direct connection**: For complex analytics and reporting.
* **Static File Serving**: Fetching evidence images from the `data/evidence/` directory.
