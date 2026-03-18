"""Tests for building device handlers, PID controller, and entities."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from homeassistant.components.climate import HVACAction, HVACMode

from custom_components.ha_revpi.devices import create_handler
from custom_components.ha_revpi.devices.base import (
    BuildingDeviceHandler,
)
from custom_components.ha_revpi.devices.pid import PIDController, PIDParams

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_coordinator(io_values: dict[str, Any] | None = None) -> MagicMock:
    """Create a mock coordinator with io_values."""
    coord = MagicMock()
    data = MagicMock()
    data.io_values = io_values or {}
    coord.data = data
    coord.async_write_io = AsyncMock()
    coord.async_request_refresh = AsyncMock()
    return coord


def _ahu_config(**overrides) -> dict[str, Any]:
    """Return a minimal AHU device config."""
    cfg: dict[str, Any] = {
        "name": "Test AHU",
        "type": "ahu",
        "manufacturer": "TestCo",
        "model": "AHU-100",
        "ios": {
            "fan_cmd": {
                "io_name": "DO_FAN",
                "role": "fan_command",
                "direction": "output",
                "data_type": "bool",
            },
            "fan_status": {
                "io_name": "DI_FAN_FB",
                "role": "fan_status",
                "direction": "input",
                "data_type": "bool",
            },
            "supply_temp": {
                "io_name": "AI_TEMP",
                "role": "current_temperature",
                "direction": "input",
                "data_type": "analog",
                "transform": {
                    "type": "linear",
                    "input_min": 0,
                    "input_max": 10000,
                    "output_min": -20.0,
                    "output_max": 80.0,
                    "unit": "\u00b0C",
                    "precision": 1,
                },
            },
            "htg_valve": {
                "io_name": "AO_HTG",
                "role": "heating_valve",
                "direction": "output",
                "data_type": "analog",
                "transform": {
                    "type": "linear",
                    "input_min": 0,
                    "input_max": 10000,
                    "output_min": 0.0,
                    "output_max": 100.0,
                    "unit": "%",
                    "precision": 0,
                },
            },
            "filter": {
                "io_name": "DI_FILTER",
                "role": "filter_alarm",
                "direction": "input",
                "data_type": "bool",
            },
        },
    }
    cfg.update(overrides)
    return cfg


def _ahu_with_cooling_config(**overrides) -> dict[str, Any]:
    """Return an AHU config that includes a cooling valve."""
    cfg = _ahu_config()
    cfg["ios"]["clg_valve"] = {
        "io_name": "AO_CLG",
        "role": "cooling_valve",
        "direction": "output",
        "data_type": "analog",
        "transform": {
            "type": "linear",
            "input_min": 0,
            "input_max": 10000,
            "output_min": 0.0,
            "output_max": 100.0,
            "unit": "%",
            "precision": 0,
        },
    }
    cfg.update(overrides)
    return cfg


def _fan_config() -> dict[str, Any]:
    return {
        "name": "Test Fan",
        "type": "fan",
        "ios": {
            "cmd": {
                "io_name": "DO_FAN",
                "role": "fan_command",
                "direction": "output",
                "data_type": "bool",
            },
            "speed": {
                "io_name": "AO_SPEED",
                "role": "speed_command",
                "direction": "output",
                "data_type": "analog",
                "transform": {
                    "type": "linear",
                    "input_min": 0,
                    "input_max": 10000,
                    "output_min": 0.0,
                    "output_max": 100.0,
                },
            },
        },
    }


def _valve_config() -> dict[str, Any]:
    return {
        "name": "Test Valve",
        "type": "valve",
        "ios": {
            "pos_cmd": {
                "io_name": "AO_VALVE",
                "role": "position_command",
                "direction": "output",
                "data_type": "analog",
                "transform": {
                    "type": "linear",
                    "input_min": 0,
                    "input_max": 10000,
                    "output_min": 0.0,
                    "output_max": 100.0,
                },
            },
            "pos_fb": {
                "io_name": "AI_VALVE_FB",
                "role": "position_feedback",
                "direction": "input",
                "data_type": "analog",
                "transform": {
                    "type": "linear",
                    "input_min": 0,
                    "input_max": 10000,
                    "output_min": 0.0,
                    "output_max": 100.0,
                },
            },
        },
    }


def _damper_config() -> dict[str, Any]:
    return {
        "name": "Test Damper",
        "type": "damper",
        "ios": {
            "pos_cmd": {
                "io_name": "AO_DAMPER",
                "role": "position_command",
                "direction": "output",
                "data_type": "analog",
                "transform": {
                    "type": "linear",
                    "input_min": 0,
                    "input_max": 10000,
                    "output_min": 0.0,
                    "output_max": 100.0,
                },
            },
        },
    }


# ---------------------------------------------------------------------------
# Handler tests
# ---------------------------------------------------------------------------


class TestBuildingDeviceHandler:
    """Tests for the base handler."""

    def test_parse_ios(self):
        coord = _make_coordinator()
        handler = BuildingDeviceHandler(
            _ahu_config(), coord, "entry_1"
        )
        assert len(handler.ios) == 5
        assert handler.ios["fan_cmd"].role == "fan_command"
        assert handler.ios["supply_temp"].transform is not None

    def test_get_io_by_role(self):
        coord = _make_coordinator()
        handler = BuildingDeviceHandler(
            _ahu_config(), coord, "entry_1"
        )
        mapping = handler.get_io_by_role("fan_command")
        assert mapping is not None
        assert mapping.io_name == "DO_FAN"

    def test_get_io_by_role_missing(self):
        coord = _make_coordinator()
        handler = BuildingDeviceHandler(
            _ahu_config(), coord, "entry_1"
        )
        assert handler.get_io_by_role("nonexistent") is None

    def test_read_io_engineering_bool(self):
        coord = _make_coordinator({"DI_FAN_FB": True})
        handler = BuildingDeviceHandler(
            _ahu_config(), coord, "entry_1"
        )
        mapping = handler.get_io_by_role("fan_status")
        assert handler.read_io_engineering(mapping) is True

    def test_read_io_engineering_analog(self):
        coord = _make_coordinator({"AI_TEMP": 5000})
        handler = BuildingDeviceHandler(
            _ahu_config(), coord, "entry_1"
        )
        mapping = handler.get_io_by_role("current_temperature")
        result = handler.read_io_engineering(mapping)
        assert result == 30.0  # linear: 5000/10000 * 100 + (-20) = 30

    def test_read_io_engineering_none(self):
        coord = _make_coordinator({})
        handler = BuildingDeviceHandler(
            _ahu_config(), coord, "entry_1"
        )
        mapping = handler.get_io_by_role("current_temperature")
        assert handler.read_io_engineering(mapping) is None

    @pytest.mark.asyncio
    async def test_write_io_engineering_bool(self):
        coord = _make_coordinator()
        handler = BuildingDeviceHandler(
            _ahu_config(), coord, "entry_1"
        )
        mapping = handler.get_io_by_role("fan_command")
        await handler.write_io_engineering(mapping, True)
        coord.async_write_io.assert_called_once_with("DO_FAN", True)

    @pytest.mark.asyncio
    async def test_write_io_engineering_analog(self):
        coord = _make_coordinator()
        handler = BuildingDeviceHandler(
            _ahu_config(), coord, "entry_1"
        )
        mapping = handler.get_io_by_role("heating_valve")
        await handler.write_io_engineering(mapping, 50.0)
        coord.async_write_io.assert_called_once_with("AO_HTG", 5000)

    def test_device_info(self):
        coord = _make_coordinator()
        handler = BuildingDeviceHandler(
            _ahu_config(), coord, "entry_1"
        )
        info = handler.device_info
        assert handler.name == "Test AHU"
        assert "identifiers" in info


class TestCreateHandler:
    """Tests for the factory function."""

    def test_create_ahu(self):
        coord = _make_coordinator()
        handler = create_handler(_ahu_config(), coord, "entry_1")
        assert handler is not None
        assert handler.device_type == "ahu"

    def test_create_fan(self):
        coord = _make_coordinator()
        handler = create_handler(_fan_config(), coord, "entry_1")
        assert handler is not None
        assert handler.device_type == "fan"

    def test_create_valve(self):
        coord = _make_coordinator()
        handler = create_handler(_valve_config(), coord, "entry_1")
        assert handler is not None
        assert handler.device_type == "valve"

    def test_create_damper(self):
        coord = _make_coordinator()
        handler = create_handler(_damper_config(), coord, "entry_1")
        assert handler is not None
        assert handler.device_type == "damper"

    def test_create_unknown_type(self):
        coord = _make_coordinator()
        cfg = _ahu_config(type="spaceship")
        handler = create_handler(cfg, coord, "entry_1")
        assert handler is None

    def test_create_missing_type(self):
        coord = _make_coordinator()
        handler = create_handler({"name": "bad"}, coord, "entry_1")
        assert handler is None


class TestAHUHandlerEntities:
    """Tests for AHU handler entity generation."""

    def test_get_entities(self):
        coord = _make_coordinator()
        handler = create_handler(_ahu_config(), coord, "entry_1")
        entities = handler.get_entities()
        # Should have: 1 climate + 1 alarm sensor + 1 valve sensor
        assert len(entities) >= 2

    def test_climate_entity_present(self):
        from custom_components.ha_revpi.climate import RevPiBuildingClimate

        coord = _make_coordinator()
        handler = create_handler(_ahu_config(), coord, "entry_1")
        entities = handler.get_entities()
        climates = [
            e for e in entities if isinstance(e, RevPiBuildingClimate)
        ]
        assert len(climates) == 1

    def test_entity_count_with_cooling_valve(self):
        coord = _make_coordinator()
        handler = create_handler(_ahu_with_cooling_config(), coord, "entry_1")
        entities = handler.get_entities()
        # climate + filter_alarm binary sensor + heating_valve sensor
        # + cooling_valve sensor = 4 minimum
        assert len(entities) >= 4


class TestFanHandlerEntities:
    """Tests for fan handler entity generation."""

    def test_get_entities(self):
        coord = _make_coordinator()
        handler = create_handler(_fan_config(), coord, "entry_1")
        entities = handler.get_entities()
        assert len(entities) >= 1


class TestValveHandlerEntities:
    """Tests for valve handler entity generation."""

    def test_get_entities(self):
        coord = _make_coordinator()
        handler = create_handler(_valve_config(), coord, "entry_1")
        entities = handler.get_entities()
        # position_command → number, position_feedback → sensor
        assert len(entities) == 2


class TestDamperHandlerEntities:
    """Tests for damper handler entity generation."""

    def test_get_entities(self):
        coord = _make_coordinator()
        handler = create_handler(_damper_config(), coord, "entry_1")
        entities = handler.get_entities()
        assert len(entities) >= 1


# ---------------------------------------------------------------------------
# PID controller tests
# ---------------------------------------------------------------------------


class TestPIDController:
    """Tests for the PID controller."""

    def test_proportional_only(self):
        params = PIDParams(kp=2.0, ti=0.0, td=0.0, setpoint=20.0)
        pid = PIDController(params)
        output = pid.compute(18.0)
        # error = 20 - 18 = 2, P = 2.0 * 2 = 4.0
        assert output == 4.0

    def test_output_clamping_max(self):
        params = PIDParams(
            kp=100.0, ti=0.0, td=0.0,
            setpoint=100.0, output_max=100.0,
        )
        pid = PIDController(params)
        output = pid.compute(0.0)
        assert output == 100.0

    def test_output_clamping_min(self):
        params = PIDParams(
            kp=100.0, ti=0.0, td=0.0,
            setpoint=0.0, output_min=0.0,
        )
        pid = PIDController(params)
        output = pid.compute(100.0)
        assert output == 0.0

    def test_setpoint_update(self):
        params = PIDParams(kp=1.0, setpoint=20.0)
        pid = PIDController(params)
        pid.setpoint = 25.0
        assert pid.setpoint == 25.0

    def test_reset(self):
        params = PIDParams(kp=1.0, setpoint=20.0)
        pid = PIDController(params)
        pid.compute(18.0)
        pid.reset()
        assert pid.output == 0.0

    def test_from_dict(self):
        params = PIDParams.from_dict({
            "kp": 5.0,
            "ti": 120,
            "td": 10,
            "setpoint_default": 22.0,
            "output_min": 5.0,
            "output_max": 95.0,
        })
        assert params.kp == 5.0
        assert params.ti == 120.0
        assert params.td == 10.0
        assert params.setpoint == 22.0
        assert params.output_min == 5.0
        assert params.output_max == 95.0


# ---------------------------------------------------------------------------
# Climate entity tests
# ---------------------------------------------------------------------------


class TestClimateHeatOnly:
    """Climate entity tests for heat-only AHU (no cooling valve)."""

    def _make_climate(self, io_values=None):
        from custom_components.ha_revpi.climate import RevPiBuildingClimate

        coord = _make_coordinator(io_values)
        handler = create_handler(_ahu_config(), coord, "entry_1")
        climate = RevPiBuildingClimate(handler)
        climate.async_write_ha_state = MagicMock()
        return climate, coord

    def test_hvac_modes_no_cooling_valve(self):
        climate, _ = self._make_climate()
        modes = climate.hvac_modes
        assert HVACMode.OFF in modes
        assert HVACMode.HEAT in modes
        assert HVACMode.AUTO in modes
        assert HVACMode.COOL not in modes

    def test_initial_state(self):
        climate, _ = self._make_climate()
        assert climate.hvac_mode == HVACMode.OFF
        assert climate.target_temperature == 21.0

    def test_hvac_action_off(self):
        climate, _ = self._make_climate()
        assert climate.hvac_action == HVACAction.OFF

    def test_hvac_action_heating(self):
        climate, _ = self._make_climate(
            {"DI_FAN_FB": True, "AO_HTG": 5000}
        )
        climate._hvac_mode = HVACMode.HEAT
        assert climate.hvac_action == HVACAction.HEATING

    def test_hvac_action_idle_fan_off(self):
        climate, _ = self._make_climate(
            {"DI_FAN_FB": False, "AO_HTG": 5000}
        )
        climate._hvac_mode = HVACMode.HEAT
        assert climate.hvac_action == HVACAction.IDLE

    def test_hvac_action_idle_valve_closed(self):
        climate, _ = self._make_climate(
            {"DI_FAN_FB": True, "AO_HTG": 0}
        )
        climate._hvac_mode = HVACMode.HEAT
        assert climate.hvac_action == HVACAction.IDLE

    @pytest.mark.asyncio
    async def test_set_hvac_mode_off(self):
        climate, coord = self._make_climate()
        climate._hvac_mode = HVACMode.HEAT
        await climate.async_set_hvac_mode(HVACMode.OFF)
        assert climate.hvac_mode == HVACMode.OFF
        # Fan off + heating valve closed
        assert coord.async_write_io.call_count == 2

    @pytest.mark.asyncio
    async def test_set_hvac_mode_heat(self):
        climate, coord = self._make_climate()
        await climate.async_set_hvac_mode(HVACMode.HEAT)
        assert climate.hvac_mode == HVACMode.HEAT
        coord.async_write_io.assert_called_with("DO_FAN", True)

    @pytest.mark.asyncio
    async def test_set_temperature(self):
        climate, _ = self._make_climate()
        await climate.async_set_temperature(temperature=23.5)
        assert climate.target_temperature == 23.5

    @pytest.mark.asyncio
    async def test_turn_on_off(self):
        climate, _ = self._make_climate()
        await climate.async_turn_on()
        assert climate.hvac_mode == HVACMode.HEAT
        await climate.async_turn_off()
        assert climate.hvac_mode == HVACMode.OFF

    def test_current_temperature(self):
        climate, _ = self._make_climate({"AI_TEMP": 5000})
        assert climate.current_temperature == 30.0

    def test_current_temperature_none(self):
        climate, _ = self._make_climate({})
        assert climate.current_temperature is None


class TestClimateWithCooling:
    """Climate entity tests for AHU with cooling valve."""

    def _make_climate(self, io_values=None):
        from custom_components.ha_revpi.climate import RevPiBuildingClimate

        coord = _make_coordinator(io_values)
        handler = create_handler(_ahu_with_cooling_config(), coord, "entry_1")
        climate = RevPiBuildingClimate(handler)
        climate.async_write_ha_state = MagicMock()
        return climate, coord

    def test_hvac_modes_include_cool(self):
        climate, _ = self._make_climate()
        modes = climate.hvac_modes
        assert HVACMode.COOL in modes
        assert HVACMode.HEAT in modes
        assert HVACMode.AUTO in modes
        assert HVACMode.OFF in modes

    def test_hvac_action_cooling(self):
        climate, _ = self._make_climate(
            {"DI_FAN_FB": True, "AO_CLG": 5000, "AO_HTG": 0}
        )
        climate._hvac_mode = HVACMode.COOL
        assert climate.hvac_action == HVACAction.COOLING

    def test_hvac_action_cooling_takes_priority_over_heating(self):
        climate, _ = self._make_climate(
            {"DI_FAN_FB": True, "AO_CLG": 5000, "AO_HTG": 5000}
        )
        climate._hvac_mode = HVACMode.AUTO
        # When both valves are open, cooling is reported (checked first)
        assert climate.hvac_action == HVACAction.COOLING

    def test_hvac_action_heating_when_cooling_closed(self):
        climate, _ = self._make_climate(
            {"DI_FAN_FB": True, "AO_CLG": 0, "AO_HTG": 5000}
        )
        climate._hvac_mode = HVACMode.AUTO
        assert climate.hvac_action == HVACAction.HEATING

    def test_hvac_action_idle_both_closed(self):
        climate, _ = self._make_climate(
            {"DI_FAN_FB": True, "AO_CLG": 0, "AO_HTG": 0}
        )
        climate._hvac_mode = HVACMode.AUTO
        assert climate.hvac_action == HVACAction.IDLE

    @pytest.mark.asyncio
    async def test_set_hvac_mode_cool(self):
        climate, coord = self._make_climate()
        await climate.async_set_hvac_mode(HVACMode.COOL)
        assert climate.hvac_mode == HVACMode.COOL
        # Fan on + heating valve closed
        calls = coord.async_write_io.call_args_list
        call_args = [(c.args[0], c.args[1]) for c in calls]
        assert ("DO_FAN", True) in call_args
        assert ("AO_HTG", 0) in call_args

    @pytest.mark.asyncio
    async def test_set_hvac_mode_heat_closes_cooling(self):
        climate, coord = self._make_climate()
        await climate.async_set_hvac_mode(HVACMode.HEAT)
        calls = coord.async_write_io.call_args_list
        call_args = [(c.args[0], c.args[1]) for c in calls]
        assert ("DO_FAN", True) in call_args
        assert ("AO_CLG", 0) in call_args

    @pytest.mark.asyncio
    async def test_set_hvac_mode_off_closes_both_valves(self):
        climate, coord = self._make_climate()
        await climate.async_set_hvac_mode(HVACMode.OFF)
        calls = coord.async_write_io.call_args_list
        call_args = [(c.args[0], c.args[1]) for c in calls]
        assert ("DO_FAN", False) in call_args
        assert ("AO_HTG", 0) in call_args
        assert ("AO_CLG", 0) in call_args

    @pytest.mark.asyncio
    async def test_set_hvac_mode_auto(self):
        climate, coord = self._make_climate()
        await climate.async_set_hvac_mode(HVACMode.AUTO)
        assert climate.hvac_mode == HVACMode.AUTO
        # Only fan on — AUTO lets PID or external logic handle valves
        calls = coord.async_write_io.call_args_list
        call_args = [(c.args[0], c.args[1]) for c in calls]
        assert ("DO_FAN", True) in call_args
