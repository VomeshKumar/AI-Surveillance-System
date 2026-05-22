from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone
from threading import Lock
from typing import Dict


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class ConsumerRuntimeState:
    counters: Counter = field(default_factory=Counter)
    last_heartbeat_by_consumer: Dict[str, str] = field(default_factory=dict)
    last_heartbeat_by_stream: Dict[str, str] = field(default_factory=dict)
    _lock: Lock = field(default_factory=Lock)

    def increment(self, key: str, amount: int = 1) -> None:
        with self._lock:
            self.counters[key] += amount

    def heartbeat(self, consumer_name: str, stream_name: str) -> None:
        timestamp = utc_now_iso()
        with self._lock:
            self.last_heartbeat_by_consumer[consumer_name] = timestamp
            self.last_heartbeat_by_stream[stream_name] = timestamp

    def snapshot(self) -> dict:
        with self._lock:
            return {
                "counters": dict(self.counters),
                "last_heartbeat_by_consumer": dict(self.last_heartbeat_by_consumer),
                "last_heartbeat_by_stream": dict(self.last_heartbeat_by_stream),
            }


runtime_state = ConsumerRuntimeState()

