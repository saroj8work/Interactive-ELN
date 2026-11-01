path = "frontend/src/App.tsx"
with open(path, "r", encoding="utf-8") as f:
    text = f.read()

crlf = "\r\n" in text
norm_text = text.replace("\r\n", "\n")

# 1. Remove import
import_line = 'import { EndToEndTestRunner } from "./EndToEndTestRunner";\n'
assert import_line in norm_text, "import_line not found"
norm_text = norm_text.replace(import_line, "", 1)

# 2. Remove state
state_line = "  const [e2eSuiteOpen, setE2eSuiteOpen] = useState(false);\n"
assert state_line in norm_text, "state_line not found"
norm_text = norm_text.replace(state_line, "", 1)

# 3. Remove toolbar button
button_block = """            <button
              className="button button-outline"
              type="button"
              onClick={() => setE2eSuiteOpen(true)}
              style={{ display: "inline-flex", alignItems: "center", gap: 6, borderColor: "#d8c8f7", color: "#3F1899", fontWeight: 600 }}
              title="Run automated in-browser end-to-end test suite"
            >
              🧪 {t("E2E Tests")}
            </button>
"""
assert button_block in norm_text, "button_block not found"
norm_text = norm_text.replace(button_block, "", 1)

# 4. Remove component render
component_block = """        <EndToEndTestRunner
          isOpen={e2eSuiteOpen}
          onClose={() => setE2eSuiteOpen(false)}
        />

"""
assert component_block in norm_text, "component_block not found"
norm_text = norm_text.replace(component_block, "", 1)

if crlf:
    final_text = norm_text.replace("\n", "\r\n")
else:
    final_text = norm_text

with open(path, "w", encoding="utf-8") as f:
    f.write(final_text)

print("Successfully removed EndToEndTestRunner from App.tsx!")

