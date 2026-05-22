import sys
import subprocess
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

def register_service(service_name: str, script_path: str):
    """Registers a Python script as a Windows service using NSSM."""
    # Note: When run inside a virtual environment, sys.executable points to the venv's python.exe
    python_exe = sys.executable
    script_abs_path = Path(script_path).resolve()
    
    commands = [
        f"nssm install {service_name} \"{python_exe}\" \"{script_abs_path}\"",
        f"nssm set {service_name} AppDirectory \"{script_abs_path.parent}\"",
        f"nssm set {service_name} AppStdout \"C:\\ProgramData\\{service_name}\\stdout.log\"",
        f"nssm set {service_name} AppStderr \"C:\\ProgramData\\{service_name}\\stderr.log\"",
        f"nssm set {service_name} AppRotateFiles 1",
        f"nssm set {service_name} AppRestartDelay 5000",
        f"nssm start {service_name}"
    ]
    
    for cmd in commands:
        try:
            subprocess.run(cmd, shell=True, check=True)
            logger.info(f"Executed: {cmd}")
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to execute {cmd}: {e}")

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python nssm_service.py <service_name> <script_path>")
        sys.exit(1)
        
    register_service(sys.argv[1], sys.argv[2])
