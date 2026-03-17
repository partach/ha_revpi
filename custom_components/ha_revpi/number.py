"""Number entities for the Revolution Pi integration."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from homeassistant.components.number import NumberDeviceClass, NumberEntity, NumberMode
from homeassistant.core import HomeAssistant, callback

from .const import DOMAIN, MODULE_TYPE_AIO
from .entity import RevPiEntity

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from .coordinator import RevPiCoordinator, RevPiIOInfo

_LOGGER = logging.getLogger(__name__)

# RevPi AIO typical ranges
AIO_MIN_VALUE = 0
AIO_MAX_VALUE = 32767  # 15-bit DAC on RevPi AIO


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Revolution Pi number entities based on the coordinator data."""
    coordinator: RevPiCoordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    modules = coordinator.get_modules()

    entities: list[NumberEntity] = []

    for mod_info in modules.values():
        if mod_info.module_type != MODULE_TYPE_AIO:
            continue

        for io_info in mod_info.outputs:
            if not io_info.is_digital:
                entities.append(RevPiAnalogueOutputNumber(coordinator, entry, io_info))

    async_add_entities(entities)


class RevPiAnalogueOutputNumber(RevPiEntity, NumberEntity):
    """Number entity for an analogue output."""

    _attr_device_class = NumberDeviceClass.VOLTAGE
    _attr_native_unit_of_measurement = "mV"
    _attr_icon = "mdi:knob"

    def __init__(
        self,
        coordinator: RevPiCoordinator,
        entry: ConfigEntry,
        io_info: RevPiIOInfo,
    ) -> None:
        """Initialize analogue output number."""
        super().__init__(coordinator, entry, io_info)

        if io_info.signed:
            self._attr_native_min_value = -AIO_MAX_VALUE
        else:
            self._attr_native_min_value = AIO_MIN_VALUE
        self._attr_native_max_value = AIO_MAX_VALUE
        self._attr_native_step = 1

        # Use box mode for voltage/current-type values (like ha_felicity)
        self._attr_mode = NumberMode.BOX

    @property
    def native_value(self) -> float | None:
        """Return the current value."""
        return self.io_value

    async def async_set_native_value(self, value: float) -> None:
        """Set the analogue output value."""
        await self.coordinator.async_write_io(self._io_info.name, int(value))
        self.async_write_ha_state()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        super()._handle_coordinator_update()
