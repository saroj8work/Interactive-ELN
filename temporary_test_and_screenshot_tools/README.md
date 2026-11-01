# Temporary Test & Screenshot Preparation Tools

> [!NOTE]
> All files in this directory were created exclusively for development verification, automated headless browser screenshots, and design reviews. **None of the files in this folder are part of the core business logic or production deployment.**

---

### Files Included

| File | Purpose | Description |
|------|---------|-------------|
| `EndToEndTestRunner.tsx` | In-Browser E2E Test Suite | Client-side test execution runner that automatically runs 10 end-to-end assertions in the browser DOM (stoichiometry deductions, 96-well grid mapping, barcode scanners, timers). Moved out of core production UI. |
| `previewData.ts` | Mock Dataset | Self-contained mock data (projects, experiments, entries with KaTeX math, inventory, samples) used solely for rendering offline UI preview states. |
| `take_screenshots.py` | Headless Edge Capture | Automated script that launches an in-memory SPA server and uses Microsoft Edge (`msedge.exe --headless=new`) to take full-page PNG screenshots of each view. |
| `patch_app.py` | Preview Injector | Injects offline preview routing into `frontend/src/App.tsx` when taking automated screenshots. |
| `restore_app.py` | Production Cleaner | Restores `frontend/src/App.tsx` back to pristine production code, removing all temporary preview branches. |
| `remove_e2e_runner.py` | Test Runner Stripper | Utility that removes test runner components and buttons from the production app. |
| `seed_data.py` | Dummy Database Seeder | Standalone database seeder that populates in-memory SQLite or development databases with test organizations, users, experiments, and inventory. |

---

### How to Re-Run Screenshot Capture (If Ever Needed)

1. **Inject Temporary Preview Hooks:**
   ```powershell
   python temporary_test_and_screenshot_tools/patch_app.py
   npm --prefix frontend run build
   ```

2. **Run Headless Browser Capture:**
   ```powershell
   python temporary_test_and_screenshot_tools/take_screenshots.py
   ```

3. **Restore Production Code:**
   ```powershell
   python temporary_test_and_screenshot_tools/restore_app.py
   python temporary_test_and_screenshot_tools/remove_e2e_runner.py
   npm --prefix frontend run build
   ```
