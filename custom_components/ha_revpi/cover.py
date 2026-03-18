"""Cover platform for Revolution Pi building devices (dampers)."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from homeassistant.components.cover import (
    CoverDeviceClass,
    CoverEntity,
    CoverEntityFeature,
)
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
    """Set up cover entities from building device handlers."""
    hub_data = hass.data[DOMAIN][entry.entry_id]
    handlers: list[BuildingDeviceHandler] = hub_data.get(
        "building_handlers", []
    )

    entities: list[CoverEntity] = []
    for handler in handlers:
        for entity in handler.get_entities():
            if isinstance(entity, CoverEntity):
                entities.append(entity)

    if entities:
        async_add_entities(entities)


class RevPiBuildingCover(CoordinatorEntity, CoverEntity):
    """Cover entity for a damper, backed by a building device handler."""

    _attr_has_entity_name = True
    _attr_device_class = CoverDeviceClass.DAMPER
    _attr_supported_features = (
        CoverEntityFeature.SET_POSITION
        | CoverEntityFeature.OPEN
        | CoverEntityFeature.CLOSE
    )

    def __init__(self, handler: BuildingDeviceHandler) -> None:
        """Initialize."""
        super().__init__(handler.coordinator)
        self._handler = handler
        self._attr_unique_id = f"{handler.device_id}_cover"
        self._attr_name = "Damper"
        self._attr_device_info = handler.device_info

        self._pos_cmd = handler.get_io_by_role("position_command")
        self._pos_fb = handler.get_io_by_role("position_feedback")

    @property
    def current_cover_position(self) -> int | None:
        """Return the current damper position (0-100)."""
        mapping = self._pos_fb or self._pos_cmd
        if mapping:
            val = self._handler.read_io_engineering(mapping)
            if val is not None:
                return round(val)
        return None

    @property
    def is_closed(self) -> bool | None:
        """Return True if the damper is fully closed."""
        pos = self.current_cover_position
        if pos is None:
            return None
        return pos == 0

    async def async_set_cover_position(self, **kwargs: Any) -> None:
        """Set damper position (0-100%)."""
        position = kwargs.get("position")
        if position is not None and self._pos_cmd:
            await self._handler.write_io_engineering(
                self._pos_cmd, float(position)
            )

    async def async_open_cover(self, **kwargs: Any) -> None:
        """Open the damper to 100%."""
        if self._pos_cmd:
            await self._handler.write_io_engineering(
                self._pos_cmd, 100.0
            )

    async def async_close_cover(self, **kwargs: Any) -> None:
        """Close the damper to 0%."""
        if self._pos_cmd:
            await self._handler.write_io_engineering(
                self._pos_cmd, 0.0
            )
