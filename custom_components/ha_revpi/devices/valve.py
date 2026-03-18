"""Valve building device handler."""

from __future__ import annotations

from typing import Any

from .base import BuildingDeviceHandler


class ValveHandler(BuildingDeviceHandler):
    """Handler for modulating valve devices.

    Creates a NumberEntity (0-100%) for valve position control
    and an optional feedback sensor.
    """

    device_type = "valve"

    def get_entities(self) -> list[Any]:
        """Create HA entities for this valve."""
        from ..number import RevPiBuildingValveNumber
        from ..sensor import RevPiBuildingAnalogSensor

        entities: list[Any] = []

        cmd = self.get_io_by_role("position_command")
        if cmd:
            entities.append(RevPiBuildingValveNumber(self, cmd))

        fb = self.get_io_by_role("position_feedback")
        if fb:
            entities.append(RevPiBuildingAnalogSensor(self, fb))

        return entities


HANDLER_CLASS = ValveHandler
