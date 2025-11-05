"""Simplified config validation helpers."""

from __future__ import annotations

from typing import Any


def string(value: Any) -> str:
    if not isinstance(value, str):
        raise ValueError("value must be a string")
    return value


def boolean(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        if value.lower() in {"true", "yes", "on", "1"}:
            return True
        if value.lower() in {"false", "no", "off", "0"}:
            return False
    raise ValueError("value must be boolean")
