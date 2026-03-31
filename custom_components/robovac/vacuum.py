# Copyright 2022 Brendan McCluskey
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Eufy Robovac vacuum platform.

This module provides the vacuum entity integration for Eufy Robovac devices.
"""

from __future__ import annotations
import ast
import asyncio
import base64
import binascii
from collections.abc import Callable
from datetime import timedelta
from enum import StrEnum
import json
import logging
import time
from typing import Any

from homeassistant.components.vacuum import (
    StateVacuumEntity,
    VacuumActivity,
    VacuumEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_ACCESS_TOKEN,
    CONF_DESCRIPTION,
    CONF_ID,
    CONF_IP_ADDRESS,
    CONF_MAC,
    CONF_MODEL,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_USERNAME,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CONF_VACS, DOMAIN, PING_RATE, REFRESH_RATE, TIMEOUT
from .eufywebapi import EufyLogon
from .errors import getErrorMessage
from .room_payload import decode_binary_room_list, lookup_known_room_clean_payload
from .vacuums.base import (
    RobovacCommand,
    RoboVacEntityFeature,
    TuyaCodes,
    TUYA_CONSUMABLES_CODES,
)
from .robovac import ModelNotSupportedException, RoboVac
from .tuyalocalapi import TuyaException

try:
    from homeassistant.components.vacuum import Segment
except ImportError:
    Segment = None

ATTR_BATTERY_ICON = "battery_icon"
ATTR_ERROR = "error"
ATTR_FAN_SPEED = "fan_speed"
ATTR_FAN_SPEED_LIST = "fan_speed_list"
ATTR_STATUS = "status"
ATTR_ERROR_CODE = "error_code"
ATTR_MODEL_CODE = "model_code"
ATTR_CLEANING_AREA = "cleaning_area"
ATTR_CLEANING_TIME = "cleaning_time"
ATTR_AUTO_RETURN = "auto_return"
ATTR_DO_NOT_DISTURB = "do_not_disturb"
ATTR_BOOST_IQ = "boost_iq"
ATTR_CONSUMABLES = "consumables"
ATTR_MODE = "mode"

_LOGGER = logging.getLogger(__name__)
SCAN_INTERVAL = timedelta(seconds=REFRESH_RATE)
UPDATE_RETRIES = 3
_FEATURE_CLEAN_AREA = getattr(VacuumEntityFeature, "CLEAN_AREA", 0)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Initialize my test integration 2 config entry."""
    vacuums = config_entry.data[CONF_VACS]
    username = config_entry.data.get(CONF_USERNAME)
    password = config_entry.data.get(CONF_PASSWORD)
    for vacuum_id in vacuums:
        item = dict(vacuums[vacuum_id])
        if username:
            item[CONF_USERNAME] = username
        if password:
            item[CONF_PASSWORD] = password
        entity = RoboVacEntity(item)
        hass.data[DOMAIN][CONF_VACS][item[CONF_ID]] = entity
        async_add_entities([entity])


class RoboVacEntity(StateVacuumEntity):
    """Home Assistant vacuum entity for Tuya-based robotic vacuum cleaners.

    This class implements the Home Assistant VacuumEntity interface for controlling
    and monitoring Tuya-based robotic vacuum cleaners. It provides support for
    standard vacuum operations like start/stop/pause, cleaning modes, fan speeds,
    and status reporting.

    The entity automatically maps device-specific values to Home Assistant standards
    and handles model-specific features and command mappings.
    """

    _attr_should_poll = True

    _attr_access_token: str | None = None
    _attr_ip_address: str | None = None
    _attr_model_code: str | None = None
    _attr_cleaning_area: str | None = None
    _attr_cleaning_time: str | None = None
    _attr_auto_return: str | None = None
    _attr_do_not_disturb: str | None = None
    _attr_boost_iq: str | None = None
    _attr_consumables: str | None = None
    _attr_mode: str | None = None
    _attr_robovac_supported: int | None = None
    _attr_activity_mapping: dict[str, VacuumActivity] | None = None
    _attr_error_code: int | str | None = None
    _attr_tuya_state: int | str | None = None
    _attr_room_names: dict[str, dict[str, Any]] | None = None

    @property
    def robovac_supported(self) -> int | None:
        """Return the supported features of the vacuum cleaner."""
        return self._attr_robovac_supported

    @property
    def activity_mapping(self) -> dict[str, VacuumActivity] | None:
        """Return the mapping of statuses to Home Assistant VacuumActivity."""
        return self._attr_activity_mapping

    @property
    def mode(self) -> str | None:
        """Return the cleaning mode of the vacuum cleaner."""
        return self._attr_mode

    @property
    def consumables(self) -> str | None:
        """Return the consumables status of the vacuum cleaner."""
        return self._attr_consumables

    @property
    def cleaning_area(self) -> str | None:
        """Return the cleaning area of the vacuum cleaner."""
        return self._attr_cleaning_area

    @property
    def cleaning_time(self) -> str | None:
        """Return the cleaning time of the vacuum cleaner."""
        return self._attr_cleaning_time

    @property
    def auto_return(self) -> str | None:
        """Return the auto_return mode of the vacuum cleaner."""
        return self._attr_auto_return

    @property
    def do_not_disturb(self) -> str | None:
        """Return the do_not_disturb mode of the vacuum cleaner."""
        return self._attr_do_not_disturb

    @property
    def boost_iq(self) -> str | None:
        """Return the boost_iq mode of the vacuum cleaner."""
        return self._attr_boost_iq

    @property
    def tuya_state(self) -> str | int | None:
        """Return the state of the vacuum cleaner.

        This property is for backward compatibility with tests.
        """
        return self._attr_tuya_state

    @tuya_state.setter
    def tuya_state(self, value: str | int | None) -> None:
        """Set the state of the vacuum cleaner.

        This setter is for backward compatibility with tests.
        """
        self._attr_tuya_state = value

    @property
    def error_code(self) -> int | str | None:
        """Return the error code of the vacuum cleaner.

        This property is for backward compatibility with tests.
        """
        return self._attr_error_code

    @error_code.setter
    def error_code(self, value: int | str | None) -> None:
        """Set the error code of the vacuum cleaner.

        This setter is for backward compatibility with tests.
        """
        self._attr_error_code = value

    @property
    def model_code(self) -> str | None:
        """Return the model code of the vacuum cleaner."""
        return self._attr_model_code

    @property
    def access_token(self) -> str | None:
        """Return the fan speed of the vacuum cleaner."""
        return self._attr_access_token

    @property
    def ip_address(self) -> str | None:
        """Return the ip address of the vacuum cleaner."""
        return self._attr_ip_address

    def _is_value_true(self, value: Any) -> bool:
        """Check if a value is considered 'true', either as a boolean or string.

        Args:
            value: The value to check.

        Returns:
            bool: True if the value is considered 'true', False otherwise.
        """
        if value is True:
            return True
        if isinstance(value, str):
            return value == "True" or value.lower() == "true"
        return False

    def _get_mode_command_data(self, mode: str) -> dict[str, str] | None:
        """Get mode command data for the vacuum.

        Converts a human-readable cleaning mode to the appropriate DPS command
        data structure for sending to the vacuum device.

        Args:
            mode: The cleaning mode to set (e.g., "auto", "spot", "edge", "small_room")

        Returns:
            dict[str, str] | None: Dictionary with DPS code as key and model-specific
                                  command value as value, or None if vacuum not initialized
        """
        if self.vacuum is None:
            return None

        return {
            self._get_dps_code("MODE"): self.vacuum.getRoboVacCommandValue(
                RobovacCommand.MODE, mode
            )
        }

    @property
    def activity(self) -> VacuumActivity | None:
        """Return the activity of the vacuum cleaner.

        This property is used by Home Assistant to determine the state of the vacuum.
        As of Home Assistant Core 2025.1, this property should be used instead of directly
        setting the state property.
        """
        if self._attr_tuya_state is None or self._attr_tuya_state == 0:
            # 0 is a default set when we don't have a state
            return None
        elif (
            type(self.error_code) is not None
            and self.error_code
            and self.error_code
            not in [
                0,
                "no_error",
            ]
        ):
            _LOGGER.debug(
                "State changed to error. Error message: {}".format(
                    getErrorMessage(self.error_code)
                )
            )
            return VacuumActivity.ERROR
        if self.activity_mapping is not None:
            # Use the activity mapping from the model details
            activity = self.activity_mapping.get(str(self._attr_tuya_state))

            if activity is not None:
                _LOGGER.debug(
                    "Used activity mapping, changing status %s to activity %s",
                    self._attr_tuya_state,
                    activity,
                )
                return activity
            else:
                _LOGGER.debug(
                    "Activity mapping lookup failed for status %s - no mapping found",
                    self._attr_tuya_state,
                )
                # Fall through to heuristics and mode-based mapping

        if self._attr_tuya_state == "Charging" or self._attr_tuya_state == "completed":
            return VacuumActivity.DOCKED
        elif self._attr_tuya_state == "Recharge":
            return VacuumActivity.RETURNING
        elif self._attr_tuya_state == "Sleeping" or self._attr_tuya_state == "standby":
            return VacuumActivity.IDLE
        elif self._attr_tuya_state == "Paused":
            return VacuumActivity.PAUSED
        else:
            # Heuristic: if we've been in return mode for a while, assume docked
            try:
                if (
                    self._last_return_ts is not None
                    and self._attr_mode == "return"
                    and (time.time() - float(self._last_return_ts) > 90)
                ):
                    return VacuumActivity.DOCKED
            except Exception:
                pass
            # Mode-based fallback: derive activity when status is not mapped
            if self._attr_mode:
                try:
                    mode = str(self._attr_mode).lower()
                    if "pause" in mode:
                        return VacuumActivity.PAUSED
                    if mode in (
                        "return",
                        "recharge",
                        "heading_home",
                        "go_home",
                        "returning",
                    ):
                        return VacuumActivity.RETURNING
                    if mode in (
                        "auto",
                        "spot",
                        "small_room",
                        "single_room",
                        "edge",
                        "nosweep",
                        "manual",
                        "room",
                    ):
                        return VacuumActivity.CLEANING
                except Exception:
                    pass
            _LOGGER.debug(
                "State changed to cleaning. Raw Tuya state: %s", self._attr_tuya_state
            )
            # If the state looks like an unmapped base64 payload, default to
            # an idle activity instead of incorrectly reporting cleaning.
            if isinstance(self._attr_tuya_state, str):
                try:
                    base64.b64decode(self._attr_tuya_state, validate=True)
                    _LOGGER.debug(
                        "Unmapped base64 state %s - assuming idle",
                        self._attr_tuya_state,
                    )
                    return VacuumActivity.IDLE
                except binascii.Error:
                    pass
            return VacuumActivity.CLEANING

    @property
    def battery_charging(self) -> bool | None:
        """Return whether the vacuum is currently charging."""
        if self._attr_tuya_state is None:
            return None
        return str(self._attr_tuya_state).lower() in ("charging", "recharge")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the device-specific state attributes of this vacuum."""
        data: dict[str, Any] = {}

        if self._attr_error_code is not None and self._attr_error_code not in [
            0,
            "no_error",
        ]:
            data[ATTR_ERROR] = getErrorMessage(self._attr_error_code)
        if (
            self.robovac_supported is not None
            and self.robovac_supported & RoboVacEntityFeature.CLEANING_AREA
            and self.cleaning_area
        ):
            data[ATTR_CLEANING_AREA] = self.cleaning_area
        if (
            self.robovac_supported is not None
            and self.robovac_supported & RoboVacEntityFeature.CLEANING_TIME
            and self.cleaning_time
        ):
            data[ATTR_CLEANING_TIME] = self.cleaning_time
        if (
            self.robovac_supported is not None
            and self.robovac_supported & RoboVacEntityFeature.AUTO_RETURN
            and self.auto_return
        ):
            data[ATTR_AUTO_RETURN] = self.auto_return
        if (
            self.robovac_supported is not None
            and self.robovac_supported & RoboVacEntityFeature.DO_NOT_DISTURB
            and self.do_not_disturb
        ):
            data[ATTR_DO_NOT_DISTURB] = self.do_not_disturb
        if (
            self.robovac_supported is not None
            and self.robovac_supported & RoboVacEntityFeature.BOOST_IQ
            and self.boost_iq
        ):
            data[ATTR_BOOST_IQ] = self.boost_iq
        if (
            self.robovac_supported is not None
            and self.robovac_supported & RoboVacEntityFeature.CONSUMABLES
            and self.consumables
        ):
            data[ATTR_CONSUMABLES] = self.consumables
        if self.mode:
            data[ATTR_MODE] = self.mode
        if self._attr_room_names:
            data["room_names"] = self._attr_room_names
            data.setdefault("robot_vacuum", {})["rooms"] = {
                key: {
                    "id": value.get("id"),
                    "label": value.get("label"),
                }
                for key, value in self._attr_room_names.items()
            }
        return data

    @property
    def capability_attributes(self) -> dict[str, Any] | None:
        """Return capability metadata, including cleanable room segments."""
        base = super().capability_attributes
        data = dict(base) if isinstance(base, dict) else {}

        if self._attr_room_names:
            data.setdefault("robot_vacuum", {})["rooms"] = [
                {
                    "id": entry.get("id"),
                    "name": entry.get("label"),
                    "label": entry.get("label"),
                }
                for entry in self._attr_room_names.values()
            ]

        return data or None

    def _iter_room_segments(self) -> list[dict[str, str]]:
        """Build normalized room segment list from discovered room names."""
        if not self._attr_room_names:
            return []

        segments: list[dict[str, str]] = []
        for key, entry in self._attr_room_names.items():
            identifier = entry.get("id")
            if identifier is None:
                identifier = key

            label = entry.get("label")
            if not isinstance(label, str) or not label.strip():
                label = str(identifier)

            segments.append({"id": str(identifier), "name": label.strip()})

        segments.sort(key=lambda segment: segment["name"].lower())
        return segments

    async def async_get_segments(self) -> list[Any]:
        """Return cleanable segments for Home Assistant area mapping."""
        segments = self._iter_room_segments()
        if Segment is None:
            return segments
        return [Segment(id=item["id"], name=item["name"]) for item in segments]

    async def async_clean_segments(self, segment_ids: list[str], **kwargs: Any) -> None:
        """Clean selected room segments (used by vacuum.clean_area)."""
        normalized_ids: list[int | str] = []
        for identifier in segment_ids:
            value = str(identifier)
            if value.isdigit():
                normalized_ids.append(int(value))
            else:
                normalized_ids.append(value)

        if not normalized_ids:
            return

        repeat = kwargs.get("count", kwargs.get("clean_times", 1))
        try:
            repeat_count = int(repeat)
        except (TypeError, ValueError):
            repeat_count = 1

        await self.async_send_command(
            "roomClean",
            params={"roomIds": normalized_ids, "count": max(1, repeat_count)},
        )

    def __init__(self, item: dict[str, Any]) -> None:
        """Initialize the RoboVac vacuum entity.

        Establishes connection to the physical vacuum device via Tuya local API
        and configures the Home Assistant entity with model-specific features.

        Args:
            item: Configuration dictionary containing vacuum connection details:
                  - id: Unique identifier for the vacuum
                  - name: Display name for the vacuum
                  - model: Model code (e.g., "T2080", "L60")
                  - ip_address: Local IP address of the vacuum
                  - access_token: Tuya access token for authentication
                  - device_id: Tuya device identifier
        """
        super().__init__()

        # Initialize basic attributes
        self._attr_battery_level = 0
        self._attr_name = item[CONF_NAME]
        self._attr_unique_id = item[CONF_ID]
        self._attr_model_code = item[CONF_MODEL]
        self._attr_ip_address = item[CONF_IP_ADDRESS]
        self._attr_access_token = item[CONF_ACCESS_TOKEN]
        self.vacuum: RoboVac | None = None
        self.update_failures = 0
        self.tuyastatus: dict[str, Any] | None = None
        # Track last-known mode and timing for return-to-dock heuristic
        self._last_mode_value: str | None = None
        self._last_return_ts: float | None = None
        # Track locate/beeper state for models that expose explicit on/off DPS
        self._locate_active: bool = False
        self._room_name_registry: dict[str, dict[str, Any]] = {}
        self._room_name_listeners: set[Callable[[], None]] = set()
        self._eufy_username: str | None = item.get(CONF_USERNAME)
        self._eufy_password: str | None = item.get(CONF_PASSWORD)
        self._cloud_room_lookup_attempted = False

        # Initialize the RoboVac connection
        try:
            # Extract model code prefix for device identification
            model_code_prefix = ""
            if self.model_code is not None:
                model_code_prefix = self.model_code[0:5]

            # Create the RoboVac instance
            self.vacuum = RoboVac(
                device_id=self.unique_id,
                host=self.ip_address,
                local_key=self.access_token,
                timeout=TIMEOUT,
                ping_interval=PING_RATE,
                model_code=model_code_prefix,
                update_entity_state=self.pushed_update_handler,
            )
            _LOGGER.debug(
                "Initialized RoboVac connection for %s (model: %s)",
                self._attr_name,
                self._attr_model_code,
            )
        except ModelNotSupportedException:
            _LOGGER.error("Model %s is not supported", self._attr_model_code)
            self._attr_error_code = "UNSUPPORTED_MODEL"

        # Set supported features if vacuum was initialized successfully
        if self.vacuum is not None:
            # Get the supported features from the vacuum
            features = int(self.vacuum.getHomeAssistantFeatures())
            if self.model_code and self.model_code.startswith("T2320"):
                features |= int(_FEATURE_CLEAN_AREA)
            if hasattr(
                self.vacuum, "model_details"
            ) and RobovacCommand.LOCATE in getattr(
                self.vacuum.model_details, "commands", {}
            ):
                features |= int(VacuumEntityFeature.LOCATE)
            self._attr_supported_features = VacuumEntityFeature(features)
            self._attr_robovac_supported = self.vacuum.getRoboVacFeatures()
            self._attr_activity_mapping = self.vacuum.getRoboVacActivityMapping()
            self._attr_fan_speed_list = self.vacuum.getFanSpeeds()

            _LOGGER.debug(
                "Vacuum %s supports features: %s",
                self._attr_name,
                self._attr_supported_features,
            )
        else:
            # Set default values if vacuum initialization failed
            self._attr_supported_features = VacuumEntityFeature(0)
            self._attr_robovac_supported = 0
            self._attr_fan_speed_list = []
            _LOGGER.warning(
                "Vacuum %s initialization failed, features not available",
                self._attr_name,
            )

        # Initialize additional attributes
        self._attr_mode = None
        self._attr_consumables = None

        # Set up device info for Home Assistant device registry
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, item[CONF_ID])},
            name=item[CONF_NAME],
            manufacturer="Eufy",
            model=item[CONF_DESCRIPTION],
            connections={
                (CONNECTION_NETWORK_MAC, item[CONF_MAC]),
            },
        )

    async def async_added_to_hass(self) -> None:
        """Run when entity is added to Home Assistant.

        Trigger an immediate state fetch to avoid prolonged initial Unknown state.
        """
        try:
            # First attempt at fetching state
            await self.async_update()
            # If we still have no status or fan/battery, try a couple of quick retries
            if (
                (self._attr_tuya_state is None or self._attr_tuya_state == 0)
                or (
                    not isinstance(getattr(self, "_attr_fan_speed", None), str)
                    or not self._attr_fan_speed
                )
                or (self._attr_battery_level is None or self._attr_battery_level == 0)
            ):
                for _ in range(2):
                    await asyncio.sleep(0.5)
                    await self.async_update()

            # As a last resort for models that don't answer GET until a SET is sent,
            # probe fan speed on X-series (T2320) to trigger a state push without
            # changing the cleaning state. This is limited to T2320 to avoid altering
            # behavior on other models.
            if (
                (
                    (self._attr_tuya_state is None or self._attr_tuya_state == 0)
                    or (
                        self._attr_battery_level is None
                        or self._attr_battery_level == 0
                    )
                    or (
                        not isinstance(getattr(self, "_attr_fan_speed", None), str)
                        or not self._attr_fan_speed
                    )
                )
                and self.model_code
                and self.model_code.startswith("T2320")
                and self.vacuum is not None
            ):
                try:
                    await self.vacuum.async_set(
                        {
                            self._get_dps_code(
                                "FAN_SPEED"
                            ): self.vacuum.getRoboVacCommandValue(
                                RobovacCommand.FAN_SPEED, "max"
                            )
                        }
                    )
                    await asyncio.sleep(0.5)
                    await self.async_update()
                except Exception as ex:
                    _LOGGER.debug("Startup probe failed: %s", ex)

            # If state is still unknown after sync attempts, failover to Docked
            if self._attr_tuya_state is None or self._attr_tuya_state == 0:
                self._attr_tuya_state = "Charging"  # maps to DOCKED via activity()
            # Publish what we have after startup syncing
            self.async_write_ha_state()
        except Exception as e:
            _LOGGER.debug("Initial update failed: %s", e)

    async def async_update(self) -> None:
        """Synchronize state from the vacuum.

        This method is called periodically by Home Assistant to update the entity state.
        It retrieves the current state from the vacuum via the Tuya API and updates
        the entity attributes accordingly.

        If the vacuum is not supported or the IP address is not set, the method returns
        early. If the update fails, it increments a failure counter and sets an error
        code after a certain number of retries.
        """
        # Skip update if the model is not supported
        if self._attr_error_code == "UNSUPPORTED_MODEL":
            _LOGGER.debug(
                "Skipping update for unsupported model: %s", self._attr_model_code
            )
            return

        # Skip update if the IP address is not set
        if not self.ip_address:
            _LOGGER.warning(
                "Cannot update vacuum %s: IP address not set", self._attr_name
            )
            self._attr_error_code = "IP_ADDRESS"
            return

        # Skip update if vacuum object is not initialized
        if self.vacuum is None:
            _LOGGER.warning("Cannot update %s: vacuum not initialized", self._attr_name)
            self._attr_error_code = "INITIALIZATION_FAILED"
            return

        # Try to update the vacuum state
        try:
            await self.vacuum.async_get()
            self.update_failures = 0
            self.update_entity_values()
            await self._async_fetch_room_names_from_oauth_once()
            _LOGGER.debug("Successfully updated vacuum %s", self._attr_name)
        except TuyaException as e:
            self.update_failures += 1
            _LOGGER.warning(
                "Failed to update vacuum %s. Failure count: %d/%d. Error: %s",
                self._attr_name,
                self.update_failures,
                UPDATE_RETRIES,
                str(e),
            )

            # Set error code after maximum retries
            if self.update_failures >= UPDATE_RETRIES:
                self._attr_error_code = "CONNECTION_FAILED"
                _LOGGER.error(
                    "Maximum update retries reached for vacuum %s. Marking as unavailable",
                    self._attr_name,
                )

    async def pushed_update_handler(self) -> None:
        """Handle updates pushed from the vacuum.

        This method is called when the vacuum sends an update via the Tuya API.
        It updates the entity values and writes the state to Home Assistant.
        """
        self.update_entity_values()
        self.async_write_ha_state()

    def update_entity_values(self) -> None:
        """Update entity values from the vacuum's data points.

        This method updates all the entity attributes based on the current
        state of the vacuum's data points (DPS). It handles different vacuum models
        and ensures that all values are properly typed and formatted.

        The method is called both during periodic updates and when pushed updates
        are received from the vacuum.
        """
        # Skip if vacuum is not initialized
        if self.vacuum is None:
            _LOGGER.warning("Cannot update entity values: vacuum not initialized")
            return

        # Get the current data points from the vacuum
        self.tuyastatus = self.vacuum._dps

        if self.tuyastatus is None or not self.tuyastatus:
            _LOGGER.warning("Cannot update entity values: no data points available")
            return

        _LOGGER.debug("Updating entity values from data points: %s", self.tuyastatus)

        # Update common attributes for all models
        self._update_battery_level()
        self._update_state_and_error()
        self._update_mode_and_fan_speed()
        self._update_locate_state()

        # Update model-specific attributes
        self._update_cleaning_stats()
        self._update_room_names_from_device_payload()

    def _get_dps_code(self, code_name: str) -> str:
        """Get the DPS code for a specific function.

        First checks for model-specific DPS codes, then falls back to defaults.

        Args:
            code_name: The name of the code to retrieve, e.g., "BATTERY_LEVEL"

        Returns:
            The DPS code as a string
        """
        if self.vacuum is None:
            enum_value = getattr(TuyaCodes, code_name, None)
            return enum_value.value if enum_value else ""

        model_dps_codes = self.vacuum.getDpsCodes()
        if code_name in model_dps_codes:
            return model_dps_codes[code_name]

        enum_value = getattr(TuyaCodes, code_name, None)
        return enum_value.value if enum_value else ""

    def _get_consumables_codes(self) -> list[str]:
        """Get the consumables DPS codes.

        First checks for model-specific codes, then falls back to defaults.

        Returns:
            A list of DPS codes for consumables
        """
        if self.vacuum is None:
            return TUYA_CONSUMABLES_CODES

        # Get model-specific DPS codes
        model_dps_codes = self.vacuum.getDpsCodes()

        # Return model-specific code if available, otherwise use default
        if "CONSUMABLES" in model_dps_codes:
            # Model-specific consumables can be a list or comma-separated string
            consumables = model_dps_codes["CONSUMABLES"]
            if isinstance(consumables, str):
                return [code.strip() for code in consumables.split(",")]
            return consumables

        # Fall back to default codes
        return TUYA_CONSUMABLES_CODES

    def _update_battery_level(self) -> None:
        """Update the battery level attribute."""
        if self.tuyastatus is None:
            return

        battery_level = self.tuyastatus.get(self._get_dps_code("BATTERY_LEVEL"))

        # Ensure battery level is an integer between 0 and 100
        if battery_level is not None:
            try:
                self._attr_battery_level = int(battery_level)
                # Ensure the value is within valid range
                self._attr_battery_level = max(0, min(100, self._attr_battery_level))
            except (ValueError, TypeError):
                _LOGGER.warning("Invalid battery level value: %s", battery_level)
                self._attr_battery_level = 0
        else:
            self._attr_battery_level = 0

    def _update_state_and_error(self) -> None:
        """Update the state and error code attributes."""
        if self.tuyastatus is None:
            return

        # Get state and error code from data points using model-specific DPS codes
        tuya_state = self.tuyastatus.get(self._get_dps_code("STATUS"))
        error_code = self.tuyastatus.get(self._get_dps_code("ERROR_CODE"))

        # Update state attribute
        if tuya_state is not None and self.vacuum is not None:
            self._attr_tuya_state = self.vacuum.getRoboVacHumanReadableValue(
                RobovacCommand.STATUS, tuya_state
            )
            _LOGGER.debug(
                "in _update_state_and_error, tuya_state: %s, self._attr_tuya_state: %s.",
                tuya_state,
                self._attr_tuya_state,
            )
        else:
            # Do not regress to Unknown (0). If we have no new STATUS, keep
            # the last known state; if none exists yet (boot), failover to
            # a safe default of Docked/Charging so HA doesn't show Unknown.
            if self._attr_tuya_state in (None, 0):
                self._attr_tuya_state = "Charging"

        # Update error code attribute
        if error_code is not None and self.vacuum is not None:
            self._attr_error_code = self.vacuum.getRoboVacHumanReadableValue(
                RobovacCommand.ERROR, error_code
            )
            _LOGGER.debug(
                "in _update_state_and_error, error_code: %s, self._attr_error_code: %s.",
                error_code,
                self._attr_error_code,
            )
        else:
            self._attr_error_code = 0

    def _update_mode_and_fan_speed(self) -> None:
        """Update the mode and fan speed attributes."""
        if self.tuyastatus is None:
            return

        # Get mode and fan speed from data points using model-specific DPS codes
        mode = self.tuyastatus.get(self._get_dps_code("MODE"))
        fan_speed = self.tuyastatus.get(self._get_dps_code("FAN_SPEED"))

        # Update mode attribute
        if mode is not None and self.vacuum is not None:
            previous_mode = self._attr_mode
            self._attr_mode = self.vacuum.getRoboVacHumanReadableValue(
                RobovacCommand.MODE, mode
            )
            self._last_mode_value = self._attr_mode
            # Record when we entered return mode so we can flip to docked
            # if the device doesn't provide an explicit charging status token.
            try:
                if self._attr_mode == "return" and previous_mode != "return":
                    self._last_return_ts = time.time()
            except Exception:
                pass
            _LOGGER.debug(
                "in _update_mode_and_fan_speed, mode: %s, self._attr_mode: %s.",
                mode,
                self._attr_mode,
            )
        else:
            self._attr_mode = ""

        # Update fan speed attribute; avoid clearing to Unknown if not present
        if fan_speed is not None:
            self._attr_fan_speed = fan_speed

        # Format fan speed for display
        if isinstance(self.fan_speed, str):
            if self.fan_speed == "No_suction":
                self._attr_fan_speed = "No Suction"
            elif self.fan_speed == "Boost_IQ":
                self._attr_fan_speed = "Boost IQ"
            elif self.fan_speed == "Quiet":
                self._attr_fan_speed = "Pure"

    def _update_locate_state(self) -> None:
        """Track locate state for models with explicit on/off DPS codes."""
        if (
            self.tuyastatus is None
            or self.model_code is None
            or not self.model_code.startswith("T2320")
        ):
            return

        locate_code = self._get_dps_code("LOCATE")
        if locate_code and locate_code in self.tuyastatus:
            self._locate_active = bool(self.tuyastatus.get(locate_code))

    def _update_cleaning_stats(self) -> None:
        """Update cleaning statistics (area and time)."""
        if self.tuyastatus is None:
            return

        # Update cleaning area using model-specific DPS code
        cleaning_area = self.tuyastatus.get(self._get_dps_code("CLEANING_AREA"))
        if cleaning_area is not None:
            self._attr_cleaning_area = str(cleaning_area)

        # Update cleaning time using model-specific DPS code
        cleaning_time = self.tuyastatus.get(self._get_dps_code("CLEANING_TIME"))
        if cleaning_time is not None:
            self._attr_cleaning_time = str(cleaning_time)

            # Update other attributes using model-specific DPS codes
            auto_return = self.tuyastatus.get(self._get_dps_code("AUTO_RETURN"))
            self._attr_auto_return = (
                str(auto_return) if auto_return is not None else None
            )

            do_not_disturb = self.tuyastatus.get(self._get_dps_code("DO_NOT_DISTURB"))
            self._attr_do_not_disturb = (
                str(do_not_disturb) if do_not_disturb is not None else None
            )

            boost_iq = self.tuyastatus.get(self._get_dps_code("BOOST_IQ"))
            self._attr_boost_iq = str(boost_iq) if boost_iq is not None else None

        # Handle consumables
        if (
            isinstance(self.robovac_supported, int)
            and self.robovac_supported & RoboVacEntityFeature.CONSUMABLES
            and self.tuyastatus is not None
        ):
            # Use model-specific consumables codes
            for CONSUMABLE_CODE in self._get_consumables_codes():
                if (
                    CONSUMABLE_CODE in self.tuyastatus
                    and self.tuyastatus.get(CONSUMABLE_CODE) is not None
                ):
                    consumable_data = self.tuyastatus.get(CONSUMABLE_CODE)
                    if isinstance(consumable_data, str):
                        try:
                            consumables = ast.literal_eval(
                                base64.b64decode(consumable_data).decode("ascii")
                            )
                            if (
                                "consumable" in consumables
                                and "duration" in consumables["consumable"]
                            ):
                                self._attr_consumables = consumables["consumable"][
                                    "duration"
                                ]
                        except Exception as e:
                            _LOGGER.warning(
                                "Failed to decode consumable data: %s", str(e)
                            )

    def _refresh_room_names_attr(self) -> None:
        """Refresh exported room names and notify listeners."""
        if self._room_name_registry:
            self._attr_room_names = {
                key: {
                    "id": entry.get("id"),
                    "key": entry.get("key", key),
                    "label": entry.get("label"),
                    "device_label": entry.get("device_label"),
                    "source": entry.get("source", "device"),
                }
                for key, entry in sorted(self._room_name_registry.items())
            }
        else:
            self._attr_room_names = None

        for listener in list(self._room_name_listeners):
            try:
                listener()
            except Exception:
                _LOGGER.exception("Room name listener raised an exception")

    def _normalize_room_entry(
        self, identifier: Any, label: Any, source: str
    ) -> dict[str, Any]:
        """Build a normalized room entry payload."""
        key = str(identifier)
        room_label = label.strip() if isinstance(label, str) else ""
        if not room_label:
            room_label = key
        return {
            "id": identifier,
            "key": key,
            "label": room_label,
            "device_label": room_label,
            "source": source,
        }

    def _merge_room_entries(self, entries: dict[str, dict[str, Any]]) -> bool:
        """Merge room entries into the registry."""
        changed = False
        for key, entry in entries.items():
            if self._room_name_registry.get(key) != entry:
                self._room_name_registry[key] = entry
                changed = True
        if changed:
            self._refresh_room_names_attr()
        return changed

    def _extract_rooms_from_json(
        self, payload: dict[str, Any]
    ) -> dict[str, dict[str, Any]]:
        """Extract room names from JSON payload shapes."""
        candidates: list[Any] = []

        if isinstance(payload.get("data"), dict):
            data = payload["data"]
            if isinstance(data.get("rooms"), list):
                candidates.append(data.get("rooms"))
        if isinstance(payload.get("rooms"), list):
            candidates.append(payload.get("rooms"))

        for room_list in candidates:
            parsed: dict[str, dict[str, Any]] = {}
            for room in room_list:
                if not isinstance(room, dict):
                    continue
                identifier = (
                    room.get("roomId")
                    or room.get("room_id")
                    or room.get("roomID")
                    or room.get("segmentId")
                    or room.get("segment_id")
                    or room.get("id")
                )
                if identifier is None:
                    continue
                label = (
                    room.get("roomName")
                    or room.get("room_name")
                    or room.get("segmentName")
                    or room.get("segment_name")
                    or room.get("label")
                    or room.get("name")
                )
                entry = self._normalize_room_entry(identifier, label, "device")
                parsed[str(identifier)] = entry
            if parsed:
                return parsed

        return {}

    def _decode_room_payload(self, payload: Any) -> dict[str, dict[str, Any]]:
        """Decode ROOM_CLEAN payload into room entries."""
        if payload is None:
            return {}

        payload_dict: dict[str, Any] | None = None
        payload_bytes: bytes | None = None

        if isinstance(payload, dict):
            payload_dict = payload
        elif isinstance(payload, (bytes, bytearray, memoryview)):
            payload_bytes = bytes(payload)
        elif isinstance(payload, str):
            text = payload.strip()
            if not text:
                return {}
            try:
                payload_dict = json.loads(text)
            except ValueError:
                try:
                    payload_bytes = base64.b64decode(text, validate=True)
                except (binascii.Error, ValueError):
                    try:
                        payload_bytes = base64.b64decode(text)
                    except (binascii.Error, ValueError):
                        payload_bytes = text.encode("utf-8")
        else:
            return {}

        if payload_dict is None and payload_bytes is not None:
            try:
                payload_dict = json.loads(payload_bytes.decode("utf-8"))
            except (ValueError, UnicodeDecodeError):
                payload_dict = None

        if payload_dict is not None:
            parsed = self._extract_rooms_from_json(payload_dict)
            if parsed:
                return parsed

        if payload_bytes is None:
            return {}

        parsed_binary: dict[str, dict[str, Any]] = {}
        for identifier, label in decode_binary_room_list(payload_bytes):
            parsed_binary[str(identifier)] = self._normalize_room_entry(
                identifier,
                label,
                "device",
            )
        if parsed_binary:
            return parsed_binary

        known_entries = []
        if isinstance(payload, (str, bytes, bytearray, memoryview)):
            known_entries = lookup_known_room_clean_payload(payload)
        return {
            str(identifier): self._normalize_room_entry(identifier, label, "device")
            for identifier, label in known_entries
        }

    def _decode_t2320_room_meta_payload(
        self, payload: Any
    ) -> dict[str, dict[str, Any]]:
        """Decode T2320 room metadata payload (DP 165)."""
        raw: bytes | None = None

        if isinstance(payload, (bytes, bytearray, memoryview)):
            raw = bytes(payload)
        elif isinstance(payload, str):
            text = payload.strip()
            if not text:
                return {}
            try:
                raw = base64.b64decode(text, validate=True)
            except (binascii.Error, ValueError):
                try:
                    raw = base64.b64decode(text)
                except (binascii.Error, ValueError):
                    raw = None

        if not raw:
            return {}

        try:
            top = self._parse_protobuf_message(raw)
        except ValueError:
            return {}

        parsed: dict[str, dict[str, Any]] = {}
        for entry_payload in top.get(2, []):
            if not isinstance(entry_payload, (bytes, bytearray, memoryview)):
                continue
            try:
                room_fields = self._parse_protobuf_message(bytes(entry_payload))
            except ValueError:
                continue

            identifier = None
            for value in room_fields.get(1, []):
                if isinstance(value, int):
                    identifier = value
                    break

            if identifier is None:
                continue

            label: str | None = None
            for value in room_fields.get(2, []):
                if not isinstance(value, (bytes, bytearray, memoryview)):
                    continue
                try:
                    candidate = bytes(value).decode("utf-8").strip()
                except UnicodeDecodeError:
                    continue
                if candidate:
                    label = candidate
                    break

            parsed[str(identifier)] = self._normalize_room_entry(
                identifier,
                label,
                "device",
            )

        return parsed

    def _parse_protobuf_message(self, message: bytes) -> dict[int, list[int | bytes]]:
        """Parse a minimal protobuf payload into a field mapping."""
        offset = 0
        result: dict[int, list[int | bytes]] = {}

        while offset < len(message):
            tag, offset = self._read_protobuf_varint(message, offset)
            field_number = tag >> 3
            wire_type = tag & 0x07

            if wire_type == 0:
                value, offset = self._read_protobuf_varint(message, offset)
            elif wire_type == 2:
                size, offset = self._read_protobuf_varint(message, offset)
                if offset + size > len(message):
                    raise ValueError("invalid protobuf payload")
                value = message[offset : offset + size]
                offset += size
            elif wire_type == 1:
                if offset + 8 > len(message):
                    raise ValueError("invalid protobuf payload")
                value = message[offset : offset + 8]
                offset += 8
            elif wire_type == 5:
                if offset + 4 > len(message):
                    raise ValueError("invalid protobuf payload")
                value = message[offset : offset + 4]
                offset += 4
            else:
                raise ValueError("unsupported protobuf wire type")

            result.setdefault(field_number, []).append(value)

        return result

    def _read_protobuf_varint(self, buffer: bytes, offset: int) -> tuple[int, int]:
        """Read a protobuf varint from *buffer*."""
        result = 0
        shift = 0

        while offset < len(buffer):
            byte = buffer[offset]
            offset += 1
            result |= (byte & 0x7F) << shift
            if not (byte & 0x80):
                return result, offset
            shift += 7
            if shift >= 64:
                break

        raise ValueError("invalid varint")

    def _update_room_names_from_device_payload(self) -> None:
        """Update room registry from local Tuya payload for T2320."""
        if (
            self.model_code is None
            or not self.model_code.startswith("T2320")
            or self.tuyastatus is None
        ):
            return

        room_meta_code = self._get_dps_code("ROOM_META")
        if room_meta_code:
            room_meta_payload = self.tuyastatus.get(room_meta_code)
            parsed_meta = self._decode_t2320_room_meta_payload(room_meta_payload)
            if parsed_meta:
                self._merge_room_entries(parsed_meta)
                return

        room_clean_code = self._get_dps_code("ROOM_CLEAN")
        if not room_clean_code:
            room_clean_code = TuyaCodes.ROOM_CLEAN
        payload = self.tuyastatus.get(room_clean_code)
        parsed = self._decode_room_payload(payload)
        if parsed:
            self._merge_room_entries(parsed)

    def _fetch_room_names_from_eufy_oauth(self) -> dict[str, dict[str, Any]]:
        """Fetch room names from Eufy cloud APIs for T2320."""
        username = self._eufy_username
        password = self._eufy_password
        if not username or not password:
            return {}

        eufy_session = EufyLogon(username, password)
        response = eufy_session.get_user_info()
        if response is None or response.status_code != 200:
            return {}

        user_response = response.json()
        if user_response.get("res_code") != 1:
            return {}

        user_info = user_response.get("user_info", {})
        request_host = user_info.get("request_host")
        user_id = user_info.get("id")
        access_token = user_response.get("access_token")
        if not request_host or not user_id or not access_token:
            return {}

        response = eufy_session.get_device_info(request_host, user_id, access_token)
        if response is None or response.status_code != 200:
            return {}

        payload = response.json()
        devices = payload.get("devices")
        if not isinstance(devices, list):
            items = payload.get("items")
            if isinstance(items, list):
                devices = [item.get("device", item) for item in items]
            else:
                devices = []

        target_device: dict[str, Any] | None = None
        for candidate in devices:
            if not isinstance(candidate, dict):
                continue
            if str(candidate.get("id")) == str(self.unique_id):
                target_device = candidate
                break

        if target_device is None:
            return {}

        extracted = self._search_nested_room_lists(target_device)
        return {
            str(identifier): self._normalize_room_entry(identifier, label, "cloud")
            for identifier, label in extracted
        }

    def _search_nested_room_lists(self, value: Any) -> list[tuple[Any, str]]:
        """Find likely room lists in nested JSON payloads."""
        found: list[tuple[Any, str]] = []

        def _visit(node: Any) -> None:
            nonlocal found
            if isinstance(node, dict):
                _parse_candidate_list(node.get("rooms"))
                for nested in node.values():
                    _visit(nested)
                return

            if isinstance(node, list):
                _parse_candidate_list(node)
                for nested in node:
                    _visit(nested)
                return

            if isinstance(node, str) and node and node[0] in "[{":
                try:
                    decoded = json.loads(node)
                except ValueError:
                    return
                _visit(decoded)

        def _parse_candidate_list(candidate: Any) -> None:
            if not isinstance(candidate, list):
                return
            parsed: list[tuple[Any, str]] = []
            for item in candidate:
                if not isinstance(item, dict):
                    return
                identifier = (
                    item.get("roomId")
                    or item.get("room_id")
                    or item.get("roomID")
                    or item.get("segmentId")
                    or item.get("segment_id")
                    or item.get("id")
                )
                label = (
                    item.get("roomName")
                    or item.get("room_name")
                    or item.get("segmentName")
                    or item.get("segment_name")
                    or item.get("label")
                    or item.get("name")
                )
                if identifier is None or not isinstance(label, str):
                    continue
                trimmed = label.strip()
                if not trimmed:
                    continue
                parsed.append((identifier, trimmed))

            if parsed:
                found.extend(parsed)

        _visit(value)

        deduped: dict[str, tuple[Any, str]] = {}
        for identifier, label in found:
            key = str(identifier)
            if key not in deduped:
                deduped[key] = (identifier, label)
        return list(deduped.values())

    async def _async_fetch_room_names_from_oauth_once(self) -> None:
        """Fetch room names from cloud once if local payload has none."""
        if self._cloud_room_lookup_attempted:
            return
        if self.model_code is None or not self.model_code.startswith("T2320"):
            return
        if self._attr_room_names:
            return
        if self.hass is None:
            return

        self._cloud_room_lookup_attempted = True
        try:
            cloud_rooms = await self.hass.async_add_executor_job(
                self._fetch_room_names_from_eufy_oauth
            )
        except Exception as err:
            _LOGGER.debug("Failed cloud room lookup for %s: %s", self._attr_name, err)
            return

        if cloud_rooms and self._merge_room_entries(cloud_rooms):
            self.async_write_ha_state()

    def add_room_name_listener(
        self, listener: Callable[[], None]
    ) -> Callable[[], None]:
        """Register callbacks for room metadata updates."""
        self._room_name_listeners.add(listener)

        def _remove() -> None:
            self._room_name_listeners.discard(listener)

        return _remove

    async def async_locate(self, **kwargs: Any) -> None:
        """Locate the vacuum cleaner.

        Args:
            **kwargs: Additional arguments passed from Home Assistant.
        """
        _LOGGER.debug("Locate Pressed")
        if self.vacuum is None:
            _LOGGER.error("Cannot locate vacuum: vacuum not initialized")
            return

        locate_code = self._get_dps_code("LOCATE")

        if self.model_code and self.model_code.startswith("T2320"):
            # T2320 exposes a binary DPS for locate (160) where True starts
            # the beeper and False stops it. Track the last commanded state so
            # the locate button can act as a toggle even if the device resets
            # the DPS value between updates.
            if locate_code:
                # Refresh the cached locate state from the most recent DPS
                # payload when available to keep the toggle in sync with the
                # vacuum's last reported status.
                if self.tuyastatus is not None and locate_code in self.tuyastatus:
                    self._locate_active = bool(self.tuyastatus.get(locate_code))

                target_state = not self._locate_active
                await self.vacuum.async_set({locate_code: target_state})
                self._locate_active = target_state
            return

        if self.tuyastatus is not None and self.tuyastatus.get(locate_code):
            await self.vacuum.async_set({locate_code: False})
        else:
            await self.vacuum.async_set({locate_code: True})

    async def async_identify(self, **kwargs: Any) -> None:
        """Identify the device via Matter/Apple Home Identify command."""
        await self.async_locate()

    async def async_return_to_base(self, **kwargs: Any) -> None:
        """Set the vacuum cleaner to return to the dock.

        Args:
            **kwargs: Additional arguments passed from Home Assistant.
        """
        _LOGGER.debug("Return home Pressed")
        if self.vacuum is None:
            _LOGGER.error("Cannot return to base: vacuum not initialized")
            return

        await self.vacuum.async_set(
            {
                self._get_dps_code("RETURN_HOME"): self.vacuum.getRoboVacCommandValue(
                    RobovacCommand.RETURN_HOME, "return"
                )
            }
        )

    async def async_start(self, **kwargs: Any) -> None:
        """Start the vacuum cleaner in auto mode.

        Args:
            **kwargs: Additional arguments passed from Home Assistant.
        """
        self._attr_mode = "auto"
        if self.vacuum is None:
            _LOGGER.error("Cannot start vacuum: vacuum not initialized")
            return

        await self.vacuum.async_set(
            {
                self._get_dps_code("MODE"): self.vacuum.getRoboVacCommandValue(
                    RobovacCommand.MODE, "auto"
                )
            }
        )

    async def async_pause(self, **kwargs: Any) -> None:
        """Pause the vacuum cleaner.

        Args:
            **kwargs: Additional arguments passed from Home Assistant.
        """
        if self.vacuum is None:
            _LOGGER.error("Cannot pause vacuum: vacuum not initialized")
            return

        await self.vacuum.async_set(
            {
                self._get_dps_code("START_PAUSE"): self.vacuum.getRoboVacCommandValue(
                    RobovacCommand.START_PAUSE, "pause"
                )
            }
        )

    async def async_stop(self, **kwargs: Any) -> None:
        """Stop the vacuum cleaner.

        Args:
            **kwargs: Additional arguments passed from Home Assistant.
        """
        await self.async_return_to_base()

    async def async_clean_spot(self, **kwargs: Any) -> None:
        """Perform a spot clean.

        Args:
            **kwargs: Additional arguments passed from Home Assistant.
        """
        _LOGGER.debug("Spot Clean Pressed")
        if self.vacuum is None:
            _LOGGER.error("Cannot clean spot: vacuum not initialized")
            return

        await self.vacuum.async_set(
            {
                self._get_dps_code("MODE"): self.vacuum.getRoboVacCommandValue(
                    RobovacCommand.MODE, "spot"
                )
            }
        )

    async def async_set_fan_speed(self, fan_speed: str, **kwargs: Any) -> None:
        """Set fan speed.

        Args:
            fan_speed: The fan speed to set.
            **kwargs: Additional arguments passed from Home Assistant.
        """
        _LOGGER.debug("Fan Speed Selected: %s", fan_speed)
        if self.vacuum is None:
            _LOGGER.error("Cannot set fan speed: vacuum not initialized")
            return

        normalized_fan_speed = fan_speed.lower().replace(" ", "_")

        _LOGGER.debug("Normalized Fan Speed: %s", normalized_fan_speed)

        await self.vacuum.async_set(
            {
                self._get_dps_code("FAN_SPEED"): self.vacuum.getRoboVacCommandValue(
                    RobovacCommand.FAN_SPEED, normalized_fan_speed
                )
            }
        )

    async def async_send_command(
        self, command: str, params: dict[str, Any] | list | None = None, **kwargs: Any
    ) -> None:
        """Send a command to a vacuum cleaner.

        Args:
            command: The command to send.
            params: Optional parameters for the command.
            **kwargs: Additional arguments passed from Home Assistant.
        """
        _LOGGER.debug("Send Command %s Pressed", command)
        if self.vacuum is None:
            _LOGGER.error("Cannot send command: vacuum not initialized")
            return

        # Mode commands
        mode_commands = {
            "edgeClean": "edge",
            "smallRoomClean": "small_room",
            "autoClean": "auto",
        }

        if command in mode_commands:
            command_data = self._get_mode_command_data(mode_commands[command])
            if command_data:
                await self.vacuum.async_set(command_data)
        elif command == "autoReturn":
            # Toggle the auto return setting
            new_value = not self._is_value_true(self.auto_return)
            await self.vacuum.async_set({self._get_dps_code("AUTO_RETURN"): new_value})
        elif command == "doNotDisturb":
            # Toggle the do not disturb setting
            new_value = not self._is_value_true(self.do_not_disturb)
            await self.vacuum.async_set(
                {self._get_dps_code("DO_NOT_DISTURB"): new_value}
            )
        elif command == "boostIQ":
            # Toggle the boost IQ setting
            new_value = not self._is_value_true(self.boost_iq)
            await self.vacuum.async_set({self._get_dps_code("BOOST_IQ"): new_value})
        elif command == "roomClean" and params is not None and isinstance(params, dict):
            room_ids = params.get("roomIds", [1])
            count = params.get("count", 1)
            clean_request = {"roomIds": room_ids, "cleanTimes": count}
            method_call = {
                "method": "selectRoomsClean",
                "data": clean_request,
                "timestamp": round(time.time() * 1000),
            }
            json_str = json.dumps(method_call, separators=(",", ":"))
            base64_str = base64.b64encode(json_str.encode("utf8")).decode("utf8")
            _LOGGER.debug("roomClean call %s", json_str)
            room_clean_code = self._get_dps_code("ROOM_CLEAN")
            if not room_clean_code:
                room_clean_code = TuyaCodes.ROOM_CLEAN
            await self.vacuum.async_set({room_clean_code: base64_str})

    async def async_will_remove_from_hass(self) -> None:
        """Handle removal from Home Assistant."""
        if self.vacuum is None:
            _LOGGER.debug("Cannot disable vacuum: vacuum not initialized")
            return

        await self.vacuum.async_disable()
