from typing import Any, cast
from collections.abc import Mapping
import base64
from homeassistant.components.vacuum import VacuumActivity

from .tuyalocalapi import TuyaDevice
from .vacuums import ROBOVAC_MODELS
from .vacuums.base import RobovacCommand, RobovacModelDetails

import logging

_LOGGER = logging.getLogger(__name__)


def _decode_status_field2(b64_value: str) -> int | None:
    """Decode the integer status code (field 2) from a length-prefixed
    ModeCtrlResponse protobuf, encoded as base64.

    Eufy X-series devices emit the same logical status (e.g. cleaning,
    returning, error) with multiple protobuf field orderings, producing
    many distinct base64 strings for one underlying state. Decoding
    field 2 directly avoids per-string maintenance.

    Returns the integer status code (e.g. 2=error, 3=returning, 5=cleaning)
    or None if the payload doesn't look like a length-prefixed protobuf.
    """
    try:
        data = base64.b64decode(b64_value + "==")
    except Exception:  # pylint: disable=broad-except
        return None
    if len(data) < 2:
        return None
    # Strip outer length prefix (single varint)
    inner_len = data[0]
    if inner_len & 0x80:  # multi-byte length not seen on this device family
        return None
    inner = data[1:1 + inner_len]
    pos = 0
    while pos < len(inner):
        tag = inner[pos]
        pos += 1
        field = tag >> 3
        wire = tag & 7
        if wire == 0:  # varint
            v = 0
            shift = 0
            while pos < len(inner):
                b = inner[pos]
                pos += 1
                v |= (b & 0x7F) << shift
                if not (b & 0x80):
                    break
                shift += 7
            if field == 2:
                return v
        elif wire == 2:  # length-delimited; skip
            if pos >= len(inner):
                return None
            ln = inner[pos]
            pos += 1 + ln
        else:
            return None
    return None


class ModelNotSupportedException(Exception):
    """This model is not supported"""


class RoboVac(TuyaDevice):
    """Tuya RoboVac device integration for Home Assistant.

    This class provides the main interface for controlling and monitoring
    Tuya-based robotic vacuum cleaners. It handles model-specific features,
    command mappings, and state translations.

    Attributes:
        model_details: Model-specific configuration and feature mappings
        model_code: The specific model identifier (e.g., "T2080", "L60")
    """

    model_details: type[RobovacModelDetails]

    def __init__(self, model_code: str, *args: Any, **kwargs: Any):
        """Initialize the RoboVac device.

        Args:
            model_code: The model identifier for the vacuum (must exist in ROBOVAC_MODELS)
            *args: Additional arguments passed to TuyaDevice
            **kwargs: Additional keyword arguments passed to TuyaDevice

        Raises:
            ModelNotSupportedException: If the model_code is not supported
        """
        # Determine model_details first
        if model_code not in ROBOVAC_MODELS:
            raise ModelNotSupportedException(f"Model {model_code} is not supported")
        current_model_details = ROBOVAC_MODELS[model_code]

        super().__init__(current_model_details, *args, **kwargs)

        self.model_code = model_code
        self.model_details = current_model_details

    def getHomeAssistantFeatures(self) -> int:
        """Get the Home Assistant supported features for this vacuum model.

        Returns:
            int: Bitwise OR of VacuumEntityFeature constants indicating which
                 Home Assistant vacuum features are supported by this model.
        """
        return self.model_details.homeassistant_features

    def getRoboVacFeatures(self) -> int:
        """Get the RoboVac-specific supported features for this vacuum model.

        Returns:
            int: Bitwise OR of custom RoboVac feature constants indicating which
                 vacuum-specific features are supported by this model.
        """
        return self.model_details.robovac_features

    def getRoboVacActivityMapping(self) -> dict[str, VacuumActivity] | None:
        """Get the mapping of device statuses to Home Assistant VacuumActivity enums.

        Returns:
            dict[str, VacuumActivity] | None: Dictionary mapping human-readable vacuum
                statuses (e.g., "Auto cleaning", "Returning home") to Home Assistant
                VacuumActivity enum values, or None if not configured for this model.
        """
        return self.model_details.activity_mapping

    def _get_command_values(
        self, command_name: RobovacCommand
    ) -> dict[str, str] | None:
        """Get the values for a specific command from the model details.

        This is a helper method to safely access command values for the current model.

        Args:
            command_name: The RobovacCommand enum value to get values for

        Returns:
            dict[str, str] | None: Dictionary mapping human-readable values to
                device-specific command codes, or None if command not supported
        """
        if command_name not in self.model_details.commands:
            return None

        command = self.model_details.commands[command_name]
        if not isinstance(command, dict) or "values" not in command:
            return None

        values = command["values"]
        if not isinstance(values, dict):
            return None

        return values

    def getFanSpeeds(self) -> list[str]:
        """Get the supported fan speeds for this vacuum model.

        Returns:
            list[str]: List of human-readable fan speed names (e.g., ["Standard", "Boost IQ", "Max"])
                      Returns empty list if fan speed control is not supported by this model.
        """
        values = self._get_command_values(RobovacCommand.FAN_SPEED)
        if values is None:
            return []

        # Return the values from the dictionary (the display names)
        # This preserves existing behavior for tests
        return list(values.values())

    def getSupportedCommands(self) -> list[str]:
        """Get the list of supported commands for this vacuum model.

        Returns:
            list[str]: List of RobovacCommand enum names that are supported by this model
                      (e.g., ["MODE", "FAN_SPEED", "AUTO_RETURN"])
        """
        return list(self.model_details.commands.keys())

    def getDpsCodes(self) -> dict[str, str]:
        """Get the DPS codes for this model based on command codes.

        Maps command names to their corresponding DPS code names and returns
        a dictionary of DPS codes for status updates.

        Returns:
            dict[str, str]: Dictionary mapping DPS code names (e.g., "BATTERY_LEVEL", "ERROR_CODE")
                           to their numeric string values (e.g., "104", "106") for Tuya communication
        """
        # Map command names to DPS code names
        command_to_dps = {
            "BATTERY": "BATTERY_LEVEL",
            "ERROR": "ERROR_CODE",
            # All others use the same code names
        }

        codes = {}
        # Extract codes from commands dictionary
        for key, value in self.model_details.commands.items():
            # Get the DPS name from the mapping, or use the command name if not in mapping
            dps_name = command_to_dps.get(key.name, key.name)

            # Extract code value based on whether it's a direct value or in a dictionary
            if isinstance(value, dict) and "code" in value:
                # If it has a code property, use that
                codes[dps_name] = str(value["code"])
            elif isinstance(value, dict):
                # Skip dictionaries without code property (like when only 'values' is present)
                continue
            else:
                # For direct values, use the value itself
                codes[dps_name] = str(value)

        model_overrides = getattr(self.model_details, "dps_codes", None)
        if isinstance(model_overrides, Mapping):
            for key, value in model_overrides.items():
                codes[str(key)] = str(value)

        return codes

    def getRoboVacCommandValue(self, command_name: RobovacCommand, value: str) -> str:
        """Convert human-readable command value to model-specific device value.

        Translates user-friendly command values to the actual values that need to be
        sent to the vacuum device via the Tuya protocol.

        Args:
            command_name: The command type (e.g., RobovacCommand.MODE, RobovacCommand.FAN_SPEED)
            value: The human-readable value (e.g., "auto", "edge", "Standard")

        Returns:
            str: The model-specific value for the device (e.g., "BBoCCAE=" for L60 "auto" mode,
                 "CAoCCAE=" for T2080 base64-encoded commands). Returns the original value
                 if no mapping exists.
        """
        try:
            # Check if command_name is already a RobovacCommand enum
            cmd = (
                command_name
                if isinstance(command_name, RobovacCommand)
                else RobovacCommand(command_name)
            )
            values = self._get_command_values(cmd)

            if values is not None and value in values:
                return str(values[value])

        except (ValueError, KeyError):
            pass

        return value

    def getRoboVacHumanReadableValue(
        self, command_name: RobovacCommand, value: str
    ) -> str:
        """Convert model-specific device value to human-readable command value.

        Translates device-specific values received from the vacuum via Tuya protocol
        to user-friendly, human-readable values for display in Home Assistant.

        Args:
            command_name: The command type (e.g., RobovacCommand.STATUS, RobovacCommand.MODE)
            value: The model-specific value from device (e.g., "CAoCCAE=" base64 encoded, "2")

        Returns:
            str: The human-readable value (e.g., "Auto cleaning", "Returning home", "auto").
                 Returns the original value if no mapping exists.
        """
        try:
            # Check if command_name is already a RobovacCommand enum
            cmd = (
                command_name
                if isinstance(command_name, RobovacCommand)
                else RobovacCommand(command_name)
            )
            values = self._get_command_values(cmd)

            if values is not None:
                # Direct lookup: the input value should be a key in the values dict
                if str(value) in values:
                    return str(values[value])

            # Protobuf fallback for STATUS: decode the base64 ModeCtrlResponse,
            # extract field 2 (the integer status code), and look it up in the
            # model's `status_codes` table. Lets one entry per logical state
            # cover every protobuf variant the device emits.
            if cmd == RobovacCommand.STATUS and cmd in self.model_details.commands:
                status_def = self.model_details.commands[cmd]
                status_codes = (
                    status_def.get("status_codes")
                    if isinstance(status_def, dict)
                    else None
                )
                if isinstance(status_codes, dict):
                    code = _decode_status_field2(str(value))
                    if code is not None and code in status_codes:
                        _LOGGER.debug(
                            "STATUS protobuf-decoded code=%s -> %s (raw=%s)",
                            code, status_codes[code], value,
                        )
                        return str(status_codes[code])
                    if code is not None:
                        _LOGGER.warning(
                            "STATUS protobuf code %s not in status_codes for "
                            "model %s (raw=%s). Add an entry to "
                            "vacuums/%s.py STATUS.status_codes.",
                            code, self.model_code, value, self.model_code,
                        )
                        return value

        except (ValueError, KeyError):
            pass

        _LOGGER.warning(
            "Command %s with value %s not found for model %s. If you know the status the Eufy app was showing at this time, please report that to the component maintainers.",
            command_name,
            value,
            self.model_code,
        )
        return value
