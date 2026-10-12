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

Domain writes and their activity events are committed together to a service-local outbox. A background publisher retries event delivery, while the Activity service deduplicates by event ID. This is an eventually consistent activity feed, not a validated or tamper-proof regulatory audit trail.

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

Keep `.env` private; it is ignored by Git. The audit HMAC key is used only by the Notebook service to protect the current audit/signature foundation. Keep it separate from the JWT secret and back it up securely; losing or rotating it prevents verification of existing signatures. This feature is not a compliance control.

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

Entry signatures record an authenticated user ID, declared meaning/comment, timestamp, and digest of the signed entry state. The Notebook service signs canonical audit events with `ELN_AUDIT_HMAC_KEY` and exposes an organization-admin chain verification endpoint. This is a limited foundation only: it does not reauthenticate the signer, provide trusted timestamps or external anchoring, prevent a database administrator from deleting/rewriting the chain, or meet Part 11, GLP, or GMP requirements. It is not tamper-proof or regulatory-compliant.

This is not full SciNote/eLabFTW feature parity. The table below marks implemented portions, partial foundations, and missing product capabilities. Remaining gaps include full-text indexing, broader sample/inventory lifecycle and storage-location tooling, automated workflow rules, third-party import formats, calendar integrations, scientific document tooling (LaTeX and a molecule editor), external API credentials/integration tooling, and internationalization. The implemented signature/audit foundation is not a trusted timestamp service or immutable evidence store and does not provide validated controls for 21 CFR Part 11 / GLP / GMP. Entry revisions and the operational activity feed can be changed by database operators; an HMAC chain without an external anchor cannot prevent undetected tail deletion by a privileged operator. Equipment bookings do not include maintenance workflows. Database schema changes are managed by service-specific Alembic migrations; existing databases must be safely baselined or migrated before rollout. This feature list is a roadmap, not a promise of certification or vendor parity.

## Product comparison

This is a capability check, not a claim of parity or a certification statement. Product features vary by vendor release, hosting model, and plan; the vendor columns summarize public materials reviewed on 2026-10-12. “Partial” means Interactive ELN implements a narrower workflow or a foundation without the vendor's full product-level controls.

| Capability | SciNote (vendor-documented) | eLabFTW (vendor-documented) | Interactive ELN status |
|---|---|---|---|
| Projects, experiments, records | ELN with experiment and project workflows | Experiments and protocols | **Partial** — projects, experiments, entries and experiment status; narrower workflow model |
| Structured templates and protocols | ELN workflow capabilities | Templates and protocols | **Partial** — organization-scoped entry/protocol templates; not vendor-equivalent workflow automation |
| Samples, reagents, lab inventory | Lab/sample workflows | Resource database for reagents, equipment, storage, and more | **Partial** — inventory, stock movements, sample register and tagged resources; limited lifecycle/location features |
| Equipment booking / scheduling | Product capabilities | Scheduler / booking system | **Partial** — reservations with overlap checks; no calendar integration or maintenance workflow |
| Search, tags, categories | Product-specific organization and search features | Search, tags, customizable categories | **Partial** — SQL-backed cross-record search and tags; no full-text indexing or vendor-equivalent taxonomy |
| Files, data import/export | Product-specific data management | PDF, ZIP, CSV, JSON, and `.eln` export/import | **Partial** — own JSON/CSV and attachment-inclusive ZIP bundles; no native SciNote/eLabFTW or `.eln` interoperability |
| Tasks and workflow management | Collaboration and workflow features | To-do list and workflow steps | **Partial** — project tasks and manual statuses; no automated workflow rules |
| Scientific document tools | Product-dependent scientific workflows | LaTeX, molecule editor, and doodles | **Missing** — not implemented |
| Notebook history and timestamping | Product history and compliance features | Record history and trusted timestamping | **Partial** — revision snapshots and restore; not immutable or trusted timestamping |
| Teams and granular permissions | Product access controls | Teams, groups, and fine-grained permissions | **Partial** — organization roles plus project owner/editor/viewer access |
| Audit trail and signatures | SciNote documents signatures, audit trail, timestamps, and activity log | Certified timestamping integrations and audit features | **Partial** — authenticated signature metadata and HMAC-chain foundation; not a validated or tamper-proof audit system |
| API and integrations | Product integration capabilities | Public REST API | **Partial** — application gateway API; no user-managed API credentials or external integration management |
| Internationalization and accessibility | Vendor/product-specific | 21+ languages and published accessibility claims | **Missing / unassessed** — no localization; no formal accessibility conformance assessment |

### Compatibility is not the same as feature parity

Interactive ELN is configured for PostgreSQL using SQLAlchemy's `postgresql+psycopg` driver. It is not a drop-in replacement for either hosted product and does not share their application database schema. The eLabFTW server documentation explicitly requires MySQL and says PostgreSQL is not supported by eLabFTW; therefore these products cannot share a PostgreSQL database, and Interactive ELN cannot run against an eLabFTW database. SciNote is a hosted product, not a PostgreSQL schema/API compatibility target. The project currently supports importing its own documented JSON/ZIP bundle, not direct vendor-native data imports. See [eLabFTW server requirements](https://doc.elabftw.net/) and [SciNote](https://www.scinote.net/).

**Conclusion:** PostgreSQL is the intended backend database and the application rejects a missing or non-PostgreSQL service URL. The schema/migration code is authored for PostgreSQL, and migrations have been rendered to PostgreSQL SQL; however, this environment has no live PostgreSQL server, so an actual PostgreSQL migration/app integration run remains to be performed. Feature-wise, the app has useful ELN fundamentals but does **not** have all SciNote or eLabFTW features.

### Vendor sources checked

- [SciNote official product site](https://www.scinote.net/) — describes electronic signatures, audit trail, timestamps, activity log, and access controls among its compliance feature set.
- [eLabFTW official product site](https://www.elabftw.net/) — documents experiments, inventory/resources, scheduler, advanced permissions, and export/import formats.
- [eLabFTW server documentation](https://doc.elabftw.net/) — states MySQL is required and PostgreSQL, MariaDB, and SQLite are unsupported for eLabFTW itself.
| Languages / hosting | Commercial product | Self-hostable; 21 languages listed by project | English UI; self-hosting direction |

References checked 2026-10-12: [SciNote](https://www.scinote.net/) and its [solutions page](https://www.scinote.net/solutions/); [eLabFTW feature summary](https://github.com/elabftw/elabftw#features) and [documentation](https://doc.elabftw.net/). SciNote features may depend on edition or plan. Confirm current vendor documentation and controls before procurement or compliance decisions.

This is an early general-purpose ELN foundation, not a production or compliance-ready application. Before public deployment, add database migrations, rate limiting and abuse controls, security review and operational monitoring, key rotation, secure secret management, backups, and deployment-specific email, TLS, and origin configuration. Do not store regulated records or sensitive research data until the required controls and validation are implemented.


##REmaining works
SciNote/eLabFTW parity and compatibility
The app does not have full feature parity with either product. The updated README comparison marks implemented, partial, and missing capabilities. Important gaps include native vendor-format imports, automated workflows, scientific document tools, broader resource/location management, trusted timestamping, and validated regulatory controls. The current signature and audit features are a limited foundation, not Part 11/GLP/GMP compliance.

This is also not a drop-in database or application replacement for either vendor. In particular, eLabFTW’s server documentation specifies MySQL and says PostgreSQL isn’t supported by eLabFTW itself; its database cannot be shared with this PostgreSQL application. The app supports its own JSON/ZIP bundle format, not direct SciNote or eLabFTW data imports.
