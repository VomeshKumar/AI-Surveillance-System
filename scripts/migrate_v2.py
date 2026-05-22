import os
import uuid
import psycopg2
from psycopg2.extras import DictCursor

DATABASE_URL = "postgresql://postgres:Atul@127.0.0.1:5432/ai_surveillance"

SQL_PHASE_1 = """
BEGIN;

CREATE TABLE IF NOT EXISTS people_v2 (
    id SERIAL PRIMARY KEY,
    uuid VARCHAR(36) UNIQUE NOT NULL,
    suspect_code VARCHAR(30) UNIQUE,
    name VARCHAR(100) NOT NULL,
    aliases VARCHAR(255),
    category VARCHAR(50) DEFAULT 'suspect',
    threat_level VARCHAR(20),
    crime_type VARCHAR(100),
    metadata_json TEXT,
    image_path VARCHAR(255),
    is_active BOOLEAN DEFAULT TRUE,
    is_caught BOOLEAN DEFAULT FALSE,
    caught_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS face_embeddings (
    id SERIAL PRIMARY KEY,
    person_id INTEGER NOT NULL REFERENCES people_v2(id) ON DELETE CASCADE,
    embedding vector(512),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS event_logs_v2 (
    id SERIAL PRIMARY KEY,
    person_id INTEGER REFERENCES people_v2(id) ON DELETE SET NULL,
    camera_id VARCHAR(50) NOT NULL REFERENCES cameras(camera_id) ON DELETE CASCADE,
    confidence FLOAT,
    evidence_path VARCHAR(255),
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_event_logs_v2_person ON event_logs_v2(person_id);
CREATE INDEX IF NOT EXISTS idx_event_logs_v2_camera ON event_logs_v2(camera_id);
CREATE INDEX IF NOT EXISTS idx_event_logs_v2_time ON event_logs_v2(timestamp DESC);

COMMIT;
"""

def main():
    print("Connecting to DB...")
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = False
    cur = conn.cursor(cursor_factory=DictCursor)

    try:
        print("Executing Phase 1: Creating V2 Schema...")
        cur.execute(SQL_PHASE_1)
        conn.commit()
        print("Phase 1 Complete.")

        print("Executing Phase 2: Migrating Data...")
        
        cur.execute("SELECT * FROM face_identities")
        face_idents = cur.fetchall()
        
        for fi in face_idents:
            fi_id = fi['id']
            # Check if exists in people_v2
            cur.execute("SELECT id FROM people_v2 WHERE id = %s", (fi_id,))
            if cur.fetchone():
                continue # Already migrated
            
            # Fetch from Engine 'people' if exists to grab UUID, is_caught, etc.
            cur.execute("SELECT uuid, suspect_code, aliases, metadata_json, is_caught, caught_at FROM people WHERE id = %s", (fi_id,))
            engine_person = cur.fetchone()
            
            p_uuid = engine_person['uuid'] if engine_person else str(uuid.uuid4())
            p_code = engine_person['suspect_code'] if engine_person else None
            p_aliases = engine_person['aliases'] if engine_person else None
            p_meta = engine_person['metadata_json'] if engine_person else None
            p_caught = engine_person['is_caught'] if engine_person else False
            p_caught_at = engine_person['caught_at'] if engine_person else None
            
            # Write Blobs to Disk (if image exists and image_path is None)
            img_path = fi.get('image_path')
            
            # Use dictionary access for byte array from psycopg2
            img_data = fi.get('image')
            if not img_path and img_data is not None:
                img_path = f"d:/vision ai/storage/images/{fi_id}.jpg"
                os.makedirs("d:/vision ai/storage/images", exist_ok=True)
                with open(img_path, 'wb') as f:
                    f.write(bytes(img_data))

            # Insert into people_v2 (preserving ID)
            cur.execute("""
                INSERT INTO people_v2 
                (id, uuid, suspect_code, name, aliases, category, threat_level, crime_type, metadata_json, image_path, is_active, is_caught, caught_at, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                fi_id, p_uuid, p_code, fi['name'], p_aliases, fi.get('category', 'suspect'), 
                fi.get('threat_level'), fi.get('crime_type'), p_meta, img_path, 
                fi.get('is_active', True), p_caught, p_caught_at, 
                fi.get('created_at'), fi.get('updated_at')
            ))
            
            # Migrate WatchlistFace for this person to face_embeddings
            cur.execute("SELECT embedding, created_at FROM watchlist_faces WHERE person_id = %s", (fi_id,))
            embeddings = cur.fetchall()
            for emb in embeddings:
                # pgvector parsing
                cur.execute("""
                    INSERT INTO face_embeddings (person_id, embedding, created_at)
                    VALUES (%s, %s, %s)
                """, (fi_id, emb['embedding'], emb['created_at']))

        print("People and Embeddings Migrated.")

        cur.execute("SELECT * FROM event_logs")
        events = cur.fetchall()
        for ev in events:
            cam_uuid = ev['camera_id']
            cur.execute("SELECT camera_id FROM cameras WHERE camera_id = %s OR camera_name = %s LIMIT 1", (cam_uuid, cam_uuid))
            cam_match = cur.fetchone()
            if cam_match:
                real_cam_uuid = cam_match['camera_id']
            else:
                real_cam_uuid = "unregistered-cam"
                cur.execute("SELECT camera_id FROM cameras WHERE camera_id = 'unregistered-cam'")
                if not cur.fetchone():
                    cur.execute("INSERT INTO cameras (camera_id, camera_name) VALUES ('unregistered-cam', 'Unregistered Camera')")

            cur.execute("""
                INSERT INTO event_logs_v2 (person_id, camera_id, confidence, evidence_path, timestamp)
                VALUES (%s, %s, %s, %s, %s)
            """, (ev['person_id'], real_cam_uuid, ev['confidence'], ev['evidence_path'], ev['timestamp']))

        print("Event Logs Migrated.")
        
        cur.execute("SELECT setval('people_v2_id_seq', COALESCE((SELECT MAX(id)+1 FROM people_v2), 1), false)")
        cur.execute("SELECT setval('event_logs_v2_id_seq', COALESCE((SELECT MAX(id)+1 FROM event_logs_v2), 1), false)")
        cur.execute("SELECT setval('face_embeddings_id_seq', COALESCE((SELECT MAX(id)+1 FROM face_embeddings), 1), false)")

        conn.commit()
        print("Phase 2 Complete. Data Migration Successful!")
        
        # Run Validation Queries
        cur.execute("SELECT count(*) FROM face_identities")
        v1_count = cur.fetchone()[0]
        cur.execute("SELECT count(*) FROM people_v2")
        v2_count = cur.fetchone()[0]
        print(f"Validation: Legacy face_identities={v1_count}, Unified people_v2={v2_count}")

    except Exception as e:
        conn.rollback()
        print(f"Migration Failed: {e}")
    finally:
        cur.close()
        conn.close()

if __name__ == "__main__":
    main()
