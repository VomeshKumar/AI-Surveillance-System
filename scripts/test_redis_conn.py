
import asyncio
from redis.asyncio import Redis

async def test_redis():
    try:
        redis = Redis.from_url("redis://127.0.0.1:6379")
        await redis.ping()
        print("Redis connection successful!")
        await redis.close()
    except Exception as e:
        print(f"Redis connection failed: {e}")

if __name__ == "__main__":
    asyncio.run(test_redis())
