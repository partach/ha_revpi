"""Base building device handler."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from homeassistant.helpers.entity import DeviceInfo

from ..const import BUILDING_DEVICE_SUFFIX, CORE_DEVICE_SUFFIX, DOMAIN
from .transforms import TransformConfig, to_engineering, to_raw

if TYPE_CHECKING:
    from ..coordinator import RevPiCoordinator

_LOGGER = logging.getLogger(__name__)


@dataclass
class IOMapping:
    """A single IO mapping within a building device."""

    logical_name: str
    io_name: str
    role: str
    direction: str
    data_type: str
    transform: TransformConfig | None = None
    description: str = ""


class BuildingDeviceHandler:
    """Base class for building device handlers.

    Subclasses implement get_entities() to return HA entity instances
    for this device type.
    """

    device_type: str = ""

    def __init__(
        self,
        device_config: dict[str, Any],
        coordinator: RevPiCoordinator,
        entry_id: str,
    ) -> None:
        self.config = device_config
        self.coordinator = coordinator
        self.entry_id = entry_id
        self.name: str = device_config["name"]
        self.device_type = device_config["type"]
        self.manufacturer: str = device_config.get("manufacturer", "")
        self.model: str = device_config.get("model", "")

        # Parse IO mappings
        self.ios: dict[str, IOMapping] = {}
        for key, io_conf in device_config.get("ios", {}).items():
            transform = None
            if "transform" in io_conf:
                transform = TransformConfig.from_dict(io_conf["transform"])
            self.ios[key] = IOMapping(
                logical_name=key,
                io_name=io_conf["io_name"],
                role=io_conf["role"],
                direction=io_conf["direction"],
                data_type=io_conf["data_type"],
                transform=transform,
                description=io_conf.get("description", ""),
            )

        # Stable device identifier
        self.device_id = (
            f"{entry_id}{BUILDING_DEVICE_SUFFIX}"
            f"_{self.name.lower().replace(' ', '_')}"
        )

    @property
    def device_info(self) -> DeviceInfo:
        """Return DeviceInfo for this building device."""
        info: dict[str, Any] = {
            "identifiers": {(DOMAIN, self.device_id)},
            "name": self.name,
            "via_device": (DOMAIN, f"{self.entry_id}{CORE_DEVICE_SUFFIX}"),
        }
        if self.manufacturer:
            info["manufacturer"] = self.manufacturer
        if self.model:
            info["model"] = self.model
        return DeviceInfo(**info)

    def get_io_by_role(self, role: str) -> IOMapping | None:
        """Find the first IO mapping with the given role."""
        for mapping in self.ios.values():
            if mapping.role == role:
                return mapping
        return None

    def get_ios_by_role(self, role: str) -> list[IOMapping]:
        """Find all IO mappings with the given role."""
        return [m for m in self.ios.values() if m.role == role]

    def read_io_raw(self, io_name: str) -> Any:
        """Read raw IO value from coordinator data."""
        if self.coordinator.data is None:
            return None
        return self.coordinator.data.io_values.get(io_name)

    def read_io_engineering(self, mapping: IOMapping) -> float | bool | None:
        """Read IO value, applying transform if configured."""
        raw = self.read_io_raw(mapping.io_name)
        if raw is None:
            return None
        if mapping.data_type == "bool":
            return bool(raw)
        if mapping.transform:
            return to_engineering(raw, mapping.transform)
        return float(raw)

    async def write_io_engineering(
        self, mapping: IOMapping, value: float | bool
    ) -> None:
        """Write engineering value to IO, converting to raw first."""
        if mapping.data_type == "bool":
            await self.coordinator.async_write_io(mapping.io_name, bool(value))
        elif mapping.transform:
            raw = to_raw(float(value), mapping.transform)
            await self.coordinator.async_write_io(mapping.io_name, raw)
        else:
            await self.coordinator.async_write_io(mapping.io_name, int(value))

    def get_entities(self) -> list[Any]:
        """Return HA entity instances for this device.

        Override in subclasses.
        """
        raise NotImplementedError
