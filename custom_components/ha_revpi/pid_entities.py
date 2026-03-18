"""PID controller entities for building device HA integration.

Exposes PID parameters as writable controls and PID state as sensors
within the building device in Home Assistant.

Entities created (when a building device has a "control" section):
- Switch: PID Enable/Disable
- Numbers: Kp, Ti, Td, Output Min, Output Max, Sample Interval
- Sensor: PID Output (current controller output %)
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Any

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.components.switch import SwitchEntity
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.update_coordinator import CoordinatorEntity

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

    from .devices.base import BuildingDeviceHandler
    from .devices.pid import PIDController

_LOGGER = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# PID parameter definitions: (param_key, name, min, max, step, unit, icon)
# ---------------------------------------------------------------------------
PID_PARAM_DEFS: list[tuple[str, str, float, float, float, str | None, str]] = [
    ("kp", "PID Kp", 0.0, 100.0, 0.1, None, "mdi:alpha-p-circle"),
    ("ti", "PID Ti", 0.0, 3600.0, 1.0, "s", "mdi:alpha-i-circle"),
    ("td", "PID Td", 0.0, 600.0, 0.1, "s", "mdi:alpha-d-circle"),
    ("output_min", "PID Output Min", 0.0, 100.0, 0.5, "%", "mdi:arrow-collapse-down"),
    ("output_max", "PID Output Max", 0.0, 100.0, 0.5, "%", "mdi:arrow-collapse-up"),
]


def create_pid_entities(
    handler: BuildingDeviceHandler,
) -> list[Any]:
    """Create all PID-related entities for a handler with control config.

    Returns empty list if no control section or control type is not PID.
    """
    control = handler.config.get("control")
    if not control or control.get("type") != "pid":
        return []

    entities: list[Any] = []

    # Enable/disable switch
    entities.append(RevPiPIDEnableSwitch(handler))

    # PID parameter numbers
    for param_key, name, min_val, max_val, step, unit, icon in PID_PARAM_DEFS:
        entities.append(
            RevPiPIDParameterNumber(
                handler, param_key, name, min_val, max_val, step, unit, icon,
            )
        )

    # Sample interval number
    entities.append(
        RevPiPIDSampleIntervalNumber(handler)
    )

    # PID output sensor
    entities.append(RevPiPIDOutputSensor(handler))

    return entities


# ---------------------------------------------------------------------------
# PID Enable Switch
# ---------------------------------------------------------------------------


class RevPiPIDEnableSwitch(CoordinatorEntity, SwitchEntity):
    """Switch to enable/disable the PID controller loop."""

    _attr_has_entity_name = True
    _attr_icon = "mdi:tune-vertical"
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, handler: BuildingDeviceHandler) -> None:
        """Initialize."""
        super().__init__(handler.coordinator)
        self._handler = handler
        self._attr_unique_id = f"{handler.device_id}_pid_enable"
        self._attr_name = "PID Enable"
        self._attr_device_info = handler.device_info

    @property
    def is_on(self) -> bool:
        """Return True if the PID loop is currently running."""
        task = getattr(self._handler, "_pid_task", None)
        return task is not None and not task.done()

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Start the PID controller loop."""
        from .devices.pid import start_pid_task

        # Already running?
        task = getattr(self._handler, "_pid_task", None)
        if task is not None and not task.done():
            return

        # Set enabled flag so start_pid_task proceeds
        self._handler.config.setdefault("control", {})["enabled"] = True

        hass: HomeAssistant = self.hass
        new_task = start_pid_task(hass, self._handler)
        if new_task:
            self._handler._pid_task = new_task  # type: ignore[attr-defined]
            _LOGGER.info("PID enabled for %s", self._handler.name)
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Stop the PID controller loop."""
        self._handler.config.setdefault("control", {})["enabled"] = False

        task = getattr(self._handler, "_pid_task", None)
        if task is not None and not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
            _LOGGER.info("PID disabled for %s", self._handler.name)
        self._handler._pid_task = None  # type: ignore[attr-defined]
        self.async_write_ha_state()


# ---------------------------------------------------------------------------
# PID Parameter Numbers
# ---------------------------------------------------------------------------


class RevPiPIDParameterNumber(CoordinatorEntity, NumberEntity):
    """Number entity for a PID tuning parameter (Kp, Ti, Td, etc.)."""

    _attr_has_entity_name = True
    _attr_mode = NumberMode.BOX
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(
        self,
        handler: BuildingDeviceHandler,
        param_key: str,
        name: str,
        min_val: float,
        max_val: float,
        step: float,
        unit: str | None,
        icon: str,
    ) -> None:
        """Initialize."""
        super().__init__(handler.coordinator)
        self._handler = handler
        self._param_key = param_key
        self._attr_unique_id = f"{handler.device_id}_pid_{param_key}"
        self._attr_name = name
        self._attr_native_min_value = min_val
        self._attr_native_max_value = max_val
        self._attr_native_step = step
        self._attr_icon = icon
        self._attr_device_info = handler.device_info
        if unit:
            self._attr_native_unit_of_measurement = unit

    def _get_pid(self) -> PIDController | None:
        """Get the PID controller from the handler."""
        return getattr(self._handler, "pid_controller", None)

    @property
    def native_value(self) -> float | None:
        """Return the current parameter value."""
        pid = self._get_pid()
        if pid is None:
            # Fall back to config defaults when PID hasn't been started
            params = self._handler.config.get("control", {}).get("params", {})
            key_map = {
                "kp": "kp",
                "ti": "ti",
                "td": "td",
                "output_min": "output_min",
                "output_max": "output_max",
            }
            return params.get(key_map.get(self._param_key, self._param_key))
        return getattr(pid.params, self._param_key, None)

    async def async_set_native_value(self, value: float) -> None:
        """Update the PID parameter live."""
        pid = self._get_pid()
        if pid is not None:
            setattr(pid.params, self._param_key, value)
            _LOGGER.info(
                "PID %s.%s set to %s",
                self._handler.name, self._param_key, value,
            )
        else:
            # Update the config so the value is used when PID starts
            params = self._handler.config.setdefault("control", {}).setdefault(
                "params", {}
            )
            params[self._param_key] = value
            _LOGGER.info(
                "PID %s.%s stored as %s (PID not running)",
                self._handler.name, self._param_key, value,
            )
        self.async_write_ha_state()


class RevPiPIDSampleIntervalNumber(CoordinatorEntity, NumberEntity):
    """Number entity for PID sample interval."""

    _attr_has_entity_name = True
    _attr_mode = NumberMode.BOX
    _attr_entity_category = EntityCategory.CONFIG
    _attr_icon = "mdi:timer-outline"
    _attr_native_min_value = 0.1
    _attr_native_max_value = 60.0
    _attr_native_step = 0.1
    _attr_native_unit_of_measurement = "s"

    def __init__(self, handler: BuildingDeviceHandler) -> None:
        """Initialize."""
        super().__init__(handler.coordinator)
        self._handler = handler
        self._attr_unique_id = f"{handler.device_id}_pid_sample_interval"
        self._attr_name = "PID Sample Interval"
        self._attr_device_info = handler.device_info

    @property
    def native_value(self) -> float | None:
        """Return the current sample interval."""
        return self._handler.config.get("control", {}).get(
            "sample_interval", 1.0
        )

    async def async_set_native_value(self, value: float) -> None:
        """Update sample interval.

        Note: takes effect on next PID restart (disable/enable).
        """
        self._handler.config.setdefault("control", {})["sample_interval"] = value
        _LOGGER.info(
            "PID %s sample_interval set to %s (restart PID to apply)",
            self._handler.name, value,
        )
        self.async_write_ha_state()


# ---------------------------------------------------------------------------
# PID Output Sensor
# ---------------------------------------------------------------------------


class RevPiPIDOutputSensor(CoordinatorEntity, SensorEntity):
    """Sensor showing the current PID controller output."""

    _attr_has_entity_name = True
    _attr_icon = "mdi:gauge"
    _attr_native_unit_of_measurement = "%"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, handler: BuildingDeviceHandler) -> None:
        """Initialize."""
        super().__init__(handler.coordinator)
        self._handler = handler
        self._attr_unique_id = f"{handler.device_id}_pid_output"
        self._attr_name = "PID Output"
        self._attr_device_info = handler.device_info

    @property
    def native_value(self) -> float | None:
        """Return the current PID output value."""
        pid = getattr(self._handler, "pid_controller", None)
        if pid is None:
            return None
        return round(pid.output, 1)

    @property
    def available(self) -> bool:
        """Return True if PID controller is running."""
        task = getattr(self._handler, "_pid_task", None)
        return task is not None and not task.done()
