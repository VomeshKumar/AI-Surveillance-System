import os
import logging
from urllib.parse import urlparse
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy import insert, text

from app.database.models import Base

logger = logging.getLogger(__name__)


DATABASE_URL = os.getenv(
    "POSTGRES_URL",
    "postgresql+asyncpg://postgres:admin123@127.0.0.1:5432/ai_surveillance"
)


engine = create_async_engine(
    DATABASE_URL,
    echo=False,
    pool_size=int(os.getenv("DB_POOL_SIZE", "20")),
    max_overflow=int(os.getenv("DB_MAX_OVERFLOW", "10")),
    pool_pre_ping=True
)


AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False
)


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


def get_pooling_diagnostics() -> dict:
    parsed = urlparse(DATABASE_URL.replace("+asyncpg", ""))
    port = parsed.port or 5432
    pgbouncer_port = int(os.getenv("PGBOUNCER_PORT", "5433"))
    is_likely_pgbouncer = port == pgbouncer_port
    return {
        "database_host": parsed.hostname or "unknown",
        "database_port": port,
        "pgbouncer_expected_port": pgbouncer_port,
        "pgbouncer_mode": "transaction",
        "is_likely_pgbouncer": is_likely_pgbouncer,
    }


async def init_db():
    try:
        diagnostics = get_pooling_diagnostics()
        if not diagnostics["is_likely_pgbouncer"]:
            logger.warning(
                "POSTGRES_URL does not appear to point to PgBouncer port %s",
                diagnostics["pgbouncer_expected_port"],
            )

        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        logger.info("Database initialized")

    except Exception as e:
        logger.error(f"DB init failed: {e}")
        raise
