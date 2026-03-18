"""Building device type registry."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from .ahu import AHUHandler
from .damper import DamperHandler
from .fan_device import FanHandler
from .valve import ValveHandler

if TYPE_CHECKING:
    from ..coordinator import RevPiCoordinator
    from .base import BuildingDeviceHandler

_LOGGER = logging.getLogger(__name__)

# Maps device type string to handler class
DEVICE_TYPE_REGISTRY: dict[str, type[BuildingDeviceHandler]] = {
    "ahu": AHUHandler,
    "fan": FanHandler,
    "valve": ValveHandler,
    "damper": DamperHandler,
}


def get_handler_class(device_type: str) -> type[BuildingDeviceHandler] | None:
    """Get the handler class for a device type."""
    cls = DEVICE_TYPE_REGISTRY.get(device_type)
    if cls is None:
        _LOGGER.error("Unknown building device type: %s", device_type)
    return cls


def create_handler(
    device_config: dict[str, Any],
    coordinator: RevPiCoordinator,
    entry_id: str,
) -> BuildingDeviceHandler | None:
    """Create a device handler from a stored device config."""
    device_type = device_config.get("type")
    if not device_type:
        _LOGGER.error("Building device config missing 'type': %s", device_config)
        return None

    cls = get_handler_class(device_type)
    if cls is None:
        return None

    try:
        return cls(device_config, coordinator, entry_id)
    except Exception:
        _LOGGER.exception("Failed to create handler for %s", device_type)
        return None
