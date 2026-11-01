import os

path = "frontend/src/App.tsx"
with open(path, "r", encoding="utf-8") as f:
    text = f.read()

# Normalize line endings to \n for uniform patching, we can save back
crlf = "\r\n" in text
lines = text.splitlines()

# 1. App()
old_app = """export default function App() {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [ready, setReady] = useState(false);
  const isInvitationPage = window.location.pathname === "/accept-invitation";
  const isPasswordResetPage = new URLSearchParams(
    window.location.hash.slice(1),
  ).has("password-reset-token");

  useEffect(() => {
    if (isInvitationPage || isPasswordResetPage) {"""

new_app = """export default function App() {
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

# 2. loadInventoryAndSamples
old_inv = """  const [inventoryItems, setInventoryItems] = useState<InventoryItem[]>([]);
  const [samples, setSamples] = useState<SampleRecord[]>([]);

  const loadInventoryAndSamples = useCallback(async () => {
    try {"""

new_inv = """  const [inventoryItems, setInventoryItems] = useState<InventoryItem[]>([]);
  const [samples, setSamples] = useState<SampleRecord[]>([]);

  useEffect(() => {
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

  const loadInventoryAndSamples = useCallback(async () => {
    if (new URLSearchParams(window.location.search).has("preview")) {
      setInventoryItems(MOCK_PREVIEW_INVENTORY);
      setSamples(MOCK_PREVIEW_SAMPLES);
      return;
    }
    try {"""

# 3. loadProjects
old_proj = """  const loadProjects = useCallback(async () => {
    try {"""

new_proj = """  const loadProjects = useCallback(async () => {
    if (new URLSearchParams(window.location.search).has("preview")) {
      setProjects(MOCK_PREVIEW_PROJECTS);
      setSelectedProject(1);
      return;
    }
    try {"""

# 4. experiments effect
old_exp_eff = """  useEffect(() => {
    if (selectedProject === null) {
      setExperiments([]);
      setSelectedExperiment(null);
      return;
    }
    let active = true;
    api
      .experiments(selectedProject)"""

new_exp_eff = """  useEffect(() => {
    if (new URLSearchParams(window.location.search).has("preview")) {
      setExperiments(MOCK_PREVIEW_EXPERIMENTS);
      setSelectedExperiment((current) => current ?? 1);
      return;
    }
    if (selectedProject === null) {
      setExperiments([]);
      setSelectedExperiment(null);
      return;
    }
    let active = true;
    api
      .experiments(selectedProject)"""

# 5. entries effect
old_entry_eff = """  useEffect(() => {
    if (selectedExperiment === null) {
      setEntries([]);
      setSelectedEntry(null);
      return;
    }
    let active = true;
    api
      .entries(selectedExperiment)"""

new_entry_eff = """  useEffect(() => {
    if (new URLSearchParams(window.location.search).has("preview")) {
      setEntries(MOCK_PREVIEW_ENTRIES);
      setSelectedEntry((current) => current ?? 1);
      return;
    }
    if (selectedExperiment === null) {
      setEntries([]);
      setSelectedEntry(null);
      return;
    }
    let active = true;
    api
      .entries(selectedExperiment)"""

# 6. AuthScreen demo button
old_auth_btn = """            <button className="button button-primary button-full" disabled={busy} type="submit">
              {busy
                ? recoveryMode ? "Requesting link…" : "Signing in…"
                : recoveryMode ? "Send reset link" : "Sign in"}
            </button>"""

new_auth_btn = """            <button className="button button-primary button-full" disabled={busy} type="submit">
              {busy
                ? recoveryMode ? "Requesting link…" : "Signing in…"
                : recoveryMode ? "Send reset link" : "Sign in"}
            </button>
            <button
              className="button button-outline button-full"
              type="button"
              style={{ marginTop: "0.5rem" }}
              onClick={() => {
                window.location.search = "?preview=workspace";
              }}
            >
              Explore Interactive Demo & UI
            </button>"""

norm_text = text.replace("\r\n", "\n")

for old, new in [
    (old_app, new_app),
    (old_inv, new_inv),
    (old_proj, new_proj),
    (old_exp_eff, new_exp_eff),
    (old_entry_eff, new_entry_eff),
    (old_auth_btn, new_auth_btn),
]:
    assert old in norm_text, f"Target not found: {old[:40]}"
    norm_text = norm_text.replace(old, new, 1)

if crlf:
    final_text = norm_text.replace("\n", "\r\n")
else:
    final_text = norm_text

with open(path, "w", encoding="utf-8") as f:
    f.write(final_text)

print("Successfully updated frontend/src/App.tsx")

