"""Binary sensor platform for the Lockin Cloud integration."""

from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import LockinCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the connectivity sensor."""
    coordinator: LockinCoordinator = entry.runtime_data
    async_add_entities([LockinOnlineSensor(coordinator)])


class LockinOnlineSensor(CoordinatorEntity[LockinCoordinator], BinarySensorEntity):
    """Cloud reported on/offline state of the lock."""

    _attr_has_entity_name = True
    _attr_translation_key = "online"
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY

    def __init__(self, coordinator: LockinCoordinator) -> None:
        super().__init__(coordinator)
        data = coordinator.data
        self._attr_unique_id = f"{data.uuid}_{self._attr_translation_key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, data.uuid)},
            name=data.name,
            manufacturer="Lockin",
            model=data.model,
            serial_number=data.serial or None,
        )

    @property
    def is_on(self) -> bool:
        return self.coordinator.data.online
