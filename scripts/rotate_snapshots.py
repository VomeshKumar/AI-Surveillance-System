import os
import time
import logging
from app.core.config import settings

logger = logging.getLogger(__name__)

def purge_old_snapshots(hours_to_keep=1):
    """Deletes snapshots older than `hours_to_keep`."""
    snapshots_dir = os.path.join(settings.ARTIFACTS_DIR, "..", "data", "snapshots")
    if not os.path.exists(snapshots_dir):
        return
        
    current_time = time.time()
    cutoff_time = current_time - (hours_to_keep * 3600)
    
    count = 0
    for filename in os.listdir(snapshots_dir):
        filepath = os.path.join(snapshots_dir, filename)
        if os.path.isfile(filepath):
            if os.path.getmtime(filepath) < cutoff_time:
                try:
                    os.remove(filepath)
                    count += 1
                except Exception as e:
                    logger.error(f"Failed to delete {filepath}: {e}")
                    
    logger.info(f"Purged {count} old snapshots.")

if __name__ == "__main__":
    purge_old_snapshots()
