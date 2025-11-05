"""Minimal sensor component stubs for testing."""

from __future__ import annotations

from enum import Enum


class SensorDeviceClass(Enum):
    BATTERY = "battery"


class SensorEntity:
    """Very small subset of the Home Assistant sensor entity."""

    _attr_has_entity_name = False
    _attr_device_class: SensorDeviceClass | None = None
    _attr_entity_category = None
    _attr_native_unit_of_measurement: str | None = None
    _attr_should_poll: bool = True
    _attr_native_value = None
    _attr_available: bool = True

    async def async_update(self) -> None:  # pragma: no cover - noop for tests
        return None

    @property
    def native_value(self):  # pragma: no cover - simple passthrough
        return self._attr_native_value
