from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class BackpressureThresholds:
    soft_limit: int = 1000
    hard_limit: int = 3000
    low_confidence_limit: float = 0.75
    preserve_confidence: float = 0.90


@dataclass(frozen=True)
class BackpressureDecision:
    drop: bool
    reason: str
    hard_limited: bool
    preserved_high_confidence: bool


def evaluate_backpressure(
    pending_lag: int,
    confidence: float,
    thresholds: BackpressureThresholds,
) -> BackpressureDecision:
    high_confidence = confidence >= thresholds.preserve_confidence
    if high_confidence:
        return BackpressureDecision(
            drop=False,
            reason="preserve_high_confidence",
            hard_limited=False,
            preserved_high_confidence=True,
        )

    if pending_lag >= thresholds.hard_limit:
        low_conf = confidence < thresholds.low_confidence_limit
        return BackpressureDecision(
            drop=low_conf,
            reason="hard_limit_drop_low_conf" if low_conf else "hard_limit_preserve_mid_conf",
            hard_limited=True,
            preserved_high_confidence=False,
        )

    if pending_lag >= thresholds.soft_limit and confidence < thresholds.low_confidence_limit:
        return BackpressureDecision(
            drop=True,
            reason="soft_limit_drop_low_conf",
            hard_limited=False,
            preserved_high_confidence=False,
        )

    return BackpressureDecision(
        drop=False,
        reason="normal",
        hard_limited=False,
        preserved_high_confidence=False,
    )

