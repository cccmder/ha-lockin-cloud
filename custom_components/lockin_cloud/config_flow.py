"""Config flow for the Lockin Cloud integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import LockinApi, LockinApiError
from .const import CONF_ACCESS_TOKEN, CONF_DEVICE_UUID, DOMAIN

_LOGGER = logging.getLogger(__name__)


def _lock_devices(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Pick locks out of /api/v1/device/ (those exposing locker_status)."""
    locked_uuids = {
        state.get("uuid")
        for state in payload.get("states", [])
        if state.get("locker_status")
    }
    return [d for d in payload.get("devices", []) if d.get("uuid") in locked_uuids]


def _device_label(device: dict[str, Any]) -> str:
    settings = device.get("settings") or {}
    nickname = settings.get("nickname") or device.get("model") or "Lock"
    return f"{nickname} ({device.get('model') or 'unknown'})"


class LockinCloudConfigFlow(ConfigFlow, domain=DOMAIN):
    """Ask for an access token, then let the user pick a lock."""

    VERSION = 1

    def __init__(self) -> None:
        self._token: str = ""
        self._locks: list[dict[str, Any]] = []

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            token = user_input[CONF_ACCESS_TOKEN].strip()
            api = LockinApi(async_get_clientsession(self.hass), token)
            try:
                payload = await api.async_get_devices()
            except LockinApiError as err:
                _LOGGER.debug("token validation failed: %s", err)
                errors["base"] = "cannot_connect"
            else:
                locks = _lock_devices(payload)
                if not locks:
                    errors["base"] = "no_device"
                elif len(locks) == 1:
                    return await self._async_create_entry(token, locks[0])
                else:
                    self._token = token
                    self._locks = locks
                    return await self.async_step_device()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Required(CONF_ACCESS_TOKEN): str}),
            errors=errors,
        )

    async def async_step_device(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            chosen = user_input[CONF_DEVICE_UUID]
            lock = next(d for d in self._locks if d["uuid"] == chosen)
            return await self._async_create_entry(self._token, lock)

        options = {d["uuid"]: _device_label(d) for d in self._locks}
        return self.async_show_form(
            step_id="device",
            data_schema=vol.Schema({vol.Required(CONF_DEVICE_UUID): vol.In(options)}),
        )

    async def _async_create_entry(
        self, token: str, lock: dict[str, Any]
    ) -> ConfigFlowResult:
        await self.async_set_unique_id(lock["uuid"])
        self._abort_if_unique_id_configured()
        return self.async_create_entry(
            title=_device_label(lock).split(" (")[0],
            data={CONF_ACCESS_TOKEN: token, CONF_DEVICE_UUID: lock["uuid"]},
        )
