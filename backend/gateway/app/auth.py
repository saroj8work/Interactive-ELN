import httpx
from fastapi import HTTPException, Request, status

from services.identity.app.security import Principal, decode_access_token, jwt_secret


async def get_principal(request: Request) -> Principal:
    authorization = request.headers.get("Authorization", "")
    scheme, separator, token = authorization.partition(" ")
    if not separator or scheme.lower() != "bearer" or not token.strip():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication is required.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = token.strip()
    if not token.startswith("eln_live_"):
        return decode_access_token(token, jwt_secret())

    identity_url = request.app.state.settings.identity_service_url
    client: httpx.AsyncClient = request.app.state.identity_client
    try:
        response = await client.post(
            f"{identity_url}/auth/api-credentials/authenticate",
            headers={"Authorization": f"Bearer {token}"},
        )
    except httpx.HTTPError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="The identity service is currently unavailable.",
        ) from error
    if response.status_code == 401:
        raise HTTPException(status_code=401, detail="Invalid API credential.")
    if response.is_error:
        raise HTTPException(status_code=503, detail="Identity could not validate credentials.")
    try:
        claims = response.json()
        principal = Principal(
            user_id=int(claims["user_id"]),
            organization_id=int(claims["organization_id"]),
            role=str(claims["role"]),
            scopes=frozenset(claims["scopes"]),
        )
    except (ValueError, TypeError, KeyError) as error:
        raise HTTPException(status_code=503, detail="Identity returned invalid claims.") from error

    required_scope = "read" if request.method in {"GET", "HEAD", "OPTIONS"} else "write"
    if required_scope not in (principal.scopes or frozenset()):
        raise HTTPException(status_code=403, detail=f"API credential requires the {required_scope} scope.")
    return principal
