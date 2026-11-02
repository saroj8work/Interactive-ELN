import { FormEvent, PointerEvent as ReactPointerEvent, useCallback, useEffect, useRef, useState } from "react";
import { api, authApi, AuthUser, setAccessToken } from "./api";
import type {
  ActivityEvent,
  Notification,
  EntryAttachment,
  EntryRevision,
  EntryTimestamp,
  EntryTimestampVerification,
  EquipmentBooking,
  EquipmentMaintenance,
  CalendarFeed,
  EquipmentResource,
  Experiment,
  ExperimentApproval,
  LabTask,
  InventoryItem,
  InventoryCustomFieldDefinition,
  NotebookTemplate,
  NotebookEntry,
  Project,
  RecordSignature,
  SearchHit,
  SampleRecord,
  SampleCustodyTransfer,
  StorageLocation,
  WorkflowRule,
  WebhookDelivery,
  WebhookEndpoint,
} from "./types";
import { ScientificContent } from "./ScientificContent";
import { MoleculeEditor, type Structure } from "./MoleculeEditor";
import { StoichiometryTable } from "./StoichiometryTable";
import { StorageBoxGrid } from "./StorageBoxGrid";
import { LabLabelGenerator, type LabelData } from "./LabLabelGenerator";
import { ProtocolStepTimer } from "./ProtocolStepTimer";
import { WorkflowDagCanvas } from "./WorkflowDagCanvas";
import { BarcodeScannerModal } from "./BarcodeScannerModal";
import { FormalReportView } from "./FormalReportView";
import { ChemicalSearchModal } from "./ChemicalSearchModal";
import { LandingPage } from "./LandingPage";
import { MentionAutocomplete } from "./MentionAutocomplete";
import { formatLocaleDate, formatLocaleDateOnly, getSavedLocale, saveLocale, translate, type Locale } from "./i18n";

function formatDate(value: string): string {
  return formatLocaleDate(value, getSavedLocale());
}

function dateTimeLocalValue(value: string): string {
  const date = new Date(value);
  date.setMinutes(date.getMinutes() - date.getTimezoneOffset());
  return date.toISOString().slice(0, 16);
}

function escapeIcsText(value: string): string {
  return value
    .replace(/[\u0000-\u0009\u000B\u000C\u000E-\u001F\u007F]/g, "")
    .replace(/\\/g, "\\\\")
    .replace(/\r\n|\r|\n/g, "\\n")
    .replace(/,/g, "\\,")
    .replace(/;/g, "\\;");
}

function foldIcsLine(line: string): string {
  const chunks: string[] = [];
  let current = "";
  let bytes = 0;
  for (const character of line) {
    const characterBytes = new TextEncoder().encode(character).length;
    if (bytes + characterBytes > 75) {
      chunks.push(current);
      current = " ";
      bytes = 1;
    }
    current += character;
    bytes += characterBytes;
  }
  chunks.push(current);
  return chunks.join("\r\n");
}

function icsDateTime(value: string): string {
  return new Date(value).toISOString().replace(/[-:]/g, "").replace(/\.\d{3}Z$/, "Z");
}

function exportEquipmentCalendar(
  equipment: EquipmentResource[],
  bookings: EquipmentBooking[],
  maintenance: EquipmentMaintenance[],
  organizationId: number,
): boolean {
  const now = Date.now();
  const events = [
    ...bookings.filter((booking) => booking.status === "reserved" && new Date(booking.ends_at).getTime() > now).map((booking) => {
      const name = equipment.find((item) => item.id === booking.equipment_id)?.name ?? `Equipment #${booking.equipment_id}`;
      return {
        uid: `booking-${booking.id}@org-${organizationId}.interactive-eln`,
        title: `Equipment booking: ${name}`,
        description: booking.purpose,
        startsAt: booking.starts_at,
        endsAt: booking.ends_at,
      };
    }),
    ...maintenance.filter((record) => ["scheduled", "in_progress"].includes(record.status) && new Date(record.ends_at).getTime() > now).map((record) => {
      const name = equipment.find((item) => item.id === record.equipment_id)?.name ?? `Equipment #${record.equipment_id}`;
      return {
        uid: `maintenance-${record.id}@org-${organizationId}.interactive-eln`,
        title: `Equipment maintenance: ${name} - ${record.title}`,
        description: record.notes,
        startsAt: record.starts_at,
        endsAt: record.ends_at,
      };
    }),
  ];
  if (events.length === 0) return false;
  const stamp = icsDateTime(new Date().toISOString());
  const lines = [
    "BEGIN:VCALENDAR",
    "VERSION:2.0",
    "PRODID:-//Aura Lab//Equipment Schedule//EN",
    "CALSCALE:GREGORIAN",
    "METHOD:PUBLISH",
    "X-WR-CALNAME:Aura Lab Equipment Schedule",
    ...events.flatMap((event) => [
      "BEGIN:VEVENT",
      `UID:${event.uid}`,
      `DTSTAMP:${stamp}`,
      `DTSTART:${icsDateTime(event.startsAt)}`,
      `DTEND:${icsDateTime(event.endsAt)}`,
      `SUMMARY:${escapeIcsText(event.title)}`,
      `DESCRIPTION:${escapeIcsText(event.description)}`,
      "STATUS:CONFIRMED",
      "END:VEVENT",
    ]),
    "END:VCALENDAR",
  ];
  const blob = new Blob([lines.map(foldIcsLine).join("\r\n") + "\r\n"], { type: "text/calendar;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = "interactive-eln-equipment-schedule.ics";
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
  return true;
}

function NotebookApp({ user, onLogout }: { user: AuthUser; onLogout: () => void }) {
  const [locale, setLocale] = useState<Locale>(getSavedLocale);
  const t = useCallback((text: string) => translate(locale, text), [locale]);
  const [projects, setProjects] = useState<Project[]>([]);
  const [experiments, setExperiments] = useState<Experiment[]>([]);
  const [experimentApprovals, setExperimentApprovals] = useState<ExperimentApproval[]>([]);
  const [organizationUsers, setOrganizationUsers] = useState<Awaited<ReturnType<typeof authApi.organizationUsers>>>([]);
  const [projectMemberIds, setProjectMemberIds] = useState<number[]>([]);
  const [entries, setEntries] = useState<NotebookEntry[]>([]);
  const [activity, setActivity] = useState<ActivityEvent[]>([]);
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const [notificationsOpen, setNotificationsOpen] = useState(false);
  const [selectedProject, setSelectedProject] = useState<number | null>(null);
  const [selectedExperiment, setSelectedExperiment] = useState<number | null>(null);
  const selectedExperimentRef = useRef<number | null>(selectedExperiment);
  const [selectedEntry, setSelectedEntry] = useState<number | null>(null);
  // Short-lived Toast Notification System
  const [toasts, setToasts] = useState<{ id: string; type: "error" | "success" | "info"; message: string }[]>([]);

  const showToast = useCallback((message: string, type: "error" | "success" | "info" = "info", duration = 4500) => {
    if (!message) return;
    const id = Math.random().toString(36).slice(2, 9);
    setToasts((prev) => [...prev.slice(-3), { id, type, message }]);
    window.setTimeout(() => {
      setToasts((prev) => prev.filter((t) => t.id !== id));
    }, duration);
  }, []);

  const setError = useCallback((msg: string) => {
    if (msg) showToast(msg, "error", 5000);
  }, [showToast]);

  const setNotice = useCallback((msg: string) => {
    if (msg) showToast(msg, "success", 4000);
  }, [showToast]);

  const setAuditNotice = useCallback((msg: string) => {
    if (msg) showToast(msg, "info", 4500);
  }, [showToast]);
  const [adminOpen, setAdminOpen] = useState(false);
  const [integrationsOpen, setIntegrationsOpen] = useState(false);
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
  const [entryTimestamps, setEntryTimestamps] = useState<EntryTimestamp[]>([]);
  const [timestampVerifications, setTimestampVerifications] = useState<Record<number, EntryTimestampVerification>>({});
  const [tasksOpen, setTasksOpen] = useState(false);
  const [workflowRulesOpen, setWorkflowRulesOpen] = useState(false);
  const [locationsOpen, setLocationsOpen] = useState(false);
  const [editorMode, setEditorMode] = useState<"edit" | "preview">("edit");
  const [activeMoleculeStructure, setActiveMoleculeStructure] = useState<Structure | null>(null);
  const [barcodeScannerOpen, setBarcodeScannerOpen] = useState(false);
  const [formalReportOpen, setFormalReportOpen] = useState(false);
  const [chemSearchOpen, setChemSearchOpen] = useState(false);
  const [inventoryItems, setInventoryItems] = useState<InventoryItem[]>([]);
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
  }, [entries, selectedEntry]);

  const loadInventoryAndSamples = useCallback(async () => {
    try {
      const [inv, smp] = await Promise.all([api.inventory(), api.samples()]);
      setInventoryItems(inv);
      setSamples(smp);
    } catch {
      // Non-fatal
    }
  }, []);

  useEffect(() => {
    void loadInventoryAndSamples();
  }, [loadInventoryAndSamples]);

  const handleDeductStoichiometryStock = useCallback(
    async (deductions: { itemId: number; itemName: string; amount: number; unit: string }[]) => {
      for (const d of deductions) {
        await api.adjustStock(
          d.itemId,
          -d.amount,
          `Consumed in experiment #${selectedExperimentRef.current ?? ""}`
        );
      }
      await loadInventoryAndSamples();
      setNotice(`Deducted ${deductions.length} reagents from laboratory inventory.`);
    },
    [loadInventoryAndSamples]
  );

  const handleBarcodeDetected = useCallback(
    (code: string) => {
      const trimmed = code.trim();
      const smpMatch = trimmed.match(/^(?:smp-|sample:?)(\d+)/i);
      if (smpMatch) {
        const sampleId = parseInt(smpMatch[1], 10);
        setNotice(`Scanned Sample #${sampleId}. Opening lab inventory & samples...`);
        setInventoryOpen(true);
        return;
      }
      const invMatch = trimmed.match(/^(?:inv-|reagent:?)(\d+)/i);
      if (invMatch) {
        const itemId = parseInt(invMatch[1], 10);
        setNotice(`Scanned Inventory Reagent #${itemId}. Opening inventory...`);
        setInventoryOpen(true);
        return;
      }
      const expMatch = trimmed.match(/^(?:exp-|experiment:?)(\d+)/i);
      if (expMatch) {
        const expId = parseInt(expMatch[1], 10);
        if (experiments.some((e) => e.id === expId)) {
          setSelectedExperiment(expId);
          setNotice(`Navigated to Experiment #${expId}`);
          return;
        }
      }
      setNotice(`Scanned label: ${trimmed}. Searching records...`);
      void api.search(trimmed).then((res) => {
        setSearchResults(res);
        setSearchOpen(true);
      });
    },
    [experiments]
  );

  const handleChemSearchResult = useCallback(
    (type: "experiment" | "entry" | "inventory", id: number) => {
      if (type === "inventory") {
        setInventoryOpen(true);
        setNotice(`Opened Inventory for Reagent #${id}`);
      } else {
        setSelectedExperiment(id);
        setNotice(`Navigated to Experiment #${id}`);
      }
    },
    []
  );

  const handleMentionNavigate = useCallback(
    (kind: "inventory" | "sample" | "experiment", id: number) => {
      if (kind === "inventory" || kind === "sample") {
        setInventoryOpen(true);
        setNotice(`Navigated to ${kind} #${id}`);
      } else if (kind === "experiment") {
        setSelectedExperiment(id);
        setNotice(`Navigated to experiment #${id}`);
      }
    },
    []
  );

  useEffect(() => {
    document.documentElement.lang = locale === "hi" ? "hi-IN" : "en";
    saveLocale(locale);
  }, [locale]);

  useEffect(() => {
    selectedExperimentRef.current = selectedExperiment;
  }, [selectedExperiment]);

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

  const loadNotifications = useCallback(async () => {
    try {
      setNotifications(await api.notifications());
    } catch {
      // Keep notification availability independent from the main workspace load.
    }
  }, []);

  useEffect(() => {
    void loadNotifications();
    const interval = window.setInterval(() => void loadNotifications(), 30000);
    return () => window.clearInterval(interval);
  }, [loadNotifications]);

  const markNotificationRead = async (notification: Notification) => {
    if (!notification.read_at) {
      try {
        const updated = await api.markNotificationRead(notification.id);
        setNotifications((current) => current.map((item) => item.id === updated.id ? updated : item));
      } catch (err) {
        setError(err instanceof Error ? err.message : "Unable to mark notification as read.");
      }
    }
    const projectId = Number(notification.details.project_id);
    if (Number.isInteger(projectId) && projectId > 0) setSelectedProject(projectId);
    if (notification.entity_type === "experiment" && notification.entity_id > 0) {
      setSelectedExperiment(notification.entity_id);
    }
    setNotificationsOpen(false);
  };

  useEffect(() => {
    authApi.organizationUsers().then(setOrganizationUsers).catch(() => setOrganizationUsers([]));
  }, []);

  useEffect(() => {
    if (selectedProject === null) {
      setProjectMemberIds([]);
      return;
    }
    api.projectMembers(selectedProject)
      .then((members) => setProjectMemberIds(members.map((member) => member.user_id)))
      .catch(() => setProjectMemberIds([]));
  }, [selectedProject]);

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

  const loadExperimentApprovals = useCallback(async (experimentId: number) => {
    try {
      const approvals = await api.experimentApprovals(experimentId);
      if (selectedExperimentRef.current === experimentId) setExperimentApprovals(approvals);
    } catch (err) {
      if (selectedExperimentRef.current === experimentId) {
        setExperimentApprovals([]);
        setError(err instanceof Error ? err.message : "Unable to load experiment approvals.");
      }
    }
  }, []);

  useEffect(() => {
    if (selectedExperiment === null) {
      setExperimentApprovals([]);
      return;
    }
    void loadExperimentApprovals(selectedExperiment);
  }, [selectedExperiment, loadExperimentApprovals]);

  useEffect(() => {
    if (selectedEntry === null) {
      setAttachments([]);
      setRevisions([]);
      setEntryTags([]);
      setEntryTagDraft("");
      setEntrySignatures([]);
      setEntryTimestamps([]);
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
    api
      .entryTimestamps(selectedEntry)
      .then((items) => {
        if (active) setEntryTimestamps(items);
      })
      .catch((err: unknown) => {
        if (active) setError(err instanceof Error ? err.message : "Unable to load entry timestamps.");
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

  async function handleRequestTimestamp() {
    if (selectedEntry === null) return;
    try {
      const ts = await api.createEntryTimestamp(selectedEntry);
      setEntryTimestamps((items) => [ts, ...items]);
      setNotice(`RFC 3161 timestamp created at ${formatDate(ts.tsa_time)}.`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to request RFC 3161 timestamp.");
    }
  }

  async function handleDownloadProof(timestampId: number) {
    if (selectedEntry === null) return;
    try {
      await api.downloadTimestampProof(selectedEntry, timestampId);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to download timestamp proof bundle.");
    }
  }

  async function handleVerifyTimestamp(timestampId: number) {
    if (selectedEntry === null) return;
    try {
      const result = await api.verifyEntryTimestamp(selectedEntry, timestampId);
      setTimestampVerifications((current) => ({ ...current, [timestampId]: result }));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to verify timestamp proof.");
    }
  }

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
    const values = new FormData(form);
    const file = values.get("bundle");
    if (!(file instanceof File) || file.size === 0) {
      setError("Choose a project JSON/ZIP bundle, RO-Crate .eln archive, or eLabFTW-compatible CSV.");
      return;
    }
    try {
      const entityType = String(values.get("entity_type") ?? "experiments") as "experiments" | "resources" | "samples";
      if (entityType !== "experiments" && !file.name.toLowerCase().endsWith(".csv")) {
        setError("Inventory and sample imports require an eLabFTW-compatible CSV file.");
        return;
      }
      const result = await api.importProject(selectedProject, file, entityType);
      await loadProjects();
      const importedExperiments = await api.experiments(selectedProject);
      setExperiments(importedExperiments);
      setSelectedExperiment(importedExperiments[0]?.id ?? null);
      setNotice(entityType === "resources"
        ? `Imported ${result.resources_imported} inventory resources.`
        : entityType === "samples"
          ? `Imported ${result.samples_imported} samples into this project.`
          : `Imported ${result.experiments_imported} experiments, ${result.entries_imported} entries, ${result.attachments_imported} attachments, and ${result.tasks_imported} tasks.`);
      setError("");
      form.reset();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to import project bundle.");
    }
  }

  async function handleEntrySignature(
    meaning: RecordSignature["meaning"],
    comment: string,
    password?: string,
  ): Promise<boolean> {
    if (selectedEntry === null) return false;
    try {
      const signature = await api.signEntry(selectedEntry, meaning, comment, password);
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
      setAutosaveStatus("saved");
      const timeStr = new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
      setLastSavedTime(timeStr);
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

  async function handleSaveSketch(file: File) {
    if (selectedEntry === null) return;
    try {
      await api.uploadAttachment(selectedEntry, file);
      setAttachments(await api.attachments(selectedEntry));
      setNotice("Scientific sketch attached to this notebook entry.");
      setError("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to attach the sketch.");
      throw err;
    }
  }

  async function handleSaveMolecule(files: File[]) {
    if (selectedEntry === null) return;
    try {
      for (const file of files) await api.uploadAttachment(selectedEntry, file);
      setAttachments(await api.attachments(selectedEntry));
      setNotice("Molecule SVG and editable JSON attached to this notebook entry.");
      setError("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to attach the molecule structure.");
      throw err;
    }
  }

  async function handleSaveStoichiometryAttachment(file: File) {
    if (selectedEntry === null) return;
    try {
      await api.uploadAttachment(selectedEntry, file);
      setAttachments(await api.attachments(selectedEntry));
      setNotice(t("Stoichiometry calculation attached to this notebook entry."));
      setError("");
    } catch (err) {
      setError(err instanceof Error ? err.message : t("Unable to attach the stoichiometry calculation."));
      throw err;
    }
  }

  function handleInsertStoichiometryMarkdown(markdown: string) {
    const textarea = document.getElementById("entry-content") as HTMLTextAreaElement | null;
    if (textarea) {
      const cur = textarea.value;
      const next = cur ? `${cur}\n\n${markdown}` : markdown;
      textarea.value = next;
      textarea.dispatchEvent(new Event("input", { bubbles: true }));
    }
    setEntries((items) =>
      items.map((entry) =>
        entry.id === selectedEntry
          ? { ...entry, content: entry.content ? `${entry.content}\n\n${markdown}` : markdown }
          : entry
      )
    );
    setNotice(t("Stoichiometry table inserted into notebook entry."));
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
        </div>
        <div className="workspace-label">{t("WORKSPACE")}</div>
        <div className="sidebar-heading">
          <span>{t("Projects")}</span>
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
          {projects.length === 0 && <p className="empty-hint">{t("Create your first project below.")}</p>}
        </nav>
        <form className="quick-create" onSubmit={handleCreateProject}>
          <label htmlFor="project-name">{t("New project")}</label>
          <input id="project-name" name="name" placeholder={t("Project name")} required maxLength={160} />
          <textarea name="description" placeholder={t("Short description (optional)")} rows={2} />
          <button className="button button-primary button-full" type="submit">
            {t("Create project")}
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
            <span>{t("Workspace")}</span>
            <span className="crumb-divider">/</span>
            <strong>{selectedProjectData?.name ?? t("Your notebook")}</strong>
          </div>
          <div className="topbar-right">
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
            <div className="notification-menu">
              <button className="button button-outline notification-toggle" aria-label={t("Notifications")} aria-expanded={notificationsOpen} onClick={() => setNotificationsOpen((open) => !open)}>
                {t("Notifications")}
                {notifications.some((item) => !item.read_at) && <span className="notification-badge">{notifications.filter((item) => !item.read_at).length}</span>}
              </button>
              {notificationsOpen && <section className="notification-panel" aria-label={t("Notifications")}>
                <header><strong>{t("Notifications")}</strong><button className="button button-outline button-small" onClick={() => void loadNotifications()}>{t("Refresh")}</button></header>
                {notifications.length ? notifications.map((item) => <button key={item.id} className={`notification-item${item.read_at ? "" : " notification-unread"}`} onClick={() => void markNotificationRead(item)}>
                  <strong>{item.title}</strong><span>{item.message}</span><small>{formatDate(item.created_at)}</small>
                </button>) : <p className="empty-hint">{t("No notifications yet")}</p>}
              </section>}
            </div>
            <label className="locale-picker">
              <span>{t("Language / भाषा")}</span>
              <select aria-label="Language / भाषा" value={locale} onChange={(event) => {
                const nextLocale = event.target.value as Locale;
                saveLocale(nextLocale);
                setLocale(nextLocale);
              }}>
                <option value="en">English</option>
                <option value="hi">हिन्दी</option>
              </select>
            </label>
            <form className="global-search" onSubmit={handleSearch}>
              <input name="query" placeholder={`${t("Search records")}…`} aria-label={t("Search records")} maxLength={100} />
              <button className="button button-outline" type="submit">🔍 {t("Search")}</button>
            </form>
            <button
              className="button button-outline"
              type="button"
              onClick={() => setBarcodeScannerOpen(true)}
              style={{ display: "inline-flex", alignItems: "center", gap: 6, borderColor: "#d8c8f7", color: "#3F1899" }}
              title="Scan 2D/1D barcodes or QR codes from bench camera"
            >
              📷 {t("Scan Label")}
            </button>
            <button
              className="button button-outline"
              type="button"
              onClick={() => setChemSearchOpen(true)}
              style={{ display: "inline-flex", alignItems: "center", gap: 6, borderColor: "#d8c8f7", color: "#3F1899" }}
              title="Search molecules by SMILES, formula, or functional group"
            >
              ⚛️ {t("Structure Search")}
            </button>
            <span className="environment-badge">LOCAL WORKSPACE</span>
            <button className="button button-outline" onClick={() => setInventoryOpen((open) => !open)}>
              🧪 {t("Lab inventory")}
            </button>
            <button className="button button-outline" onClick={() => setTemplatesOpen((open) => !open)}>
              📄 {t("Templates")}
            </button>
            <button className="button button-outline" onClick={() => setEquipmentOpen((open) => !open)}>
              🔬 {t("Equipment")}
            </button>
            <button className="button button-outline" onClick={() => setLocationsOpen((open) => !open)}>
              🧊 {t("Storage locations")}
            </button>
            {user.role === "admin" && (
              <button className="button button-outline" onClick={() => setIntegrationsOpen((open) => !open)}>
                🔌 {t("Integrations")}
              </button>
            )}
            {user.role === "admin" && (
              <button className="button button-outline" onClick={() => setAdminOpen((open) => !open)}>
                ⚙️ {t("Organization admin")}
              </button>
            )}
            {selectedProjectData &&
              (projectAccessRole === "admin" || projectAccessRole === "owner") && (
                <button
                  className="button button-outline"
                  onClick={() => setProjectAccessOpen((open) => !open)}
                >
                  {t("Project access")}
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
                {t("Verify audit chain")}
              </button>
            )}
            <button className="button button-outline" onClick={onLogout}>{t("Sign out")}</button>
            <span className="avatar avatar-small">R</span>
          </div>
        </header>

        {/* Short-Lived Toast Notification System */}
        <div className="aura-toast-container" aria-live="polite">
          {toasts.map((toast) => (
            <div key={toast.id} className={`aura-toast aura-toast-${toast.type}`} role="alert">
              <span className="toast-icon">
                {toast.type === "error" && "⚠️"}
                {toast.type === "success" && "✓"}
                {toast.type === "info" && "ℹ️"}
              </span>
              <span className="toast-message">{toast.message}</span>
              <button
                className="toast-close"
                type="button"
                onClick={() => setToasts((prev) => prev.filter((t) => t.id !== toast.id))}
                aria-label="Dismiss notification"
              >
                &times;
              </button>
            </div>
          ))}
        </div>
        {/* Parity Modals: Barcode Scanner, Formal Report, Chemical Search */}
        <BarcodeScannerModal
          isOpen={barcodeScannerOpen}
          onClose={() => setBarcodeScannerOpen(false)}
          onDetected={handleBarcodeDetected}
        />

        {selectedExperimentData && (
          <FormalReportView
            isOpen={formalReportOpen}
            onClose={() => setFormalReportOpen(false)}
            experiment={selectedExperimentData}
            entries={entries}
            project={selectedProjectData}
            currentUser={user}
            auditTrail={activity}
          />
        )}

        <ChemicalSearchModal
          isOpen={chemSearchOpen}
          onClose={() => setChemSearchOpen(false)}
          onSelectResult={handleChemSearchResult}
          inventoryItems={inventoryItems}
          entries={entries}
        />

        {adminOpen && user.role === "admin" && (
          <AdminPanel
            currentUserId={user.id}
            onClose={() => setAdminOpen(false)}
          />
        )}
        {integrationsOpen && user.role === "admin" && (
          <WebhookIntegrationsPanel onClose={() => setIntegrationsOpen(false)} />
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
            user={user}
            organizationUsers={organizationUsers}
            onClose={() => setInventoryOpen(false)}
          />
        )}
        {equipmentOpen && (
          <EquipmentPanel
            projects={projects}
            user={user}
            onClose={() => setEquipmentOpen(false)}
            locale={locale}
            t={t}
          />
        )}
        {locationsOpen && (
          <StorageLocationsPanel user={user} onClose={() => setLocationsOpen(false)} />
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
            <p className="muted search-hint">
              Search spans project descriptions, notebook entries, inventory, samples, equipment, templates, and tags.
            </p>
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
            <h1>{t("A clear record of every discovery.")}</h1>
            <p>{t("Create a project to organize experiments, methods, and research notes in one place.")}</p>
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
                    {t(tasksOpen ? "Hide tasks" : "Tasks")}
                  </button>
                  <button
                    className="button button-outline"
                    type="button"
                    onClick={() => setWorkflowRulesOpen((open) => !open)}
                  >
                    {t(workflowRulesOpen ? "Hide workflows" : "Workflows")}
                  </button>
                  <button
                    className="button button-outline"
                    type="button"
                    onClick={() => void handleProjectExport("json")}
                  >
                    📥 {t("Export JSON")}
                  </button>
                  <button
                    className="button button-outline"
                    type="button"
                    onClick={() => void handleProjectExport("csv")}
                  >
                    📊 {t("Export CSV")}
                  </button>
                  <button
                    className="button button-outline"
                    type="button"
                    onClick={() => void handleProjectBundleExport()}
                  >
                    📦 {t("Export ZIP")}
                  </button>
                  {projectAccessRole !== null && projectAccessRole !== "viewer" && (
                    <form className="project-import-form" onSubmit={handleProjectImport}>
                      <input
                        aria-label="Import project JSON/ZIP, RO-Crate ELN, or eLabFTW CSV"
                        name="bundle"
                        type="file"
                        accept=".json,.zip,.eln,.csv,application/json,application/zip,application/vnd.eln+zip,text/csv"
                        required
                      />
                      <select name="entity_type" aria-label="Import records as">
                        <option value="experiments">Import as experiments</option>
                        <option value="resources">Import CSV rows as inventory resources</option>
                        <option value="samples">Import CSV rows as samples</option>
                      </select>
                      <small className="project-import-help">CSV rows can become experiments, inventory resources, or project samples. Sample CSV columns include title/name, type/category, external_id, parent_external_id, location, description/body, metadata, and tags; attachments require an ELN archive.</small>
                      <button className="button button-outline" type="submit">
                        {t("Import")}
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
              {workflowRulesOpen && selectedProject !== null && (
                <WorkflowRulesPanel
                  projectId={selectedProject}
                  writable={projectAccessRole !== null && projectAccessRole !== "viewer"}
                  translate={t}
                  onClose={() => setWorkflowRulesOpen(false)}
                />
              )}

              <div className="section-heading">
                <div>
                  <h2>{t("Experiments")}</h2>
                  <p>{t("Organize your work into focused investigations.")}</p>
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
                  <div className="inline-empty">{t("No experiments yet. Start with the form below.")}</div>
                )}
              </div>

              <form className="inline-form" onSubmit={handleCreateExperiment}>
                <input name="name" placeholder={t("New experiment name")} required maxLength={160} />
                <input name="description" placeholder={t("Brief description (optional)")} maxLength={5000} />
                <button className="button button-outline" type="submit">{t("Add experiment")}</button>
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
                        {t("Status")}
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
                          <option value="in_progress">{t("In progress")}</option>
                          <option value="completed">{t("Completed")}</option>
                          <option value="archived">{t("Archived")}</option>
                        </select>
                      </label>
                      <button
                        className="button button-primary"
                        onClick={() => void handleCreateEntry()}
                        disabled={
                          projectAccessRole === null || projectAccessRole === "viewer"
                        }
                      >
                        <span>＋</span> {t("New entry")}
                      </button>
                      <button
                        className="button button-outline"
                        type="button"
                        onClick={async () => {
                          try {
                            await api.exportAuditTrail(selectedExperimentData.id, "csv");
                            setNotice("Audit trail CSV downloaded.");
                          } catch {
                            setError("Failed to download audit trail CSV.");
                          }
                        }}
                      >
                        Audit Trail (CSV)
                      </button>
                      <button
                        className="button button-outline"
                        type="button"
                        onClick={async () => {
                          try {
                            await api.exportAuditTrail(selectedExperimentData.id, "json");
                            setNotice("Audit trail JSON downloaded.");
                          } catch {
                            setError("Failed to download audit trail JSON.");
                          }
                        }}
                      >
                        Audit Trail (JSON)
                      </button>
                      <button
                        className="button button-primary"
                        type="button"
                        onClick={() => setFormalReportOpen(true)}
                        style={{ display: "inline-flex", alignItems: "center", gap: 6, background: "#3F1899", borderColor: "#3F1899" }}
                        title="Generate regulatory-compliant GLP/GMP printable laboratory report"
                      >
                        📄 {t("Formal PDF Report")}
                      </button>
                    </div>
                  </div>
                  <ExperimentApprovalPanel
                    key={selectedExperimentData.id}
                    experimentId={selectedExperimentData.id}
                    experimentStatus={selectedExperimentData.status}
                    approvals={experimentApprovals}
                    organizationUsers={organizationUsers}
                    projectMemberIds={projectMemberIds}
                    currentUser={user}
                    writable={projectAccessRole !== null && projectAccessRole !== "viewer"}
                    onRefresh={() => loadExperimentApprovals(selectedExperimentData.id)}
                    translate={t}
                  />
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
                              const pass = String(values.get("signaturePassword") ?? "");
                              if (
                                meaning === "authored" ||
                                meaning === "reviewed" ||
                                meaning === "approved"
                              ) {
                                void handleEntrySignature(
                                  meaning,
                                  String(values.get("comment") ?? ""),
                                  pass,
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
                            <input
                              name="signaturePassword"
                              type="password"
                              placeholder="Password (21 CFR Part 11)"
                              autoComplete="current-password"
                            />
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
                        <section className="timestamp-panel" aria-label="RFC 3161 Trusted Timestamps">
                          <div className="timestamp-header">
                            <div>
                              <strong>RFC 3161 trusted timestamps</strong>
                              <p>
                                Cryptographically verifiable timestamp proof issued by a Time Stamping Authority (TSA).
                                Proves the exact content digest existed at the specified time.
                              </p>
                            </div>
                            <button
                              className="button button-outline"
                              type="button"
                              onClick={() => void handleRequestTimestamp()}
                              disabled={projectAccessRole === null || projectAccessRole === "viewer"}
                            >
                              Request RFC 3161 timestamp
                            </button>
                          </div>
                          {entryTimestamps.length > 0 && (
                            <ul className="timestamp-list">
                              {entryTimestamps.map((ts) => (
                                <li key={ts.id} className="timestamp-item">
                                  <div>
                                    <strong>{formatDate(ts.tsa_time)}</strong> · <small>{ts.tsa_url}</small>
                                    <div className="timestamp-hash">
                                      SHA-256: <code>{ts.record_sha256.slice(0, 20)}…</code>
                                    </div>
                                  </div>
                                  <div className="workflow-rule-actions">
                                    <button className="button button-outline button-small" type="button" onClick={() => void handleVerifyTimestamp(ts.id)}>Verify proof</button>
                                    <button className="button button-outline button-small" type="button" onClick={() => void handleDownloadProof(ts.id)}>Download proof ZIP</button>
                                  </div>
                                  {timestampVerifications[ts.id] && <p className={timestampVerifications[ts.id].valid ? "admin-notice" : "inline-error"} role="status">{timestampVerifications[ts.id].message} {timestampVerifications[ts.id].token_time ? `TSA time: ${formatDate(timestampVerifications[ts.id].token_time!)}` : ""}</p>}
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
                        <details className="sketch-tools">
                          <summary>Draw a scientific sketch</summary>
                          <ScientificSketchPad
                            disabled={projectAccessRole === null || projectAccessRole === "viewer"}
                            onSave={handleSaveSketch}
                          />
                        </details>
                        <details className="sketch-tools molecule-tools">
                          <summary>{t("Draw a molecule structure")}</summary>
                          <MoleculeEditor
                            disabled={projectAccessRole === null || projectAccessRole === "viewer"}
                            onSave={handleSaveMolecule}
                            onStructureChange={setActiveMoleculeStructure}
                            t={t}
                          />
                        </details>
                        <details className="sketch-tools stoichiometry-tools">
                          <summary>{t("Reaction & stoichiometry calculator")}</summary>
                          <StoichiometryTable
                            disabled={projectAccessRole === null || projectAccessRole === "viewer"}
                            activeStructure={activeMoleculeStructure}
                            inventoryItems={inventoryItems}
                            onDeductStock={handleDeductStoichiometryStock}
                            onSaveAttachment={handleSaveStoichiometryAttachment}
                            onInsertMarkdown={handleInsertStoichiometryMarkdown}
                            t={t}
                          />
                        </details>
                        <details className="sketch-tools protocol-timer-tools">
                          <summary>⏱️ Bench timers & protocol checklist</summary>
                          <ProtocolStepTimer
                            disabled={projectAccessRole === null || projectAccessRole === "viewer"}
                            onInsertMarkdown={handleInsertStoichiometryMarkdown}
                          />
                        </details>
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
                        </div>
                        <div className="editor-mode-toggle">
                          <label className="editor-label" htmlFor="entry-content">OBSERVATIONS &amp; NOTES</label>
                          <div style={{ marginLeft: "auto", display: "flex", gap: "6px" }}>
                            <button
                              type="button"
                              className={`button button-small ${editorMode === "edit" ? "button-primary" : "button-outline"}`}
                              onClick={() => setEditorMode("edit")}
                            >
                              Edit notes
                            </button>
                            <button
                              type="button"
                              className={`button button-small ${editorMode === "preview" ? "button-primary" : "button-outline"}`}
                              onClick={() => setEditorMode("preview")}
                            >
                              Scientific preview (KaTeX)
                            </button>
                          </div>
                        </div>
                        {editorMode === "preview" ? (
                          <div className="scientific-preview-container">
                            <ScientificContent content={activeEntry.content} onNavigate={handleMentionNavigate} />
                          </div>
                        ) : (
                          <>
                            <div className="mention-toolbar" style={{ display: "flex", gap: 6, marginBottom: 6, alignItems: "center", flexWrap: "wrap" }}>
                              <small style={{ color: "#6b5f88", fontWeight: 600 }}>Insert Mention:</small>
                              <select
                                aria-label="Mention inventory reagent"
                                defaultValue=""
                                onChange={(e) => {
                                  const id = parseInt(e.target.value, 10);
                                  const item = inventoryItems.find((i) => i.id === id);
                                  if (item) {
                                    const textarea = document.getElementById("entry-content") as HTMLTextAreaElement | null;
                                    if (textarea) {
                                      const text = `[@${item.name}](#inv:${item.id}) `;
                                      const start = textarea.selectionStart;
                                      const end = textarea.selectionEnd;
                                      textarea.setRangeText(text, start, end, "end");
                                      textarea.focus();
                                    }
                                  }
                                  e.target.value = "";
                                }}
                                style={{ fontSize: "0.78rem", padding: "2px 6px", borderRadius: 4, border: "1px solid #d8c8f7", color: "#3F1899" }}
                              >
                                <option value="">🧪 @ Reagent...</option>
                                {inventoryItems.map((inv) => (
                                  <option key={inv.id} value={inv.id}>{inv.name} ({inv.quantity} {inv.unit})</option>
                                ))}
                              </select>

                              <select
                                aria-label="Mention sample record"
                                defaultValue=""
                                onChange={(e) => {
                                  const id = parseInt(e.target.value, 10);
                                  const smp = samples.find((s) => s.id === id);
                                  if (smp) {
                                    const textarea = document.getElementById("entry-content") as HTMLTextAreaElement | null;
                                    if (textarea) {
                                      const text = `[#${smp.name}](#smp:${smp.id}) `;
                                      const start = textarea.selectionStart;
                                      const end = textarea.selectionEnd;
                                      textarea.setRangeText(text, start, end, "end");
                                      textarea.focus();
                                    }
                                  }
                                  e.target.value = "";
                                }}
                                style={{ fontSize: "0.78rem", padding: "2px 6px", borderRadius: 4, border: "1px solid #c9b4f4", color: "#2b0f6c" }}
                              >
                                <option value="">🧬 # Sample...</option>
                                {samples.map((s) => (
                                  <option key={s.id} value={s.id}>{s.name} ({s.sample_type})</option>
                                ))}
                              </select>

                              <select
                                aria-label="Mention experiment"
                                defaultValue=""
                                onChange={(e) => {
                                  const id = parseInt(e.target.value, 10);
                                  const exp = experiments.find((x) => x.id === id);
                                  if (exp) {
                                    const textarea = document.getElementById("entry-content") as HTMLTextAreaElement | null;
                                    if (textarea) {
                                      const text = `[!${exp.name}](#exp:${exp.id}) `;
                                      const start = textarea.selectionStart;
                                      const end = textarea.selectionEnd;
                                      textarea.setRangeText(text, start, end, "end");
                                      textarea.focus();
                                    }
                                  }
                                  e.target.value = "";
                                }}
                                style={{ fontSize: "0.78rem", padding: "2px 6px", borderRadius: 4, border: "1px solid #f9d8a7", color: "#92540c" }}
                              >
                                <option value="">📓 ! Experiment...</option>
                                {experiments.map((exp) => (
                                  <option key={exp.id} value={exp.id}>{exp.name}</option>
                                ))}
                              </select>
                            </div>
                            <textarea
                              aria-label="Entry content"
                              id="entry-content"
                              key={`${activeEntry.id}-${activeEntry.updated_at}-content`}
                              name="content"
                              defaultValue={activeEntry.content}
                              onChange={handleEntryInputChange}
                              placeholder="Record your observations, methods, results, and next steps..."
                              maxLength={100_000}
                            />
                            <small className="editor-math-hint">
                              LaTeX &amp; formula support: inline math with <code>$E=mc^2$</code> or block equations with <code>$$...$$</code>. Supports chemical notations and scientific symbols.
                            </small>
                          </>
                        )}
                        <div className="editor-footer" style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
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
                      />
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
                  <strong>{formatLocaleDateOnly(selectedProjectData.created_at, locale)}</strong>
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

function ScientificSketchPad({
  disabled,
  onSave,
}: {
  disabled: boolean;
  onSave: (file: File) => Promise<void>;
}) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const drawing = useRef(false);
  const [hasMarks, setHasMarks] = useState(false);
  const [saving, setSaving] = useState(false);

  function getPoint(event: ReactPointerEvent<HTMLCanvasElement>) {
    const canvas = event.currentTarget;
    const bounds = canvas.getBoundingClientRect();
    return {
      x: (event.clientX - bounds.left) * (canvas.width / bounds.width),
      y: (event.clientY - bounds.top) * (canvas.height / bounds.height),
    };
  }

  function startStroke(event: ReactPointerEvent<HTMLCanvasElement>) {
    if (disabled) return;
    event.currentTarget.setPointerCapture(event.pointerId);
    const context = event.currentTarget.getContext("2d");
    if (!context) return;
    const point = getPoint(event);
    context.beginPath();
    context.moveTo(point.x, point.y);
    context.lineWidth = 3;
    context.lineCap = "round";
    context.lineJoin = "round";
    context.strokeStyle = "#253b2d";
    context.beginPath();
    context.arc(point.x, point.y, context.lineWidth / 2, 0, Math.PI * 2);
    context.fill();
    context.beginPath();
    context.moveTo(point.x, point.y);
    drawing.current = true;
    setHasMarks(true);
  }

  function continueStroke(event: ReactPointerEvent<HTMLCanvasElement>) {
    if (!drawing.current) return;
    const context = event.currentTarget.getContext("2d");
    if (!context) return;
    const point = getPoint(event);
    context.lineTo(point.x, point.y);
    context.stroke();
    setHasMarks(true);
  }

  async function saveSketch() {
    const canvas = canvasRef.current;
    if (!canvas || !hasMarks || disabled || saving) return;
    setSaving(true);
    try {
      const blob = await new Promise<Blob | null>((resolve) => canvas.toBlob(resolve, "image/png"));
      if (!blob) throw new Error("The sketch image could not be created.");
      const file = new File([blob], `notebook-sketch-${new Date().toISOString().slice(0, 10)}.png`, {
        type: "image/png",
      });
      await onSave(file);
      const context = canvas.getContext("2d");
      context?.clearRect(0, 0, canvas.width, canvas.height);
      setHasMarks(false);
    } catch {
      // The parent displays the upload error and preserves the drawing for retry.
    } finally {
      setSaving(false);
    }
  }

  function clearSketch() {
    const canvas = canvasRef.current;
    const context = canvas?.getContext("2d");
    if (!canvas || !context || disabled || saving) return;
    context.clearRect(0, 0, canvas.width, canvas.height);
    setHasMarks(false);
  }

  return (
    <div className="sketch-pad">
      <p className="auth-copy">Draw with a mouse, pen, or touch. Save the PNG as an entry attachment.</p>
      <canvas
        ref={canvasRef}
        width={840}
        height={280}
        aria-label="Freehand scientific sketch drawing area"
        aria-disabled={disabled}
        onPointerDown={startStroke}
        onPointerMove={continueStroke}
        onPointerUp={() => { drawing.current = false; }}
        onPointerCancel={() => { drawing.current = false; }}
      />
      {disabled && <small>Editing access is required to attach a sketch.</small>}
      <div>
        <button className="button button-outline" type="button" onClick={clearSketch} disabled={!hasMarks || disabled || saving}>Clear</button>
        <button className="button button-primary" type="button" onClick={() => void saveSketch()} disabled={!hasMarks || disabled || saving}>
          {saving ? "Saving sketch…" : "Attach sketch"}
        </button>
      </div>
    </div>
  );
}

function AuthScreen({
  onLogin,
  onBackToLanding,
}: {
  onLogin: (organization: string, email: string, password: string) => Promise<void>;
  onBackToLanding?: () => void;
}) {
  const [error, setErrorState] = useState("");
  const setError = useCallback((msg: string) => {
    setErrorState(msg);
    if (msg) {
      window.setTimeout(() => setErrorState(""), 5000);
    }
  }, []);
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
        {onBackToLanding && (
          <button
            className="auth-back-link"
            type="button"
            onClick={onBackToLanding}
          >
            &larr; Return to Aura Lab Overview
          </button>
        )}
        <div className="brand-mark">
            <img src="/app-icon.jpg" alt="Aura Lab" />
          </div>
        <p className="eyebrow">AURA LAB</p>
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
        <div className="brand-mark">
            <img src="/app-icon.jpg" alt="Aura Lab" />
          </div>
        <p className="eyebrow">AURA LAB</p>
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
        <div className="brand-mark">
            <img src="/app-icon.jpg" alt="Aura Lab" />
          </div>
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

function WebhookIntegrationsPanel({ onClose }: { onClose: () => void }) {
  const [endpoints, setEndpoints] = useState<WebhookEndpoint[]>([]);
  const [deliveries, setDeliveries] = useState<Record<number, WebhookDelivery[]>>({});
  const [oneTimeSecret, setOneTimeSecret] = useState("");
  const [editingId, setEditingId] = useState<number | null>(null);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const load = useCallback(async () => {
    try { setEndpoints(await api.webhookEndpoints()); setError(""); }
    catch (err) { setError(err instanceof Error ? err.message : "Unable to load integrations."); }
  }, []);
  useEffect(() => { void load(); }, [load]);

  async function create(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const values = new FormData(form);
    const eventTypes = String(values.get("event_types") ?? "*").split(",").map((item) => item.trim()).filter(Boolean);
    try {
      const result = await api.createWebhookEndpoint({ name: String(values.get("name") ?? ""), url: String(values.get("url") ?? ""), event_types: eventTypes });
      setOneTimeSecret(result.secret);
      setNotice("Integration created. Copy its signing secret now; it will not be shown again.");
      form.reset();
      await load();
    } catch (err) { setError(err instanceof Error ? err.message : "Unable to create integration."); }
  }
  async function rotate(id: number) {
    try { const result = await api.rotateWebhookSecret(id); setOneTimeSecret(result.secret); setNotice("Signing secret rotated. Copy the new secret now."); }
    catch (err) { setError(err instanceof Error ? err.message : "Unable to rotate secret."); }
  }
  async function revoke(id: number) {
    try { await api.revokeWebhookEndpoint(id); setOneTimeSecret(""); await load(); setNotice("Integration revoked and pending deliveries cancelled."); }
    catch (err) { setError(err instanceof Error ? err.message : "Unable to revoke integration."); }
  }
  async function showDeliveries(id: number) {
    try { const rows = await api.webhookDeliveries(id); setDeliveries((current) => ({ ...current, [id]: rows })); }
    catch (err) { setError(err instanceof Error ? err.message : "Unable to load delivery history."); }
  }
  async function toggle(endpoint: WebhookEndpoint) {
    try { await api.updateWebhookEndpoint(endpoint.id, { enabled: !endpoint.enabled }); await load(); }
    catch (err) { setError(err instanceof Error ? err.message : "Unable to update integration."); }
  }
  async function update(event: FormEvent<HTMLFormElement>, endpointId: number) {
    event.preventDefault();
    const values = new FormData(event.currentTarget);
    try {
      await api.updateWebhookEndpoint(endpointId, {
        name: String(values.get("name") ?? ""),
        url: String(values.get("url") ?? ""),
        event_types: String(values.get("event_types") ?? "*").split(",").map((item) => item.trim()).filter(Boolean),
      });
      setEditingId(null);
      await load();
      setNotice("Integration settings updated.");
    } catch (err) { setError(err instanceof Error ? err.message : "Unable to update integration."); }
  }
  return (
    <section className="admin-panel" aria-label="External integrations">
      <header><div><p className="eyebrow">ORGANIZATION</p><h2>External integrations</h2></div><button className="button button-outline" onClick={onClose}>Close</button></header>
      {error && <p className="auth-error" role="alert">{error}</p>}
      {notice && <p className="admin-notice" role="status">{notice}</p>}
      {oneTimeSecret && <div className="notice notice-success"><strong>Signing secret:</strong> <code>{oneTimeSecret}</code> <button className="button button-outline button-small" onClick={() => void navigator.clipboard.writeText(oneTimeSecret).then(() => setNotice("Signing secret copied."))}>Copy</button></div>}
      <form className="admin-invite-form" onSubmit={(event) => void create(event)}>
        <input name="name" placeholder="Integration name" maxLength={120} required />
        <input name="url" type="url" placeholder="https://service.example/webhook" maxLength={2048} required />
        <input name="event_types" placeholder="Event types, comma separated; * for all" defaultValue="*" />
        <small>HTTPS endpoints only. Events use source.action names, such as notebook.entry_created. Leave * to receive all organization events.</small>
        <button className="button button-primary" type="submit">Create webhook</button>
      </form>
      <div className="admin-users">
        {endpoints.map((endpoint) => (
          <article className="workflow-rule-card" key={endpoint.id}>
            {editingId === endpoint.id ? <form className="admin-invite-form" onSubmit={(event) => void update(event, endpoint.id)}><input name="name" defaultValue={endpoint.name} maxLength={120} required /><input name="url" type="url" defaultValue={endpoint.url} maxLength={2048} required /><input name="event_types" defaultValue={endpoint.event_types.join(", ")} /><button className="button button-primary" type="submit">Save</button><button className="button button-outline" type="button" onClick={() => setEditingId(null)}>Cancel</button></form> : <div className="workflow-rule-info"><strong>{endpoint.name}</strong><p><code>{endpoint.url}</code></p><small>{endpoint.event_types.join(", ")} · secret {endpoint.secret_prefix} · Created {formatDate(endpoint.created_at)}</small></div>}
            <span className={`status-chip ${endpoint.revoked_at ? "status-archived" : endpoint.enabled ? "status-completed" : "status-archived"}`}>{endpoint.revoked_at ? "Revoked" : endpoint.enabled ? "Active" : "Paused"}</span>
            {!endpoint.revoked_at && <div className="workflow-rule-actions"><button className="button button-outline" onClick={() => setEditingId(editingId === endpoint.id ? null : endpoint.id)}>Edit</button><button className="button button-outline" onClick={() => void showDeliveries(endpoint.id)}>Deliveries</button><button className="button button-outline" onClick={() => void toggle(endpoint)}>{endpoint.enabled ? "Pause" : "Enable"}</button><button className="button button-outline" onClick={() => void rotate(endpoint.id)}>Rotate secret</button><button className="button button-outline" onClick={() => void revoke(endpoint.id)}>Revoke</button></div>}
            {deliveries[endpoint.id] && <div className="workflow-rule-info">{deliveries[endpoint.id].map((delivery) => <small key={delivery.id} className="delivery-row">{delivery.event_type} · {delivery.delivered_at ? "Delivered" : delivery.failed_at ? "Failed" : `Queued · ${delivery.attempts} attempts`}{delivery.last_status_code ? ` · HTTP ${delivery.last_status_code}` : ""}{delivery.last_error ? ` · ${delivery.last_error}` : ""}</small>)}</div>}
          </article>
        ))}
        {endpoints.length === 0 && <p className="empty-hint">No external webhooks configured.</p>}
      </div>
    </section>
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
  const [viewMode, setViewMode] = useState<"list" | "dag">("list");

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
        <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
          <button
            className={viewMode === "list" ? "button button-primary" : "button button-outline"}
            type="button"
            onClick={() => setViewMode("list")}
            style={{ padding: "0.25rem 0.6rem", fontSize: "0.8rem" }}
          >
            List View
          </button>
          <button
            className={viewMode === "dag" ? "button button-primary" : "button button-outline"}
            type="button"
            onClick={() => setViewMode("dag")}
            style={{ padding: "0.25rem 0.6rem", fontSize: "0.8rem" }}
          >
            Visual DAG Canvas
          </button>
          <span className="count-pill">{tasks.length}</span>
        </div>
      </div>
      {viewMode === "dag" && (
        <WorkflowDagCanvas
          tasks={tasks}
          disabled={!writable}
          onUpdateTaskStatus={async (taskId, status) => {
            await api.updateTaskStatus(taskId, status);
            await loadTasks();
          }}
        />
      )}
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

function ExperimentApprovalPanel({
  experimentId,
  experimentStatus,
  approvals,
  organizationUsers,
  projectMemberIds,
  currentUser,
  writable,
  onRefresh,
  translate,
}: {
  experimentId: number;
  experimentStatus: Experiment["status"];
  approvals: ExperimentApproval[];
  organizationUsers: Awaited<ReturnType<typeof authApi.organizationUsers>>;
  projectMemberIds: number[];
  currentUser: AuthUser;
  writable: boolean;
  onRefresh: () => Promise<void>;
  translate: (text: string) => string;
}) {
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [reviewerChoice, setReviewerChoice] = useState("");
  const [reviewerSequence, setReviewerSequence] = useState<number[]>([]);
  const [rejectionReviewerChoice, setRejectionReviewerChoice] = useState("");
  const [rejectionReviewerSequence, setRejectionReviewerSequence] = useState<number[]>([]);
  const [reviewMode, setReviewMode] = useState<ExperimentApproval["review_mode"]>("sequential");
  const eligibleReviewers = organizationUsers.filter((member) =>
    member.is_active
    && member.id !== currentUser.id
    && (member.role === "admin" || projectMemberIds.includes(member.id)),
  );

  async function requestApproval(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const formElement = event.currentTarget;
    const form = new FormData(formElement);
    try {
      await api.requestExperimentApproval(
        experimentId,
        reviewerSequence,
        String(form.get("comment") ?? ""),
        reviewMode,
        reviewMode === "sequential" ? rejectionReviewerSequence : [],
      );
      formElement.reset();
      setReviewerSequence([]);
      setRejectionReviewerSequence([]);
      setReviewerChoice("");
      setRejectionReviewerChoice("");
      setReviewMode("sequential");
      setNotice(translate("Approval requested."));
      setError("");
      await onRefresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : translate("Unable to request approval."));
    }
  }

  async function decideApproval(
    formElement: HTMLFormElement,
    approvalId: number,
    status: "approved" | "rejected",
  ) {
    const form = new FormData(formElement);
    try {
      const result = await api.decideExperimentApproval(
        approvalId,
        status,
        String(form.get("decision_comment") ?? ""),
      );
      setNotice(translate(result.status === "stale" ? "Experiment changed; request a new review." : `Approval ${result.status}.`));
      setError("");
      await onRefresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : translate("Unable to record approval decision."));
    }
  }

  return (
    <section className="experiment-approval-panel" aria-label={translate("Experiment approval") }>
      <div className="experiment-approval-heading">
        <strong>{translate("Experiment approval")}</strong>
        {writable && experimentStatus === "in_progress" && !approvals.some((approval) => approval.status === "pending") && (
          <form className="experiment-approval-request" onSubmit={(event) => void requestApproval(event)}>
            <label className="approval-mode-select">
              {translate("Review mode")}
              <select name="review_mode" value={reviewMode} onChange={(event) => setReviewMode(event.target.value as ExperimentApproval["review_mode"])}>
                <option value="sequential">{translate("Sequential review")}</option>
                <option value="parallel">{translate("Parallel review; all must approve")}</option>
              </select>
            </label>
            <select aria-label={translate("Select reviewer")} value={reviewerChoice} onChange={(event) => setReviewerChoice(event.target.value)}>
              <option value="">{translate("Choose a reviewer")}</option>
              {eligibleReviewers.filter((member) => !reviewerSequence.includes(member.id) && !rejectionReviewerSequence.includes(member.id)).map((member) => (
                <option value={member.id} key={member.id}>{member.display_name}</option>
              ))}
            </select>
            <button className="button button-outline" type="button" disabled={!reviewerChoice || reviewerSequence.length >= 10} onClick={() => {
              const reviewerId = Number(reviewerChoice);
              if (Number.isInteger(reviewerId) && !rejectionReviewerSequence.includes(reviewerId) && eligibleReviewers.some((member) => member.id === reviewerId)) {
                setReviewerSequence((sequence) => sequence.includes(reviewerId) || sequence.length >= 10 ? sequence : [...sequence, reviewerId]);
                setReviewerChoice("");
              }
            }}>{translate("Add reviewer")}</button>
            {reviewerSequence.length > 0 && <div className="experiment-approval-sequence">
              {reviewerSequence.map((reviewerId, index) => (
                <div className="experiment-approval-sequence-step" key={reviewerId}>
                  <span>{index + 1}. {eligibleReviewers.find((member) => member.id === reviewerId)?.display_name ?? `#${reviewerId}`}</span>
                  <button type="button" className="button button-outline" disabled={reviewMode === "parallel" || index === 0} aria-label={translate("Move reviewer up")} onClick={() => setReviewerSequence((sequence) => {
                    const next = [...sequence];
                    [next[index - 1], next[index]] = [next[index], next[index - 1]];
                    return next;
                  })}>↑</button>
                  <button type="button" className="button button-outline" disabled={reviewMode === "parallel" || index === reviewerSequence.length - 1} aria-label={translate("Move reviewer down")} onClick={() => setReviewerSequence((sequence) => {
                    const next = [...sequence];
                    [next[index], next[index + 1]] = [next[index + 1], next[index]];
                    return next;
                  })}>↓</button>
                  <button type="button" className="button button-outline" aria-label={translate("Remove reviewer")} onClick={() => setReviewerSequence((sequence) => sequence.filter((id) => id !== reviewerId))}>×</button>
                </div>
              ))}
            </div>}
            {reviewMode === "sequential" && <>
              <strong>{translate("Reviewers if rejected")}</strong>
              <select aria-label={translate("Select rejection-path reviewer")} value={rejectionReviewerChoice} onChange={(event) => setRejectionReviewerChoice(event.target.value)}>
                <option value="">{translate("Choose a reviewer")}</option>
                {eligibleReviewers.filter((member) => !reviewerSequence.includes(member.id) && !rejectionReviewerSequence.includes(member.id)).map((member) => (
                  <option value={member.id} key={member.id}>{member.display_name}</option>
                ))}
              </select>
              <button className="button button-outline" type="button" disabled={!rejectionReviewerChoice || rejectionReviewerSequence.length >= 10} onClick={() => {
                const reviewerId = Number(rejectionReviewerChoice);
                if (Number.isInteger(reviewerId) && eligibleReviewers.some((member) => member.id === reviewerId)) {
                  setRejectionReviewerSequence((sequence) => sequence.includes(reviewerId) || sequence.length >= 10 ? sequence : [...sequence, reviewerId]);
                  setRejectionReviewerChoice("");
                }
              }}>{translate("Add rejection-path reviewer")}</button>
              {rejectionReviewerSequence.length > 0 && <div className="experiment-approval-sequence">
                {rejectionReviewerSequence.map((reviewerId, index) => <div className="experiment-approval-sequence-step" key={reviewerId}>
                  <span>{index + 1}. {eligibleReviewers.find((member) => member.id === reviewerId)?.display_name ?? `#${reviewerId}`}</span>
                  <button type="button" className="button button-outline" disabled={index === 0} aria-label={translate("Move reviewer up")} onClick={() => setRejectionReviewerSequence((sequence) => { const next = [...sequence]; [next[index - 1], next[index]] = [next[index], next[index - 1]]; return next; })}>↑</button>
                  <button type="button" className="button button-outline" disabled={index === rejectionReviewerSequence.length - 1} aria-label={translate("Move reviewer down")} onClick={() => setRejectionReviewerSequence((sequence) => { const next = [...sequence]; [next[index], next[index + 1]] = [next[index + 1], next[index]]; return next; })}>↓</button>
                  <button type="button" className="button button-outline" aria-label={translate("Remove reviewer")} onClick={() => setRejectionReviewerSequence((sequence) => sequence.filter((id) => id !== reviewerId))}>×</button>
                </div>)}
              </div>}
              <small>{translate("If any main-path reviewer rejects, this sequential review path starts. The experiment snapshot must remain unchanged.")}</small>
            </>}
            <small>{translate(reviewMode === "parallel"
              ? "All selected reviewers are notified at once; each must approve, and any rejection ends the request."
              : "Add reviewers in order. Each reviewer must approve before the next step begins; up to ten reviewers are allowed.")}</small>
            <input name="comment" placeholder={translate("Review request note (optional)")} maxLength={2000} />
            <button className="button button-outline" type="submit" disabled={reviewerSequence.length === 0}>
              {translate("Request approval")}
            </button>
          </form>
        )}
      </div>
      {error && <p className="auth-error" role="alert">{error}</p>}
      {notice && <p className="admin-notice" role="status">{notice}</p>}
      {approvals.map((approval) => {
        const requester = organizationUsers.find((member) => member.id === approval.requested_by_user_id);
        const ownPendingStep = approval.step_history.some((step) => step.reviewer_user_id === currentUser.id && step.status === "pending");
        const canDecide = approval.status === "pending"
          && approval.requested_by_user_id !== currentUser.id
          && (currentUser.role === "admin" || (approval.review_mode === "parallel" ? ownPendingStep : approval.reviewer_user_id === currentUser.id));
        return (
          <article className="experiment-approval-record" key={approval.id}>
            <div className="experiment-approval-record-heading">
              <span className={`status-chip status-${approval.status}`}>{translate(approval.status)}</span>
              <small>{translate("Requested by")} {requester?.display_name ?? `#${approval.requested_by_user_id}`} · {approval.review_mode === "parallel"
                ? `${translate("Parallel review")}: ${approval.step_history.filter((step) => step.status === "approved").length}/${approval.reviewer_user_ids.length} ${translate("approved")}`
                : `${approval.active_branch === "rejection" ? `${translate("Rejection path")} · ` : ""}${translate("Step")} ${Math.min(approval.current_step_index + 1, approval.active_branch === "rejection" ? approval.rejection_reviewer_user_ids.length : approval.reviewer_user_ids.length)} / ${approval.active_branch === "rejection" ? approval.rejection_reviewer_user_ids.length : approval.reviewer_user_ids.length}`}</small>
            </div>
            {approval.request_comment && <p>{approval.request_comment}</p>}
            {approval.status === "stale" && approval.decision_comment && <p>{approval.decision_comment}</p>}
            <div className="experiment-approval-steps">
              {approval.step_history.map((step) => {
                const reviewer = organizationUsers.find((member) => member.id === step.reviewer_user_id);
                return <small key={`${approval.id}-${step.step_order}`}>
                  {step.step_order}. {step.branch === "rejection" ? `${translate("Rejection path")}: ` : ""}{reviewer?.display_name ?? `#${step.reviewer_user_id}`} · {translate(step.status)}{step.comment ? ` — ${step.comment}` : ""}
                </small>;
              })}
            </div>
            <small>{translate("Reviewed snapshot")} {approval.snapshot_digest.slice(0, 16)}… · {formatDate(approval.requested_at)}</small>
            {canDecide && <form className="experiment-approval-decision" onSubmit={(event) => { event.preventDefault(); void decideApproval(event.currentTarget, approval.id, "approved"); }}>
              <input name="decision_comment" placeholder={translate("Reviewer note (optional)")} maxLength={2000} />
              <button className="button button-outline" type="submit">{translate("Approve")}</button>
              <button className="button button-outline" type="button" onClick={(event) => {
                const form = event.currentTarget.form;
                if (form) void decideApproval(form, approval.id, "rejected");
              }}>{translate("Reject")}</button>
            </form>}
          </article>
        );
      })}
      {approvals.length === 0 && <small className="muted">{translate("No approval requests yet.")}</small>}
    </section>
  );
}

function InventoryPanel({
  projects,
  user,
  organizationUsers,
  onClose,
}: {
  projects: Project[];
  user: AuthUser;
  organizationUsers: Awaited<ReturnType<typeof authApi.organizationUsers>>;
  onClose: () => void;
}) {
  const [items, setItems] = useState<InventoryItem[]>([]);
  const [samples, setSamples] = useState<SampleRecord[]>([]);
  const [labelData, setLabelData] = useState<LabelData | null>(null);
  const [storageLocations, setStorageLocations] = useState<StorageLocation[]>([]);
  const [customFieldDefinitions, setCustomFieldDefinitions] = useState<InventoryCustomFieldDefinition[]>([]);
  const [editingCustomFieldId, setEditingCustomFieldId] = useState<number | null>(null);
  const [sampleHistory, setSampleHistory] = useState<Record<number, ActivityEvent[]>>({});
  const [sampleTransfers, setSampleTransfers] = useState<Record<number, SampleCustodyTransfer[]>>({});
  const [sampleTransferChoices, setSampleTransferChoices] = useState<Record<number, string>>({});
  const [historyOpenFor, setHistoryOpenFor] = useState<number | null>(null);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const loadRecords = useCallback(async () => {
    try {
      const [inventoryItems, sampleRecords, locs, customFields, pendingTransfers] = await Promise.all([
        api.inventory(),
        api.samples(),
        api.storageLocations(),
        api.inventoryCustomFields(),
        api.pendingSampleCustodyTransfers(),
      ]);
      setItems(inventoryItems);
      setSamples(sampleRecords);
      setStorageLocations(locs);
      setCustomFieldDefinitions(customFields);
      setSampleTransfers(pendingTransfers.reduce<Record<number, SampleCustodyTransfer[]>>((grouped, transfer) => {
        (grouped[transfer.sample_id] ??= []).push(transfer);
        return grouped;
      }, {}));
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
    const locationIdValue = String(form.get("location_id") ?? "");
    const customFields = Object.fromEntries(
      customFieldDefinitions
        .filter((definition) => definition.status === "active")
        .map((definition) => [definition.name, String(form.get(`custom_field:${definition.id}`) ?? "").trim()])
        .filter(([, value]) => value !== ""),
    );
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
        location_id: locationIdValue ? Number(locationIdValue) : null,
        notes: String(form.get("notes") ?? ""),
        custom_fields: customFields,
      });
      formElement.reset();
      setNotice("Inventory item added.");
      await loadRecords();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to add inventory item.");
    }
  }

  async function createCustomFieldDefinition(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const formElement = event.currentTarget;
    const form = new FormData(formElement);
    const fieldType = String(form.get("field_type") ?? "text") as InventoryCustomFieldDefinition["field_type"];
    try {
      await api.createInventoryCustomField({
        name: String(form.get("name") ?? "").trim(),
        field_type: fieldType,
        required: form.get("required") === "on",
        options: fieldType === "select"
          ? String(form.get("options") ?? "").split(",").map((option) => option.trim()).filter(Boolean)
          : [],
      });
      formElement.reset();
      setNotice("Inventory field added.");
      await loadRecords();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to add inventory field.");
    }
  }

  async function setCustomFieldStatus(field: InventoryCustomFieldDefinition, status: InventoryCustomFieldDefinition["status"]) {
    try {
      await api.setInventoryCustomFieldStatus(field.id, status);
      setNotice(status === "archived" ? "Inventory field archived." : "Inventory field restored.");
      await loadRecords();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to update inventory field.");
    }
  }

  async function updateCustomFieldDefinition(
    event: FormEvent<HTMLFormElement>,
    definition: InventoryCustomFieldDefinition,
  ) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const fieldType = String(form.get("field_type") ?? definition.field_type) as InventoryCustomFieldDefinition["field_type"];
    try {
      await api.updateInventoryCustomField(definition.id, {
        name: String(form.get("name") ?? "").trim(),
        field_type: fieldType,
        required: form.get("required") === "on",
        options: fieldType === "select"
          ? String(form.get("options") ?? "").split(",").map((option) => option.trim()).filter(Boolean)
          : [],
      });
      setEditingCustomFieldId(null);
      setNotice("Inventory field updated.");
      await loadRecords();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to update inventory field.");
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
    const parentSampleIdValue = String(form.get("parent_sample_id") ?? "");
    const storageLocationIdValue = String(form.get("storage_location_id") ?? "");
    const parentSample = parentSampleIdValue
      ? samples.find((sample) => sample.id === Number(parentSampleIdValue))
      : undefined;
    if (parentSample?.project_id && projectIdValue && Number(projectIdValue) !== parentSample.project_id) {
      setError("A derived sample must remain in its parent sample's project.");

    }
    try {
      await api.createSample({
        name: String(form.get("name") ?? ""),
        sample_type: String(form.get("sample_type") ?? ""),
        external_id: String(form.get("external_id") ?? ""),
        project_id: parentSample?.project_id ?? (projectIdValue ? Number(projectIdValue) : null),
        parent_sample_id: parentSampleIdValue ? Number(parentSampleIdValue) : null,
        storage_location: String(form.get("storage_location") ?? ""),
        storage_location_id: storageLocationIdValue ? Number(storageLocationIdValue) : null,
        description: String(form.get("description") ?? ""),
      });
      formElement.reset();
      setNotice("Sample registered.");
      await loadRecords();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to register sample.");
    }
  }

  async function moveSample(event: FormEvent<HTMLFormElement>, sampleId: number) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const rawLocationId = String(form.get("storage_location_id") ?? "");
    try {
      await api.moveSample(sampleId, {
        storage_location_id: rawLocationId ? Number(rawLocationId) : null,
        storage_location: String(form.get("storage_location") ?? "").trim(),
      });
      setNotice("Sample location updated.");
      await loadRecords();
      if (historyOpenFor === sampleId) {
        const history = await api.sampleLocationHistory(sampleId);
        setSampleHistory((current) => ({ ...current, [sampleId]: history }));
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to update sample location.");
    }
  }

  async function toggleSampleHistory(sampleId: number) {
    if (historyOpenFor === sampleId) {
      setHistoryOpenFor(null);
      return;
    }
    try {
      const history = await api.sampleLocationHistory(sampleId);
      const transfers = await api.sampleCustodyTransfers(sampleId);
      setSampleHistory((current) => ({ ...current, [sampleId]: history }));
      setSampleTransfers((current) => ({ ...current, [sampleId]: transfers }));
      setHistoryOpenFor(sampleId);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to load sample movement history.");
    }
  }

  async function requestSampleTransfer(event: FormEvent<HTMLFormElement>, sampleId: number) {
    event.preventDefault();
    const formElement = event.currentTarget;
    const form = new FormData(formElement);
    try {
      await api.requestSampleCustodyTransfer(
        sampleId,
        Number(form.get("to_user_id")),
        String(form.get("request_note") ?? ""),
      );
      formElement.reset();
      setSampleTransferChoices((current) => ({ ...current, [sampleId]: "" }));
      setNotice("Custody transfer requested. The recipient must confirm receipt.");
      const transfers = await api.sampleCustodyTransfers(sampleId);
      setSampleTransfers((current) => ({ ...current, [sampleId]: transfers }));
      await loadRecords();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to request sample transfer.");
    }
  }

  async function acceptSampleTransfer(event: FormEvent<HTMLFormElement>, transfer: SampleCustodyTransfer) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    try {
      await api.acceptSampleCustodyTransfer(
        transfer.sample_id,
        transfer.id,
        String(form.get("receipt_note") ?? ""),
      );
      setNotice("Sample receipt confirmed; custody is now recorded under your account.");
      const [transfers, history] = await Promise.all([
        api.sampleCustodyTransfers(transfer.sample_id),
        api.sampleLocationHistory(transfer.sample_id),
      ]);
      setSampleTransfers((current) => ({ ...current, [transfer.sample_id]: transfers }));
      setSampleHistory((current) => ({ ...current, [transfer.sample_id]: history }));
      await loadRecords();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to confirm sample receipt.");
    }
  }

  async function cancelSampleTransfer(sampleId: number, transferId: number) {
    try {
      await api.cancelSampleCustodyTransfer(sampleId, transferId);
      setNotice("Pending sample transfer cancelled.");
      const transfers = await api.sampleCustodyTransfers(sampleId);
      setSampleTransfers((current) => ({ ...current, [sampleId]: transfers }));
      await loadRecords();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to cancel sample transfer.");
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
        <select name="location_id" defaultValue="">
          <option value="">Unassigned structured location</option>
          {storageLocations.map((loc) => (
            <option key={loc.id} value={loc.id}>
              {loc.code ? `[${loc.code}] ` : ""}{loc.name} ({loc.location_type})
            </option>
          ))}
        </select>
        <input name="location" placeholder="Free-text location note" maxLength={200} />
        <input name="notes" placeholder="Notes" maxLength={5000} />
        {customFieldDefinitions.filter((definition) => definition.status === "active").map((definition) => (
          <label key={definition.id} className="inventory-custom-field">
            <span>{definition.name}{definition.required ? " *" : ""}</span>
            {definition.field_type === "select" ? (
              <select name={`custom_field:${definition.id}`} required={definition.required} defaultValue="">
                <option value="">Select {definition.name}</option>
                {definition.options.map((option) => <option key={option} value={option}>{option}</option>)}
              </select>
            ) : definition.field_type === "boolean" ? (
              <select name={`custom_field:${definition.id}`} required={definition.required} defaultValue="">
                <option value="">Choose…</option><option value="true">Yes</option><option value="false">No</option>
              </select>
            ) : (
              <input
                name={`custom_field:${definition.id}`}
                type={definition.field_type === "number" ? "number" : definition.field_type === "date" ? "date" : "text"}
                required={definition.required}
                step={definition.field_type === "number" ? "any" : undefined}
              />
            )}
          </label>
        ))}
        <button className="button button-primary" type="submit">Add inventory item</button>
      </form>
      {user.role === "admin" && <section className="inventory-custom-field-admin" aria-label="Inventory field settings">
        <h4>Custom inventory fields</h4>
        <div style={{ marginBottom: "0.75rem" }}>
          <label className="button button-outline" style={{ cursor: "pointer", display: "inline-block" }}>
            Import eLabFTW Schema (.json)
            <input
              type="file"
              accept=".json,application/json"
              style={{ display: "none" }}
              onChange={async (e) => {
                const file = e.target.files?.[0];
                if (!file) return;
                try {
                  const text = await file.text();
                  const parsed = JSON.parse(text);
                  const result = await api.importElabftwSchema(parsed);
                  setNotice(`Imported ${result.imported_count} custom fields from eLabFTW schema (skipped ${result.skipped_count} existing).`);
                  const updated = await api.inventoryCustomFields();
                  setCustomFieldDefinitions(updated);
                } catch (err) {
                  setError(err instanceof Error ? err.message : "Failed to import eLabFTW schema.");
                }
                e.target.value = "";
              }}
            />
          </label>
        </div>
        <form className="inventory-form" onSubmit={(event) => void createCustomFieldDefinition(event)}>
          <input name="name" placeholder="Field name" required maxLength={120} />
          <select name="field_type" defaultValue="text">
            <option value="text">Text</option><option value="number">Number</option><option value="date">Date</option><option value="boolean">Yes / no</option><option value="select">Select list</option>
          </select>
          <input name="options" placeholder="Select options (comma separated)" maxLength={12000} />
          <label><input type="checkbox" name="required" /> Required</label>
          <button className="button button-outline" type="submit">Add field</button>
        </form>
        {customFieldDefinitions.map((definition) => (
          <div className="inventory-custom-field-row" key={definition.id}>
            {editingCustomFieldId === definition.id ? (
              <form className="inventory-custom-field-edit" onSubmit={(event) => void updateCustomFieldDefinition(event, definition)}>
                <input name="name" aria-label="Field name" defaultValue={definition.name} required maxLength={120} />
                <select name="field_type" aria-label="Field type" defaultValue={definition.field_type}>
                  <option value="text">Text</option><option value="number">Number</option><option value="date">Date</option><option value="boolean">Yes / no</option><option value="select">Select list</option>
                </select>
                <input name="options" aria-label="Select options" defaultValue={definition.options.join(", ")} placeholder="Select options (comma separated)" maxLength={12000} />
                <label><input type="checkbox" name="required" defaultChecked={definition.required} /> Required</label>
                <button className="button button-primary" type="submit">Save</button>
                <button className="button button-outline" type="button" onClick={() => setEditingCustomFieldId(null)}>Cancel</button>
              </form>
            ) : <>
              <span>{definition.name} · {definition.field_type}{definition.required ? " · required" : ""}{definition.options.length ? ` · ${definition.options.join(", ")}` : ""}</span>
              <div className="inventory-custom-field-actions">
                <button className="button button-outline" type="button" onClick={() => setEditingCustomFieldId(definition.id)}>Edit</button>
                <button className="button button-outline" type="button" onClick={() => void setCustomFieldStatus(definition, definition.status === "active" ? "archived" : "active")}>
                  {definition.status === "active" ? "Archive" : "Restore"}
                </button>
              </div>
            </>}
          </div>
        ))}
      </section>}
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
                  onClick={() => setLabelData({
                    title: item.name,
                    idCode: `INV-${item.id}`,
                    type: item.category,
                  })}
                  style={{ padding: "0.2rem 0.5rem", fontSize: "0.75rem" }}
                >
                  🏷️ Label / QR
                </button>
                <button
                  className="button button-outline"
                  type="button"
                  onClick={() => void changeResourceStatus("inventory", item.id, item.status === "active" ? "archived" : "active")}
                >
                  {item.status === "active" ? "Archive" : "Reactivate"}
                </button>
              </div>
            </div>
            <small>
              {item.category} · {item.location || "No text location"} · Lot {item.lot_number || "not specified"}
              {item.location_id && (
                <span className="location-tag">
                  📍 {storageLocations.find((l) => l.id === item.location_id)?.name ?? `Location #${item.location_id}`}
                </span>
              )}
            </small>
            <ResourceTagEditor entityType="inventory" entityId={item.id} />
            {Object.entries(item.custom_fields ?? {}).map(([fieldName, value]) => (
              <small key={`${item.id}-${fieldName}`}><strong>{fieldName}:</strong> {value}</small>
            ))}
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
        <select name="parent_sample_id" defaultValue="">
          <option value="">Original sample (no parent)</option>
          {samples.filter((sample) => sample.status === "active").map((sample) => (
            <option key={sample.id} value={sample.id}>
              {sample.name}{sample.external_id ? ` · ${sample.external_id}` : ""}
            </option>
          ))}
        </select>
        <select name="storage_location_id" defaultValue="">
          <option value="">Unassigned structured location</option>
          {storageLocations.map((loc) => (
            <option key={loc.id} value={loc.id}>
              {loc.code ? `[${loc.code}] ` : ""}{loc.name} ({loc.location_type})
            </option>
          ))}
        </select>
        <input name="storage_location" placeholder="Free-text location note" maxLength={200} />
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
                  onClick={() => setLabelData({
                    title: sample.name,
                    idCode: sample.external_id || `SMP-${sample.id}`,
                    type: sample.sample_type,
                    creator: `User #${sample.created_by_user_id}`,
                  })}
                  style={{ padding: "0.2rem 0.5rem", fontSize: "0.75rem" }}
                >
                  🏷️ Label / QR
                </button>
                <button
                  className="button button-outline"
                  type="button"
                  onClick={() => void changeResourceStatus("sample", sample.id, sample.status === "active" ? "archived" : "active")}
                >
                  {sample.status === "active" ? "Archive" : "Reactivate"}
                </button>
              </div>
            </div>
            <small>
              {sample.external_id || "No sample ID"} · {sample.storage_location || "No text location"} · {projects.find((project) => project.id === sample.project_id)?.name ?? "Organization sample"}
              {sample.storage_location_id && (
                <span className="location-tag">
                  📍 {storageLocations.find((l) => l.id === sample.storage_location_id)?.name ?? `Location #${sample.storage_location_id}`}
                </span>
              )}
            </small>
            {sample.parent_sample_id && (
              <small className="sample-lineage">
                Derived from {samples.find((parent) => parent.id === sample.parent_sample_id)?.name ?? `sample #${sample.parent_sample_id}`}
              </small>
            )}
            {samples.some((child) => child.parent_sample_id === sample.id) && (
              <small className="sample-lineage">
                Derived samples: {samples.filter((child) => child.parent_sample_id === sample.id).map((child) => child.name).join(", ")}
              </small>
            )}
            <small>
              Recorded custodian: {organizationUsers.find((member) => member.id === sample.current_custodian_user_id)?.display_name ?? `User #${sample.current_custodian_user_id}`}
            </small>
            {sample.status === "active" && sample.current_custodian_user_id === user.id && !(sampleTransfers[sample.id] ?? []).some((transfer) => transfer.status === "pending") && (
              <form className="sample-move-form" onSubmit={(event) => void requestSampleTransfer(event, sample.id)}>
                <select
                  name="to_user_id"
                  aria-label={`Transfer ${sample.name} to`}
                  value={sampleTransferChoices[sample.id] ?? ""}
                  onChange={(event) => setSampleTransferChoices((current) => ({ ...current, [sample.id]: event.target.value }))}
                  required
                >
                  <option value="">Select recipient</option>
                  {organizationUsers.filter((member) => member.is_active && member.id !== user.id).map((member) => (
                    <option key={member.id} value={member.id}>{member.display_name}</option>
                  ))}
                </select>
                <input name="request_note" placeholder="Transfer note (optional)" maxLength={2000} />
                <button className="button button-outline" type="submit">Request custody transfer</button>
              </form>
            )}
            {(sampleTransfers[sample.id] ?? []).filter((transfer) => transfer.status === "pending" && transfer.to_user_id === user.id).map((transfer) => (
              <form className="sample-move-form" key={transfer.id} onSubmit={(event) => void acceptSampleTransfer(event, transfer)}>
                <small>Incoming transfer from {organizationUsers.find((member) => member.id === transfer.from_user_id)?.display_name ?? `User #${transfer.from_user_id}`}{transfer.request_note ? `: ${transfer.request_note}` : ""}</small>
                <input name="receipt_note" placeholder="Receipt note (optional)" maxLength={2000} />
                <button className="button button-outline" type="submit">Confirm receipt and accept custody</button>
              </form>
            ))}
            {(sampleTransfers[sample.id] ?? []).filter((transfer) => transfer.status === "pending" && transfer.from_user_id === user.id).map((transfer) => (
              <small className="sample-lineage" key={`outgoing-${transfer.id}`}>
                Transfer pending with {organizationUsers.find((member) => member.id === transfer.to_user_id)?.display_name ?? `User #${transfer.to_user_id}`}. {transfer.request_note}
                <button className="button button-outline" type="button" onClick={() => void cancelSampleTransfer(sample.id, transfer.id)}>Cancel transfer</button>
              </small>
            ))}
            {sample.status === "active" && <form className="sample-move-form" onSubmit={(event) => void moveSample(event, sample.id)}>
              <select name="storage_location_id" aria-label={`New structured location for ${sample.name}`} defaultValue={sample.storage_location_id ?? ""}>
                <option value="">No structured location</option>
                {storageLocations.map((loc) => <option key={loc.id} value={loc.id}>{loc.code ? `[${loc.code}] ` : ""}{loc.name}</option>)}
              </select>
              <input name="storage_location" aria-label={`Free-text location for ${sample.name}`} placeholder="Free-text location note" defaultValue={sample.storage_location_id ? "" : sample.storage_location} maxLength={200} />
              <button className="button button-outline" type="submit">Move sample</button>
            </form>}
            <button className="button button-outline sample-history-toggle" type="button" onClick={() => void toggleSampleHistory(sample.id)}>
              {historyOpenFor === sample.id ? "Hide movement history" : "Movement history"}
            </button>
            {historyOpenFor === sample.id && <div className="sample-history-list">
              {(sampleHistory[sample.id] ?? []).map((event) => (
                <div className="sample-history-event" key={event.id}>
                  {event.action === "location_changed" ? <>
                    <strong>{event.details.from_location || "Unassigned"} → {event.details.to_location || "Unassigned"}</strong>
                    <small>{formatDate(event.occurred_at)} · User #{event.details.changed_by_user_id}</small>
                  </> : <>
                    <strong>{event.action === "custody_transfer_requested" ? "Custody transfer requested" : event.action === "custody_transfer_accepted" ? "Custody transfer accepted" : "Custody transfer cancelled"}</strong>
                    <small>{formatDate(event.occurred_at)} · User #{event.details.from_user_id ?? event.details.to_user_id}</small>
                    {(event.details.request_note || event.details.receipt_note) && <small>{event.details.request_note || event.details.receipt_note}</small>}
                  </>}
                </div>
              ))}
              {(sampleHistory[sample.id] ?? []).length === 0 && (sampleTransfers[sample.id] ?? []).length === 0 && <p className="empty-hint">No recorded sample movements yet.</p>}
            </div>}
            <ResourceTagEditor entityType="sample" entityId={sample.id} />
          </article>
        ))}
        {samples.length === 0 && <p className="empty-hint">No samples registered yet.</p>}
      </div>
      {labelData && <LabLabelGenerator data={labelData} onClose={() => setLabelData(null)} />}
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
  locale,
  t,
}: {
  projects: Project[];
  user: AuthUser;
  onClose: () => void;
  locale: Locale;
  t: (text: string) => string;
}) {
  const [equipment, setEquipment] = useState<EquipmentResource[]>([]);
  const [bookings, setBookings] = useState<EquipmentBooking[]>([]);
  const [maintenance, setMaintenance] = useState<EquipmentMaintenance[]>([]);
  const [editingMaintenanceId, setEditingMaintenanceId] = useState<number | null>(null);
  const [calendarFeeds, setCalendarFeeds] = useState<CalendarFeed[]>([]);
  const [newFeedUrl, setNewFeedUrl] = useState("");
  const [storageLocations, setStorageLocations] = useState<StorageLocation[]>([]);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const loadSchedule = useCallback(async () => {
    try {
      const [resources, reservations, locs, maintenanceRecords, feeds] = await Promise.all([
        api.equipment(),
        api.bookings(),
        api.storageLocations(),
        api.equipmentMaintenance(),
        api.calendarFeeds(),
      ]);
      setEquipment(resources);
      setBookings(reservations);
      setStorageLocations(locs);
      setMaintenance(maintenanceRecords);
      setCalendarFeeds(feeds);
      setError("");
    } catch (err) {
      setError(err instanceof Error ? err.message : t("Unable to load equipment schedule."));
    }
  }, [t]);

  async function createCalendarSubscription(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const name = String(new FormData(form).get("calendar_name") ?? "").trim();
    if (!name) return;
    try {
      const feed = await api.createCalendarFeed(name);
      const url = new URL(`/api/calendar-feeds/${feed.id}.ics`, window.location.origin);
      url.searchParams.set("token", feed.secret);
      setNewFeedUrl(url.toString());
      setCalendarFeeds((items) => [feed, ...items]);
      form.reset();
      setNotice(t("Calendar subscription created. Copy its private URL into your calendar app."));
      setError("");
    } catch (err) {
      setError(err instanceof Error ? err.message : t("Unable to create calendar subscription."));
    }
  }

  async function importCalendarBookings(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const values = new FormData(form);
    const file = values.get("calendar_file");
    const equipmentId = Number(values.get("equipment_id"));
    if (!(file instanceof File) || file.size === 0 || !Number.isInteger(equipmentId) || equipmentId < 1) {
      setError("Choose an .ics file and an active equipment item.");
      return;
    }
    const projectIdValue = String(values.get("project_id") ?? "");
    try {
      const result = await api.importEquipmentCalendar(
        equipmentId,
        file,
        String(values.get("timezone_name") ?? "UTC"),
        projectIdValue ? Number(projectIdValue) : null,
      );
      await loadSchedule();
      setNotice(`Imported ${result.imported_count} calendar events as equipment bookings.`);
      setError("");
      form.reset();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to import calendar bookings.");
    }
  }

  async function revokeCalendarSubscription(feedId: number) {
    try {
      await api.revokeCalendarFeed(feedId);
      setCalendarFeeds((items) => items.map((feed) => feed.id === feedId ? { ...feed, revoked_at: new Date().toISOString() } : feed));
      setNewFeedUrl("");
      setNotice(t("Calendar subscription revoked."));
      setError("");
    } catch (err) {
      setError(err instanceof Error ? err.message : t("Unable to revoke calendar subscription."));
    }
  }

  useEffect(() => {
    void loadSchedule();
  }, [loadSchedule]);

  async function addEquipment(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const formElement = event.currentTarget;
    const form = new FormData(formElement);
    const storageLocationIdValue = String(form.get("storage_location_id") ?? "");
    try {
      await api.createEquipment({
        name: String(form.get("name") ?? ""),
        description: String(form.get("description") ?? ""),
        location: String(form.get("location") ?? ""),
        storage_location_id: storageLocationIdValue ? Number(storageLocationIdValue) : null,
        category: String(form.get("category") ?? "equipment"),
      });
      formElement.reset();
      setNotice(t("Equipment registered."));
      await loadSchedule();
    } catch (err) {
      setError(err instanceof Error ? err.message : t("Unable to register equipment."));
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
      const isRecurring = form.get("is_recurring") === "on";
      const recurrenceUnit = String(form.get("recurrence_unit") ?? "week") as "day" | "week" | "month";
      const recurrenceInterval = Number(form.get("recurrence_interval") ?? 1);
      const recurrenceCount = form.get("recurrence_count") ? Number(form.get("recurrence_count")) : undefined;
      const recurrenceUntil = String(form.get("recurrence_until") ?? "") || undefined;
      if (isRecurring) {
        await api.createRecurringBooking(equipmentId, {
          starts_at: new Date(startValue).toISOString(),
          ends_at: new Date(endValue).toISOString(),
          purpose: String(form.get("purpose") ?? ""),
          project_id: projectIdValue ? Number(projectIdValue) : null,
          recurrence_unit: recurrenceUnit,
          recurrence_interval: recurrenceInterval > 0 ? recurrenceInterval : 1,
          recurrence_count: recurrenceCount && recurrenceCount > 0 ? recurrenceCount : undefined,
          recurrence_until: recurrenceUntil,
        });
        setNotice(t("Recurring equipment bookings created."));
      } else {
        await api.createBooking(equipmentId, {
          starts_at: new Date(startValue).toISOString(),
          ends_at: new Date(endValue).toISOString(),
          purpose: String(form.get("purpose") ?? ""),
          project_id: projectIdValue ? Number(projectIdValue) : null,
        });
        setNotice(t("Equipment booking created."));
      }
      formElement.reset();
      await loadSchedule();

      if (isRecurring) {
        await api.createRecurringBooking(equipmentId, {
          starts_at: new Date(startValue).toISOString(),
          ends_at: new Date(endValue).toISOString(),
          purpose: String(form.get("purpose") ?? ""),
          project_id: projectIdValue ? Number(projectIdValue) : null,
          recurrence_unit: recurrenceUnit,
          recurrence_interval: recurrenceInterval > 0 ? recurrenceInterval : 1,
          recurrence_count: recurrenceCount && recurrenceCount > 0 ? recurrenceCount : undefined,
          recurrence_until: recurrenceUntil,
        });
        formElement.reset();
        setNotice(t("Recurring equipment bookings created."));
      } else {
        await api.createBooking(equipmentId, {
          starts_at: new Date(startValue).toISOString(),
          ends_at: new Date(endValue).toISOString(),
          purpose: String(form.get("purpose") ?? ""),
          project_id: projectIdValue ? Number(projectIdValue) : null,
        });
        formElement.reset();
        setNotice(t("Equipment booking created."));
      }
      await loadSchedule();
    } catch (err) {
      setError(err instanceof Error ? err.message : t("Unable to book equipment."));
    }
  }

  async function cancel(bookingId: number) {
    try {
      await api.cancelBooking(bookingId);
      setNotice(t("Booking cancelled."));
      await loadSchedule();
    } catch (err) {
      setError(err instanceof Error ? err.message : t("Unable to cancel booking."));
    }
  }

  async function scheduleMaintenance(event: FormEvent<HTMLFormElement>, equipmentId: number) {
    event.preventDefault();
    const formElement = event.currentTarget;
    const form = new FormData(formElement);
    try {
      await api.createEquipmentMaintenance(equipmentId, {
        title: String(form.get("title") ?? ""),
        notes: String(form.get("notes") ?? ""),
        service_provider: String(form.get("service_provider") ?? "").trim(),
        service_contact_email: String(form.get("service_contact_email") ?? "").trim(),
        service_contact_phone: String(form.get("service_contact_phone") ?? "").trim(),
        recurrence_days: form.get("recurrence_days") ? Number(form.get("recurrence_days")) : null,
        recurrence_unit: String(form.get("recurrence_unit") ?? "days") as EquipmentMaintenance["recurrence_unit"],
        recurrence_until: String(form.get("recurrence_until") ?? "") || null,
        starts_at: new Date(String(form.get("starts_at") ?? "")).toISOString(),
        ends_at: new Date(String(form.get("ends_at") ?? "")).toISOString(),
      });
      formElement.reset();
      setNotice(t("Maintenance scheduled. Equipment bookings cannot overlap this window."));
      await loadSchedule();
    } catch (err) {
      setError(err instanceof Error ? err.message : t("Unable to schedule maintenance."));
    }
  }

  async function editMaintenance(event: FormEvent<HTMLFormElement>, record: EquipmentMaintenance) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    try {
      await api.updateEquipmentMaintenance(record.id, {
        title: String(form.get("title") ?? ""),
        notes: String(form.get("notes") ?? ""),
        service_provider: String(form.get("service_provider") ?? ""),
        service_contact_email: String(form.get("service_contact_email") ?? ""),
        service_contact_phone: String(form.get("service_contact_phone") ?? ""),
        recurrence_days: form.get("recurrence_days") ? Number(form.get("recurrence_days")) : null,
        recurrence_unit: String(form.get("recurrence_unit") ?? "days") as EquipmentMaintenance["recurrence_unit"],
        recurrence_until: String(form.get("recurrence_until") ?? "") || null,
        starts_at: new Date(String(form.get("starts_at") ?? "")).toISOString(),
        ends_at: new Date(String(form.get("ends_at") ?? "")).toISOString(),
      });
      setEditingMaintenanceId(null);
      setNotice(t("Maintenance plan updated."));
      await loadSchedule();
    } catch (err) { setError(err instanceof Error ? err.message : t("Unable to edit maintenance plan.")); }
  }

  return (
    <section className="admin-panel equipment-panel" aria-label={t("Equipment scheduler")}>
      <header>
        <div><p className="eyebrow">{t("LAB SCHEDULING")}</p><h2>{t("Equipment & bookings")}</h2></div>
        <div className="equipment-panel-actions">
          <button
            className="button button-outline"
            type="button"
          onClick={() => setNotice(exportEquipmentCalendar(equipment, bookings, maintenance, user.organization_id)
              ? t("Calendar file downloaded. Import it into your calendar app.")
              : t("There are no upcoming bookings or maintenance windows to export."))}
          >
            {t("Export calendar (.ics)")}
          </button>
          <button className="button button-outline" onClick={onClose}>{t("Close")}</button>
        </div>
      </header>
      {error && <p className="auth-error" role="alert">{error}</p>}
      {notice && <p className="admin-notice" role="status">{notice}</p>}
      <section className="calendar-subscriptions" aria-label={t("Live calendar subscriptions")}>
        <div>
          <strong>{t("Live calendar subscription")}</strong>
          <p>{t("Subscribe with this private read-only feed URL. Calendar applications refresh it periodically.")}</p>
        </div>
        <form onSubmit={(event) => void createCalendarSubscription(event)}>
          <input name="calendar_name" aria-label={t("Calendar subscription name")} placeholder={t("Calendar name")} defaultValue="Equipment schedule" maxLength={120} required />
          <button className="button button-outline" type="submit">{t("Create subscription")}</button>
        </form>
        {newFeedUrl && <div className="calendar-feed-created"><code>{newFeedUrl}</code><button className="button button-outline button-small" type="button" onClick={() => void navigator.clipboard.writeText(newFeedUrl).then(() => setNotice(t("Private calendar URL copied."))).catch(() => setError(t("Unable to copy the URL. Select and copy it manually.")))}>{t("Copy URL")}</button><button className="button button-outline button-small" type="button" onClick={() => setNewFeedUrl("")}>{t("Hide URL")}</button></div>}
        {calendarFeeds.filter((feed) => feed.revoked_at === null).map((feed) => <div className="calendar-feed-row" key={feed.id}><span>{feed.name} <small>{t("Created")} {formatDate(feed.created_at)}{feed.last_used_at ? ` | ${t("Last fetched")} ${formatDate(feed.last_used_at)}` : ` | ${t("Not fetched yet")}`}</small></span><button className="button button-outline button-small" type="button" onClick={() => void revokeCalendarSubscription(feed.id)}>{t("Revoke")}</button></div>)}
      </section>
      <section className="calendar-subscriptions" aria-label="Import calendar bookings">
        <div>
          <strong>Import calendar bookings</strong>
          <p>Import .ics events for one equipment item. RRULE series expand to at most 100 bookings; recurrence exceptions and overrides are not supported. Local event times use the selected IANA time zone.</p>
        </div>
        <form onSubmit={(event) => void importCalendarBookings(event)}>
          <input name="calendar_file" type="file" accept=".ics,text/calendar,application/ics" aria-label="iCalendar file" required />
          <select name="equipment_id" aria-label="Equipment for imported bookings" defaultValue="" required>
            <option value="">Choose equipment</option>
            {equipment.filter((item) => item.status === "active").map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
          </select>
          <select name="project_id" aria-label="Project for imported bookings" defaultValue="">
            <option value="">Organization-level booking</option>
            {projects.map((project) => <option key={project.id} value={project.id}>{project.name}</option>)}
          </select>
          <input name="timezone_name" aria-label="Time zone for floating events" defaultValue={Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC"} maxLength={80} required />
          <button className="button button-outline" type="submit">Import bookings</button>
        </form>
      </section>
      {user.role === "admin" && (
        <form className="equipment-create-form" onSubmit={addEquipment}>
          <input name="name" placeholder={t("Equipment name")} required maxLength={160} />
          <input name="category" placeholder={t("Category")} defaultValue="equipment" maxLength={64} />
          <select name="storage_location_id" defaultValue="">
            <option value="">{t("Unassigned structured location")}</option>
            {storageLocations.map((loc) => (
              <option key={loc.id} value={loc.id}>
                {loc.code ? `[${loc.code}] ` : ""}{loc.name} ({t(loc.location_type)})
              </option>
            ))}
          </select>
          <input name="location" placeholder={t("Free-text location note")} maxLength={200} />
          <input name="description" placeholder={t("Description (optional)")} maxLength={5000} />
          <button className="button button-primary" type="submit">{t("Add equipment")}</button>
        </form>
      )}
      <div className="equipment-resource-list">
        {equipment.map((resource) => (
          <article className="inventory-record" key={resource.id}>
            <div className="inventory-record-heading">
              <strong>{resource.name}</strong>
              <div>
                <span className={`status-chip ${resource.status === "archived" ? "status-archived" : ""}`}>
                  {resource.status === "archived" ? t("Archived") : resource.location || t("Location unspecified")}
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
                      err instanceof Error ? err.message : t("Unable to update equipment lifecycle."),
                    ))}
                  >
                    {resource.status === "active" ? t("Archive") : t("Reactivate")}
                  </button>
                )}
              </div>
            </div>
            <small>
              {t(resource.category)}
              {resource.storage_location_id && (
                <span className="location-tag">
                  {t("Location")}: {storageLocations.find((l) => l.id === resource.storage_location_id)?.name ?? `#${resource.storage_location_id}`}
                </span>
              )}
            </small>
            {resource.description && <small>{resource.description}</small>}
            <ResourceTagEditor entityType="equipment" entityId={resource.id} />
            {user.role === "admin" && resource.status === "active" && (
              <form className="equipment-maintenance-form" onSubmit={(event) => void scheduleMaintenance(event, resource.id)}>
                <strong>{t("Schedule maintenance")}</strong>
                <input name="title" placeholder={t("Maintenance task")} required maxLength={200} />
                <input name="starts_at" type="datetime-local" required aria-label={t("Maintenance start")} />
                <input name="ends_at" type="datetime-local" required aria-label={t("Maintenance end")} />
                <input name="service_provider" placeholder={t("Service provider (optional)")} maxLength={200} />
                <input name="service_contact_email" type="email" placeholder={t("Provider email (optional)")} maxLength={320} />
                <input name="service_contact_phone" type="tel" placeholder={t("Provider phone (optional)")} maxLength={64} />
                <input name="recurrence_days" type="number" min="1" max="3650" placeholder={t("Repeat every N days (optional)")} aria-label={t("Repeat every N days")} />
                <select name="recurrence_unit" aria-label={t("Recurrence unit")} defaultValue="days"><option value="days">{t("Days")}</option><option value="weeks">{t("Weeks")}</option><option value="months">{t("Months")}</option></select>
                <label>{t("Repeat until (optional)")}<input name="recurrence_until" type="date" aria-label={t("Repeat until date")} /></label>
                <input name="notes" placeholder={t("Notes (optional)")} maxLength={5000} />
                <button className="button button-outline" type="submit">{t("Schedule")}</button>
              </form>
            )}
            {resource.status === "active" && <form className="equipment-booking-form" onSubmit={(event) => void reserve(event, resource.id)}>
              <input name="starts_at" type="datetime-local" required aria-label={t("Booking start")} />
              <input name="ends_at" type="datetime-local" required aria-label={t("Booking end")} />
              <input name="purpose" placeholder={t("Purpose")} required maxLength={500} />
              <select name="project_id" defaultValue="">
                <option value="">{t("Organization-level")}</option>
                {projects.map((project) => <option key={project.id} value={project.id}>{project.name}</option>)}
              </select>
              <details style={{ gridColumn: "1 / -1", margin: "4px 0" }}>
                <summary style={{ fontSize: "11px", color: "#477b61", cursor: "pointer", fontWeight: 600 }}>
                  {t("Repeat booking options")}
                </summary>
                <div style={{ display: "flex", gap: "8px", alignItems: "center", flexWrap: "wrap", paddingTop: "8px", fontSize: "11px" }}>
                  <label style={{ display: "flex", alignItems: "center", gap: "5px" }}>
                    <input type="checkbox" name="is_recurring" />
                    {t("Enable recurrence")}
                  </label>
                  <span>{t("Every")}</span>
                  <input name="recurrence_interval" type="number" min="1" max="30" defaultValue="1" style={{ width: "50px", minHeight: "28px" }} />
                  <select name="recurrence_unit" defaultValue="week" style={{ width: "95px", minHeight: "28px" }}>
                    <option value="day">{t("Day(s)")}</option>
                    <option value="week">{t("Week(s)")}</option>
                    <option value="month">{t("Month(s)")}</option>
                  </select>
                  <span>{t("Count")}</span>
                  <input name="recurrence_count" type="number" min="1" max="50" defaultValue="4" style={{ width: "55px", minHeight: "28px" }} />
                  <span>{t("or until")}</span>
                  <input name="recurrence_until" type="date" style={{ width: "135px", minHeight: "28px" }} />
                </div>
              </details>
              <button className="button button-outline" type="submit">{t("Book")}</button>
            </form>}
          </article>
        ))}
        {equipment.length === 0 && <p className="empty-hint">{t("No equipment has been registered yet.")}</p>}
      </div>
      <h3 className="inventory-subheading">{t("Reservations")}</h3>
      <div className="equipment-booking-list">
        {bookings.filter((booking) => booking.status === "reserved").map((booking) => (
          <article className="equipment-booking-row" key={booking.id}>
            <div>
              <strong>{equipment.find((resource) => resource.id === booking.equipment_id)?.name ?? `Equipment #${booking.equipment_id}`}</strong>
              <small>{formatDate(booking.starts_at)} - {formatDate(booking.ends_at)} | {booking.purpose}</small>
            </div>
            {(booking.booked_by_user_id === user.id || user.role === "admin") && (
              <button className="button button-outline" onClick={() => void cancel(booking.id)}>{t("Cancel")}</button>
            )}
          </article>
        ))}
        {bookings.filter((booking) => booking.status === "reserved").length === 0 &&
          <p className="empty-hint">{t("No active equipment bookings.")}</p>}
      </div>
      <h3 className="inventory-subheading">{t("Maintenance")}</h3>
      <div className="equipment-booking-list">
        {maintenance.map((record) => (
          <article className="equipment-booking-row" key={record.id}>
            <div>
              <strong>{equipment.find((resource) => resource.id === record.equipment_id)?.name ?? `Equipment #${record.equipment_id}`} | {record.title}</strong>
              <small>{formatDate(record.starts_at)} - {formatDate(record.ends_at)} | {t(record.status)}</small>
              {(record.service_provider || record.recurrence_days) && <small>
                {record.service_provider && `${t("Provider")}: ${record.service_provider}`}
                {record.service_provider && record.recurrence_days ? " | " : ""}
                {record.recurrence_days && `${t("Repeats every")} ${record.recurrence_days} ${t(record.recurrence_unit ?? "days")}`}
              </small>}
              {(record.service_contact_email || record.service_contact_phone) && <small>{t("Provider contact")}: {record.service_contact_email} {record.service_contact_phone}</small>}
              {record.recurrence_until && <small>{t("Recurrence ends")} {formatLocaleDateOnly(record.recurrence_until, locale)}</small>}
              {record.notes && <small>{record.notes}</small>}
            </div>
            {editingMaintenanceId === record.id && <form className="equipment-maintenance-form" onSubmit={(event) => void editMaintenance(event, record)}>
              <strong>{t("Edit scheduled maintenance")}</strong>
              <input name="title" defaultValue={record.title} required maxLength={200} />
              <input name="starts_at" type="datetime-local" defaultValue={dateTimeLocalValue(record.starts_at)} required aria-label={t("Maintenance start")} />
              <input name="ends_at" type="datetime-local" defaultValue={dateTimeLocalValue(record.ends_at)} required aria-label={t("Maintenance end")} />
              <input name="service_provider" defaultValue={record.service_provider} placeholder={t("Service provider")} maxLength={200} />
              <input name="service_contact_email" type="email" defaultValue={record.service_contact_email} placeholder={t("Provider email")} maxLength={320} />
              <input name="service_contact_phone" type="tel" defaultValue={record.service_contact_phone} placeholder={t("Provider phone")} maxLength={64} />
              <input name="recurrence_days" type="number" min="1" max="3650" defaultValue={record.recurrence_days ?? ""} placeholder={t("Repeat every N days")} />
              <select name="recurrence_unit" aria-label={t("Recurrence unit")} defaultValue={record.recurrence_unit ?? "days"}><option value="days">{t("Days")}</option><option value="weeks">{t("Weeks")}</option><option value="months">{t("Months")}</option></select>
              <label>{t("Repeat until")}<input name="recurrence_until" type="date" defaultValue={record.recurrence_until ?? ""} /></label>
              <input name="notes" defaultValue={record.notes} placeholder={t("Notes")} maxLength={5000} />
              <button className="button button-primary" type="submit">{t("Save plan")}</button>
              <button className="button button-outline" type="button" onClick={() => setEditingMaintenanceId(null)}>{t("Cancel edit")}</button>
            </form>}
            {user.role === "admin" && record.status !== "completed" && record.status !== "cancelled" && (
              <div className="equipment-maintenance-actions">
                {record.status === "scheduled" && <button className="button button-outline" onClick={() => setEditingMaintenanceId(record.id)}>{t("Edit")}</button>}
                {record.status === "scheduled" && <button className="button button-outline" onClick={() => void api.updateEquipmentMaintenanceStatus(record.id, "in_progress").then(loadSchedule).catch((err: unknown) => setError(err instanceof Error ? err.message : t("Unable to update maintenance.")))}>{t("Start")}</button>}
                <button className="button button-outline" onClick={() => void api.updateEquipmentMaintenanceStatus(record.id, "completed").then(loadSchedule).catch((err: unknown) => setError(err instanceof Error ? err.message : t("Unable to update maintenance.")))}>{t("Complete")}</button>
                <button className="button button-outline" onClick={() => void api.updateEquipmentMaintenanceStatus(record.id, "cancelled").then(loadSchedule).catch((err: unknown) => setError(err instanceof Error ? err.message : t("Unable to update maintenance.")))}>{t("Cancel")}</button>
              </div>
            )}
          </article>
        ))}
        {maintenance.length === 0 && <p className="empty-hint">{t("No maintenance has been scheduled.")}</p>}
      </div>
    </section>
  );
}
function StorageLocationsPanel({ user, onClose }: { user: AuthUser; onClose: () => void }) {
  const [locations, setLocations] = useState<StorageLocation[]>([]);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [samples, setSamples] = useState<SampleRecord[]>([]);
  const [gridLocation, setGridLocation] = useState<StorageLocation | null>(null);

  useEffect(() => {
    void api.samples().then(setSamples).catch(() => {});
  }, []);

  const loadLocations = useCallback(async () => {
    try {
      setLocations(await api.storageLocations(user.role === "admin"));
      setError("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to load storage locations.");
    }
  }, [user.role]);

  useEffect(() => {
    void loadLocations();
  }, [loadLocations]);

  async function createLocation(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const formElement = event.currentTarget;
    const form = new FormData(formElement);
    const parentIdValue = String(form.get("parent_id") ?? "");
    const codeVal = String(form.get("code") ?? "").trim();
    const nameVal = String(form.get("name") ?? "").trim();
    const locType = (String(form.get("location_type") ?? "room")) as StorageLocation["location_type"];
    try {
      await api.createStorageLocation({
        name: nameVal,
        location_type: locType,
        code: codeVal || `LOC-${Date.now().toString(36).toUpperCase()}`,
        parent_id: parentIdValue ? Number(parentIdValue) : null,
        description: String(form.get("description") ?? "").trim(),
      });
      formElement.reset();
      setNotice("Storage location created.");
      await loadLocations();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to create storage location.");
    }
  }

  async function updateLocation(event: FormEvent<HTMLFormElement>, locationId: number) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const rawParent = String(form.get("parent_id") ?? "");
    try {
      await api.updateStorageLocation(locationId, {
        name: String(form.get("name") ?? "").trim(),
        code: String(form.get("code") ?? "").trim(),
        location_type: String(form.get("location_type") ?? "other") as StorageLocation["location_type"],
        parent_id: rawParent ? Number(rawParent) : null,
        description: String(form.get("description") ?? "").trim(),
      });
      setEditingId(null);
      setNotice("Storage location updated.");
      await loadLocations();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to update storage location.");
    }
  }

  async function toggleLocationStatus(location: StorageLocation) {
    const nextStatus = location.status === "active" ? "archived" : "active";
    try {
      await api.setStorageLocationStatus(location.id, nextStatus);
      setNotice(`Storage location ${nextStatus === "active" ? "restored" : "archived"}.`);
      await loadLocations();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to change storage location status.");
    }
  }

  const locationMap = new Map(locations.map((l) => [l.id, l]));

  function getLocationPath(loc: StorageLocation): string {
    const parts = [loc.name];
    let curr = loc;
    while (curr.parent_id !== null) {
      const parent = locationMap.get(curr.parent_id);
      if (!parent) break;
      parts.unshift(parent.name);
      curr = parent;
    }
    return parts.join(" > ");
  }

  return (
    <section className="admin-panel storage-locations-panel" aria-label="Storage locations">
      <header>
        <div>
          <p className="eyebrow">LABORATORY LOGISTICS</p>
          <h2>Storage locations hierarchy</h2>
        </div>
        <button className="button button-outline" onClick={onClose}>Close</button>
      </header>
      <p className="auth-copy">
        Define hierarchical physical and virtual locations (facilities, rooms, freezers, shelves, racks, boxes) for sample, inventory, and equipment tracking.
      </p>
      {error && <p className="auth-error" role="alert">{error}</p>}
      {notice && <p className="admin-notice" role="status">{notice}</p>}

      {user.role === "admin" && <>
      <h3 className="inventory-subheading">Add new storage location</h3>
      <form className="location-form" onSubmit={createLocation}>
        <input name="name" placeholder="Location name (e.g. -80C Freezer A)" required maxLength={160} />
        <select name="location_type" defaultValue="freezer">
          <option value="building">Building / Facility</option>
          <option value="room">Room / Lab</option>
          <option value="freezer">Freezer (-80°C / -20°C)</option>
          <option value="refrigerator">Refrigerator (4°C)</option>
          <option value="shelf">Shelf</option>
          <option value="cabinet">Cabinet</option>
          <option value="box">Cryobox / Grid Box</option>
          <option value="other">Other</option>
        </select>
        <input name="code" placeholder="Code (e.g. FRZ-01)" maxLength={80} required />
        <select name="parent_id" defaultValue="">
          <option value="">No parent (Top-level)</option>
          {locations
            .filter((l) => l.status === "active")
            .map((l) => (
              <option key={l.id} value={l.id}>
                Inside: {getLocationPath(l)} ({l.location_type})
              </option>
            ))}
        </select>
        <input name="description" placeholder="Description / notes" maxLength={2000} />
        <button className="button button-primary" type="submit">Create location</button>
      </form>
      </>}

      {gridLocation && (
        <StorageBoxGrid
          location={gridLocation}
          samples={samples}
          disabled={user.role !== "admin"}
          onAssignCoordinate={async (sampleId, coord) => {
            await api.moveSample(sampleId, {
              storage_location_id: gridLocation.id,
              storage_location: `[${coord}]`,
            });
            setSamples(await api.samples());
            setNotice(`Sample placed in slot ${coord}.`);
          }}
          onClearCoordinate={async (sampleId) => {
            await api.moveSample(sampleId, {
              storage_location_id: gridLocation.id,
              storage_location: "",
            });
            setSamples(await api.samples());
            setNotice("Sample removed from coordinate slot.");
          }}
        />
      )}
      <h3 className="inventory-subheading">Configured locations ({locations.length})</h3>
      <div className="location-list">
        {locations.map((loc) => (
          <article className="location-card" key={loc.id}>
            {editingId === loc.id ? <form className="location-edit-form" onSubmit={(event) => void updateLocation(event, loc.id)}>
              <input name="name" aria-label="Location name" defaultValue={loc.name} required maxLength={160} />
              <input name="code" aria-label="Location code" defaultValue={loc.code} required maxLength={80} />
              <select name="location_type" aria-label="Location type" defaultValue={loc.location_type}>
                {["building", "room", "freezer", "refrigerator", "cabinet", "shelf", "box", "other"].map((type) => <option key={type} value={type}>{type}</option>)}
              </select>
              <select name="parent_id" aria-label="Parent location" defaultValue={loc.parent_id ?? ""}>
                <option value="">No parent (Top-level)</option>
                {locations.filter((item) => item.status === "active" && item.id !== loc.id).map((item) => <option key={item.id} value={item.id}>{getLocationPath(item)}</option>)}
              </select>
              <input name="description" aria-label="Description" defaultValue={loc.description} maxLength={2000} />
              <button className="button button-primary" type="submit">Save</button>
              <button className="button button-outline" type="button" onClick={() => setEditingId(null)}>Cancel</button>
            </form> : <div className="location-card-info">
              <div className="location-hierarchy-path">
                <strong>{loc.name}</strong>
                {loc.code && <span className="location-code-badge">{loc.code}</span>}
                <span className="status-chip">{loc.location_type}</span>
              </div>
              <small className="muted">Hierarchy: {getLocationPath(loc)}</small>
              {loc.description && <p className="location-description">{loc.description}</p>}
            </div>}
            <div className="location-card-meta">
              <button
                className="button button-outline"
                type="button"
                onClick={() => setGridLocation(gridLocation?.id === loc.id ? null : loc)}
                style={{ padding: "0.2rem 0.5rem", fontSize: "0.75rem" }}
              >
                {gridLocation?.id === loc.id ? "Close Grid" : "2D Grid View"}
              </button>
              <span className={`status-chip ${loc.status === "archived" ? "status-archived" : "status-completed"}`}>
                {loc.status}
              </span>
              {user.role === "admin" && <>
                {loc.status === "active" && <button className="button button-outline" onClick={() => setEditingId(loc.id)}>Edit</button>}
                <button className="button button-outline" onClick={() => void toggleLocationStatus(loc)}>{loc.status === "active" ? "Archive" : "Restore"}</button>
              </>}
            </div>
          </article>
        ))}
        {locations.length === 0 && (
          <p className="empty-hint">No storage locations configured yet. Add your first room or freezer above.</p>
        )}
      </div>
    </section>
  );
}

function WorkflowRulesPanel({
  projectId,
  writable,
  translate,
  onClose,
}: {
  projectId: number;
  writable: boolean;
  translate: (text: string) => string;
  onClose: () => void;
}) {
  const [rules, setRules] = useState<WorkflowRule[]>([]);
  const [editingRule, setEditingRule] = useState<WorkflowRule | null>(null);
  const [selectedTrigger, setSelectedTrigger] = useState<WorkflowRule["trigger_type"]>("experiment_status_changed");
  const [organizationUsers, setOrganizationUsers] = useState<Awaited<ReturnType<typeof authApi.organizationUsers>>>([]);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const loadRules = useCallback(async () => {
    try {
      setRules(await api.workflowRules(projectId));
      setError("");
    } catch (err) {
      setError(translate(err instanceof Error ? err.message : "Unable to load workflow rules."));
    }
  }, [projectId, translate]);

  useEffect(() => {
    void loadRules();
  }, [loadRules]);

  useEffect(() => {
    authApi.organizationUsers()
      .then(setOrganizationUsers)
      .catch(() => setOrganizationUsers([]));
  }, []);

  async function saveRule(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const formElement = event.currentTarget;
    const form = new FormData(formElement);
    const triggerType = String(form.get("trigger_type") ?? "experiment_status_changed") as WorkflowRule["trigger_type"];
    const rawFrom = String(form.get("from_status") ?? "in_progress");
    const fromStatus: WorkflowRule["from_status"] =
      rawFrom === "any" || !rawFrom ? null : (rawFrom as "in_progress" | "completed" | "archived");
    const toStatus = triggerType === "experiment_status_changed"
      ? String(form.get("to_status") ?? "completed") as WorkflowRule["to_status"]
      : null;
    const approvalOutcomeValue = String(form.get("approval_outcome") ?? "any");
    const approvalOutcome = triggerType === "experiment_approval_ended" && approvalOutcomeValue !== "any"
      ? approvalOutcomeValue as NonNullable<WorkflowRule["approval_outcome"]>
      : null;
    const taskPriority = String(form.get("task_priority") ?? "normal") as WorkflowRule["task_priority"];
    const dueDaysVal = form.get("due_days");
    const dueDays = dueDaysVal ? Number(dueDaysVal) : null;
    try {
      const payload = {
        name: String(form.get("name") ?? "").trim(),
        trigger_type: triggerType,
        approval_outcome: approvalOutcome,
        from_status: triggerType === "experiment_status_changed" ? fromStatus : null,
        to_status: toStatus,
        task_title: String(form.get("task_title") ?? "").trim(),
        task_description: String(form.get("task_description") ?? "").trim(),
        task_priority: taskPriority,
        due_days: dueDays,
        assigned_to_user_id: form.get("assigned_to_user_id") ? Number(form.get("assigned_to_user_id")) : null,
      };
      if (editingRule) {
        await api.updateWorkflowRule(projectId, editingRule.id, payload);
        setNotice(translate("Workflow rule updated."));
        setEditingRule(null);
      } else {
        await api.createWorkflowRule(projectId, payload);
        setNotice(translate("Workflow rule created."));
      }
      formElement.reset();
      setSelectedTrigger("experiment_status_changed");
      await loadRules();
    } catch (err) {
      setError(translate(err instanceof Error ? err.message : "Unable to create workflow rule."));
    }
  }

  async function toggleRule(rule: WorkflowRule) {
    try {
      await api.setWorkflowRuleEnabled(projectId, rule.id, !rule.enabled);
      setNotice(translate(rule.enabled ? "Workflow rule paused." : "Workflow rule enabled."));
      await loadRules();
    } catch (err) {
      setError(translate(err instanceof Error ? err.message : "Unable to update workflow rule."));
    }
  }

  return (
    <section className="task-panel workflow-panel" aria-label="Workflow automation rules">
      <header className="task-panel-header">
        <div>
          <strong>{translate("Workflow automations")}</strong>
          <small>{translate("Create tasks on experiment or entry creation, status changes, or when approval sequences end.")}</small>
        </div>
        <button className="button button-outline" type="button" onClick={onClose}>{translate("Close")}</button>
      </header>
      {error && <p className="auth-error" role="alert">{error}</p>}
      {notice && <p className="admin-notice" role="status">{notice}</p>}

      {writable && (
        <form className="workflow-form" key={editingRule?.id ?? "new-rule"} onSubmit={saveRule}>
          <h3>{editingRule ? `${translate("Edit workflow rule")}: ${editingRule.name}` : translate("Create workflow rule")}</h3>
          <input name="name" placeholder={translate("Rule name (e.g. Generate QA report on completion)")} required maxLength={160} defaultValue={editingRule?.name ?? ""} />
          <label className="workflow-trigger-select">
            {translate("Trigger")}:
            <select name="trigger_type" value={selectedTrigger} onChange={(event) => setSelectedTrigger(event.target.value as WorkflowRule["trigger_type"])}>
              <option value="experiment_status_changed">{translate("Experiment status changes")}</option>
              <option value="experiment_created">{translate("An experiment is created")}</option>
              <option value="entry_created">{translate("A notebook entry is created")}</option>
              <option value="experiment_approval_ended">{translate("An approval sequence ends")}</option>
            </select>
          </label>
          {selectedTrigger === "experiment_status_changed" ? <div className="workflow-status-row">
            <label>
              {translate("From status")}:
              <select name="from_status" defaultValue={editingRule?.from_status ?? "any"}>
                <option value="any">{translate("Any status")}</option>
                <option value="in_progress">{translate("In progress")}</option>
                <option value="completed">{translate("Completed")}</option>
                <option value="archived">{translate("Archived")}</option>
              </select>
            </label>
            <label>
              {translate("To status")}:
              <select name="to_status" defaultValue={editingRule?.to_status ?? "completed"}>
                <option value="in_progress">{translate("In progress")}</option>
                <option value="completed">{translate("Completed")}</option>
                <option value="archived">{translate("Archived")}</option>
              </select>
            </label>
          </div> : selectedTrigger === "experiment_approval_ended" ? <>
            <label className="workflow-trigger-select">
              {translate("Run this branch when the approval outcome is")}:
              <select name="approval_outcome" defaultValue={editingRule?.approval_outcome ?? "any"}>
                <option value="any">{translate("Any outcome")}</option>
                <option value="approved">{translate("approved")}</option>
                <option value="rejected">{translate("rejected")}</option>
                <option value="stale">{translate("stale")}</option>
              </select>
            </label>
            <small className="muted">{translate("This task rule is one branch of the approval outcome flow.")}</small>
          </> : <small className="muted">{translate("This trigger runs once when the selected record is created.")}</small>}
          <input name="task_title" placeholder={translate("Auto-generated task title")} required maxLength={200} defaultValue={editingRule?.task_title ?? ""} />
          <input name="task_description" placeholder={translate("Task description (optional)")} maxLength={5000} defaultValue={editingRule?.task_description ?? ""} />
          <label>
            {translate("Assign generated task to")}:
            <select name="assigned_to_user_id" defaultValue={editingRule?.assigned_to_user_id ?? ""}>
              <option value="">{translate("Leave unassigned")}</option>
              {organizationUsers.map((member) => (
                <option key={member.id} value={member.id}>{member.display_name} ({member.email})</option>
              ))}
            </select>
          </label>
          <div className="workflow-status-row">
            <label>
              {translate("Task priority")}:
              <select name="task_priority" defaultValue={editingRule?.task_priority ?? "normal"}>
                <option value="low">{translate("Low")}</option>
                <option value="normal">{translate("Normal")}</option>
                <option value="high">{translate("High")}</option>
                <option value="urgent">{translate("Urgent")}</option>
              </select>
            </label>
            <label>
              {translate("Due in (days)")}:
              <input name="due_days" type="number" min="0" max="3650" defaultValue={editingRule?.due_days ?? 3} />
            </label>
          </div>
          <button className="button button-primary" type="submit">{editingRule ? translate("Save rule") : translate("Create workflow rule")}</button>
          {editingRule && <button className="button button-outline" type="button" onClick={() => { setEditingRule(null); setSelectedTrigger("experiment_status_changed"); }}>{translate("Cancel edit")}</button>}
        </form>
      )}

      <div className="workflow-rule-list">
        {rules.map((rule) => (
          <article className="workflow-rule-card" key={rule.id}>
            <div className="workflow-rule-info">
              <strong>{rule.name}</strong>
              <div className="workflow-trigger-badge">
                {translate("Trigger")}: {rule.trigger_type === "experiment_status_changed"
                  ? <><code>{rule.from_status ? translate(rule.from_status.replaceAll("_", " ").replace(/^\w/, (letter) => letter.toUpperCase())) : translate("Any")}</code> {translate("to")} <code>{rule.to_status ? translate(rule.to_status.replaceAll("_", " ").replace(/^\w/, (letter) => letter.toUpperCase())) : ""}</code></>
                  : rule.trigger_type === "experiment_created" ? translate("Experiment created")
                    : rule.trigger_type === "entry_created" ? translate("Notebook entry created")
                      : <>{translate("Approval sequence ended")}{rule.approval_outcome ? ` · ${translate("Outcome")}: ${translate(rule.approval_outcome)}` : ` · ${translate("Any outcome")}`}</>}
              </div>
              <p className="workflow-action-text">
                {translate("Action: Create task")} "<strong>{rule.task_title}</strong>" ({translate("Priority")}: {translate(rule.task_priority.replace(/^\w/, (letter) => letter.toUpperCase()))}, {translate("Due")}: {rule.due_days !== null ? `+${rule.due_days} ${translate("days")}` : translate("none")}, {rule.assigned_to_user_id !== null ? `${translate("assigned to")} ${organizationUsers.find((member) => member.id === rule.assigned_to_user_id)?.display_name ?? `member #${rule.assigned_to_user_id}`}` : translate("unassigned")})
              </p>
              {rule.task_description && <small className="muted">{rule.task_description}</small>}
            </div>
            <span className={`status-chip ${rule.enabled ? "status-completed" : "status-archived"}`}>
              {translate(rule.enabled ? "Active" : "Inactive")}
            </span>
            {writable && <div className="workflow-rule-actions">
              <button className="button button-outline" type="button" onClick={() => { setSelectedTrigger(rule.trigger_type); setEditingRule(rule); }}>{translate("Edit")}</button>
              <button className="button button-outline" type="button" onClick={() => void toggleRule(rule)}>{translate(rule.enabled ? "Pause" : "Enable")}</button>
            </div>}
          </article>
        ))}
        {rules.length === 0 && (
          <p className="empty-hint">{translate("No workflow rules configured for this project yet.")}</p>
        )}
      </div>
    </section>
  );
}

export default function App() {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [ready, setReady] = useState(false);
  const [showLogin, setShowLogin] = useState(() => {
    const search = typeof window !== "undefined" ? window.location.search : "";
    return search.includes("login") || search.includes("organization");
  });
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
  if (!user) {
    if (!showLogin) {
      return <LandingPage onOpenLogin={() => setShowLogin(true)} />;
    }
    return <AuthScreen onLogin={login} onBackToLanding={() => setShowLogin(false)} />;
  }
  return <NotebookApp user={user} onLogout={() => void logout()} />;
}
