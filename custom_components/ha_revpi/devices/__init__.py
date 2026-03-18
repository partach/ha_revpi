"""Building device type registry."""

from __future__ import annotations

import importlib
import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..coordinator import RevPiCoordinator
    from .base import BuildingDeviceHandler

_LOGGER = logging.getLogger(__name__)

# Maps device type string to module name within this package
DEVICE_TYPE_REGISTRY: dict[str, str] = {
    "ahu": "ahu",
    "fan": "fan_device",
    "valve": "valve",
    "damper": "damper",
}


def get_handler_class(device_type: str) -> type[BuildingDeviceHandler] | None:
    """Get the handler class for a device type."""
    module_name = DEVICE_TYPE_REGISTRY.get(device_type)
    if not module_name:
        _LOGGER.error("Unknown building device type: %s", device_type)
        return None

    try:
        module = importlib.import_module(f".{module_name}", package=__name__)
        return getattr(module, "HANDLER_CLASS", None)
    except (ImportError, AttributeError) as err:
        _LOGGER.error("Failed to load handler for %s: %s", device_type, err)
        return None


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
