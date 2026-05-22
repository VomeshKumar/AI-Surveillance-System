import asyncio
from app.database.postgres import async_session_maker
from app.database.models import AlertModel
from sqlalchemy import select, func

async def check_alerts():
    async with async_session_maker() as session:
        result = await session.execute(select(func.count(AlertModel.id)))
        count = result.scalar()
        print(f"Total alerts in database: {count}")
        
        if count > 0:
            result = await session.execute(select(AlertModel).order_by(AlertModel.id.desc()).limit(1))
            latest = result.scalar()
            print(f"Latest alert: ID={latest.id}, Status={latest.status}")

if __name__ == "__main__":
    asyncio.run(check_alerts())
