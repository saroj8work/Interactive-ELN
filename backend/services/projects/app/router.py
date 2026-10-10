from typing import Annotated

from fastapi import APIRouter, Depends, Header, status
from sqlalchemy.orm import Session

from eln_common.contracts import (
    ProjectAccessRead,
    ProjectCreate,
    ProjectMemberCreate,
    ProjectMemberRead,
    ProjectRead,
)
from eln_common.database import Database
from eln_common.errors import InvalidInputError

from .repository import ProjectRepository
from .service import ProjectService


def create_router(database: Database) -> APIRouter:
    router = APIRouter(prefix="/projects", tags=["projects"])

    def get_service(db: Annotated[Session, Depends(database.dependency)]) -> ProjectService:
        return ProjectService(ProjectRepository(db), db)

    def actor_headers(
        organization_id: Annotated[int, Header(alias="X-Organization-ID")],
        user_id: Annotated[int, Header(alias="X-User-ID")],
        organization_role: Annotated[str, Header(alias="X-Organization-Role")],
    ) -> tuple[int, int, bool]:
        return organization_id, user_id, organization_role == "admin"

    @router.get("", response_model=list[ProjectRead])
    def list_projects(
        service: Annotated[ProjectService, Depends(get_service)],
        actor: Annotated[tuple[int, int, bool], Depends(actor_headers)],
    ) -> list[ProjectRead]:
        organization_id, user_id, is_admin = actor
        return service.list_projects(organization_id, user_id, is_admin)

    @router.get("/{project_id}", response_model=ProjectRead)
    def get_project(
        project_id: int,
        service: Annotated[ProjectService, Depends(get_service)],
        actor: Annotated[tuple[int, int, bool], Depends(actor_headers)],
    ) -> ProjectRead:
        organization_id, user_id, is_admin = actor
        return service.get_project(organization_id, project_id, user_id, is_admin)

    @router.get("/{project_id}/access", response_model=ProjectAccessRead)
    def get_project_access(
        project_id: int,
        service: Annotated[ProjectService, Depends(get_service)],
        actor: Annotated[tuple[int, int, bool], Depends(actor_headers)],
    ) -> ProjectAccessRead:
        organization_id, user_id, is_admin = actor
        return ProjectAccessRead(
            project_id=project_id,
            role=service.project_access(organization_id, project_id, user_id, is_admin),
        )

    @router.post("", response_model=ProjectRead, status_code=status.HTTP_201_CREATED)
    def create_project(
        payload: ProjectCreate,
        service: Annotated[ProjectService, Depends(get_service)],
        actor: Annotated[tuple[int, int, bool], Depends(actor_headers)],
    ) -> ProjectRead:
        organization_id, user_id, _ = actor
        return service.create_project(
            organization_id, user_id, payload.name, payload.description
        )

    @router.get("/{project_id}/members", response_model=list[ProjectMemberRead])
    def list_members(
        project_id: int,
        service: Annotated[ProjectService, Depends(get_service)],
        actor: Annotated[tuple[int, int, bool], Depends(actor_headers)],
    ) -> list[ProjectMemberRead]:
        organization_id, user_id, is_admin = actor
        return service.list_members(organization_id, project_id, user_id, is_admin)

    @router.put(
        "/{project_id}/members/{target_user_id}",
        response_model=ProjectMemberRead,
    )
    def set_member(
        project_id: int,
        target_user_id: int,
        payload: ProjectMemberCreate,
        service: Annotated[ProjectService, Depends(get_service)],
        actor: Annotated[tuple[int, int, bool], Depends(actor_headers)],
    ) -> ProjectMemberRead:
        organization_id, user_id, is_admin = actor
        if target_user_id != payload.user_id:
            raise InvalidInputError("User ID in path and payload must match.")
        return service.set_member(
            organization_id,
            project_id,
            user_id,
            is_admin,
            target_user_id,
            payload.role,
        )

    @router.delete("/{project_id}/members/{target_user_id}", status_code=204)
    def remove_member(
        project_id: int,
        target_user_id: int,
        service: Annotated[ProjectService, Depends(get_service)],
        actor: Annotated[tuple[int, int, bool], Depends(actor_headers)],
    ) -> None:
        organization_id, user_id, is_admin = actor
        service.remove_member(
            organization_id, project_id, user_id, is_admin, target_user_id
        )

    return router
