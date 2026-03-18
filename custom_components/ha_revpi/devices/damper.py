"""Damper building device handler."""

from __future__ import annotations

from typing import Any

from .base import BuildingDeviceHandler


class DamperHandler(BuildingDeviceHandler):
    """Handler for motorised damper devices.

    Creates a CoverEntity with position control.
    """

    device_type = "damper"

    def get_entities(self) -> list[Any]:
        """Create HA entities for this damper."""
        from ..cover import RevPiBuildingCover
        from ..sensor import RevPiBuildingAnalogSensor

        entities: list[Any] = []

        entities.append(RevPiBuildingCover(self))

        fb = self.get_io_by_role("position_feedback")
        if fb:
            entities.append(RevPiBuildingAnalogSensor(self, fb))

        return entities


HANDLER_CLASS = DamperHandler
