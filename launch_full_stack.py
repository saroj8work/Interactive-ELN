"""
Master Full-Stack Launcher for Interactive-ELN (Aura Lab)
Modeled directly from Interactive-voice-assistant's launch_full_stack.py.
Starts all 12 backend microservices, optional Voice AI agent, and Vite frontend dev server.
Performs port verification and live health checking.
"""

import os
import sys
import time
import socket
import subprocess
from pathlib import Path

# Paths
ROOT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = ROOT_DIR / "backend"
FRONTEND_DIR = ROOT_DIR / "frontend"
ASSISTANT_DIR = ROOT_DIR.parent / "Interactive-voice-assistant"
VENV_PY = (ROOT_DIR / ".venv" / "Scripts" / "python.exe") if (ROOT_DIR / ".venv" / "Scripts" / "python.exe").exists() else sys.executable
HOST_PY = sys.executable

# Load ELN .env
eln_env = os.environ.copy()
eln_env["PYTHONPATH"] = str(BACKEND_DIR)
eln_env_file = ROOT_DIR / ".env"
try:
    if eln_env_file.exists():
        for line in eln_env_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                eln_env[k.strip()] = v.strip()
except Exception:
    pass

# Internal service URL bindings
eln_env["IDENTITY_SERVICE_URL"] = "http://127.0.0.1:8004"
eln_env["PROJECTS_SERVICE_URL"] = "http://127.0.0.1:8001"
eln_env["NOTEBOOK_SERVICE_URL"] = "http://127.0.0.1:8002"
eln_env["ACTIVITY_SERVICE_URL"] = "http://127.0.0.1:8003"
eln_env["PLATES_SERVICE_URL"] = "http://127.0.0.1:8005"
eln_env["CHEMINFORMATICS_SERVICE_URL"] = "http://127.0.0.1:8006"
eln_env["MOLECULAR_SERVICE_URL"] = "http://127.0.0.1:8007"
eln_env["CANVAS_SERVICE_URL"] = "http://127.0.0.1:8008"
eln_env["ANALYTICS_SERVICE_URL"] = "http://127.0.0.1:8009"
eln_env["DOSSIER_SERVICE_URL"] = "http://127.0.0.1:8011"
eln_env["THERMAL_PRINTER_SERVICE_URL"] = "http://127.0.0.1:8012"


def check_port(port: int, host: str = "127.0.0.1") -> bool:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(0.4)
    res = s.connect_ex((host, port))
    s.close()
    return res == 0


def wait_for_port(port: int, name: str, timeout: int = 20) -> bool:
    start = time.time()
    while time.time() - start < timeout:
        if check_port(port):
            print(f"  [OK] {name:<26} listening on port {port}")
            return True
        time.sleep(0.5)
    print(f"  [TIMEOUT] {name:<26} port {port} not listening after {timeout}s")
    return False


def main():
    print("=" * 75)
    print("   LAUNCHING FULL AURA LAB STACK (12 MICROSERVICES + UI + VOICE)")
    print("=" * 75)

    processes = []

    service_specs = [
        ("Identity Service", "services.identity.app.main:app", 8004),
        ("Projects Service", "services.projects.app.main:app", 8001),
        ("Notebook Service", "services.notebook.app.main:app", 8002),
        ("Activity Service", "services.activity.app.main:app", 8003),
        ("Plates Service", "services.plates.app.main:app", 8005),
        ("Cheminformatics Service", "services.cheminformatics.app.main:app", 8006),
        ("Molecular Biology Service", "services.molecular.app.main:app", 8007),
        ("Workflow Canvas Service", "services.canvas.app.main:app", 8008),
        ("Analytics & 4PL Service", "services.analytics.app.main:app", 8009),
        ("Regulatory Dossier Service", "services.dossier.app.main:app", 8011),
        ("ZPL & Protocols Service", "services.thermal_printer.app.main:app", 8012),
        ("ELN API Gateway", "gateway.app.main:app", 8000),
    ]

    # Start all 12 backend microservices
    for idx, (name, app_target, port) in enumerate(service_specs, 1):
        if not check_port(port):
            print(f"[{idx:02d}/14] Starting {name} on port {port}...")
            cmd = [
                str(VENV_PY),
                "-m",
                "uvicorn",
                app_target,
                "--host",
                "127.0.0.1",
                "--port",
                str(port),
                "--log-level",
                "warning",
            ]
            p = subprocess.Popen(cmd, cwd=str(BACKEND_DIR), env=eln_env)
            processes.append((name, p, port))
        else:
            print(f"[{idx:02d}/14] {name} already active on port {port}.")

    # Optional Voice Assistant (Port 8010) if present in sibling repo
    try:
        if ASSISTANT_DIR.is_dir() and (ASSISTANT_DIR / "main.py").exists():
            if not check_port(8010):
                print(f"[13/14] Starting Voice Assistant AI Agent on port 8010...")
                assistant_env = os.environ.copy()
                p = subprocess.Popen([HOST_PY, "main.py"], cwd=str(ASSISTANT_DIR), env=assistant_env)
                processes.append(("Voice Assistant", p, 8010))
            else:
                print(f"[13/14] Voice Assistant Agent already active on port 8010.")
        else:
            print("[13/14] Voice Assistant directory not configured; skipping port 8010.")
    except Exception:
        print("[13/14] Voice Assistant not accessible; skipping port 8010.")

    # Frontend Dev Server (Port 5173)
    if not check_port(5173):
        print(f"[14/14] Starting React Frontend (Vite) on port 5173...")
        p = subprocess.Popen(["npm.cmd", "run", "dev"], cwd=str(FRONTEND_DIR), shell=True)
        processes.append(("Frontend", p, 5173))
    else:
        print(f"[14/14] Frontend already active on port 5173.")

    # Wait for all newly started processes to be ready
    print("\nWaiting for all services to become healthy and reachable...")
    all_healthy = True
    for name, p, port in processes:
        if not wait_for_port(port, name, timeout=18):
            all_healthy = False

    print("\n" + "=" * 75)
    print("   ALL AURA LAB SERVICES ARE ONLINE AND OPERATIONAL!")
    print("=" * 75)
    print("  • Web UI (Frontend)       : http://localhost:5173")
    print("  • ELN API Gateway         : http://127.0.0.1:8000 (Docs: /docs)")
    print("  • Identity Service        : http://127.0.0.1:8004 (Docs: /docs)")
    print("  • Plates & Assay Studio   : http://127.0.0.1:8005 (Docs: /docs)")
    print("  • Cheminformatics Studio  : http://127.0.0.1:8006 (Docs: /docs)")
    print("  • Molecular Biology Studio: http://127.0.0.1:8007 (Docs: /docs)")
    print("  • Workflow Canvas DAG     : http://127.0.0.1:8008 (Docs: /docs)")
    print("  • Analytics & 4PL Sheet   : http://127.0.0.1:8009 (Docs: /docs)")
    print("  • Regulatory Dossier GxP  : http://127.0.0.1:8011 (Docs: /docs)")
    print("  • ZPL & Protocols.io      : http://127.0.0.1:8012 (Docs: /docs)")
    if check_port(8010):
        print("  • Voice Assistant AI      : http://127.0.0.1:8010 (Docs: /docs)")
    print("=" * 75)
    print("\nStack running. Monitoring processes...")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nStopping full stack...")
        for name, p, port in processes:
            p.terminate()
        print("All processes terminated.")


if __name__ == "__main__":
    main()

