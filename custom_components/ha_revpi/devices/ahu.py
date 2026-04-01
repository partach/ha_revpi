"""AHU building device handler."""

from __future__ import annotations

import logging
from typing import Any

from .base import BuildingDeviceHandler

_LOGGER = logging.getLogger(__name__)

# Roles that the climate entity manages directly (not created as standalone entities)
_CLIMATE_ROLES = {"fan_command", "fan_status", "current_temperature"}

# Roles that get output monitoring sensors (analog outputs shown as % sensors)
_OUTPUT_MONITOR_ROLES = {
    "heating_valve",
    "cooling_valve",
    "damper_position",
}

# Roles that get alarm binary sensors
_ALARM_ROLES = {"filter_alarm", "frost_alarm", "fire_alarm"}

# Roles that get standalone analog input sensors (temperatures, pressures)
_ANALOG_SENSOR_ROLES = {
    "outdoor_temperature",
    "return_temperature",
    "pre_heater_temperature",
    "post_heater_temperature",
    "supply_pressure",
    "return_pressure",
    "exhaust_temperature",
}


class AHUHandler(BuildingDeviceHandler):
    """Handler for Air Handling Unit devices.

    Creates a ClimateEntity plus optional binary sensors for alarms,
    analogue sensors for valve/damper monitoring and temperature/pressure
    readings, and switch entities for auxiliary equipment (pumps, exhaust
    fan, fire damper, heat wheel).
    If a PID control section is defined, also creates PID tuning entities.
    """

    device_type = "ahu"

    def get_entities(self) -> list[Any]:
        """Create HA entities for this AHU."""
        from ..climate import RevPiBuildingClimate
        from ..pid_entities import create_pid_entities
        from ..sensor import RevPiBuildingAnalogSensor, RevPiBuildingBinarySensor
        from ..switch import RevPiBuildingSwitch

        entities: list[Any] = []

        # Primary climate entity
        entities.append(RevPiBuildingClimate(self))

        for mapping in self.ios.values():
            # Skip roles handled inside the climate entity
            if mapping.role in _CLIMATE_ROLES:
                continue

            # Alarm binary sensors
            if mapping.role in _ALARM_ROLES:
                entities.append(
                    RevPiBuildingBinarySensor(self, mapping, device_class="problem")
                )
            # Exhaust filter alarm (same as supply filter, just different IO)
            elif mapping.role == "exhaust_filter_alarm":
                entities.append(
                    RevPiBuildingBinarySensor(self, mapping, device_class="problem")
                )
            # Output monitoring sensors (valve %, damper %)
            elif mapping.role in _OUTPUT_MONITOR_ROLES and mapping.direction == "output":
                entities.append(RevPiBuildingAnalogSensor(self, mapping))
            # Analog input sensors (extra temperatures, pressures)
            elif mapping.role in _ANALOG_SENSOR_ROLES and mapping.direction == "input":
                entities.append(RevPiBuildingAnalogSensor(self, mapping))
            # Auxiliary bool outputs as switches (pump, exhaust fan, fire damper, heat wheel)
            elif mapping.role in (
                "pump_command",
                "exhaust_fan_command",
                "fire_damper",
                "heat_wheel_command",
            ):
                entities.append(RevPiBuildingSwitch(self, mapping))
            # Auxiliary bool inputs as binary sensors (exhaust fan status, etc.)
            elif mapping.role in (
                "exhaust_fan_status",
                "pump_status",
            ):
                entities.append(
                    RevPiBuildingBinarySensor(self, mapping, device_class="running")
                )

        # PID controller entities (switch, parameter numbers, output sensor)
        entities.extend(create_pid_entities(self))

        return entities


HANDLER_CLASS = AHUHandler
