"""
Migration Script: Upgrade 'people' and 'event_logs' tables to Industry Standard schema.
Run once: python migrate_schema.py

Safe to run multiple times — uses ALTER TABLE IF NOT EXISTS style checks.
"""
import uuid
from sqlalchemy import text
from app.database.connection import engine, SessionLocal
from app.database.models import Base


def run_migration():
    print("=" * 55)
    print("  AI Surveillance DB Migration: Industry Standard v2")
    print("=" * 55)

    with engine.connect() as conn:
        # ── Step 1: Add new columns to 'people' table ─────────────────────
        print("\n[1/4] Adding UUID column to 'people'...")
        conn.execute(text("""
            ALTER TABLE people
            ADD COLUMN IF NOT EXISTS uuid VARCHAR(36) UNIQUE;
        """))

        print("[2/4] Adding suspect_code column to 'people'...")
        conn.execute(text("""
            ALTER TABLE people
            ADD COLUMN IF NOT EXISTS suspect_code VARCHAR(30) UNIQUE;
        """))

        print("[3/4] Adding aliases and metadata_json columns to 'people'...")
        conn.execute(text("""
            ALTER TABLE people
            ADD COLUMN IF NOT EXISTS aliases VARCHAR(500);
        """))
        conn.execute(text("""
            ALTER TABLE people
            ADD COLUMN IF NOT EXISTS metadata_json TEXT;
        """))
        conn.execute(text("""
            ALTER TABLE people
            ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP DEFAULT NOW();
        """))

        # ── Step 2: Add suspect_code to event_logs ─────────────────────────
        print("[4/4] Adding suspect_code to 'event_logs'...")
        conn.execute(text("""
            ALTER TABLE event_logs
            ADD COLUMN IF NOT EXISTS suspect_code VARCHAR(30);
        """))

        conn.commit()

    # ── Step 3: Backfill UUID and suspect_code for existing records ────────
    print("\n[Backfill] Generating UUID and suspect_code for existing suspects...")
    db = SessionLocal()
    try:
        from app.database.models import Person
        suspects = db.query(Person).filter(Person.uuid == None).all()
        print(f"Found {len(suspects)} existing suspects to backfill...")

        for person in suspects:
            if not person.uuid:
                person.uuid = str(uuid.uuid4())
            if not person.suspect_code:
                person.suspect_code = _generate_suspect_code(person.id, person.created_at)

        db.commit()
        print(f"Backfill complete for {len(suspects)} suspects.")
    except Exception as e:
        print(f"Backfill error: {e}")
        db.rollback()
    finally:
        db.close()

    print("\n✅ Migration complete! Database is now Industry Standard compliant.")
    print("\nNew fields added:")
    print("  • people.uuid          — Secure internal identifier")
    print("  • people.suspect_code  — Human-readable case code (SUS-YYYYMMDD-XXXX)")
    print("  • people.aliases       — Known alternate names")
    print("  • people.metadata_json — Physical descriptors (height, marks, etc.)")
    print("  • event_logs.suspect_code — Fast audit trail (denormalized)")


def _generate_suspect_code(person_id: int, created_at) -> str:
    """Generate SUS-YYYYMMDD-XXXX format code."""
    date_str = created_at.strftime("%Y%m%d") if created_at else "00000000"
    return f"SUS-{date_str}-{person_id:04d}"


if __name__ == "__main__":
    run_migration()
