"""Base entity for Revolution Pi integration."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.core import callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CORE_DEVICE_SUFFIX, DOMAIN, MODULE_TYPE_CORE
from .coordinator import RevPiCoordinator, RevPiIOInfo

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry


class RevPiEntity(CoordinatorEntity[RevPiCoordinator]):
    """Base entity for a Revolution Pi IO point."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: RevPiCoordinator,
        entry: ConfigEntry,
        io_info: RevPiIOInfo,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self._io_info = io_info
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_{io_info.name}"
        self._attr_name = f"{entry.title} {io_info.name}"

        if io_info.module_type == MODULE_TYPE_CORE:
            # Core module IOs belong directly to the core (parent) device
            self._attr_device_info = DeviceInfo(
                identifiers={(DOMAIN, f"{entry.entry_id}{CORE_DEVICE_SUFFIX}")},
            )
        else:
            # IO module entities belong to the child device, linked to core via via_device
            self._attr_device_info = DeviceInfo(
                identifiers={(DOMAIN, f"{entry.entry_id}_{io_info.device_name}")},
                name=f"RevPi {io_info.device_name}",
                manufacturer="KUNBUS GmbH",
                model=io_info.module_type.upper(),
                via_device=(DOMAIN, f"{entry.entry_id}{CORE_DEVICE_SUFFIX}"),
            )

    @property
    def io_value(self):
        """Return the current IO value from coordinator data."""
        if self.coordinator.data is None:
            return None
        return self.coordinator.data.io_values.get(self._io_info.name)

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        super()._handle_coordinator_update()
