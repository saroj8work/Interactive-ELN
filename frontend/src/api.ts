import type {
  ActivityEvent,
  AuditVerification,
  EntryAttachment,
  EntryRevision,
  LabTask,
  RecordTagSet,
  RecordSignature,
  EquipmentBooking,
  EquipmentResource,
  Experiment,
  InventoryItem,
  NotebookTemplate,
  NotebookEntry,
  Project,
  ProjectAccess,
  ProjectMember,
  SampleRecord,
  SearchHit,
} from "./types";

let accessToken: string | null = null;

export function setAccessToken(token: string | null): void {
  accessToken = token;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const headers = new Headers(init?.headers);
  if (!(init?.body instanceof FormData)) {
    headers.set("Content-Type", "application/json");
  }
  if (accessToken) headers.set("Authorization", `Bearer ${accessToken}`);
  let response = await fetch(path, { ...init, headers });
  if (response.status === 401 && accessToken && !path.startsWith("/auth/")) {
    const refreshed = await fetch("/auth/refresh", {
      method: "POST",
      credentials: "same-origin",
    });
    if (refreshed.ok) {
      const session = (await refreshed.json()) as AuthToken;
      setAccessToken(session.access_token);
      headers.set("Authorization", `Bearer ${session.access_token}`);
      response = await fetch(path, { ...init, headers });
    } else {
      setAccessToken(null);
    }
  }
  if (!response.ok) {
    const body = (await response.json().catch(() => null)) as { detail?: string } | null;
    throw new Error(body?.detail ?? `Request failed (${response.status}).`);
  }
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

export const api = {
  projects: () => request<Project[]>("/api/projects"),
  createProject: (name: string, description: string) =>
    request<Project>("/api/projects", {
      method: "POST",
      body: JSON.stringify({ name, description }),
    }),
  projectAccess: (projectId: number) =>
    request<ProjectAccess>(`/api/projects/${projectId}/access`),
  projectMembers: (projectId: number) =>
    request<ProjectMember[]>(`/api/projects/${projectId}/members`),
  setProjectMember: (projectId: number, userId: number, role: "editor" | "viewer") =>
    request<ProjectMember>(`/api/projects/${projectId}/members/${userId}`, {
      method: "PUT",
      body: JSON.stringify({ user_id: userId, role }),
    }),
  removeProjectMember: (projectId: number, userId: number) =>
    request<void>(`/api/projects/${projectId}/members/${userId}`, { method: "DELETE" }),
  inventory: () => request<InventoryItem[]>("/api/inventory"),
  createInventoryItem: (payload: {
    name: string;
    category: string;
    catalog_number: string;
    lot_number: string;
    expires_on: string | null;
    quantity: number;
    unit: string;
    low_stock_threshold: number;
    location: string;
    notes: string;
  }) =>
    request<InventoryItem>("/api/inventory", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  adjustStock: (itemId: number, quantityDelta: number, reason: string) =>
    request(`/api/inventory/${itemId}/adjustments`, {
      method: "POST",
      body: JSON.stringify({ quantity_delta: quantityDelta, reason }),
    }),
  samples: () => request<SampleRecord[]>("/api/samples"),
  createSample: (payload: {
    name: string;
    sample_type: string;
    external_id: string;
    project_id: number | null;
    parent_sample_id: number | null;
    storage_location: string;
    description: string;
  }) =>
    request<SampleRecord>("/api/samples", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  attachments: (entryId: number) =>
    request<EntryAttachment[]>(`/api/entries/${entryId}/attachments`),
  uploadAttachment: (entryId: number, file: File) => {
    const body = new FormData();
    body.set("file", file);
    return request<EntryAttachment>(`/api/entries/${entryId}/attachments`, {
      method: "POST",
      body,
    });
  },
  downloadAttachment: async (attachment: EntryAttachment) => {
    const blob = await requestBlob(`/api/attachments/${attachment.id}/download`);
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = attachment.original_filename;
    link.click();
    URL.revokeObjectURL(url);
  },
  exportEntry: async (entryId: number) => {
    const blob = await requestBlob(`/api/entries/${entryId}/export`);
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `eln-entry-${entryId}.zip`;
    link.click();
    URL.revokeObjectURL(url);
  },
  exportProject: async (projectId: number, format: "json" | "csv") => {
    const blob = await requestBlob(`/api/projects/${projectId}/export?format=${format}`);
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `eln-project-${projectId}.${format}`;
    link.click();
    URL.revokeObjectURL(url);
  },
  exportProjectBundle: async (projectId: number) => {
    const blob = await requestBlob(`/api/projects/${projectId}/export?format=zip`);
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `eln-project-${projectId}.zip`;
    link.click();
    URL.revokeObjectURL(url);
  },
  importProject: (projectId: number, file: File) => {
    const body = new FormData();
    body.set("file", file);
    return request<{
      project_id: number;
      experiments_imported: number;
      entries_imported: number;
      attachments_imported: number;
      tasks_imported: number;
    }>(`/api/projects/${projectId}/import`, { method: "POST", body });
  },
  updateResourceStatus: (
    entityType: "inventory" | "sample" | "equipment" | "template",
    entityId: number,
    status: "active" | "archived",
  ) =>
    request(`/api/resources/${entityType}/${entityId}/status`, {
      method: "PATCH",
      body: JSON.stringify({ status }),
    }),
  templates: () => request<NotebookTemplate[]>("/api/templates"),
  createTemplate: (payload: Omit<NotebookTemplate, "id" | "organization_id" | "created_by_user_id" | "created_at" | "updated_at" | "status">) =>
    request<NotebookTemplate>("/api/templates", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  updateTemplate: (templateId: number, payload: Omit<NotebookTemplate, "id" | "organization_id" | "created_by_user_id" | "created_at" | "updated_at" | "status">) =>
    request<NotebookTemplate>(`/api/templates/${templateId}`, {
      method: "PUT",
      body: JSON.stringify(payload),
    }),
  applyTemplate: (entryId: number, templateId: number) =>
    request<NotebookEntry>(`/api/entries/${entryId}/apply-template?template_id=${templateId}`, {
      method: "POST",
    }),
  startProtocol: (projectId: number, templateId: number) =>
    request<Experiment>(
      `/api/projects/${projectId}/experiments/from-protocol?template_id=${templateId}`,
      { method: "POST" },
    ),
  experiments: (projectId: number) => request<Experiment[]>(`/api/projects/${projectId}/experiments`),
  updateExperimentStatus: (
    experimentId: number,
    status: Experiment["status"],
  ) =>
    request<Experiment>(`/api/experiments/${experimentId}/status`, {
      method: "PATCH",
      body: JSON.stringify({ status }),
    }),
  createExperiment: (projectId: number, name: string, description: string) =>
    request<Experiment>(`/api/projects/${projectId}/experiments`, {
      method: "POST",
      body: JSON.stringify({ name, description }),
    }),
  entries: (experimentId: number) =>
    request<NotebookEntry[]>(`/api/experiments/${experimentId}/entries`),
  createEntry: (experimentId: number, title: string, content: string) =>
    request<NotebookEntry>(`/api/experiments/${experimentId}/entries`, {
      method: "POST",
      body: JSON.stringify({ title, content }),
    }),
  updateEntry: (entryId: number, title: string, content: string) =>
    request<NotebookEntry>(`/api/entries/${entryId}`, {
      method: "PUT",
      body: JSON.stringify({ title, content }),
    }),
  entryRevisions: (entryId: number) =>
    request<EntryRevision[]>(`/api/entries/${entryId}/revisions`),
  restoreEntryRevision: (entryId: number, revisionId: number) =>
    request<NotebookEntry>(
      `/api/entries/${entryId}/revisions/${revisionId}/restore`,
      { method: "POST" },
    ),
  recordTags: (
    entityType: RecordTagSet["entity_type"],
    entityId: number,
  ) =>
    request<RecordTagSet>(`/api/records/${entityType}/${entityId}/tags`),
  updateRecordTags: (
    entityType: RecordTagSet["entity_type"],
    entityId: number,
    tags: string[],
  ) =>
    request<RecordTagSet>(`/api/records/${entityType}/${entityId}/tags`, {
      method: "PUT",
      body: JSON.stringify({ entity_type: entityType, tags }),
    }),
  activity: () => request<ActivityEvent[]>("/api/activity"),
  search: (query: string) =>
    request<SearchHit[]>(`/api/search?query=${encodeURIComponent(query)}`),
  tasks: (projectId: number) =>
    request<LabTask[]>(`/api/projects/${projectId}/tasks`),
  createTask: (
    projectId: number,
    payload: Pick<LabTask, "title" | "description" | "due_at" | "priority"> & {
      experiment_id: number | null;
    },
  ) =>
    request<LabTask>(`/api/projects/${projectId}/tasks`, {
      method: "POST",
      body: JSON.stringify({ ...payload, project_id: projectId }),
    }),
  updateTaskStatus: (taskId: number, status: LabTask["status"]) =>
    request<LabTask>(`/api/tasks/${taskId}/status`, {
      method: "PATCH",
      body: JSON.stringify({ status }),
    }),
  entrySignatures: (entryId: number) =>
    request<RecordSignature[]>(`/api/entries/${entryId}/signatures`),
  signEntry: (
    entryId: number,
    meaning: RecordSignature["meaning"],
    comment: string,
  ) =>
    request<RecordSignature>(`/api/entries/${entryId}/signatures`, {
      method: "POST",
      body: JSON.stringify({ entity_type: "entry", entity_id: entryId, meaning, comment }),
    }),
  verifyAuditChain: () => request<AuditVerification>("/api/audit/verify"),
  equipment: () => request<EquipmentResource[]>("/api/equipment"),
  createEquipment: (payload: { name: string; description: string; location: string; category: string }) =>
    request<EquipmentResource>("/api/equipment", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  bookings: () => request<EquipmentBooking[]>("/api/equipment/bookings"),
  createBooking: (
    equipmentId: number,
    payload: { starts_at: string; ends_at: string; purpose: string; project_id: number | null },
  ) =>
    request<EquipmentBooking>(`/api/equipment/${equipmentId}/bookings`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  cancelBooking: (bookingId: number) =>
    request<EquipmentBooking>(`/api/equipment/bookings/${bookingId}/cancel`, {
      method: "POST",
    }),
};

async function requestBlob(path: string): Promise<Blob> {
  const headers = new Headers();
  if (accessToken) headers.set("Authorization", "Bearer " + accessToken);
  let response = await fetch(path, { headers });
  if (response.status === 401 && accessToken) {
    const refreshed = await fetch("/auth/refresh", {
      method: "POST",
      credentials: "same-origin",
    });
    if (refreshed.ok) {
      const session = (await refreshed.json()) as AuthToken;
      setAccessToken(session.access_token);
      headers.set("Authorization", "Bearer " + session.access_token);
      response = await fetch(path, { headers });
    } else {
      setAccessToken(null);
    }
  }
  if (!response.ok) {
    const body = (await response.json().catch(() => null)) as { detail?: string } | null;
    throw new Error(body?.detail ?? `Request failed (${response.status}).`);
  }
  return response.blob();
}

export interface AuthUser {
  id: number;
  email: string;
  display_name: string;
  organization_id: number;
  role: "admin" | "member";
}

export interface AuthToken {
  access_token: string;
  token_type: "bearer";
  expires_in: number;
}

export interface OrganizationUser {
  id: number;
  email: string;
  display_name: string;
  role: "admin" | "member";
  is_active: boolean;
  email_verified_at: string;
  created_at: string;
}

async function authRequest<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, {
    ...init,
    credentials: "same-origin",
    headers: { "Content-Type": "application/json", ...init?.headers },
  });
  if (!response.ok) {
    const body = (await response.json().catch(() => null)) as { detail?: string } | null;
    throw new Error(body?.detail ?? `Request failed (${response.status}).`);
  }
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

export const authApi = {
  login: (organizationSlug: string, email: string, password: string) =>
    authRequest<AuthToken>("/auth/login", {
      method: "POST",
      body: JSON.stringify({
        organization_slug: organizationSlug,
        email,
        password,
      }),
    }),
  refresh: () => authRequest<AuthToken>("/auth/refresh", { method: "POST" }),
  logout: () => authRequest<void>("/auth/logout", { method: "POST" }),
  me: (token: string) =>
    authRequest<AuthUser>("/auth/me", {
      headers: { Authorization: `Bearer ${token}` },
    }),
  acceptInvitation: (token: string, displayName: string, password: string) =>
    authRequest<void>("/auth/invitations/accept", {
      method: "POST",
      body: JSON.stringify({
        token,
        display_name: displayName,
        password,
      }),
    }),
  requestPasswordReset: (organizationSlug: string, email: string) =>
    authRequest<{ status: string }>("/auth/password-reset/request", {
      method: "POST",
      body: JSON.stringify({ organization_slug: organizationSlug, email }),
    }),
  completePasswordReset: (token: string, newPassword: string) =>
    authRequest<void>("/auth/password-reset/complete", {
      method: "POST",
      body: JSON.stringify({ token, new_password: newPassword }),
    }),
  users: () => request<OrganizationUser[]>("/auth/admin/users"),
  organizationUsers: () => request<OrganizationUser[]>("/auth/users"),
  invite: (email: string, role: "admin" | "member") =>
    request<{ status: string }>("/auth/admin/invitations", {
      method: "POST",
      body: JSON.stringify({ email, role }),
    }),
  setUserActive: (userId: number, isActive: boolean) =>
    request<OrganizationUser>(`/auth/admin/users/${userId}/active?is_active=${isActive}`, {
      method: "PATCH",
    }),
};
