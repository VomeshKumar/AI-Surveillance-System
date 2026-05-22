# ENTERPRISE AI SURVEILLANCE ENGINE
## Technical Architecture & Design Specification
**Current Implementation Context: Live Deployment Phase**

---

### Part I: Architectural Rationale & Self-Countering
Before implementing the current codebase, every design choice was countered against real-world constraints (Windows 11, 8GB RAM, CPU-bound inference).

#### ★ Counter 1: Monolithic vs. Microservices
**Initial**: Use a distributed microservice architecture with gRPC for FAISS and separate processes for each camera.
**Counter**: On Windows, every new Python process consumes ~200MB RAM just for the interpreter and imports. 10 cameras would exhaust 2GB before processing.
**Refinement**: Use a **Threaded Orchestrator** (`run_live_viewer.py`). A single process handles multiple cameras using a threaded producer-consumer model. This keeps the memory footprint under 3GB total.

#### ★ Counter 2: Tracking vs. Continuous Recognition
**Initial**: Run Face Recognition (GhostFaceNet) on every detected face in every frame.
**Counter**: GhostFaceNet takes ~30ms on CPU. At 30 FPS, one camera would consume 90% of a CPU core. 4 cameras would cause massive lag.
**Refinement**: Integrated **MOT (Centroid Tracking)**. We assign a `Track ID` to a face. We run GhostFaceNet **EXACTLY ONCE** per Track ID. As long as the person is being tracked, we only draw the box. This reduces CPU load by >80%.

#### ★ Counter 3: Evidence Spam Prevention
**Initial**: Save a photo every time a suspect is recognized.
**Counter**: If a suspect stands in front of the camera for 1 minute, the system would save 1,800 identical photos, filling the disk and cluttering the database.
**Refinement**: **Track-Based Triggering**. Evidence is saved only when a *new* Track ID is identified as a suspect. A second photo is only taken if the track is lost (e.g., person leaves the room) and a new track is created upon reappearance.

---

### Part II: System Architecture

#### 2.1 The Parallel Pipeline
The system utilizes a multi-threaded execution model to ensure zero-latency stream processing.

- **Thread 1: CLI Listener**: Continuously listens for terminal input (`add`) to allow hot-swapping cameras without stopping the engine.
- **Thread N: Camera Streams**: Each camera (Webcam or RTSP) runs in its own thread, pulling frames into a buffer to prevent blocking.
- **Main Thread: AI Engine**: Iterates through all active camera buffers, running:
    1. **YuNet Detection** (where is the face?)
    2. **Centroid Tracking** (is this the same person from the last frame?)
    3. **GhostFaceNet Recognition** (who is this? - only if new track)
    4. **FAISS Search** (vector lookup in <1ms)
    5. **Evidence Logging** (Save to disk + DB)

#### 2.2 Memory Management (8GB Constraint)
- **Model Loading**: YuNet and GhostFaceNet weights are loaded into RAM once and shared across all camera threads.
- **FAISS HNSW**: Uses an in-process index for sub-millisecond lookups with a footprint of <50MB for thousands of suspects.
- **JSON Persistence**: Camera configurations are stored in `data/config/cameras.json` to avoid database overhead for simple source management.

---

### Part III: Data Design

#### 3.1 Entity Relationship Diagram (ERD)
The system uses PostgreSQL with the `pgvector` extension for biometric storage.

- **People Table**: `id`, `name`, `category`.
- **Watchlist_Faces**: `id`, `person_id`, `embedding` (vector(512)).
- **Event_Logs**: `id`, `camera_id`, `person_id`, `confidence`, `timestamp`, `evidence_path`.

#### 3.2 Evidence Storage Strategy
Snapshots are stored in `data/evidence/` using a sanitized naming convention:
`[SuspectName]_[Timestamp].jpg`
This allows for easy manual auditing while the `event_logs` table provides the programmatic index.

---

### Part IV: Technology Stack

| Layer | Component | Specification |
| :--- | :--- | :--- |
| **Detection** | **YuNet** | ONNX, 320x320 input, lightweight CPU-optimized |
| **Recognition** | **GhostFaceNet** | 512D Embedding, SOTA accuracy on CPU |
| **Biometric Search** | **FAISS** | HNSWFlat index, Cosine Similarity (Inner Product) |
| **Tracking** | **CentroidTracker** | Pure Python/NumPy MOT, IoU/Distance association |
| **Database** | **PostgreSQL** | `pgvector` for 512D vector storage |
| **Messaging/Cache** | **Redis (Memurai)** | Metadata streams and hot-reload triggers |
| **API Framework** | **FastAPI** | Uvicorn-driven, Async/Sync hybrid |

---

### Part V: State & Logic Flow

#### 5.1 Re-Trigger Logic State Machine
1. **Person Enters**: Tracker assigns `TrackID: 101`.
2. **Identification**: AI matches `TrackID: 101` to "Atul".
3. **Capture**: **Evidence Saved** (Atul_Snapshot.jpg). Record added to DB.
4. **Persistence**: Person stays on screen. Green box stays. **No more photos taken.**
5. **Person Leaves**: `TrackID: 101` disappears for >2 seconds. Tracker deletes ID.
6. **Re-Entry**: Person returns. Tracker assigns `TrackID: 105`.
7. **Re-Capture**: AI recognizes Atul again. **New Evidence Saved**.

---

### Part VI: Admin & Deployment Workflows

#### 6.1 Enrollment Workflow
1. **Single**: Upload via Swagger UI (`/api/admin/upload-suspect`).
2. **Bulk**: Run `bulk_enroll.py` to process an entire folder of suspect photos instantly.

#### 6.2 Live Management
The `CLI_Listener` allows the administrator to manage the grid while it's live:
- Type `add` → select `webcam` or `rtsp` → window opens instantly.
- All recognition parameters (thresholds, trackers) are applied to the new stream automatically.

---

### Part VII: Future Scalability
- **Node Replication**: To scale to 50+ cameras, the same codebase can be deployed on additional 8GB nodes, sharing the same central PostgreSQL and Redis cluster.
- **Hardware Acceleration**: If an NVIDIA GPU is added, the ONNX providers can be swapped from `CPUExecutionProvider` to `CUDAExecutionProvider` in one line of code.
