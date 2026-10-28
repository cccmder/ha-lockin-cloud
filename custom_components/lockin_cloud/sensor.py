"""Sensor platform for the Lockin Cloud integration."""

from __future__ import annotations

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
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
    """Set up Lockin sensors from a config entry."""
    coordinator: LockinCoordinator = entry.runtime_data
    async_add_entities(
        [
            LockinDoorStateSensor(coordinator),
            LockinBatterySensor(coordinator),
            LockinSignalSensor(coordinator),
            LockinLastEventSensor(coordinator),
            LockinLastEventTimeSensor(coordinator),
        ]
    )


class LockinBaseSensor(CoordinatorEntity[LockinCoordinator], SensorEntity):
    """Common device metadata for every entity of one lock."""

    _attr_has_entity_name = True

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


class LockinDoorStateSensor(LockinBaseSensor):
    """Whether the door is open or closed."""

    _attr_translation_key = "door_state"
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = ["open", "closed"]

    @property
    def native_value(self) -> str | None:
        return self.coordinator.data.door_state

    @property
    def icon(self) -> str:
        return "mdi:door-open" if self.coordinator.data.door_state == "open" else "mdi:door-closed"


class LockinBatterySensor(LockinBaseSensor):
    """Battery level reported by the lock."""

    _attr_translation_key = "battery"
    _attr_device_class = SensorDeviceClass.BATTERY
    _attr_native_unit_of_measurement = "%"
    _attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def native_value(self) -> int | None:
        return self.coordinator.data.battery


class LockinSignalSensor(LockinBaseSensor):
    """Radio link quality (lqi)."""

    _attr_translation_key = "signal"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:signal"

    @property
    def native_value(self) -> int | None:
        return self.coordinator.data.signal


class LockinLastEventSensor(LockinBaseSensor):
    """Who opened the door last, and how."""

    _attr_translation_key = "last_event"
    _attr_icon = "mdi:account-clock"

    @property
    def native_value(self) -> str | None:
        return self.coordinator.data.last_event_by

    @property
    def extra_state_attributes(self) -> dict[str, object]:
        data = self.coordinator.data
        return {
            "event_id": data.last_event_id,
            "source": data.last_event_source,
            "occurred_at": data.last_event_at.isoformat() if data.last_event_at else None,
        }


class LockinLastEventTimeSensor(LockinBaseSensor):
    """Timestamp of the most recent door event."""

    _attr_translation_key = "last_event_time"
    _attr_device_class = SensorDeviceClass.TIMESTAMP

    @property
    def native_value(self):
        return self.coordinator.data.last_event_at
