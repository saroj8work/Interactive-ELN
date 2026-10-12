-- Reference snapshot generated from the current SQLAlchemy models.

-- Use the service-specific Alembic migrations for installation and upgrades.

-- Do not apply this snapshot in addition to Alembic migrations.

-- Sections correspond to separate databases; table names use the default public search_path.

-- Alembic manages each database's separate alembic_version table.



-- ============================================================================

-- DATABASE: identity

-- ============================================================================

CREATE TABLE organizations (
	id SERIAL NOT NULL, 
	name VARCHAR(160) NOT NULL, 
	slug VARCHAR(80) NOT NULL, 
	is_active BOOLEAN NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id)
);

CREATE TABLE users (
	id SERIAL NOT NULL, 
	email VARCHAR(254) NOT NULL, 
	password_hash VARCHAR(256) NOT NULL, 
	display_name VARCHAR(160) NOT NULL, 
	is_active BOOLEAN NOT NULL, 
	email_verified_at TIMESTAMP WITH TIME ZONE, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id)
);

CREATE TABLE invitations (
	id SERIAL NOT NULL, 
	organization_id INTEGER NOT NULL, 
	email VARCHAR(254) NOT NULL, 
	role VARCHAR(24) NOT NULL, 
	token_hash VARCHAR(64) NOT NULL, 
	invited_by_user_id INTEGER, 
	expires_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	accepted_at TIMESTAMP WITH TIME ZONE, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(organization_id) REFERENCES organizations (id), 
	FOREIGN KEY(invited_by_user_id) REFERENCES users (id)
);

CREATE TABLE memberships (
	id SERIAL NOT NULL, 
	organization_id INTEGER NOT NULL, 
	user_id INTEGER NOT NULL, 
	role VARCHAR(24) NOT NULL, 
	is_active BOOLEAN NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (organization_id, user_id), 
	FOREIGN KEY(organization_id) REFERENCES organizations (id), 
	FOREIGN KEY(user_id) REFERENCES users (id)
);

CREATE TABLE password_resets (
	id SERIAL NOT NULL, 
	token_hash VARCHAR(64) NOT NULL, 
	user_id INTEGER NOT NULL, 
	organization_id INTEGER NOT NULL, 
	expires_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	used_at TIMESTAMP WITH TIME ZONE, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(user_id) REFERENCES users (id), 
	FOREIGN KEY(organization_id) REFERENCES organizations (id)
);

CREATE TABLE refresh_sessions (
	id SERIAL NOT NULL, 
	token_hash VARCHAR(64) NOT NULL, 
	user_id INTEGER NOT NULL, 
	organization_id INTEGER NOT NULL, 
	expires_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	revoked_at TIMESTAMP WITH TIME ZONE, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(user_id) REFERENCES users (id), 
	FOREIGN KEY(organization_id) REFERENCES organizations (id)
);

CREATE UNIQUE INDEX ix_organizations_slug ON organizations (slug);

CREATE UNIQUE INDEX ix_users_email ON users (email);

CREATE INDEX ix_invitations_email ON invitations (email);

CREATE INDEX ix_invitations_organization_id ON invitations (organization_id);

CREATE UNIQUE INDEX ix_invitations_token_hash ON invitations (token_hash);

CREATE INDEX ix_memberships_organization_id ON memberships (organization_id);

CREATE INDEX ix_memberships_user_id ON memberships (user_id);

CREATE INDEX ix_password_resets_organization_id ON password_resets (organization_id);

CREATE UNIQUE INDEX ix_password_resets_token_hash ON password_resets (token_hash);

CREATE INDEX ix_password_resets_user_id ON password_resets (user_id);

CREATE INDEX ix_refresh_sessions_organization_id ON refresh_sessions (organization_id);

CREATE UNIQUE INDEX ix_refresh_sessions_token_hash ON refresh_sessions (token_hash);

CREATE INDEX ix_refresh_sessions_user_id ON refresh_sessions (user_id);



-- ============================================================================

-- DATABASE: projects

-- ============================================================================

CREATE TABLE outbox_events (
	id SERIAL NOT NULL, 
	event_id VARCHAR(36) NOT NULL, 
	source_service VARCHAR(64) NOT NULL, 
	action VARCHAR(48) NOT NULL, 
	entity_type VARCHAR(48) NOT NULL, 
	entity_id INTEGER NOT NULL, 
	organization_id INTEGER NOT NULL, 
	occurred_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	details JSON NOT NULL, 
	published_at TIMESTAMP WITH TIME ZONE, 
	attempts INTEGER NOT NULL, 
	PRIMARY KEY (id)
);

CREATE TABLE projects (
	id SERIAL NOT NULL, 
	organization_id INTEGER NOT NULL, 
	name VARCHAR(160) NOT NULL, 
	description TEXT NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id)
);

CREATE TABLE project_memberships (
	id SERIAL NOT NULL, 
	organization_id INTEGER NOT NULL, 
	project_id INTEGER NOT NULL, 
	user_id INTEGER NOT NULL, 
	role VARCHAR(24) NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (organization_id, project_id, user_id), 
	FOREIGN KEY(project_id) REFERENCES projects (id)
);

CREATE UNIQUE INDEX ix_outbox_events_event_id ON outbox_events (event_id);

CREATE INDEX ix_outbox_events_organization_id ON outbox_events (organization_id);

CREATE INDEX ix_projects_name ON projects (name);

CREATE INDEX ix_projects_organization_id ON projects (organization_id);

CREATE INDEX ix_project_memberships_organization_id ON project_memberships (organization_id);

CREATE INDEX ix_project_memberships_project_id ON project_memberships (project_id);

CREATE INDEX ix_project_memberships_user_id ON project_memberships (user_id);



-- ============================================================================

-- DATABASE: notebook

-- ============================================================================

CREATE TABLE audit_events (
	id SERIAL NOT NULL, 
	organization_id INTEGER NOT NULL, 
	actor_user_id INTEGER NOT NULL, 
	action VARCHAR(48) NOT NULL, 
	entity_type VARCHAR(32) NOT NULL, 
	entity_id INTEGER NOT NULL, 
	payload_json TEXT NOT NULL, 
	previous_hash VARCHAR(64) NOT NULL, 
	event_hash VARCHAR(64) NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (event_hash)
);

CREATE TABLE equipment_resources (
	id SERIAL NOT NULL, 
	organization_id INTEGER NOT NULL, 
	name VARCHAR(160) NOT NULL, 
	description TEXT NOT NULL, 
	location VARCHAR(200) NOT NULL, 
	category VARCHAR(64) NOT NULL, 
	status VARCHAR(24) NOT NULL, 
	created_by_user_id INTEGER NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id)
);

CREATE TABLE experiments (
	id SERIAL NOT NULL, 
	organization_id INTEGER NOT NULL, 
	project_id INTEGER NOT NULL, 
	name VARCHAR(160) NOT NULL, 
	description TEXT NOT NULL, 
	status VARCHAR(32) NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id)
);

CREATE TABLE inventory_items (
	id SERIAL NOT NULL, 
	organization_id INTEGER NOT NULL, 
	name VARCHAR(160) NOT NULL, 
	category VARCHAR(64) NOT NULL, 
	catalog_number VARCHAR(120) NOT NULL, 
	lot_number VARCHAR(120) NOT NULL, 
	expires_on DATE, 
	quantity NUMERIC(14, 3) NOT NULL, 
	unit VARCHAR(32) NOT NULL, 
	low_stock_threshold NUMERIC(14, 3) NOT NULL, 
	location VARCHAR(200) NOT NULL, 
	notes TEXT NOT NULL, 
	status VARCHAR(24) NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id)
);

CREATE TABLE lab_tasks (
	id SERIAL NOT NULL, 
	organization_id INTEGER NOT NULL, 
	project_id INTEGER NOT NULL, 
	experiment_id INTEGER, 
	assigned_to_user_id INTEGER, 
	created_by_user_id INTEGER NOT NULL, 
	title VARCHAR(200) NOT NULL, 
	description TEXT NOT NULL, 
	due_at TIMESTAMP WITH TIME ZONE, 
	priority VARCHAR(16) NOT NULL, 
	status VARCHAR(24) NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id)
);

CREATE TABLE notebook_templates (
	id SERIAL NOT NULL, 
	organization_id INTEGER NOT NULL, 
	created_by_user_id INTEGER NOT NULL, 
	name VARCHAR(160) NOT NULL, 
	template_kind VARCHAR(24) NOT NULL, 
	description TEXT NOT NULL, 
	sections JSON NOT NULL, 
	status VARCHAR(24) NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id)
);

CREATE TABLE outbox_events (
	id SERIAL NOT NULL, 
	event_id VARCHAR(36) NOT NULL, 
	source_service VARCHAR(64) NOT NULL, 
	action VARCHAR(48) NOT NULL, 
	entity_type VARCHAR(48) NOT NULL, 
	entity_id INTEGER NOT NULL, 
	organization_id INTEGER NOT NULL, 
	occurred_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	details JSON NOT NULL, 
	published_at TIMESTAMP WITH TIME ZONE, 
	attempts INTEGER NOT NULL, 
	PRIMARY KEY (id)
);

CREATE TABLE record_signatures (
	id SERIAL NOT NULL, 
	organization_id INTEGER NOT NULL, 
	entity_type VARCHAR(32) NOT NULL, 
	entity_id INTEGER NOT NULL, 
	signed_by_user_id INTEGER NOT NULL, 
	meaning VARCHAR(24) NOT NULL, 
	comment VARCHAR(500) NOT NULL, 
	record_sha256 VARCHAR(64) NOT NULL, 
	previous_hash VARCHAR(64) NOT NULL, 
	event_hash VARCHAR(64) NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (event_hash)
);

CREATE TABLE record_tags (
	id SERIAL NOT NULL, 
	organization_id INTEGER NOT NULL, 
	entity_type VARCHAR(24) NOT NULL, 
	entity_id INTEGER NOT NULL, 
	tag VARCHAR(40) NOT NULL, 
	created_by_user_id INTEGER NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (organization_id, entity_type, entity_id, tag)
);

CREATE TABLE samples (
	id SERIAL NOT NULL, 
	organization_id INTEGER NOT NULL, 
	project_id INTEGER, 
	name VARCHAR(160) NOT NULL, 
	sample_type VARCHAR(80) NOT NULL, 
	external_id VARCHAR(120) NOT NULL, 
	parent_sample_id INTEGER, 
	storage_location VARCHAR(200) NOT NULL, 
	description TEXT NOT NULL, 
	status VARCHAR(24) NOT NULL, 
	created_by_user_id INTEGER NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(parent_sample_id) REFERENCES samples (id)
);

CREATE TABLE equipment_bookings (
	id SERIAL NOT NULL, 
	organization_id INTEGER NOT NULL, 
	equipment_id INTEGER NOT NULL, 
	booked_by_user_id INTEGER NOT NULL, 
	project_id INTEGER, 
	starts_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	ends_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	purpose VARCHAR(500) NOT NULL, 
	status VARCHAR(24) NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(equipment_id) REFERENCES equipment_resources (id)
);

CREATE TABLE notebook_entries (
	id SERIAL NOT NULL, 
	experiment_id INTEGER NOT NULL, 
	organization_id INTEGER NOT NULL, 
	title VARCHAR(200) NOT NULL, 
	content TEXT NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(experiment_id) REFERENCES experiments (id)
);

CREATE TABLE stock_movements (
	id SERIAL NOT NULL, 
	organization_id INTEGER NOT NULL, 
	item_id INTEGER NOT NULL, 
	changed_by_user_id INTEGER NOT NULL, 
	quantity_delta NUMERIC(14, 3) NOT NULL, 
	resulting_quantity NUMERIC(14, 3) NOT NULL, 
	reason VARCHAR(240) NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(item_id) REFERENCES inventory_items (id)
);

CREATE TABLE entry_attachments (
	id SERIAL NOT NULL, 
	organization_id INTEGER NOT NULL, 
	entry_id INTEGER NOT NULL, 
	storage_key VARCHAR(64) NOT NULL, 
	original_filename VARCHAR(255) NOT NULL, 
	media_type VARCHAR(160) NOT NULL, 
	size_bytes INTEGER NOT NULL, 
	sha256 VARCHAR(64) NOT NULL, 
	uploaded_by_user_id INTEGER NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(entry_id) REFERENCES notebook_entries (id), 
	UNIQUE (storage_key)
);

CREATE TABLE entry_revisions (
	id SERIAL NOT NULL, 
	organization_id INTEGER NOT NULL, 
	entry_id INTEGER NOT NULL, 
	revision_number INTEGER NOT NULL, 
	title VARCHAR(200) NOT NULL, 
	content TEXT NOT NULL, 
	changed_by_user_id INTEGER NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (organization_id, entry_id, revision_number), 
	FOREIGN KEY(entry_id) REFERENCES notebook_entries (id)
);

CREATE INDEX ix_audit_events_actor_user_id ON audit_events (actor_user_id);

CREATE INDEX ix_audit_events_entity_id ON audit_events (entity_id);

CREATE INDEX ix_audit_events_entity_type ON audit_events (entity_type);

CREATE INDEX ix_audit_events_organization_id ON audit_events (organization_id);

CREATE INDEX ix_equipment_resources_category ON equipment_resources (category);

CREATE INDEX ix_equipment_resources_name ON equipment_resources (name);

CREATE INDEX ix_equipment_resources_organization_id ON equipment_resources (organization_id);

CREATE INDEX ix_equipment_resources_status ON equipment_resources (status);

CREATE INDEX ix_experiments_name ON experiments (name);

CREATE INDEX ix_experiments_organization_id ON experiments (organization_id);

CREATE INDEX ix_experiments_project_id ON experiments (project_id);

CREATE INDEX ix_inventory_items_category ON inventory_items (category);

CREATE INDEX ix_inventory_items_name ON inventory_items (name);

CREATE INDEX ix_inventory_items_organization_id ON inventory_items (organization_id);

CREATE INDEX ix_inventory_items_status ON inventory_items (status);

CREATE INDEX ix_lab_tasks_assigned_to_user_id ON lab_tasks (assigned_to_user_id);

CREATE INDEX ix_lab_tasks_experiment_id ON lab_tasks (experiment_id);

CREATE INDEX ix_lab_tasks_organization_id ON lab_tasks (organization_id);

CREATE INDEX ix_lab_tasks_project_id ON lab_tasks (project_id);

CREATE INDEX ix_lab_tasks_status ON lab_tasks (status);

CREATE INDEX ix_notebook_templates_name ON notebook_templates (name);

CREATE INDEX ix_notebook_templates_organization_id ON notebook_templates (organization_id);

CREATE INDEX ix_notebook_templates_status ON notebook_templates (status);

CREATE INDEX ix_notebook_templates_template_kind ON notebook_templates (template_kind);

CREATE UNIQUE INDEX ix_outbox_events_event_id ON outbox_events (event_id);

CREATE INDEX ix_outbox_events_organization_id ON outbox_events (organization_id);

CREATE INDEX ix_record_signatures_entity_id ON record_signatures (entity_id);

CREATE INDEX ix_record_signatures_entity_type ON record_signatures (entity_type);

CREATE INDEX ix_record_signatures_organization_id ON record_signatures (organization_id);

CREATE INDEX ix_record_signatures_signed_by_user_id ON record_signatures (signed_by_user_id);

CREATE INDEX ix_record_tags_entity_id ON record_tags (entity_id);

CREATE INDEX ix_record_tags_entity_type ON record_tags (entity_type);

CREATE INDEX ix_record_tags_organization_id ON record_tags (organization_id);

CREATE INDEX ix_record_tags_tag ON record_tags (tag);

CREATE INDEX ix_samples_external_id ON samples (external_id);

CREATE INDEX ix_samples_name ON samples (name);

CREATE INDEX ix_samples_organization_id ON samples (organization_id);

CREATE INDEX ix_samples_project_id ON samples (project_id);

CREATE INDEX ix_samples_status ON samples (status);

CREATE INDEX ix_equipment_bookings_booked_by_user_id ON equipment_bookings (booked_by_user_id);

CREATE INDEX ix_equipment_bookings_ends_at ON equipment_bookings (ends_at);

CREATE INDEX ix_equipment_bookings_equipment_id ON equipment_bookings (equipment_id);

CREATE INDEX ix_equipment_bookings_organization_id ON equipment_bookings (organization_id);

CREATE INDEX ix_equipment_bookings_project_id ON equipment_bookings (project_id);

CREATE INDEX ix_equipment_bookings_starts_at ON equipment_bookings (starts_at);

CREATE INDEX ix_equipment_bookings_status ON equipment_bookings (status);

CREATE INDEX ix_notebook_entries_experiment_id ON notebook_entries (experiment_id);

CREATE INDEX ix_notebook_entries_organization_id ON notebook_entries (organization_id);

CREATE INDEX ix_stock_movements_item_id ON stock_movements (item_id);

CREATE INDEX ix_stock_movements_organization_id ON stock_movements (organization_id);

CREATE INDEX ix_entry_attachments_entry_id ON entry_attachments (entry_id);

CREATE INDEX ix_entry_attachments_organization_id ON entry_attachments (organization_id);

CREATE INDEX ix_entry_revisions_entry_id ON entry_revisions (entry_id);

CREATE INDEX ix_entry_revisions_organization_id ON entry_revisions (organization_id);



-- ============================================================================

-- DATABASE: activity

-- ============================================================================

CREATE TABLE activity_events (
	id SERIAL NOT NULL, 
	event_id VARCHAR(36) NOT NULL, 
	source_service VARCHAR(64) NOT NULL, 
	action VARCHAR(48) NOT NULL, 
	entity_type VARCHAR(48) NOT NULL, 
	entity_id INTEGER NOT NULL, 
	organization_id INTEGER NOT NULL, 
	occurred_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	details JSON NOT NULL, 
	PRIMARY KEY (id)
);

CREATE INDEX ix_activity_events_action ON activity_events (action);

CREATE INDEX ix_activity_events_entity_id ON activity_events (entity_id);

CREATE INDEX ix_activity_events_entity_type ON activity_events (entity_type);

CREATE UNIQUE INDEX ix_activity_events_event_id ON activity_events (event_id);

CREATE INDEX ix_activity_events_occurred_at ON activity_events (occurred_at);

CREATE INDEX ix_activity_events_organization_id ON activity_events (organization_id);

CREATE INDEX ix_activity_events_source_service ON activity_events (source_service);
