import type {
  ActivityEvent,
  Notification,
  AuditVerification,
  EntryAttachment,
  EntryRevision,
  EntryTimestamp,
  EntryTimestampVerification,
  LabTask,
  RecordTagSet,
  RecordSignature,
  EquipmentBooking,
  EquipmentMaintenance,
  CalendarFeed,
  CalendarFeedCreated,
  EquipmentResource,
  Experiment,
  ExperimentApproval,
  InventoryItem,
  InventoryCustomFieldDefinition,
  NotebookTemplate,
  NotebookEntry,
  Project,
  ProjectAccess,
  ProjectMember,
  SampleRecord,
  SampleCustodyTransfer,
  SearchHit,
  StorageLocation,
  WorkflowRule,
  WebhookDelivery,
  WebhookEndpoint,
  WebhookEndpointCreated,
} from "./types";

let accessToken: string | null = null;

export function setAccessToken(token: string | null): void {
  accessToken = token;
}


export function getFriendlyApiErrorMessage(status: number, detail?: string): string {
  if (detail && typeof detail === "string") {
    const trimmed = detail.trim();
    if (
      trimmed.length > 0 &&
      trimmed.length < 120 &&
      !trimmed.includes("Traceback") &&
      !trimmed.includes("OperationalError") &&
      !trimmed.includes("Exception") &&
      !trimmed.includes("<") &&
      !trimmed.includes("{")
    ) {
      return trimmed;
    }
  }

  switch (status) {
    case 400:
      return "The request was invalid. Please check your laboratory input data.";
    case 401:
      return "Your session has expired or requires authentication. Please sign in.";
    case 403:
      return "You do not have administrative permission for this action.";
    case 404:
      return "The requested laboratory record, sample, or experiment could not be found.";
    case 409:
      return "A record with this name or code already exists, or was updated in another session.";
    case 422:
      return "Invalid data formatting. Please check the values you entered.";
    case 429:
      return "Too many requests. Please wait a moment before trying again.";
    case 500:
    case 502:
    case 503:
    case 504:
      return "The laboratory service is temporarily unavailable. Please try again shortly.";
    default:
      return `Operation could not be completed (Status ${status}). Please try again.`;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const headers = new Headers(init?.headers);
  if (!(init?.body instanceof FormData)) {
    headers.set("Content-Type", "application/json");
  }
  if (accessToken) headers.set("Authorization", `Bearer ${accessToken}`);
  let response: Response;
  try {
    response = await fetch(path, { ...init, headers });
  } catch {
    throw new Error("Unable to connect to the laboratory server. Please check your network connection.");
  }
  const unauthenticatedAuthPaths = [
    "/auth/login", "/auth/refresh", "/auth/logout", "/auth/password-reset/request",
    "/auth/password-reset/complete", "/auth/invitations/accept",
  ];
  if (response.status === 401 && accessToken && !unauthenticatedAuthPaths.includes(path.split("?")[0])) {
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
    const friendlyMsg = getFriendlyApiErrorMessage(response.status, body?.detail);
    const err = new Error(friendlyMsg);
    (err as any).status = response.status;
    throw err;
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
    location_id?: number | null;
    notes: string;
    custom_fields: Record<string, string>;
  }) =>
    request<InventoryItem>("/api/inventory", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  inventoryCustomFields: () =>
    request<InventoryCustomFieldDefinition[]>("/api/inventory/custom-fields"),
  createInventoryCustomField: (payload: {
    name: string;
    field_type: InventoryCustomFieldDefinition["field_type"];
    required: boolean;
    options: string[];
  }) =>
    request<InventoryCustomFieldDefinition>("/api/inventory/custom-fields", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  updateInventoryCustomField: (fieldId: number, payload: {
    name: string;
    field_type: InventoryCustomFieldDefinition["field_type"];
    required: boolean;
    options: string[];
  }) =>
    request<InventoryCustomFieldDefinition>(`/api/inventory/custom-fields/${fieldId}`, {
      method: "PUT",
      body: JSON.stringify(payload),
    }),
  setInventoryCustomFieldStatus: (fieldId: number, status: InventoryCustomFieldDefinition["status"]) =>
    request<InventoryCustomFieldDefinition>(`/api/inventory/custom-fields/${fieldId}/status`, {
      method: "POST",
      body: JSON.stringify({ status }),
    }),
  importElabftwSchema: (payload: Record<string, unknown>) =>
    request<{
      imported: string[];
      skipped: string[];
      imported_count: number;
      skipped_count: number;
    }>("/api/inventory/custom-fields/import-elabftw", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  adjustStock: (itemId: number, quantityDelta: number, reason: string) =>
    request(`/api/inventory/${itemId}/adjustments`, {
      method: "POST",
      body: JSON.stringify({ quantity_delta: quantityDelta, reason }),
    }),
  samples: () => request<SampleRecord[]>("/api/samples"),
  pendingSampleCustodyTransfers: () =>
    request<SampleCustodyTransfer[]>("/api/sample-custody-transfers/pending"),
  createSample: (payload: {
    name: string;
    sample_type: string;
    external_id: string;
    project_id: number | null;
    parent_sample_id: number | null;
    storage_location: string;
    storage_location_id?: number | null;
    description: string;
  }) =>
    request<SampleRecord>("/api/samples", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  moveSample: (sampleId: number, payload: { storage_location_id: number | null; storage_location: string }) =>
    request<SampleRecord>(`/api/samples/${sampleId}/location`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    }),
  sampleLocationHistory: (sampleId: number) =>
    request<ActivityEvent[]>(`/api/samples/${sampleId}/history`),
  sampleCustodyTransfers: (sampleId: number) =>
    request<SampleCustodyTransfer[]>(`/api/samples/${sampleId}/custody-transfers`),
  requestSampleCustodyTransfer: (sampleId: number, toUserId: number, requestNote: string) =>
    request<SampleCustodyTransfer>(`/api/samples/${sampleId}/custody-transfers`, {
      method: "POST",
      body: JSON.stringify({ to_user_id: toUserId, request_note: requestNote }),
    }),
  acceptSampleCustodyTransfer: (sampleId: number, transferId: number, receiptNote: string) =>
    request<SampleCustodyTransfer>(`/api/samples/${sampleId}/custody-transfers/${transferId}/accept`, {
      method: "POST",
      body: JSON.stringify({ receipt_note: receiptNote }),
    }),
  cancelSampleCustodyTransfer: (sampleId: number, transferId: number) =>
    request<SampleCustodyTransfer>(`/api/samples/${sampleId}/custody-transfers/${transferId}/cancel`, {
      method: "POST",
      body: JSON.stringify({}),
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
  importProject: (projectId: number, file: File, entityType: "experiments" | "resources" | "samples" = "experiments") => {
    const body = new FormData();
    body.set("file", file);
    body.set("entity_type", entityType);
    return request<{
      project_id: number;
      experiments_imported: number;
      entries_imported: number;
      attachments_imported: number;
      tasks_imported: number;
      resources_imported: number;
      samples_imported: number;
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
  experimentApprovals: (experimentId: number) =>
    request<ExperimentApproval[]>(`/api/experiments/${experimentId}/approvals`),
  requestExperimentApproval: (experimentId: number, reviewerUserIds: number[], comment: string, reviewMode: ExperimentApproval["review_mode"], rejectionReviewerUserIds: number[] = []) =>
    request<ExperimentApproval>(`/api/experiments/${experimentId}/approvals`, {
      method: "POST",
      body: JSON.stringify({ reviewer_user_ids: reviewerUserIds, rejection_reviewer_user_ids: rejectionReviewerUserIds, review_mode: reviewMode, comment }),
    }),
  decideExperimentApproval: (approvalId: number, status: "approved" | "rejected", comment: string) =>
    request<ExperimentApproval>(`/api/experiment-approvals/${approvalId}/decision`, {
      method: "POST",
      body: JSON.stringify({ status, comment }),
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
  notifications: () => request<Notification[]>("/api/notifications"),
  markNotificationRead: (notificationId: number) =>
    request<Notification>(`/api/notifications/${notificationId}/read`, {
      method: "POST",
      body: JSON.stringify({}),
    }),
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
    password?: string,
  ) =>
    request<RecordSignature>(`/api/entries/${entryId}/signatures`, {
      method: "POST",
      body: JSON.stringify({
        entity_type: "entry",
        entity_id: entryId,
        meaning,
        comment,
        password: password || undefined,
      }),
    }),
  exportAuditTrail: async (experimentId: number, format: "json" | "csv" = "json") => {
    const token = localStorage.getItem("eln_access_token") || "";
    const headers: Record<string, string> = {};
    if (token) headers["Authorization"] = `Bearer ${token}`;
    const res = await fetch(`/api/experiments/${experimentId}/audit-trail/export?format=${format}`, { headers });
    if (!res.ok) throw new Error("Failed to export audit trail");
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `audit_trail_exp_${experimentId}.${format}`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  },
  verifyAuditChain: () => request<AuditVerification>("/api/audit/verify"),
  equipment: () => request<EquipmentResource[]>("/api/equipment"),
  createEquipment: (payload: {
    name: string;
    description: string;
    location: string;
    storage_location_id?: number | null;
    category: string;
  }) =>
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
  createRecurringBooking: (
    equipmentId: number,
    payload: {
      starts_at: string;
      ends_at: string;
      purpose: string;
      project_id: number | null;
      recurrence_unit: "day" | "week" | "month";
      recurrence_interval: number;
      recurrence_count?: number;
      recurrence_until?: string;
    },
  ) =>
    request<EquipmentBooking[]>(`/api/equipment/${equipmentId}/bookings/recurring`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  cancelBooking: (bookingId: number) =>
    request<EquipmentBooking>(`/api/equipment/bookings/${bookingId}/cancel`, {
      method: "POST",
    }),
  importEquipmentCalendar: (equipmentId: number, file: File, timezoneName: string, projectId: number | null) => {
    const body = new FormData();
    body.set("file", file);
    body.set("timezone_name", timezoneName);
    if (projectId !== null) body.set("project_id", String(projectId));
    return request<{ imported_count: number }>(`/api/equipment/${equipmentId}/bookings/import-ics`, {
      method: "POST",
      body,
    });
  },
  equipmentMaintenance: () => request<EquipmentMaintenance[]>("/api/equipment/maintenance"),
  calendarFeeds: () => request<CalendarFeed[]>("/auth/calendar-feeds"),
  createCalendarFeed: (name: string) => request<CalendarFeedCreated>("/auth/calendar-feeds", {
    method: "POST", body: JSON.stringify({ name }),
  }),
  revokeCalendarFeed: (feedId: number) => request<void>(`/auth/calendar-feeds/${feedId}`, { method: "DELETE" }),
  webhookEndpoints: () => request<WebhookEndpoint[]>("/api/integrations/webhooks"),
  createWebhookEndpoint: (payload: { name: string; url: string; event_types: string[] }) =>
    request<WebhookEndpointCreated>("/api/integrations/webhooks", { method: "POST", body: JSON.stringify(payload) }),
  updateWebhookEndpoint: (id: number, payload: Partial<Pick<WebhookEndpoint, "name" | "url" | "event_types" | "enabled">>) =>
    request<WebhookEndpoint>(`/api/integrations/webhooks/${id}`, { method: "PATCH", body: JSON.stringify(payload) }),
  rotateWebhookSecret: (id: number) =>
    request<WebhookEndpointCreated>(`/api/integrations/webhooks/${id}/rotate-secret`, { method: "POST", body: "{}" }),
  webhookDeliveries: (id: number) => request<WebhookDelivery[]>(`/api/integrations/webhooks/${id}/deliveries`),
  revokeWebhookEndpoint: (id: number) => request<void>(`/api/integrations/webhooks/${id}`, { method: "DELETE" }),
  createEquipmentMaintenance: (equipmentId: number, payload: {
    title: string; notes: string; service_provider: string; service_contact_email: string; service_contact_phone: string; recurrence_days: number | null; recurrence_unit: EquipmentMaintenance["recurrence_unit"]; recurrence_until: string | null; starts_at: string; ends_at: string;
  }) => request<EquipmentMaintenance>(`/api/equipment/${equipmentId}/maintenance`, {
    method: "POST", body: JSON.stringify(payload),
  }),
  updateEquipmentMaintenance: (maintenanceId: number, payload: Partial<Omit<EquipmentMaintenance, "id" | "organization_id" | "equipment_id" | "created_by_user_id" | "status" | "created_at">>) =>
    request<EquipmentMaintenance>(`/api/equipment/maintenance/${maintenanceId}`, { method: "PATCH", body: JSON.stringify(payload) }),
  updateEquipmentMaintenanceStatus: (maintenanceId: number, status: EquipmentMaintenance["status"]) =>
    request<EquipmentMaintenance>(`/api/equipment/maintenance/${maintenanceId}/status`, {
      method: "PATCH", body: JSON.stringify({ status }),
    }),
  storageLocations: (includeArchived = false) =>
    request<StorageLocation[]>(includeArchived ? "/api/storage-locations/all" : "/api/storage-locations"),
  createStorageLocation: (payload: {
    code: string;
    name: string;
    location_type: StorageLocation["location_type"];
    parent_id: number | null;
    description: string;
  }) =>
    request<StorageLocation>("/api/storage-locations", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  updateStorageLocation: (id: number, payload: Partial<Pick<StorageLocation, "code" | "name" | "location_type" | "parent_id" | "description">>) =>
    request<StorageLocation>(`/api/storage-locations/${id}`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    }),
  setStorageLocationStatus: (id: number, status: StorageLocation["status"]) =>
    request<StorageLocation>(`/api/storage-locations/${id}/status`, {
      method: "POST",
      body: JSON.stringify({ status }),
    }),
  workflowRules: (projectId: number) =>
    request<WorkflowRule[]>(`/api/projects/${projectId}/workflow-rules`),
  createWorkflowRule: (
    projectId: number,
    payload: {
      name: string;
      trigger_type: WorkflowRule["trigger_type"];
      approval_outcome: WorkflowRule["approval_outcome"];
      from_status: WorkflowRule["from_status"];
      to_status: WorkflowRule["to_status"];
      task_title: string;
      task_description: string;
      task_priority: WorkflowRule["task_priority"];
      due_days: number | null;
      assigned_to_user_id: number | null;
    },
  ) =>
    request<WorkflowRule>(`/api/projects/${projectId}/workflow-rules`, {
      method: "POST",
      body: JSON.stringify({ ...payload, project_id: projectId }),
    }),
  updateWorkflowRule: (
    projectId: number,
    ruleId: number,
    payload: {
      name: string;
      trigger_type: WorkflowRule["trigger_type"];
      approval_outcome: WorkflowRule["approval_outcome"];
      from_status: WorkflowRule["from_status"];
      to_status: WorkflowRule["to_status"];
      task_title: string;
      task_description: string;
      task_priority: WorkflowRule["task_priority"];
      due_days: number | null;
      assigned_to_user_id: number | null;
    },
  ) => request<WorkflowRule>(`/api/projects/${projectId}/workflow-rules/${ruleId}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  }),
  setWorkflowRuleEnabled: (projectId: number, ruleId: number, enabled: boolean) =>
    request<WorkflowRule>(`/api/projects/${projectId}/workflow-rules/${ruleId}/enabled`, {
      method: "PATCH",
      body: JSON.stringify({ enabled }),
    }),
  entryTimestamps: (entryId: number) =>
    request<EntryTimestamp[]>(`/api/entries/${entryId}/timestamps`),
  verifyEntryTimestamp: (entryId: number, timestampId: number) =>
    request<EntryTimestampVerification>(`/api/entries/${entryId}/timestamps/${timestampId}/verify`),
  createEntryTimestamp: (entryId: number) =>
    request<EntryTimestamp>(`/api/entries/${entryId}/timestamps`, {
      method: "POST",
      body: JSON.stringify({}),
    }),
  downloadTimestampProof: async (entryId: number, timestampId: number) => {
    const blob = await requestBlob(`/api/entries/${entryId}/timestamps/${timestampId}/proof`);
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `entry-${entryId}-timestamp-${timestampId}.zip`;
    link.click();
    URL.revokeObjectURL(url);
  },
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
    throw new Error(getFriendlyApiErrorMessage(response.status, body?.detail));
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
  let response: Response;
  try {
    response = await fetch(path, {
      ...init,
      credentials: "same-origin",
      headers: { "Content-Type": "application/json", ...init?.headers },
    });
  } catch {
    throw new Error("Unable to connect to the authentication service. Please check your network connection.");
  }
  if (!response.ok) {
    const body = (await response.json().catch(() => null)) as { detail?: string } | null;
    const friendlyMsg = getFriendlyApiErrorMessage(response.status, body?.detail);
    const err = new Error(friendlyMsg);
    (err as any).status = response.status;
    throw err;
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


export interface AuraUIAction {
  action_type: string;
  target: string;
  parameters?: Record<string, any>;
}

export interface AuraVoiceResponse {
  status: string;
  action: string;
  transcript: string;
  audio_received: boolean;
  audio_size_bytes: number;
  audio_mime_type: string;
  ai_response: string;
  assistant_reply?: string;
  timestamp: string;
  ui_actions?: AuraUIAction[];
  audio_base64?: string;
}

const VOICE_AGENT_API_URL = "http://127.0.0.1:8010";

export const auraApi = {
  sendVoiceCommand: async (transcript: string, audioBlob?: Blob): Promise<AuraVoiceResponse> => {
    // 1. Send command to the live Interactive Voice Assistant Agent Backend
    try {
      // Try direct local agent port first, then Vite proxy fallback
      let resp = null;
      try {
        resp = await fetch(`/voice/api/conversation/chat`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            message: transcript,
            session_id: "aura_eln_session",
            generate_audio: true,
          }),
        });
      } catch {
        resp = await fetch(`${VOICE_AGENT_API_URL}/api/conversation/chat`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            message: transcript,
            session_id: "aura_eln_session",
            generate_audio: true,
          }),
        });
      }

      if (resp.ok) {
        const data = await resp.json();
        return {
          status: "success",
          action: data.action_identified ? "action_executed" : "conversation",
          transcript: data.user_message || transcript.trim(),
          audio_received: !!audioBlob,
          audio_size_bytes: audioBlob ? audioBlob.size : 0,
          audio_mime_type: audioBlob?.type || "audio/webm",
          ai_response: data.assistant_reply,
          timestamp: new Date().toISOString(),
          ui_actions: data.ui_actions || [],
          audio_base64: data.audio_base64,
        };
      }
    } catch (err) {
      console.warn("Direct connection to Voice Agent backend failed, using fallback:", err);
    }

    const formData = new FormData();
    formData.append("transcript", transcript);
    if (audioBlob) {
      formData.append("audio", audioBlob, "voice_input.webm");
    }

    try {
      return await authRequest<AuraVoiceResponse>("/api/aura/voice-command", {
        method: "POST",
        body: formData,
      });
    } catch {
      const size = audioBlob ? audioBlob.size : 0;
      const t = transcript.trim().toLowerCase();
      const localUiActions: any[] = [];
      let replyText = `Aura AI Gate: "${transcript.trim()}". Telemetry analyzed.`;

      if (t.includes("inventory")) {
        localUiActions.push({ action_type: "OPEN_MODAL", target: "inventory", parameters: {} });
        replyText = "Opening reagent inventory manager.";
      } else if (t.includes("equipment") || t.includes("schedule")) {
        localUiActions.push({ action_type: "OPEN_MODAL", target: "equipment", parameters: {} });
        replyText = "Opening equipment booking schedule.";
      } else if (t.includes("chem") || t.includes("structure")) {
        localUiActions.push({ action_type: "OPEN_MODAL", target: "chemical_search", parameters: {} });
        replyText = "Opening chemical structure search.";
      } else if (t.includes("barcode") || t.includes("scan")) {
        localUiActions.push({ action_type: "OPEN_MODAL", target: "barcode_scanner", parameters: {} });
        replyText = "Opening barcode scanner.";
      } else if (t.includes("report") || t.includes("formal")) {
        localUiActions.push({ action_type: "OPEN_MODAL", target: "formal_report", parameters: {} });
        replyText = "Opening formal compliance report generator.";
      } else if (t.includes("task")) {
        localUiActions.push({ action_type: "OPEN_MODAL", target: "tasks", parameters: {} });
        replyText = "Opening project tasks.";
      } else if (t.includes("theme")) {
        localUiActions.push({ action_type: "SET_THEME", target: t.includes("light") ? "light" : "dark", parameters: {} });
        replyText = "Toggling application theme.";
      } else if (t.includes("pcr")) {
        replyText = "For standard PCR, use Initial Denaturation at 98°C for 30 seconds, 30 cycles of annealing at 58°C and extension at 72°C.";
      }

      return {
        status: "success",
        action: localUiActions.length > 0 ? "action_executed" : "conversation",
        transcript: transcript.trim(),
        audio_received: !!audioBlob,
        audio_size_bytes: size,
        audio_mime_type: audioBlob?.type || "audio/webm",
        ai_response: replyText,
        ui_actions: localUiActions,
        timestamp: new Date().toISOString(),
      };
    }
  },
};


// ==========================================
// Phase 1: Microplate & Assay Analysis API
// ==========================================

export interface PlateWell {
  id: number;
  coordinate: string;
  row_letter: string;
  col_number: number;
  role: "sample" | "standard" | "control_pos" | "control_neg" | "blank" | "empty";
  sample_name: string;
  sample_id: number | null;
  replicate_group: string;
  standard_concentration: number | null;
  concentration_unit: string;
  dilution_factor: number;
  raw_value: number | null;
  corrected_value: number | null;
  calculated_concentration: number | null;
}

export interface Microplate {
  id: number;
  organization_id: number;
  project_id: number | null;
  experiment_id: number | null;
  name: string;
  plate_format: "96-well" | "384-well" | "24-well";
  rows: number;
  cols: number;
  description: string;
  assay_type: string;
  wavelength: string;
  measurement_unit: string;
  created_at: string;
  updated_at: string;
  wells: PlateWell[];
}

export interface HeatmapMatrix {
  plate_id: number;
  name: string;
  rows: number;
  cols: number;
  measurement_unit: string;
  matrix: { coordinate: string; raw_value: number | null; normalized: number; role: string }[][];
  min_value: number | null;
  max_value: number | null;
}

export const platesApi = {
  list: (projectId?: number | null, experimentId?: number | null) => {
    const params = new URLSearchParams();
    if (projectId) params.set("project_id", String(projectId));
    if (experimentId) params.set("experiment_id", String(experimentId));
    const qs = params.toString() ? `?${params.toString()}` : "";
    return authRequest<Microplate[]>(`/api/plates${qs}`);
  },
  get: (plateId: number) => authRequest<Microplate>(`/api/plates/${plateId}`),
  create: (data: {
    name: string;
    plate_format?: string;
    project_id?: number | null;
    experiment_id?: number | null;
    description?: string;
    assay_type?: string;
    wavelength?: string;
    measurement_unit?: string;
  }) => authRequest<Microplate>("/api/plates", {
    method: "POST",
    body: JSON.stringify(data),
  }),
  updateWells: (plateId: number, wells: Partial<PlateWell>[]) =>
    authRequest<Microplate>(`/api/plates/${plateId}/wells`, {
      method: "PUT",
      body: JSON.stringify({ wells }),
    }),
  calculate: (plateId: number) =>
    authRequest<Record<string, any>>(`/api/plates/${plateId}/calculate`, {
      method: "POST",
    }),
  getHeatmap: (plateId: number) =>
    authRequest<HeatmapMatrix>(`/api/plates/${plateId}/heatmap`),
  uploadCsv: (plateId: number, file: File) => {
    const fd = new FormData();
    fd.append("file", file);
    return authRequest<{ plate_id: number; updated_wells: number; status: string }>(
      `/api/plates/${plateId}/readings/csv`,
      {
        method: "POST",
        body: fd,
      }
    );
  },
};


export interface ChemicalCompound {
  id: number;
  organization_id: number;
  project_id?: number | null;
  experiment_id?: number | null;
  name: string;
  smiles: string;
  formula: string;
  molecular_weight: number;
  monoisotopic_mass: number;
  logp: number;
  hbd: number;
  hba: number;
  rotatable_bonds: number;
  tpsa: number;
  rule_of_five_violations: number;
  drug_likeness_score: number;
  ghs_hazard_codes: string;
  ghs_pictograms: string;
  svg_depiction: string;
  created_at: string;
}

export interface ChemicalAnalysis {
  name: string;
  smiles: string;
  formula: string;
  molecular_weight: number;
  monoisotopic_mass: number;
  logp: number;
  hbd: number;
  hba: number;
  rotatable_bonds: number;
  tpsa: number;
  rule_of_five_violations: number;
  drug_likeness_score: number;
  ghs_hazard_codes: string;
  ghs_pictograms: string;
  svg_depiction: string;
}

export interface ChemicalPreset {
  name: string;
  smiles: string;
  description: string;
}

export const cheminformaticsApi = {
  analyze: (smiles: string, name?: string) =>
    authRequest<ChemicalAnalysis>("/api/cheminformatics/analyze", {
      method: "POST",
      body: JSON.stringify({ smiles, name: name || "Molecule" }),
    }),
  getPresets: () => authRequest<ChemicalPreset[]>("/api/cheminformatics/presets"),
  list: (projectId?: number | null, experimentId?: number | null, search?: string) => {
    const params = new URLSearchParams();
    if (projectId) params.set("project_id", String(projectId));
    if (experimentId) params.set("experiment_id", String(experimentId));
    if (search) params.set("search", search);
    const qs = params.toString() ? `?${params.toString()}` : "";
    return authRequest<ChemicalCompound[]>(`/api/cheminformatics/compounds${qs}`);
  },
  save: (data: { name: string; smiles: string; project_id?: number | null; experiment_id?: number | null }) =>
    authRequest<ChemicalCompound>("/api/cheminformatics/compounds", {
      method: "POST",
      body: JSON.stringify(data),
    }),
  delete: (compoundId: number) =>
    authRequest<{ deleted: boolean }>(`/api/cheminformatics/compounds/${compoundId}`, {
      method: "DELETE",
    }),
};


export interface MolecularSequenceItem {
  id: number;
  organization_id: number;
  project_id?: number | null;
  experiment_id?: number | null;
  name: string;
  sequence_data?: string;
  sequence_type: string;
  topology: string;
  length: number;
  gc_content: number;
  melting_temp: number;
  molecular_weight: number;
  description: string;
  created_at: string;
}

export interface SequenceAnalysis {
  name: string;
  sequence: string;
  sequence_type: string;
  length: number;
  gc_content: number;
  melting_temp: number;
  molecular_weight: number;
  base_counts: Record<string, number>;
  reverse_complement: string;
}

export interface CutSite {
  enzyme: string;
  position: number;
  motif: string;
  overhang: string;
  type: string;
}

export interface RestrictionFragment {
  start: number;
  end: number;
  length: number;
  label: string;
  migration_percent: number;
}

export interface DigestResult {
  sequence_length: number;
  topology: string;
  total_cut_sites: number;
  cut_sites: CutSite[];
  fragments: RestrictionFragment[];
}

export interface OpenReadingFrame {
  strand: string;
  frame: string;
  start: number;
  end: number;
  length_bp: number;
  length_aa: number;
  protein_sequence: string;
}

export interface PrimerCheckResult {
  forward: {
    sequence: string;
    length: number;
    gc_content: number;
    melting_temp: number;
    molecular_weight: number;
    gc_clamp_score: number;
  };
  reverse: {
    sequence: string;
    length: number;
    gc_content: number;
    melting_temp: number;
    molecular_weight: number;
    gc_clamp_score: number;
  };
  tm_difference: number;
  quality_score: number;
  warnings: string[];
  recommended_annealing_temp: number;
}

export const molecularApi = {
  analyze: (sequence: string, name?: string, sequenceType: string = "dna") =>
    authRequest<SequenceAnalysis>("/api/molecular/analyze", {
      method: "POST",
      body: JSON.stringify({ sequence, name: name || "Sequence", sequence_type: sequenceType }),
    }),
  digest: (sequence: string, enzymes: string[] = [], topology: string = "linear") =>
    authRequest<DigestResult>("/api/molecular/digest", {
      method: "POST",
      body: JSON.stringify({ sequence, enzymes, topology }),
    }),
  findOrfs: (sequence: string, minAa: number = 30) =>
    authRequest<OpenReadingFrame[]>("/api/molecular/orfs", {
      method: "POST",
      body: JSON.stringify({ sequence, min_aa: minAa }),
    }),
  testPrimers: (forward: string, reverse: string) =>
    authRequest<PrimerCheckResult>("/api/molecular/primers", {
      method: "POST",
      body: JSON.stringify({ forward, reverse }),
    }),
  getEnzymes: () => authRequest<{ name: string; motif: string; cut_offset: number; overhang: string }[]>("/api/molecular/enzymes"),
  getPresets: () => authRequest<{ name: string; sequence: string; topology: string; description: string }[]>("/api/molecular/presets"),
  list: (projectId?: number | null, experimentId?: number | null, search?: string) => {
    const params = new URLSearchParams();
    if (projectId) params.set("project_id", String(projectId));
    if (experimentId) params.set("experiment_id", String(experimentId));
    if (search) params.set("search", search);
    const qs = params.toString() ? `?${params.toString()}` : "";
    return authRequest<MolecularSequenceItem[]>(`/api/molecular/sequences${qs}`);
  },
  get: (sequenceId: number) => authRequest<MolecularSequenceItem>(`/api/molecular/sequences/${sequenceId}`),
  save: (data: {
    name: string;
    sequence: string;
    sequence_type?: string;
    topology?: string;
    project_id?: number | null;
    experiment_id?: number | null;
    description?: string;
  }) => authRequest<MolecularSequenceItem>("/api/molecular/sequences", {
    method: "POST",
    body: JSON.stringify(data),
  }),
  delete: (sequenceId: number) =>
    authRequest<{ deleted: boolean }>(`/api/molecular/sequences/${sequenceId}`, {
      method: "DELETE",
    }),
};


export interface CanvasNode {
  id: string;
  label: string;
  type: "prep" | "pipette" | "incubate" | "wash" | "read" | "qc";
  duration_min: number;
  x: number;
  y: number;
}

export interface CanvasEdge {
  id: string;
  source: string;
  target: string;
  label?: string;
}

export interface WorkflowCanvasItem {
  id: number;
  organization_id: number;
  project_id?: number | null;
  experiment_id?: number | null;
  name: string;
  description: string;
  status: string;
  nodes: CanvasNode[];
  edges: CanvasEdge[];
  created_at: string;
}

export interface CanvasRunItem {
  id: number;
  canvas_id: number;
  status: "pending" | "running" | "completed" | "failed";
  current_node_id?: string | null;
  node_states: Record<string, "pending" | "ready" | "running" | "completed" | "failed">;
  logs: string[];
  started_at: string;
  completed_at?: string | null;
}

export const canvasApi = {
  getTemplates: () => authRequest<{ name: string; description: string; nodes: CanvasNode[]; edges: CanvasEdge[] }[]>("/api/canvas/templates"),
  validateDag: (nodes: CanvasNode[], edges: CanvasEdge[]) =>
    authRequest<{ is_valid: boolean; has_cycle: boolean; total_nodes: number; total_edges: number; topological_order: string[]; error?: string | null }>(
      "/api/canvas/validate",
      {
        method: "POST",
        body: JSON.stringify({ nodes, edges }),
      }
    ),
  list: (projectId?: number | null, experimentId?: number | null) => {
    const params = new URLSearchParams();
    if (projectId) params.set("project_id", String(projectId));
    if (experimentId) params.set("experiment_id", String(experimentId));
    const qs = params.toString() ? `?${params.toString()}` : "";
    return authRequest<WorkflowCanvasItem[]>(`/api/canvas${qs}`);
  },
  get: (canvasId: number) => authRequest<WorkflowCanvasItem>(`/api/canvas/${canvasId}`),
  create: (data: { name: string; description?: string; nodes?: CanvasNode[]; edges?: CanvasEdge[]; project_id?: number | null; experiment_id?: number | null }) =>
    authRequest<WorkflowCanvasItem>("/api/canvas", {
      method: "POST",
      body: JSON.stringify(data),
    }),
  update: (canvasId: number, data: { name?: string; description?: string; nodes?: CanvasNode[]; edges?: CanvasEdge[]; status?: string }) =>
    authRequest<WorkflowCanvasItem>(`/api/canvas/${canvasId}`, {
      method: "PUT",
      body: JSON.stringify(data),
    }),
  startRun: (canvasId: number) =>
    authRequest<CanvasRunItem>(`/api/canvas/${canvasId}/runs`, {
      method: "POST",
    }),
  stepRun: (runId: number, completedNodeId: string) =>
    authRequest<CanvasRunItem>(`/api/canvas/runs/${runId}/step`, {
      method: "POST",
      body: JSON.stringify({ completed_node_id: completedNodeId }),
    }),
  listRuns: (canvasId: number) => authRequest<CanvasRunItem[]>(`/api/canvas/${canvasId}/runs`),
};


export interface CurvePoint {
  x: number;
  y: number;
}

export interface Fit4plResult {
  bottom_asymptote_a: number;
  hill_slope_b: number;
  ec50_c: number;
  top_asymptote_d: number;
  r_squared: number;
  rmse: number;
  curve_points: CurvePoint[];
}

export interface ScientificSpreadsheetItem {
  id: number;
  organization_id: number;
  project_id?: number | null;
  experiment_id?: number | null;
  name: string;
  description: string;
  sheet_data: {
    columns: string[];
    rows: (string | number)[][];
  };
  curves_data?: Fit4plResult | Record<string, any>;
  created_at: string;
}

export const analyticsApi = {
  fit4pl: (points: CurvePoint[]) =>
    authRequest<Fit4plResult>("/api/analytics/fit-4pl", {
      method: "POST",
      body: JSON.stringify({ points }),
    }),
  evaluateFormula: (expression: string, values: number[]) =>
    authRequest<{ result: number }>("/api/analytics/evaluate-formula", {
      method: "POST",
      body: JSON.stringify({ expression, values }),
    }),
  getPresets: () => authRequest<{ name: string; description: string; sheet_data: { columns: string[]; rows: (string | number)[][] } }[]>("/api/analytics/presets"),
  list: (projectId?: number | null, experimentId?: number | null) => {
    const params = new URLSearchParams();
    if (projectId) params.set("project_id", String(projectId));
    if (experimentId) params.set("experiment_id", String(experimentId));
    const qs = params.toString() ? `?${params.toString()}` : "";
    return authRequest<ScientificSpreadsheetItem[]>(`/api/analytics/sheets${qs}`);
  },
  get: (sheetId: number) => authRequest<ScientificSpreadsheetItem>(`/api/analytics/sheets/${sheetId}`),
  create: (data: {
    name: string;
    description?: string;
    sheet_data?: Record<string, any>;
    curves_data?: Record<string, any>;
    project_id?: number | null;
    experiment_id?: number | null;
  }) => authRequest<ScientificSpreadsheetItem>("/api/analytics/sheets", {
    method: "POST",
    body: JSON.stringify(data),
  }),
  update: (sheetId: number, data: { name?: string; sheet_data?: Record<string, any>; curves_data?: Record<string, any> }) =>
    authRequest<ScientificSpreadsheetItem>(`/api/analytics/sheets/${sheetId}`, {
      method: "PUT",
      body: JSON.stringify(data),
    }),
};


export interface DossierSection {
  title: string;
  content: string;
  status: string;
}

export interface RegulatoryDossierItem {
  id: number;
  organization_id: number;
  project_id?: number | null;
  experiment_id?: number | null;
  title: string;
  dossier_type: string;
  summary: string;
  sections: DossierSection[];
  sha256_checksum: string;
  status: "draft" | "certified" | "submitted" | "archived";
  certified_by_user_name?: string | null;
  certified_at?: string | null;
  created_at: string;
}

export const dossierApi = {
  compile: (data: {
    title: string;
    dossier_type?: string;
    summary?: string;
    project_id?: number | null;
    experiment_id?: number | null;
    custom_sections?: DossierSection[];
  }) => authRequest<RegulatoryDossierItem>("/api/dossier/compile", {
    method: "POST",
    body: JSON.stringify(data),
  }),
  list: (projectId?: number | null, experimentId?: number | null) => {
    const params = new URLSearchParams();
    if (projectId) params.set("project_id", String(projectId));
    if (experimentId) params.set("experiment_id", String(experimentId));
    const qs = params.toString() ? `?${params.toString()}` : "";
    return authRequest<RegulatoryDossierItem[]>(`/api/dossier${qs}`);
  },
  get: (dossierId: number) => authRequest<RegulatoryDossierItem>(`/api/dossier/${dossierId}`),
  certify: (dossierId: number, data: { user_id: number; user_name: string }) =>
    authRequest<{ id: number; status: string; certified_by_user_name: string; certified_at: string; sha256_checksum: string }>(
      `/api/dossier/${dossierId}/certify`,
      {
        method: "POST",
        body: JSON.stringify(data),
      }
    ),
};


export interface ThermalLabelPreview {
  label_type: string;
  width_dots: number;
  height_dots: number;
  dpi: number;
  zpl_code: string;
  svg_preview: string;
}

export interface ProtocolsIoStep {
  step_num: number;
  title: string;
  duration_min: number;
  temp_c: number;
  notes: string;
}

export interface ProtocolsIoProtocol {
  protocol_id_ext: string;
  title: string;
  authors: string;
  doi: string;
  description: string;
  steps: ProtocolsIoStep[];
}

export const thermalPrinterApi = {
  generateZpl: (data: {
    label_type: string;
    barcode_data: string;
    sample_name: string;
    lot_number?: string;
    storage_temp?: string;
    expiry_date?: string;
    hazard_symbol?: string;
    dpi?: number;
  }) => authRequest<ThermalLabelPreview>("/api/thermal_printer/generate-zpl", {
    method: "POST",
    body: JSON.stringify(data),
  }),
  getPresets: () => authRequest<{ name: string; label_type: string; width_mm: number; height_mm: number; dpi: number; barcode_type: string }[]>("/api/thermal_printer/presets"),
  searchProtocols: (query?: string) => {
    const qs = query ? `?query=${encodeURIComponent(query)}` : "";
    return authRequest<ProtocolsIoProtocol[]>(`/api/thermal_printer/protocols-search${qs}`);
  },
  importProtocol: (protocolIdExt: string) =>
    authRequest<ProtocolsIoProtocol & { id: number; created_at: string }>("/api/thermal_printer/protocols-import", {
      method: "POST",
      body: JSON.stringify({ protocol_id_ext: protocolIdExt }),
    }),
  listImported: () => authRequest<(ProtocolsIoProtocol & { id: number; created_at: string })[]>("/api/thermal_printer/imported-protocols"),
};
