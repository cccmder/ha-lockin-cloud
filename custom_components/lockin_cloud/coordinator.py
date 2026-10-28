"""Data coordinator for the Lockin Cloud integration."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .api import LockinApi, LockinApiError, LockinAuthError, LockinConnectionError
from .const import (
    AUX_REFRESH_INTERVAL,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    DOOR_STATE_MAP,
    OPEN_EVENT_IDS,
    SOURCE_METHOD,
)

_LOGGER = logging.getLogger(__name__)


@dataclass(slots=True)
class LockinGatewayData:
    """Parsed snapshot of one gateway."""

    uuid: str
    name: str
    model: str
    serial: str
    online: bool
    firmware: str | None
    ip: str | None
    child_count: int | None


@dataclass(slots=True)
class LockinLockData:
    """Parsed snapshot of one lock."""

    uuid: str
    name: str
    model: str
    serial: str
    online: bool
    battery: int | None
    signal: int | None
    door_state: str | None
    backlock: int | None
    last_event: str | None
    last_event_by: str | None
    last_event_method: str | None
    last_event_at: datetime | None
    last_event_id: int | None
    last_event_source: int | None
    gateway_uuid: str | None


@dataclass(slots=True)
class LockinData:
    """Everything one config entry exposes."""

    lock: LockinLockData
    gateway: LockinGatewayData | None = None
    key_index: dict[str, Any] = field(default_factory=dict)


def _hardware(device: dict[str, Any]) -> dict[str, Any]:
    """Return the hardware_info block of a device payload."""
    return device.get("hardware_info") or {}


def _method_for(
    source: Any, source_id: Any, key_index: dict[str, Any]
) -> str | None:
    """Best-effort label of the credential used to open the door."""
    if isinstance(source, int) and source in SOURCE_METHOD:
        return SOURCE_METHOD[source]
    if source_id is None:
        return None
    passwords = key_index.get("passwords") or {}
    if str(source_id) in passwords:
        return SOURCE_METHOD[1]
    if any(fp.get("id") == source_id for fp in key_index.get("fingerprints") or []):
        return SOURCE_METHOD[3]
    if any(card.get("id") == source_id for card in key_index.get("cards") or []):
        return SOURCE_METHOD[4]
    return None


def build_event_text(name: str | None, method: str | None) -> str | None:
    """Render a human readable door event, e.g. ``张三使用指纹开锁``."""
    if name and method:
        return f"{name}使用{method}开锁"
    if name:
        return f"{name}开锁"
    if method:
        return f"使用{method}开锁"
    return None


def _latest_record(
    records: dict[str, Any], device_uuid: str
) -> dict[str, Any] | None:
    """Newest door-open record of one lock (falls back to any record)."""
    mine = [
        record
        for record in records.get("family_record") or []
        if record.get("uuid") == device_uuid
    ]
    if not mine:
        return None
    opens = [record for record in mine if record.get("eventid") in OPEN_EVENT_IDS]
    pool = opens or mine
    return max(pool, key=lambda record: record.get("time") or 0)


def parse_lock(
    device_uuid: str,
    info: dict[str, Any],
    records: dict[str, Any],
    key_index: dict[str, Any] | None = None,
) -> LockinLockData:
    """Turn /api/lock/v1/info + /api/v1/safety/family_record replies into data."""
    device = info.get("device") or {}
    if not device:
        raise UpdateFailed(f"lock {device_uuid} returned no device payload")

    hardware = _hardware(device)
    locker = device.get("locker_status") or {}
    key_index = key_index or {}

    latest = _latest_record(records, device_uuid)
    detail = (latest or {}).get("detail") or {}
    event_ms = (latest or {}).get("time")

    name = detail.get("source_name") or detail.get("nickname")
    method = _method_for(detail.get("source"), detail.get("sourceid"), key_index)

    return LockinLockData(
        uuid=device_uuid,
        name=device.get("nickname") or device.get("model") or "Lock",
        model=device.get("model") or "unknown",
        serial=hardware.get("sn") or "",
        online=device.get("onoff_line") == 1,
        battery=device.get("power"),
        signal=device.get("lqi"),
        door_state=DOOR_STATE_MAP.get(locker.get("doorstate")),
        backlock=locker.get("backlock"),
        last_event=build_event_text(name, method),
        last_event_by=name,
        last_event_method=method,
        last_event_at=dt_util.utc_from_timestamp(event_ms / 1000) if event_ms else None,
        last_event_id=(latest or {}).get("eventid"),
        last_event_source=detail.get("source"),
        gateway_uuid=device.get("parent") or None,
    )


def parse_gateway(
    device_uuid: str,
    info: dict[str, Any],
    topology: dict[str, str] | None,
) -> LockinGatewayData:
    """Turn /api/gateway/v1/info into data."""
    device = info.get("device") or {}
    hardware = _hardware(device)
    versions = hardware.get("versions") or {}

    child_count: int | None = None
    if topology:
        child_count = sum(
            1 for child, parent in topology.items()
            if parent == device_uuid and child != device_uuid
        )

    return LockinGatewayData(
        uuid=device_uuid,
        name=device.get("nickname") or device.get("name") or device.get("model") or "Gateway",
        model=device.get("model") or "unknown",
        serial=hardware.get("sn") or "",
        online=device.get("onoff_line") == 1,
        firmware=versions.get("app_version"),
        ip=device.get("sourceip") or None,
        child_count=child_count,
    )


class LockinCoordinator(DataUpdateCoordinator[LockinData]):
    """Poll the Lockin cloud for one lock and its gateway."""

    def __init__(self, hass: HomeAssistant, api: LockinApi, device_uuid: str) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}:{device_uuid[:8]}",
            update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL),
        )
        self.api = api
        self.device_uuid = device_uuid
        self.gateway_device_id: str | None = None
        self._key_index: dict[str, Any] = {}
        self._topology: dict[str, str] = {}
        self._aux_refreshed_at: datetime | None = None

    async def _async_refresh_aux(self) -> None:
        """Refresh key lists and account topology, at most every ~10 minutes."""
        now = dt_util.utcnow()
        if self._aux_refreshed_at is not None and (
            now - self._aux_refreshed_at
        ) < timedelta(seconds=AUX_REFRESH_INTERVAL):
            return

        try:
            passwords = await self.api.async_get_passwords(self.device_uuid)
            fingerprints = await self.api.async_get_fingerprints(self.device_uuid)
            cards = await self.api.async_get_cards(self.device_uuid)
            devices = await self.api.async_get_devices()
        except LockinApiError as err:
            # Portal data is only used for cosmetics; never fail a cycle on it.
            _LOGGER.debug("auxiliary refresh failed, keeping stale data: %s", err)
            self._aux_refreshed_at = now
            return

        self._key_index = {
            "passwords": passwords.get("passwords") or {},
            "fingerprints": fingerprints.get("fingerprints") or [],
            "cards": cards.get("cards") or [],
        }
        self._topology = {
            state.get("uuid"): state.get("parent")
            for state in devices.get("states") or []
            if state.get("uuid")
        }
        self._aux_refreshed_at = now

    async def _async_update_data(self) -> LockinData:
        try:
            info = await self.api.async_get_lock_info(self.device_uuid)
        except LockinAuthError as err:
            raise UpdateFailed(f"credentials rejected: {err}") from err
        except LockinConnectionError as err:
            raise UpdateFailed(f"cannot reach Lockin cloud: {err}") from err
        except LockinApiError as err:
            raise UpdateFailed(str(err)) from err

        await self._async_refresh_aux()

        try:
            records = await self.api.async_get_records()
        except LockinConnectionError as err:
            raise UpdateFailed(f"cannot reach Lockin cloud: {err}") from err
        except LockinApiError as err:
            raise UpdateFailed(str(err)) from err

        lock = parse_lock(self.device_uuid, info, records, self._key_index)

        gateway: LockinGatewayData | None = None
        if lock.gateway_uuid and lock.gateway_uuid != self.device_uuid:
            try:
                gateway_info = await self.api.async_get_gateway_info(lock.gateway_uuid)
            except LockinApiError as err:
                _LOGGER.debug("gateway %s unavailable: %s", lock.gateway_uuid, err)
            else:
                gateway = parse_gateway(lock.gateway_uuid, gateway_info, self._topology)

        return LockinData(lock=lock, gateway=gateway, key_index=self._key_index)
