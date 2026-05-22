from __future__ import annotations

import json
import subprocess
import time


class GPUMemoryGuard:
    def __init__(
        self,
        soft_limit_bytes: int = int(3.2 * 1024 * 1024 * 1024),
        hysteresis_seconds: int = 30,
    ):
        self.soft_limit_bytes = soft_limit_bytes
        self.hysteresis_seconds = hysteresis_seconds
        self._fallback_since: float | None = None

    def _read_rocm_memory_bytes(self) -> int:
        result = subprocess.run(
            ["rocm-smi", "--showmeminfo", "vram", "--json"],
            capture_output=True,
            text=True,
            timeout=2,
            check=False,
        )
        if result.returncode != 0:
            return 0
        payload = json.loads(result.stdout or "{}")
        card = payload.get("card0", {})
        return int(card.get("VRAM Total Used Memory (B)", 0))

    def get_gpu_usage_bytes(self) -> int:
        try:
            return self._read_rocm_memory_bytes()
        except Exception:
            return 0

    def select_device(self, now: float | None = None) -> str:
        current_time = now if now is not None else time.monotonic()
        usage = self.get_gpu_usage_bytes()

        if usage > self.soft_limit_bytes:
            if self._fallback_since is None:
                self._fallback_since = current_time
            return "cpu"

        # Hysteresis: stay on CPU briefly before restoring GPU
        if self._fallback_since is not None:
            if current_time - self._fallback_since < self.hysteresis_seconds:
                return "cpu"
            self._fallback_since = None

        return "gpu"

