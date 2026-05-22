from app.database.connection import engine
from sqlalchemy import text

def migrate():
    print("[*] Adding is_caught and caught_at columns to 'people' table...")
    with engine.connect() as conn:
        try:
            conn.execute(text("ALTER TABLE people ADD COLUMN is_caught BOOLEAN DEFAULT FALSE"))
            print("  - Added 'is_caught'")
        except Exception as e:
            print(f"  - 'is_caught' might already exist: {e}")
            
        try:
            conn.execute(text("ALTER TABLE people ADD COLUMN caught_at TIMESTAMP WITHOUT TIME ZONE"))
            print("  - Added 'caught_at'")
        except Exception as e:
            print(f"  - 'caught_at' might already exist: {e}")
        
        conn.commit()
    print("✅ Migration complete!")

if __name__ == "__main__":
    migrate()
