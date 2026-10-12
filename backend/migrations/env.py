from __future__ import annotations

from alembic import context
from sqlalchemy import engine_from_config, pool
from sqlalchemy.engine import Connection

from eln_common.config import required_postgresql_url
from eln_common.database import Base


config = context.config

service = config.get_main_option("service")
if service == "identity":
    from services.identity.app import models as service_models

    database_url = required_postgresql_url("IDENTITY_DATABASE_URL")
elif service == "projects":
    from eln_common import outbox as outbox_models
    from services.projects.app import models as service_models

    _ = outbox_models
    database_url = required_postgresql_url("PROJECTS_DATABASE_URL")
elif service == "notebook":
    from eln_common import outbox as outbox_models
    from services.notebook.app import models as service_models

    _ = outbox_models
    database_url = required_postgresql_url("NOTEBOOK_DATABASE_URL")
elif service == "activity":
    from services.activity.app import models as service_models

    database_url = required_postgresql_url("ACTIVITY_DATABASE_URL")
else:
    raise RuntimeError(f"Unknown Alembic service configured: {service!r}")

_ = service_models

config.set_main_option("sqlalchemy.url", database_url.replace("%", "%%"))
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    external_connection = config.attributes.get("connection")
    if external_connection is not None:
        _run_with_connection(external_connection)
        return

    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        _run_with_connection(connection)


def _run_with_connection(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
