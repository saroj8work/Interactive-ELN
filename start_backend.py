"""
start_backend.py
Runs all 5 ELN backend microservices concurrently for local development:
- Identity Service (port 8004)
- Projects Service (port 8001)
- Notebook Service (port 8002)
- Activity Service (port 8003)
- API Gateway (port 8000)
"""

import os
import sys
import subprocess
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

backend_dir = Path(__file__).resolve().parent / "backend"
python_exe = sys.executable

services = [
    {"name": "Identity Service", "app": "services.identity.app.main:app", "port": 8004},
    {"name": "Projects Service", "app": "services.projects.app.main:app", "port": 8001},
    {"name": "Notebook Service", "app": "services.notebook.app.main:app", "port": 8002},
    {"name": "Activity Service", "app": "services.activity.app.main:app", "port": 8003},
    {"name": "Plates Service", "app": "services.plates.app.main:app", "port": 8005},
    {"name": "Cheminformatics Service", "app": "services.cheminformatics.app.main:app", "port": 8006},
    {"name": "Molecular Service", "app": "services.molecular.app.main:app", "port": 8007},
    {"name": "Canvas Service", "app": "services.canvas.app.main:app", "port": 8008},
    {"name": "Analytics Service", "app": "services.analytics.app.main:app", "port": 8009},
    {"name": "Dossier Service", "app": "services.dossier.app.main:app", "port": 8011},
    {"name": "Thermal Printer Service", "app": "services.thermal_printer.app.main:app", "port": 8012},
    {"name": "API Gateway", "app": "gateway.app.main:app", "port": 8000},
]

processes = []

env = os.environ.copy()
env["PYTHONPATH"] = str(backend_dir)

print("=" * 60)
print("STARTING AURA LAB BACKEND SERVICES...")
print("=" * 60)

try:
    for s in services:
        cmd = [
            python_exe,
            "-m",
            "uvicorn",
            s["app"],
            "--host",
            "127.0.0.1",
            "--port",
            str(s["port"]),
            "--log-level",
            "warning",
        ]
        p = subprocess.Popen(cmd, cwd=str(backend_dir), env=env)
        processes.append((s["name"], p, s["port"]))
        print(f"  [RUNNING] {s['name']:<20} -> http://127.0.0.1:{s['port']}")

    print("=" * 60)
    print("ALL 5 BACKEND SERVICES ARE LIVE & HEALTHY!")
    print("API Gateway URL:  http://127.0.0.1:8000")
    print("Identity URL:     http://127.0.0.1:8004")
    print("Frontend App:     http://localhost:5173")
    print("=" * 60)
    print("Press Ctrl+C to terminate all services.")
    
    # Wait for processes
    for _, p, _ in processes:
        p.wait()

except KeyboardInterrupt:
    print("\nShutting down backend services...")
    for name, p, _ in processes:
        p.terminate()
    print("All services stopped.")

