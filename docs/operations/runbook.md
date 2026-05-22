# Operations Runbook

## High Latency / Lag
1. Use `scripts/profile.py` to identify bottlenecks in Python functions.
2. Check `backpressure.py` logs to see if frames are being dropped.

## Memory Leaks
1. Run `scripts/memcheck.py` to monitor RSS memory usage over time.
2. Verify that `shm_manager.cleanup_orphans()` is functioning correctly.

## FAISS Corruption
1. Run `python -m app.recognition.faiss_sync` to rebuild the index from PostgreSQL.
