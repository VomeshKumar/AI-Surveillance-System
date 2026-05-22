from prometheus_client import Counter, Histogram, Gauge

# Counters for key events
FACES_DETECTED = Counter('faces_detected_total', 'Total number of faces detected', ['camera_id'])
MATCHES_FOUND = Counter('matches_found_total', 'Total number of watchlist matches', ['camera_id', 'category'])
FRAMES_DROPPED = Counter('frames_dropped_total', 'Frames dropped due to backpressure', ['camera_id'])

# Latency Histograms
DETECTION_LATENCY = Histogram('detection_latency_seconds', 'Time spent in YuNet detection')
RECOGNITION_LATENCY = Histogram('recognition_latency_seconds', 'Time spent in GhostFaceNet and FAISS')
END_TO_END_LATENCY = Histogram('e2e_pipeline_latency_seconds', 'Total time from ingestion to match event')

# System Health Gauges
QUEUE_DEPTH = Gauge('redis_queue_depth', 'Number of pending messages in Redis stream', ['stream_name'])
CAMERA_STATUS = Gauge('camera_status', '1 if camera is online, 0 if offline', ['camera_id'])
