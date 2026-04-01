"""Switch platform for Revolution Pi integration."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from homeassistant.components.switch import SwitchDeviceClass, SwitchEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MODULE_TYPE_DIO, MODULE_TYPE_MIO, MODULE_TYPE_RELAY
from .entity import RevPiEntity

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from .coordinator import RevPiCoordinator, RevPiIOInfo
    from .devices.base import BuildingDeviceHandler, IOMapping

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Revolution Pi switches based on the coordinator data."""
    hub_data = hass.data[DOMAIN][entry.entry_id]
    coordinator: RevPiCoordinator = hub_data["coordinator"]
    modules = coordinator.get_modules()

    entities: list[SwitchEntity] = []

    for mod_info in modules.values():
        if mod_info.module_type not in (MODULE_TYPE_DIO, MODULE_TYPE_MIO, MODULE_TYPE_RELAY):
            continue

        for io_info in mod_info.outputs:
            if io_info.is_digital:
                entities.append(RevPiDigitalOutputSwitch(coordinator, entry, io_info))

    # Building device switches (e.g. PID enable)
    handlers = hub_data.get("building_handlers", [])
    for handler in handlers:
        for entity in handler.get_entities():
            if isinstance(entity, SwitchEntity):
                entities.append(entity)

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


# ---------------------------------------------------------------------------
# Building device auxiliary switch (pump, exhaust fan, fire damper, etc.)
# ---------------------------------------------------------------------------

_ROLE_ICONS: dict[str, str] = {
    "pump_command": "mdi:pump",
    "exhaust_fan_command": "mdi:fan",
    "fire_damper": "mdi:fire-alert",
    "heat_wheel_command": "mdi:rotate-3d-variant",
}


class RevPiBuildingSwitch(CoordinatorEntity, SwitchEntity):
    """Switch for a building device boolean output (pump, fan, damper, etc.)."""

    _attr_has_entity_name = True

    def __init__(
        self,
        handler: BuildingDeviceHandler,
        mapping: IOMapping,
    ) -> None:
        """Initialize."""
        super().__init__(handler.coordinator)
        self._handler = handler
        self._mapping = mapping
        self._attr_unique_id = f"{handler.device_id}_{mapping.logical_name}_switch"
        self._attr_name = mapping.description or mapping.role.replace("_", " ").title()
        self._attr_device_info = handler.device_info
        self._attr_icon = _ROLE_ICONS.get(mapping.role, "mdi:toggle-switch")

    @property
    def is_on(self) -> bool | None:
        """Return True if the switch is on."""
        val = self._handler.read_io_raw(self._mapping.io_name)
        if val is None:
            return None
        return bool(val)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        await self._handler.write_io_engineering(self._mapping, True)
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        await self._handler.write_io_engineering(self._mapping, False)
        self.async_write_ha_state()
