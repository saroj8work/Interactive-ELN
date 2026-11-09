import os
import shutil
import subprocess
import tempfile
import time
from http.server import HTTPServer, SimpleHTTPRequestHandler
import threading

PORT = 4176
DIST_DIR = os.path.abspath("frontend/dist")
EDGE_PATH = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
if not os.path.exists(EDGE_PATH):
    EDGE_PATH = r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"

ARTIFACT_DIR = r"C:\Users\saroj\.gemini\antigravity\brain\8a67c1fe-49e1-4021-bdf3-f467bafafd57"
output_file = os.path.join(ARTIFACT_DIR, "aura_voice_ai_gate_preview.png")

class QuietSPAHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=DIST_DIR, **kwargs)

    def do_POST(self):
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(b'{"status":"success"}')

    def log_message(self, format, *args):
        pass

server = HTTPServer(("127.0.0.1", PORT), QuietSPAHandler)
t = threading.Thread(target=server.serve_forever, daemon=True)
t.start()
time.sleep(1)

temp_user_data = tempfile.mkdtemp(prefix="edge_preview_")

try:
    cmd = [
        EDGE_PATH,
        "--headless=new",
        "--disable-gpu",
        "--no-sandbox",
        "--hide-scrollbars",
        "--no-first-run",
        "--no-default-browser-check",
        f"--user-data-dir={temp_user_data}",
        "--window-size=1600,1000",
        "--virtual-time-budget=3000",
        f"--screenshot={output_file}",
        f"http://127.0.0.1:{PORT}/",
    ]
    print("Capturing screenshot...")
    res = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    print("Returncode:", res.returncode)
    if os.path.exists(output_file):
        print(f"Captured {output_file} ({os.path.getsize(output_file)} bytes)")
    else:
        print("File was not created. Stdout:", res.stdout, "Stderr:", res.stderr)
finally:
    shutil.rmtree(temp_user_data, ignore_errors=True)
