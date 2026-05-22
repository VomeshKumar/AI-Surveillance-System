from __future__ import annotations

import asyncio
import logging
import os

from app.ai.inference_service import InferenceService

logger = logging.getLogger(__name__)


class PlaceholderModel:
    """
    Replace with the actual inference model integration.
    Must return a list aligned with input payloads.
    """

    def infer(self, payloads, device: str = "gpu"):
        results = []
        for payload in payloads:
            response = dict(payload)
            response["inference_device"] = device
            response.setdefault("match", True)
            response.setdefault("confidence", 1.0)
            results.append(response)
        return results


async def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    service = InferenceService(
        model=PlaceholderModel(),
        batch_size=int(os.getenv("INFERENCE_BATCH_SIZE", "4")),
        batch_timeout_ms=int(os.getenv("INFERENCE_BATCH_TIMEOUT_MS", "50")),
    )
    await service.run()


if __name__ == "__main__":
    asyncio.run(main())

