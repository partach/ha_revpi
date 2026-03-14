"""Select platform for Revolution Pi integration."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from homeassistant.components.select import SelectEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo, EntityCategory
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CORE_DEVICE_SUFFIX, DOMAIN
from .coordinator import RevPiCoordinator

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

_LOGGER = logging.getLogger(__name__)

# Monitoring mode options
MONITOR_MODE_OPTIONS = ["read_only", "read_write"]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Revolution Pi select entities."""
    coordinator: RevPiCoordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]

    # Attach config selects to the core (parent) device
    core_device_info = DeviceInfo(
        identifiers={(DOMAIN, f"{entry.entry_id}{CORE_DEVICE_SUFFIX}")},
    )

    entities: list[SelectEntity] = [
        RevPiModeSelect(
            coordinator,
            entry,
            option_key="monitor_mode",
            name="Monitor Mode",
            options=MONITOR_MODE_OPTIONS,
            icon="mdi:eye-settings",
            device_info=core_device_info,
        ),
    ]

    async_add_entities(entities)


class RevPiModeSelect(CoordinatorEntity[RevPiCoordinator], SelectEntity):
    """Select entity for configuration options stored in entry.options."""

    _attr_entity_category = EntityCategory.CONFIG

    def __init__(
        self,
        coordinator: RevPiCoordinator,
        entry: ConfigEntry,
        option_key: str,
        name: str,
        options: list[str],
        icon: str,
        device_info: DeviceInfo,
    ) -> None:
        """Initialize the select entity."""
        super().__init__(coordinator)
        self._entry = entry
        self._option_key = option_key
        self._attr_unique_id = f"{entry.entry_id}_{option_key}"
        self._attr_name = f"{entry.title} {name}"
        self._attr_options = options
        self._attr_icon = icon
        self._attr_device_info = device_info

    @property
    def current_option(self) -> str | None:
        """Return the currently selected option."""
        return self._entry.options.get(self._option_key, self._attr_options[0])

    async def async_select_option(self, option: str) -> None:
        """Update the selected option in config entry."""
        _LOGGER.info("Setting %s to %s", self._attr_name, option)
        updated_options = dict(self._entry.options)
        updated_options[self._option_key] = option
        self.hass.config_entries.async_update_entry(
            self._entry,
            options=updated_options,
        )
        await self.coordinator.async_request_refresh()
        self.async_write_ha_state()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        super()._handle_coordinator_update()
