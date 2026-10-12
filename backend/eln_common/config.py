import os
from dataclasses import dataclass
from typing import Literal

from sqlalchemy.exc import ArgumentError
from sqlalchemy.engine import make_url

ServiceName = Literal["projects", "notebook", "activity"]


def required_postgresql_url(environment_variable: str) -> str:
    value = os.getenv(environment_variable)
    if not value:
        raise RuntimeError(
            f"{environment_variable} must be configured with a PostgreSQL "
            "SQLAlchemy URL using the psycopg 3 driver."
        )
    try:
        url = make_url(value)
    except ArgumentError as error:
        raise RuntimeError(f"{environment_variable} is not a valid database URL.") from error
    if url.drivername != "postgresql+psycopg" or not url.database:
        raise RuntimeError(
            f"{environment_variable} must use "
            "'postgresql+psycopg://user:password@host:port/database'."
        )
    return value


@dataclass(frozen=True)
class ServiceSettings:
    name: str
    database_url: str
    activity_service_url: str = "http://activity-service:8003"

    @classmethod
    def for_service(cls, name: str) -> "ServiceSettings":
        if name not in {"projects", "notebook", "activity"}:
            raise ValueError(f"Unknown database service: {name}")
        return cls(
            name=name,
            database_url=required_postgresql_url(f"{name.upper()}_DATABASE_URL"),
            activity_service_url=os.getenv(
                "ACTIVITY_SERVICE_URL", "http://activity-service:8003"
            ).rstrip("/"),
        )


@dataclass(frozen=True)
class GatewaySettings:
    projects_service_url: str = os.getenv(
        "PROJECTS_SERVICE_URL", "http://projects-service:8001"
    ).rstrip("/")
    notebook_service_url: str = os.getenv(
        "NOTEBOOK_SERVICE_URL", "http://notebook-service:8002"
    ).rstrip("/")
    activity_service_url: str = os.getenv(
        "ACTIVITY_SERVICE_URL", "http://activity-service:8003"
    ).rstrip("/")

    def url_for(self, service: ServiceName) -> str:
        services = {
            "projects": self.projects_service_url,
            "notebook": self.notebook_service_url,
            "activity": self.activity_service_url,
        }
        return services[service]
