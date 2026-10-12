from collections.abc import Generator
from pathlib import Path

from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import Engine, create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.pool import StaticPool


MIGRATION_SERVICES = {"identity", "projects", "notebook", "activity"}


class Base(DeclarativeBase):
    pass


class Database:
    def __init__(self, url: str, *, allow_sqlite_for_tests: bool = False):
        parsed_url = make_url(url)
        if parsed_url.drivername == "sqlite":
            if not allow_sqlite_for_tests or parsed_url.database not in {
                None,
                "",
                ":memory:",
            }:
                raise ValueError(
                    "SQLite is disabled for application databases; use PostgreSQL. "
                    "In-memory SQLite is available only to explicit test fixtures."
                )
            self.engine: Engine = create_engine(
                url,
                connect_args={"check_same_thread": False},
                poolclass=StaticPool,
            )
        elif parsed_url.drivername == "postgresql+psycopg" and parsed_url.database:
            self.engine = create_engine(url, pool_pre_ping=True)
        else:
            raise ValueError(
                "Application databases must use PostgreSQL with the psycopg 3 "
                "driver and include a database name."
            )
        self._session_factory = sessionmaker(
            bind=self.engine, autoflush=False, expire_on_commit=False
        )

    def assert_schema_is_current(self, service: str) -> None:
        if service not in MIGRATION_SERVICES:
            raise ValueError(f"Unknown database migration service: {service}")
        config_path = (
            Path(__file__).resolve().parents[1]
            / "migrations"
            / service
            / "alembic.ini"
        )
        config = Config(str(config_path))
        script = ScriptDirectory.from_config(config)
        with self.engine.connect() as connection:
            current_heads = set(
                MigrationContext.configure(connection).get_current_heads()
            )
        expected_heads = set(script.get_heads())
        if current_heads != expected_heads:
            current = ", ".join(sorted(current_heads)) if current_heads else "none"
            expected = ", ".join(sorted(expected_heads)) or "no migration revisions"
            raise RuntimeError(
                f"The {service} database schema is not at the latest migration "
                f"(current: {current}; expected: {expected}). Apply migrations with "
                f"`python -m alembic -c migrations/{service}/alembic.ini upgrade head`."
            )

    def session(self) -> Session:
        return self._session_factory()

    def dependency(self) -> Generator[Session, None, None]:
        with self.session() as session:
            yield session
