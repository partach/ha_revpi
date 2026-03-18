"""PID controller for building devices.

Runs as a separate async task with its own timing, independent of the
coordinator poll interval. The sample interval is configurable via the
template's control.sample_interval field (default: 1 second).
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from ..const import DEFAULT_PID_SAMPLE_INTERVAL

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

    from .base import BuildingDeviceHandler

_LOGGER = logging.getLogger(__name__)


@dataclass
class PIDParams:
    """PID controller parameters."""

    kp: float = 3.0
    ti: float = 180.0
    td: float = 0.0
    setpoint: float = 21.0
    output_min: float = 0.0
    output_max: float = 100.0

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PIDParams:
        """Create from control.params dict."""
        return cls(
            kp=float(data.get("kp", 3.0)),
            ti=float(data.get("ti", 180.0)),
            td=float(data.get("td", 0.0)),
            setpoint=float(data.get("setpoint_default", 21.0)),
            output_min=float(data.get("output_min", 0.0)),
            output_max=float(data.get("output_max", 100.0)),
        )


class PIDController:
    """Discrete PID controller with anti-windup clamping."""

    def __init__(self, params: PIDParams) -> None:
        self.params = params
        self._integral: float = 0.0
        self._prev_error: float = 0.0
        self._prev_time: float = 0.0
        self._output: float = 0.0

    @property
    def output(self) -> float:
        """Return the last computed output."""
        return self._output

    @property
    def setpoint(self) -> float:
        """Return the current setpoint."""
        return self.params.setpoint

    @setpoint.setter
    def setpoint(self, value: float) -> None:
        """Update the setpoint."""
        self.params.setpoint = value

    def compute(self, measured: float) -> float:
        """Compute PID output."""
        now = time.monotonic()
        dt = now - self._prev_time if self._prev_time else 1.0
        if dt <= 0:
            return self._output

        error = self.params.setpoint - measured

        # Proportional
        p_term = self.params.kp * error

        # Integral with anti-windup
        if self.params.ti > 0:
            self._integral += error * dt
            i_term = (self.params.kp / self.params.ti) * self._integral
        else:
            i_term = 0.0

        # Derivative
        if self.params.td > 0 and dt > 0:
            d_term = (
                self.params.kp
                * self.params.td
                * (error - self._prev_error)
                / dt
            )
        else:
            d_term = 0.0

        output = p_term + i_term + d_term
        output = max(
            self.params.output_min,
            min(self.params.output_max, output),
        )

        # Anti-windup: undo last integral step if output is saturated
        if (
            output == self.params.output_max
            or output == self.params.output_min
        ):
            self._integral -= error * dt

        self._prev_error = error
        self._prev_time = now
        self._output = output
        return output

    def reset(self) -> None:
        """Reset controller state."""
        self._integral = 0.0
        self._prev_error = 0.0
        self._prev_time = 0.0
        self._output = 0.0


async def _pid_loop(
    hass: HomeAssistant,
    handler: BuildingDeviceHandler,
    controller: PIDController,
    sample_interval: float,
    input_role: str,
    output_role: str,
) -> None:
    """Async PID control loop running at its own interval."""
    _LOGGER.info(
        "PID loop started for %s (interval=%.1fs, setpoint=%.1f)",
        handler.name,
        sample_interval,
        controller.setpoint,
    )

    input_mapping = handler.get_io_by_role(input_role)
    output_mapping = handler.get_io_by_role(output_role)

    if not input_mapping:
        _LOGGER.error(
            "PID input role '%s' not found in %s", input_role, handler.name
        )
        return
    if not output_mapping:
        _LOGGER.error(
            "PID output role '%s' not found in %s",
            output_role,
            handler.name,
        )
        return

    while True:
        try:
            await asyncio.sleep(sample_interval)

            # Read current measured value
            measured = handler.read_io_engineering(input_mapping)
            if measured is None:
                _LOGGER.debug(
                    "PID %s: no measurement available, skipping",
                    handler.name,
                )
                continue

            # Compute PID output
            output = controller.compute(float(measured))

            # Write output
            await handler.write_io_engineering(output_mapping, output)

            _LOGGER.debug(
                "PID %s: measured=%.1f setpoint=%.1f output=%.1f",
                handler.name,
                measured,
                controller.setpoint,
                output,
            )
        except asyncio.CancelledError:
            _LOGGER.info("PID loop stopped for %s", handler.name)
            raise
        except Exception:
            _LOGGER.exception(
                "PID loop error for %s", handler.name
            )
            # Continue running despite errors
            await asyncio.sleep(sample_interval)


def start_pid_task(
    hass: HomeAssistant,
    handler: BuildingDeviceHandler,
) -> asyncio.Task | None:
    """Create and start a PID async task for a handler.

    Returns the task, or None if PID is not configured/enabled.
    """
    control = handler.config.get("control", {})
    if not control.get("enabled"):
        return None

    params_dict = control.get("params", {})
    params = PIDParams.from_dict(params_dict)
    controller = PIDController(params)

    sample_interval = float(
        control.get("sample_interval", DEFAULT_PID_SAMPLE_INTERVAL)
    )
    input_role = control.get("input_role", "")
    output_role = control.get("output_role", "")

    if not input_role or not output_role:
        _LOGGER.error(
            "PID config for %s missing input_role or output_role",
            handler.name,
        )
        return None

    # Store controller on handler so climate entity can update setpoint
    handler.pid_controller = controller  # type: ignore[attr-defined]

    task = hass.async_create_task(
        _pid_loop(
            hass, handler, controller, sample_interval,
            input_role, output_role,
        ),
        f"pid_{handler.name}",
    )
    return task
