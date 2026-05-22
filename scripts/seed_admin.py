import asyncio
import sys
import pathlib
import bcrypt
from sqlalchemy import select
from app.database.postgres import AsyncSessionLocal, init_db
from app.database.models import UserModel
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
TARGET_USERNAME = "Dev"
TARGET_PASSWORD = "Admin123"

def get_password_hash(password: str) -> str:
    try:
        return pwd_context.hash(password)
    except Exception:
        # Fallback for environments with passlib/bcrypt backend incompatibility.
        return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

async def seed_admin():
    print("Re-seeding admin user...")
    await init_db()
    
    async with AsyncSessionLocal() as db:
        # Remove any existing old/new admin account before creating fresh one.
        result = await db.execute(
            select(UserModel).where(UserModel.username.in_(["admin", TARGET_USERNAME, "Atul"]))
        )
        existing_users = result.scalars().all()

        if existing_users:
            for user in existing_users:
                print(f"User '{user.username}' found. Deleting before recreation...")
                await db.delete(user)
            await db.commit()
            
        new_admin = UserModel(
            username=TARGET_USERNAME,
            full_name="Dev",
            email="dev@aiflow.local",
            hashed_password=get_password_hash(TARGET_PASSWORD),
            role="admin",
            is_active=True
        )
        db.add(new_admin)
        await db.commit()
        print("Admin user created successfully!")
        print(f"Username: {TARGET_USERNAME}")
        print(f"New Password: {TARGET_PASSWORD}")

if __name__ == "__main__":
    asyncio.run(seed_admin())
