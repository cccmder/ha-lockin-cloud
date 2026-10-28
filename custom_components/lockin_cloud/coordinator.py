"""Data coordinator for the Lockin Cloud integration."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .api import LockinApi, LockinApiError, LockinAuthError, LockinConnectionError
from .const import DEFAULT_SCAN_INTERVAL, DOMAIN, DOOR_STATE_MAP

_LOGGER = logging.getLogger(__name__)


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
    last_event_by: str | None
    last_event_at: datetime | None
    last_event_id: int | None
    last_event_source: int | None


def parse_lock(
    device_uuid: str, info: dict[str, Any], records: dict[str, Any]
) -> LockinLockData:
    """Turn /api/lock/v1/info + /api/v1/safety/family_record replies into data."""
    device = info.get("device") or {}
    if not device:
        raise UpdateFailed(f"lock {device_uuid} returned no device payload")

    locker = device.get("locker_status") or {}

    latest: dict[str, Any] | None = None
    for record in records.get("family_record") or []:
        if record.get("uuid") != device_uuid:
            continue
        if latest is None or record.get("time", 0) > latest.get("time", 0):
            latest = record

    detail = (latest or {}).get("detail") or {}
    event_ms = (latest or {}).get("time")
    return LockinLockData(
        uuid=device_uuid,
        name=device.get("nickname") or device.get("model") or "Lock",
        model=device.get("model") or "unknown",
        serial=device.get("sn") or "",
        online=device.get("onoff_line") == 1,
        battery=device.get("power"),
        signal=device.get("lqi"),
        door_state=DOOR_STATE_MAP.get(locker.get("doorstate")),
        backlock=locker.get("backlock"),
        last_event_by=detail.get("source_name") or detail.get("nickname"),
        last_event_at=dt_util.utc_from_timestamp(event_ms / 1000) if event_ms else None,
        last_event_id=(latest or {}).get("eventid"),
        last_event_source=detail.get("source"),
    )


class LockinCoordinator(DataUpdateCoordinator[LockinLockData]):
    """Poll the Lockin cloud for one lock."""

    def __init__(self, hass: HomeAssistant, api: LockinApi, device_uuid: str) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}:{device_uuid[:8]}",
            update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL),
        )
        self.api = api
        self.device_uuid = device_uuid

    async def _async_update_data(self) -> LockinLockData:
        try:
            info = await self.api.async_get_lock_info(self.device_uuid)
            records = await self.api.async_get_records()
        except LockinAuthError as err:
            raise UpdateFailed(f"credentials rejected: {err}") from err
        except LockinConnectionError as err:
            raise UpdateFailed(f"cannot reach Lockin cloud: {err}") from err
        except LockinApiError as err:
            raise UpdateFailed(str(err)) from err
        return parse_lock(self.device_uuid, info, records)
