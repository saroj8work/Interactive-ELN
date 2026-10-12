from io import StringIO
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import text

from eln_common.config import required_postgresql_url
from eln_common.database import Database


BACKEND_ROOT = Path(__file__).resolve().parents[1]
SERVICE_TABLES = {
    "identity": {"organizations", "users", "memberships", "password_resets"},
    "projects": {"projects", "project_memberships", "outbox_events"},
    "notebook": {"experiments", "notebook_entries", "lab_tasks", "audit_events"},
    "activity": {"activity_events"},
}
DATABASE_URL_VARIABLES = {
    "identity": "IDENTITY_DATABASE_URL",
    "projects": "PROJECTS_DATABASE_URL",
    "notebook": "NOTEBOOK_DATABASE_URL",
    "activity": "ACTIVITY_DATABASE_URL",
}


@pytest.mark.parametrize("service,expected_tables", SERVICE_TABLES.items())
def test_service_migrations_render_postgresql_ddl(
    service: str,
    expected_tables: set[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    variable = DATABASE_URL_VARIABLES[service]
    monkeypatch.setenv(
        variable,
        f"postgresql+psycopg://test:test@localhost/{service}",
    )
    config = Config(str(BACKEND_ROOT / "migrations" / service / "alembic.ini"))
    config.output_buffer = StringIO()

    command.upgrade(config, "head", sql=True)

    migration_sql = config.output_buffer.getvalue()
    assert "CREATE TABLE alembic_version" in migration_sql
    for table in expected_tables:
        assert f"CREATE TABLE {table}" in migration_sql


@pytest.mark.parametrize(
    "url",
    [
        "sqlite://",
        "sqlite:///:memory:",
        "postgresql://test:test@localhost/eln",
        "mysql+pymysql://test:test@localhost/eln",
    ],
)
def test_application_database_rejects_non_psycopg_postgresql_urls(url: str) -> None:
    with pytest.raises(ValueError, match="disabled|must use PostgreSQL"):
        Database(url)


def test_sqlite_is_available_only_for_explicit_in_memory_test_database() -> None:
    database = Database("sqlite://", allow_sqlite_for_tests=True)
    try:
        with database.engine.begin() as connection:
            connection.execute(
                text(
                    "CREATE TABLE alembic_version "
                    "(version_num VARCHAR(32) NOT NULL PRIMARY KEY)"
                )
            )
            connection.execute(
                text("INSERT INTO alembic_version (version_num) VALUES ('test-head')")
            )
        assert database.engine.dialect.name == "sqlite"
    finally:
        database.engine.dispose()


def test_postgresql_url_must_be_explicit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("NOTEBOOK_DATABASE_URL", raising=False)
    with pytest.raises(RuntimeError, match="must be configured"):
        required_postgresql_url("NOTEBOOK_DATABASE_URL")
