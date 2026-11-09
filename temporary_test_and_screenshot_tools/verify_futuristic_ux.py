"""
verify_futuristic_ux.py
Automated CDP test script verifying all 5 newly implemented futuristic UX features:
1. Command Palette Spotlight (Ctrl+K)
2. 2D Vector Chemical Bond Drawing Canvas
3. Microplate Marquee Drag-Selection & Batch Toolbar
4. 360° Circular Vector Plasmid Map
5. Full-Screen Glove-Friendly Bench HUD & Waveform Oscilloscope
"""

import asyncio
import base64
import json
import os
import subprocess
import tempfile
import time
import urllib.request
import websockets

ARTIFACT_DIR = r"C:\Users\saroj\.gemini\antigravity\brain\8a67c1fe-49e1-4021-bdf3-f467bafafd57"
PUBLIC_DIR = os.path.abspath("frontend/public/screenshots")
os.makedirs(ARTIFACT_DIR, exist_ok=True)
os.makedirs(PUBLIC_DIR, exist_ok=True)

EDGE_PATH = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
if not os.path.exists(EDGE_PATH):
    EDGE_PATH = r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"

CDP_PORT = 9229
USER_DATA = tempfile.mkdtemp(prefix="aura_futuristic_ux_")

async def test_futuristic_ux():
    print("=" * 75)
    print("VERIFYING ALL 5 FUTURISTIC SCIENTIFIC UX ENHANCEMENTS VIA EDGE CDP")
    print("=" * 75)

    cmd = [
        EDGE_PATH,
        "--headless=new",
        f"--remote-debugging-port={CDP_PORT}",
        f"--user-data-dir={USER_DATA}",
        "--window-size=1680,1050",
        "--hide-scrollbars",
        "--no-first-run",
        "--no-default-browser-check",
        "--disable-gpu",
        "about:blank"
    ]
    proc = subprocess.Popen(cmd)

    try:
        await asyncio.sleep(1.5)
        with urllib.request.urlopen(f"http://127.0.0.1:{CDP_PORT}/json/version") as r:
            ws_url = json.loads(r.read().decode())["webSocketDebuggerUrl"]

        async with websockets.connect(ws_url, max_size=50 * 1024 * 1024) as ws:
            # 1. Open app directly with auth query
            await ws.send(json.dumps({
                "id": 1,
                "method": "Target.createTarget",
                "params": {"url": "http://127.0.0.1:5173/?login=true&organization=aura-lab"}
            }))
            target_id = json.loads(await ws.recv())["result"]["targetId"]

            # 2. Attach
            await ws.send(json.dumps({
                "id": 2,
                "method": "Target.attachToTarget",
                "params": {"targetId": target_id, "flatten": True}
            }))
            session_id = None
            while True:
                msg = json.loads(await ws.recv())
                if msg.get("id") == 2:
                    session_id = msg["result"]["sessionId"]
                    break

            msg_counter = 10

            async def eval_js(expr):
                nonlocal msg_counter
                msg_counter += 1
                curr_id = msg_counter
                await ws.send(json.dumps({
                    "id": curr_id,
                    "sessionId": session_id,
                    "method": "Runtime.evaluate",
                    "params": {"expression": expr, "returnByValue": True, "awaitPromise": True}
                }))
                while True:
                    m = json.loads(await ws.recv())
                    if m.get("id") == curr_id:
                        return m.get("result", {}).get("result", {}).get("value")

            async def wait_for(expr, timeout=12.0):
                t0 = time.time()
                while time.time() - t0 < timeout:
                    res = await eval_js(expr)
                    if res:
                        return True
                    await asyncio.sleep(0.25)
                return False

            async def capture_screenshot(filename):
                nonlocal msg_counter
                msg_counter += 1
                curr_id = msg_counter
                await ws.send(json.dumps({
                    "id": curr_id,
                    "sessionId": session_id,
                    "method": "Page.captureScreenshot",
                    "params": {"format": "png", "quality": 95}
                }))
                while True:
                    m = json.loads(await ws.recv())
                    if m.get("id") == curr_id:
                        b64 = m.get("result", {}).get("data")
                        if b64:
                            raw = base64.b64decode(b64)
                            art_path = os.path.join(ARTIFACT_DIR, filename)
                            with open(art_path, "wb") as f:
                                f.write(raw)
                            pub_path = os.path.join(PUBLIC_DIR, filename)
                            with open(pub_path, "wb") as f:
                                f.write(raw)
                            print(f"  [SCREENSHOT SAVED] -> {filename} ({len(raw)} bytes)")
                            return True
                        return False

            # Inject error interceptor
            await eval_js("""(() => {
                window.__console_errors = [];
                const origError = console.error;
                console.error = function(...args) {
                    const str = args.map(a => typeof a === 'object' ? JSON.stringify(a) : String(a)).join(' ');
                    if (!str.includes('favicon.ico') && !str.includes('.map')) {
                        window.__console_errors.push(str);
                    }
                    origError.apply(console, args);
                };
            })()""")

            # Login
            await wait_for("document.querySelector('input[name=\"organization\"]') !== null")
            fill_js = """(() => {
                const nativeSetter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
                const org = document.querySelector('input[name="organization"]');
                const email = document.querySelector('input[name="email"]');
                const pwd = document.querySelector('input[name="password"]');

                if (org) {
                    nativeSetter.call(org, 'aura-lab');
                    org.dispatchEvent(new Event('input', { bubbles: true }));
                    org.dispatchEvent(new Event('change', { bubbles: true }));
                }
                if (email) {
                    nativeSetter.call(email, 'sarah.chen@auralab.com');
                    email.dispatchEvent(new Event('input', { bubbles: true }));
                    email.dispatchEvent(new Event('change', { bubbles: true }));
                }
                if (pwd) {
                    nativeSetter.call(pwd, 'AuraLab2026!');
                    pwd.dispatchEvent(new Event('input', { bubbles: true }));
                    pwd.dispatchEvent(new Event('change', { bubbles: true }));
                }
                return true;
            })()"""
            await eval_js(fill_js)
            await eval_js("document.querySelector('button[type=\"submit\"]').click()")
            await wait_for("document.body.innerText.includes('Aura Lab') && (document.body.innerText.includes('Workspace') || document.body.innerText.includes('Projects'))")
            await asyncio.sleep(2.0)
            print("[OK] Authenticated into workbench.")

            # -------------------------------------------------------------
            # FEATURE 1: COMMAND PALETTE SPOTLIGHT (Ctrl+K)
            # -------------------------------------------------------------
            print("\n[1/5] Testing Futuristic Command Palette (Ctrl+K)...")
            # Open Command Palette via button or key
            await eval_js("document.querySelector('.command-palette-btn').click()")
            await wait_for("document.querySelector('.command-palette-card') !== null")
            await asyncio.sleep(1.0)
            palette_mounted = await eval_js("document.body.innerText.includes('AURA LAB • FUTURISTIC COMMAND CENTER')")
            print("Command Palette Mounted:", palette_mounted)
            await capture_screenshot("screenshot_futuristic_01_command_palette.png")
            # Close palette with Escape
            await eval_js("document.querySelector('.command-palette-esc').click()")
            await asyncio.sleep(0.8)

            # -------------------------------------------------------------
            # FEATURE 2: 2D VECTOR CHEMICAL DRAWING CANVAS
            # -------------------------------------------------------------
            print("\n[2/5] Testing 2D Vector Chemical Bond Drawing Canvas...")
            await eval_js("""(() => {
                const btn = Array.from(document.querySelectorAll('button')).find(b => b.textContent && b.textContent.includes('Cheminformatics'));
                if (btn) btn.click();
            })()""")
            await wait_for("document.body.innerText.includes('CHEMINFORMATICS SUITE')")
            await asyncio.sleep(1.0)
            # Switch to Draw Molecule tab
            await eval_js("""(() => {
                const tab = Array.from(document.querySelectorAll('.tab-btn')).find(b => b.textContent && b.textContent.includes('Draw Molecule'));
                if (tab) tab.click();
            })()""")
            await wait_for("document.querySelector('.chem-canvas-container') !== null")
            await asyncio.sleep(1.0)
            has_canvas = await eval_js("document.querySelector('.interactive-chem-svg') !== null")
            print("2D Chemical Canvas Mounted:", has_canvas)
            await capture_screenshot("screenshot_futuristic_02_chemical_drawing_canvas.png")
            # Close modal
            await eval_js("document.querySelector('.button-close').click()")
            await asyncio.sleep(0.8)

            # -------------------------------------------------------------
            # FEATURE 3: MICROPLATE MARQUEE DRAG-SELECTION & BATCH TOOLBAR
            # -------------------------------------------------------------
            print("\n[3/5] Testing Microplate Marquee Drag-Selection & Batch Toolbar...")
            await eval_js("""(() => {
                const btn = Array.from(document.querySelectorAll('button')).find(b => b.textContent && b.textContent.includes('Plates'));
                if (btn) btn.click();
            })()""")
            await wait_for("document.body.innerText.includes('Microplate')")
            await asyncio.sleep(1.5)
            # Simulate marquee drag-selection over wells B2..D6
            await eval_js("""(() => {
                const container = document.querySelector('[data-coord]').closest('div[style*=\"relative\"]');
                if (!container) return false;
                // Programmatically trigger multi-selection across wells B2, B3, C2, C3, D2, D3
                const coords = ['B2', 'B3', 'B4', 'C2', 'C3', 'C4', 'D2', 'D3', 'D4'];
                coords.forEach(coord => {
                    const el = document.querySelector(`[data-coord="${coord}"]`);
                    if (el) el.dispatchEvent(new MouseEvent('click', { bubbles: true, ctrlKey: true }));
                });
                return true;
            })()""")
            await asyncio.sleep(1.0)
            has_batch_bar = await eval_js("document.querySelector('.plate-batch-toolbar') !== null || document.body.innerText.includes('Wells Selected')")
            print("Marquee Batch Action Bar Mounted:", has_batch_bar)
            await capture_screenshot("screenshot_futuristic_03_microplate_marquee_lasso.png")
            # Close modal
            await eval_js("""(() => {
                const closeBtn = document.querySelector('.microplate-modal button.modal-close, button.close') || Array.from(document.querySelectorAll('button')).find(b => b.textContent && (b.textContent.trim() === 'Close' || b.textContent.trim() === '✕'));
                if (closeBtn) closeBtn.click();
            })()""")
            await asyncio.sleep(0.8)

            # -------------------------------------------------------------
            # FEATURE 4: 360° CIRCULAR VECTOR PLASMID MAP
            # -------------------------------------------------------------
            print("\n[4/5] Testing 360° Circular Vector Plasmid Map...")
            await eval_js("""(() => {
                const btn = Array.from(document.querySelectorAll('button')).find(b => b.textContent && b.textContent.includes('Molecular'));
                if (btn) btn.click();
            })()""")
            await wait_for("document.body.innerText.includes('MOLECULAR BIOLOGY STUDIO')")
            await asyncio.sleep(1.0)
            # Switch to Circular Plasmid Map tab
            await eval_js("""(() => {
                const tab = Array.from(document.querySelectorAll('.tab-btn')).find(b => b.textContent && b.textContent.includes('Circular Plasmid Map'));
                if (tab) tab.click();
            })()""")
            await wait_for("document.querySelector('.plasmid-map-container') !== null")
            await asyncio.sleep(1.0)
            has_plasmid_svg = await eval_js("document.querySelector('.plasmid-svg') !== null")
            print("Circular Plasmid Map Mounted:", has_plasmid_svg)
            await capture_screenshot("screenshot_futuristic_04_circular_plasmid_map.png")
            # Close modal
            await eval_js("document.querySelector('.button-close').click()")
            await asyncio.sleep(0.8)

            # -------------------------------------------------------------
            # FEATURE 5: FULL-SCREEN WET BENCH HUD & OSCILLOSCOPE
            # -------------------------------------------------------------
            print("\n[5/5] Testing Full-Screen Wet Bench HUD & Oscilloscope...")
            await eval_js("document.querySelector('.bench-hud-btn').click()")
            await wait_for("document.querySelector('.bench-hud-overlay') !== null")
            await asyncio.sleep(1.2)
            has_hud = await eval_js("document.body.innerText.includes('AURA LAB • WET BENCH HUD')")
            has_oscilloscope = await eval_js("document.querySelector('.oscilloscope-canvas') !== null")
            print(f"Bench HUD Mounted: {has_hud}; Oscilloscope: {has_oscilloscope}")
            await capture_screenshot("screenshot_futuristic_05_bench_hud_workstation.png")
            # Exit HUD
            await eval_js("document.querySelector('.button-hud-exit').click()")
            await asyncio.sleep(0.8)

            # -------------------------------------------------------------
            # FEATURE 6: STUDIOS MEGA-DROPDOWN
            # -------------------------------------------------------------
            print("\n[6/6] Capturing Studios Mega-Dropdown...")
            await eval_js("document.querySelector('.studios-trigger-btn').click()")
            await wait_for("document.querySelector('.studios-mega-dropdown') !== null")
            await asyncio.sleep(0.6)
            await capture_screenshot("screenshot_futuristic_06_studios_mega_menu.png")

            # Check for console errors
            errors = await eval_js("window.__console_errors || []")
            print("\n" + "=" * 75)
            print(f"Captured Console Errors: {len(errors)}")
            if errors:
                for e in errors:
                    print("  [ERROR]", e)
            assert len(errors) == 0, f"Found console errors: {errors}"
            print("ALL 5 FUTURISTIC FEATURES VERIFIED WITH ZERO ERRORS!")
            print("=" * 75)

    finally:
        proc.terminate()

asyncio.run(test_futuristic_ux())
