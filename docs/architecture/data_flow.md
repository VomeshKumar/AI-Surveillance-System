# Data Flow Architecture

1. **Ingestion**: `CameraIngestor` (cv2/FFMPEG) reads RTSP -> Writes to `SharedMemoryAllocator` -> Publishes to `frames.meta` Redis stream.
2. **Detection**: `DetectionWorker` reads `frames.meta` -> Zero-copy reads SHM -> `YuNetDetector` -> `ByteTracker` -> Publishes to `detections.meta`.
3. **Recognition**: Reads `detections.meta` -> `GhostFaceNet` embedding -> `FAISS` vector search -> PostgreSQL evidence log.
