import json
import os
import uuid

class CameraManager:
    """Manages the persistence of camera configurations using a JSON file."""
    
    def __init__(self, config_path="data/config/cameras.json"):
        self.config_path = config_path
        os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
        self.cameras = self.load()
        
    def load(self):
        if not os.path.exists(self.config_path):
            # Return default webcam if no config exists
            return [{"id": "default_webcam", "name": "Webcam", "type": "webcam", "src": 0}]
        try:
            with open(self.config_path, "r") as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading cameras: {e}")
            return [{"id": "default_webcam", "name": "Webcam", "type": "webcam", "src": 0}]
            
    def save(self):
        with open(self.config_path, "w") as f:
            json.dump(self.cameras, f, indent=4)
            
    def add_camera(self, name, type_str, src):
        # Convert numeric strings to int for webcam index
        if type_str == "webcam" and str(src).isdigit():
            src = int(src)
            
        cam = {
            "id": str(uuid.uuid4())[:8],
            "name": name,
            "type": type_str,
            "src": src
        }
        self.cameras.append(cam)
        self.save()
        return cam
        
    def remove_camera(self, cam_id):
        self.cameras = [c for c in self.cameras if c["id"] != cam_id]
        self.save()
        
    def get_all(self):
        return self.cameras
