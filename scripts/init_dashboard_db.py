import asyncio
import os
import sys

# Set up paths
root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.append(os.path.join(root_dir, "services", "dashboard-api"))

from app.database.postgres import init_db

async def main():
    print("Initializing Dashboard API Database Tables...")
    await init_db()
    print("Dashboard API Tables created successfully!")

if __name__ == "__main__":
    # Ensure environment variables are loaded if needed
    # (The dashboard-api's postgres.py might need them)
    os.environ["POSTGRES_URL"] = "postgresql+asyncpg://postgres:admin123@127.0.0.1:5432/ai_surveillance"
    asyncio.run(main())
