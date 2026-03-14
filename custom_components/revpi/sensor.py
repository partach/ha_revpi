"""Sensor platform for Revolution Pi integration."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)

from .const import DOMAIN, MODULE_TYPE_AIO
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
    """Set up Revolution Pi sensors based on the coordinator data."""
    coordinator: RevPiCoordinator = hass.data[DOMAIN][entry.entry_id]
    modules = coordinator.get_modules()

    entities: list[SensorEntity] = []

    for mod_info in modules.values():
        # Create sensors for all inputs
        for io_info in mod_info.inputs:
            if io_info.is_digital:
                entities.append(RevPiDigitalInputSensor(coordinator, entry, io_info))
            else:
                entities.append(RevPiAnalogueInputSensor(coordinator, entry, io_info))

        # Also expose analogue outputs as read-only sensors for monitoring
        if mod_info.module_type == MODULE_TYPE_AIO:
            for io_info in mod_info.outputs:
                if not io_info.is_digital:
                    entities.append(RevPiAnalogueOutputSensor(coordinator, entry, io_info))

    async_add_entities(entities)


class RevPiDigitalInputSensor(RevPiEntity, SensorEntity):
    """Sensor for a digital input (on/off state exposed as sensor)."""

    _attr_device_class = None
    _attr_state_class = None
    _attr_icon = "mdi:electric-switch"

    def __init__(
        self,
        coordinator: RevPiCoordinator,
        entry: ConfigEntry,
        io_info: RevPiIOInfo,
    ) -> None:
        """Initialize digital input sensor."""
        super().__init__(coordinator, entry, io_info)
        self._attr_unique_id = f"{entry.entry_id}_{io_info.name}_sensor"

    @property
    def native_value(self) -> str | None:
        """Return the state of the digital input."""
        val = self.io_value
        if val is None:
            return None
        return "ON" if val else "OFF"


class RevPiAnalogueInputSensor(RevPiEntity, SensorEntity):
    """Sensor for an analogue input."""

    _attr_device_class = SensorDeviceClass.VOLTAGE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = "mV"
    _attr_icon = "mdi:sine-wave"

    def __init__(
        self,
        coordinator: RevPiCoordinator,
        entry: ConfigEntry,
        io_info: RevPiIOInfo,
    ) -> None:
        """Initialize analogue input sensor."""
        super().__init__(coordinator, entry, io_info)
        self._attr_unique_id = f"{entry.entry_id}_{io_info.name}_sensor"

    @property
    def native_value(self) -> int | float | None:
        """Return the analogue input value."""
        return self.io_value


class RevPiAnalogueOutputSensor(RevPiEntity, SensorEntity):
    """Sensor that monitors the current value of an analogue output."""

    _attr_device_class = SensorDeviceClass.VOLTAGE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = "mV"
    _attr_icon = "mdi:sine-wave"

    def __init__(
        self,
        coordinator: RevPiCoordinator,
        entry: ConfigEntry,
        io_info: RevPiIOInfo,
    ) -> None:
        """Initialize analogue output monitoring sensor."""
        super().__init__(coordinator, entry, io_info)
        self._attr_unique_id = f"{entry.entry_id}_{io_info.name}_out_sensor"
        self._attr_name = f"{entry.title} {io_info.name} (output)"

    @property
    def native_value(self) -> int | float | None:
        """Return the analogue output value."""
        return self.io_value
