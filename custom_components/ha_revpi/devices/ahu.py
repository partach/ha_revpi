"""AHU building device handler."""

from __future__ import annotations

import logging
from typing import Any

from .base import BuildingDeviceHandler

_LOGGER = logging.getLogger(__name__)


class AHUHandler(BuildingDeviceHandler):
    """Handler for Air Handling Unit devices.

    Creates a ClimateEntity plus optional binary sensors for alarms
    and analogue sensors for valve/damper monitoring.
    """

    device_type = "ahu"

    def get_entities(self) -> list[Any]:
        """Create HA entities for this AHU."""
        from ..climate import RevPiBuildingClimate
        from ..sensor import RevPiBuildingAnalogSensor, RevPiBuildingBinarySensor

        entities: list[Any] = []

        # Primary climate entity
        entities.append(RevPiBuildingClimate(self))

        # Alarm binary sensors
        for mapping in self.ios.values():
            if mapping.role in ("filter_alarm", "frost_alarm"):
                entities.append(
                    RevPiBuildingBinarySensor(self, mapping, device_class="problem")
                )
            elif (
                mapping.role in ("heating_valve", "cooling_valve", "damper_position")
                and mapping.direction == "output"
            ):
                entities.append(RevPiBuildingAnalogSensor(self, mapping))

        return entities


HANDLER_CLASS = AHUHandler
