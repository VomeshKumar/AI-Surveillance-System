import argparse
import yaml
import subprocess
import threading
import signal
import sys
import os
import time
import logging
import socket
from typing import Dict, List, Optional

# Logging setup
os.makedirs("logs", exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("logs/system.log"),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("orchestrator")

COLORS = {
    "blue": "\033[94m",
    "green": "\033[92m",
    "magenta": "\033[95m",
    "cyan": "\033[96m",
    "red": "\033[91m",
    "reset": "\033[0m"
}

class Orchestrator:
    def __init__(self, config_path: str):
        self.config_path = config_path
        self.config = self.load_config()
        self.processes: Dict[str, subprocess.Popen] = {}
        self.retries: Dict[str, int] = {}
        self.is_shutting_down = False

        # Register signals
        signal.signal(signal.SIGINT, self.handle_signal)
        signal.signal(signal.SIGTERM, self.handle_signal)

    def load_config(self) -> dict:
        try:
            with open(self.config_path, "r") as f:
                return yaml.safe_load(f)
        except Exception as e:
            logger.error(f"Failed to load config file: {e}")
            sys.exit(1)

    def print_colored(self, color_name: str, prefix: str, text: str):
        color = COLORS.get(color_name, COLORS["reset"])
        reset = COLORS["reset"]
        if not text.endswith("\n"):
            text += "\n"
        sys.stdout.write(f"{color}[{prefix}]{reset} {text}")
        sys.stdout.flush()

    def stream_logs(self, process: subprocess.Popen, name: str, color: str):
        def read_stream(stream):
            for line in iter(stream.readline, ""):
                if line:
                    self.print_colored(color, name, line.strip())

        t1 = threading.Thread(target=read_stream, args=(process.stdout,))
        t2 = threading.Thread(target=read_stream, args=(process.stderr,))
        t1.daemon = True
        t2.daemon = True
        t1.start()
        t2.start()

    def check_health(self) -> bool:
        logger.info("Performing health checks...")
        db_cfg = self.config.get("database", {})
        redis_url = db_cfg.get("redis_url")
        pg_url = db_cfg.get("postgres_url")

        all_healthy = True

        # Check Redis
        try:
            import redis
            r = redis.from_url(redis_url, socket_timeout=3)
            r.ping()
            logger.info("[OK] Redis connection verified.")
        except ImportError:
            logger.warning("Redis python package not found in global env. Skipping ping.")
        except Exception as e:
            logger.error(f"[FAIL] Redis connection failed: {e}")
            all_healthy = False

        # Check Postgres
        try:
            import psycopg2
            conn = psycopg2.connect(pg_url, connect_timeout=3)
            conn.close()
            logger.info("[OK] PostgreSQL connection verified.")
        except ImportError:
            logger.warning("psycopg2 package not found in global env. Skipping ping.")
        except Exception as e:
            logger.error(f"[FAIL] PostgreSQL connection failed: {e}")
            all_healthy = False

        return all_healthy

    def is_port_in_use(self, host: str, port: int) -> bool:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(0.5)
            return sock.connect_ex((host, port)) == 0

    def check_service_ports(self) -> bool:
        services = self.config.get("services", {})
        all_available = True

        for key, cfg in services.items():
            port = cfg.get("port")
            if not port:
                continue

            host = cfg.get("host", "127.0.0.1")
            if self.is_port_in_use(host, int(port)):
                logger.error(
                    "[FAIL] Port %s is already in use for service %s (%s). "
                    "Stop the existing process or change the configured port before starting the orchestrator.",
                    port,
                    cfg.get("name", key.upper()),
                    host,
                )
                all_available = False

        return all_available

    def start_service(self, service_key: str, cfg: dict):
        if self.is_shutting_down:
            return

        name = cfg["name"]
        color = cfg["color"]
        directory = os.path.abspath(cfg["directory"])
        command = cfg["command"].copy()
        
        # Resolve the executable to an absolute path if it is a relative path inside the directory
        if not os.path.isabs(command[0]) and "npm" not in command[0]:
            cmd_path = os.path.join(directory, command[0])
            if os.path.exists(cmd_path):
                command[0] = cmd_path

        logger.info(f"Starting service: {name} in {directory}")
        try:
            p = subprocess.Popen(
                command,
                cwd=directory,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
                shell=True if "npm" in command[0] else False
            )
            self.processes[service_key] = p
            self.stream_logs(p, name, color)
        except Exception as e:
            logger.error(f"Failed to start {name}: {e}")

    def monitor(self):
        services = self.config.get("services", {})
        while not self.is_shutting_down:
            for key, p in list(self.processes.items()):
                if p.poll() is not None:
                    # Process died
                    cfg = services[key]
                    name = cfg["name"]
                    code = p.returncode
                    logger.error(f"Service {name} crashed with exit code {code}.")
                    
                    retries = self.retries.get(key, 0)
                    max_retries = cfg.get("retries", 0)
                    
                    if retries < max_retries:
                        self.retries[key] = retries + 1
                        logger.info(f"Restarting {name} (Attempt {self.retries[key]}/{max_retries})...")
                        self.start_service(key, cfg)
                    else:
                        logger.error(f"Service {name} exhausted retries. Initiating system shutdown.")
                        self.handle_signal(signal.SIGINT, None)
            time.sleep(2)

    def handle_signal(self, signum, frame):
        if self.is_shutting_down:
            return
        self.is_shutting_down = True
        logger.info("\nGracefully shutting down all services...")
        
        for key, p in self.processes.items():
            if p.poll() is None:
                logger.info(f"Terminating {key}...")
                p.terminate()
        
        # Wait for processes
        for key, p in self.processes.items():
            try:
                p.wait(timeout=5)
            except subprocess.TimeoutExpired:
                logger.warning(f"Force killing {key}...")
                p.kill()
        
        logger.info("System shutdown complete.")
        sys.exit(0)

    def handle_restart(self):
        if self.is_shutting_down:
            return
        self.is_shutting_down = True
        logger.info("\nGracefully shutting down all services for RESTART...")
        
        for key, p in self.processes.items():
            if p.poll() is None:
                logger.info(f"Terminating {key}...")
                p.terminate()
        
        # Wait for processes
        for key, p in self.processes.items():
            try:
                p.wait(timeout=5)
            except subprocess.TimeoutExpired:
                logger.warning(f"Force killing {key}...")
                p.kill()
        
        logger.info("System shutdown complete. Restarting Orchestrator...")
        import sys
        import os
        os.execv(sys.executable, ['python'] + sys.argv)

    def _redis_listener(self):
        db_cfg = self.config.get("database", {})
        redis_url = db_cfg.get("redis_url")
        if not redis_url:
            return
            
        import json
        import redis
        
        while not self.is_shutting_down:
            try:
                # Removed socket_timeout so we don't drop the connection during idle periods
                r = redis.from_url(redis_url)
                pubsub = r.pubsub()
                pubsub.subscribe("system_control")
                logger.info("Orchestrator subscribed to 'system_control' Redis channel.")
                
                while not self.is_shutting_down:
                    # Use get_message with a short timeout instead of blocking listen
                    message = pubsub.get_message(timeout=1.0)
                    if message and message["type"] == "message":
                        try:
                            data = json.loads(message["data"])
                            if data.get("command") == "shutdown":
                                logger.critical(f"Remote shutdown command received! Requested by: {data.get('requested_by')}")
                                logger.info("Initiating shutdown sequence in 3 seconds...")
                                time.sleep(3)
                                self.handle_signal(signal.SIGINT, None)
                                break
                            elif data.get("command") == "restart":
                                logger.critical(f"Remote restart command received! Requested by: {data.get('requested_by')}")
                                logger.info("Initiating restart sequence in 3 seconds...")
                                time.sleep(3)
                                self.handle_restart()
                                break
                        except json.JSONDecodeError:
                            pass
                    time.sleep(0.1) # Small sleep to prevent CPU spike if get_message returns immediately
            except Exception as e:
                if not self.is_shutting_down:
                    logger.error(f"Redis listener error: {e}. Reconnecting in 5s...")
                    time.sleep(5)

    def run(self, mode: str):
        print("==========================================")
        print(" AI Surveillance System Orchestrator ")
        print(f" Mode: {mode}")
        print("==========================================")

        if not self.check_health():
            logger.error("Health checks failed. Exiting.")
            sys.exit(1)

        if not self.check_service_ports():
            logger.error("One or more required service ports are already in use. Exiting.")
            sys.exit(1)

        if mode == "prod":
            logger.info("Running in prod mode. Dependencies validated. Exiting orchestrator.")
            sys.exit(0)

        services = self.config.get("services", {})
        
        # Start in order: Engine, Consumer, API, Frontend
        order = ["engine", "consumer", "backend", "frontend"]
        for key in order:
            if key in services:
                self.start_service(key, services[key])
                self.retries[key] = 0
                time.sleep(1) # Stagger startups slightly
                
        # Start Redis control listener
        threading.Thread(target=self._redis_listener, daemon=True).start()
                
        logger.info("All services started. Monitoring...")
        self.monitor()

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["dev", "prod"], default="dev", help="Run mode")
    parser.add_argument("--config", default="config/config.yaml", help="Path to config file")
    args = parser.parse_args()

    orchestrator = Orchestrator(args.config)
    
    # Ensure dependencies for health check are available (pyyaml is, redis/psycopg2 might not be in global, but we use try/except)
    orchestrator.run(args.mode)
