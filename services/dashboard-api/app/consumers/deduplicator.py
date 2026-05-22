from __future__ import annotations

import time


class DetectionDeduplicator:
    def __init__(self, window_seconds: float = 2.0):
        self.window_seconds = window_seconds
        self._seen: dict[tuple[int, str], float] = {}

    def is_duplicate(self, face_id: int, camera_id: str) -> bool:
        key = (face_id, camera_id)
        now = time.monotonic()
        seen_at = self._seen.get(key)
        if seen_at is not None and now - seen_at < self.window_seconds:
            return True

        self._seen[key] = now
        self._cleanup(now)
        return False

    def _cleanup(self, now: float) -> None:
        expiry = self.window_seconds * 5
        self._seen = {
            key: timestamp
            for key, timestamp in self._seen.items()
            if now - timestamp < expiry
        }

