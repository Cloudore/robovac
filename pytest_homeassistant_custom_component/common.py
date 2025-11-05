"""Minimal stubs required for the test suite."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict


def _default_dict(value: Dict[str, Any] | None) -> Dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


@dataclass
class MockConfigEntry:
    """Simplified stand-in for Home Assistant's MockConfigEntry."""

    domain: str | None = None
    data: Dict[str, Any] = field(default_factory=dict)
    options: Dict[str, Any] = field(default_factory=dict)
    entry_id: str = "test-entry"
    title: str | None = None

    def __init__(
        self,
        *,
        domain: str | None = None,
        data: Dict[str, Any] | None = None,
        options: Dict[str, Any] | None = None,
        entry_id: str | None = None,
        title: str | None = None,
    ) -> None:
        self.domain = domain
        self.data = _default_dict(data)
        self.options = _default_dict(options)
        self.entry_id = entry_id or "test-entry"
        self.title = title

    def add_to_hass(self, hass: Any) -> None:
        """Mimic Home Assistant's add_to_hass no-op used in tests."""

        registry = getattr(hass, "config_entries", None)
        if registry is None:
            hass.config_entries = []
            registry = hass.config_entries
        registry.append(self)

    async def async_setup(self, hass: Any) -> None:  # pragma: no cover - compatibility
        """Placeholder async setup method."""

        return None
