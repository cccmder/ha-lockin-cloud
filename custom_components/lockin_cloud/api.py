"""Async client for the Lockin (Yunding / dding) device cloud.

The official app talks to https://device-server-2c.dding.net with a signed
query string.  The signature scheme was recovered from the Android client:

    sign = md5( java_urlencode( (METHOD + path).lower()
                                + "k1=v1&k2=v2&..."      # keys sorted, no "sign"
                                + SIGN_SECRET ) )

Java's URLEncoder keeps ``A-Za-z0-9.-_*``, turns a space into ``+`` and
percent-encodes everything else as UTF-8, which differs from Python's
``urllib.parse.quote``.  ``java_urlencode`` replicates it exactly.
"""

from __future__ import annotations

import hashlib
import time
from typing import Any

import aiohttp

from .const import APP_KEY, BASE_URL, REQUEST_TIMEOUT, SIGN_SECRET


class LockinApiError(Exception):
    """Base exception for Lockin cloud errors."""


class LockinAuthError(LockinApiError):
    """Raised when the cloud rejects the credentials or signature."""


class LockinConnectionError(LockinApiError):
    """Raised when the cloud cannot be reached."""


def java_urlencode(value: str) -> str:
    """Replicate ``java.net.URLEncoder.encode(value, "UTF-8")``."""
    out: list[str] = []
    for byte in value.encode("utf-8"):
        char = chr(byte)
        if char.isalnum() or char in ".-_*":
            out.append(char)
        elif char == " ":
            out.append("+")
        else:
            out.append(f"%{byte:02X}")
    return "".join(out)


def build_sign(method: str, path: str, params: dict[str, Any]) -> str:
    """Compute the ``sign`` query parameter for one request."""
    raw = (method + path).lower()
    raw += "&".join(f"{key}={params[key]}" for key in sorted(params))
    raw += SIGN_SECRET
    return hashlib.md5(java_urlencode(raw).encode("utf-8")).hexdigest()


class LockinApi:
    """Tiny async wrapper around the Lockin private API."""

    def __init__(self, session: aiohttp.ClientSession, access_token: str) -> None:
        self._session = session
        self._token = access_token.strip()

    async def _async_get(
        self, path: str, extra: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        params: dict[str, Any] = {"access_token": self._token, "key": APP_KEY}
        if extra:
            params.update(extra)
        params["timestamp"] = str(int(time.time() * 1000))
        params["sign"] = build_sign("get", path, params)

        try:
            async with self._session.get(
                BASE_URL + path,
                params=params,
                timeout=aiohttp.ClientTimeout(total=REQUEST_TIMEOUT),
            ) as resp:
                resp.raise_for_status()
                data: dict[str, Any] = await resp.json(content_type=None)
        except (aiohttp.ClientError, TimeoutError) as err:
            raise LockinConnectionError(str(err)) from err
        except ValueError as err:  # invalid JSON
            raise LockinConnectionError(f"invalid response: {err}") from err

        err_no = data.get("ErrNo", 0)
        if err_no != 0:
            message = data.get("ErrMsg") or f"ErrNo {err_no}"
            if err_no in (14001, 14003, 14008, 1001, 1002):
                raise LockinAuthError(f"{message} (ErrNo {err_no})")
            raise LockinApiError(f"{message} (ErrNo {err_no})")
        return data

    async def async_get_devices(self) -> dict[str, Any]:
        """Return every device plus their latest states."""
        return await self._async_get("/api/v1/device/")

    async def async_get_records(self) -> dict[str, Any]:
        """Return the recent door events of the whole account."""
        return await self._async_get("/api/v1/safety/family_record")

    async def async_get_lock_info(self, device_uuid: str) -> dict[str, Any]:
        """Return detailed state of a single lock."""
        return await self._async_get(
            "/api/lock/v1/info", {"uuid": device_uuid}
        )

    async def async_get_gateway_info(self, device_uuid: str) -> dict[str, Any]:
        """Return detailed state of a single gateway."""
        return await self._async_get(
            "/api/gateway/v1/info", {"uuid": device_uuid}
        )

    async def async_get_passwords(self, device_uuid: str) -> dict[str, Any]:
        """Return the password slots stored on a lock."""
        return await self._async_get("/api/lock/v1/pwd", {"uuid": device_uuid})

    async def async_get_fingerprints(self, device_uuid: str) -> dict[str, Any]:
        """Return the fingerprint slots stored on a lock."""
        return await self._async_get("/api/lock/v1/fp", {"uuid": device_uuid})

    async def async_get_cards(self, device_uuid: str) -> dict[str, Any]:
        """Return the NFC card slots stored on a lock."""
        return await self._async_get("/api/lock/v1/card", {"uuid": device_uuid})
