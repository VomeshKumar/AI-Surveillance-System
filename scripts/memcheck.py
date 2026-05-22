import psutil
import time
import logging
import os

logger = logging.getLogger(__name__)

def log_memory_usage():
    process = psutil.Process(os.getpid())
    mem_info = process.memory_info()
    rss_mb = mem_info.rss / (1024 * 1024)
    logger.info(f"Memory Usage: RSS = {rss_mb:.2f} MB")

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    while True:
        log_memory_usage()
        time.sleep(300) # 5 min sampling
