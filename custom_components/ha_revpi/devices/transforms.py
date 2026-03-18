"""Value transforms for building device IOs.

Converts between raw RevPi process image values (integer mV) and
engineering units (float °C, %, RPM, etc.). All transforms are
bidirectional.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class TransformConfig:
    """Parsed transform configuration from a JSON template."""

    type: str  # "linear", "inverse_linear", "scale_offset"
    input_min: float = 0.0
    input_max: float = 10000.0
    output_min: float = 0.0
    output_max: float = 100.0
    scale: float = 1.0
    offset: float = 0.0
    unit: str = ""
    precision: int = 1

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TransformConfig:
        """Create from a JSON template dict."""
        return cls(
            type=data["type"],
            input_min=float(data.get("input_min", 0.0)),
            input_max=float(data.get("input_max", 10000.0)),
            output_min=float(data.get("output_min", 0.0)),
            output_max=float(data.get("output_max", 100.0)),
            scale=float(data.get("scale", 1.0)),
            offset=float(data.get("offset", 0.0)),
            unit=data.get("unit", ""),
            precision=int(data.get("precision", 1)),
        )


def to_engineering(raw: int | float, config: TransformConfig) -> float:
    """Convert raw process image value to engineering units.

    linear:         [input_min..input_max] → [output_min..output_max]
    inverse_linear: [input_min..input_max] → [output_max..output_min]
    scale_offset:   raw * scale + offset
    """
    if config.type == "linear":
        span_in = config.input_max - config.input_min
        if span_in == 0:
            return config.output_min
        ratio = (raw - config.input_min) / span_in
        value = config.output_min + ratio * (config.output_max - config.output_min)
    elif config.type == "inverse_linear":
        span_in = config.input_max - config.input_min
        if span_in == 0:
            return config.output_max
        ratio = (raw - config.input_min) / span_in
        value = config.output_max - ratio * (config.output_max - config.output_min)
    elif config.type == "scale_offset":
        value = raw * config.scale + config.offset
    else:
        value = float(raw)

    return round(value, config.precision)


def to_raw(engineering: float, config: TransformConfig) -> int:
    """Convert engineering units to raw process image value.

    Inverse of to_engineering(). Returns int for the process image.
    """
    if config.type == "linear":
        span_out = config.output_max - config.output_min
        if span_out == 0:
            return int(config.input_min)
        ratio = (engineering - config.output_min) / span_out
        raw = config.input_min + ratio * (config.input_max - config.input_min)
    elif config.type == "inverse_linear":
        span_out = config.output_max - config.output_min
        if span_out == 0:
            return int(config.input_max)
        ratio = (config.output_max - engineering) / span_out
        raw = config.input_min + ratio * (config.input_max - config.input_min)
    elif config.type == "scale_offset":
        if config.scale == 0:
            return 0
        raw = (engineering - config.offset) / config.scale
    else:
        raw = engineering

    raw = max(config.input_min, min(config.input_max, raw))
    return round(raw)
