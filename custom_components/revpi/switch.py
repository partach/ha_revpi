"""Switch platform for Revolution Pi integration."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from homeassistant.components.switch import SwitchDeviceClass, SwitchEntity

from .const import DOMAIN, MODULE_TYPE_DIO, MODULE_TYPE_RELAY
from .entity import RevPiEntity

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from .coordinator import RevPiCoordinator, RevPiIOInfo

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Revolution Pi switches based on the coordinator data."""
    coordinator: RevPiCoordinator = hass.data[DOMAIN][entry.entry_id]
    modules = coordinator.get_modules()

    entities: list[SwitchEntity] = []

    for mod_info in modules.values():
        if mod_info.module_type not in (MODULE_TYPE_DIO, MODULE_TYPE_RELAY):
            continue

        for io_info in mod_info.outputs:
            if io_info.is_digital:
                entities.append(RevPiDigitalOutputSwitch(coordinator, entry, io_info))

    async_add_entities(entities)


class RevPiDigitalOutputSwitch(RevPiEntity, SwitchEntity):
    """Switch for a digital output or relay."""

    def __init__(
        self,
        coordinator: RevPiCoordinator,
        entry: ConfigEntry,
        io_info: RevPiIOInfo,
    ) -> None:
        """Initialize digital output switch."""
        super().__init__(coordinator, entry, io_info)

        if io_info.module_type == MODULE_TYPE_RELAY:
            self._attr_device_class = SwitchDeviceClass.SWITCH
            self._attr_icon = "mdi:electric-switch"
        else:
            self._attr_device_class = SwitchDeviceClass.OUTLET
            self._attr_icon = "mdi:toggle-switch"

    @property
    def is_on(self) -> bool | None:
        """Return True if the switch is on."""
        val = self.io_value
        if val is None:
            return None
        return bool(val)

    async def async_turn_on(self, **kwargs) -> None:
        """Turn the switch on."""
        await self.coordinator.async_write_io(self._io_info.name, True)

    async def async_turn_off(self, **kwargs) -> None:
        """Turn the switch off."""
        await self.coordinator.async_write_io(self._io_info.name, False)
