from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class ConsumerTopology:
    shards: int
    consumers_per_shard: int
    total_consumers: int
    max_allowed_consumers: int


def get_cpu_cores() -> int:
    return max(1, os.cpu_count() or 1)


def calculate_topology(
    requested_shards: int,
    requested_consumers_per_shard: int,
    cpu_cores: int | None = None,
) -> ConsumerTopology:
    cores = cpu_cores or get_cpu_cores()
    max_allowed = max(1, cores * 2)

    shards = max(1, requested_shards)
    per_shard = max(1, requested_consumers_per_shard)
    total = shards * per_shard

    if total <= max_allowed:
        return ConsumerTopology(
            shards=shards,
            consumers_per_shard=per_shard,
            total_consumers=total,
            max_allowed_consumers=max_allowed,
        )

    # Clamp to keep formula true: total = shards * consumers_per_shard
    if shards > max_allowed:
        shards = max_allowed
        per_shard = 1
        total = shards * per_shard
    else:
        per_shard = max(1, max_allowed // shards)
        total = shards * per_shard

    return ConsumerTopology(
        shards=shards,
        consumers_per_shard=per_shard,
        total_consumers=total,
        max_allowed_consumers=max_allowed,
    )

