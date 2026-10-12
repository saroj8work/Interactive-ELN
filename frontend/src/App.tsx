import { FormEvent, useCallback, useEffect, useState } from "react";
import { api, authApi, AuthUser, setAccessToken } from "./api";
import type {
  ActivityEvent,
  EntryAttachment,
  EntryRevision,
  EquipmentBooking,
  EquipmentResource,
  Experiment,
  LabTask,
  InventoryItem,
  NotebookTemplate,
  NotebookEntry,
  Project,
  RecordSignature,
  SearchHit,
  SampleRecord,
} from "./types";

function formatDate(value: string): string {
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

function NotebookApp({ user, onLogout }: { user: AuthUser; onLogout: () => void }) {
  const [projects, setProjects] = useState<Project[]>([]);
  const [experiments, setExperiments] = useState<Experiment[]>([]);
  const [entries, setEntries] = useState<NotebookEntry[]>([]);
  const [activity, setActivity] = useState<ActivityEvent[]>([]);
  const [selectedProject, setSelectedProject] = useState<number | null>(null);
  const [selectedExperiment, setSelectedExperiment] = useState<number | null>(null);
  const [selectedEntry, setSelectedEntry] = useState<number | null>(null);
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");
  const [adminOpen, setAdminOpen] = useState(false);
  const [projectAccessRole, setProjectAccessRole] = useState<
    "admin" | "owner" | "editor" | "viewer" | null
  >(null);
  const [projectAccessOpen, setProjectAccessOpen] = useState(false);
  const [inventoryOpen, setInventoryOpen] = useState(false);
  const [equipmentOpen, setEquipmentOpen] = useState(false);
  const [templatesOpen, setTemplatesOpen] = useState(false);
  const [templates, setTemplates] = useState<NotebookTemplate[]>([]);
  const [searchResults, setSearchResults] = useState<SearchHit[]>([]);
  const [searchOpen, setSearchOpen] = useState(false);
  const [attachments, setAttachments] = useState<EntryAttachment[]>([]);
  const [revisions, setRevisions] = useState<EntryRevision[]>([]);
  const [historyOpen, setHistoryOpen] = useState(false);
  const [entryTags, setEntryTags] = useState<string[]>([]);
  const [entryTagDraft, setEntryTagDraft] = useState("");
  const [entrySignatures, setEntrySignatures] = useState<RecordSignature[]>([]);
  const [tasksOpen, setTasksOpen] = useState(false);
  const [auditNotice, setAuditNotice] = useState("");

  const loadProjects = useCallback(async () => {
    try {
      const [loadedProjects, loadedActivity] = await Promise.all([api.projects(), api.activity()]);
      setProjects(loadedProjects);
      setActivity(loadedActivity);
      setSelectedProject((current) =>
        current !== null && loadedProjects.some((project) => project.id === current)
          ? current
          : loadedProjects[0]?.id ?? null,
      );
      setError("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to load notebook.");
    }
  }, []);

  useEffect(() => {
    void loadProjects();
  }, [loadProjects]);

  const loadTemplates = useCallback(async () => {
    try {
      setTemplates(await api.templates());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to load notebook templates.");
    }
  }, []);

  useEffect(() => {
    void loadTemplates();
  }, [loadTemplates]);

  useEffect(() => {
    if (selectedProject === null) {
      setExperiments([]);
      setSelectedExperiment(null);
      return;
    }
    let active = true;
    api
      .experiments(selectedProject)
      .then((items) => {
        if (!active) return;
        setExperiments(items);
        setSelectedExperiment((current) =>
          current !== null && items.some((experiment) => experiment.id === current)
            ? current
            : items[0]?.id ?? null,
        );
      })
      .catch((err: unknown) => {
        if (active) setError(err instanceof Error ? err.message : "Unable to load experiments.");
      });
    return () => {
      active = false;
    };
  }, [selectedProject]);

  useEffect(() => {
    if (selectedProject === null) {
      setProjectAccessRole(null);
      setProjectAccessOpen(false);
      return;
    }
    let active = true;
    api
      .projectAccess(selectedProject)
      .then((access) => {
        if (active) setProjectAccessRole(access.role);
      })
      .catch((err: unknown) => {
        if (active) setError(err instanceof Error ? err.message : "Unable to load project access.");
      });
    return () => {
      active = false;
    };
  }, [selectedProject]);

  useEffect(() => {
    if (selectedExperiment === null) {
      setEntries([]);
      setSelectedEntry(null);
      return;
    }
    let active = true;
    api
      .entries(selectedExperiment)
      .then((items) => {
        if (!active) return;
        setEntries(items);
        setSelectedEntry((current) =>
          current !== null && items.some((entry) => entry.id === current)
            ? current
            : items[0]?.id ?? null,
        );
      })
      .catch((err: unknown) => {
        if (active) setError(err instanceof Error ? err.message : "Unable to load entries.");
      });
    return () => {
      active = false;
    };
  }, [selectedExperiment]);

  useEffect(() => {
    if (selectedEntry === null) {
      setAttachments([]);
      setRevisions([]);
      setEntryTags([]);
      setEntryTagDraft("");
      setEntrySignatures([]);
      setHistoryOpen(false);
      return;
    }
    let active = true;
    api
      .attachments(selectedEntry)
      .then((items) => {
        if (active) setAttachments(items);
      })
      .catch((err: unknown) => {
        if (active) setError(err instanceof Error ? err.message : "Unable to load attachments.");
      });
    api
      .recordTags("entry", selectedEntry)
      .then((tagSet) => {
        if (!active) return;
        setEntryTags(tagSet.tags);
        setEntryTagDraft(tagSet.tags.join(", "));
      })
      .catch((err: unknown) => {
        if (active) setError(err instanceof Error ? err.message : "Unable to load entry tags.");
      });
    api
      .entrySignatures(selectedEntry)
      .then((items) => {
        if (active) setEntrySignatures(items);
      })
      .catch((err: unknown) => {
        if (active) setError(err instanceof Error ? err.message : "Unable to load entry signatures.");
      });
    return () => {
      active = false;
    };
  }, [selectedEntry]);

  const selectedProjectData = projects.find((project) => project.id === selectedProject);
  const selectedExperimentData = experiments.find(
    (experiment) => experiment.id === selectedExperiment,
  );
  const activeEntry = entries.find((entry) => entry.id === selectedEntry);

  async function handleCreateProject(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    try {
      const project = await api.createProject(
        String(form.get("name") ?? ""),
        String(form.get("description") ?? ""),
      );
      await loadProjects();
      setSelectedProject(project.id);
      setNotice("Project created.");
      event.currentTarget.reset();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to create project.");
    }
  }

  async function handleProjectExport(format: "json" | "csv") {
    if (selectedProject === null) return;
    try {
      await api.exportProject(selectedProject, format);
      setError("");
      setNotice(`Project ${format.toUpperCase()} export downloaded.`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to export project.");
    }
  }

  async function handleProjectBundleExport() {
    if (selectedProject === null) return;
    try {
      await api.exportProjectBundle(selectedProject);
      setNotice("Attachment-inclusive project bundle downloaded.");
      setError("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to export project bundle.");
    }
  }

  async function handleProjectImport(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (selectedProject === null) return;
    const form = event.currentTarget;
    const file = new FormData(form).get("bundle");
    if (!(file instanceof File) || file.size === 0) {
      setError("Choose a project JSON or ZIP bundle to import.");
      return;
    }
    try {
      const result = await api.importProject(selectedProject, file);
      await loadProjects();
      const importedExperiments = await api.experiments(selectedProject);
      setExperiments(importedExperiments);
      setSelectedExperiment(importedExperiments[0]?.id ?? null);
      setNotice(
        `Imported ${result.experiments_imported} experiments, ${result.entries_imported} entries, ${result.attachments_imported} attachments, and ${result.tasks_imported} tasks.`,
      );
      setError("");
      form.reset();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to import project bundle.");
    }
  }

  async function handleEntrySignature(
    meaning: RecordSignature["meaning"],
    comment: string,
  ): Promise<boolean> {
    if (selectedEntry === null) return false;
    try {
      const signature = await api.signEntry(selectedEntry, meaning, comment);
      setEntrySignatures((current) => [...current, signature]);
      setNotice(`Record signed as ${meaning}.`);
      setError("");
      return true;
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to sign notebook record.");
      return false;
    }
  }

  async function handleCreateExperiment(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (selectedProject === null) return;
    const form = new FormData(event.currentTarget);
    try {
      const experiment = await api.createExperiment(
        selectedProject,
        String(form.get("name") ?? ""),
        String(form.get("description") ?? ""),
      );
      setExperiments((items) => [experiment, ...items]);
      setSelectedExperiment(experiment.id);
      setNotice("Experiment created.");
      event.currentTarget.reset();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to create experiment.");
    }
  }

  async function handleExperimentStatusChange(status: Experiment["status"]) {
    if (selectedExperiment === null) return;
    try {
      const updated = await api.updateExperimentStatus(selectedExperiment, status);
      setExperiments((items) =>
        items.map((experiment) =>
          experiment.id === updated.id ? updated : experiment,
        ),
      );
      setNotice(`Experiment marked ${status.replace("_", " ")}.`);
      setError("");
      await loadProjects();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to update experiment status.");
    }
  }

  async function handleCreateEntry() {
    if (selectedExperiment === null) return;
    try {
      const entry = await api.createEntry(selectedExperiment, "New notebook entry", "");
      setEntries((items) => [entry, ...items]);
      setSelectedEntry(entry.id);
      setNotice("Notebook entry created.");
      await loadProjects();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to create entry.");
    }
  }

  async function handleSaveEntry(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (selectedEntry === null) return;
    const form = new FormData(event.currentTarget);
    try {
      const updated = await api.updateEntry(
        selectedEntry,
        String(form.get("title") ?? ""),
        String(form.get("content") ?? ""),
      );
      setEntries((items) => items.map((entry) => (entry.id === updated.id ? updated : entry)));
      setNotice(`Saved ${formatDate(updated.updated_at)}.`);
      await loadProjects();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to save entry.");
    }
  }

  async function handleApplyTemplate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (selectedEntry === null) return;
    const form = new FormData(event.currentTarget);
    const templateId = Number(form.get("template_id"));
    if (!Number.isInteger(templateId) || templateId < 1) return;
    try {
      const updated = await api.applyTemplate(selectedEntry, templateId);
      setEntries((items) => items.map((entry) => (entry.id === updated.id ? updated : entry)));
      setNotice("Entry template applied. Review the entry and save any edits.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to apply template.");
    }
  }

  async function handleUploadAttachment(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (selectedEntry === null) return;
    const formElement = event.currentTarget;
    const file = (new FormData(formElement).get("file") as File | null) ?? null;
    if (!file) return;
    try {
      await api.uploadAttachment(selectedEntry, file);
      formElement.reset();
      setAttachments(await api.attachments(selectedEntry));
      setNotice("Attachment uploaded.");
      setError("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to upload attachment.");
    }
  }

  async function handleExportEntry() {
    if (selectedEntry === null) return;
    try {
      await api.exportEntry(selectedEntry);
      setError("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to export notebook entry.");
    }
  }

  async function toggleEntryHistory() {
    if (selectedEntry === null) return;
    if (!historyOpen) {
      try {
        setRevisions(await api.entryRevisions(selectedEntry));
        setError("");
      } catch (err) {
        setError(err instanceof Error ? err.message : "Unable to load entry history.");
        return;
      }
    }
    setHistoryOpen((open) => !open);
  }

  async function restoreRevision(revisionId: number) {
    if (selectedEntry === null) return;
    try {
      const restored = await api.restoreEntryRevision(selectedEntry, revisionId);
      setEntries((current) =>
        current.map((entry) => (entry.id === restored.id ? restored : entry)),
      );
      setRevisions(await api.entryRevisions(selectedEntry));
      setNotice("Revision restored. The previous content remains in history.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to restore revision.");
    }
  }

  async function handleSaveEntryTags(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (selectedEntry === null) return;
    try {
      const result = await api.updateRecordTags(
        "entry",
        selectedEntry,
        entryTagDraft.split(","),
      );
      setEntryTags(result.tags);
      setEntryTagDraft(result.tags.join(", "));
      setNotice("Entry tags updated.");
      setError("");
      await loadProjects();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to update entry tags.");
    }
  }

  const latestActivity = activity.slice(0, 5);

  async function handleSearch(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const query = String(form.get("query") ?? "").trim();
    if (query.length < 2) {
      setError("Search with at least two characters.");
      return;
    }
    try {
      setSearchResults(await api.search(query));
      setSearchOpen(true);
      setError("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to search notebook records.");
    }
  }

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-mark">i</div>
          <div>
            <strong>Interactive ELN</strong>
            <span>Research workspace</span>
          </div>
        </div>
        <div className="workspace-label">WORKSPACE</div>
        <div className="sidebar-heading">
          <span>Projects</span>
          <span className="count-pill">{projects.length}</span>
        </div>
        <nav className="project-nav" aria-label="Projects">
          {projects.map((project) => (
            <button
              className={`project-link ${selectedProject === project.id ? "selected" : ""}`}
              key={project.id}
              onClick={() => setSelectedProject(project.id)}
            >
              <span className="project-dot" />
              <span>{project.name}</span>
            </button>
          ))}
          {projects.length === 0 && <p className="empty-hint">Create your first project below.</p>}
        </nav>
        <form className="quick-create" onSubmit={handleCreateProject}>
          <label htmlFor="project-name">New project</label>
          <input id="project-name" name="name" placeholder="Project name" required maxLength={160} />
          <textarea name="description" placeholder="Short description (optional)" rows={2} />
          <button className="button button-primary button-full" type="submit">
            Create project
          </button>
        </form>
        <div className="sidebar-footer">
          <span className="avatar">R</span>
          <span>Researcher</span>
          <span className="online-dot" />
        </div>
      </aside>

      <main className="main-area">
        <header className="topbar">
          <div className="breadcrumbs">
            <span>Workspace</span>
            <span className="crumb-divider">/</span>
            <strong>{selectedProjectData?.name ?? "Your notebook"}</strong>
          </div>
          <div className="topbar-right">
            <form className="global-search" onSubmit={handleSearch}>
              <input name="query" placeholder="Search records…" aria-label="Search records" maxLength={100} />
              <button className="button button-outline" type="submit">Search</button>
            </form>
            <span className="environment-badge">LOCAL WORKSPACE</span>
            <button className="button button-outline" onClick={() => setInventoryOpen((open) => !open)}>
              Lab inventory
            </button>
            <button className="button button-outline" onClick={() => setTemplatesOpen((open) => !open)}>
              Templates
            </button>
            <button className="button button-outline" onClick={() => setEquipmentOpen((open) => !open)}>
              Equipment
            </button>
            {user.role === "admin" && (
              <button className="button button-outline" onClick={() => setAdminOpen((open) => !open)}>
                Organization admin
              </button>
            )}
            {selectedProjectData &&
              (projectAccessRole === "admin" || projectAccessRole === "owner") && (
                <button
                  className="button button-outline"
                  onClick={() => setProjectAccessOpen((open) => !open)}
                >
                  Project access
                </button>
              )}
            <span className="signed-in-user">{user.display_name}</span>
            {user.role === "admin" && (
              <button
                className="button button-outline"
                onClick={() => {
                  void api.verifyAuditChain()
                    .then((result) => setAuditNotice(
                      result.valid
                        ? `Audit chain verified (${result.checked_events} events).`
                        : `Audit chain integrity check failed (${result.checked_events} events checked).`,
                    ))
                    .catch((err: unknown) => setError(
                      err instanceof Error ? err.message : "Unable to verify audit chain.",
                    ));
                }}
              >
                Verify audit chain
              </button>
            )}
            <button className="button button-outline" onClick={onLogout}>Sign out</button>
            <span className="avatar avatar-small">R</span>
          </div>
        </header>

        {error && (
          <div className="notice notice-error" role="alert">
            {error}
            <button aria-label="Dismiss error" onClick={() => setError("")}>×</button>
          </div>
        )}
        {auditNotice && (
          <div className="notice notice-success" role="status">
            {auditNotice}
            <button aria-label="Dismiss audit notice" onClick={() => setAuditNotice("")}>×</button>
          </div>
        )}
        {notice && (
          <div className="notice notice-success" role="status">
            {notice}
            <button aria-label="Dismiss notice" onClick={() => setNotice("")}>×</button>
          </div>
        )}
        {adminOpen && user.role === "admin" && (
          <AdminPanel
            currentUserId={user.id}
            onClose={() => setAdminOpen(false)}
          />
        )}
        {projectAccessOpen && selectedProjectData && (
          <ProjectAccessPanel
            key={selectedProjectData.id}
            projectId={selectedProjectData.id}
            onClose={() => setProjectAccessOpen(false)}
          />
        )}
        {inventoryOpen && (
          <InventoryPanel
            projects={projects}
            onClose={() => setInventoryOpen(false)}
          />
        )}
        {equipmentOpen && (
          <EquipmentPanel
            projects={projects}
            user={user}
            onClose={() => setEquipmentOpen(false)}
          />
        )}
        {templatesOpen && (
          <TemplatePanel
            user={user}
            templates={templates}
            projects={projects}
            onRefresh={loadTemplates}
            onProtocolStarted={async (experiment) => {
              await loadProjects();
              setSelectedProject(experiment.project_id);
              setExperiments((items) => [experiment, ...items]);
              setSelectedExperiment(experiment.id);
              setNotice("Protocol started as a new experiment.");
            }}
            onClose={() => setTemplatesOpen(false)}
          />
        )}
        {searchOpen && (
          <section className="search-results-panel" aria-label="Search results">
            <header>
              <strong>Search results</strong>
              <button className="button button-outline" onClick={() => setSearchOpen(false)}>Close</button>
            </header>
            {searchResults.length ? (
              <ul>
                {searchResults.map((hit) => (
                  <li key={`${hit.entity_type}-${hit.entity_id}`}>
                    <span className="status-chip">{hit.entity_type}</span>
                    <div><strong>{hit.title}</strong><small>{hit.detail}</small></div>
                    {hit.entity_type === "project" && (
                      <button className="button button-outline" onClick={() => {
                        setSelectedProject(hit.entity_id);
                        setSearchOpen(false);
                      }}>Open</button>
                    )}
                  </li>
                ))}
              </ul>
            ) : <p className="empty-hint">No matching records.</p>}
          </section>
        )}

        {!selectedProjectData ? (
          <section className="welcome-panel">
            <div className="welcome-icon">✳</div>
            <p className="eyebrow">YOUR DIGITAL LAB NOTEBOOK</p>
            <h1>A clear record of every discovery.</h1>
            <p>Create a project to organize experiments, methods, and research notes in one place.</p>
          </section>
        ) : (
          <div className="content-grid">
            <section className="work-column">
              <div className="page-heading">
                <div>
                  <p className="eyebrow">PROJECT</p>
                  <h1>{selectedProjectData.name}</h1>
                  <p className="muted">{selectedProjectData.description || "A shared space for your research."}</p>
                </div>
                <div className="project-export-actions">
                  <button
                    className="button button-outline"
                    type="button"
                    onClick={() => setTasksOpen((open) => !open)}
                  >
                    {tasksOpen ? "Hide tasks" : "Tasks"}
                  </button>
                  <button
                    className="button button-outline"
                    type="button"
                    onClick={() => void handleProjectExport("json")}
                  >
                    Export JSON
                  </button>
                  <button
                    className="button button-outline"
                    type="button"
                    onClick={() => void handleProjectExport("csv")}
                  >
                    Export CSV
                  </button>
                  <button
                    className="button button-outline"
                    type="button"
                    onClick={() => void handleProjectBundleExport()}
                  >
                    Export ZIP
                  </button>
                  {projectAccessRole !== null && projectAccessRole !== "viewer" && (
                    <form className="project-import-form" onSubmit={handleProjectImport}>
                      <input
                        aria-label="Import project JSON or ZIP"
                        name="bundle"
                        type="file"
                        accept=".json,.zip,application/json,application/zip"
                        required
                      />
                      <button className="button button-outline" type="submit">
                        Import
                      </button>
                    </form>
                  )}
                </div>
              </div>
              {tasksOpen && selectedProject !== null && (
                <TaskPanel
                  projectId={selectedProject}
                  writable={projectAccessRole !== null && projectAccessRole !== "viewer"}
                />
              )}

              <div className="section-heading">
                <div>
                  <h2>Experiments</h2>
                  <p>Organize your work into focused investigations.</p>
                </div>
                <span className="count-pill">{experiments.length}</span>
              </div>

              <div className="experiment-list">
                {experiments.map((experiment) => (
                  <button
                    className={`experiment-card ${selectedExperiment === experiment.id ? "active" : ""}`}
                    key={experiment.id}
                    onClick={() => setSelectedExperiment(experiment.id)}
                  >
                    <span className="experiment-icon">⌬</span>
                    <span className="experiment-copy">
                      <strong>{experiment.name}</strong>
                      <small>{experiment.description || "No description added"}</small>
                    </span>
                    <span className={`status-chip status-${experiment.status}`}>
                      {experiment.status.replace("_", " ")}
                    </span>
                  </button>
                ))}
                {experiments.length === 0 && (
                  <div className="inline-empty">No experiments yet. Start with the form below.</div>
                )}
              </div>

              <form className="inline-form" onSubmit={handleCreateExperiment}>
                <input name="name" placeholder="New experiment name" required maxLength={160} />
                <input name="description" placeholder="Brief description (optional)" maxLength={5000} />
                <button className="button button-outline" type="submit">Add experiment</button>
              </form>

              {selectedExperimentData && (
                <section className="notebook-section">
                  <div className="section-heading notebook-heading">
                    <div>
                      <p className="eyebrow">EXPERIMENT NOTEBOOK</p>
                      <h2>{selectedExperimentData.name}</h2>
                    </div>
                    <div className="experiment-actions">
                      <label>
                        Status
                        <select
                          value={selectedExperimentData.status}
                          disabled={
                            projectAccessRole === null || projectAccessRole === "viewer"
                          }
                          onChange={(event) =>
                            event.target.value === "in_progress" ||
                            event.target.value === "completed" ||
                            event.target.value === "archived"
                              ? void handleExperimentStatusChange(event.target.value)
                              : undefined
                          }
                        >
                          <option value="in_progress">In progress</option>
                          <option value="completed">Completed</option>
                          <option value="archived">Archived</option>
                        </select>
                      </label>
                      <button
                        className="button button-primary"
                        onClick={() => void handleCreateEntry()}
                        disabled={
                          projectAccessRole === null || projectAccessRole === "viewer"
                        }
                      >
                        <span>＋</span> New entry
                      </button>
                    </div>
                  </div>
                  <div className="notebook-layout">
                    <nav className="entry-list" aria-label="Notebook entries">
                      {entries.map((entry) => (
                        <button
                          className={`entry-link ${selectedEntry === entry.id ? "selected" : ""}`}
                          key={entry.id}
                          onClick={() => setSelectedEntry(entry.id)}
                        >
                          <strong>{entry.title}</strong>
                          <small>{formatDate(entry.updated_at)}</small>
                        </button>
                      ))}
                      {entries.length === 0 && <p className="empty-hint">Your notes will appear here.</p>}
                    </nav>
                    {activeEntry ? (
                      <div className="entry-editor-wrapper">
                      <form className="template-apply-form" onSubmit={handleApplyTemplate}>
                        <select name="template_id" defaultValue="">
                          <option value="">Apply entry template…</option>
                          {templates.filter((template) => template.template_kind === "entry").map((template) => (
                            <option key={template.id} value={template.id}>{template.name}</option>
                          ))}
                        </select>
                        <button className="button button-outline" type="submit" disabled={!templates.some((template) => template.template_kind === "entry")}>
                          Apply template
                        </button>
                      </form>
                      <div className="entry-editor">
                        <div className="editor-meta">
                          <span className="record-indicator"><span /> Notebook record</span>
                          <span>Updated {formatDate(activeEntry.updated_at)}</span>
                        </div>
                        <form className="entry-tags-form" onSubmit={handleSaveEntryTags}>
                          <label htmlFor="entry-tags">Tags</label>
                          <input
                            id="entry-tags"
                            value={entryTagDraft}
                            onChange={(event) => setEntryTagDraft(event.target.value)}
                            placeholder="cell culture, assay (comma separated)"
                            maxLength={840}
                          />
                          <button
                            className="button button-outline"
                            type="submit"
                            disabled={
                              projectAccessRole === null || projectAccessRole === "viewer"
                            }
                          >
                            Save tags
                          </button>
                        </form>
                        {entryTags.length > 0 && (
                          <div className="entry-tag-list" aria-label="Entry tags">
                            {entryTags.map((tag) => <span key={tag}>{tag}</span>)}
                          </div>
                        )}
                        <section className="signature-panel" aria-label="Electronic signature foundation">
                          <strong>Record signatures</strong>
                          <p>
                            A signature records your authenticated account, intent, timestamp, and a digest
                            of this entry. This foundation is not validated or regulatory-compliant.
                          </p>
                          <form
                            className="signature-form"
                            onSubmit={(event) => {
                              event.preventDefault();
                              const form = event.currentTarget;
                              const values = new FormData(form);
                              const meaning = String(values.get("meaning"));
                              if (
                                meaning === "authored" ||
                                meaning === "reviewed" ||
                                meaning === "approved"
                              ) {
                                void handleEntrySignature(
                                  meaning,
                                  String(values.get("comment") ?? ""),
                                ).then((signed) => {
                                  if (signed) form.reset();
                                });
                              }
                            }}
                          >
                            <select name="meaning" aria-label="Signature meaning" defaultValue="reviewed">
                              <option value="authored">Authored</option>
                              <option value="reviewed">Reviewed</option>
                              <option value="approved">Approved</option>
                            </select>
                            <input name="comment" maxLength={500} placeholder="Comment (optional)" />
                            <label>
                              <input name="confirm" type="checkbox" required />
                              I intend to apply this signature to the current record.
                            </label>
                            <button
                              className="button button-outline"
                              type="submit"
                              disabled={projectAccessRole === null || projectAccessRole === "viewer"}
                            >
                              Sign record
                            </button>
                          </form>
                          {entrySignatures.length > 0 && (
                            <ul className="signature-list">
                              {entrySignatures.map((signature) => (
                                <li key={signature.id}>
                                  <span>
                                    <strong>{signature.meaning}</strong> · user #{signature.signed_by_user_id}
                                    <small>{formatDate(signature.created_at)} · SHA-256 {signature.record_sha256.slice(0, 12)}…</small>
                                  </span>
                                </li>
                              ))}
                            </ul>
                          )}
                        </section>
                        <div className="attachment-tools">
                          <form className="attachment-upload-form" onSubmit={handleUploadAttachment}>
                            <input name="file" type="file" required aria-label="Choose a file to attach" />
                            <button className="button button-outline" type="submit">Attach file</button>
                          </form>
                          <button className="button button-outline" type="button" onClick={() => void handleExportEntry()}>
                            Export entry
                          </button>
                          <button className="button button-outline" type="button" onClick={() => void toggleEntryHistory()}>
                            {historyOpen ? "Hide history" : "History"}
                          </button>
                        </div>
                        {historyOpen && (
                          <div className="revision-list" aria-label="Entry version history">
                            {revisions.map((revision) => (
                              <article key={revision.id}>
                                <div>
                                  <strong>Revision {revision.revision_number}: {revision.title}</strong>
                                  <small>{formatDate(revision.created_at)} · user #{revision.changed_by_user_id}</small>
                                </div>
                                <button
                                  className="button button-outline"
                                  type="button"
                                  onClick={() => void restoreRevision(revision.id)}
                                >
                                  Restore
                                </button>
                              </article>
                            ))}
                            {revisions.length === 0 && <small>No saved revisions yet.</small>}
                          </div>
                        )}
                        {attachments.length > 0 && (
                          <ul className="attachment-list" aria-label="Entry attachments">
                            {attachments.map((attachment) => (
                              <li key={attachment.id}>
                                <button
                                  className="attachment-download"
                                  type="button"
                                  onClick={() => void api.downloadAttachment(attachment).catch((err: unknown) =>
                                    setError(err instanceof Error ? err.message : "Unable to download attachment."),
                                  )}
                                >
                                  {attachment.original_filename}
                                </button>
                                <small>{(attachment.size_bytes / 1024).toFixed(1)} KB</small>
                              </li>
                            ))}
                          </ul>
                        )}
                      </div>
                      <form className="entry-content-form" onSubmit={handleSaveEntry}>
                        <input
                          aria-label="Entry title"
                          className="entry-title-input"
                          defaultValue={activeEntry.title}
                          key={`${activeEntry.id}-${activeEntry.updated_at}-title`}
                          name="title"
                          required
                          maxLength={200}
                        />
                        <label className="editor-label" htmlFor="entry-content">OBSERVATIONS &amp; NOTES</label>
                        <textarea
                          aria-label="Entry content"
                          id="entry-content"
                          key={`${activeEntry.id}-${activeEntry.updated_at}-content`}
                          name="content"
                          defaultValue={activeEntry.content}
                          placeholder="Record your observations, methods, results, and next steps..."
                          maxLength={100_000}
                        />
                        <div className="editor-footer">
                          <span>Changes are saved when you select Save entry.</span>
                          <button className="button button-primary" type="submit">Save entry</button>
                        </div>
                      </form>
                      </div>
                    ) : (
                      <div className="editor-empty">
                        <span className="editor-empty-icon">✎</span>
                        <strong>No notebook entry selected</strong>
                        <p>Create an entry to begin recording your research.</p>
                      </div>
                    )}
                  </div>
                </section>
              )}
            </section>

            <aside className="activity-column">
              <div className="side-card">
                <div className="side-card-heading">
                  <div>
                    <p className="eyebrow">RESEARCH SNAPSHOT</p>
                    <h2>At a glance</h2>
                  </div>
                  <span className="snapshot-icon">✳</span>
                </div>
                <div className="metric-row">
                  <span>Experiments</span>
                  <strong>{experiments.length}</strong>
                </div>
                <div className="metric-row">
                  <span>Notebook entries</span>
                  <strong>{entries.length}</strong>
                </div>
                <div className="metric-row">
                  <span>Project created</span>
                  <strong>{new Intl.DateTimeFormat(undefined, { dateStyle: "medium" }).format(new Date(selectedProjectData.created_at))}</strong>
                </div>
              </div>
              <div className="side-card activity-card">
                <div className="side-card-heading">
                  <div>
                    <p className="eyebrow">TRACEABILITY</p>
                    <h2>Recent activity</h2>
                  </div>
                  <span className="activity-count">{latestActivity.length}</span>
                </div>
                {latestActivity.length ? (
                  <ul className="activity-list">
                    {latestActivity.map((event) => (
                      <li key={event.id}>
                        <span className="activity-marker" />
                        <div>
                          <strong>{event.action} {event.entity_type.replace("_", " ")}</strong>
                          <span>{event.details.title ?? event.details.name ?? `Record #${event.entity_id}`}</span>
                          <time>{formatDate(event.occurred_at)}</time>
                        </div>
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p className="empty-hint">Project and notebook activity will show here.</p>
                )}
                <p className="activity-disclaimer">Basic activity history only; not a validated or tamper-proof audit trail.</p>
              </div>
              <div className="tip-card">
                <span>✦</span>
                <div><strong>Keep your notes useful</strong><p>Capture methods, observations, and results while your work is fresh.</p></div>
              </div>
            </aside>
          </div>
        )}
      </main>
    </div>
  );
}

function AuthScreen({
  onLogin,
}: {
  onLogin: (organization: string, email: string, password: string) => Promise<void>;
}) {
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [recoveryMode, setRecoveryMode] = useState(false);
  const [recoverySent, setRecoverySent] = useState(false);
  const [organization, setOrganization] = useState(
    new URLSearchParams(window.location.search).get("organization") ?? "",
  );

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    setBusy(true);
    setError("");
    try {
      if (recoveryMode) {
        await authApi.requestPasswordReset(
          organization,
          String(form.get("email") ?? ""),
        );
        setRecoverySent(true);
        return;
      }
      await onLogin(
        organization,
        String(form.get("email") ?? ""),
        String(form.get("password") ?? ""),
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to sign in.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="auth-page">
      <form className="auth-card" onSubmit={submit}>
        <div className="brand-mark">i</div>
        <p className="eyebrow">INTERACTIVE ELN</p>
        <h1>{recoveryMode ? "Reset your password" : "Welcome back"}</h1>
        <p className="auth-copy">
          {recoveryMode
            ? "Enter your organization and email. If the account is active, we will email a reset link."
            : "Sign in to your research organization."}
        </p>
        {error && <p className="auth-error" role="alert">{error}</p>}
        {recoverySent ? (
          <>
            <p className="auth-success" role="status">
              If the account is active, a password reset link will be sent.
            </p>
            <button
              className="button button-outline button-full"
              type="button"
              onClick={() => {
                setRecoveryMode(false);
                setRecoverySent(false);
              }}
            >
              Back to sign in
            </button>
          </>
        ) : (
          <>
            <label>Organization ID
              <input
                name="organization"
                value={organization}
                onChange={(event) => setOrganization(event.target.value)}
                placeholder="your-lab"
                autoComplete="organization"
                required
              />
            </label>
            <label>Email
              <input name="email" type="email" autoComplete="email" required />
            </label>
            {!recoveryMode && (
              <label>Password
                <input name="password" type="password" autoComplete="current-password" required />
              </label>
            )}
            <button className="button button-primary button-full" disabled={busy} type="submit">
              {busy
                ? recoveryMode ? "Requesting link…" : "Signing in…"
                : recoveryMode ? "Send reset link" : "Sign in"}
            </button>
            {recoveryMode ? (
              <button
                className="auth-link"
                type="button"
                onClick={() => setRecoveryMode(false)}
              >
                Back to sign in
              </button>
            ) : (
              <>
                <button
                  className="auth-link"
                  type="button"
                  onClick={() => setRecoveryMode(true)}
                >
                  Forgot password?
                </button>
                <small>Accounts are invitation-only. Ask your organization admin for an invite.</small>
              </>
            )}
          </>
        )}
      </form>
    </main>
  );
}

function PasswordResetScreen() {
  const params = new URLSearchParams(window.location.search);
  const token = new URLSearchParams(window.location.hash.slice(1)).get(
    "password-reset-token",
  ) ?? "";
  const organization = params.get("organization") ?? "";
  const [error, setError] = useState("");
  const [complete, setComplete] = useState(false);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const password = String(form.get("password") ?? "");
    if (password !== String(form.get("confirm_password") ?? "")) {
      setError("The passwords do not match.");
      return;
    }
    setError("");
    try {
      await authApi.completePasswordReset(token, password);
      setComplete(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to reset password.");
    }
  }

  return (
    <main className="auth-page">
      <form className="auth-card" onSubmit={(event) => void submit(event)}>
        <div className="brand-mark">i</div>
        <p className="eyebrow">INTERACTIVE ELN</p>
        <h1>Choose a new password</h1>
        {complete ? (
          <>
            <p className="auth-success" role="status">
              Your password has been updated. Other refresh sessions are revoked; existing access tokens expire within 15 minutes.
            </p>
            <a className="button button-primary button-full" href={`/?organization=${encodeURIComponent(organization)}`}>
              Continue to sign in
            </a>
          </>
        ) : (
          <>
            <p className="auth-copy">Choose a new password with at least 12 characters.</p>
            {error && <p className="auth-error" role="alert">{error}</p>}
            <label>New password
              <input name="password" type="password" autoComplete="new-password" minLength={12} maxLength={128} required />
            </label>
            <label>Confirm new password
              <input name="confirm_password" type="password" autoComplete="new-password" minLength={12} maxLength={128} required />
            </label>
            <button className="button button-primary button-full" type="submit" disabled={!token}>
              Reset password
            </button>
            {!token && <p className="auth-error" role="alert">This password reset link is invalid.</p>}
          </>
        )}
      </form>
    </main>
  );
}

function AcceptInvitationScreen() {
  const query = new URLSearchParams(window.location.search);
  const invitationToken = query.get("token") ?? "";
  const organization = query.get("organization") ?? "";
  const [error, setError] = useState("");
  const [complete, setComplete] = useState(false);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    setError("");
    try {
      await authApi.acceptInvitation(
        invitationToken,
        String(form.get("display_name") ?? ""),
        String(form.get("password") ?? ""),
      );
      window.history.replaceState({}, "", `/?organization=${encodeURIComponent(organization)}`);
      setComplete(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to accept invitation.");
    }
  }

  return (
    <main className="auth-page">
      <form className="auth-card" onSubmit={submit}>
        <div className="brand-mark">i</div>
        <p className="eyebrow">ORGANIZATION INVITATION</p>
        <h1>Join your research team</h1>
        {complete ? (
          <>
            <p className="auth-copy">Your account is verified. Sign in to continue.</p>
            <a className="button button-primary button-full" href={`/?organization=${encodeURIComponent(organization)}`}>Continue to sign in</a>
          </>
        ) : (
          <>
            <p className="auth-copy">Set your name and a strong password to accept the invitation.</p>
            {error && <p className="auth-error" role="alert">{error}</p>}
            <label>Display name
              <input name="display_name" autoComplete="name" minLength={1} maxLength={160} required />
            </label>
            <label>Password
              <input name="password" type="password" autoComplete="new-password" minLength={12} maxLength={128} required />
            </label>
            <small>Use at least 12 characters. Existing accounts must enter their current password.</small>
            <button className="button button-primary button-full" type="submit">Accept invitation</button>
          </>
        )}
      </form>
    </main>
  );
}

function AdminPanel({ onClose, currentUserId }: { onClose: () => void; currentUserId: number }) {
  const [users, setUsers] = useState<Awaited<ReturnType<typeof authApi.users>>>([]);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const loadUsers = useCallback(async () => {
    try {
      setUsers(await authApi.users());
      setError("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to load organization users.");
    }
  }, []);

  useEffect(() => {
    void loadUsers();
  }, [loadUsers]);

  async function invite(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    try {
      await authApi.invite(
        String(form.get("email") ?? ""),
        String(form.get("role") ?? "member") as "admin" | "member",
      );
      setNotice("Invitation email sent.");
      event.currentTarget.reset();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to send invitation.");
    }
  }

  async function toggleUser(userId: number, isActive: boolean) {
    try {
      const updated = await authApi.setUserActive(userId, !isActive);
      setUsers((items) => items.map((user) => (user.id === userId ? updated : user)));
      setError("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to update user.");
    }
  }

  return (
    <section className="admin-panel" aria-label="Organization administration">
      <header>
        <div><p className="eyebrow">ORGANIZATION</p><h2>Members &amp; invitations</h2></div>
        <button className="button button-outline" onClick={onClose}>Close</button>
      </header>
      {error && <p className="auth-error" role="alert">{error}</p>}
      {notice && <p className="admin-notice" role="status">{notice}</p>}
      <form className="admin-invite-form" onSubmit={invite}>
        <input name="email" type="email" placeholder="colleague@lab.org" required />
        <select name="role" defaultValue="member">
          <option value="member">Member</option>
          <option value="admin">Organization admin</option>
        </select>
        <button className="button button-primary" type="submit">Send invitation</button>
      </form>
      <div className="admin-users">
        {users.map((user) => (
          <div className="admin-user-row" key={user.id}>
            <span><strong>{user.display_name}</strong><small>{user.email}</small></span>
            <span className="status-chip">{user.role}</span>
            <span className="admin-user-state">{user.is_active ? "Active" : "Inactive"}</span>
            {user.id !== currentUserId && (
              <button className="button button-outline" onClick={() => void toggleUser(user.id, user.is_active)}>
                {user.is_active ? "Deactivate" : "Reactivate"}
              </button>
            )}
          </div>
        ))}
      </div>
    </section>
  );
}

function TaskPanel({ projectId, writable }: { projectId: number; writable: boolean }) {
  const [tasks, setTasks] = useState<LabTask[]>([]);
  const [error, setError] = useState("");

  const loadTasks = useCallback(async () => {
    try {
      setTasks(await api.tasks(projectId));
      setError("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to load project tasks.");
    }
  }, [projectId]);

  useEffect(() => {
    void loadTasks();
  }, [loadTasks]);

  async function createTask(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const values = new FormData(form);
    const due = String(values.get("due_at") ?? "");
    try {
      await api.createTask(projectId, {
        title: String(values.get("title") ?? ""),
        description: String(values.get("description") ?? ""),
        priority:
          values.get("priority") === "low" ||
          values.get("priority") === "high" ||
          values.get("priority") === "urgent"
            ? values.get("priority") as LabTask["priority"]
            : "normal",
        due_at: due ? new Date(due).toISOString() : null,
        experiment_id: null,
      });
      form.reset();
      await loadTasks();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to create task.");
    }
  }

  async function changeStatus(taskId: number, status: LabTask["status"]) {
    try {
      await api.updateTaskStatus(taskId, status);
      await loadTasks();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to update task.");
    }
  }

  return (
    <section className="task-panel" aria-label="Project tasks and workflow">
      <div className="section-heading">
        <div>
          <h2>Tasks and workflow</h2>
          <p>Track actionable work against this project.</p>
        </div>
        <span className="count-pill">{tasks.length}</span>
      </div>
      {error && <p className="inline-error" role="alert">{error}</p>}
      {writable && (
        <form className="task-create-form" onSubmit={createTask}>
          <input name="title" placeholder="Task title" maxLength={200} required />
          <input name="description" placeholder="Description (optional)" maxLength={5000} />
          <input name="due_at" type="datetime-local" aria-label="Task due date" />
          <select name="priority" defaultValue="normal" aria-label="Task priority">
            <option value="low">Low</option>
            <option value="normal">Normal</option>
            <option value="high">High</option>
            <option value="urgent">Urgent</option>
          </select>
          <button className="button button-outline" type="submit">Add task</button>
        </form>
      )}
      <ul className="task-list">
        {tasks.map((task) => (
          <li key={task.id}>
            <div>
              <strong>{task.title}</strong>
              <small>{task.priority} priority · {task.due_at ? formatDate(task.due_at) : "No due date"}</small>
              {task.description && <p>{task.description}</p>}
            </div>
            <select
              aria-label={`Status for ${task.title}`}
              value={task.status}
              disabled={!writable}
              onChange={(event) => {
                const value = event.target.value;
                if (
                  value === "open" ||
                  value === "in_progress" ||
                  value === "blocked" ||
                  value === "completed" ||
                  value === "cancelled"
                ) {
                  void changeStatus(task.id, value);
                }
              }}
            >
              <option value="open">Open</option>
              <option value="in_progress">In progress</option>
              <option value="blocked">Blocked</option>
              <option value="completed">Completed</option>
              <option value="cancelled">Cancelled</option>
            </select>
          </li>
        ))}
        {tasks.length === 0 && <li className="empty-hint">No tasks for this project yet.</li>}
      </ul>
    </section>
  );
}

function ResourceTagEditor({
  entityType,
  entityId,
}: {
  entityType: "inventory" | "sample" | "equipment" | "template";
  entityId: number;
}) {
  const [draft, setDraft] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;
    api.recordTags(entityType, entityId)
      .then((result) => {
        if (active) setDraft(result.tags.join(", "));
      })
      .catch((err: unknown) => {
        if (active) setError(err instanceof Error ? err.message : "Unable to load resource tags.");
      });
    return () => {
      active = false;
    };
  }, [entityId, entityType]);

  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    try {
      const result = await api.updateRecordTags(
        entityType,
        entityId,
        draft.split(","),
      );
      setDraft(result.tags.join(", "));
      setError("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to update resource tags.");
    }
  }

  return (
    <form className="resource-tags-form" onSubmit={(event) => void save(event)}>
      <input
        aria-label={`${entityType} tags`}
        value={draft}
        onChange={(event) => setDraft(event.target.value)}
        placeholder="Tags, comma separated"
        maxLength={840}
      />
      <button className="button button-outline" type="submit">Save tags</button>
      {error && <small role="alert">{error}</small>}
    </form>
  );
}

function ProjectAccessPanel({
  projectId,
  onClose,
}: {
  projectId: number;
  onClose: () => void;
}) {
  const [members, setMembers] = useState<Awaited<ReturnType<typeof api.projectMembers>>>([]);
  const [users, setUsers] = useState<Awaited<ReturnType<typeof authApi.organizationUsers>>>([]);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const loadAccess = useCallback(async () => {
    try {
      const [projectMembers, organizationUsers] = await Promise.all([
        api.projectMembers(projectId),
        authApi.organizationUsers(),
      ]);
      setMembers(projectMembers);
      setUsers(organizationUsers);
      setError("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to load project access.");
    }
  }, [projectId]);

  useEffect(() => {
    void loadAccess();
  }, [loadAccess]);

  async function saveAccess(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const userId = Number(form.get("user_id"));
    const role = String(form.get("role"));
    if (!Number.isInteger(userId) || !["editor", "viewer"].includes(role)) return;
    try {
      await api.setProjectMember(projectId, userId, role as "editor" | "viewer");
      setNotice("Project access updated.");
      await loadAccess();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to update project access.");
    }
  }

  async function revoke(userId: number) {
    try {
      await api.removeProjectMember(projectId, userId);
      setNotice("Project access removed.");
      await loadAccess();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to remove project access.");
    }
  }

  return (
    <section className="admin-panel" aria-label="Project access management">
      <header>
        <div><p className="eyebrow">PROJECT PERMISSIONS</p><h2>Shared access</h2></div>
        <button className="button button-outline" onClick={onClose}>Close</button>
      </header>
      <p className="auth-copy">Projects are private by default. Editors can change notebook records; viewers can only read them.</p>
      {error && <p className="auth-error" role="alert">{error}</p>}
      {notice && <p className="admin-notice" role="status">{notice}</p>}
      <form className="admin-invite-form project-access-form" onSubmit={saveAccess}>
        <select name="user_id" required defaultValue="">
          <option value="" disabled>Select an organization member</option>
          {users.map((member) => (
            <option key={member.id} value={member.id}>
              {member.display_name} ({member.email})
            </option>
          ))}
        </select>
        <select name="role" defaultValue="viewer">
          <option value="viewer">Viewer</option>
          <option value="editor">Editor</option>
        </select>
        <button className="button button-primary" type="submit">Grant access</button>
      </form>
      <div className="admin-users">
        {members.map((member) => {
          const directoryUser = users.find((candidate) => candidate.id === member.user_id);
          return (
            <div className="admin-user-row" key={member.id}>
              <span>
                <strong>{directoryUser?.display_name ?? `User #${member.user_id}`}</strong>
                <small>{directoryUser?.email ?? "Organization account unavailable"}</small>
              </span>
              <span className="status-chip">{member.role}</span>
              {member.role !== "owner" && (
                <button
                  className="button button-outline"
                  onClick={() => void revoke(member.user_id)}
                >
                  Remove
                </button>
              )}
            </div>
          );
        })}
      </div>
    </section>
  );
}

function InventoryPanel({
  projects,
  onClose,
}: {
  projects: Project[];
  onClose: () => void;
}) {
  const [items, setItems] = useState<InventoryItem[]>([]);
  const [samples, setSamples] = useState<SampleRecord[]>([]);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const loadRecords = useCallback(async () => {
    try {
      const [inventoryItems, sampleRecords] = await Promise.all([
        api.inventory(),
        api.samples(),
      ]);
      setItems(inventoryItems);
      setSamples(sampleRecords);
      setError("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to load lab inventory.");
    }
  }, []);

  useEffect(() => {
    void loadRecords();
  }, [loadRecords]);

  async function createInventoryItem(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const formElement = event.currentTarget;
    const form = new FormData(formElement);
    try {
      await api.createInventoryItem({
        name: String(form.get("name") ?? ""),
        category: String(form.get("category") ?? "reagent") as InventoryItem["category"],
        catalog_number: String(form.get("catalog_number") ?? ""),
        lot_number: String(form.get("lot_number") ?? ""),
        expires_on: String(form.get("expires_on") ?? "") || null,
        quantity: Number(form.get("quantity") ?? 0),
        unit: String(form.get("unit") ?? ""),
        low_stock_threshold: Number(form.get("low_stock_threshold") ?? 0),
        location: String(form.get("location") ?? ""),
        notes: String(form.get("notes") ?? ""),
      });
      formElement.reset();
      setNotice("Inventory item added.");
      await loadRecords();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to add inventory item.");
    }
  }

  async function adjustStock(event: FormEvent<HTMLFormElement>, itemId: number) {
    event.preventDefault();
    const formElement = event.currentTarget;
    const form = new FormData(formElement);
    try {
      await api.adjustStock(
        itemId,
        Number(form.get("quantity_delta")),
        String(form.get("reason") ?? ""),
      );
      formElement.reset();
      setNotice("Stock adjustment recorded.");
      await loadRecords();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to adjust stock.");
    }
  }

  async function createSample(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const formElement = event.currentTarget;
    const form = new FormData(formElement);
    const projectIdValue = String(form.get("project_id") ?? "");
    try {
      await api.createSample({
        name: String(form.get("name") ?? ""),
        sample_type: String(form.get("sample_type") ?? ""),
        external_id: String(form.get("external_id") ?? ""),
        project_id: projectIdValue ? Number(projectIdValue) : null,
        parent_sample_id: null,
        storage_location: String(form.get("storage_location") ?? ""),
        description: String(form.get("description") ?? ""),
      });
      formElement.reset();
      setNotice("Sample registered.");
      await loadRecords();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to register sample.");
    }
  }

  async function changeResourceStatus(
    entityType: "inventory" | "sample",
    entityId: number,
    status: "active" | "archived",
  ) {
    try {
      await api.updateResourceStatus(entityType, entityId, status);
      setNotice(`Resource ${status}.`);
      await loadRecords();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to update resource lifecycle.");
    }
  }

  return (
    <section className="admin-panel inventory-panel" aria-label="Lab inventory">
      <header>
        <div><p className="eyebrow">LAB OPERATIONS</p><h2>Inventory &amp; samples</h2></div>
        <button className="button button-outline" onClick={onClose}>Close</button>
      </header>
      <p className="auth-copy">Stock adjustments are recorded with the acting user and reason. This operational log is not a regulated audit trail.</p>
      {error && <p className="auth-error" role="alert">{error}</p>}
      {notice && <p className="admin-notice" role="status">{notice}</p>}
      <h3 className="inventory-subheading">Reagents, consumables &amp; equipment</h3>
      <form className="inventory-form" onSubmit={createInventoryItem}>
        <input name="name" placeholder="Item name" required maxLength={160} />
        <input
          name="category"
          list="inventory-categories"
          defaultValue="reagent"
          placeholder="Category (custom allowed)"
          required
          maxLength={64}
        />
        <datalist id="inventory-categories">
          <option value="reagent" />
          <option value="consumable" />
          <option value="equipment" />
          <option value="chemical" />
          <option value="biological" />
          <option value="safety" />
        </datalist>
        <input name="unit" placeholder="Unit (mL, g, each)" required maxLength={32} />
        <input name="quantity" type="number" min="0" step="0.001" placeholder="Opening stock" defaultValue="0" />
        <input name="low_stock_threshold" type="number" min="0" step="0.001" placeholder="Low-stock threshold" defaultValue="0" />
        <input name="catalog_number" placeholder="Catalog number" maxLength={120} />
        <input name="lot_number" placeholder="Lot number" maxLength={120} />
        <input name="expires_on" type="date" aria-label="Expiration date (optional)" />
        <input name="location" placeholder="Storage location" maxLength={200} />
        <input name="notes" placeholder="Notes" maxLength={5000} />
        <button className="button button-primary" type="submit">Add inventory item</button>
      </form>
      <div className="inventory-record-list">
        {items.map((item) => (
          <article className="inventory-record" key={item.id}>
            <div className="inventory-record-heading">
              <strong>{item.name}</strong>
              <div>
                <span className={`status-chip ${item.status === "archived" ? "status-archived" : item.quantity <= item.low_stock_threshold ? "status-low-stock" : ""}`}>
                  {item.status === "archived" ? "Archived" : `${item.quantity} ${item.unit}${item.quantity <= item.low_stock_threshold ? " · low stock" : ""}`}
                </span>
                <button
                  className="button button-outline"
                  type="button"
                  onClick={() => void changeResourceStatus("inventory", item.id, item.status === "active" ? "archived" : "active")}
                >
                  {item.status === "active" ? "Archive" : "Reactivate"}
                </button>
              </div>
            </div>
            <small>{item.category} · {item.location || "No location"} · Lot {item.lot_number || "not specified"}</small>
            <ResourceTagEditor entityType="inventory" entityId={item.id} />
            {item.expires_on && <small>Expires {item.expires_on}</small>}
            {item.status === "active" && <form className="stock-adjust-form" onSubmit={(event) => void adjustStock(event, item.id)}>
              <input name="quantity_delta" type="number" step="0.001" placeholder="± quantity" required />
              <input name="reason" placeholder="Reason for adjustment" maxLength={240} required />
              <button className="button button-outline" type="submit">Record adjustment</button>
            </form>}
          </article>
        ))}
        {items.length === 0 && <p className="empty-hint">No inventory records yet.</p>}
      </div>
      <h3 className="inventory-subheading">Biological samples</h3>
      <form className="inventory-form sample-form" onSubmit={createSample}>
        <input name="name" placeholder="Sample name" required maxLength={160} />
        <input name="sample_type" placeholder="Type (cell line, tissue, plasmid…)" required maxLength={80} />
        <input name="external_id" placeholder="Sample / barcode ID" maxLength={120} />
        <select name="project_id" defaultValue="">
          <option value="">Organization-level sample</option>
          {projects.map((project) => <option key={project.id} value={project.id}>{project.name}</option>)}
        </select>
        <input name="storage_location" placeholder="Storage location" maxLength={200} />
        <input name="description" placeholder="Description" maxLength={5000} />
        <button className="button button-primary" type="submit">Register sample</button>
      </form>
      <div className="sample-record-list">
        {samples.map((sample) => (
          <article className="inventory-record" key={sample.id}>
            <div className="inventory-record-heading">
              <strong>{sample.name}</strong>
              <div>
                <span className="status-chip">{sample.status === "archived" ? "Archived" : sample.sample_type}</span>
                <button
                  className="button button-outline"
                  type="button"
                  onClick={() => void changeResourceStatus("sample", sample.id, sample.status === "active" ? "archived" : "active")}
                >
                  {sample.status === "active" ? "Archive" : "Reactivate"}
                </button>
              </div>
            </div>
            <small>{sample.external_id || "No sample ID"} · {sample.storage_location || "No location"} · {projects.find((project) => project.id === sample.project_id)?.name ?? "Organization sample"}</small>
            <ResourceTagEditor entityType="sample" entityId={sample.id} />
          </article>
        ))}
        {samples.length === 0 && <p className="empty-hint">No samples registered yet.</p>}
      </div>
    </section>
  );
}

function TemplatePanel({
  user,
  templates,
  projects,
  onRefresh,
  onProtocolStarted,
  onClose,
}: {
  user: AuthUser;
  templates: NotebookTemplate[];
  projects: Project[];
  onRefresh: () => Promise<void>;
  onProtocolStarted: (experiment: Experiment) => Promise<void>;
  onClose: () => void;
}) {
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  async function startProtocol(event: FormEvent<HTMLFormElement>, templateId: number) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const projectId = Number(form.get("project_id"));
    if (!Number.isInteger(projectId) || projectId < 1) return;
    try {
      const experiment = await api.startProtocol(projectId, templateId);
      await onProtocolStarted(experiment);
      setNotice("Protocol started as a new experiment.");
      setError("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to start protocol.");
    }
  }

  async function saveTemplate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const formElement = event.currentTarget;
    const form = new FormData(formElement);
    const payload = {
      name: String(form.get("name") ?? ""),
      template_kind: String(form.get("template_kind") ?? "entry") as "entry" | "protocol",
      description: String(form.get("description") ?? ""),
      sections: String(form.get("sections") ?? "")
        .split("\n")
        .map((line) => line.trim())
        .filter(Boolean)
        .map((title) => ({ title, instructions: "", required: false })),
    };
    try {
      await api.createTemplate(payload);
      formElement.reset();
      setNotice("Template saved.");
      setError("");
      await onRefresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to save template.");
    }
  }

  return (
    <section className="admin-panel template-panel" aria-label="Notebook templates">
      <header>
        <div><p className="eyebrow">REUSABLE WORKFLOWS</p><h2>Templates &amp; protocols</h2></div>
        <button className="button button-outline" onClick={onClose}>Close</button>
      </header>
      <p className="auth-copy">Create reusable entry structures and protocol outlines for your organization.</p>
      {error && <p className="auth-error" role="alert">{error}</p>}
      {notice && <p className="admin-notice" role="status">{notice}</p>}
      <form className="template-create-form" onSubmit={saveTemplate}>
        <input name="name" placeholder="Template or protocol name" required maxLength={160} />
        <select name="template_kind" defaultValue="entry">
          <option value="entry">Notebook entry template</option>
          <option value="protocol">Reusable protocol</option>
        </select>
        <input name="description" placeholder="Description (optional)" maxLength={5000} />
        <textarea name="sections" placeholder={"One section heading per line\nPurpose\nMaterials\nProcedure\nResults"} rows={5} required />
        <button className="button button-primary" type="submit">Save template</button>
      </form>
      <div className="template-list">
        {templates.map((template) => (
          <article className="inventory-record" key={template.id}>
            <div className="inventory-record-heading">
              <strong>{template.name}</strong>
              <div>
                <span className={`status-chip ${template.status === "archived" ? "status-archived" : ""}`}>
                  {template.status === "archived" ? "Archived" : template.template_kind}
                </span>
                {user.role === "admin" && (
                  <button
                    className="button button-outline"
                    type="button"
                    onClick={() => void api.updateResourceStatus(
                      "template",
                      template.id,
                      template.status === "active" ? "archived" : "active",
                    ).then(onRefresh).catch((err: unknown) => setError(
                      err instanceof Error ? err.message : "Unable to update template lifecycle.",
                    ))}
                  >
                    {template.status === "active" ? "Archive" : "Reactivate"}
                  </button>
                )}
              </div>
            </div>
            <small>{template.description || template.sections.map((section) => section.title).join(" · ")}</small>
            <ResourceTagEditor entityType="template" entityId={template.id} />
            {template.template_kind === "protocol" && template.status === "active" && (
              <form className="template-apply-form" onSubmit={(event) => void startProtocol(event, template.id)}>
                <select name="project_id" defaultValue="" required>
                  <option value="" disabled>Choose project</option>
                  {projects.map((project) => <option key={project.id} value={project.id}>{project.name}</option>)}
                </select>
                <button className="button button-outline" type="submit">Start protocol</button>
              </form>
            )}
          </article>
        ))}
        {templates.length === 0 && <p className="empty-hint">No templates or protocols saved yet.</p>}
      </div>
    </section>
  );
}

function EquipmentPanel({
  projects,
  user,
  onClose,
}: {
  projects: Project[];
  user: AuthUser;
  onClose: () => void;
}) {
  const [equipment, setEquipment] = useState<EquipmentResource[]>([]);
  const [bookings, setBookings] = useState<EquipmentBooking[]>([]);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const loadSchedule = useCallback(async () => {
    try {
      const [resources, reservations] = await Promise.all([api.equipment(), api.bookings()]);
      setEquipment(resources);
      setBookings(reservations);
      setError("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to load equipment schedule.");
    }
  }, []);

  useEffect(() => {
    void loadSchedule();
  }, [loadSchedule]);

  async function addEquipment(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const formElement = event.currentTarget;
    const form = new FormData(formElement);
    try {
      await api.createEquipment({
        name: String(form.get("name") ?? ""),
        description: String(form.get("description") ?? ""),
        location: String(form.get("location") ?? ""),
        category: String(form.get("category") ?? "equipment"),
      });
      formElement.reset();
      setNotice("Equipment registered.");
      await loadSchedule();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to register equipment.");
    }
  }

  async function reserve(event: FormEvent<HTMLFormElement>, equipmentId: number) {
    event.preventDefault();
    const formElement = event.currentTarget;
    const form = new FormData(formElement);
    const startValue = String(form.get("starts_at") ?? "");
    const endValue = String(form.get("ends_at") ?? "");
    const projectIdValue = String(form.get("project_id") ?? "");
    try {
      await api.createBooking(equipmentId, {
        starts_at: new Date(startValue).toISOString(),
        ends_at: new Date(endValue).toISOString(),
        purpose: String(form.get("purpose") ?? ""),
        project_id: projectIdValue ? Number(projectIdValue) : null,
      });
      formElement.reset();
      setNotice("Equipment booking created.");
      await loadSchedule();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to book equipment.");
    }
  }

  async function cancel(bookingId: number) {
    try {
      await api.cancelBooking(bookingId);
      setNotice("Booking cancelled.");
      await loadSchedule();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to cancel booking.");
    }
  }

  return (
    <section className="admin-panel equipment-panel" aria-label="Equipment scheduler">
      <header>
        <div><p className="eyebrow">LAB SCHEDULING</p><h2>Equipment &amp; bookings</h2></div>
        <button className="button button-outline" onClick={onClose}>Close</button>
      </header>
      {error && <p className="auth-error" role="alert">{error}</p>}
      {notice && <p className="admin-notice" role="status">{notice}</p>}
      {user.role === "admin" && (
        <form className="equipment-create-form" onSubmit={addEquipment}>
          <input name="name" placeholder="Equipment name" required maxLength={160} />
          <input name="category" placeholder="Category" defaultValue="equipment" maxLength={64} />
          <input name="location" placeholder="Location" maxLength={200} />
          <input name="description" placeholder="Description (optional)" maxLength={5000} />
          <button className="button button-primary" type="submit">Add equipment</button>
        </form>
      )}
      <div className="equipment-resource-list">
        {equipment.map((resource) => (
          <article className="inventory-record" key={resource.id}>
            <div className="inventory-record-heading">
              <strong>{resource.name}</strong>
              <div>
                <span className={`status-chip ${resource.status === "archived" ? "status-archived" : ""}`}>
                  {resource.status === "archived" ? "Archived" : resource.location || "Location unspecified"}
                </span>
                {user.role === "admin" && (
                  <button
                    className="button button-outline"
                    type="button"
                    onClick={() => void api.updateResourceStatus(
                      "equipment",
                      resource.id,
                      resource.status === "active" ? "archived" : "active",
                    ).then(loadSchedule).catch((err: unknown) => setError(
                      err instanceof Error ? err.message : "Unable to update equipment lifecycle.",
                    ))}
                  >
                    {resource.status === "active" ? "Archive" : "Reactivate"}
                  </button>
                )}
              </div>
            </div>
            <small>{resource.category}</small>
            {resource.description && <small>{resource.description}</small>}
            <ResourceTagEditor entityType="equipment" entityId={resource.id} />
            {resource.status === "active" && <form className="equipment-booking-form" onSubmit={(event) => void reserve(event, resource.id)}>
              <input name="starts_at" type="datetime-local" required aria-label="Booking start" />
              <input name="ends_at" type="datetime-local" required aria-label="Booking end" />
              <input name="purpose" placeholder="Purpose" required maxLength={500} />
              <select name="project_id" defaultValue="">
                <option value="">Organization-level</option>
                {projects.map((project) => <option key={project.id} value={project.id}>{project.name}</option>)}
              </select>
              <button className="button button-outline" type="submit">Book</button>
            </form>}
          </article>
        ))}
        {equipment.length === 0 && <p className="empty-hint">No equipment has been registered yet.</p>}
      </div>
      <h3 className="inventory-subheading">Reservations</h3>
      <div className="equipment-booking-list">
        {bookings.filter((booking) => booking.status === "reserved").map((booking) => (
          <article className="equipment-booking-row" key={booking.id}>
            <div>
              <strong>{equipment.find((resource) => resource.id === booking.equipment_id)?.name ?? `Equipment #${booking.equipment_id}`}</strong>
              <small>{formatDate(booking.starts_at)} – {formatDate(booking.ends_at)} · {booking.purpose}</small>
            </div>
            {(booking.booked_by_user_id === user.id || user.role === "admin") && (
              <button className="button button-outline" onClick={() => void cancel(booking.id)}>Cancel</button>
            )}
          </article>
        ))}
        {bookings.filter((booking) => booking.status === "reserved").length === 0 &&
          <p className="empty-hint">No active equipment bookings.</p>}
      </div>
    </section>
  );
}

export default function App() {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [ready, setReady] = useState(false);
  const isInvitationPage = window.location.pathname === "/accept-invitation";
  const isPasswordResetPage = new URLSearchParams(
    window.location.hash.slice(1),
  ).has("password-reset-token");

  useEffect(() => {
    if (isInvitationPage || isPasswordResetPage) {
      setReady(true);
      return;
    }
    let active = true;
    void authApi
      .refresh()
      .then(async (session) => {
        setAccessToken(session.access_token);
        const currentUser = await authApi.me(session.access_token);
        if (active) setUser(currentUser);
      })
      .catch(() => {
        setAccessToken(null);
      })
      .finally(() => {
        if (active) setReady(true);
      });
    return () => {
      active = false;
    };
  }, [isInvitationPage, isPasswordResetPage]);

  async function login(organization: string, email: string, password: string) {
    const session = await authApi.login(organization, email, password);
    setAccessToken(session.access_token);
    try {
      setUser(await authApi.me(session.access_token));
    } catch (err) {
      setAccessToken(null);
      await authApi.logout();
      throw err;
    }
  }

  async function logout() {
    await authApi.logout();
    setAccessToken(null);
    setUser(null);
  }

  if (isInvitationPage) return <AcceptInvitationScreen />;
  if (isPasswordResetPage) return <PasswordResetScreen />;
  if (!ready) return <main className="auth-page"><p className="auth-copy">Checking your session…</p></main>;
  if (!user) return <AuthScreen onLogin={login} />;
  return <NotebookApp user={user} onLogout={() => void logout()} />;
}
