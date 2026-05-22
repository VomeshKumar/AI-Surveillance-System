import json
import os
import logging
from typing import List
from app.core.config import settings

logger = logging.getLogger(__name__)

class NodeConfig:
    """Manages identity and capabilities for a specific edge node."""
    def __init__(self):
        self.node_id = settings.NODE_ID
        self.config_path = os.path.join(settings.ARTIFACTS_DIR, "..", "data", "config", f"{self.node_id}.json")
        self.assigned_cameras: List[str] = []
        self.capabilities = ["detection", "recognition"]
        self.load_config()
        
    def load_config(self):
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, 'r') as f:
                    data = json.load(f)
                    self.assigned_cameras = data.get("cameras", [])
            except Exception as e:
                logger.error(f"Failed to load node config: {e}")
                
    def save_config(self):
        os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
        with open(self.config_path, 'w') as f:
            json.dump({
                "node_id": self.node_id,
                "cameras": self.assigned_cameras,
                "capabilities": self.capabilities
            }, f, indent=4)
