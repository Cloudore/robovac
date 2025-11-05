"""Home Assistant exception stubs."""


class HomeAssistantError(Exception):
    """Base error for stubbed Home Assistant."""


class ConfigEntryNotReady(HomeAssistantError):
    """Raised when config entry setup cannot proceed."""
