from app.database.session import SessionLocal
from app.database.models import Camera
import sys

def add_camera(name, source):
    db = SessionLocal()
    try:
        # Check if camera exists
        existing = db.query(Camera).filter(Camera.name == name).first()
        if existing:
            print(f"[*] Camera '{name}' already exists. Updating source...")
            existing.source = source
        else:
            print(f"[*] Adding new camera: {name}")
            new_cam = Camera(name=name, source=source)
            db.add(new_cam)
        
        db.commit()
        print(f"✅ Success! Camera '{name}' is now in the system.")
    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python add_camera.py <CameraName> <Source>")
        print("Examples:")
        print("  python add_camera.py MainGate 0")
        print("  python add_camera.py Office rtsp://user:pass@192.168.1.10:554/stream")
    else:
        add_camera(sys.argv[1], sys.argv[2])
