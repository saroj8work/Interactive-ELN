from sqlalchemy import func, literal_column, or_, select
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

    def search_accessible(
        self, organization_id: int, user_id: int, is_admin: bool, query: str
    ) -> list[Project]:
        statement = select(Project).where(Project.organization_id == organization_id)
        if not is_admin:
            statement = statement.join(
                ProjectMembership,
                (ProjectMembership.project_id == Project.id)
                & (ProjectMembership.organization_id == Project.organization_id),
            ).where(ProjectMembership.user_id == user_id)
        if self._db.get_bind().dialect.name == "postgresql":
            document = (
                func.coalesce(Project.name, literal_column("''"))
                .op("||")(literal_column("' '"))
                .op("||")(func.coalesce(Project.description, literal_column("''")))
            )
            matches = func.to_tsvector(
                literal_column("'simple'::regconfig"), document
            ).op("@@")(
                func.plainto_tsquery(literal_column("'simple'::regconfig"), query)
            )
        else:
            pattern = "%" + query.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
            matches = or_(
                Project.name.ilike(pattern, escape="\\"),
                Project.description.ilike(pattern, escape="\\"),
            )
        return list(
            self._db.scalars(
                statement.where(matches)
                .order_by(Project.created_at.desc())
                .limit(100)
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
