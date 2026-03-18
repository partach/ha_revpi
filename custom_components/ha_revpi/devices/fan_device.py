"""Fan building device handler."""

from __future__ import annotations

from typing import Any

from .base import BuildingDeviceHandler


class FanHandler(BuildingDeviceHandler):
    """Handler for fan devices (exhaust fans, supply fans).

    Creates a FanEntity with on/off and optional speed control.
    """

    device_type = "fan"

    def get_entities(self) -> list[Any]:
        """Create HA entities for this fan."""
        from ..fan import RevPiBuildingFan
        from ..sensor import RevPiBuildingBinarySensor

        entities: list[Any] = [RevPiBuildingFan(self)]

        # Add status sensor if available
        status = self.get_io_by_role("fan_status")
        if status:
            entities.append(
                RevPiBuildingBinarySensor(
                    self, status, device_class="running"
                )
            )

        return entities


HANDLER_CLASS = FanHandler
