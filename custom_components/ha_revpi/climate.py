"""Climate platform for Revolution Pi building devices."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.const import UnitOfTemperature
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from .devices.base import BuildingDeviceHandler

_LOGGER = logging.getLogger(__name__)

_HEAT_ONLY_MODES: list[HVACMode] = [HVACMode.OFF, HVACMode.HEAT, HVACMode.AUTO]
_HEAT_COOL_MODES: list[HVACMode] = [
    HVACMode.OFF,
    HVACMode.HEAT,
    HVACMode.COOL,
    HVACMode.AUTO,
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up climate entities from building device handlers."""
    hub_data = hass.data[DOMAIN][entry.entry_id]
    handlers: list[BuildingDeviceHandler] = hub_data.get("building_handlers", [])

    entities: list[ClimateEntity] = []
    for handler in handlers:
        for entity in handler.get_entities():
            if isinstance(entity, ClimateEntity):
                entities.append(entity)

    if entities:
        async_add_entities(entities)


class RevPiBuildingClimate(CoordinatorEntity, ClimateEntity, RestoreEntity):
    """Climate entity backed by a building device handler."""

    _attr_has_entity_name = True
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.TURN_ON
        | ClimateEntityFeature.TURN_OFF
    )
    _attr_target_temperature_step = 0.5
    _attr_min_temp = 10.0
    _attr_max_temp = 35.0

    def __init__(self, handler: BuildingDeviceHandler) -> None:
        """Initialize."""
        super().__init__(handler.coordinator)
        self._handler = handler
        self._attr_unique_id = f"{handler.device_id}_climate"
        self._attr_name = "Climate"
        self._attr_device_info = handler.device_info

        self._target_temp: float = 21.0
        self._hvac_mode: HVACMode = HVACMode.OFF

        # Resolve IO mappings
        self._temp_mapping = handler.get_io_by_role("current_temperature")
        self._fan_cmd_mapping = handler.get_io_by_role("fan_command")
        self._fan_status_mapping = handler.get_io_by_role("fan_status")
        self._heating_valve_mapping = handler.get_io_by_role("heating_valve")
        self._cooling_valve_mapping = handler.get_io_by_role("cooling_valve")

        # Expose COOL mode only when a cooling valve is configured
        self._attr_hvac_modes = (
            _HEAT_COOL_MODES if self._cooling_valve_mapping else _HEAT_ONLY_MODES
        )

    async def async_added_to_hass(self) -> None:
        """Restore last known state on startup."""
        await super().async_added_to_hass()
        last_state = await self.async_get_last_state()
        if last_state is None:
            return

        # Restore HVAC mode
        if last_state.state in (m.value for m in HVACMode):
            self._hvac_mode = HVACMode(last_state.state)

        # Restore target temperature
        last_temp = last_state.attributes.get("temperature")
        if last_temp is not None:
            try:
                self._target_temp = float(last_temp)
            except (ValueError, TypeError):
                pass

        # Sync restored setpoint to PID controller if it exists
        pid = getattr(self._handler, "pid_controller", None)
        if pid is not None:
            pid.setpoint = self._target_temp

        # Re-apply IO state for the restored mode
        if self._hvac_mode != HVACMode.OFF:
            await self.async_set_hvac_mode(self._hvac_mode)

        _LOGGER.debug(
            "Restored climate %s: mode=%s target=%.1f",
            self._attr_name,
            self._hvac_mode,
            self._target_temp,
        )

    @property
    def current_temperature(self) -> float | None:
        """Return current temperature from sensor IO."""
        if self._temp_mapping:
            return self._handler.read_io_engineering(self._temp_mapping)
        return None

    @property
    def target_temperature(self) -> float:
        """Return target temperature."""
        return self._target_temp

    @property
    def hvac_mode(self) -> HVACMode:
        """Return current HVAC mode."""
        return self._hvac_mode

    @property
    def hvac_action(self) -> HVACAction | None:
        """Return current HVAC action based on valve state and mode."""
        if self._hvac_mode == HVACMode.OFF:
            return HVACAction.OFF

        # Determine action from valve positions first
        cooling_active = False
        heating_active = False

        if self._cooling_valve_mapping:
            valve_pct = self._handler.read_io_engineering(
                self._cooling_valve_mapping
            )
            if valve_pct is not None and valve_pct > 5:
                cooling_active = True

        if self._heating_valve_mapping:
            valve_pct = self._handler.read_io_engineering(
                self._heating_valve_mapping
            )
            if valve_pct is not None and valve_pct > 5:
                heating_active = True

        if cooling_active:
            return HVACAction.COOLING
        if heating_active:
            return HVACAction.HEATING

        return HVACAction.IDLE

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set target temperature.

        If PID is active, update the PID setpoint so the controller
        tracks the new target.  Also persist to config so it survives
        restarts.
        """
        temp = kwargs.get("temperature")
        if temp is not None:
            self._target_temp = temp
            # Update PID setpoint if controller is running
            pid = getattr(self._handler, "pid_controller", None)
            if pid is not None:
                pid.setpoint = temp
            # Persist setpoint_default to config entry options
            params = self._handler.config.setdefault(
                "control", {}
            ).setdefault("params", {})
            params["setpoint_default"] = temp
            from .pid_entities import _persist_control_config

            _persist_control_config(self.hass, self._handler)
            self.async_write_ha_state()

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set HVAC mode (off/heat/cool/auto)."""
        self._hvac_mode = hvac_mode

        if hvac_mode == HVACMode.OFF:
            if self._fan_cmd_mapping:
                await self._handler.write_io_engineering(
                    self._fan_cmd_mapping, False
                )
            if self._heating_valve_mapping:
                await self._handler.write_io_engineering(
                    self._heating_valve_mapping, 0.0
                )
            if self._cooling_valve_mapping:
                await self._handler.write_io_engineering(
                    self._cooling_valve_mapping, 0.0
                )
        elif hvac_mode == HVACMode.HEAT:
            if self._fan_cmd_mapping:
                await self._handler.write_io_engineering(
                    self._fan_cmd_mapping, True
                )
            if self._cooling_valve_mapping:
                await self._handler.write_io_engineering(
                    self._cooling_valve_mapping, 0.0
                )
        elif hvac_mode == HVACMode.COOL:
            if self._fan_cmd_mapping:
                await self._handler.write_io_engineering(
                    self._fan_cmd_mapping, True
                )
            if self._heating_valve_mapping:
                await self._handler.write_io_engineering(
                    self._heating_valve_mapping, 0.0
                )
        elif hvac_mode == HVACMode.AUTO:
            if self._fan_cmd_mapping:
                await self._handler.write_io_engineering(
                    self._fan_cmd_mapping, True
                )

        self.async_write_ha_state()

    async def async_turn_on(self) -> None:
        """Turn on (set to HEAT mode)."""
        await self.async_set_hvac_mode(HVACMode.HEAT)

    async def async_turn_off(self) -> None:
        """Turn off."""
        await self.async_set_hvac_mode(HVACMode.OFF)
