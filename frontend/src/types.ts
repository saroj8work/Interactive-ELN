export interface Project {
  id: number;
  organization_id: number;
  name: string;
  description: string;
  created_at: string;
}

export interface ProjectMember {
  id: number;
  organization_id: number;
  project_id: number;
  user_id: number;
  role: "owner" | "editor" | "viewer";
}

export interface ProjectAccess {
  project_id: number;
  role: "admin" | "owner" | "editor" | "viewer";
}

export interface InventoryItem {
  id: number;
  organization_id: number;
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
  created_at: string;
  updated_at: string;
  status: "active" | "archived";
}

export interface InventoryCustomFieldDefinition {
  id: number;
  organization_id: number;
  name: string;
  field_type: "text" | "number" | "date" | "boolean" | "select";
  required: boolean;
  options: string[];
  status: "active" | "archived";
  created_by_user_id: number;
  created_at: string;
}

export interface SampleRecord {
  id: number;
  organization_id: number;
  project_id: number | null;
  name: string;
  sample_type: string;
  external_id: string;
  parent_sample_id: number | null;
  storage_location: string;
  storage_location_id?: number | null;
  description: string;
  created_by_user_id: number;
  current_custodian_user_id: number;
  created_at: string;
  status: "active" | "archived";
}

export interface SampleCustodyTransfer {
  id: number;
  organization_id: number;
  sample_id: number;
  from_user_id: number;
  to_user_id: number;
  status: "pending" | "accepted" | "cancelled";
  request_note: string;
  receipt_note: string;
  requested_at: string;
  accepted_at: string | null;
}

export interface NotebookTemplate {
  id: number;
  organization_id: number;
  created_by_user_id: number;
  name: string;
  template_kind: "entry" | "protocol";
  description: string;
  sections: { title: string; instructions: string; required: boolean }[];
  created_at: string;
  updated_at: string;
  status: "active" | "archived";
}

export interface EntryAttachment {
  id: number;
  organization_id: number;
  entry_id: number;
  original_filename: string;
  media_type: string;
  size_bytes: number;
  sha256: string;
  uploaded_by_user_id: number;
  created_at: string;
}

export interface SearchHit {
  entity_type:
    | "project"
    | "experiment"
    | "entry"
    | "inventory"
    | "sample"
    | "template"
    | "equipment";
  entity_id: number;
  title: string;
  detail: string;
  project_id: number | null;
}

export interface EquipmentResource {
  id: number;
  organization_id: number;
  name: string;
  description: string;
  location: string;
  storage_location_id?: number | null;
  category: string;
  created_by_user_id: number;
  created_at: string;
  status: "active" | "archived";
}

export interface EquipmentBooking {
  id: number;
  organization_id: number;
  equipment_id: number;
  booked_by_user_id: number;
  project_id: number | null;
  starts_at: string;
  ends_at: string;
  purpose: string;
  status: "reserved" | "cancelled" | "completed";
  created_at: string;
}

export interface EquipmentMaintenance {
  id: number;
  organization_id: number;
  equipment_id: number;
  created_by_user_id: number;
  title: string;
  notes: string;
  service_provider: string;
  service_contact_email: string;
  service_contact_phone: string;
  recurrence_days: number | null;
  recurrence_unit: "days" | "weeks" | "months" | null;
  recurrence_until: string | null;
  starts_at: string;
  ends_at: string;
  status: "scheduled" | "in_progress" | "completed" | "cancelled";
  created_at: string;
}

export interface CalendarFeed {
  id: number;
  name: string;
  token_prefix: string;
  created_at: string;
  last_used_at: string | null;
  revoked_at: string | null;
}

export interface CalendarFeedCreated extends CalendarFeed {
  secret: string;
}

export interface WebhookEndpoint {
  id: number;
  name: string;
  url: string;
  event_types: string[];
  secret_prefix: string;
  enabled: boolean;
  created_at: string;
  revoked_at: string | null;
}

export interface WebhookEndpointCreated extends WebhookEndpoint {
  secret: string;
}

export interface WebhookDelivery {
  id: number;
  event_id: string;
  event_type: string;
  attempts: number;
  next_attempt_at: string | null;
  last_attempt_at: string | null;
  last_status_code: number | null;
  last_error: string | null;
  delivered_at: string | null;
  failed_at: string | null;
  created_at: string;
}

export interface Experiment {
  id: number;
  organization_id: number;
  project_id: number;
  name: string;
  description: string;
  status: "in_progress" | "completed" | "archived";
  created_at: string;
  updated_at: string;
}

export interface ExperimentApproval {
  id: number;
  organization_id: number;
  experiment_id: number;
  requested_by_user_id: number;
  reviewer_user_id: number;
  reviewer_user_ids: number[];
  rejection_reviewer_user_ids: number[];
  review_mode: "sequential" | "parallel";
  active_branch: "main" | "rejection";
  current_step_index: number;
  step_history: {
    step_order: number;
    branch: "main" | "rejection";
    reviewer_user_id: number;
    status: "pending" | "approved" | "rejected" | "stale" | "not_required";
    comment: string;
    decided_by_user_id: number | null;
    decided_at: string | null;
  }[];
  status: "pending" | "approved" | "rejected" | "stale";
  request_comment: string;
  decision_comment: string;
  snapshot_digest: string;
  decided_by_user_id: number | null;
  requested_at: string;
  decided_at: string | null;
}

export interface NotebookEntry {
  id: number;
  experiment_id: number;
  title: string;
  content: string;
  created_at: string;
  updated_at: string;
}

export interface EntryRevision {
  id: number;
  organization_id: number;
  entry_id: number;
  revision_number: number;
  title: string;
  content: string;
  changed_by_user_id: number;
  created_at: string;
}

export interface RecordTagSet {
  entity_type: "experiment" | "entry" | "inventory" | "sample" | "equipment" | "template";
  entity_id: number;
  tags: string[];
}

export interface LabTask {
  id: number;
  organization_id: number;
  project_id: number;
  experiment_id: number | null;
  assigned_to_user_id: number | null;
  created_by_user_id: number;
  title: string;
  description: string;
  due_at: string | null;
  priority: "low" | "normal" | "high" | "urgent";
  status: "open" | "in_progress" | "blocked" | "completed" | "cancelled";
  created_at: string;
  updated_at: string;
}

export interface RecordSignature {
  id: number;
  organization_id: number;
  entity_type: string;
  entity_id: number;
  signed_by_user_id: number;
  meaning: "authored" | "reviewed" | "approved";
  comment: string;
  record_sha256: string;
  previous_hash: string;
  event_hash: string;
  created_at: string;
}

export interface AuditVerification {
  organization_id: number;
  valid: boolean;
  checked_events: number;
}

export interface ActivityEvent {
  id: number;
  action: string;
  entity_type: string;
  entity_id: number;
  occurred_at: string;
  details: Record<string, string>;
}

export interface Notification {
  id: number;
  organization_id: number;
  user_id: number;
  event_id: string;
  title: string;
  message: string;
  entity_type: string;
  entity_id: number;
  details: Record<string, string>;
  created_at: string;
  read_at: string | null;
}

export interface StorageLocation {
  id: number;
  organization_id: number;
  code: string;
  name: string;
  parent_id: number | null;
  location_type:
    | "building"
    | "room"
    | "freezer"
    | "refrigerator"
    | "cabinet"
    | "shelf"
    | "box"
    | "other";
  description: string;
  status: "active" | "archived";
  created_by_user_id: number;
  created_at: string;
}

export interface WorkflowRule {
  id: number;
  organization_id: number;
  project_id: number;
  name: string;
  trigger_type: "experiment_status_changed" | "experiment_created" | "entry_created" | "experiment_approval_ended";
  approval_outcome: "approved" | "rejected" | "stale" | null;
  from_status: "in_progress" | "completed" | "archived" | null;
  to_status: "in_progress" | "completed" | "archived" | null;
  task_title: string;
  task_description: string;
  task_priority: "low" | "normal" | "high" | "urgent";
  due_days: number | null;
  assigned_to_user_id: number | null;
  enabled: boolean;
  created_by_user_id: number;
  created_at: string;
}

export interface EntryTimestamp {
  id: number;
  organization_id: number;
  entry_id: number;
  requested_by_user_id: number;
  tsa_url: string;
  record_sha256: string;
  tsa_time: string;
  created_at: string;
}

export interface EntryTimestampVerification {
  timestamp_id: number;
  snapshot_sha256: string;
  recorded_sha256: string;
  digest_matches: boolean;
  token_valid_for_snapshot: boolean;
  token_time: string | null;
  stored_time_matches: boolean;
  valid: boolean;
  message: string;
}
