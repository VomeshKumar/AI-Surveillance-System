import redis
from sqlalchemy import create_engine
from app.core.config import settings

def test_redis():
    try:
        r = redis.Redis(host=settings.REDIS_HOST, port=settings.REDIS_PORT, db=settings.REDIS_DB)
        r.ping()
        print("Redis: OK")
        return True
    except Exception as e:
        print(f"Redis: FAILED - {e}")
        return False

def test_db():
    try:
        engine = create_engine(settings.database_url)
        with engine.connect() as conn:
            print("PostgreSQL: OK")
            return True
    except Exception as e:
        print(f"PostgreSQL: FAILED - {e}")
        return False

if __name__ == "__main__":
    test_redis()
    test_db()
