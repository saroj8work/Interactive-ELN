from sqlalchemy.orm import Session

from eln_common.errors import EntityNotFoundError, InvalidInputError
from eln_common.outbox import enqueue_event

from .models import Project, ProjectMembership
from .repository import ProjectRepository


class ProjectService:
    def __init__(self, repository: ProjectRepository, db: Session):
        self._repository = repository
        self._db = db

    def list_projects(
        self, organization_id: int, user_id: int, is_admin: bool
    ) -> list[Project]:
        return self._repository.list_accessible(organization_id, user_id, is_admin)

    def get_project(
        self, organization_id: int, project_id: int, user_id: int, is_admin: bool
    ) -> Project:
        project = self._repository.get(organization_id, project_id)
        if project is None or (
            not is_admin
            and self._repository.access(organization_id, project_id, user_id) is None
        ):
            raise EntityNotFoundError("Project not found.")
        return project

    def create_project(
        self, organization_id: int, user_id: int, name: str, description: str
    ) -> Project:
        normalized_name = name.strip()
        if not normalized_name:
            raise InvalidInputError("Project name cannot be blank.")
        project = self._repository.add(
            Project(
                organization_id=organization_id,
                name=normalized_name,
                description=description.strip(),
            )
        )
        self._repository.add_member(
            ProjectMembership(
                organization_id=organization_id,
                project_id=project.id,
                user_id=user_id,
                role="owner",
            )
        )
        enqueue_event(
            self._db,
            source_service="projects",
            action="created",
            entity_type="project",
            entity_id=project.id,
            organization_id=organization_id,
            details={"name": project.name},
        )
        self._db.commit()
        self._db.refresh(project)
        return project

    def project_access(
        self, organization_id: int, project_id: int, user_id: int, is_admin: bool
    ) -> str:
        self.get_project(organization_id, project_id, user_id, is_admin)
        if is_admin:
            return "admin"
        member = self._repository.access(organization_id, project_id, user_id)
        if member is None:
            raise EntityNotFoundError("Project not found.")
        return member.role

    def list_members(
        self, organization_id: int, project_id: int, user_id: int, is_admin: bool
    ) -> list[ProjectMembership]:
        self._require_manager(organization_id, project_id, user_id, is_admin)
        return self._repository.list_members(organization_id, project_id)

    def set_member(
        self,
        organization_id: int,
        project_id: int,
        user_id: int,
        is_admin: bool,
        target_user_id: int,
        role: str,
    ) -> ProjectMembership:
        self._require_manager(organization_id, project_id, user_id, is_admin)
        if target_user_id == user_id and not is_admin:
            raise InvalidInputError("Project owners cannot change their own access.")
        member = self._repository.access(organization_id, project_id, target_user_id)
        action = "access_granted" if member is None else "access_updated"
        if member is not None and member.role == "owner":
            raise InvalidInputError("Project ownership cannot be changed here.")
        if member is None:
            member = ProjectMembership(
                organization_id=organization_id,
                project_id=project_id,
                user_id=target_user_id,
                role=role,
            )
            self._repository.add_member(member)
        else:
            member.role = role
        enqueue_event(
            self._db,
            source_service="projects",
            action=action,
            entity_type="project_access",
            entity_id=member.id,
            organization_id=organization_id,
            details={
                "project_id": str(project_id),
                "user_id": str(target_user_id),
                "role": role,
                "changed_by_user_id": str(user_id),
            },
        )
        self._db.commit()
        self._db.refresh(member)
        return member

    def remove_member(
        self,
        organization_id: int,
        project_id: int,
        user_id: int,
        is_admin: bool,
        target_user_id: int,
    ) -> None:
        self._require_manager(organization_id, project_id, user_id, is_admin)
        member = self._repository.access(organization_id, project_id, target_user_id)
        if member is None:
            raise EntityNotFoundError("Project member not found.")
        if member.role == "owner":
            raise InvalidInputError("Project ownership cannot be removed.")
        enqueue_event(
            self._db,
            source_service="projects",
            action="access_removed",
            entity_type="project_access",
            entity_id=member.id,
            organization_id=organization_id,
            details={
                "project_id": str(project_id),
                "user_id": str(target_user_id),
                "changed_by_user_id": str(user_id),
            },
        )
        self._repository.remove_member(member)
        self._db.commit()

    def _require_manager(
        self, organization_id: int, project_id: int, user_id: int, is_admin: bool
    ) -> None:
        role = self.project_access(organization_id, project_id, user_id, is_admin)
        if role not in {"owner", "admin"}:
            raise EntityNotFoundError("Project not found.")
