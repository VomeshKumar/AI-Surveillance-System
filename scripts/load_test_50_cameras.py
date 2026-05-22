import asyncio
import json
import logging
import os
import random
import time
from uuid import uuid4

import redis.asyncio as redis

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("load_test")


async def simulate_camera_producer(
    camera_id: str,
    redis_client: redis.Redis,
    stream_name: str,
    fps: int,
    duration_sec: int,
):
    delay = 1.0 / fps
    end_time = time.time() + duration_sec
    events_sent = 0

    while time.time() < end_time:
        face_id = random.randint(1, 1000)
        confidence = round(random.uniform(0.5, 0.99), 2)
        
        payload = {
            "face_id": str(face_id),
            "camera_id": camera_id,
            "confidence": confidence,
            "timestamp": time.time(),
        }

        try:
            await redis_client.xadd(
                stream_name,
                {"payload": json.dumps(payload)},
                maxlen=100000
            )
            events_sent += 1
        except Exception as e:
            logger.error(f"Failed to push from {camera_id}: {e}")

        await asyncio.sleep(delay)

    logger.info(f"Camera {camera_id} finished. Sent {events_sent} events.")


async def monitor_lag(redis_client: redis.Redis, stream_name: str, group_name: str, duration_sec: int):
    end_time = time.time() + duration_sec
    while time.time() < end_time:
        try:
            groups = await redis_client.xinfo_groups(stream_name)
            for group in groups:
                if group.get("name") == group_name:
                    lag = group.get("pending", 0)
                    logger.info(f"Stream '{stream_name}' pending lag for group '{group_name}': {lag}")
        except Exception:
            pass  # Ignore errors if stream/group not ready
        await asyncio.sleep(2)


async def main():
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    redis_client = redis.from_url(redis_url, decode_responses=True)

    stream_name = "face_events"
    group_name = "api_group"
    num_cameras = 50
    fps = 10  # Reduced FPS for detection events vs raw video
    duration = 60  # Run for 60 seconds (for manual testing)

    logger.info(f"Starting load test with {num_cameras} cameras at {fps} fps for {duration} seconds.")
    logger.info("This will test ingestion, consumer scaling, and backpressure.")

    tasks = []
    
    # 1. Start lag monitor
    tasks.append(asyncio.create_task(monitor_lag(redis_client, stream_name, group_name, duration)))

    # 2. Start cameras
    for i in range(1, num_cameras + 1):
        camera_id = f"camera_{i:03d}"
        task = asyncio.create_task(
            simulate_camera_producer(camera_id, redis_client, stream_name, fps, duration)
        )
        tasks.append(task)

    await asyncio.gather(*tasks)
    logger.info("Load test completed.")


if __name__ == "__main__":
    asyncio.run(main())
