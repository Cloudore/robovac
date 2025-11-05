"""Minimal vacuum component stubs for testing."""

from __future__ import annotations

from enum import Enum, IntFlag, auto
from typing import Any


class VacuumActivity(Enum):
    CLEANING = "cleaning"
    DOCKED = "docked"
    PAUSED = "paused"
    IDLE = "idle"
    ERROR = "error"
    RETURNING = "returning"


class VacuumEntityFeature(IntFlag):
    NONE = 0
    BATTERY = auto()
    CLEAN_SPOT = auto()
    FAN_SPEED = auto()
    LOCATE = auto()
    PAUSE = auto()
    RETURN_HOME = auto()
    SEND_COMMAND = auto()
    START = auto()
    STATE = auto()
    STOP = auto()
    MAP = auto()


class StateVacuumEntity:
    """Very small subset of the Home Assistant vacuum entity."""

    _attr_supported_features: VacuumEntityFeature = VacuumEntityFeature.NONE
    _attr_should_poll = False

    def __init__(self) -> None:
        self._attr_supported_features = VacuumEntityFeature.NONE
        self._attr_name: str | None = None
        self._attr_unique_id: str | None = None
        self._attr_ip_address: str | None = None
        self._attr_access_token: str | None = None
        self._attr_model_code: str | None = None

    @property
    def supported_features(self) -> VacuumEntityFeature:
        return self._attr_supported_features

    @property
    def unique_id(self) -> str | None:
        return self._attr_unique_id

    @property
    def name(self) -> str | None:
        return self._attr_name

    @property
    def ip_address(self) -> str | None:
        return self._attr_ip_address

    @property
    def access_token(self) -> str | None:
        return self._attr_access_token

    @property
    def model_code(self) -> str | None:
        return self._attr_model_code

    @property
    def fan_speed(self) -> str | None:
        return getattr(self, "_attr_fan_speed", None)

    def async_write_ha_state(self) -> None:  # pragma: no cover - noop for tests
        return None

    async def async_update(self) -> None:  # pragma: no cover - noop for tests
        return None

    async def async_added_to_hass(self) -> None:  # pragma: no cover - optional hook
        return None
