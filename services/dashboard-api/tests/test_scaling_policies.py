import unittest

from app.consumers.backpressure import BackpressureThresholds, evaluate_backpressure
from app.consumers.scaling import calculate_topology
from app.ingestion.adaptive_sampler import compute_next_skip


class ScalingPoliciesTests(unittest.TestCase):
    def test_consumer_topology_is_clamped_to_cpu_limit(self):
        topology = calculate_topology(
            requested_shards=6,
            requested_consumers_per_shard=4,
            cpu_cores=4,
        )
        self.assertLessEqual(topology.total_consumers, 8)
        self.assertEqual(topology.total_consumers, topology.shards * topology.consumers_per_shard)

    def test_backpressure_preserves_high_confidence(self):
        thresholds = BackpressureThresholds(soft_limit=1000, hard_limit=3000)
        decision = evaluate_backpressure(pending_lag=9000, confidence=0.95, thresholds=thresholds)
        self.assertFalse(decision.drop)
        self.assertTrue(decision.preserved_high_confidence)

    def test_backpressure_drops_low_confidence_on_soft_limit(self):
        thresholds = BackpressureThresholds(soft_limit=1000, hard_limit=3000, low_confidence_limit=0.75)
        decision = evaluate_backpressure(pending_lag=1100, confidence=0.60, thresholds=thresholds)
        self.assertTrue(decision.drop)
        self.assertEqual(decision.reason, "soft_limit_drop_low_conf")

    def test_adaptive_skip_policy(self):
        self.assertEqual(compute_next_skip(3, cpu_percent=80.0, stream_lag=100, min_skip=2, max_skip=10), 4)
        self.assertEqual(compute_next_skip(6, cpu_percent=30.0, stream_lag=100, min_skip=2, max_skip=10), 5)
        self.assertGreaterEqual(
            compute_next_skip(3, cpu_percent=95.0, stream_lag=5000, min_skip=2, max_skip=10),
            8,
        )


if __name__ == "__main__":
    unittest.main()

