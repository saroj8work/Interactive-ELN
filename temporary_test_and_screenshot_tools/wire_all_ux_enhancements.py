path = "frontend/src/App.tsx"
with open(path, "r", encoding="utf-8") as f:
    text = f.read()

crlf = "\r\n" in text
norm_text = text.replace("\r\n", "\n")

# 1. Add MentionAutocomplete import
old_import = 'import { LandingPage } from "./LandingPage";\n'
new_import = 'import { LandingPage } from "./LandingPage";\nimport { MentionAutocomplete } from "./MentionAutocomplete";\n'
assert old_import in norm_text, "LandingPage import not found"
norm_text = norm_text.replace(old_import, new_import, 1)

# 2. Add Theme, Sidebar, Bench Mode, and Autosave state in NotebookApp
old_state = """  const [inventoryItems, setInventoryItems] = useState<InventoryItem[]>([]);
  const [samples, setSamples] = useState<SampleRecord[]>([]);"""

new_state = """  const [inventoryItems, setInventoryItems] = useState<InventoryItem[]>([]);
  const [samples, setSamples] = useState<SampleRecord[]>([]);

  // UX Enhancements: Theme State
  const [theme, setTheme] = useState<"dark" | "light">(() =>
    typeof window !== "undefined" && localStorage.getItem("aura_theme") === "light" ? "light" : "dark"
  );
  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme);
    localStorage.setItem("aura_theme", theme);
  }, [theme]);

  // UX Enhancements: Sidebar Collapse & Ctrl+B shortcut
  const [sidebarCollapsed, setSidebarCollapsed] = useState<boolean>(() =>
    typeof window !== "undefined" && localStorage.getItem("aura_sidebar_collapsed") === "true"
  );
  useEffect(() => {
    localStorage.setItem("aura_sidebar_collapsed", String(sidebarCollapsed));
  }, [sidebarCollapsed]);

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "b") {
        e.preventDefault();
        setSidebarCollapsed((prev) => !prev);
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, []);

  // UX Enhancements: Glove-Friendly Bench Mode
  const [benchMode, setBenchMode] = useState<boolean>(() =>
    typeof window !== "undefined" && localStorage.getItem("aura_bench_mode") === "true"
  );
  useEffect(() => {
    document.documentElement.setAttribute("data-bench-mode", String(benchMode));
    localStorage.setItem("aura_bench_mode", String(benchMode));
  }, [benchMode]);

  // UX Enhancements: Continuous Autosave
  const [autosaveStatus, setAutosaveStatus] = useState<"saved" | "unsaved" | "saving" | null>(null);
  const [lastSavedTime, setLastSavedTime] = useState<string | null>(null);
  const autosaveTimerRef = useRef<number | null>(null);

  const handleEntryInputChange = useCallback(() => {
    setAutosaveStatus("unsaved");
    if (autosaveTimerRef.current) window.clearTimeout(autosaveTimerRef.current);
    autosaveTimerRef.current = window.setTimeout(async () => {
      const activeEntry = entries.find((item) => item.id === selectedEntry);
      if (!activeEntry) return;
      const titleEl = document.getElementById("entry-title") as HTMLInputElement | null;
      const contentEl = document.getElementById("entry-content") as HTMLTextAreaElement | null;
      if (!titleEl || !contentEl) return;
      setAutosaveStatus("saving");
      try {
        const updated = await api.updateEntry(
          activeEntry.id,
          titleEl.value.trim() || activeEntry.title,
          contentEl.value,
        );
        setEntries((items) => items.map((e) => (e.id === updated.id ? updated : e)));
        setAutosaveStatus("saved");
        const timeStr = new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
        setLastSavedTime(timeStr);
      } catch {
        setAutosaveStatus("unsaved");
      }
    }, 2500);
  }, [entries, selectedEntry]);"""

assert old_state in norm_text, "old_state not found"
norm_text = norm_text.replace(old_state, new_state, 1)

# 3. Update handleSaveEntry to update autosave status
old_handle_save = """      setNotice(`Saved ${formatDate(updated.updated_at)}.`);
      await loadProjects();"""

new_handle_save = """      setNotice(`Saved ${formatDate(updated.updated_at)}.`);
      setAutosaveStatus("saved");
      const timeStr = new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
      setLastSavedTime(timeStr);
      await loadProjects();"""

assert old_handle_save in norm_text, "old_handle_save not found"
norm_text = norm_text.replace(old_handle_save, new_handle_save, 1)

# 4. Update Sidebar to be collapsible and add collapse button
old_sidebar = """  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-mark">
            <img src="/app-icon.jpg" alt="Aura Lab" />
          </div>
          <div>
            <strong>Aura Lab</strong>
            <span>{t("Research workspace")}</span>
          </div>
        </div>"""

new_sidebar = """  return (
    <div className="app-shell">
      <aside className={`sidebar ${sidebarCollapsed ? "collapsed" : ""}`}>
        <div className="brand" style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
          <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
            <div className="brand-mark">
              <img src="/app-icon.jpg" alt="Aura Lab" />
            </div>
            <div>
              <strong>Aura Lab</strong>
              <span>{t("Research workspace")}</span>
            </div>
          </div>
          <button
            className="sidebar-collapse-btn"
            type="button"
            onClick={() => setSidebarCollapsed((c) => !c)}
            title={sidebarCollapsed ? "Expand sidebar (Ctrl+B)" : "Collapse sidebar (Ctrl+B)"}
          >
            {sidebarCollapsed ? "▶" : "◀"}
          </button>
        </div>"""

assert old_sidebar in norm_text, "old_sidebar not found"
norm_text = norm_text.replace(old_sidebar, new_sidebar, 1)

# 5. Add Theme toggle, Bench mode toggle, and sidebar expand in topbar-right
old_topbar = """          <div className="topbar-right">
            <div className="notification-menu">"""

new_topbar = """          <div className="topbar-right">
            <button
              className="sidebar-collapse-btn"
              type="button"
              onClick={() => setSidebarCollapsed((c) => !c)}
              title={sidebarCollapsed ? "Expand sidebar (Ctrl+B)" : "Collapse sidebar (Ctrl+B)"}
            >
              {sidebarCollapsed ? "▶ Expand" : "◀ Collapse"}
            </button>
            <button
              className="button button-outline"
              type="button"
              onClick={() => setTheme((curr) => (curr === "dark" ? "light" : "dark"))}
              title={theme === "dark" ? "Switch to Light Mode" : "Switch to Dark Mode"}
              style={{ display: "inline-flex", alignItems: "center", gap: 6 }}
            >
              {theme === "dark" ? "☀️ Light" : "🌙 Dark"}
            </button>
            <button
              className={`button button-outline ${benchMode ? "bench-mode-active" : ""}`}
              type="button"
              onClick={() => setBenchMode((curr) => !curr)}
              title="Toggle Glove-Friendly Benchtop Mode"
              style={{ display: "inline-flex", alignItems: "center", gap: 6 }}
            >
              🧤 {benchMode ? "Bench Mode: ON" : "Bench Mode"}
            </button>
            <div className="notification-menu">"""

assert old_topbar in norm_text, "old_topbar not found"
norm_text = norm_text.replace(old_topbar, new_topbar, 1)

# 6. Update entry title input, textarea, and footer with Autosave pill and MentionAutocomplete
old_entry_form = """                      <form className="entry-content-form" onSubmit={handleSaveEntry}>
                        <input
                          aria-label="Entry title"
                          className="entry-title-input"
                          defaultValue={activeEntry.title}
                          key={`${activeEntry.id}-${activeEntry.updated_at}-title`}
                          name="title"
                          required
                          maxLength={200}
                        />"""

new_entry_form = """                      <form className="entry-content-form" onSubmit={handleSaveEntry}>
                        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: "10px" }}>
                          <input
                            aria-label="Entry title"
                            id="entry-title"
                            className="entry-title-input"
                            defaultValue={activeEntry.title}
                            key={`${activeEntry.id}-${activeEntry.updated_at}-title`}
                            name="title"
                            onChange={handleEntryInputChange}
                            required
                            maxLength={200}
                            style={{ flex: 1 }}
                          />
                          {autosaveStatus && (
                            <span className={`autosave-pill status-${autosaveStatus}`}>
                              <span className="autosave-dot" />
                              {autosaveStatus === "saved" && `Saved${lastSavedTime ? ` (${lastSavedTime})` : ""}`}
                              {autosaveStatus === "saving" && "Saving draft..."}
                              {autosaveStatus === "unsaved" && "Unsaved changes"}
                            </span>
                          )}
                        </div>"""

assert old_entry_form in norm_text, "old_entry_form not found"
norm_text = norm_text.replace(old_entry_form, new_entry_form, 1)

# Update textarea with onChange
old_textarea = """                            <textarea
                              aria-label="Entry content"
                              id="entry-content"
                              key={`${activeEntry.id}-${activeEntry.updated_at}-content`}
                              name="content"
                              defaultValue={activeEntry.content}
                              placeholder="Record your observations, methods, results, and next steps..."
                              maxLength={100_000}
                            />"""

new_textarea = """                            <textarea
                              aria-label="Entry content"
                              id="entry-content"
                              key={`${activeEntry.id}-${activeEntry.updated_at}-content`}
                              name="content"
                              defaultValue={activeEntry.content}
                              onChange={handleEntryInputChange}
                              placeholder="Record your observations, methods, results, and next steps..."
                              maxLength={100_000}
                            />"""

assert old_textarea in norm_text, "old_textarea not found"
norm_text = norm_text.replace(old_textarea, new_textarea, 1)

# Mount MentionAutocomplete under the form
old_form_close = """                        <div className="editor-footer">
                          <span>Changes are saved when you select Save entry.</span>
                          <button className="button button-primary" type="submit">Save entry</button>
                        </div>
                      </form>"""

new_form_close = """                        <div className="editor-footer" style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                            {autosaveStatus ? (
                              <span className={`autosave-pill status-${autosaveStatus}`}>
                                <span className="autosave-dot" />
                                {autosaveStatus === "saved" && `Autosaved${lastSavedTime ? ` at ${lastSavedTime}` : ""}`}
                                {autosaveStatus === "saving" && "Saving draft..."}
                                {autosaveStatus === "unsaved" && "Unsaved changes"}
                              </span>
                            ) : (
                              <span style={{ fontSize: 11, color: "var(--text-secondary, #64748b)" }}>Autosaves continuously</span>
                            )}
                          </div>
                          <button className="button button-primary" type="submit">Save entry</button>
                        </div>
                      </form>
                      <MentionAutocomplete
                        textareaId="entry-content"
                        inventoryItems={inventoryItems}
                        samples={samples}
                        experiments={experiments}
                      />"""

assert old_form_close in norm_text, "old_form_close not found"
norm_text = norm_text.replace(old_form_close, new_form_close, 1)

if crlf:
    final_text = norm_text.replace("\n", "\r\n")
else:
    final_text = norm_text

with open(path, "w", encoding="utf-8") as f:
    f.write(final_text)

print("Successfully wired all 6 UX enhancements in App.tsx!")
