"""Fan platform for Revolution Pi building devices."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from homeassistant.components.fan import FanEntity, FanEntityFeature
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from .devices.base import BuildingDeviceHandler

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up fan entities from building device handlers."""
    hub_data = hass.data[DOMAIN][entry.entry_id]
    handlers: list[BuildingDeviceHandler] = hub_data.get(
        "building_handlers", []
    )

    entities: list[FanEntity] = []
    for handler in handlers:
        for entity in handler.get_entities():
            if isinstance(entity, FanEntity):
                entities.append(entity)

    if entities:
        async_add_entities(entities)


class RevPiBuildingFan(CoordinatorEntity, FanEntity):
    """Fan entity backed by a building device handler."""

    _attr_has_entity_name = True

    def __init__(self, handler: BuildingDeviceHandler) -> None:
        """Initialize."""
        super().__init__(handler.coordinator)
        self._handler = handler
        self._attr_unique_id = f"{handler.device_id}_fan"
        self._attr_name = "Fan"
        self._attr_device_info = handler.device_info

        self._fan_cmd = handler.get_io_by_role("fan_command")
        self._fan_status = handler.get_io_by_role("fan_status")
        self._speed_cmd = handler.get_io_by_role("speed_command")
        self._speed_fb = handler.get_io_by_role("speed_feedback")

        features = FanEntityFeature(0)
        if self._speed_cmd:
            features |= FanEntityFeature.SET_SPEED
        features |= FanEntityFeature.TURN_ON
        features |= FanEntityFeature.TURN_OFF
        self._attr_supported_features = features

    @property
    def is_on(self) -> bool | None:
        """Return True if the fan is on."""
        if self._fan_status:
            val = self._handler.read_io_engineering(self._fan_status)
            if val is not None:
                return bool(val)
        if self._fan_cmd:
            val = self._handler.read_io_engineering(self._fan_cmd)
            if val is not None:
                return bool(val)
        return None

    @property
    def percentage(self) -> int | None:
        """Return fan speed percentage."""
        mapping = self._speed_fb or self._speed_cmd
        if mapping:
            val = self._handler.read_io_engineering(mapping)
            if val is not None:
                return round(val)
        return None

    async def async_turn_on(
        self,
        percentage: int | None = None,
        preset_mode: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Turn on the fan."""
        if self._fan_cmd:
            await self._handler.write_io_engineering(
                self._fan_cmd, True
            )
        if percentage is not None and self._speed_cmd:
            await self._handler.write_io_engineering(
                self._speed_cmd, float(percentage)
            )

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the fan."""
        if self._fan_cmd:
            await self._handler.write_io_engineering(
                self._fan_cmd, False
            )
        if self._speed_cmd:
            await self._handler.write_io_engineering(
                self._speed_cmd, 0.0
            )

    async def async_set_percentage(self, percentage: int) -> None:
        """Set fan speed percentage."""
        if self._speed_cmd:
            await self._handler.write_io_engineering(
                self._speed_cmd, float(percentage)
            )
        # Also turn on/off based on percentage
        if percentage == 0 and self._fan_cmd:
            await self._handler.write_io_engineering(
                self._fan_cmd, False
            )
        elif percentage > 0 and self._fan_cmd:
            await self._handler.write_io_engineering(
                self._fan_cmd, True
            )
