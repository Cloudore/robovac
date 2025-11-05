"""Tests for the RoboVac vacuum entity commands."""

import base64
import json

import pytest
from unittest.mock import MagicMock, call, patch

from homeassistant.components.vacuum import VacuumEntityFeature

from custom_components.robovac.const import CONF_ROOM_NAMES
from custom_components.robovac.vacuum import RoboVacEntity
from custom_components.robovac.vacuums.base import RobovacCommand


@pytest.mark.asyncio
async def test_async_locate(mock_robovac, mock_vacuum_data):
    """Test the async_locate method."""
    # Arrange
    with patch("custom_components.robovac.vacuum.RoboVac", return_value=mock_robovac):
        entity = RoboVacEntity(mock_vacuum_data)

        # Initialize the entity's tuyastatus attribute
        mock_robovac._dps = {"103": False}
        entity.tuyastatus = mock_robovac._dps

        # Act
        await entity.async_locate()

        # Assert
        mock_robovac.async_set.assert_called_once_with({"103": True})

        # Reset mock
        mock_robovac.async_set.reset_mock()

        # Test when locate is on
        mock_robovac._dps = {"103": True}
        entity.tuyastatus = mock_robovac._dps

        # Act
        await entity.async_locate()

        # Assert
        mock_robovac.async_set.assert_called_once_with({"103": False})


@pytest.mark.asyncio
async def test_async_identify_triggers_locate(mock_robovac, mock_vacuum_data):
    """Ensure async_identify calls async_locate."""
    with patch("custom_components.robovac.vacuum.RoboVac", return_value=mock_robovac):
        entity = RoboVacEntity(mock_vacuum_data)
        with patch.object(entity, "async_locate") as mock_locate:
            await entity.async_identify()
            mock_locate.assert_called_once()


@pytest.mark.asyncio
async def test_supported_features_include_locate(mock_robovac, mock_vacuum_data):
    """Ensure LOCATE feature is set when command exists."""
    with patch("custom_components.robovac.vacuum.RoboVac", return_value=mock_robovac):
        mock_robovac.getHomeAssistantFeatures.return_value = VacuumEntityFeature.BATTERY
        mock_robovac.model_details = MagicMock()
        mock_robovac.model_details.commands = {RobovacCommand.LOCATE: {"code": "103"}}
        entity = RoboVacEntity(mock_vacuum_data)
        assert entity.supported_features & VacuumEntityFeature.LOCATE


@pytest.mark.asyncio
async def test_async_return_to_base(mock_robovac, mock_vacuum_data):
    """Test the async_return_to_base method."""
    # Arrange
    with patch("custom_components.robovac.vacuum.RoboVac", return_value=mock_robovac):
        entity = RoboVacEntity(mock_vacuum_data)

        # Act
        await entity.async_return_to_base()

        # Assert
        mock_robovac.async_set.assert_called_once_with({"101": True})


@pytest.mark.asyncio
async def test_async_start(mock_robovac, mock_vacuum_data):
    """Test the async_start method."""
    # Arrange
    with patch("custom_components.robovac.vacuum.RoboVac", return_value=mock_robovac):
        entity = RoboVacEntity(mock_vacuum_data)

        # Act
        await entity.async_start()

        # Assert
        assert entity._attr_mode == "auto"
        mock_robovac.async_set.assert_called_once_with({"5": "auto"})


@pytest.mark.asyncio
async def test_async_start_model_specific(
    mock_robovac, mock_vacuum_data, mock_l60, mock_l60_data
):
    """Test that async_start uses the correct code for different models."""
    # Test with standard model (should use code "5")
    with patch("custom_components.robovac.vacuum.RoboVac", return_value=mock_robovac):
        entity = RoboVacEntity(mock_vacuum_data)
        await entity.async_start()
        mock_robovac.async_set.assert_called_once_with({"5": "auto"})
        mock_robovac.async_set.reset_mock()

    # Test with L60 model (should use code "152")
    # Mock should return "152" for the MODE code
    mock_l60.getDpsCodes.return_value = {"MODE": "152"}
    with patch("custom_components.robovac.vacuum.RoboVac", return_value=mock_l60):
        entity = RoboVacEntity(mock_l60_data)
        await entity.async_start()
        # This will fail with the current implementation because it always uses code "5"
        # The fix will make it use "152" for L60 models
        mock_l60.async_set.assert_called_once_with({"152": "auto"})


@pytest.mark.asyncio
async def test_async_pause(mock_robovac, mock_vacuum_data):
    """Test the async_pause method."""
    # Arrange
    with patch("custom_components.robovac.vacuum.RoboVac", return_value=mock_robovac):
        entity = RoboVacEntity(mock_vacuum_data)

        # Act
        await entity.async_pause()

        # Assert
        mock_robovac.async_set.assert_called_once_with({"2": False})


@pytest.mark.asyncio
async def test_async_stop(mock_robovac, mock_vacuum_data):
    """Test the async_stop method."""
    # Arrange
    with patch("custom_components.robovac.vacuum.RoboVac", return_value=mock_robovac):
        entity = RoboVacEntity(mock_vacuum_data)

        # Mock the async_return_to_base method
        with patch.object(entity, "async_return_to_base") as mock_return:
            # Act
            await entity.async_stop()

            # Assert
            mock_return.assert_called_once()


@pytest.mark.asyncio
async def test_async_clean_spot(mock_robovac, mock_vacuum_data):
    """Test the async_clean_spot method."""
    # Arrange
    with patch("custom_components.robovac.vacuum.RoboVac", return_value=mock_robovac):
        entity = RoboVacEntity(mock_vacuum_data)

        # Act
        await entity.async_clean_spot()

        # Assert
        mock_robovac.async_set.assert_called_once_with({"5": "Spot"})


@pytest.mark.asyncio
async def test_async_set_fan_speed(mock_robovac, mock_vacuum_data):
    """Test the async_set_fan_speed method."""
    # Arrange
    with patch("custom_components.robovac.vacuum.RoboVac", return_value=mock_robovac):
        entity = RoboVacEntity(mock_vacuum_data)

        # Test cases for fan speed conversion
        test_cases = [
            ("No Suction", "No_suction"),
            ("Boost IQ", "Boost_IQ"),
            ("Pure", "Quiet"),
            ("Standard", "Standard"),  # No change
        ]

        for input_speed, expected_output in test_cases:
            # Reset mock
            mock_robovac.async_set.reset_mock()

            # Act
            await entity.async_set_fan_speed(input_speed)

            # Assert
            mock_robovac.async_set.assert_called_once_with({"102": expected_output})


@pytest.mark.asyncio
async def test_async_send_command(mock_robovac, mock_vacuum_data):
    """Test the async_send_command method."""
    # Arrange
    with patch("custom_components.robovac.vacuum.RoboVac", return_value=mock_robovac):
        entity = RoboVacEntity(mock_vacuum_data)

        # Test edge clean command
        await entity.async_send_command("edgeClean")
        mock_robovac.async_set.assert_called_once_with({"5": "Edge"})
        mock_robovac.async_set.reset_mock()

        # Test small room clean command
        await entity.async_send_command("smallRoomClean")
        mock_robovac.async_set.assert_called_once_with({"5": "SmallRoom"})
        mock_robovac.async_set.reset_mock()

        # Test auto clean command
        await entity.async_send_command("autoClean")
        mock_robovac.async_set.assert_called_once_with({"5": "auto"})
        mock_robovac.async_set.reset_mock()

        # Test auto return command (when off)
        entity._attr_auto_return = False
        await entity.async_send_command("autoReturn")
        mock_robovac.async_set.assert_called_once_with({"135": True})
        mock_robovac.async_set.reset_mock()

        # Test auto return command (when on)
        entity._attr_auto_return = True
        await entity.async_send_command("autoReturn")
        mock_robovac.async_set.assert_called_once_with({"135": False})
        mock_robovac.async_set.reset_mock()

        # Test do not disturb command (when off)
        entity._attr_do_not_disturb = False
        await entity.async_send_command("doNotDisturb")
        assert mock_robovac.async_set.call_count == 2
        mock_robovac.async_set.assert_has_calls(
            [call({"139": "MTAwMDAwMDAw"}), call({"107": True})]
        )
        mock_robovac.async_set.reset_mock()

        # Test do not disturb command (when on)
        entity._attr_do_not_disturb = True
        await entity.async_send_command("doNotDisturb")
        assert mock_robovac.async_set.call_count == 2
        mock_robovac.async_set.assert_has_calls(
            [call({"139": "MEQ4MDAwMDAw"}), call({"107": False})]
        )
        mock_robovac.async_set.reset_mock()

        # Test boost IQ command (when off)
        entity._attr_boost_iq = False
        await entity.async_send_command("boostIQ")
        mock_robovac.async_set.assert_called_once_with({"118": True})
        mock_robovac.async_set.reset_mock()

        # Test boost IQ command (when on)
        entity._attr_boost_iq = True
        await entity.async_send_command("boostIQ")
        mock_robovac.async_set.assert_called_once_with({"118": False})


@pytest.mark.asyncio
async def test_async_send_command_room_clean_uses_model_code(
    mock_robovac, mock_vacuum_data
):
    """Ensure roomClean uses the model-specific ROOM_CLEAN DPS code."""

    with patch("custom_components.robovac.vacuum.RoboVac", return_value=mock_robovac):
        mock_robovac.getDpsCodes.return_value = {"ROOM_CLEAN": "168"}
        entity = RoboVacEntity(mock_vacuum_data)

        with patch("custom_components.robovac.vacuum.time.time", return_value=1234.567):
            await entity.async_send_command(
                "roomClean", {"roomIds": [100], "count": 2}
            )

        expected_payload = base64.b64encode(
            json.dumps(
                {
                    "method": "selectRoomsClean",
                    "data": {"roomIds": [100], "cleanTimes": 2},
                    "timestamp": 1234567,
                },
                separators=(",", ":"),
            ).encode("utf8")
        ).decode("utf8")

        mock_robovac.async_set.assert_called_once_with({"168": expected_payload})


@pytest.mark.asyncio
async def test_async_send_command_room_clean_accepts_room_names(
    mock_robovac, mock_vacuum_data
):
    """Ensure roomClean resolves room names to ids when provided."""

    with patch("custom_components.robovac.vacuum.RoboVac", return_value=mock_robovac):
        mock_robovac.getDpsCodes.return_value = {"ROOM_CLEAN": "168"}
        mock_robovac.getRoomNames.return_value = {100: "Kitchen"}
        entity = RoboVacEntity(mock_vacuum_data)

        with patch("custom_components.robovac.vacuum.time.time", return_value=321.0):
            await entity.async_send_command(
                "roomClean", {"roomNames": ["Kitchen"], "count": 1}
            )

        expected_payload = base64.b64encode(
            json.dumps(
                {
                    "method": "selectRoomsClean",
                    "data": {"roomIds": [100], "cleanTimes": 1},
                    "timestamp": 321000,
                },
                separators=(",", ":"),
            ).encode("utf8")
        ).decode("utf8")

        mock_robovac.async_set.assert_called_once_with({"168": expected_payload})


@pytest.mark.asyncio
async def test_extra_state_attributes_include_room_names(mock_robovac, mock_vacuum_data):
    """Room names should be exposed when the feature is supported."""

    data = dict(mock_vacuum_data)
    data[CONF_ROOM_NAMES] = {"200": "Configured"}

    with patch("custom_components.robovac.vacuum.RoboVac", return_value=mock_robovac):
        entity = RoboVacEntity(data)

    attrs = entity.extra_state_attributes
    assert attrs["room_names"] == {200: "Configured", 100: "Kitchen", 101: "Bedroom"}

@pytest.mark.asyncio
async def test_async_update(mock_robovac, mock_vacuum_data):
    """Test the async_update method."""
    # Arrange
    with patch("custom_components.robovac.vacuum.RoboVac", return_value=mock_robovac):
        entity = RoboVacEntity(mock_vacuum_data)

        # Act - normal update
        await entity.async_update()

        # Assert
        mock_robovac.async_get.assert_called_once()

        # Reset mock
        mock_robovac.async_get.reset_mock()

        # Test with unsupported model
        entity.error_code = "UNSUPPORTED_MODEL"
        await entity.async_update()
        mock_robovac.async_get.assert_not_called()

        # Reset error code
        entity.error_code = None

        # Test with empty IP address
        entity._attr_ip_address = ""
        await entity.async_update()
        assert entity.error_code == "IP_ADDRESS"
        mock_robovac.async_get.assert_not_called()


@pytest.mark.asyncio
async def test_async_will_remove_from_hass(mock_robovac, mock_vacuum_data):
    """Test the async_will_remove_from_hass method."""
    # Arrange
    with patch("custom_components.robovac.vacuum.RoboVac", return_value=mock_robovac):
        entity = RoboVacEntity(mock_vacuum_data)

        # Act
        await entity.async_will_remove_from_hass()

        # Assert
        mock_robovac.async_disable.assert_called_once()
