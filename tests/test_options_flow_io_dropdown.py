"""Tests for the options flow IO dropdown selectors."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

from custom_components.ha_revpi.config_flow import RevPiOptionsFlowHandler
from custom_components.ha_revpi.const import (
    DOMAIN,
    IO_TYPE_INP,
    IO_TYPE_OUT,
)
from custom_components.ha_revpi.coordinator import RevPiIOInfo

def _make_io_info(
    name: str,
    device_name: str,
    io_type: int,
    is_digital: bool,
    module_type: str = "dio",
) -> RevPiIOInfo:
    """Create a RevPiIOInfo for testing."""
    return RevPiIOInfo(
        name=name,
        device_name=device_name,
        module_type=module_type,
        io_type=io_type,
        is_digital=is_digital,
        address=0,
        length=0 if is_digital else 2,
    )


def _make_mock_coordinator(
    io_infos: dict[str, RevPiIOInfo],
    io_values: dict[str, Any] | None = None,
) -> MagicMock:
    """Create a mock coordinator with IO info and values."""
    coord = MagicMock()
    coord.get_all_io_info.return_value = dict(io_infos)
    data = MagicMock()
    data.io_values = io_values or dict.fromkeys(io_infos, 0)
    coord.data = data
    return coord


def _make_flow_handler(coordinator: MagicMock | None = None) -> RevPiOptionsFlowHandler:
    """Create an options flow handler with mocked hass data."""
    handler = RevPiOptionsFlowHandler()
    handler.hass = MagicMock()
    handler.config_entry = MagicMock()
    handler.config_entry.entry_id = "test_entry"

    hub_data = {}
    if coordinator is not None:
        hub_data["coordinator"] = coordinator

    handler.hass.data = {DOMAIN: {"test_entry": hub_data}}
    return handler


# Sample IO set matching a realistic RevPi setup
SAMPLE_IOS = {
    "I_1": _make_io_info("I_1", "dio01", IO_TYPE_INP, True),
    "I_2": _make_io_info("I_2", "dio01", IO_TYPE_INP, True),
    "O_1": _make_io_info("O_1", "dio01", IO_TYPE_OUT, True),
    "O_2": _make_io_info("O_2", "dio01", IO_TYPE_OUT, True),
    "AI_1": _make_io_info("AI_1", "aio01", IO_TYPE_INP, False, "aio"),
    "AO_1": _make_io_info("AO_1", "aio01", IO_TYPE_OUT, False, "aio"),
    "AO_2": _make_io_info("AO_2", "aio01", IO_TYPE_OUT, False, "aio"),
    "InputValue_1": _make_io_info("InputValue_1", "mio01", IO_TYPE_INP, True, "mio"),
    "OutputValue_1": _make_io_info("OutputValue_1", "mio01", IO_TYPE_OUT, True, "mio"),
    "InputValue_3": _make_io_info("InputValue_3", "mio01", IO_TYPE_INP, False, "mio"),
}


# ---------------------------------------------------------------------------
# Tests for _get_compatible_ios
# ---------------------------------------------------------------------------


class TestGetCompatibleIOs:
    """Tests for filtering IOs by direction and data type."""

    def test_digital_output(self):
        coord = _make_mock_coordinator(SAMPLE_IOS)
        handler = _make_flow_handler(coord)
        io_conf = {"direction": "output", "data_type": "bool"}

        result = handler._get_compatible_ios(io_conf)

        assert "O_1" in result
        assert "O_2" in result
        assert "OutputValue_1" in result
        # Should NOT include inputs or analog outputs
        assert "I_1" not in result
        assert "AO_1" not in result
        assert "AI_1" not in result

    def test_digital_input(self):
        coord = _make_mock_coordinator(SAMPLE_IOS)
        handler = _make_flow_handler(coord)
        io_conf = {"direction": "input", "data_type": "bool"}

        result = handler._get_compatible_ios(io_conf)

        assert "I_1" in result
        assert "I_2" in result
        assert "InputValue_1" in result
        # Should NOT include outputs or analog inputs
        assert "O_1" not in result
        assert "AI_1" not in result
        assert "InputValue_3" not in result

    def test_analog_input(self):
        coord = _make_mock_coordinator(SAMPLE_IOS)
        handler = _make_flow_handler(coord)
        io_conf = {"direction": "input", "data_type": "analog"}

        result = handler._get_compatible_ios(io_conf)

        assert "AI_1" in result
        assert "InputValue_3" in result
        # Should NOT include digital inputs or any outputs
        assert "I_1" not in result
        assert "AO_1" not in result

    def test_analog_output(self):
        coord = _make_mock_coordinator(SAMPLE_IOS)
        handler = _make_flow_handler(coord)
        io_conf = {"direction": "output", "data_type": "analog"}

        result = handler._get_compatible_ios(io_conf)

        assert "AO_1" in result
        assert "AO_2" in result
        # Should NOT include digital outputs or any inputs
        assert "O_1" not in result
        assert "AI_1" not in result

    def test_no_coordinator_returns_empty(self):
        handler = _make_flow_handler(coordinator=None)
        io_conf = {"direction": "output", "data_type": "bool"}

        result = handler._get_compatible_ios(io_conf)

        assert result == {}

    def test_label_format(self):
        coord = _make_mock_coordinator(SAMPLE_IOS)
        handler = _make_flow_handler(coord)
        io_conf = {"direction": "output", "data_type": "bool"}

        result = handler._get_compatible_ios(io_conf)

        assert result["O_1"] == "O_1 (dio01 - digital output)"
        assert result["OutputValue_1"] == "OutputValue_1 (mio01 - digital output)"


# ---------------------------------------------------------------------------
# Tests for _build_confirm_schema
# ---------------------------------------------------------------------------


class TestBuildConfirmSchema:
    """Tests for the confirmation schema with dropdowns."""

    def test_dropdown_when_coordinator_available(self):
        coord = _make_mock_coordinator(SAMPLE_IOS)
        handler = _make_flow_handler(coord)
        template = {
            "name": "Test",
            "ios": {
                "fan_cmd": {
                    "io_name": "DO_FAN",
                    "direction": "output",
                    "data_type": "bool",
                    "description": "Fan command",
                },
            },
        }

        schema = handler._build_confirm_schema(template)
        # The schema should contain io_fan_cmd as a key
        schema_keys = {str(k): k for k in schema.schema}
        assert "io_fan_cmd" in schema_keys

        # The validator for io_fan_cmd should be vol.In (dropdown)
        validator = schema.schema[schema_keys["io_fan_cmd"]]
        # vol.In creates an In validator — check it has a container attribute
        assert hasattr(validator, "container")

    def test_fallback_to_text_without_coordinator(self):
        handler = _make_flow_handler(coordinator=None)
        template = {
            "name": "Test",
            "ios": {
                "fan_cmd": {
                    "io_name": "DO_FAN",
                    "direction": "output",
                    "data_type": "bool",
                    "description": "Fan command",
                },
            },
        }

        schema = handler._build_confirm_schema(template)
        schema_keys = {str(k): k for k in schema.schema}

        # Without coordinator, should fall back to str (free text)
        validator = schema.schema[schema_keys["io_fan_cmd"]]
        assert validator is str

    def test_dropdown_includes_placeholder(self):
        coord = _make_mock_coordinator(SAMPLE_IOS)
        handler = _make_flow_handler(coord)
        template = {
            "name": "Test",
            "ios": {
                "fan_cmd": {
                    "io_name": "DO_FAN",
                    "direction": "output",
                    "data_type": "bool",
                    "description": "Fan command",
                },
            },
        }

        schema = handler._build_confirm_schema(template)
        schema_keys = {str(k): k for k in schema.schema}
        validator = schema.schema[schema_keys["io_fan_cmd"]]

        # The placeholder empty string should be in the choices
        assert "" in validator.container
        assert "-- Select" in validator.container[""]

    def test_default_cleared_when_not_in_choices(self):
        """Template default IO name not in hardware -> default should be empty."""
        coord = _make_mock_coordinator(SAMPLE_IOS)
        handler = _make_flow_handler(coord)
        template = {
            "name": "Test",
            "ios": {
                "fan_cmd": {
                    "io_name": "NONEXISTENT_IO",
                    "direction": "output",
                    "data_type": "bool",
                    "description": "Fan command",
                },
            },
        }

        schema = handler._build_confirm_schema(template)
        schema_keys = {str(k): k for k in schema.schema}
        key_obj = schema_keys["io_fan_cmd"]
        assert key_obj.default() == ""
