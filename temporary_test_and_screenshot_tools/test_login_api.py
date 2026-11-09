import os
import sys
import time
import subprocess
import httpx
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()
backend_dir = Path(__file__).resolve().parents[1] / "backend"
env = os.environ.copy()
env["PYTHONPATH"] = str(backend_dir)

print("Starting Identity service on 8004...")
p_ident = subprocess.Popen(
    [sys.executable, "-m", "uvicorn", "services.identity.app.main:app", "--host", "127.0.0.1", "--port", "8004"],
    cwd=str(backend_dir),
    env=env,
)
print("Starting Gateway service on 8000...")
p_gate = subprocess.Popen(
    [sys.executable, "-m", "uvicorn", "gateway.app.main:app", "--host", "127.0.0.1", "--port", "8000"],
    cwd=str(backend_dir),
    env=env,
)

time.sleep(3)

try:
    with httpx.Client(base_url="http://127.0.0.1:8004", timeout=5) as client:
        # Test health
        res = client.get("/health")
        print("Identity health:", res.status_code, res.json())

        # Test login
        login_payload = {
            "organization_slug": "aura-lab",
            "email": "sarah.chen@auralab.com",
            "password": "AuraLab2026!",
        }
        res_login = client.post("/auth/login", json=login_payload)
        print("Login status:", res_login.status_code)
        if res_login.status_code == 200:
            data = res_login.json()
            print("Login SUCCESS! Access token received:", data["access_token"][:30] + "...")
        else:
            print("Login failed:", res_login.text)

finally:
    p_ident.terminate()
    p_gate.terminate()

