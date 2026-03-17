"""Sensor platform for Revolution Pi integration."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.helpers.entity import DeviceInfo, EntityCategory
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CORE_DEVICE_SUFFIX, DOMAIN, MODULE_TYPE_AIO, MODULE_TYPE_CORE
from .coordinator import RevPiCoordinator
from .entity import RevPiEntity

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from .coordinator import RevPiIOInfo

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Revolution Pi sensors based on the coordinator data."""
    coordinator: RevPiCoordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    modules = coordinator.get_modules()

    entities: list[SensorEntity] = []

    for mod_info in modules.values():
        # Skip core module IOs — they are handled by _add_core_sensors() below
        if mod_info.module_type == MODULE_TYPE_CORE:
            continue

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

    # Add core module diagnostic sensors (CPU temp, frequency, IO errors, etc.)
    _add_core_sensors(coordinator, entry, entities)

    async_add_entities(entities)


def _add_core_sensors(
    coordinator: RevPiCoordinator,
    entry: ConfigEntry,
    entities: list[SensorEntity],
) -> None:
    """Add sensors for the core (CPU) module."""
    core_device_info = DeviceInfo(
        identifiers={(DOMAIN, f"{entry.entry_id}{CORE_DEVICE_SUFFIX}")},
    )

    entities.extend(
        [
            RevPiCoreSensor(
                coordinator,
                entry,
                core_key="cpu_temperature",
                name="CPU Temperature",
                device_class=SensorDeviceClass.TEMPERATURE,
                state_class=SensorStateClass.MEASUREMENT,
                unit="°C",
                icon="mdi:thermometer",
                device_info=core_device_info,
            ),
            RevPiCoreSensor(
                coordinator,
                entry,
                core_key="cpu_frequency",
                name="CPU Frequency",
                device_class=None,
                state_class=SensorStateClass.MEASUREMENT,
                unit="MHz",
                icon="mdi:chip",
                device_info=core_device_info,
            ),
            RevPiCoreSensor(
                coordinator,
                entry,
                core_key="io_cycle",
                name="IO Cycle Time",
                device_class=None,
                state_class=SensorStateClass.MEASUREMENT,
                unit="ms",
                icon="mdi:timer-outline",
                device_info=core_device_info,
                entity_category=EntityCategory.DIAGNOSTIC,
            ),
            RevPiCoreSensor(
                coordinator,
                entry,
                core_key="io_error_count",
                name="IO Error Count",
                device_class=None,
                state_class=SensorStateClass.TOTAL_INCREASING,
                unit=None,
                icon="mdi:alert-circle-outline",
                device_info=core_device_info,
                entity_category=EntityCategory.DIAGNOSTIC,
            ),
            RevPiCoreBinarySensor(
                coordinator,
                entry,
                core_key="picontrol_running",
                name="piControl Status",
                icon="mdi:cog-outline",
                device_info=core_device_info,
                entity_category=EntityCategory.DIAGNOSTIC,
            ),
        ]
    )


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


class RevPiCoreSensor(CoordinatorEntity[RevPiCoordinator], SensorEntity):
    """Sensor for core module values (CPU temperature, frequency, etc.)."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: RevPiCoordinator,
        entry: ConfigEntry,
        core_key: str,
        name: str,
        device_class: SensorDeviceClass | None,
        state_class: SensorStateClass | None,
        unit: str | None,
        icon: str,
        device_info: DeviceInfo,
        entity_category: EntityCategory | None = None,
    ) -> None:
        """Initialize core sensor."""
        super().__init__(coordinator)
        self._core_key = core_key
        self._attr_unique_id = f"{entry.entry_id}_core_{core_key}"
        self._attr_name = f"{entry.title} {name}"
        self._attr_device_class = device_class
        self._attr_state_class = state_class
        self._attr_native_unit_of_measurement = unit
        self._attr_icon = icon
        self._attr_device_info = device_info
        if entity_category is not None:
            self._attr_entity_category = entity_category

    @property
    def native_value(self) -> int | float | None:
        """Return the core sensor value."""
        if self.coordinator.data is None:
            return None
        return self.coordinator.data.core_values.get(self._core_key)


class RevPiCoreBinarySensor(CoordinatorEntity[RevPiCoordinator], SensorEntity):
    """Sensor for core module boolean status values."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: RevPiCoordinator,
        entry: ConfigEntry,
        core_key: str,
        name: str,
        icon: str,
        device_info: DeviceInfo,
        entity_category: EntityCategory | None = None,
    ) -> None:
        """Initialize core binary sensor."""
        super().__init__(coordinator)
        self._core_key = core_key
        self._attr_unique_id = f"{entry.entry_id}_core_{core_key}"
        self._attr_name = f"{entry.title} {name}"
        self._attr_icon = icon
        self._attr_device_info = device_info
        if entity_category is not None:
            self._attr_entity_category = entity_category

    @property
    def native_value(self) -> str | None:
        """Return the boolean status as a string."""
        if self.coordinator.data is None:
            return None
        val = self.coordinator.data.core_values.get(self._core_key)
        if val is None:
            return None
        return "Running" if val else "Stopped"
