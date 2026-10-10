from datetime import datetime

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from .models import (
    Invitation,
    Membership,
    Organization,
    PasswordReset,
    RefreshSession,
    User,
)


class IdentityRepository:
    def __init__(self, db: Session):
        self._db = db

    def get_organization_by_slug(self, slug: str) -> Organization | None:
        return self._db.scalar(select(Organization).where(Organization.slug == slug))

    def get_organization(self, organization_id: int) -> Organization | None:
        return self._db.get(Organization, organization_id)

    def add_organization(self, organization: Organization) -> Organization:
        self._db.add(organization)
        self._db.flush()
        return organization

    def get_user_by_email(self, email: str) -> User | None:
        return self._db.scalar(select(User).where(User.email == email))

    def get_user(self, user_id: int) -> User | None:
        return self._db.get(User, user_id)

    def add_user(self, user: User) -> User:
        self._db.add(user)
        self._db.flush()
        return user

    def membership(
        self, organization_id: int, user_id: int
    ) -> Membership | None:
        return self._db.scalar(
            select(Membership).where(
                Membership.organization_id == organization_id,
                Membership.user_id == user_id,
            )
        )

    def add_membership(self, membership: Membership) -> Membership:
        self._db.add(membership)
        self._db.flush()
        return membership

    def add_invitation(self, invitation: Invitation) -> Invitation:
        self._db.add(invitation)
        self._db.flush()
        return invitation

    def get_invitation(self, token_hash: str) -> Invitation | None:
        return self._db.scalar(
            select(Invitation)
            .where(Invitation.token_hash == token_hash)
            .with_for_update()
        )

    def list_memberships(self, organization_id: int) -> list[tuple[Membership, User]]:
        return list(
            self._db.execute(
                select(Membership, User)
                .join(User, User.id == Membership.user_id)
                .where(Membership.organization_id == organization_id)
                .order_by(User.email)
            )
        )

    def add_refresh_session(self, session: RefreshSession) -> RefreshSession:
        self._db.add(session)
        self._db.flush()
        return session

    def get_refresh_session(self, token_hash: str) -> RefreshSession | None:
        return self._db.scalar(
            select(RefreshSession)
            .where(RefreshSession.token_hash == token_hash)
            .with_for_update()
        )

    def add_password_reset(self, reset: PasswordReset) -> PasswordReset:
        self._db.add(reset)
        self._db.flush()
        return reset

    def get_password_reset(self, token_hash: str) -> PasswordReset | None:
        return self._db.scalar(
            select(PasswordReset)
            .where(PasswordReset.token_hash == token_hash)
            .with_for_update()
        )

    def invalidate_password_resets(
        self, user_id: int, organization_id: int, used_at: datetime
    ) -> None:
        self._db.execute(
            update(PasswordReset)
            .where(
                PasswordReset.user_id == user_id,
                PasswordReset.organization_id == organization_id,
                PasswordReset.used_at.is_(None),
            )
            .values(used_at=used_at)
        )

    def revoke_user_refresh_sessions(self, user_id: int, revoked_at: datetime) -> None:
        self._db.execute(
            update(RefreshSession)
            .where(
                RefreshSession.user_id == user_id,
                RefreshSession.revoked_at.is_(None),
            )
            .values(revoked_at=revoked_at)
        )
