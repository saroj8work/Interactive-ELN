import hmac
import os
from urllib.parse import urlsplit
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response
from sqlalchemy.orm import Session

from eln_common.database import Database
from eln_common.errors import InvalidInputError

from .models import Membership, User
from .repository import IdentityRepository
from .schemas import (
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
)
from .security import Principal, get_principal, require_admin
from .service import IdentityService, InvitationSender


def create_router(
    database: Database, mailer: InvitationSender | None = None
) -> APIRouter:
    router = APIRouter(prefix="/auth", tags=["identity"])

    def get_service(db: Annotated[Session, Depends(database.dependency)]) -> IdentityService:
        return IdentityService(IdentityRepository(db), db, mailer=mailer)

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
