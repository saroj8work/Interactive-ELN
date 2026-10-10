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
  category: "reagent" | "consumable" | "equipment";
  catalog_number: string;
  lot_number: string;
  expires_on: string | null;
  quantity: number;
  unit: string;
  low_stock_threshold: number;
  location: string;
  notes: string;
  created_at: string;
  updated_at: string;
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
  description: string;
  created_by_user_id: number;
  created_at: string;
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
  entity_type: "project" | "experiment" | "entry" | "inventory" | "sample" | "template";
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
  created_by_user_id: number;
  created_at: string;
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

export interface ActivityEvent {
  id: number;
  action: string;
  entity_type: string;
  entity_id: number;
  occurred_at: string;
  details: Record<string, string>;
}
