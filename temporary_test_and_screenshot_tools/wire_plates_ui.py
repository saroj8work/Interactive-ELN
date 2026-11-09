with open("frontend/src/App.tsx", "r", encoding="utf-8") as f:
    text = f.read()

crlf = "\r\n" in text
norm = text.replace("\r\n", "\n")

# 1. Import
old_import = 'import { ChemicalSearchModal } from "./ChemicalSearchModal";'
new_import = """import { ChemicalSearchModal } from "./ChemicalSearchModal";
import { MicroplateAssayModal } from "./MicroplateAssayModal";"""

assert old_import in norm, "old_import not found"
norm = norm.replace(old_import, new_import, 1)

# 2. State
old_state = 'const [chemSearchOpen, setChemSearchOpen] = useState(false);'
new_state = """const [chemSearchOpen, setChemSearchOpen] = useState(false);
  const [plateModalOpen, setPlateModalOpen] = useState(false);"""

assert old_state in norm, "old_state not found"
norm = norm.replace(old_state, new_state, 1)

# 3. Voice handler
old_voice = 'else if (target.includes("chem") || target.includes("structure")) setChemSearchOpen(true);'
new_voice = """else if (target.includes("chem") || target.includes("structure")) setChemSearchOpen(true);
          else if (target.includes("plate") || target.includes("assay") || target.includes("heatmap") || target.includes("elisa")) setPlateModalOpen(true);"""

assert old_voice in norm, "old_voice not found"
norm = norm.replace(old_voice, new_voice, 1)

# 4. Topbar button
old_topbar = """            <button
              className={`button button-outline ${benchMode ? "bench-mode-active" : ""}`}"""
new_topbar = """            <button
              className="button button-outline"
              type="button"
              onClick={() => setPlateModalOpen(true)}
              title="Open 96-Well & 384-Well Microplate & Spectrophotometry Studio"
            >
              🔬 Plates
            </button>
            <button
              className={`button button-outline ${benchMode ? "bench-mode-active" : ""}`}"""

assert old_topbar in norm, "old_topbar not found"
norm = norm.replace(old_topbar, new_topbar, 1)

# 5. Render Modal
old_render = """        <ChemicalSearchModal
          isOpen={chemSearchOpen}
          onClose={() => setChemSearchOpen(false)}
          onSelectResult={handleChemSearchResult}
          inventoryItems={inventoryItems}
          entries={entries}
        />"""

new_render = """        <ChemicalSearchModal
          isOpen={chemSearchOpen}
          onClose={() => setChemSearchOpen(false)}
          onSelectResult={handleChemSearchResult}
          inventoryItems={inventoryItems}
          entries={entries}
        />

        <MicroplateAssayModal
          isOpen={plateModalOpen}
          onClose={() => setPlateModalOpen(false)}
          projectId={selectedProject}
          experimentId={selectedExperiment}
        />"""

assert old_render in norm, "old_render not found"
norm = norm.replace(old_render, new_render, 1)

res = norm.replace("\n", "\r\n") if crlf else norm
with open("frontend/src/App.tsx", "w", encoding="utf-8") as f:
    f.write(res)

print("Successfully wired MicroplateAssayModal into App.tsx!")

