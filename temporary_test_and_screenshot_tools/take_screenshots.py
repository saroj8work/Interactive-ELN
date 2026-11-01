import os
import shutil
import subprocess
import sys
import tempfile
import time
from http.server import HTTPServer, SimpleHTTPRequestHandler
import threading

PORT = 4173
DIST_DIR = os.path.abspath("frontend/dist")
EDGE_PATH = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
if not os.path.exists(EDGE_PATH):
    EDGE_PATH = r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"

ARTIFACT_DIR = r"C:\Users\saroj\.gemini\antigravity\brain\8a67c1fe-49e1-4021-bdf3-f467bafafd57"
PUBLIC_DIR = os.path.abspath("frontend/public/screenshots")
os.makedirs(PUBLIC_DIR, exist_ok=True)

class QuietSPAHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=DIST_DIR, **kwargs)

    def do_POST(self):
        # Gracefully handle any stray client POST in preview
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(b"{}")

    def log_message(self, format, *args):
        pass

server = HTTPServer(("127.0.0.1", PORT), QuietSPAHandler)
server_thread = threading.Thread(target=server.serve_forever, daemon=True)
server_thread.start()
print(f"HTTP server running on http://127.0.0.1:{PORT}")
time.sleep(1)

TARGETS = [
    {
        "filename": "screenshot_01_login.png",
        "url": f"http://127.0.0.1:{PORT}/",
        "title": "Application Login Screen with Glowing DNA App Icon",
        "budget": "3000",
    },
    {
        "filename": "screenshot_02_workspace.png",
        "url": f"http://127.0.0.1:{PORT}/?preview=workspace",
        "title": "Laboratory Notebook Workspace (Projects, Experiments & KaTeX Entries)",
        "budget": "4000",
    },
    {
        "filename": "screenshot_03_in_browser_e2e_runner.png",
        "url": f"http://127.0.0.1:{PORT}/?preview=e2e",
        "title": "Interactive In-Browser End-to-End Test Suite Runner",
        "budget": "4000",
    },
    {
        "filename": "screenshot_04_formal_report_view.png",
        "url": f"http://127.0.0.1:{PORT}/?preview=report",
        "title": "Formal Regulatory PDF/Print-Ready Experiment Report",
        "budget": "4000",
    },
    {
        "filename": "screenshot_05_chemical_structure_search.png",
        "url": f"http://127.0.0.1:{PORT}/?preview=chemsearch",
        "title": "Substructure & Similarity Chemical Search Modal",
        "budget": "4000",
    },
    {
        "filename": "screenshot_06_inventory_biobank.png",
        "url": f"http://127.0.0.1:{PORT}/?preview=inventory",
        "title": "Cryogenic Biobank & Chemical Reagents Inventory Management",
        "budget": "4000",
    },
]

temp_user_data = tempfile.mkdtemp(prefix="edge_preview_")
print(f"Using temp profile: {temp_user_data}")

captured = []

try:
    for target in TARGETS:
        out_path = os.path.abspath(target["filename"])
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
            f"--virtual-time-budget={target['budget']}",
            f"--screenshot={out_path}",
            target["url"],
        ]
        print(f"Capturing: {target['title']} -> {target['filename']}")
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        
        if os.path.exists(out_path) and os.path.getsize(out_path) > 1000:
            size_kb = os.path.getsize(out_path) / 1024
            print(f"  [OK] Saved {target['filename']} ({size_kb:.1f} KB)")
            shutil.copy2(out_path, os.path.join(PUBLIC_DIR, target["filename"]))
            shutil.copy2(out_path, os.path.join(ARTIFACT_DIR, target["filename"]))
            captured.append(target)
        else:
            print(f"  [WARN] Failed to capture {target['filename']}. returncode={res.returncode}")

finally:
    try:
        shutil.rmtree(temp_user_data, ignore_errors=True)
    except Exception:
        pass
    server.shutdown()

print(f"\nSuccessfully captured and archived {len(captured)} of {len(TARGETS)} screenshots!")
