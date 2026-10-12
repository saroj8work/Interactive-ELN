import logging
from typing import TypeVar, cast

import httpx
from pydantic import TypeAdapter, ValidationError

from eln_common.config import GatewaySettings, ServiceName
from eln_common.errors import DownstreamServiceError, ServiceUnavailableError

logger = logging.getLogger(__name__)
ResponseT = TypeVar("ResponseT")


class ServiceClient:
    def __init__(
        self,
        settings: GatewaySettings,
        client: httpx.AsyncClient | None = None,
    ):
        self._settings = settings
        self._client = client or httpx.AsyncClient(timeout=10)

    async def close(self) -> None:
        await self._client.aclose()

    async def get(
        self,
        service: ServiceName,
        path: str,
        adapter: TypeAdapter[ResponseT],
        *,
        organization_id: int,
        user_id: int | None = None,
        organization_role: str | None = None,
    ) -> ResponseT:
        return await self._request(
            "GET",
            service,
            path,
            adapter,
            organization_id=organization_id,
            user_id=user_id,
            organization_role=organization_role,
        )

    async def post(
        self,
        service: ServiceName,
        path: str,
        payload: dict,
        adapter: TypeAdapter[ResponseT],
        *,
        organization_id: int,
        user_id: int | None = None,
        organization_role: str | None = None,
    ) -> ResponseT:
        return await self._request(
            "POST",
            service,
            path,
            adapter,
            organization_id=organization_id,
            user_id=user_id,
            organization_role=organization_role,
            json=payload,
        )

    async def put(
        self,
        service: ServiceName,
        path: str,
        payload: dict,
        adapter: TypeAdapter[ResponseT],
        *,
        organization_id: int,
        user_id: int | None = None,
        organization_role: str | None = None,
    ) -> ResponseT:
        return await self._request(
            "PUT",
            service,
            path,
            adapter,
            organization_id=organization_id,
            user_id=user_id,
            organization_role=organization_role,
            json=payload,
        )

    async def patch(
        self,
        service: ServiceName,
        path: str,
        payload: dict,
        adapter: TypeAdapter[ResponseT],
        *,
        organization_id: int,
        user_id: int | None = None,
        organization_role: str | None = None,
    ) -> ResponseT:
        return await self._request(
            "PATCH",
            service,
            path,
            adapter,
            organization_id=organization_id,
            user_id=user_id,
            organization_role=organization_role,
            json=payload,
        )

    async def delete(
        self,
        service: ServiceName,
        path: str,
        adapter: TypeAdapter[ResponseT],
        *,
        organization_id: int,
        user_id: int,
        organization_role: str,
    ) -> ResponseT:
        return await self._request(
            "DELETE",
            service,
            path,
            adapter,
            organization_id=organization_id,
            user_id=user_id,
            organization_role=organization_role,
        )

    async def post_bytes(
        self,
        service: ServiceName,
        path: str,
        content: bytes,
        adapter: TypeAdapter[ResponseT],
        *,
        organization_id: int,
        user_id: int,
        content_type: str,
    ) -> ResponseT:
        return await self._request(
            "POST",
            service,
            path,
            adapter,
            organization_id=organization_id,
            user_id=user_id,
            content_type=content_type,
            content=content,
        )

    async def get_bytes(
        self,
        service: ServiceName,
        path: str,
        *,
        organization_id: int,
    ) -> bytes:
        return await self._request_bytes(
            "GET", service, path, organization_id=organization_id
        )

    async def _request_bytes(
        self,
        method: str,
        service: ServiceName,
        path: str,
        *,
        organization_id: int,
        user_id: int | None = None,
        content_type: str | None = None,
        content: bytes | None = None,
    ) -> bytes:
        headers = {"X-Organization-ID": str(organization_id)}
        if user_id is not None:
            headers["X-User-ID"] = str(user_id)
        if content_type is not None:
            headers["Content-Type"] = content_type
        try:
            response = await self._client.request(
                method,
                f"{self._settings.url_for(service)}{path}",
                headers=headers,
                content=content,
            )
        except httpx.HTTPError as error:
            logger.exception("Gateway request to %s service failed.", service)
            raise ServiceUnavailableError(
                f"The {service} service is currently unavailable."
            ) from error
        if response.is_error:
            try:
                detail = response.json().get("detail", response.text)
            except (ValueError, AttributeError):
                detail = response.text
            raise DownstreamServiceError(response.status_code, str(detail))
        return response.content

    async def _request(
        self,
        method: str,
        service: ServiceName,
        path: str,
        adapter: TypeAdapter[ResponseT],
        *,
        organization_id: int,
        user_id: int | None = None,
        organization_role: str | None = None,
        json: dict | None = None,
        content: bytes | None = None,
        content_type: str | None = None,
    ) -> ResponseT:
        headers = {"X-Organization-ID": str(organization_id)}
        if user_id is not None:
            headers["X-User-ID"] = str(user_id)
        if organization_role is not None:
            headers["X-Organization-Role"] = organization_role
        if content_type is not None:
            headers["Content-Type"] = content_type
        try:
            response = await self._client.request(
                method,
                f"{self._settings.url_for(service)}{path}",
                json=json,
                content=content,
                headers=headers,
            )
        except httpx.HTTPError as error:
            logger.exception("Gateway request to %s service failed.", service)
            raise ServiceUnavailableError(
                f"The {service} service is currently unavailable."
            ) from error
        if response.is_error:
            try:
                detail = response.json().get("detail", response.text)
            except (ValueError, AttributeError):
                detail = response.text
            raise DownstreamServiceError(response.status_code, str(detail))
        if response.status_code == 204:
            return cast(ResponseT, None)
        try:
            return adapter.validate_python(response.json())
        except (ValueError, ValidationError) as error:
            logger.exception(
                "The %s service response failed JSON parsing or contract validation.",
                service,
            )
            raise ServiceUnavailableError(
                f"The {service} service returned an invalid response."
            ) from error
