from sqlalchemy import text
from app.database.connection import Base, engine
from app.database.models import Person, FaceEmbedding, EventLog

print("Creating AI Engine Database Tables...")
try:
    # Ensure pgvector extension exists
    with engine.connect() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
        conn.commit()
except Exception as e:
    print(f"Error creating vector extension: {e}")

Base.metadata.create_all(bind=engine)
print("Tables created successfully!")
