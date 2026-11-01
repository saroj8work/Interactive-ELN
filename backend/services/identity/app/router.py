import hmac
import os
from datetime import datetime, timezone
from urllib.parse import urlsplit
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response
from sqlalchemy.orm import Session

from eln_common.database import Database
from eln_common.errors import InvalidInputError

from .models import ApiCredential, CalendarFeed, Membership, Organization, User
from .repository import IdentityRepository
from .schemas import (
    ApiCredentialCreate,
    ApiCredentialCreated,
    ApiCredentialPrincipal,
    ApiCredentialRead,
    CalendarFeedAuthenticate,
    CalendarFeedCreated,
    CalendarFeedCreate,
    CalendarFeedPrincipal,
    CalendarFeedRead,
    CurrentUserRead,
    InvitationAccept,
    InvitationCreate,
    LoginRequest,
    OrganizationCreate,
    OrganizationRead,
    PasswordResetComplete,
    PasswordResetRequest,
    TokenResponse,
    UserRead,
    VerifyPasswordRequest,
)
from .security import (
    Principal,
    get_principal,
    opaque_token,
    require_admin,
    token_digest,
)
from .service import IdentityService, InvitationSender


def create_router(
    database: Database, mailer: InvitationSender | None = None
) -> APIRouter:
    router = APIRouter(prefix="/auth", tags=["identity"])

    def get_service(
        db: Annotated[Session, Depends(database.dependency)],
    ) -> IdentityService:
        return IdentityService(IdentityRepository(db), db, mailer=mailer)

    def credential_read(credential: ApiCredential) -> ApiCredentialRead:
        return ApiCredentialRead(
            id=credential.id,
            name=credential.name,
            token_prefix=credential.token_prefix,
            scopes=credential.scopes.split(","),
            created_at=credential.created_at,
            last_used_at=credential.last_used_at,
            revoked_at=credential.revoked_at,
        )

    def calendar_feed_read(feed: CalendarFeed) -> CalendarFeedRead:
        return CalendarFeedRead(
            id=feed.id,
            name=feed.name,
            token_prefix=feed.token_prefix,
            created_at=feed.created_at,
            last_used_at=feed.last_used_at,
            revoked_at=feed.revoked_at,
        )

    @router.post("/calendar-feeds", response_model=CalendarFeedCreated, status_code=201)
    def create_calendar_feed(
        payload: CalendarFeedCreate,
        principal: Annotated[Principal, Depends(get_principal)],
        db: Annotated[Session, Depends(database.dependency)],
    ) -> CalendarFeedCreated:
        name = payload.name.strip()
        if not name:
            raise InvalidInputError("Calendar feed name cannot be blank.")
        secret = f"eln_calendar_{opaque_token()}"
        feed = CalendarFeed(
            organization_id=principal.organization_id,
            user_id=principal.user_id,
            name=name,
            token_hash=token_digest(secret),
            token_prefix=secret[:24],
        )
        db.add(feed)
        db.commit()
        db.refresh(feed)
        return CalendarFeedCreated(**calendar_feed_read(feed).model_dump(), secret=secret)

    @router.get("/calendar-feeds", response_model=list[CalendarFeedRead])
    def list_calendar_feeds(
        principal: Annotated[Principal, Depends(get_principal)],
        db: Annotated[Session, Depends(database.dependency)],
    ) -> list[CalendarFeedRead]:
        records = (
            db.query(CalendarFeed)
            .filter(CalendarFeed.organization_id == principal.organization_id, CalendarFeed.user_id == principal.user_id)
            .order_by(CalendarFeed.id.desc())
            .all()
        )
        return [calendar_feed_read(feed) for feed in records]

    @router.delete("/calendar-feeds/{feed_id}", status_code=204)
    def revoke_calendar_feed(
        feed_id: int,
        principal: Annotated[Principal, Depends(get_principal)],
        db: Annotated[Session, Depends(database.dependency)],
    ) -> Response:
        feed = db.query(CalendarFeed).filter(
            CalendarFeed.id == feed_id,
            CalendarFeed.organization_id == principal.organization_id,
            CalendarFeed.user_id == principal.user_id,
        ).one_or_none()
        if feed is None:
            raise HTTPException(status_code=404, detail="Calendar feed not found.")
        if feed.revoked_at is None:
            feed.revoked_at = datetime.now(timezone.utc)
            db.commit()
        return Response(status_code=204)

    @router.post("/calendar-feeds/authenticate", response_model=CalendarFeedPrincipal)
    def authenticate_calendar_feed(
        payload: CalendarFeedAuthenticate,
        db: Annotated[Session, Depends(database.dependency)],
    ) -> CalendarFeedPrincipal:
        feed = db.query(CalendarFeed).filter(
            CalendarFeed.id == payload.feed_id,
            CalendarFeed.token_hash == token_digest(payload.secret),
            CalendarFeed.token_prefix == payload.secret[:24],
            CalendarFeed.revoked_at.is_(None),
        ).one_or_none()
        if feed is None:
            raise HTTPException(status_code=401, detail="Calendar feed is invalid or revoked.")
        user = db.get(User, feed.user_id)
        organization = db.get(Organization, feed.organization_id)
        membership = db.query(Membership).filter(
            Membership.user_id == feed.user_id,
            Membership.organization_id == feed.organization_id,
            Membership.is_active.is_(True),
        ).one_or_none()
        if user is None or not user.is_active or user.email_verified_at is None or organization is None or not organization.is_active or membership is None:
            raise HTTPException(status_code=401, detail="Calendar feed is invalid or revoked.")
        feed.last_used_at = datetime.now(timezone.utc)
        db.commit()
        return CalendarFeedPrincipal(feed_id=feed.id, user_id=feed.user_id, organization_id=feed.organization_id)

    @router.post("/api-credentials", response_model=ApiCredentialCreated, status_code=201)
    def create_api_credential(
        payload: ApiCredentialCreate,
        principal: Annotated[Principal, Depends(get_principal)],
        db: Annotated[Session, Depends(database.dependency)],
    ) -> ApiCredentialCreated:
        scopes = sorted(set(payload.scopes))
        if not scopes or len(scopes) != len(payload.scopes):
            raise InvalidInputError("Credential scopes must be unique.")
        name = payload.name.strip()
        if not name:
            raise InvalidInputError("Credential name cannot be blank.")
        secret = f"eln_live_{opaque_token()}"
        credential = ApiCredential(
            organization_id=principal.organization_id,
            user_id=principal.user_id,
            name=name,
            token_hash=token_digest(secret),
            token_prefix=secret[:16],
            scopes=",".join(scopes),
        )
        db.add(credential)
        db.commit()
        db.refresh(credential)
        return ApiCredentialCreated(
            **credential_read(credential).model_dump(), secret=secret
        )

    @router.get("/api-credentials", response_model=list[ApiCredentialRead])
    def list_api_credentials(
        principal: Annotated[Principal, Depends(get_principal)],
        db: Annotated[Session, Depends(database.dependency)],
    ) -> list[ApiCredentialRead]:
        records = (
            db.query(ApiCredential)
            .filter(
                ApiCredential.organization_id == principal.organization_id,
                ApiCredential.user_id == principal.user_id,
            )
            .order_by(ApiCredential.id.desc())
            .all()
        )
        return [credential_read(record) for record in records]

    @router.delete("/api-credentials/{credential_id}", status_code=204)
    def revoke_api_credential(
        credential_id: int,
        principal: Annotated[Principal, Depends(get_principal)],
        db: Annotated[Session, Depends(database.dependency)],
    ) -> Response:
        credential = (
            db.query(ApiCredential)
            .filter(
                ApiCredential.id == credential_id,
                ApiCredential.organization_id == principal.organization_id,
                ApiCredential.user_id == principal.user_id,
            )
            .one_or_none()
        )
        if credential is None:
            raise HTTPException(status_code=404, detail="API credential not found.")
        if not credential.is_revoked:
            credential.is_revoked = True
            credential.revoked_at = datetime.now(timezone.utc)
            db.commit()
        return Response(status_code=204)

    @router.post(
        "/api-credentials/{credential_id}/rotate",
        response_model=ApiCredentialCreated,
    )
    def rotate_api_credential(
        credential_id: int,
        principal: Annotated[Principal, Depends(get_principal)],
        db: Annotated[Session, Depends(database.dependency)],
    ) -> ApiCredentialCreated:
        credential = (
            db.query(ApiCredential)
            .filter(
                ApiCredential.id == credential_id,
                ApiCredential.organization_id == principal.organization_id,
                ApiCredential.user_id == principal.user_id,
                ApiCredential.is_revoked.is_(False),
            )
            .one_or_none()
        )
        if credential is None:
            raise HTTPException(status_code=404, detail="Active API credential not found.")
        secret = f"eln_live_{opaque_token()}"
        credential.token_hash = token_digest(secret)
        credential.token_prefix = secret[:16]
        credential.last_used_at = None
        db.commit()
        db.refresh(credential)
        return ApiCredentialCreated(
            **credential_read(credential).model_dump(), secret=secret
        )

    @router.post("/api-credentials/authenticate", response_model=ApiCredentialPrincipal)
    def authenticate_api_credential(
        authorization: Annotated[str | None, Header()] = None,
        db: Session = Depends(database.dependency),
    ) -> ApiCredentialPrincipal:
        scheme, separator, secret = (authorization or "").partition(" ")
        if (
            not separator
            or scheme.lower() != "bearer"
            or not secret.startswith("eln_live_")
        ):
            raise HTTPException(status_code=401, detail="Invalid API credential.")
        credential = (
            db.query(ApiCredential)
            .filter(
                ApiCredential.token_hash == token_digest(secret),
                ApiCredential.token_prefix == secret[:16],
                ApiCredential.is_revoked.is_(False),
            )
            .one_or_none()
        )
        if credential is None:
            raise HTTPException(status_code=401, detail="Invalid API credential.")
        user = db.get(User, credential.user_id)
        organization = db.get(Organization, credential.organization_id)
        membership = (
            db.query(Membership)
            .filter(
                Membership.user_id == credential.user_id,
                Membership.organization_id == credential.organization_id,
            )
            .one_or_none()
        )
        if (
            user is None
            or not user.is_active
            or user.email_verified_at is None
            or organization is None
            or not organization.is_active
            or membership is None
            or not membership.is_active
        ):
            raise HTTPException(status_code=401, detail="Invalid API credential.")
        credential.last_used_at = datetime.now(timezone.utc)
        db.commit()
        return ApiCredentialPrincipal(
            user_id=user.id,
            organization_id=organization.id,
            role=membership.role,
            scopes=credential.scopes.split(","),
        )

    @router.post("/bootstrap/organizations", response_model=OrganizationRead, status_code=201)
    def bootstrap_organization(
        payload: OrganizationCreate,
        service: Annotated[IdentityService, Depends(get_service)],
        bootstrap_token: Annotated[str | None, Header(alias="X-Bootstrap-Token")] = None,
    ) -> OrganizationRead:
        configured_token = os.getenv("ELN_BOOTSTRAP_TOKEN", "")
        if (
            len(configured_token) < 32
            or bootstrap_token is None
            or not hmac.compare_digest(bootstrap_token, configured_token)
        ):
            raise HTTPException(status_code=403, detail="Platform bootstrap is disabled.")
        organization, _ = service.bootstrap_organization(
            name=payload.name,
            slug=payload.slug,
            owner_email=str(payload.owner_email),
            owner_name=payload.owner_name,
        )
        return organization

    @router.post("/invitations/accept", status_code=204)
    def accept_invitation(
        payload: InvitationAccept,
        service: Annotated[IdentityService, Depends(get_service)],
    ) -> Response:
        service.accept_invitation(payload.token, payload.display_name, payload.password)
        return Response(status_code=204)

    @router.post("/password-reset/request", status_code=202)
    def request_password_reset(
        payload: PasswordResetRequest,
        service: Annotated[IdentityService, Depends(get_service)],
    ) -> dict[str, str]:
        service.request_password_reset(
            payload.organization_slug, str(payload.email)
        )
        return {
            "status": (
                "If the account is active, a password reset link will be sent."
            )
        }

    @router.post("/password-reset/complete", status_code=204)
    def complete_password_reset(
        payload: PasswordResetComplete,
        service: Annotated[IdentityService, Depends(get_service)],
    ) -> Response:
        service.complete_password_reset(payload.token, payload.new_password)
        return Response(status_code=204)

    @router.post("/login", response_model=TokenResponse)
    def login(
        payload: LoginRequest,
        response: Response,
        request: Request,
        service: Annotated[IdentityService, Depends(get_service)],
    ) -> TokenResponse:
        access_token, refresh_token = service.login(
            payload.organization_slug, str(payload.email), payload.password
        )
        response.set_cookie(
            key="eln_refresh",
            value=refresh_token,
            httponly=True,
            secure=_secure_cookies(request),
            samesite="strict",
            path="/auth",
            max_age=14 * 24 * 60 * 60,
        )
        return TokenResponse(access_token=access_token)

    @router.post("/refresh", response_model=TokenResponse)
    def refresh(
        request: Request,
        response: Response,
        service: Annotated[IdentityService, Depends(get_service)],
        refresh_token: Annotated[str | None, Header(alias="X-Refresh-Token")] = None,
    ) -> TokenResponse:
        _verify_browser_origin(request)
        token = request.cookies.get("eln_refresh") or refresh_token
        if token is None:
            raise InvalidInputError("Refresh session is required.")
        access_token, new_refresh_token = service.refresh(token)
        response.set_cookie(
            key="eln_refresh",
            value=new_refresh_token,
            httponly=True,
            secure=_secure_cookies(request),
            samesite="strict",
            path="/auth",
            max_age=14 * 24 * 60 * 60,
        )
        return TokenResponse(access_token=access_token)

    @router.post("/logout", status_code=204)
    def logout(
        request: Request,
        response: Response,
        service: Annotated[IdentityService, Depends(get_service)],
        refresh_token: Annotated[str | None, Header(alias="X-Refresh-Token")] = None,
    ) -> Response:
        _verify_browser_origin(request)
        service.logout(request.cookies.get("eln_refresh") or refresh_token)
        response.delete_cookie("eln_refresh", path="/auth", samesite="strict")
        response.status_code = 204
        return response

    @router.get("/me", response_model=CurrentUserRead)
    def current_user(
        principal: Annotated[Principal, Depends(get_principal)],
        service: Annotated[IdentityService, Depends(get_service)],
    ) -> CurrentUserRead:
        user = service.get_user(principal.user_id)
        membership = service.get_membership(principal.organization_id, principal.user_id)
        if (
            user is None
            or not user.is_active
            or user.email_verified_at is None
            or membership is None
            or not membership.is_active
        ):
            raise HTTPException(status_code=401, detail="Account is inactive.")
        return CurrentUserRead(
            id=user.id,
            email=user.email,
            display_name=user.display_name,
            organization_id=principal.organization_id,
            role=membership.role,
        )

    @router.post("/verify-password")
    def verify_password_endpoint(
        payload: VerifyPasswordRequest,
        principal: Annotated[Principal, Depends(get_principal)],
        service: Annotated[IdentityService, Depends(get_service)],
    ) -> dict[str, bool]:
        valid = service.verify_user_password(principal.user_id, payload.password)
        return {"valid": valid}

    @router.post("/admin/invitations", status_code=202)
    def create_invitation(
        payload: InvitationCreate,
        principal: Annotated[Principal, Depends(require_admin)],
        service: Annotated[IdentityService, Depends(get_service)],
    ) -> dict[str, str]:
        service.create_invitation(
            principal.organization_id,
            principal.user_id,
            str(payload.email),
            payload.role,
        )
        return {"status": "invitation_sent"}

    @router.get("/admin/users", response_model=list[UserRead])
    def list_users(
        principal: Annotated[Principal, Depends(require_admin)],
        service: Annotated[IdentityService, Depends(get_service)],
    ) -> list[UserRead]:
        return [
            UserRead(
                id=user.id,
                email=user.email,
                display_name=user.display_name,
                role=membership.role,
                is_active=membership.is_active and user.is_active,
                email_verified_at=user.email_verified_at,
                created_at=user.created_at,
            )
            for membership, user in service.list_users(principal.organization_id)
            if user.email_verified_at is not None
        ]

    @router.get("/users", response_model=list[UserRead])
    def list_organization_members(
        principal: Annotated[Principal, Depends(get_principal)],
        service: Annotated[IdentityService, Depends(get_service)],
    ) -> list[UserRead]:
        return [
            UserRead(
                id=user.id,
                email=user.email,
                display_name=user.display_name,
                role=membership.role,
                is_active=membership.is_active and user.is_active,
                email_verified_at=user.email_verified_at,
                created_at=user.created_at,
            )
            for membership, user in service.list_users(principal.organization_id)
            if user.email_verified_at is not None
            and membership.is_active
            and user.is_active
        ]

    @router.patch("/admin/users/{user_id}/active", response_model=UserRead)
    def set_user_active(
        user_id: int,
        is_active: bool,
        principal: Annotated[Principal, Depends(require_admin)],
        service: Annotated[IdentityService, Depends(get_service)],
    ) -> UserRead:
        if user_id == principal.user_id and not is_active:
            raise InvalidInputError("You cannot deactivate your own account.")
        membership: Membership = service.set_membership_active(
            principal.organization_id, user_id, is_active
        )
        user = service.get_user(user_id)
        if user is None or user.email_verified_at is None:
            raise InvalidInputError("User account is unavailable.")
        return UserRead(
            id=user.id,
            email=user.email,
            display_name=user.display_name,
            role=membership.role,
            is_active=membership.is_active and user.is_active,
            email_verified_at=user.email_verified_at,
            created_at=user.created_at,
        )

    return router


def _secure_cookies(request: Request) -> bool:
    return request.url.scheme == "https" or os.getenv("ELN_ENV") == "production"


def _verify_browser_origin(request: Request) -> None:
    origin = request.headers.get("Origin")
    public_origin = os.getenv("PUBLIC_APP_URL", "http://localhost:5173").rstrip("/")
    actual = urlsplit(origin) if origin else None
    expected = urlsplit(public_origin)
    if (
        actual is None
        or actual.scheme != expected.scheme
        or actual.netloc.lower() != expected.netloc.lower()
        or actual.path not in {"", "/"}
    ):
        raise HTTPException(status_code=403, detail="Request origin is not allowed.")
