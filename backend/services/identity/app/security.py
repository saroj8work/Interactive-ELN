import hashlib
import hmac
import os
import secrets
import time
from dataclasses import dataclass

import jwt
from fastapi import Depends, HTTPException, Request, status

PASSWORD_ITERATIONS = 600_000
TOKEN_ISSUER = "interactive-eln-identity"
TOKEN_AUDIENCE = "interactive-eln-api"


def hash_password(password: str) -> str:
    if len(password) < 12 or len(password) > 128:
        raise ValueError("Password must be between 12 and 128 characters.")
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt, PASSWORD_ITERATIONS
    )
    return f"pbkdf2_sha256${PASSWORD_ITERATIONS}${salt.hex()}${digest.hex()}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, iterations, salt, expected = encoded.split("$", maxsplit=3)
        if algorithm != "pbkdf2_sha256":
            return False
        actual = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            bytes.fromhex(salt),
            int(iterations),
        )
        return hmac.compare_digest(actual, bytes.fromhex(expected))
    except (ValueError, TypeError):
        return False


def opaque_token() -> str:
    return secrets.token_urlsafe(48)


def token_digest(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def jwt_secret() -> bytes:
    secret = os.getenv("ELN_JWT_SECRET", "")
    if len(secret.encode("utf-8")) < 32:
        raise RuntimeError("ELN_JWT_SECRET must contain at least 32 bytes.")
    return secret.encode("utf-8")


def create_access_token(
    *,
    user_id: int,
    organization_id: int,
    role: str,
    secret: bytes,
    expires_in: int = 900,
) -> str:
    now = int(time.time())
    payload = {
        "iss": TOKEN_ISSUER,
        "aud": TOKEN_AUDIENCE,
        "sub": str(user_id),
        "org": organization_id,
        "role": role,
        "iat": now,
        "exp": now + expires_in,
    }
    return jwt.encode(payload, secret, algorithm="HS256", headers={"typ": "JWT"})


@dataclass(frozen=True)
class Principal:
    user_id: int
    organization_id: int
    role: str


def get_principal(request: Request) -> Principal:
    authorization = request.headers.get("Authorization", "")
    scheme, separator, token = authorization.partition(" ")
    if not separator or scheme.lower() != "bearer" or not token.strip():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication is required.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return decode_access_token(token.strip(), jwt_secret())


def require_admin(principal: Principal = Depends(get_principal)) -> Principal:
    if principal.role != "admin":
        raise HTTPException(status_code=403, detail="Organization admin role required.")
    return principal


def decode_access_token(token: str, secret: bytes) -> Principal:
    try:
        payload = jwt.decode(
            token,
            secret,
            algorithms=["HS256"],
            issuer=TOKEN_ISSUER,
            audience=TOKEN_AUDIENCE,
            options={
                "require": ["iss", "aud", "sub", "org", "role", "iat", "exp"]
            },
        )
        user_id = int(payload["sub"])
        organization_id = int(payload["org"])
        role = payload["role"]
        if user_id < 1 or organization_id < 1 or role not in {"admin", "member"}:
            raise ValueError("Invalid token claims.")
        return Principal(user_id, organization_id, role)
    except (
        jwt.PyJWTError,
        ValueError,
        TypeError,
        KeyError,
        OverflowError,
    ) as error:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired access token.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from error
