# Interactive ELN

An independent electronic lab notebook monorepo with a Python microservice backend and a React + TypeScript frontend. It is informed by common ELN workflows and is not a copy of SciNote.

## Backend architecture

```text
frontend/
backend/
├── eln_common/       Shared database, error, API-contract, and outbox primitives
├── gateway/          Public API gateway; routes the UI API to domain services
├── migrations/       Independent Alembic configuration and revisions per database
├── services/
│   ├── identity/     Invite-only accounts, organizations, memberships, and sessions
│   ├── projects/     Project ownership and persistence
│   ├── notebook/    Experiments and notebook entries
│   └── activity/     Activity-event ingestion and query
└── tests/            Domain service tests
docker-compose.yml    Five API containers and four isolated PostgreSQL databases
```

Each service has its own FastAPI application. Identity, Projects, Notebook, and Activity have separate data stores; services do not query another service's database. The gateway provides the stable `/api` surface used by the frontend. It verifies short-lived signed access tokens, scopes project, experiment, entry, and activity queries by the token's organization, and forwards trusted organization and user identities to private domain services. Projects are private by default: creators are owners, owners can grant viewer/editor access to active organization members, and organization admins can access every project. Viewers can read; editors can also create/update notebook records. Activity events are filtered to projects the caller can access.

Identity is a separate service in this monorepo, not a separate repository. It supports invite-only organization provisioning, verified-by-invitation email/password accounts, organization admin/member roles, membership management, short-lived access tokens, rotating HttpOnly refresh cookies, logout, and email-based password recovery. Password reset links are single-use, expire after one hour, and contain a token fragment that is not sent in HTTP requests; only token hashes are stored. Resetting a password revokes the user's refresh sessions across organizations; already-issued access tokens remain valid until their short expiry. Organization creation is restricted to a bootstrap token configured by the deployment operator. Passwords are salted PBKDF2-HMAC-SHA256 hashes; only hashed invitation, refresh, and reset tokens are stored.

Domain writes and their activity events are committed together to a service-local outbox. A background publisher retries event delivery, while the Activity service deduplicates by event ID. The Activity service also creates durable, user-scoped in-app notifications for experiment approval requests, reviewer handoffs, and final outcomes. This is an eventually consistent activity feed and notification inbox, not a validated or tamper-proof regulatory audit trail.

## Run the full backend with Docker Compose

Requirements: Docker Desktop with Docker Compose.

From the repository root:

```powershell
docker compose up --build
```

Create a local `.env` from `.env.example`, replacing all three placeholders with independent random secrets of at least 32 bytes. For example, generate each with:

```powershell
py -c "import secrets; print(secrets.token_urlsafe(48))"
```

Keep `.env` private; it is ignored by Git. The audit HMAC key is used only by the Notebook service to protect the current audit/signature foundation. Keep it separate from the JWT secret and back it up securely; losing or rotating it prevents verification of existing signatures. This feature is not a compliance control. To enable outbound webhooks, set `ELN_WEBHOOK_ENCRYPTION_KEY` in `.env` to a persistent Fernet key, generated with `py -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`. Back up this key with the database: existing webhook signing secrets cannot be decrypted if it is lost or changed. Optionally set `ELN_WEBHOOK_ALLOWED_HOSTS` to a comma-separated hostname allowlist. Apply outgoing network egress controls appropriate to your deployment.

Then run:

```powershell
docker compose up --build
```

The public ELN gateway is at `http://localhost:8000`; its API documentation is at `http://localhost:8000/docs`. The identity service is at `http://localhost:8004`; identity API documentation is at `http://localhost:8004/docs`. Mailpit, the local-only development email inbox, is at `http://localhost:8025`. Vite proxies `/auth` to the identity service and `/api` to the ELN gateway. PostgreSQL data is held in separate named volumes. The credentials in `docker-compose.yml` are local-development-only and must be replaced for any real deployment.

Compose runs one Alembic migration job for each database before starting its API service. Fresh databases are created by these jobs. An existing database created by an earlier application version has no Alembic history and must be backed up and safely baselined before using this Compose workflow; see [Database migrations](#database-migrations) and the [migration design document](docs/database-migrations.md).

Once services are healthy, create an organization and send the owner invitation. In PowerShell, set `$bootstrap` to the same `ELN_BOOTSTRAP_TOKEN` value in your private `.env`:

```powershell
$bootstrap = "your-private-bootstrap-token"
$headers = @{ "X-Bootstrap-Token" = $bootstrap }
$body = @{
  name = "Example Life Sciences Lab"
  slug = "example-life-sciences"
  owner_email = "owner@example.org"
  owner_name = "Lab Owner"
} | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri "http://localhost:8004/auth/bootstrap/organizations" -Headers $headers -ContentType "application/json" -Body $body
```

Open the owner invitation in Mailpit, accept it in the React application at `http://localhost:5173`, then sign in using the organization slug, email, and chosen password. Organization admins can send member/admin invitations and deactivate/reactivate memberships from the ELN's **Organization admin** panel.

Users can manage personal API credentials through the Identity API: `POST /auth/api-credentials` with a bearer access token and `{"name":"Analysis client","scopes":["read"]}` creates a key. The response includes the secret once; save it securely. `GET /auth/api-credentials` lists the caller's keys, `POST /auth/api-credentials/{id}/rotate` replaces a key and returns its new secret once, and `DELETE /auth/api-credentials/{id}` revokes one. Send the key as `Authorization: Bearer <secret>` to the gateway. `read` permits GET requests and `write` permits non-GET requests. Identity stores only a SHA-256 digest; revocation and inactive membership are checked when the gateway authenticates each request. Organization admins can also configure outgoing HTTPS webhooks in the **Integrations** panel. Webhooks subscribe to all events or comma-separated `source.action` types; requests include HMAC-SHA256 signatures and delivery IDs. Activity retries failures and keeps delivery history. Secrets appear only on creation or rotation and are encrypted at rest.

For a gateway process started directly on the host, set `IDENTITY_SERVICE_URL=http://127.0.0.1:8004` (the default). Compose sets this to the Identity service's container address and waits for Identity health before starting the gateway.

To stop the services while preserving local database data:

```powershell
docker compose down
```

## Run a service directly for development

Requirements: Python 3.12+.

```powershell
cd backend
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
$env:PYTHONPATH = (Get-Location).Path
python -m alembic -c migrations\identity\alembic.ini upgrade head
python -m alembic -c migrations\projects\alembic.ini upgrade head
python -m alembic -c migrations\notebook\alembic.ini upgrade head
python -m alembic -c migrations\activity\alembic.ini upgrade head
uvicorn services.projects.app.main:app --reload --port 8001
```

Run the other services in separate terminals using these app paths and ports:

| Service | Uvicorn app | Port |
|---|---|---:|
| Identity | `services.identity.app.main:app` | 8004 |
| Projects | `services.projects.app.main:app` | 8001 |
| Notebook | `services.notebook.app.main:app` | 8002 |
| Activity | `services.activity.app.main:app` | 8003 |
| Gateway | `gateway.app.main:app` | 8000 |

Set `ELN_JWT_SECRET` to the same strong value for the identity service and gateway. Set `ELN_BOOTSTRAP_TOKEN` for organization provisioning, `IDENTITY_DATABASE_URL`, `PROJECTS_DATABASE_URL`, `NOTEBOOK_DATABASE_URL`, and `ACTIVITY_DATABASE_URL` to their respective PostgreSQL databases, `PUBLIC_APP_URL` for invitation links, and `SMTP_HOST` / `SMTP_FROM` (plus SMTP credentials where needed) for email delivery. Each service URL must use the `postgresql+psycopg://` SQLAlchemy dialect. For local processes, export these settings to the shell; the example `.env` file is automatically consumed by Docker Compose, not by Uvicorn or Alembic. Set `PROJECTS_SERVICE_URL`, `NOTEBOOK_SERVICE_URL`, and `ACTIVITY_SERVICE_URL` for the gateway when services are not using defaults; Projects and Notebook also use `ACTIVITY_SERVICE_URL` for their outbox publisher.

## Database migrations

PostgreSQL is required for all application and migration connections. There is no SQLite application or migration fallback: each service requires its explicit service-specific `*_DATABASE_URL`, validates the `postgresql+psycopg` driver, and fails at startup if it is missing or invalid. Alembic is the schema source of truth. The four databases have independent revision histories and each service refuses to start if its database is not at the latest revision. Startup no longer calls SQLAlchemy `create_all()`; it does not silently mutate a deployed schema. In-memory SQLite remains an explicit test-fixture option only; it is not supported for deployments or migrations.

For manual migration commands or direct Uvicorn development, export the corresponding values from `.env` into the current PowerShell process first; PowerShell and Python do not automatically load `.env`:

```powershell
$env:IDENTITY_DATABASE_URL = "postgresql+psycopg://identity:<password>@<host>:5432/identity"
$env:PROJECTS_DATABASE_URL = "postgresql+psycopg://projects:<password>@<host>:5432/projects"
$env:NOTEBOOK_DATABASE_URL = "postgresql+psycopg://notebook:<password>@<host>:5432/notebook"
$env:ACTIVITY_DATABASE_URL = "postgresql+psycopg://activity:<password>@<host>:5432/activity"
```

Then run migrations from `backend`:

```powershell
python -m alembic -c migrations\identity\alembic.ini upgrade head
python -m alembic -c migrations\projects\alembic.ini upgrade head
python -m alembic -c migrations\notebook\alembic.ini upgrade head
python -m alembic -c migrations\activity\alembic.ini upgrade head
```

For an existing database without Alembic history, take and verify a backup first. Compare its schema to the initial migration for that service. Only if it already matches that schema exactly, record the baseline without re-creating tables:

```powershell
python -m alembic -c migrations\identity\alembic.ini stamp head
```

Repeat with the correct service config and database URL for each database. `stamp` records a revision; **it does not create, inspect, or repair application tables**. Do not run `upgrade head` against an existing unversioned database with populated tables: its initial migration creates those tables. Do not stamp a database whose schema differs from the revision. Reconcile the schema under a reviewed, backed-up deployment plan first.

The four migration environments and revision directories live under [`backend/migrations`](backend/migrations). Generate a new revision for one service from `backend` after changing that service's SQLAlchemy models:

```powershell
python -m alembic -c migrations\notebook\alembic.ini revision --autogenerate -m "describe notebook schema change"
```

Review and edit every generated revision before applying it. Autogeneration does not reliably infer data transformations, renames, every server-default change, or safe rollout ordering. Apply `upgrade head` separately to each affected environment and commit the revision with the corresponding model and application changes. Downgrades are for controlled recovery, not a replacement for database backups; destructive or data-losing operations require a deliberate rollback plan.

[`backend/postgresql_ddl.sql`](backend/postgresql_ddl.sql) remains a PostgreSQL schema snapshot/reference. For normal new installs and upgrades, use Alembic; do not apply the snapshot as well as the migrations. See [Database migration design](docs/database-migrations.md) for the architecture, deployment sequence, legacy-database baseline procedure, and operational safeguards.

## Frontend

Requirements: Node.js 20+ and npm.

```powershell
cd frontend
npm install
npm run dev
```

The Vite development server proxies `/api` calls to `http://127.0.0.1:8000`. Start the gateway and its domain services first.

## Test the backend

From the repository root:

```powershell
$env:PYTHONPATH = (Resolve-Path .\backend).Path
python -m pytest backend\tests
```

## Current features and next areas

The current slice covers invite-only organization/user administration, authentication and password recovery, tenant-scoped projects, explicit project-level owner/editor/viewer access, experiments with status lifecycle, notebook entries with revision history and restore, tags across notebook and lab resources, custom inventory categories, archive/reactivate resource lifecycle, project tasks with priority/due dates/status workflows, reusable organization-scoped entry templates and protocols, project-filtered activity, stock adjustment history, biological sample records, equipment booking with overlap checks, entry attachments, per-entry ZIP exports, project JSON/CSV exports, attachment-inclusive project ZIP export/import, and cross-record search. Imported bundles are validated and size-bounded; imports create new experiments, entries, and tasks in the selected project, remap task-to-experiment references, clear user assignments that may not exist in the destination, and preserve experiment/entry tags, task statuses, and included attachment bytes. Stock adjustments are transactionally recorded with the actor, reason, delta, and resulting quantity; negative stock is rejected. Attachment uploads are capped at 25 MiB each, stored under opaque server-generated names, checksum recorded, and only served as downloads. Project import/export bundles have bounded record, file-count, and byte sizes. Project-linked samples, bookings, notebook attachments, tasks, tags, and signatures are filtered to project collaborators and admins. Projects created before project access control was introduced have no membership records and are visible only to organization admins until they grant access.

Organization admins can manage typed inventory custom fields, including editing names, types, required status, and select options. Renames carry existing values forward. Changes to field type or select options are rejected when they conflict with stored values; required status applies to new inventory records. Experiment approval workflows create an in-app notification for each reviewer handoff and for the requester when a decision completes or becomes stale.

Entry signatures record an authenticated user ID, declared meaning/comment, timestamp, and digest of the signed entry state. The Notebook service signs canonical audit events with `ELN_AUDIT_HMAC_KEY` and exposes an organization-admin chain verification endpoint. Optional RFC 3161 timestamps can request a signed timestamp token from an HTTPS TSA configured with `ELN_TSA_URL` and `ELN_TSA_CERTIFICATE_FILE`; the app stores a content snapshot, offers a proof ZIP, and can verify the token against the configured pinned signer certificate. The proof ZIP includes an offline verification script. This provides a limited timestamping feature, not an immutable evidence store or validated regulatory control. The HMAC audit chain does not prevent a database administrator from deleting or rewriting the chain, and these features do not meet Part 11, GLP, or GMP requirements.

This is not full SciNote/eLabFTW feature parity. The table below marks implemented portions, partial foundations, and missing product capabilities. The [remaining parity work tracker](docs/remaining-parity-implementation-status.md) lists each first-pass feature, its gaps, migration status, and validation state. Remaining gaps include richer sample processing (sample custody handoffs are implemented as a first pass), vendor custom-field template import and attachment import from CSV, bidirectional calendar integration, stereochemical SMILES and deeper molecular editing, OAuth/provider-specific integrations, broader translation coverage, and deployment trust validation for timestamp proofs. PostgreSQL full-text matching and its GIN indexes are implemented across projects, notebook records, lab resources, and tags. Equipment booking includes admin-managed maintenance schedules, provider contacts, editable day-, week-, and month-based recurrence with end dates that schedules the next occurrence on completion, conflict protection, and read-only iCalendar subscriptions, and one-time import of `.ics` events with RRULE series capped at 100 bookings per import. The workspace shell and project dashboard have an English/Hindi selector and locale-aware dates; workflow, molecule-editor, and equipment-scheduler controls also use Hindi translations, while other detailed panels remain English. Scientific entry content supports inline and block LaTeX math rendering using `$...$` and `$$...$$`, freehand sketches, and a first-pass 2D molecule editor. Workflow rules generate tasks from experiment creation, notebook entry creation, experiment status transitions, or approval sequences ending as approved, rejected, or stale, with optional assignment to an active organization member; experiments support sequential or all-reviewers parallel snapshot-bound approval before completion, with up to ten reviewers on each sequential path, in-app notifications, approval-outcome task branches, and conditional sequential rejection paths (requires Notebook migration 8c2d7f1a6b40 and Activity migration f4c8a1d29e63). Database schema changes are managed by service-specific Alembic migrations. This feature list is a roadmap, not a promise of certification or vendor parity.

## Product comparison

This is a capability check, not a claim of parity or a certification statement. Product features vary by vendor release, hosting model, and plan; the vendor columns summarize public materials reviewed on 2026-10-12. “Partial” means Interactive ELN implements a narrower workflow or a foundation without the vendor's full product-level controls.

| Capability | SciNote (vendor-documented) | eLabFTW (vendor-documented) | Interactive ELN status |
|---|---|---|---|
| Projects, experiments, records | ELN with experiment and project workflows | Experiments and protocols | **Partial** — projects, experiments, entries and experiment status; narrower workflow model |
| Structured templates and protocols | ELN workflow capabilities | Templates and protocols | **Partial** — organization-scoped entry/protocol templates; not vendor-equivalent workflow automation |
| Samples, reagents, lab inventory | Lab/sample workflows | Resource database for reagents, equipment, storage, and more | **Partial** — inventory, stock movements, sample register with parent/derived-sample lineage and parent archive protection, hierarchical storage locations, sample movement history, and tagged resources, plus recipient-confirmed custody transfers with acceptance notes, sender cancellation, and in-app notifications (requires Notebook migration 7b3e9c2d5a14) |
| Equipment booking / scheduling | Product capabilities | Scheduler / booking system | **Partial** — reservations with overlap checks, admin-managed maintenance lifecycle, service provider contact fields, bounded recurring windows scheduled on completion, conflict protection, `.ics` export, one-time `.ics` event import as equipment bookings with RRULE series capped at 100 occurrences per import, and read-only live calendar subscriptions; no ongoing bidirectional/provider-specific sync |
| Search, tags, categories | Product-specific organization and search features | Search, tags, customizable categories | **Partial** — PostgreSQL full-text query matching and applied GIN indexes across accessible projects, notebook text, lab resources and tags; no vendor-equivalent taxonomy |
| Files, data import/export | Product-specific data management | PDF, ZIP, CSV, JSON, and `.eln` export/import | **Partial** — own JSON/CSV/ZIP, supported RO-Crate `.eln` subset, and eLabFTW-compatible CSV rows mapped to experiments/entries, inventory resources, or project samples with parent links resolved by external ID; organization-managed typed inventory fields are supported, while importing vendor field templates and SciNote-native import remain |
| Tasks and workflow management | Collaboration and workflow features | To-do list and workflow steps | **Partial** — project tasks plus editable, pausable rules that generate tasks on experiment creation, notebook entry creation, or status transitions, with optional task assignment, sequential or unanimous parallel snapshot-bound experiment review, and approved/rejected/stale outcome branches for approval tasks, and ordered rejection escalation paths |
| Scientific document tools | Product-dependent scientific workflows | LaTeX, molecule editor, and doodles | **Partial** — inline/block LaTeX rendering, freehand PNG sketches, and a 2D molecule editor with formal charges, common charged-valence checks, editable JSON, MDL V2000 MOL/SDF charge and single-bond stereo-marker import/export, and a common SMILES subset; no R/S assignment or double-bond E/Z support |
| Localization | Product-dependent multilingual interfaces | Interface translations | **Partial** — English/Hindi selection for workspace navigation and the project dashboard, with locale-aware dates and Hindi workflow, molecule-editor, and equipment-scheduler controls; other detailed panels remain English |
| Notebook history and timestamping | Product history and compliance features | Record history and trusted timestamping | **Partial** — revision snapshots, RFC 3161 timestamp requests, proof ZIPs, and pinned-certificate verification when TSA configuration is supplied; not an immutable evidence service |
| Teams and granular permissions | Product access controls | Teams, groups, and fine-grained permissions | **Partial** — organization roles plus project owner/editor/viewer access |
| Audit trail and signatures | SciNote documents signatures, audit trail, timestamps, and activity log | Certified timestamping integrations and audit features | **Partial** — authenticated signature metadata and HMAC-chain foundation; not a validated or tamper-proof audit system |
| API and integrations | Product integration capabilities | Public REST API | **Partial** — gateway API, user-managed read/write credentials, and organization-managed outbound webhooks; no OAuth/provider-specific connectors |
| Internationalization and accessibility | Vendor/product-specific | 21+ languages and published accessibility claims | **Partial / unassessed** — English/Hindi workspace and project-dashboard strings, with locale-aware dates; detailed panels untranslated and no formal accessibility conformance assessment |

### Compatibility is not the same as feature parity

Interactive ELN is configured for PostgreSQL using SQLAlchemy's `postgresql+psycopg` driver. It is not a drop-in replacement for either hosted product and does not share their application database schema. The eLabFTW server documentation explicitly requires MySQL and says PostgreSQL is not supported by eLabFTW; therefore these products cannot share a PostgreSQL database, and Interactive ELN cannot run against an eLabFTW database. SciNote is a hosted product, not a PostgreSQL schema/API compatibility target. Import supports the application's JSON/ZIP bundle, a subset of ELN Consortium RO-Crate `.eln` records, and eLabFTW-compatible CSV rows mapped to experiments/notebook entries, inventory resources, or project samples with parent links resolved by external ID. Resource CSV imports preserve tags, stock fields, locations, and extra values as custom fields; organization admins can configure typed fields for manual inventory records. Vendor custom-field templates, ownership, and every eLabFTW export feature are not reconstructed, and it does not import SciNote's proprietary protocol-template files. See [eLabFTW server requirements](https://doc.elabftw.net/), [eLabFTW import/export documentation](https://doc.elabftw.net/docs/usage/import-export/), and [SciNote](https://www.scinote.net/).

**Conclusion:** PostgreSQL is the intended backend database and the application rejects a missing or non-PostgreSQL service URL. The schema/migration code is authored for PostgreSQL, and migrations have been rendered to PostgreSQL SQL. The local `identity`, `projects`, `notebook`, and `activity` databases have been created and upgraded to their current Alembic heads, including workflow assignment, sequential snapshot-bound approval reviews, recurring equipment maintenance, and typed inventory custom-field schemas. Feature-wise, the app has useful ELN fundamentals but does **not** have all SciNote or eLabFTW features.

### Vendor sources checked

- [SciNote official product site](https://www.scinote.net/) — describes electronic signatures, audit trail, timestamps, activity log, and access controls among its compliance feature set.
- [eLabFTW official product site](https://www.elabftw.net/) — documents experiments, inventory/resources, scheduler, advanced permissions, and export/import formats.
- [eLabFTW server documentation](https://doc.elabftw.net/) — states MySQL is required and PostgreSQL, MariaDB, and SQLite are unsupported for eLabFTW itself.
| Languages / hosting | Commercial product | Self-hostable; 21 languages listed by project | English UI; self-hosting direction |

References checked 2026-10-12: [SciNote](https://www.scinote.net/) and its [solutions page](https://www.scinote.net/solutions/); [eLabFTW feature summary](https://github.com/elabftw/elabftw#features) and [documentation](https://doc.elabftw.net/). SciNote features may depend on edition or plan. Confirm current vendor documentation and controls before procurement or compliance decisions.

This is an early general-purpose ELN foundation, not a production or compliance-ready application. Before public deployment, apply or safely baseline the service database migrations, add rate limiting and abuse controls, complete security review and operational monitoring, configure key rotation and secure secret management, verify backups, and configure deployment-specific email, TLS, and origin settings. Do not store regulated records or sensitive research data until the required controls and validation are implemented.

