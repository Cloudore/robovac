"""Eufy Robot Vacuum and Mop X9 Pro with Auto-Clean Station (T2320)"""
from homeassistant.components.vacuum import VacuumEntityFeature
from .base import RoboVacEntityFeature, RobovacCommand, RobovacModelDetails


class T2320(RobovacModelDetails):
    homeassistant_features = (
        VacuumEntityFeature.BATTERY
        | VacuumEntityFeature.FAN_SPEED
        | VacuumEntityFeature.LOCATE
        | VacuumEntityFeature.PAUSE
        | VacuumEntityFeature.RETURN_HOME
        | VacuumEntityFeature.SEND_COMMAND
        | VacuumEntityFeature.START
        | VacuumEntityFeature.STATE
        | VacuumEntityFeature.STOP
        | getattr(VacuumEntityFeature, "WATER_LEVEL", 0)
        | getattr(VacuumEntityFeature, "MOP_MODE", 0)
    )
    robovac_features = (
        RoboVacEntityFeature.DO_NOT_DISTURB
        | RoboVacEntityFeature.BOOST_IQ
        | RoboVacEntityFeature.WATER_LEVEL
        | RoboVacEntityFeature.MOP_MODE
    )
    # Align DP codes/values with field logs (similar to T2267/L60 layout)
    commands = {
        # Pause is applied via MODE DP (152) on this model
        RobovacCommand.START_PAUSE: {
            "code": 152,
            "values": {
                "pause": "AggN",
            },
        },
        # Mode selection is DP 152 using Tuya base64 tokens
        RobovacCommand.MODE: {
            "code": 152,
            "values": {
                # Bidirectional mapping: human -> token and token -> human
                # human -> token (for sending commands)
                "auto": "BBoCCAE=",
                "pause": "AggN",
                "spot": "AA==",
                "return": "AggG",
                "nosweep": "AggO",
                # token -> human (for decoding DPS -> readable mode)
                "BBoCCAE=": "auto",
                "AggN": "pause",
                "AA==": "spot",
                "AggG": "return",
                "AggO": "nosweep",
            },
        },
        # Status reports via DP 153 (base64-encoded status payloads)
        RobovacCommand.STATUS: {
            "code": 173,
        },
        # Return home is triggered via MODE DP (152) on this model
        RobovacCommand.RETURN_HOME: {
            "code": 152,
            "values": {
                "return": "AggG",
            },
        },
        # Fan speed is DP 158 with human-readable values
        RobovacCommand.FAN_SPEED: {
            "code": 158,
            "values": {
                "quiet": "Quiet",
                "standard": "Standard",
                "turbo": "Turbo",
                "max": "Max",
            },
        },
        # Mop mode selection is DP 161
        RobovacCommand.MOP_MODE: {
            "code": 161,
            "values": {
                "standard": "Standard",
                "deep": "Deep",
            },
        },
        # Water level control is DP 162
        RobovacCommand.WATER_LEVEL: {
            "code": 162,
            "values": {
                "low": "Low",
                "medium": "Medium",
                "high": "High",
            },
        },
        # Locate/beep is DP 160
        RobovacCommand.LOCATE: {
            "code": 160,
        },
        # Battery level is DP 172
        RobovacCommand.BATTERY: {
            "code": 172,
        },
        # Error reports are DP 169
        RobovacCommand.ERROR: {
            "code": 169,
        },
    }
