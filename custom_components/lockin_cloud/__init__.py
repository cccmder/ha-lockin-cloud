"""The Lockin Cloud integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import LockinApi
from .const import CONF_ACCESS_TOKEN, CONF_DEVICE_UUID, DOMAIN
from .coordinator import LockinCoordinator

PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.BINARY_SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Lockin Cloud from a config entry."""
    api = LockinApi(async_get_clientsession(hass), entry.data[CONF_ACCESS_TOKEN])
    coordinator = LockinCoordinator(hass, api, entry.data[CONF_DEVICE_UUID])
    await coordinator.async_config_entry_first_refresh()

    _async_register_gateway(hass, entry, coordinator)

    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


def _async_register_gateway(
    hass: HomeAssistant, entry: ConfigEntry, coordinator: LockinCoordinator
) -> None:
    """Create the gateway device first so the lock can point at it."""
    gateway = coordinator.data.gateway
    if gateway is None:
        return

    device = dr.async_get(hass).async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, gateway.uuid)},
        name=gateway.name,
        manufacturer="Lockin",
        model=gateway.model,
        serial_number=gateway.serial or None,
    )
    coordinator.gateway_device_id = device.id
