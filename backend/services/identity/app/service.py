import os
import re
from datetime import datetime, timedelta, timezone
from typing import Protocol
from urllib.parse import urlencode

from sqlalchemy.orm import Session

from eln_common.errors import (
    AuthenticationError,
    EntityNotFoundError,
    InvalidInputError,
)

from .models import (
    Invitation,
    Membership,
    Organization,
    PasswordReset,
    RefreshSession,
    User,
)
from .repository import IdentityRepository
from .security import (
    create_access_token,
    hash_password,
    opaque_token,
    token_digest,
    verify_password,
)


INVITATION_LIFETIME = timedelta(days=7)
REFRESH_LIFETIME = timedelta(days=14)
PASSWORD_RESET_LIFETIME = timedelta(hours=1)

class InvitationSender(Protocol):
    def send(self, recipient: str, organization_name: str, invite_url: str) -> None: ...
    def send_password_reset(self, recipient: str, reset_url: str) -> None: ...


class IdentityService:
    def __init__(
        self,
        repository: IdentityRepository,
        db: Session,
        mailer: InvitationSender | None = None,
    ):
        self._repository = repository
        self._db = db
        self._mailer = mailer

    def bootstrap_organization(
        self,
        *,
        name: str,
        slug: str,
        owner_email: str,
        owner_name: str,
    ) -> tuple[Organization, str]:
        normalized_slug = slug.strip().lower()
        self._validate_slug(normalized_slug)
        if self._repository.get_organization_by_slug(normalized_slug):
            raise InvalidInputError("Organization slug is already registered.")
        organization = self._repository.add_organization(
            Organization(name=name.strip(), slug=normalized_slug)
        )
        token = self._create_invitation(
            organization=organization,
            email=owner_email,
            role="admin",
            invited_by_user_id=None,
        )
        self._db.commit()
        self._db.refresh(organization)
        return organization, token

    def create_invitation(
        self,
        organization_id: int,
        invited_by_user_id: int,
        email: str,
        role: str,
    ) -> str:
        organization = self._repository.get_organization(organization_id)
        if organization is None or not organization.is_active:
            raise EntityNotFoundError("Organization not found.")
        return self._create_invitation(
            organization=organization,
            email=email,
            role=role,
            invited_by_user_id=invited_by_user_id,
        )

    def _create_invitation(
        self,
        *,
        organization: Organization,
        email: str,
        role: str,
        invited_by_user_id: int | None,
    ) -> str:
        normalized_email = email.strip().lower()
        if role not in {"admin", "member"}:
            raise InvalidInputError("Invitation role must be admin or member.")
        existing_user = self._repository.get_user_by_email(normalized_email)
        if existing_user and self._repository.membership(organization.id, existing_user.id):
            raise InvalidInputError("This user already belongs to the organization.")
        if self._mailer is None:
            self._validate_mail_configuration()
        raw_token = opaque_token()
        invitation = Invitation(
            organization_id=organization.id,
            email=normalized_email,
            role=role,
            token_hash=token_digest(raw_token),
            invited_by_user_id=invited_by_user_id,
            expires_at=datetime.now(timezone.utc) + INVITATION_LIFETIME,
        )
        try:
            self._repository.add_invitation(invitation)
            base_url = os.getenv("PUBLIC_APP_URL", "http://localhost:5173").rstrip("/")
            query = urlencode(
                {"token": raw_token, "organization": organization.slug}
            )
            invite_url = f"{base_url}/accept-invitation?{query}"
            if self._mailer is None:
                from .mailer import InvitationMailer

                mailer: InvitationSender = InvitationMailer()
            else:
                mailer = self._mailer
            mailer.send(normalized_email, organization.name, invite_url)
            self._db.commit()
            return raw_token
        except Exception:
            self._db.rollback()
            raise

    def accept_invitation(
        self, token: str, display_name: str, password: str
    ) -> User:
        invitation = self._repository.get_invitation(token_digest(token))
        now = datetime.now(timezone.utc)
        expires_at = invitation.expires_at if invitation is not None else None
        if expires_at is not None and expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        if (
            invitation is None
            or invitation.accepted_at is not None
            or expires_at is None
            or expires_at <= now
        ):
            raise InvalidInputError("Invitation is invalid or expired.")
        organization = self._repository.get_organization(invitation.organization_id)
        if organization is None or not organization.is_active:
            raise EntityNotFoundError("Organization not found.")

        try:
            user = self._repository.get_user_by_email(invitation.email)
            if user is None:
                user = self._repository.add_user(
                    User(
                        email=invitation.email,
                        display_name=display_name.strip(),
                        password_hash=hash_password(password),
                        email_verified_at=now,
                    )
                )
            elif (
                user.email_verified_at is None
                or not user.is_active
                or not verify_password(password, user.password_hash)
            ):
                raise InvalidInputError(
                    "Sign in with the existing account password to accept this invitation."
                )

            membership = self._repository.membership(organization.id, user.id)
            if membership is None:
                self._repository.add_membership(
                    Membership(
                        organization_id=organization.id,
                        user_id=user.id,
                        role=invitation.role,
                    )
                )
            elif not membership.is_active:
                raise InvalidInputError("This organization membership is inactive.")
            invitation.accepted_at = now
            self._db.commit()
            self._db.refresh(user)
            return user
        except Exception:
            self._db.rollback()
            raise

    def login(self, organization_slug: str, email: str, password: str) -> tuple[str, str]:
        organization = self._repository.get_organization_by_slug(
            organization_slug.strip().lower()
        )
        user = self._repository.get_user_by_email(email.strip().lower())
        if (
            organization is None
            or not organization.is_active
            or user is None
            or not user.is_active
            or user.email_verified_at is None
            or not verify_password(password, user.password_hash)
        ):
            raise AuthenticationError("Invalid organization, email, or password.")
        membership = self._repository.membership(organization.id, user.id)
        if membership is None or not membership.is_active:
            raise AuthenticationError("Invalid organization, email, or password.")

        refresh_token = opaque_token()
        self._repository.add_refresh_session(
            RefreshSession(
                token_hash=token_digest(refresh_token),
                user_id=user.id,
                organization_id=organization.id,
                expires_at=datetime.now(timezone.utc) + REFRESH_LIFETIME,
            )
        )
        self._db.commit()
        return (
            self._access_token(user.id, organization.id, membership.role),
            refresh_token,
        )

    def refresh(self, token: str) -> tuple[str, str]:
        session = self._repository.get_refresh_session(token_digest(token))
        now = datetime.now(timezone.utc)
        expires_at = session.expires_at if session is not None else None
        if expires_at is not None and expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        if (
            session is None
            or session.revoked_at is not None
            or expires_at is None
            or expires_at <= now
        ):
            raise AuthenticationError("Refresh session is invalid or expired.")
        user = self._repository.get_user(session.user_id)
        organization = self._repository.get_organization(session.organization_id)
        membership = self._repository.membership(session.organization_id, session.user_id)
        if (
            user is None
            or not user.is_active
            or user.email_verified_at is None
            or organization is None
            or not organization.is_active
            or membership is None
            or not membership.is_active
        ):
            session.revoked_at = now
            self._db.commit()
            raise AuthenticationError("Refresh session is invalid or expired.")

        session.revoked_at = now
        new_token = opaque_token()
        self._repository.add_refresh_session(
            RefreshSession(
                token_hash=token_digest(new_token),
                user_id=user.id,
                organization_id=organization.id,
                expires_at=now + REFRESH_LIFETIME,
            )
        )
        access_token = self._access_token(
            user.id, organization.id, membership.role
        )
        self._db.commit()
        return access_token, new_token

    def logout(self, token: str | None) -> None:
        if not token:
            return
        session = self._repository.get_refresh_session(token_digest(token))
        if session is not None and session.revoked_at is None:
            session.revoked_at = datetime.now(timezone.utc)
            self._db.commit()

    def request_password_reset(self, organization_slug: str, email: str) -> None:
        if self._mailer is None:
            self._validate_mail_configuration()
        organization = self._repository.get_organization_by_slug(
            organization_slug.strip().lower()
        )
        user = self._repository.get_user_by_email(email.strip().lower())
        if organization is None or not organization.is_active or user is None:
            return
        membership = self._repository.membership(organization.id, user.id)
        if (
            membership is None
            or not membership.is_active
            or not user.is_active
            or user.email_verified_at is None
        ):
            return

        now = datetime.now(timezone.utc)
        raw_token = opaque_token()
        self._repository.invalidate_password_resets(user.id, organization.id, now)
        self._repository.add_password_reset(
            PasswordReset(
                token_hash=token_digest(raw_token),
                user_id=user.id,
                organization_id=organization.id,
                expires_at=now + PASSWORD_RESET_LIFETIME,
            )
        )
        base_url = os.getenv("PUBLIC_APP_URL", "http://localhost:5173").rstrip("/")
        reset_url = (
            f"{base_url}/?organization={organization.slug}"
            f"#password-reset-token={raw_token}"
        )
        try:
            if self._mailer is None:
                from .mailer import InvitationMailer

                mailer: InvitationSender = InvitationMailer()
            else:
                mailer = self._mailer
            mailer.send_password_reset(user.email, reset_url)
            self._db.commit()
        except Exception:
            self._db.rollback()
            raise

    def complete_password_reset(self, token: str, new_password: str) -> None:
        reset = self._repository.get_password_reset(token_digest(token))
        now = datetime.now(timezone.utc)
        expires_at = reset.expires_at if reset is not None else None
        if expires_at is not None and expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        if reset is None or reset.used_at is not None or expires_at is None or expires_at <= now:
            raise InvalidInputError("Password reset link is invalid or expired.")

        user = self._repository.get_user(reset.user_id)
        organization = self._repository.get_organization(reset.organization_id)
        membership = self._repository.membership(reset.organization_id, reset.user_id)
        if (
            user is None
            or not user.is_active
            or user.email_verified_at is None
            or organization is None
            or not organization.is_active
            or membership is None
            or not membership.is_active
        ):
            reset.used_at = now
            self._db.commit()
            raise InvalidInputError("Password reset link is invalid or expired.")

        user.password_hash = hash_password(new_password)
        reset.used_at = now
        self._repository.revoke_user_refresh_sessions(user.id, now)
        self._db.commit()

    def list_users(self, organization_id: int) -> list[tuple[Membership, User]]:
        return self._repository.list_memberships(organization_id)

    def get_user(self, user_id: int) -> User | None:
        return self._repository.get_user(user_id)

    def get_membership(
        self, organization_id: int, user_id: int
    ) -> Membership | None:
        return self._repository.membership(organization_id, user_id)

    def set_membership_active(
        self, organization_id: int, user_id: int, is_active: bool
    ) -> Membership:
        membership = self._repository.membership(organization_id, user_id)
        if membership is None:
            raise EntityNotFoundError("Organization member not found.")
        if membership.role == "admin" and is_active is False:
            active_admins = [
                item
                for item, _ in self._repository.list_memberships(organization_id)
                if item.role == "admin" and item.is_active
            ]
            if len(active_admins) <= 1:
                raise InvalidInputError("An organization must retain an active admin.")
        membership.is_active = is_active
        self._db.commit()
        return membership

    def _access_token(self, user_id: int, organization_id: int, role: str) -> str:
        from .security import create_access_token, jwt_secret

        return create_access_token(
            user_id=user_id,
            organization_id=organization_id,
            role=role,
            secret=jwt_secret(),
        )

    @staticmethod
    def _validate_slug(slug: str) -> None:
        if not re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,78}[a-z0-9])?", slug):
            raise InvalidInputError("Organization slug is invalid.")

    @staticmethod
    def _validate_mail_configuration() -> None:
        if not os.getenv("SMTP_HOST") or not os.getenv("SMTP_FROM"):
            raise InvalidInputError("Email delivery is not configured.")
