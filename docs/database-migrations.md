# Database Migration Design

## Purpose and scope

This document describes the versioned database schema lifecycle for Interactive ELN. Alembic migrations are the authoritative, reviewable record of schema changes for the four service-owned databases. The goal is to make fresh installation, schema evolution, deployment checks, and recovery explicit and repeatable.

This design manages relational schema changes. It does not replace database backups, operational monitoring, data-retention policy, or a validated regulatory change-control process. It does not make the ELN Part 11-, GLP-, or GMP-certified.

## Architecture and ownership

The application has four isolated databases. A service owns and migrates only its own database; there are no cross-service foreign keys or distributed DDL transactions.

| Service | Database | Connection setting | Alembic configuration | Revision directory |
|---|---|---|---|---|
| Identity | `identity` | `IDENTITY_DATABASE_URL` | `backend/migrations/identity/alembic.ini` | `backend/migrations/identity/versions/` |
| Projects | `projects` | `PROJECTS_DATABASE_URL` | `backend/migrations/projects/alembic.ini` | `backend/migrations/projects/versions/` |
| Notebook | `notebook` | `NOTEBOOK_DATABASE_URL` | `backend/migrations/notebook/alembic.ini` | `backend/migrations/notebook/versions/` |
| Activity | `activity` | `ACTIVITY_DATABASE_URL` | `backend/migrations/activity/alembic.ini` | `backend/migrations/activity/versions/` |

The shared `backend/migrations/env.py` selects one service's SQLAlchemy models and URL using the `service` option in the selected configuration. Each Alembic environment uses the standard `alembic_version` table, but each table lives in a different database and therefore tracks an independent revision graph. Projects and Notebook include their service-local outbox table in their metadata. Identity and Activity do not include unrelated models.

The versioned DDL is concrete Python in each revision; revisions do not call `Base.metadata.create_all()`. This is important: an old revision must continue to represent the schema change it introduced, even after model definitions evolve.

## Initial baseline

Each service has an initial migration generated from the current SQLAlchemy model set. Applying `upgrade head` to a new empty database creates that service's tables, indexes, constraints, and `alembic_version` record. The initial revisions are independent; advancing one service does not advance another.

The repository previously created tables through `create_all()` during application startup. Existing databases from that era have tables but no Alembic revision marker. Alembic cannot infer from the presence of tables that they match the initial revision.

For a pre-existing database:

1. Stop writers and take a verified, restorable backup of each service database independently.
2. Inspect its tables, columns, nullability, defaults, indexes, unique constraints, and foreign keys. Compare the result with the corresponding initial revision and current model/schema snapshot. A successful `stamp` is not evidence that this comparison was done.
3. If and only if the complete schema already matches the initial revision, use that service's `stamp head` command to record the existing baseline. `stamp` only writes migration metadata; it does not create, alter, or validate application tables.
4. If the schema is older or differs, do not stamp it and do not run the initial `upgrade head` against populated tables. Prepare a service-specific, forward-only reconciliation/upgrade plan against a restored clone, preserve existing data, validate it, and only then mark the correct baseline. The repository cannot safely infer or synthesize that data-preserving plan without knowing the deployed schema and data.
5. Verify the service is at the expected Alembic head before restarting application writers.

Never use `docker compose down -v` as a migration or recovery step. It deletes named database volumes.

## Applying migrations

PostgreSQL with the `postgresql+psycopg` driver is required for application and migration connections. There are no SQLite defaults or fallback database URLs. Each service requires its own explicit connection setting from the table above. Docker Compose supplies container-network URLs; for local processes, export the service URLs from `.env` into the shell because Alembic and Uvicorn do not load `.env` automatically. Only in-memory SQLite may be explicitly enabled by isolated unit-test fixtures; it is not supported for migration execution or deployments.

Run migration commands from `backend` after setting the URLs:

Apply current migrations:

```powershell
python -m alembic -c migrations\identity\alembic.ini upgrade head
python -m alembic -c migrations\projects\alembic.ini upgrade head
python -m alembic -c migrations\notebook\alembic.ini upgrade head
python -m alembic -c migrations\activity\alembic.ini upgrade head
```

Inspect the history/current database before and after a deployment:

```powershell
python -m alembic -c migrations\notebook\alembic.ini history
python -m alembic -c migrations\notebook\alembic.ini current
python -m alembic -c migrations\notebook\alembic.ini heads
```

Baseline an already verified database that exactly matches the initial revision:

```powershell
python -m alembic -c migrations\notebook\alembic.ini stamp head
```

Use the matching configuration and connection URL for each service. Do not reuse one service's URL for another.

## Docker Compose lifecycle

Compose defines one one-shot migration job per database. Each job waits for its PostgreSQL container to become healthy, runs that database's `upgrade head`, and exits. Its API service is allowed to start only after the migration job completes successfully. Thus a failed migration prevents that service from starting with an unverified schema.

Fresh Compose volumes need no manual DDL: `docker compose up --build` builds the images, applies all four initial revisions, and then starts the APIs. Existing unversioned Compose volumes must first follow the verified-baseline procedure above. A typical controlled baseline starts the database containers, then overrides each migration job's command only after backups and schema comparison. For example:

```powershell
docker compose up -d identity-db projects-db notebook-db activity-db
docker compose run --rm identity-migrate python -m alembic -c migrations/identity/alembic.ini stamp head
docker compose run --rm projects-migrate python -m alembic -c migrations/projects/alembic.ini stamp head
docker compose run --rm notebook-migrate python -m alembic -c migrations/notebook/alembic.ini stamp head
docker compose run --rm activity-migrate python -m alembic -c migrations/activity/alembic.ini stamp head
docker compose up --build
```

These commands are safe only when every target database already matches its corresponding initial revision exactly. The normal Compose migration job remains `upgrade head`.

For production or multi-replica deployments, run migrations as a single deployment/release step with a database role that has schema-change privileges. Do not let every application replica race to migrate. Deploy compatible schema changes before application code that requires them, and do not route traffic until the migration and application health checks pass. Cross-service migrations are not atomic; plan and verify each service separately.

## Creating a schema change

1. Identify which service owns the data. Keep changes in that service's SQLAlchemy models and its migration history; never add cross-database foreign keys.
2. Update models and create a candidate revision from `backend`:

   ```powershell
   python -m alembic -c migrations\notebook\alembic.ini revision --autogenerate -m "add notebook field"
   ```

3. Review the revision as executable code. Confirm upgrade and downgrade operations, names, nullability, server defaults, data preservation, index costs, and PostgreSQL behavior. Autogeneration compares model metadata with a database; it is a starting point, not an approved migration.
4. For data transformations or renames, write explicit migration operations and test representative old data. For large tables, prefer staged expand/backfill/contract rollouts: add compatible nullable structures, deploy code that can handle both shapes, backfill in bounded batches, and remove obsolete structures only in a later release.
5. Apply to a disposable PostgreSQL database from the previous revision, verify the resulting schema and application behavior, and test downgrade only when the operation is genuinely reversible. SQLite-only unit tests do not prove PostgreSQL locking, constraints, or DDL behavior.
6. Commit the model, revision, tests, and relevant documentation together. Once a revision has been shared or applied to a persistent environment, add a new forward revision to correct it; do not rewrite its history.

An offline SQL preview can be produced for review:

```powershell
python -m alembic -c migrations\notebook\alembic.ini upgrade head --sql
```

Review that output before applying it through a separately controlled database operation.

## Application startup guard

Each service lifespan compares the database's current Alembic revision heads with the heads shipped in its code. A missing, older, or unexpected revision raises a startup error with the matching upgrade command instead of creating or altering tables implicitly. Version drift therefore cannot be mistaken for a successful startup. The guard does not detect manual schema edits when the recorded revision remains at head; schema inspection and controlled database access are still required.

Tests that construct isolated in-memory databases may still call SQLAlchemy `create_all()` directly as a test fixture. That helper is not invoked by a service lifespan and is not a deployment mechanism.

## Safety, backups, and rollback

- Take and verify restorable database backups before production migrations, especially before data changes or destructive DDL.
- A transaction around DDL is dialect- and operation-dependent. Do not assume every operation can be rolled back after a process or database failure.
- A downgrade can destroy data, and some transformations have no truthful inverse. Prefer a forward corrective migration or restore-and-replay plan when rollback cannot preserve data.
- Preserve the `alembic_version` table. Do not edit its row by hand to hide a failed migration or schema mismatch.
- Use least-privilege application credentials in production. Grant schema-altering privileges only to the migration job where practical.
- Keep connection strings and credentials out of revisions, logs, command history, and committed configuration.
- Review lock duration, table size, index build strategy, and maintenance window for PostgreSQL operations. Use staged rollout for changes that cannot safely block writers.

## Limitations

There is no automatic schema diff or repair for an unversioned database, no cross-service migration transaction, and no release-system integration beyond the Compose migration jobs and startup gate. PostgreSQL is the only supported application and migration database. The retained `backend/postgresql_ddl.sql` is a point-in-time reference, not the migration history and not a script to apply alongside Alembic. Database migrations provide operational schema versioning, not audit immutability or regulatory certification.
