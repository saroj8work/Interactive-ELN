import os
from dataclasses import dataclass
from typing import Literal

from sqlalchemy.exc import ArgumentError
from sqlalchemy.engine import make_url

ServiceName = Literal[
    "projects",
    "notebook",
    "activity",
    "plates",
    "cheminformatics",
    "molecular",
    "canvas",
    "analytics",
    "dossier",
    "thermal_printer",
]


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
        valid = {
            "projects",
            "notebook",
            "activity",
            "plates",
            "cheminformatics",
            "molecular",
            "canvas",
            "analytics",
            "dossier",
            "thermal_printer",
        }
        if name not in valid:
            raise ValueError(f"Unknown database service: {name}")
        env_var = f"{name.upper()}_DATABASE_URL"
        db_url = os.getenv(env_var) or os.getenv("NOTEBOOK_DATABASE_URL")
        return cls(
            name=name,
            database_url=db_url or required_postgresql_url("NOTEBOOK_DATABASE_URL"),
            activity_service_url=os.getenv(
                "ACTIVITY_SERVICE_URL", "http://activity-service:8003"
            ).rstrip("/"),
        )


@dataclass(frozen=True)
class GatewaySettings:
    projects_service_url: str = os.getenv(
        "PROJECTS_SERVICE_URL", "http://127.0.0.1:8001"
    ).rstrip("/")
    notebook_service_url: str = os.getenv(
        "NOTEBOOK_SERVICE_URL", "http://127.0.0.1:8002"
    ).rstrip("/")
    activity_service_url: str = os.getenv(
        "ACTIVITY_SERVICE_URL", "http://127.0.0.1:8003"
    ).rstrip("/")
    identity_service_url: str = os.getenv(
        "IDENTITY_SERVICE_URL", "http://127.0.0.1:8004"
    ).rstrip("/")
    plates_service_url: str = os.getenv(
        "PLATES_SERVICE_URL", "http://127.0.0.1:8005"
    ).rstrip("/")
    cheminformatics_service_url: str = os.getenv(
        "CHEMINFORMATICS_SERVICE_URL", "http://127.0.0.1:8006"
    ).rstrip("/")
    molecular_service_url: str = os.getenv(
        "MOLECULAR_SERVICE_URL", "http://127.0.0.1:8007"
    ).rstrip("/")
    canvas_service_url: str = os.getenv(
        "CANVAS_SERVICE_URL", "http://127.0.0.1:8008"
    ).rstrip("/")
    analytics_service_url: str = os.getenv(
        "ANALYTICS_SERVICE_URL", "http://127.0.0.1:8009"
    ).rstrip("/")
    dossier_service_url: str = os.getenv(
        "DOSSIER_SERVICE_URL", "http://127.0.0.1:8011"
    ).rstrip("/")
    thermal_printer_service_url: str = os.getenv(
        "THERMAL_PRINTER_SERVICE_URL", "http://127.0.0.1:8012"
    ).rstrip("/")

    def url_for(self, service: ServiceName) -> str:
        services = {
            "projects": self.projects_service_url,
            "notebook": self.notebook_service_url,
            "activity": self.activity_service_url,
            "plates": self.plates_service_url,
            "cheminformatics": self.cheminformatics_service_url,
            "molecular": self.molecular_service_url,
            "canvas": self.canvas_service_url,
            "analytics": self.analytics_service_url,
            "dossier": self.dossier_service_url,
            "thermal_printer": self.thermal_printer_service_url,
        }
        return services[service]
