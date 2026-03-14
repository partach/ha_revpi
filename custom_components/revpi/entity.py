"""Base entity for Revolution Pi integration."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import RevPiCoordinator, RevPiIOInfo


class RevPiEntity(CoordinatorEntity[RevPiCoordinator]):
    """Base entity for a Revolution Pi IO point."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: RevPiCoordinator,
        io_info: RevPiIOInfo,
        entry_id: str,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self._io_info = io_info
        self._attr_unique_id = f"{entry_id}_{io_info.name}"
        self._attr_name = io_info.name
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{entry_id}_{io_info.device_name}")},
        )

    @property
    def io_value(self):
        """Return the current IO value from coordinator data."""
        if self.coordinator.data is None:
            return None
        return self.coordinator.data.io_values.get(self._io_info.name)
