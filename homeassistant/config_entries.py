"""Minimal config entries stubs."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional

ConfigFlowResult = Dict[str, Any]


@dataclass
class ConfigEntry:
    domain: str
    data: Dict[str, Any] = field(default_factory=dict)
    options: Dict[str, Any] = field(default_factory=dict)
    entry_id: str = "test-entry"


class ConfigFlow:
    """Simplified ConfigFlow base class."""

    def __init__(self) -> None:
        self._unique_id: Optional[str] = None
        self.hass: Any = None

    async def async_set_unique_id(self, unique_id: str) -> None:
        self._unique_id = unique_id

    async def async_show_form(self, *, step_id: str, data_schema: Any | None = None, errors: Dict[str, str] | None = None) -> ConfigFlowResult:
        return {"type": "form", "step_id": step_id, "errors": errors or {}, "data_schema": data_schema}

    async def async_create_entry(self, *, title: str, data: Dict[str, Any]) -> ConfigFlowResult:
        return {"type": "create_entry", "title": title, "data": data}


class OptionsFlow:
    """Simplified OptionsFlow base class."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        self.config_entry = config_entry

    async def async_create_entry(self, *, title: str, data: Dict[str, Any]) -> ConfigFlowResult:
        return {"type": "create_entry", "title": title, "data": data}
