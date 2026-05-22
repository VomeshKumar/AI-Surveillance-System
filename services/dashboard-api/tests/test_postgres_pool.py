import asyncio
import os
import unittest
from unittest.mock import patch

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from app.database.postgres import get_db_session, get_pooling_diagnostics


class PostgresPoolTests(unittest.IsolatedAsyncioTestCase):
    def test_pgbouncer_diagnostics(self):
        diagnostics = get_pooling_diagnostics()
        self.assertIn("database_port", diagnostics)
        self.assertEqual(diagnostics["pgbouncer_mode"], "transaction")
        # Depending on environment, is_likely_pgbouncer might be True or False,
        # but the expected port should be 5433 by default.
        self.assertEqual(diagnostics["pgbouncer_expected_port"], int(os.getenv("PGBOUNCER_PORT", "5433")))

    @patch("app.database.postgres.DATABASE_URL", "sqlite+aiosqlite:///:memory:")
    async def test_connection_saturation_handling(self):
        """
        Simulate concurrent connection requests to ensure the SQLAlchemy pool
        handles queuing and timeouts without throwing immediate exhaustion errors.
        """
        # Note: In a real environment, this tests the asyncpg pool limits or PgBouncer.
        # Here we mock it with SQLite just to ensure the async_sessionmaker yields sessions
        # concurrently up to the pool size.
        
        async def worker_task(worker_id):
            async for session in get_db_session():
                self.assertIsInstance(session, AsyncSession)
                await session.execute(text("SELECT 1"))
                # Simulate some quick work
                await asyncio.sleep(0.01)
                return True
            return False

        # Simulate 100 concurrent workers trying to get DB sessions
        tasks = [asyncio.create_task(worker_task(i)) for i in range(100)]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for result in results:
            self.assertNotIsInstance(result, Exception, f"Worker raised exception: {result}")
            self.assertTrue(result, "Worker failed to acquire session")


if __name__ == "__main__":
    unittest.main()
