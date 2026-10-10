import os
from dataclasses import dataclass
from typing import Literal

ServiceName = Literal["projects", "notebook", "activity"]


@dataclass(frozen=True)
class ServiceSettings:
    name: str
    database_url: str
    activity_service_url: str = "http://activity-service:8003"

    @classmethod
    def for_service(cls, name: str, default_database_url: str) -> "ServiceSettings":
        return cls(
            name=name,
            database_url=os.getenv("DATABASE_URL", default_database_url),
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
