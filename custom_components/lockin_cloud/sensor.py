"""Sensor platform for the Lockin Cloud integration."""

from __future__ import annotations

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import LockinCoordinator, LockinGatewayData, LockinLockData


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Lockin sensors from a config entry."""
    coordinator: LockinCoordinator = entry.runtime_data

    entities: list[SensorEntity] = [
        LockinDoorStateSensor(coordinator),
        LockinBatterySensor(coordinator),
        LockinSignalSensor(coordinator),
        LockinLastEventSensor(coordinator),
        LockinLastEventTimeSensor(coordinator),
    ]
    if coordinator.data.gateway is not None:
        entities.extend(
            [
                LockinGatewayFirmwareSensor(coordinator),
                LockinGatewayLinkedDevicesSensor(coordinator),
                LockinGatewayIpSensor(coordinator),
            ]
        )
    async_add_entities(entities)


class LockinLockSensor(CoordinatorEntity[LockinCoordinator], SensorEntity):
    """Common device metadata for every entity of one lock."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: LockinCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{self.lock.uuid}_{self._attr_translation_key}"
        info = DeviceInfo(
            identifiers={(DOMAIN, self.lock.uuid)},
            name=self.lock.name,
            manufacturer="Lockin",
            model=self.lock.model,
            serial_number=self.lock.serial or None,
        )
        if self.lock.gateway_uuid and coordinator.gateway_device_id:
            info["via_device_id"] = coordinator.gateway_device_id
        self._attr_device_info = info

    @property
    def lock(self) -> LockinLockData:
        """Lock snapshot of the current cycle."""
        return self.coordinator.data.lock


class LockinGatewaySensor(CoordinatorEntity[LockinCoordinator], SensorEntity):
    """Common device metadata for every entity of one gateway."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: LockinCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{self.gateway.uuid}_{self._attr_translation_key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self.gateway.uuid)},
            name=self.gateway.name,
            manufacturer="Lockin",
            model=self.gateway.model,
            serial_number=self.gateway.serial or None,
        )

    @property
    def gateway(self) -> LockinGatewayData:
        """Gateway snapshot of the current cycle."""
        return self.coordinator.data.gateway


class LockinDoorStateSensor(LockinLockSensor):
    """Whether the door is open or closed."""

    _attr_translation_key = "door_state"
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = ["open", "closed"]

    @property
    def native_value(self) -> str | None:
        return self.lock.door_state

    @property
    def icon(self) -> str:
        return "mdi:door-open" if self.lock.door_state == "open" else "mdi:door-closed"


class LockinBatterySensor(LockinLockSensor):
    """Battery level reported by the lock."""

    _attr_translation_key = "battery"
    _attr_device_class = SensorDeviceClass.BATTERY
    _attr_native_unit_of_measurement = "%"
    _attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def native_value(self) -> int | None:
        return self.lock.battery


class LockinSignalSensor(LockinLockSensor):
    """Radio link quality (lqi)."""

    _attr_translation_key = "signal"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:signal"

    @property
    def native_value(self) -> int | None:
        return self.lock.signal


class LockinLastEventSensor(LockinLockSensor):
    """Who opened the door last, and how."""

    _attr_translation_key = "last_event"
    _attr_icon = "mdi:account-clock"

    @property
    def native_value(self) -> str | None:
        return self.lock.last_event

    @property
    def extra_state_attributes(self) -> dict[str, object]:
        data = self.lock
        return {
            "who": data.last_event_by,
            "method": data.last_event_method,
            "event_id": data.last_event_id,
            "source": data.last_event_source,
            "occurred_at": data.last_event_at.isoformat() if data.last_event_at else None,
        }


class LockinLastEventTimeSensor(LockinLockSensor):
    """Timestamp of the most recent door event."""

    _attr_translation_key = "last_event_time"
    _attr_device_class = SensorDeviceClass.TIMESTAMP

    @property
    def native_value(self):
        return self.lock.last_event_at


class LockinGatewayFirmwareSensor(LockinGatewaySensor):
    """Firmware version reported by the gateway."""

    _attr_translation_key = "gateway_firmware"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = "mdi:chip"

    @property
    def native_value(self) -> str | None:
        return self.gateway.firmware


class LockinGatewayLinkedDevicesSensor(LockinGatewaySensor):
    """How many devices are paired with the gateway."""

    _attr_translation_key = "gateway_linked_devices"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = "devices"
    _attr_icon = "mdi:lock-multiple"

    @property
    def native_value(self) -> int | None:
        return self.gateway.child_count


class LockinGatewayIpSensor(LockinGatewaySensor):
    """Public IP the gateway last reported from."""

    _attr_translation_key = "gateway_ip"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_entity_registry_enabled_default = False
    _attr_icon = "mdi:ip-network"

    @property
    def native_value(self) -> str | None:
        return self.gateway.ip
