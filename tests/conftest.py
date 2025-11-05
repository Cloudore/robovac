"""Test fixtures for RoboVac integration tests."""

import asyncio
import os
import sys
import pytest
from unittest.mock import MagicMock, patch, AsyncMock

# Add the project root directory to the Python path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

# Import from pytest_homeassistant_custom_component instead of directly from homeassistant
from pytest_homeassistant_custom_component.common import MockConfigEntry
from homeassistant.components.vacuum import VacuumEntityFeature
from homeassistant.core import HomeAssistant
from homeassistant.const import (
    CONF_ACCESS_TOKEN,
    CONF_MODEL,
    CONF_NAME,
    CONF_ID,
    CONF_IP_ADDRESS,
    CONF_DESCRIPTION,
    CONF_MAC,
)

from custom_components.robovac.const import CONF_VACS, DOMAIN
from custom_components.robovac.vacuums.base import RobovacCommand, RoboVacEntityFeature


def _command_value(command, value):
    mapping = {
        RobovacCommand.START_PAUSE: {
            "pause": False,
            "start": True,
        },
        RobovacCommand.RETURN_HOME: True,
        RobovacCommand.MODE: {
            "auto": "auto",
            "spot": "Spot",
            "edge": "Edge",
            "small_room": "SmallRoom",
        },
        RobovacCommand.FAN_SPEED: {
            "no_suction": "No_suction",
            "boost_iq": "Boost_IQ",
            "pure": "Quiet",
            "standard": "Standard",
        },
    }
    result = mapping.get(command)
    if isinstance(result, dict):
        return result.get(value, value)
    if result is not None:
        return result
    return value


# This fixture is required for testing custom components
@pytest.fixture
def enable_custom_integrations():
    """Stub fixture matching Home Assistant's enable_custom_integrations."""

    yield


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Enable custom integrations for testing."""
    yield


@pytest.fixture
def mock_robovac():
    """Create a mock RoboVac device."""
    mock = MagicMock()
    # Set up common return values
    mock.getHomeAssistantFeatures.return_value = (
        VacuumEntityFeature.BATTERY
        | VacuumEntityFeature.CLEAN_SPOT
        | VacuumEntityFeature.FAN_SPEED
        | VacuumEntityFeature.LOCATE
        | VacuumEntityFeature.PAUSE
        | VacuumEntityFeature.RETURN_HOME
        | VacuumEntityFeature.SEND_COMMAND
        | VacuumEntityFeature.START
        | VacuumEntityFeature.STATE
        | VacuumEntityFeature.STOP
    )
    mock.getRoboVacFeatures.return_value = (
        RoboVacEntityFeature.EDGE
        | RoboVacEntityFeature.SMALL_ROOM
        | RoboVacEntityFeature.ROOM
    )
    mock.getFanSpeeds.return_value = ["No Suction", "Standard", "Boost IQ", "Max"]
    mock._dps = {}

    # Set up async methods with AsyncMock
    mock.async_get = AsyncMock(return_value=mock._dps)
    mock.async_set = AsyncMock(return_value=True)
    mock.async_disable = AsyncMock(return_value=True)
    mock.getRoboVacCommandValue.side_effect = _command_value
    mock.getRoboVacHumanReadableValue.side_effect = _command_value
    mock.getRoboVacActivityMapping.return_value = None
    mock.getRoomNames.return_value = {100: "Kitchen", 101: "Bedroom"}
    mock.getDpsCodes.return_value = {
        "START_PAUSE": "2",
        "MODE": "5",
        "STATUS": "15",
        "FAN_SPEED": "102",
        "RETURN_HOME": "101",
        "DO_NOT_DISTURB": "107",
        "DO_NOT_DISTURB_SCHEDULE": "139",
        "AUTO_RETURN": "135",
        "BOOST_IQ": "118",
        "ROOM_CLEAN": "168",
    }

    return mock


@pytest.fixture
def mock_g30():
    """Create a mock G30 RoboVac device."""
    mock = MagicMock()
    # Set up common return values
    mock.getHomeAssistantFeatures.return_value = (
        VacuumEntityFeature.BATTERY
        | VacuumEntityFeature.CLEAN_SPOT
        | VacuumEntityFeature.FAN_SPEED
        | VacuumEntityFeature.LOCATE
        | VacuumEntityFeature.PAUSE
        | VacuumEntityFeature.RETURN_HOME
        | VacuumEntityFeature.SEND_COMMAND
        | VacuumEntityFeature.START
        | VacuumEntityFeature.STATE
        | VacuumEntityFeature.STOP
    )
    mock.getRoboVacFeatures.return_value = (
        RoboVacEntityFeature.EDGE | RoboVacEntityFeature.SMALL_ROOM
    )
    mock.getFanSpeeds.return_value = ["No Suction", "Standard", "Boost IQ", "Max"]
    mock._dps = {}

    # Set up async methods with AsyncMock
    mock.async_get = AsyncMock(return_value=mock._dps)
    mock.async_set = AsyncMock(return_value=True)
    mock.async_disable = AsyncMock(return_value=True)
    mock.getRoboVacCommandValue.side_effect = _command_value

    return mock


@pytest.fixture
def mock_vacuum_data():
    """Create mock vacuum configuration data."""
    return {
        CONF_NAME: "Test RoboVac",
        CONF_ID: "test_robovac_id",
        CONF_MODEL: "T2118",  # 15C model
        CONF_IP_ADDRESS: "192.168.1.100",
        CONF_ACCESS_TOKEN: "test_access_token",
        CONF_DESCRIPTION: "RoboVac 15C",
        CONF_MAC: "aa:bb:cc:dd:ee:ff",
    }


@pytest.fixture
async def hass() -> HomeAssistant:
    """Provide a minimal Home Assistant instance for tests."""

    instance = HomeAssistant()
    # Ensure the loop reference matches the running test loop
    instance.loop = asyncio.get_running_loop()
    instance.data = {DOMAIN: {CONF_VACS: {}}}
    return instance


@pytest.fixture
def mock_g30_data():
    """Create mock G30 vacuum configuration data."""
    return {
        CONF_NAME: "Test G30",
        CONF_ID: "test_g30_id",
        CONF_MODEL: "T2250",  # G30 model
        CONF_IP_ADDRESS: "192.168.1.101",
        CONF_ACCESS_TOKEN: "test_access_token_g30",
        CONF_DESCRIPTION: "RoboVac G30",
        CONF_MAC: "aa:bb:cc:dd:ee:00",
    }


@pytest.fixture
def mock_l60():
    """Create a mock L60 RoboVac device."""
    mock = MagicMock()
    # Set up common return values
    mock.getHomeAssistantFeatures.return_value = (
        VacuumEntityFeature.BATTERY
        | VacuumEntityFeature.FAN_SPEED
        | VacuumEntityFeature.LOCATE
        | VacuumEntityFeature.PAUSE
        | VacuumEntityFeature.RETURN_HOME
        | VacuumEntityFeature.SEND_COMMAND
        | VacuumEntityFeature.START
        | VacuumEntityFeature.STATE
        | VacuumEntityFeature.STOP
    )
    mock.getRoboVacFeatures.return_value = (
        RoboVacEntityFeature.DO_NOT_DISTURB | RoboVacEntityFeature.BOOST_IQ
    )
    mock.getFanSpeeds.return_value = ["No Suction", "Standard", "Boost IQ", "Max"]
    mock._dps = {}

    # Set up model-specific DPS codes for L60 (T2278)
    mock.getDpsCodes.return_value = {
        "MODE": "152",
        "STATUS": "173",
        "RETURN_HOME": "153",
        "FAN_SPEED": "154",
        "LOCATE": "153",
        "BATTERY_LEVEL": "172",
        "ERROR_CODE": "169",
    }

    # Set up async methods with AsyncMock
    mock.async_get = AsyncMock(return_value=mock._dps)
    mock.async_set = AsyncMock(return_value=True)
    mock.async_disable = AsyncMock(return_value=True)
    mock.getRoboVacCommandValue.side_effect = _command_value

    return mock


@pytest.fixture
def mock_l60_data():
    """Create mock L60 vacuum configuration data."""
    return {
        CONF_NAME: "Test L60",
        CONF_ID: "test_l60_id",
        CONF_MODEL: "T2278",  # L60 model
        CONF_IP_ADDRESS: "192.168.1.102",
        CONF_ACCESS_TOKEN: "test_access_token_l60",
        CONF_DESCRIPTION: "eufy Clean L60 Hybrid SES",
        CONF_MAC: "aa:bb:cc:dd:ee:11",
    }
