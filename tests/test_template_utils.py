"""Tests for template validation utilities."""

from __future__ import annotations

from custom_components.ha_revpi.template_utils import (
    validate_io_mapping,
    validate_template,
)


class TestValidateTemplate:
    """Tests for validate_template()."""

    def _minimal_template(self, **overrides):
        template = {
            "schema_version": 1,
            "name": "Test Device",
            "type": "ahu",
            "ios": {
                "fan_cmd": {
                    "io_name": "DO_FAN",
                    "role": "fan_command",
                    "direction": "output",
                    "data_type": "bool",
                }
            },
        }
        template.update(overrides)
        return template

    def test_valid_minimal(self):
        errors = validate_template(self._minimal_template())
        assert errors == []

    def test_missing_name(self):
        t = self._minimal_template()
        del t["name"]
        errors = validate_template(t)
        assert len(errors) > 0
        assert "Missing required fields" in errors[0]

    def test_missing_ios(self):
        t = self._minimal_template()
        del t["ios"]
        errors = validate_template(t)
        assert len(errors) > 0

    def test_invalid_device_type(self):
        errors = validate_template(self._minimal_template(type="spaceship"))
        assert any("Unknown device type" in e for e in errors)

    def test_invalid_direction(self):
        t = self._minimal_template()
        t["ios"]["fan_cmd"]["direction"] = "sideways"
        errors = validate_template(t)
        assert any("invalid direction" in e for e in errors)

    def test_invalid_data_type(self):
        t = self._minimal_template()
        t["ios"]["fan_cmd"]["data_type"] = "quantum"
        errors = validate_template(t)
        assert any("invalid data_type" in e for e in errors)

    def test_missing_io_fields(self):
        t = self._minimal_template()
        t["ios"]["fan_cmd"] = {"io_name": "DO_FAN"}
        errors = validate_template(t)
        assert any("missing fields" in e for e in errors)

    def test_invalid_transform_type(self):
        t = self._minimal_template()
        t["ios"]["fan_cmd"]["transform"] = {"type": "logarithmic"}
        errors = validate_template(t)
        assert any("invalid type" in e for e in errors)

    def test_valid_with_transform(self):
        t = self._minimal_template()
        t["ios"]["temp"] = {
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
            },
        }
        errors = validate_template(t)
        assert errors == []

    def test_valid_with_control(self):
        t = self._minimal_template()
        t["control"] = {
            "type": "pid",
            "enabled": True,
            "input_role": "current_temperature",
            "output_role": "heating_valve",
            "params": {"kp": 3.0, "ti": 180},
        }
        errors = validate_template(t)
        assert errors == []

    def test_control_missing_roles(self):
        t = self._minimal_template()
        t["control"] = {"type": "pid"}
        errors = validate_template(t)
        assert any("input_role" in e for e in errors)

    def test_empty_ios(self):
        errors = validate_template(self._minimal_template(ios={}))
        assert any("non-empty" in e for e in errors)

    def test_all_valid_device_types(self):
        for dtype in ("ahu", "fan", "valve", "damper", "pump"):
            errors = validate_template(self._minimal_template(type=dtype))
            assert errors == [], f"Failed for type={dtype}"


class TestValidateIOMapping:
    """Tests for validate_io_mapping()."""

    def test_all_present(self):
        template = {
            "ios": {
                "fan": {"io_name": "DO_FAN"},
                "temp": {"io_name": "AI_TEMP"},
            }
        }
        errors = validate_io_mapping(template, {"DO_FAN", "AI_TEMP", "AO_1"})
        assert errors == []

    def test_missing_io(self):
        template = {
            "ios": {
                "fan": {"io_name": "DO_MISSING"},
            }
        }
        errors = validate_io_mapping(template, {"DO_FAN", "AI_TEMP"})
        assert len(errors) == 1
        assert "DO_MISSING" in errors[0]

    def test_empty_available(self):
        template = {
            "ios": {
                "fan": {"io_name": "DO_FAN"},
            }
        }
        errors = validate_io_mapping(template, set())
        assert len(errors) == 1
