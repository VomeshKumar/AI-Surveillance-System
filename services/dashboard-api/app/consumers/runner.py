from __future__ import annotations

import asyncio
import logging
import os

from redis.asyncio import Redis

from app.consumers.queue_consumer import FaceDetectionConsumer
from app.consumers.scaling import calculate_topology, get_cpu_cores
from app.database.postgres import init_db
from app.database.redis_cache import redis_manager
from app.ingestion.policy_controller import FramePolicyController

logger = logging.getLogger(__name__)


def resolve_stream_names(mode: str, shards: int) -> list[str]:
    shard_streams = [f"face_events_{index}" for index in range(shards)]
    normalized = mode.strip().lower()

    if normalized == "legacy":
        return ["face_events"]
    if normalized == "sharded":
        return shard_streams
    if normalized == "dual":
        return ["face_events", *shard_streams]
    raise ValueError(f"Unsupported STREAM_MODE: {mode}")


async def run_consumers():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    cpu_cores = get_cpu_cores()
    requested_shards = int(os.getenv("STREAM_SHARDS", "6"))
    requested_per_shard = int(os.getenv("CONSUMERS_PER_SHARD", "1"))
    topology = calculate_topology(
        requested_shards=requested_shards,
        requested_consumers_per_shard=requested_per_shard,
        cpu_cores=cpu_cores,
    )

    if (
        topology.shards != requested_shards
        or topology.consumers_per_shard != requested_per_shard
    ):
        logger.warning(
            "Consumer topology clamped requested=%sx%s effective=%sx%s max=%s",
            requested_shards,
            requested_per_shard,
            topology.shards,
            topology.consumers_per_shard,
            topology.max_allowed_consumers,
    )

    await init_db()

    stream_mode = os.getenv("STREAM_MODE", "dual")
    streams = resolve_stream_names(stream_mode, topology.shards)
    redis_url = os.getenv("REDIS_URL", "redis://127.0.0.1:6379/0")
    redis_client = Redis.from_url(redis_url, decode_responses=True)
    await redis_client.ping()
    redis_manager.redis_client = redis_client

    tasks: list[asyncio.Task] = []
    policy_controller: FramePolicyController | None = None
    try:
        policy_controller = FramePolicyController(redis_client=redis_client)
        tasks.append(asyncio.create_task(policy_controller.run_forever(), name="frame-policy-controller"))

        for stream_name in streams:
            workers = (
                topology.consumers_per_shard
                if stream_name.startswith("face_events_")
                else 1
            )
            for worker_idx in range(workers):
                consumer = FaceDetectionConsumer(
                    redis_client=redis_client,
                    stream_name=stream_name,
                    consumer_name=f"{stream_name}_worker_{worker_idx}",
                )
                tasks.append(asyncio.create_task(consumer.start_consuming()))

        logger.info(
            "Started consumers mode=%s streams=%s total_tasks=%s cpu_cores=%s",
            stream_mode,
            ",".join(streams),
            len(tasks),
            cpu_cores,
        )

        try:
            await asyncio.gather(*tasks)
        except asyncio.CancelledError:
            logger.info("Consumer tasks cancelled for shutdown.")
    finally:
        if policy_controller:
            policy_controller.stop()
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        redis_manager.redis_client = None
        await redis_client.aclose()


if __name__ == "__main__":
    try:
        asyncio.run(run_consumers())
    except KeyboardInterrupt:
        logger.info("Consumer process shut down gracefully.")
