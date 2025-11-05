"""Device registry stubs."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Set, Tuple

CONNECTION_NETWORK_MAC = "mac"


@dataclass
class DeviceInfo:
    identifiers: Set[Tuple[str, str]]
    name: str | None = None
    manufacturer: str | None = None
    model: str | None = None
    connections: Set[Tuple[str, str]] = field(default_factory=set)
