"""Core constants used in tests."""

from __future__ import annotations

from enum import Enum

CONF_ACCESS_TOKEN = "access_token"
CONF_CLIENT_ID = "client_id"
CONF_COUNTRY_CODE = "country_code"
CONF_DESCRIPTION = "description"
CONF_ID = "id"
CONF_IP_ADDRESS = "ip_address"
CONF_MAC = "mac"
CONF_MODEL = "model"
CONF_NAME = "name"
CONF_PASSWORD = "password"
CONF_REGION = "region"
CONF_TIME_ZONE = "time_zone"
CONF_USERNAME = "username"
CONF_VACUUM = "vacuum"
PERCENTAGE = "%"
EVENT_HOMEASSISTANT_STOP = "event_homeassistant_stop"


class EntityCategory(Enum):
    DIAGNOSTIC = "diagnostic"


class Platform(Enum):
    VACUUM = "vacuum"
    SENSOR = "sensor"
