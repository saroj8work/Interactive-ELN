import os

app_path = "frontend/src/App.tsx"
with open(app_path, "r", encoding="utf-8") as f:
    text = f.read()

crlf = "\r\n" in text
norm_text = text.replace("\r\n", "\n")

# 1. Remove previewData import
import_block = """import {
  MOCK_PREVIEW_USER,
  MOCK_PREVIEW_PROJECTS,
  MOCK_PREVIEW_EXPERIMENTS,
  MOCK_PREVIEW_ENTRIES,
  MOCK_PREVIEW_INVENTORY,
  MOCK_PREVIEW_SAMPLES,
} from "./previewData";
"""
assert import_block in norm_text, "import_block not found"
norm_text = norm_text.replace(import_block, "", 1)

# 2. Revert error state in NotebookApp
error_block = """  const isPreviewMode = Boolean(new URLSearchParams(window.location.search).get("preview"));
  const [errorState, setErrorState] = useState("");
  const error = isPreviewMode ? "" : errorState;
  const setError = useCallback((val: string) => {
    if (isPreviewMode) return;
    setErrorState(val);
  }, [isPreviewMode]);"""
target_error = """  const [error, setError] = useState("");"""
assert error_block in norm_text, "error_block not found"
norm_text = norm_text.replace(error_block, target_error, 1)

# 3. Remove preview effect in NotebookApp
preview_effect = """  useEffect(() => {
    const previewParam = new URLSearchParams(window.location.search).get("preview");
    if (!previewParam) return;
    setProjects(MOCK_PREVIEW_PROJECTS);
    setExperiments(MOCK_PREVIEW_EXPERIMENTS);
    setEntries(MOCK_PREVIEW_ENTRIES);
    setInventoryItems(MOCK_PREVIEW_INVENTORY);
    setSamples(MOCK_PREVIEW_SAMPLES);
    setSelectedProject(1);
    setSelectedExperiment(1);
    setSelectedEntry(1);
    if (previewParam === "e2e") {
      setE2eSuiteOpen(true);
    } else if (previewParam === "report") {
      setFormalReportOpen(true);
    } else if (previewParam === "chemsearch") {
      setChemSearchOpen(true);
    } else if (previewParam === "inventory") {
      setInventoryOpen(true);
    }
  }, []);

"""
assert preview_effect in norm_text, "preview_effect not found"
norm_text = norm_text.replace(preview_effect, "", 1)

# 4. Revert loadInventoryAndSamples
old_inv = """  const loadInventoryAndSamples = useCallback(async () => {
    if (new URLSearchParams(window.location.search).has("preview")) {
      setInventoryItems(MOCK_PREVIEW_INVENTORY);
      setSamples(MOCK_PREVIEW_SAMPLES);
      return;
    }
    try {"""
clean_inv = """  const loadInventoryAndSamples = useCallback(async () => {
    try {"""
assert old_inv in norm_text, "old_inv not found"
norm_text = norm_text.replace(old_inv, clean_inv, 1)

# 5. Revert loadProjects
old_proj = """  const loadProjects = useCallback(async () => {
    if (new URLSearchParams(window.location.search).has("preview")) {
      setProjects(MOCK_PREVIEW_PROJECTS);
      setSelectedProject(1);
      return;
    }
    try {"""
clean_proj = """  const loadProjects = useCallback(async () => {
    try {"""
assert old_proj in norm_text, "old_proj not found"
norm_text = norm_text.replace(old_proj, clean_proj, 1)

# 6. Revert experiments effect
old_exp = """  useEffect(() => {
    if (new URLSearchParams(window.location.search).has("preview")) {
      setExperiments(MOCK_PREVIEW_EXPERIMENTS);
      setSelectedExperiment((current) => current ?? 1);
      return;
    }
    if (selectedProject === null) {"""
clean_exp = """  useEffect(() => {
    if (selectedProject === null) {"""
assert old_exp in norm_text, "old_exp not found"
norm_text = norm_text.replace(old_exp, clean_exp, 1)

# 7. Revert entries effect
old_entry = """  useEffect(() => {
    if (new URLSearchParams(window.location.search).has("preview")) {
      setEntries(MOCK_PREVIEW_ENTRIES);
      setSelectedEntry((current) => current ?? 1);
      return;
    }
    if (selectedExperiment === null) {"""
clean_entry = """  useEffect(() => {
    if (selectedExperiment === null) {"""
assert old_entry in norm_text, "old_entry not found"
norm_text = norm_text.replace(old_entry, clean_entry, 1)

# 8. Revert AuthScreen demo button
old_demo_btn = """            <button
              className="button button-outline button-full"
              type="button"
              style={{ marginTop: "0.5rem" }}
              onClick={() => {
                window.location.search = "?preview=workspace";
              }}
            >
              Explore Interactive Demo & UI
            </button>
"""
assert old_demo_btn in norm_text, "old_demo_btn not found"
norm_text = norm_text.replace(old_demo_btn, "", 1)

# 9. Revert App()
old_app = """export default function App() {
  const previewParam = typeof window !== "undefined" ? new URLSearchParams(window.location.search).get("preview") : null;
  const [user, setUser] = useState<AuthUser | null>(previewParam ? MOCK_PREVIEW_USER : null);
  const [ready, setReady] = useState(Boolean(previewParam));
  const isInvitationPage = window.location.pathname === "/accept-invitation";
  const isPasswordResetPage = new URLSearchParams(
    window.location.hash.slice(1),
  ).has("password-reset-token");

  useEffect(() => {
    if (previewParam) return;
    if (isInvitationPage || isPasswordResetPage) {"""
clean_app = """export default function App() {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [ready, setReady] = useState(false);
  const isInvitationPage = window.location.pathname === "/accept-invitation";
  const isPasswordResetPage = new URLSearchParams(
    window.location.hash.slice(1),
  ).has("password-reset-token");

  useEffect(() => {
    if (isInvitationPage || isPasswordResetPage) {"""
assert old_app in norm_text, "old_app not found"
norm_text = norm_text.replace(old_app, clean_app, 1)

if crlf:
    final_text = norm_text.replace("\n", "\r\n")
else:
    final_text = norm_text

with open(app_path, "w", encoding="utf-8") as f:
    f.write(final_text)

print("Successfully restored frontend/src/App.tsx to clean production code!")

