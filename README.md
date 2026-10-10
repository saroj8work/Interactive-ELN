# Interactive ELN

An independent electronic lab notebook monorepo with a Python microservice backend and a React + TypeScript frontend. It is informed by common ELN workflows and is not a copy of SciNote.

## Backend architecture

```text
frontend/
backend/
├── eln_common/       Shared database, error, API-contract, and outbox primitives
├── gateway/          Public API gateway; routes the UI API to domain services
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

Create a local `.env` from `.env.example`, replacing both placeholders with separate random secrets of at least 32 bytes. For example, generate each with:

```powershell
py -c "import secrets; print(secrets.token_urlsafe(48))"
```

Keep `.env` private; it is ignored by Git. Then run:

```powershell
docker compose up --build
```

The public ELN gateway is at `http://localhost:8000`; its API documentation is at `http://localhost:8000/docs`. The identity service is at `http://localhost:8004`; identity API documentation is at `http://localhost:8004/docs`. Mailpit, the local-only development email inbox, is at `http://localhost:8025`. Vite proxies `/auth` to the identity service and `/api` to the ELN gateway. PostgreSQL data is held in separate named volumes. The credentials in `docker-compose.yml` are local-development-only and must be replaced for any real deployment.

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

Set `ELN_JWT_SECRET` to the same strong value for the identity service and gateway. Set `ELN_BOOTSTRAP_TOKEN` for organization provisioning, `IDENTITY_DATABASE_URL` for identity storage, `PUBLIC_APP_URL` for invitation links, and `SMTP_HOST` / `SMTP_FROM` (plus SMTP credentials where needed) for email delivery. Set `DATABASE_URL` separately for Projects, Notebook, and Activity. Set `PROJECTS_SERVICE_URL`, `NOTEBOOK_SERVICE_URL`, and `ACTIVITY_SERVICE_URL` for the gateway when services are not using defaults; Projects and Notebook also use `ACTIVITY_SERVICE_URL` for their outbox publisher.

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

The current slice covers invite-only organization/user administration, authentication and password recovery, tenant-scoped projects, explicit project-level owner/editor/viewer access, experiments, notebook entries with revision history and restore, reusable organization-scoped entry templates and protocols, project-filtered activity, organization-scoped reagent/consumable inventory, stock adjustment history, biological sample records, equipment booking with overlap checks, entry attachments, per-entry ZIP exports, and cross-record search. Entry templates can be applied to notebook records; protocols can start a new experiment with a structured protocol entry. Stock adjustments are transactionally recorded with the actor, reason, delta, and resulting quantity; negative stock is rejected. Attachment uploads are capped at 25 MiB each, stored under opaque server-generated names, checksum recorded, and only served as downloads; entry exports are capped at 100 MiB of attachments. Project-linked samples, bookings, and notebook attachments are filtered to project collaborators and admins. Projects created before project access control was introduced have no membership records and are visible only to organization admins until they grant access.

Still to build are full-text indexing, tags/categories, broader sample and inventory lifecycle workflows, and validated electronic-signature/tamper-resistant audit capabilities. Notebook history records prior content snapshots but is not tamper-proof. Equipment bookings support active/cancelled reservations and prevent overlapping active bookings, but do not yet include calendar integrations or maintenance workflows. The current activity/stock records are operational features, not a validated regulatory audit trail. Schema startup currently uses SQLAlchemy `create_all`; deployments with existing persistent databases need proper versioned migrations before production rollout.

## Product comparison

This is a directional comparison of publicly documented features, not a claim of feature parity.

| Capability | [SciNote](https://www.scinote.net/) | [eLabFTW](https://www.elabftw.net/) | Interactive ELN |
|---|---|---|---|
| Projects, experiments, notebook records | Yes | Yes (experiments and protocols) | Basic projects, experiments, entries |
| Structured templates and protocols | Documented workflow support | Templates and protocols | Organization-scoped entry/protocol templates |
| Samples, reagents, lab inventory | Product workflows | Resources/inventory | Sample register, inventory, and stock adjustment history |
| Equipment booking / scheduling | Product capabilities vary by plan | Scheduler/booking documented | Reservations with overlap checks; calendar integrations planned |
| Search, tags, categories, customization | Product capabilities | Search, tags, categories | SQL-backed cross-record search; tags/categories planned |
| Files, data export / interoperability | Product capabilities | Attachments, PDF/ZIP/CSV/JSON/ELN export | Per-entry attachments and ZIP bundle; other export formats planned |
| Notebook version history | Product capabilities | Timestamped record history | Prior-content snapshots and restore; not tamper-proof |
| Teams and granular permissions | Access controls | Teams, groups, entry permissions | Private-by-default projects; owner/editor/viewer sharing plus org admins |
| Activity traceability | Activity log and audit trail | Timestamping and signed/timestamped entries | Retriable activity feed; not tamper-proof |
| Electronic signatures / regulated use | Compliance-focused capabilities documented | Trusted timestamping and signing integrations | Not implemented; no compliance claim |
| Source / hosting model | Commercial product | Open-source AGPLv3, self-hostable | Open-source project in this repository; hosted multi-organization direction |

References: [SciNote public site](https://www.scinote.net/), [eLabFTW public features](https://www.elabftw.net/), and [eLabFTW documentation](https://doc.elabftw.net/). Confirm vendor plan details and current documentation directly before making procurement or compliance decisions.

This is an early general-purpose ELN foundation, not a production or compliance-ready application. Before public deployment, add database migrations, rate limiting and abuse controls, security review and operational monitoring, key rotation, secure secret management, backups, and deployment-specific email, TLS, and origin configuration. Do not store regulated records or sensitive research data until the required controls and validation are implemented.
