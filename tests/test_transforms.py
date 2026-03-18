"""Tests for the value transform functions."""

from __future__ import annotations

from custom_components.ha_revpi.devices.transforms import (
    TransformConfig,
    to_engineering,
    to_raw,
)


class TestLinearTransform:
    """Tests for linear transform (0-10V → engineering units)."""

    def _cfg(self, **kwargs):
        defaults = {
            "type": "linear",
            "input_min": 0,
            "input_max": 10000,
            "output_min": 0.0,
            "output_max": 100.0,
            "precision": 1,
        }
        defaults.update(kwargs)
        return TransformConfig(**defaults)

    def test_zero(self):
        assert to_engineering(0, self._cfg()) == 0.0

    def test_midpoint(self):
        assert to_engineering(5000, self._cfg()) == 50.0

    def test_full_scale(self):
        assert to_engineering(10000, self._cfg()) == 100.0

    def test_temperature_range(self):
        cfg = self._cfg(output_min=-20.0, output_max=80.0)
        assert to_engineering(0, cfg) == -20.0
        assert to_engineering(5000, cfg) == 30.0
        assert to_engineering(10000, cfg) == 80.0

    def test_to_raw_zero(self):
        assert to_raw(0.0, self._cfg()) == 0

    def test_to_raw_midpoint(self):
        assert to_raw(50.0, self._cfg()) == 5000

    def test_to_raw_full_scale(self):
        assert to_raw(100.0, self._cfg()) == 10000

    def test_roundtrip(self):
        cfg = self._cfg(output_min=-20.0, output_max=80.0)
        for raw in [0, 2500, 5000, 7500, 10000]:
            eng = to_engineering(raw, cfg)
            assert to_raw(eng, cfg) == raw

    def test_zero_span(self):
        cfg = self._cfg(input_min=0, input_max=0)
        assert to_engineering(5000, cfg) == 0.0

    def test_clamping(self):
        cfg = self._cfg()
        assert to_raw(150.0, cfg) == 10000
        assert to_raw(-50.0, cfg) == 0


class TestInverseLinearTransform:
    """Tests for inverse linear (normally-open valve: 10V = closed)."""

    def _cfg(self):
        return TransformConfig(
            type="inverse_linear",
            input_min=0,
            input_max=10000,
            output_min=0.0,
            output_max=100.0,
            precision=1,
        )

    def test_zero_voltage_is_full_open(self):
        assert to_engineering(0, self._cfg()) == 100.0

    def test_full_voltage_is_closed(self):
        assert to_engineering(10000, self._cfg()) == 0.0

    def test_midpoint(self):
        assert to_engineering(5000, self._cfg()) == 50.0

    def test_to_raw_full_open(self):
        assert to_raw(100.0, self._cfg()) == 0

    def test_to_raw_closed(self):
        assert to_raw(0.0, self._cfg()) == 10000

    def test_roundtrip(self):
        cfg = self._cfg()
        for raw in [0, 2500, 5000, 7500, 10000]:
            eng = to_engineering(raw, cfg)
            assert to_raw(eng, cfg) == raw


class TestScaleOffsetTransform:
    """Tests for scale+offset transform."""

    def _cfg(self):
        return TransformConfig(
            type="scale_offset",
            scale=0.1,
            offset=-10.0,
            precision=1,
        )

    def test_basic(self):
        cfg = self._cfg()
        assert to_engineering(200, cfg) == 10.0  # 200 * 0.1 - 10 = 10.0

    def test_to_raw(self):
        cfg = self._cfg()
        assert to_raw(10.0, cfg) == 200  # (10.0 + 10) / 0.1 = 200


class TestFromDict:
    """Tests for TransformConfig.from_dict()."""

    def test_full(self):
        cfg = TransformConfig.from_dict({
            "type": "linear",
            "input_min": 100,
            "input_max": 9000,
            "output_min": 5.0,
            "output_max": 50.0,
            "unit": "°C",
            "precision": 2,
        })
        assert cfg.type == "linear"
        assert cfg.input_min == 100.0
        assert cfg.input_max == 9000.0
        assert cfg.output_min == 5.0
        assert cfg.output_max == 50.0
        assert cfg.unit == "°C"
        assert cfg.precision == 2

    def test_defaults(self):
        cfg = TransformConfig.from_dict({"type": "linear"})
        assert cfg.input_min == 0.0
        assert cfg.input_max == 10000.0
        assert cfg.output_min == 0.0
        assert cfg.output_max == 100.0
