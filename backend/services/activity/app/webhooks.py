import asyncio
import hashlib
import hmac
import ipaddress
import json
import logging
import os
import socket
from datetime import datetime, timedelta, timezone
from urllib.parse import urlsplit

import httpx
from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import select

from eln_common.database import Database
from eln_common.errors import InvalidInputError, ServiceUnavailableError

from .models import WebhookDelivery, WebhookEndpoint


logger = logging.getLogger(__name__)
MAX_DELIVERY_ATTEMPTS = 10
DELIVERY_LEASE = timedelta(minutes=2)


def _fernet() -> Fernet:
    key = os.getenv("ELN_WEBHOOK_ENCRYPTION_KEY", "").strip()
    if not key:
        raise ServiceUnavailableError(
            "Webhook integrations require ELN_WEBHOOK_ENCRYPTION_KEY to be configured."
        )
    try:
        return Fernet(key.encode("ascii"))
    except (ValueError, UnicodeEncodeError) as error:
        raise ServiceUnavailableError(
            "ELN_WEBHOOK_ENCRYPTION_KEY must be a valid Fernet key."
        ) from error


def encrypt_secret(secret: str) -> str:
    return _fernet().encrypt(secret.encode()).decode("ascii")


def decrypt_secret(encrypted_secret: str) -> bytes:
    try:
        return _fernet().decrypt(encrypted_secret.encode("ascii"))
    except (InvalidToken, ValueError, UnicodeEncodeError) as error:
        raise ServiceUnavailableError(
            "Webhook signing secret cannot be decrypted; check ELN_WEBHOOK_ENCRYPTION_KEY."
        ) from error


def validate_webhook_destination(url: str) -> None:
    parsed = urlsplit(url)
    host = (parsed.hostname or "").rstrip(".").casefold()
    if parsed.scheme != "https" or not host or parsed.username or parsed.password:
        raise InvalidInputError("Webhook destinations must use HTTPS without embedded credentials.")
    if parsed.query or parsed.fragment:
        raise InvalidInputError("Webhook URLs cannot contain query parameters or fragments.")
    try:
        port = parsed.port or 443
    except ValueError as error:
        raise InvalidInputError("Webhook URL contains an invalid port.") from error

    allowlist = {
        item.strip().casefold().rstrip(".")
        for item in os.getenv("ELN_WEBHOOK_ALLOWED_HOSTS", "").split(",")
        if item.strip()
    }
    if allowlist and host not in allowlist:
        raise InvalidInputError("Webhook host is not included in ELN_WEBHOOK_ALLOWED_HOSTS.")
    if host == "localhost" or host.endswith((".localhost", ".local", ".internal")):
        raise InvalidInputError("Webhook destinations cannot use local or internal hostnames.")

    try:
        literal_ip = ipaddress.ip_address(host)
    except ValueError:
        try:
            addresses = {
                ipaddress.ip_address(item[4][0])
                for item in socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
            }
        except (OSError, ValueError) as error:
            raise InvalidInputError("Webhook host did not resolve to a public address.") from error
        if not addresses:
            raise InvalidInputError("Webhook host did not resolve to a public address.")
    else:
        addresses = {literal_ip}
    if any(not address.is_global for address in addresses):
        raise InvalidInputError("Webhook destinations must resolve only to public IP addresses.")


class WebhookDeliveryWorker:
    def __init__(self, database: Database, *, poll_interval: float = 2):
        self._database = database
        self._poll_interval = poll_interval
        self._stopping = asyncio.Event()

    def stop(self) -> None:
        self._stopping.set()

    async def run(self) -> None:
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(10),
            follow_redirects=False,
            trust_env=False,
            limits=httpx.Limits(max_connections=10, max_keepalive_connections=5),
        ) as client:
            while not self._stopping.is_set():
                await self._deliver_batch(client)
                try:
                    await asyncio.wait_for(self._stopping.wait(), timeout=self._poll_interval)
                except TimeoutError:
                    continue

    async def _deliver_batch(self, client: httpx.AsyncClient) -> None:
        now = datetime.now(timezone.utc)
        claimed: list[dict] = []
        try:
            with self._database.session() as db:
                rows = db.execute(
                    select(WebhookDelivery, WebhookEndpoint)
                    .join(WebhookEndpoint, WebhookEndpoint.id == WebhookDelivery.endpoint_id)
                    .where(
                        WebhookDelivery.delivered_at.is_(None),
                        WebhookDelivery.failed_at.is_(None),
                        WebhookDelivery.next_attempt_at <= now,
                        WebhookEndpoint.enabled.is_(True),
                        WebhookEndpoint.revoked_at.is_(None),
                    )
                    .order_by(WebhookDelivery.id)
                    .limit(10)
                    .with_for_update(skip_locked=True)
                ).all()
                for delivery, endpoint in rows:
                    delivery.attempts += 1
                    delivery.last_attempt_at = now
                    delivery.next_attempt_at = now + DELIVERY_LEASE
                    claimed.append({
                        "delivery_id": delivery.id,
                        "endpoint_id": endpoint.id,
                        "url": endpoint.url,
                        "encrypted_secret": endpoint.encrypted_secret,
                        "event_id": delivery.event_id,
                        "payload": delivery.payload,
                        "attempts": delivery.attempts,
                    })
                if claimed:
                    db.commit()
            for item in claimed:
                await self._deliver_one(client, item)
        except Exception:
            logger.exception("Could not process an external webhook delivery batch.")

    async def _deliver_one(self, client: httpx.AsyncClient, item: dict) -> None:
        error_message: str | None = None
        status_code: int | None = None
        try:
            await asyncio.to_thread(validate_webhook_destination, item["url"])
            secret = decrypt_secret(item["encrypted_secret"])
            body = json.dumps(
                item["payload"], ensure_ascii=False, separators=(",", ":"), sort_keys=True
            ).encode("utf-8")
            timestamp = str(int(datetime.now(timezone.utc).timestamp()))
            signature = hmac.new(
                secret, timestamp.encode("ascii") + b"." + body, hashlib.sha256
            ).hexdigest()
            async with client.stream(
                "POST",
                item["url"],
                content=body,
                headers={
                    "Content-Type": "application/json",
                    "User-Agent": "Interactive-ELN-Webhook/1.0",
                    "X-ELN-Event": item["payload"]["source_service"] + "." + item["payload"]["action"],
                    "X-ELN-Event-ID": item["event_id"],
                    "X-ELN-Delivery-ID": str(item["delivery_id"]),
                    "X-ELN-Timestamp": timestamp,
                    "X-ELN-Signature": f"sha256={signature}",
                },
            ) as response:
                status_code = response.status_code
            if not 200 <= status_code < 300:
                error_message = f"Endpoint returned HTTP {status_code}."
        except (httpx.HTTPError, InvalidInputError, ServiceUnavailableError, KeyError, TypeError) as error:
            error_message = str(error)[:500] or type(error).__name__
        except Exception as error:
            error_message = f"Delivery failed: {type(error).__name__}"[:500]

        with self._database.session() as db:
            delivery = db.get(WebhookDelivery, item["delivery_id"])
            if delivery is None or delivery.delivered_at is not None or delivery.failed_at is not None:
                return
            delivery.last_status_code = status_code
            delivery.last_error = error_message
            if error_message is None:
                delivery.delivered_at = datetime.now(timezone.utc)
                delivery.next_attempt_at = None
            elif delivery.attempts >= MAX_DELIVERY_ATTEMPTS:
                delivery.failed_at = datetime.now(timezone.utc)
                delivery.next_attempt_at = None
            else:
                delay = min(3600, 15 * (2 ** min(delivery.attempts - 1, 8)))
                delivery.next_attempt_at = datetime.now(timezone.utc) + timedelta(seconds=delay)
            db.commit()
