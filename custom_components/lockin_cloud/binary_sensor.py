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
    """Set up the connectivity sensors."""
    coordinator: LockinCoordinator = entry.runtime_data
    entities: list[BinarySensorEntity] = [LockinOnlineSensor(coordinator)]
    if coordinator.data.gateway is not None:
        entities.append(LockinGatewayOnlineSensor(coordinator))
    async_add_entities(entities)


class LockinOnlineSensor(CoordinatorEntity[LockinCoordinator], BinarySensorEntity):
    """Cloud reported on/offline state of the lock."""

    _attr_has_entity_name = True
    _attr_translation_key = "online"
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY

    def __init__(self, coordinator: LockinCoordinator) -> None:
        super().__init__(coordinator)
        lock = coordinator.data.lock
        self._attr_unique_id = f"{lock.uuid}_{self._attr_translation_key}"
        info = DeviceInfo(
            identifiers={(DOMAIN, lock.uuid)},
            name=lock.name,
            manufacturer="Lockin",
            model=lock.model,
            serial_number=lock.serial or None,
        )
        if lock.gateway_uuid and coordinator.gateway_device_id:
            info["via_device_id"] = coordinator.gateway_device_id
        self._attr_device_info = info

    @property
    def is_on(self) -> bool:
        return self.coordinator.data.lock.online


class LockinGatewayOnlineSensor(
    CoordinatorEntity[LockinCoordinator], BinarySensorEntity
):
    """Cloud reported on/offline state of the gateway."""

    _attr_has_entity_name = True
    _attr_translation_key = "gateway_online"
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY

    def __init__(self, coordinator: LockinCoordinator) -> None:
        super().__init__(coordinator)
        gateway = coordinator.data.gateway
        self._attr_unique_id = f"{gateway.uuid}_{self._attr_translation_key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, gateway.uuid)},
            name=gateway.name,
            manufacturer="Lockin",
            model=gateway.model,
            serial_number=gateway.serial or None,
        )

    @property
    def is_on(self) -> bool:
        return bool(self.coordinator.data.gateway and self.coordinator.data.gateway.online)
