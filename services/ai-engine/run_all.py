import subprocess
import time
import sys
import os
import signal
import threading
import json
import psycopg2
import redis

from app.core.config import settings

class Orchestrator:
    def __init__(self):
        self.project_root = os.path.dirname(os.path.abspath(__file__))
        self.core_processes = []
        self.camera_processes = {}  # {camera_id: Popen}
        self.running = True
        
        # Register signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self.handle_signal)
        signal.signal(signal.SIGTERM, self.handle_signal)

    def handle_signal(self, signum, frame):
        print(f"\n[!] Received signal {signum}. Initiating graceful shutdown...")
        self.running = False
        self.stop_all()
        sys.exit(0)

    def stop_all(self):
        print("\n[!] Shutting down all AI Surveillance Engine components gracefully...")
        all_procs = self.core_processes + list(self.camera_processes.values())
        for p in all_procs:
            try:
                p.terminate()
            except Exception as e:
                print(f"Error terminating process: {e}")
                
        # Wait for processes to exit cleanly
        for p in all_procs:
            try:
                p.wait(timeout=5)
            except subprocess.TimeoutExpired:
                print(f"Process {p.pid} didn't stop, forcing kill...")
                p.kill()
        print("Shutdown complete. No zombie processes.")

    def get_cameras_from_db(self):
        cameras = []
        try:
            conn = psycopg2.connect(
                dbname=settings.DB_NAME,
                user=settings.DB_USER,
                password=settings.DB_PASSWORD,
                host=settings.DB_HOST,
                port=settings.DB_PORT
            )
            cur = conn.cursor()
            # Fetch from the frontend's cameras table
            cur.execute("SELECT camera_id, camera_name, rtsp_url FROM cameras")
            rows = cur.fetchall()
            for row in rows:
                cameras.append({
                    "id": row[0],
                    "name": row[1],
                    "src": row[2] if row[2] else "0"
                })
            conn.close()
        except Exception as e:
            print(f"Failed to fetch cameras from DB: {e}")
            # Fallback to default if DB fails
            cameras = [{"id": "default", "name": "Webcam", "src": "0"}]
        return cameras

    def start_camera(self, cam_id, name, src):
        if cam_id in self.camera_processes:
            print(f"[*] Camera [{name}] is already running.")
            return

        print(f"[*] Spawning Camera Worker for [{name}] (src={src})...")
        cam_proc = subprocess.Popen(
            [sys.executable, "-m", "app.workers.camera_worker", "--id", cam_id, "--name", name, "--src", str(src)],
            cwd=self.project_root
        )
        self.camera_processes[cam_id] = cam_proc

    def stop_camera(self, cam_id):
        if cam_id in self.camera_processes:
            print(f"[*] Stopping Camera Worker [{cam_id}]...")
            proc = self.camera_processes.pop(cam_id)
            try:
                proc.terminate()
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
            except Exception as e:
                print(f"Error terminating camera {cam_id}: {e}")

    def redis_listener(self):
        try:
            r = redis.Redis(
                host=settings.REDIS_HOST,
                port=settings.REDIS_PORT,
                db=settings.REDIS_DB,
                decode_responses=True
            )
            pubsub = r.pubsub()
            pubsub.subscribe("system_control")
            print("[*] Engine subscribed to 'system_control' for dynamic camera updates.")

            for message in pubsub.listen():
                if not self.running:
                    break
                if message["type"] == "message":
                    try:
                        data = json.loads(message["data"])
                        cmd = data.get("command")
                        if cmd == "start_camera":
                            self.start_camera(
                                data.get("camera_id"), 
                                data.get("camera_name"), 
                                data.get("rtsp_url")
                            )
                        elif cmd == "stop_camera":
                            self.stop_camera(data.get("camera_id"))
                    except json.JSONDecodeError:
                        pass
        except Exception as e:
            print(f"Engine Redis listener error: {e}")

    def run(self):
        print("==========================================")
        print("Starting AI Surveillance Engine components")
        print("==========================================")
        
        os.chdir(self.project_root)
        
        try:
            # Sync FAISS index from DB on startup to ensure consistency
            print("[*] Synchronizing FAISS vector index from PostgreSQL database...")
            try:
                from app.recognition.faiss_sync import sync_faiss_from_db
                sync_faiss_from_db()
                print("[*] FAISS synchronization successful.")
            except Exception as sync_err:
                print(f"[!] FAISS sync failed (might be first run): {sync_err}")

            # Start FastAPI
            print("[*] Starting FastAPI Orchestrator (Port 8000)...")
            api_proc = subprocess.Popen(
                [sys.executable, "-m", "uvicorn", "app.api.main:app", "--host", "127.0.0.1", "--port", "8000"],
                cwd=self.project_root
            )
            self.core_processes.append(api_proc)
            
            # Start Recognition Worker (The Brain)
            print("[*] Starting Recognition Worker (The Brain)...")
            rec_proc = subprocess.Popen(
                [sys.executable, "-m", "app.workers.recognition_worker"],
                cwd=self.project_root
            )
            self.core_processes.append(rec_proc)
            
            # Give DB and Redis a moment to stabilize
            time.sleep(1)
            
            # Start Initial Cameras from DB
            cameras = self.get_cameras_from_db()
            for cam in cameras:
                self.start_camera(cam["id"], cam["name"], cam["src"])

            # Start Dynamic Camera Listener
            listener_thread = threading.Thread(target=self.redis_listener, daemon=True)
            listener_thread.start()
                    
            print("\n=======================================================")
            print(">>> Enterprise Microservices System is LIVE! <<<")
            print(">>> Dynamic Orchestration Active. <<<")
            print(">>> Press Ctrl+C to safely shutdown all nodes. <<<")
            print("=======================================================\n")
            
            # Wait for any core process to exit
            for p in self.core_processes:
                p.wait()
                
        except Exception as e:
            print(f"Error during execution: {e}")
            self.stop_all()

def main():
    orchestrator = Orchestrator()
    orchestrator.run()

if __name__ == "__main__":
    main()
