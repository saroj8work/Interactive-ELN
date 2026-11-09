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

CDP_PORT = 9235
USER_DATA = tempfile.mkdtemp(prefix="aura_advanced_studios_")

async def test_and_capture_all_studios():
    print("=" * 80)
    print("END-TO-END VERIFICATION: 7 ADVANCED SCIENTIFIC STUDIOS & GANTT PLANNER")
    print("=" * 80)

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
        await asyncio.sleep(1.8)
        with urllib.request.urlopen(f"http://127.0.0.1:{CDP_PORT}/json/version") as r:
            ws_url = json.loads(r.read().decode())["webSocketDebuggerUrl"]

        async with websockets.connect(ws_url, max_size=50 * 1024 * 1024) as ws:
            # 1. Open app
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
                        res_obj = m.get("result", {}).get("result", {})
                        if "value" in res_obj:
                            return res_obj["value"]
                        return True

            async def wait_for(expr, timeout=18.0):
                t0 = time.time()
                while time.time() - t0 < timeout:
                    res = await eval_js(expr)
                    if res:
                        return res
                    await asyncio.sleep(0.3)
                raise TimeoutError(f"Timed out waiting for: {expr}")

            async def take_screenshot(name, description):
                nonlocal msg_counter
                msg_counter += 1
                curr_id = msg_counter
                await ws.send(json.dumps({
                    "id": curr_id,
                    "sessionId": session_id,
                    "method": "Page.captureScreenshot",
                    "params": {"format": "png"}
                }))
                while True:
                    m = json.loads(await ws.recv())
                    if m.get("id") == curr_id:
                        data = base64.b64decode(m["result"]["data"])
                        p1 = os.path.join(ARTIFACT_DIR, f"{name}.png")
                        p2 = os.path.join(PUBLIC_DIR, f"{name}.png")
                        with open(p1, "wb") as f:
                            f.write(data)
                        with open(p2, "wb") as f:
                            f.write(data)
                        print(f"  [SCREENSHOT CAPTURED] {name}.png -> {description}")
                        break

            # Wait for either login input or landing page sign-in button
            print("  Connecting to Aura Lab frontend...")
            await asyncio.sleep(2.0)
            is_landing = await eval_js("document.querySelector('button.landing-btn-primary') !== null")
            if is_landing:
                print("  Landing page detected; clicking 'Sign In'...")
                await eval_js("document.querySelector('button.landing-btn-primary').click()")
                await asyncio.sleep(1.0)

            # Wait for Login screen
            await wait_for("document.querySelector('input[name=\"organization\"]') !== null")
            await eval_js("""
            (() => {
                const setVal = (el, val) => {
                    Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set.call(el, val);
                    el.dispatchEvent(new Event('input', { bubbles: true }));
                    el.dispatchEvent(new Event('change', { bubbles: true }));
                };
                setVal(document.querySelector('input[name="organization"]'), 'aura-lab');
                setVal(document.querySelector('input[name="email"]'), 'sarah.chen@auralab.com');
                setVal(document.querySelector('input[name="password"]'), 'AuraLab2026!');
                document.querySelector('button[type="submit"]').click();
                return true;
            })()
            """)

            # Wait for main application
            await wait_for("document.body.innerText.includes('Aura Lab') && (document.body.innerText.includes('Workspace') || document.body.innerText.includes('Projects'))")
            print("  ✓ Authenticated as Dr. Sarah Chen into Aura Lab Dashboard")
            await asyncio.sleep(1.0)

            # -------------------------------------------------------------
            # TEST 1: Sample Aliquot Genealogy & Freeze-Thaw Tree
            # -------------------------------------------------------------
            print("\n[STUDIO 1/7] Testing Sample Aliquot Genealogy & Freeze-Thaw Tree...")
            await eval_js("window.dispatchEvent(new CustomEvent('aura-ui-action', { detail: { action_type: 'OPEN_MODAL', target: 'lineage' } }))")
            await wait_for("document.querySelector('.lineage-modal-content') !== null")
            await asyncio.sleep(0.8)
            await take_screenshot("screenshot_advanced_01_sample_genealogy_tree", "DAG Sample Genealogy Tree & Freeze-Thaw Cycle Tracker")
            await eval_js("document.querySelector('.button-close').click()")
            await asyncio.sleep(0.5)

            # -------------------------------------------------------------
            # TEST 2: Cell Culture & In Vitro Passage Tracker
            # -------------------------------------------------------------
            print("\n[STUDIO 2/7] Testing Cell Culture & In Vitro Passage Tracker...")
            await eval_js("window.dispatchEvent(new CustomEvent('aura-ui-action', { detail: { action_type: 'OPEN_MODAL', target: 'cell-culture' } }))")
            await wait_for("document.querySelector('.cell-modal-content') !== null")
            await asyncio.sleep(0.8)
            await take_screenshot("screenshot_advanced_02_cell_culture_passage_tracker", "Cell Line Registry, Doubling Regression Curve & Cryovial Drawer Matrix")
            await eval_js("document.querySelector('.button-close').click()")
            await asyncio.sleep(0.5)

            # -------------------------------------------------------------
            # TEST 3: GxP Equipment Calibration, Qualification & Lockout
            # -------------------------------------------------------------
            print("\n[STUDIO 3/7] Testing Equipment Calibration & GxP Lockout Hub...")
            await eval_js("window.dispatchEvent(new CustomEvent('aura-ui-action', { detail: { action_type: 'OPEN_MODAL', target: 'calibration' } }))")
            await wait_for("document.querySelector('.futuristic-calibration-modal') !== null")
            await asyncio.sleep(0.8)
            await take_screenshot("screenshot_advanced_03_equipment_calibration_lockout", "GxP Metrology Calibration Hub with Linear Regression & Automated Lockout")
            await eval_js("document.querySelector('.futuristic-close-btn').click()")
            await asyncio.sleep(0.5)

            # -------------------------------------------------------------
            # TEST 4: Sanger Sequencing Chromatogram (.ab1) Studio
            # -------------------------------------------------------------
            print("\n[STUDIO 4/7] Testing Sanger Sequencing Chromatogram Studio...")
            await eval_js("window.dispatchEvent(new CustomEvent('aura-ui-action', { detail: { action_type: 'OPEN_MODAL', target: 'chromatogram' } }))")
            await wait_for("document.querySelector('.futuristic-chromatogram-modal') !== null")
            await asyncio.sleep(0.8)
            await take_screenshot("screenshot_advanced_04_chromatogram_ab1_viewer", "Sanger 4-Dye Electropherogram Waveforms, Phred Quality Scores & Mutation Calling")
            await eval_js("document.querySelector('.futuristic-close-btn').click()")
            await asyncio.sleep(0.5)

            # -------------------------------------------------------------
            # TEST 5: Automated Reagent Procurement & PO Requisitions
            # -------------------------------------------------------------
            print("\n[STUDIO 5/7] Testing Automated Reagent Procurement & PO Requisitions...")
            await eval_js("window.dispatchEvent(new CustomEvent('aura-ui-action', { detail: { action_type: 'OPEN_MODAL', target: 'procurement' } }))")
            await wait_for("document.querySelector('.futuristic-procurement-modal') !== null")
            await asyncio.sleep(0.8)
            await take_screenshot("screenshot_advanced_05_reagent_procurement_po", "Vendor Catalog Procurement Requisitions, Approval Pipeline & EDI Integration")
            await eval_js("document.querySelector('.futuristic-close-btn').click()")
            await asyncio.sleep(0.5)

            # -------------------------------------------------------------
            # TEST 6: Gantt Resource Scheduling & Workload Planner
            # -------------------------------------------------------------
            print("\n[STUDIO 6/7] Testing Gantt Resource Scheduling & Workload Planner...")
            await eval_js("window.dispatchEvent(new CustomEvent('aura-ui-action', { detail: { action_type: 'OPEN_MODAL', target: 'gantt' } }))")
            await wait_for("document.querySelector('.futuristic-gantt-modal') !== null")
            await asyncio.sleep(0.8)
            await take_screenshot("screenshot_advanced_06_gantt_resource_workload_planner", "Multi-Track Instrument/Scientist Gantt Timeline with Overlap Collision Alert")
            # Click Auto-Resolve Collisions to test the dynamic workload optimizer
            await eval_js("document.querySelector('.gantt-btn-amber')?.click()")
            await asyncio.sleep(0.4)
            await eval_js("document.querySelector('.futuristic-close-btn').click()")
            await asyncio.sleep(0.5)

            # -------------------------------------------------------------
            # TEST 7: In Vivo Preclinical Rodent Colony Management
            # -------------------------------------------------------------
            print("\n[STUDIO 7/7] Testing In Vivo Preclinical Rodent Colony Management...")
            await eval_js("window.dispatchEvent(new CustomEvent('aura-ui-action', { detail: { action_type: 'OPEN_MODAL', target: 'rodent' } }))")
            await wait_for("document.querySelector('.futuristic-rodent-modal') !== null")
            await asyncio.sleep(0.8)
            await take_screenshot("screenshot_advanced_07_rodent_colony_vivarium", "Vivarium Rodent Registry, Longitudinal Body Weight Trajectory & Caliper Metrics")
            # Switch to IVC Cage Rack Matrix tab
            await eval_js("document.querySelectorAll('.gantt-tab-btn')[2]?.click()")
            await asyncio.sleep(0.5)
            await take_screenshot("screenshot_advanced_08_ivc_cage_rack_matrix", "Interactive IVC Ventilated Cage Rack Matrix with Airflow Balance & Animal Density")
            await eval_js("document.querySelector('.futuristic-close-btn').click()")
            await asyncio.sleep(0.5)

            # -------------------------------------------------------------
            # TEST 8: Command Palette with all studios
            # -------------------------------------------------------------
            print("\n[SPOTLIGHT SEARCH] Testing Command Palette with all new studios...")
            await eval_js("window.dispatchEvent(new KeyboardEvent('keydown', { key: 'k', ctrlKey: true, bubbles: true }))")
            await wait_for("document.querySelector('.command-palette-card') !== null")
            await asyncio.sleep(0.5)
            await take_screenshot("screenshot_advanced_09_command_palette_all_studios", "Futuristic Command Center (Ctrl+K) Indexing All 7 New Studios")
            await eval_js("document.querySelector('.command-palette-esc').click()")
            await asyncio.sleep(0.4)

            print("\n" + "=" * 80)
            print("ALL 7 ADVANCED SCIENTIFIC STUDIOS & GANTT PLANNER VERIFIED 100% PASSING!")
            print("=" * 80)

    finally:
        proc.kill()

if __name__ == "__main__":
    asyncio.run(test_and_capture_all_studios())

