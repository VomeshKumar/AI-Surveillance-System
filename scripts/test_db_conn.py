
import asyncio
import asyncpg
import sys

async def test_conn():
    try:
        conn = await asyncpg.connect(user='postgres', password='Atul', database='ai_surveillance', host='127.0.0.1')
        print("Connection successful!")
        await conn.close()
    except Exception as e:
        print(f"Connection failed: {e}")

if __name__ == "__main__":
    asyncio.run(test_conn())
