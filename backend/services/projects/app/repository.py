from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import Project, ProjectMembership


class ProjectRepository:
    def __init__(self, db: Session):
        self._db = db

    def list_accessible(
        self, organization_id: int, user_id: int, is_admin: bool
    ) -> list[Project]:
        statement = select(Project).where(Project.organization_id == organization_id)
        if not is_admin:
            statement = statement.join(
                ProjectMembership,
                (ProjectMembership.project_id == Project.id)
                & (ProjectMembership.organization_id == Project.organization_id),
            ).where(ProjectMembership.user_id == user_id)
        return list(
            self._db.scalars(
                statement.order_by(Project.created_at.desc())
            )
        )

    def get(self, organization_id: int, project_id: int) -> Project | None:
        return self._db.scalar(
            select(Project).where(
                Project.id == project_id,
                Project.organization_id == organization_id,
            )
        )

    def add(self, project: Project) -> Project:
        self._db.add(project)
        self._db.flush()
        return project

    def access(
        self, organization_id: int, project_id: int, user_id: int
    ) -> ProjectMembership | None:
        return self._db.scalar(
            select(ProjectMembership).where(
                ProjectMembership.organization_id == organization_id,
                ProjectMembership.project_id == project_id,
                ProjectMembership.user_id == user_id,
            )
        )

    def list_members(
        self, organization_id: int, project_id: int
    ) -> list[ProjectMembership]:
        return list(
            self._db.scalars(
                select(ProjectMembership)
                .where(
                    ProjectMembership.organization_id == organization_id,
                    ProjectMembership.project_id == project_id,
                )
                .order_by(ProjectMembership.id)
            )
        )

    def add_member(self, member: ProjectMembership) -> ProjectMembership:
        self._db.add(member)
        self._db.flush()
        return member

    def remove_member(self, member: ProjectMembership) -> None:
        self._db.delete(member)
        self._db.flush()
