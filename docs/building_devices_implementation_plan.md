# Building Device Templates — Implementation Plan

## Overview

Extend the `ha_revpi` integration to support **logical building devices** (AHUs, fans,
valves, dampers, pumps) that are composed of multiple raw RevPi IOs. A user loads a
JSON template at runtime via the Options flow, maps IO names to roles, and the
integration creates a new HA device with proper platform entities (climate, fan,
cover, etc.) under the existing core hub.

The raw IO entities from physical modules remain unchanged and fully functional
alongside the building device entities. Both layers read/write through the same
coordinator and process image.

---

## Current Architecture (unchanged)

```
RevPi Hardware
    │
    ▼
revpimodio2 (process image read/write)
    │
    ▼
RevPiCoordinator (polls every N seconds)
    │
    ├── RevPiData.io_values    ← dict[io_name, raw_value]
    ├── RevPiData.core_values  ← CPU temp, frequency, etc.
    └── RevPiData.modules      ← dict[mod_name, RevPiModuleInfo]
    │
    ▼
Platform entities (sensor, switch, number, select)
    │
    ▼
HA Device Registry
    ├── Core Device (hub/parent)
    ├── dio01 (child module)
    ├── aio01 (child module)
    └── mio01 (child module)
```

**Key existing code paths:**
- `coordinator.async_write_io(io_name, value)` — writes raw value and refreshes
- `coordinator.data.io_values[io_name]` — reads raw value
- `entry.options` — persisted configuration (survives reboots)
- `__init__._register_devices()` — registers devices in HA device registry
- `entity.RevPiEntity.io_value` — property to read from coordinator data

---

## New Architecture

```
RevPi Hardware (unchanged)
    │
    ▼
RevPiCoordinator (unchanged — same poll, same io_values dict)
    │
    ├── Raw IO entities (existing, unchanged)
    │
    └── Building Device entities (NEW)
            │
            ├── Transform layer (raw mV ↔ engineering units)
            │       linear: 0-10000 mV → 0-100%
            │       inverse_linear: 10000 mV = 0%, 0 mV = 100%
            │       scale_offset: value * scale + offset
            │
            ├── Device handler (maps roles → HA platform capabilities)
            │       AHU handler → ClimateEntity
            │       Fan handler → FanEntity
            │       Valve handler → NumberEntity (0-100%)
            │
            └── Optional control (PID — Phase 5)
                    Reads transformed input, computes output, writes back
```

**Device Registry after template loaded:**
```
Core Device (hub/parent)               ← existing, unchanged
├── dio01 (child module)               ← existing, unchanged
├── aio01 (child module)               ← existing, unchanged
├── mio01 (child module)               ← existing, unchanged
├── AHU Supply Unit 1 (building)       ← NEW, from template
│   ├── Climate entity
│   ├── Binary sensor (fan status)
│   ├── Binary sensor (filter alarm)
│   └── Sensor (supply temperature)
└── Exhaust Fan 1 (building)           ← NEW, from template
    └── Fan entity
```

---

## File Structure

```
custom_components/ha_revpi/
├── __init__.py              ← MODIFY: register building devices on setup, add dispatcher
├── config_flow.py           ← MODIFY: add options flow steps for template management
├── coordinator.py           ← unchanged
├── entity.py                ← unchanged
├── const.py                 ← MODIFY: add new constants
├── sensor.py                ← unchanged
├── switch.py                ← unchanged
├── number.py                ← unchanged
├── select.py                ← unchanged
│
├── devices/                 ← NEW: building device engine
│   ├── __init__.py          ← device type registry + factory
│   ├── base.py              ← base handler class + entity sync
│   ├── transforms.py        ← value transform functions
│   ├── ahu.py               ← AHU → climate entity
│   ├── fan_device.py        ← fan → fan entity
│   ├── valve.py             ← valve → number entity (0-100%)
│   └── damper.py            ← damper → cover entity
│
├── template_utils.py        ← NEW: JSON template load/list/validate
│
├── climate.py               ← NEW: climate platform
├── fan.py                   ← NEW: fan platform (deliberately named fan.py for HA)
├── cover.py                 ← NEW: cover platform (for dampers)
│
├── templates/               ← NEW: built-in JSON templates
│   ├── ahu_basic.json
│   ├── fan_basic.json
│   └── valve_basic.json
│
└── strings.json             ← MODIFY: add template flow strings
```

**Note on naming:** The device handler `fan_device.py` avoids collision with the
HA platform file `fan.py`. The platform files (`climate.py`, `fan.py`, `cover.py`)
follow HA convention and are registered in PLATFORMS.

---

## JSON Template Schema

### Complete Example: AHU with Heating Coil and Damper

```json
{
  "schema_version": 1,
  "name": "AHU Supply Unit",
  "type": "ahu",
  "manufacturer": "Custom",
  "model": "AHU-2000",
  "description": "Supply air handling unit with heating coil, damper, and filter monitoring",
  "ios": {
    "supply_fan_command": {
      "io_name": "DO_AHU1_FAN",
      "role": "fan_command",
      "direction": "output",
      "data_type": "bool",
      "description": "Supply fan start/stop"
    },
    "supply_fan_status": {
      "io_name": "DI_AHU1_FAN_FB",
      "role": "fan_status",
      "direction": "input",
      "data_type": "bool",
      "description": "Supply fan running feedback"
    },
    "supply_temp": {
      "io_name": "AI_AHU1_SUPPLY_TEMP",
      "role": "current_temperature",
      "direction": "input",
      "data_type": "analog",
      "transform": {
        "type": "linear",
        "input_min": 0,
        "input_max": 10000,
        "output_min": -20.0,
        "output_max": 80.0,
        "unit": "°C",
        "precision": 1
      },
      "description": "Supply air temperature sensor (0-10V = -20..+80°C)"
    },
    "heating_valve": {
      "io_name": "AO_AHU1_HTG_VALVE",
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
        "precision": 0
      },
      "description": "Heating coil valve (0-10V = 0-100% open)"
    },
    "damper_position": {
      "io_name": "AO_AHU1_DAMPER",
      "role": "damper_position",
      "direction": "output",
      "data_type": "analog",
      "transform": {
        "type": "linear",
        "input_min": 0,
        "input_max": 10000,
        "output_min": 0.0,
        "output_max": 100.0,
        "unit": "%",
        "precision": 0
      },
      "description": "Fresh air damper (0-10V = 0-100% open)"
    },
    "filter_alarm": {
      "io_name": "DI_AHU1_FILTER",
      "role": "filter_alarm",
      "direction": "input",
      "data_type": "bool",
      "description": "Filter differential pressure alarm"
    }
  },
  "control": {
    "type": "pid",
    "enabled": false,
    "params": {
      "kp": 3.0,
      "ti": 180,
      "td": 0,
      "setpoint_default": 21.0,
      "output_min": 0.0,
      "output_max": 100.0,
      "sample_time": 5.0
    },
    "input_role": "current_temperature",
    "output_role": "heating_valve"
  }
}
```

### Minimal Example: Simple Fan

```json
{
  "schema_version": 1,
  "name": "Exhaust Fan",
  "type": "fan",
  "ios": {
    "fan_command": {
      "io_name": "DO_EF1_CMD",
      "role": "fan_command",
      "direction": "output",
      "data_type": "bool"
    },
    "fan_status": {
      "io_name": "DI_EF1_FB",
      "role": "fan_status",
      "direction": "input",
      "data_type": "bool"
    },
    "fan_speed": {
      "io_name": "AO_EF1_SPEED",
      "role": "speed_command",
      "direction": "output",
      "data_type": "analog",
      "transform": {
        "type": "linear",
        "input_min": 0,
        "input_max": 10000,
        "output_min": 0.0,
        "output_max": 100.0,
        "unit": "%"
      }
    }
  }
}
```

### Minimal Example: Modulating Valve

```json
{
  "schema_version": 1,
  "name": "Heating Valve",
  "type": "valve",
  "ios": {
    "valve_position": {
      "io_name": "AO_VALVE1",
      "role": "position_command",
      "direction": "output",
      "data_type": "analog",
      "transform": {
        "type": "linear",
        "input_min": 0,
        "input_max": 10000,
        "output_min": 0.0,
        "output_max": 100.0,
        "unit": "%"
      }
    },
    "valve_feedback": {
      "io_name": "AI_VALVE1_FB",
      "role": "position_feedback",
      "direction": "input",
      "data_type": "analog",
      "transform": {
        "type": "linear",
        "input_min": 0,
        "input_max": 10000,
        "output_min": 0.0,
        "output_max": 100.0,
        "unit": "%"
      }
    }
  }
}
```

### Template Fields Reference

| Field | Required | Description |
|-------|----------|-------------|
| `schema_version` | yes | Always `1` for forward compatibility |
| `name` | yes | Display name for the device in HA |
| `type` | yes | Device type: `ahu`, `fan`, `valve`, `damper`, `pump` |
| `manufacturer` | no | Device manufacturer (shown in HA device info) |
| `model` | no | Device model (shown in HA device info) |
| `description` | no | Human-readable description |
| `ios` | yes | Dict of IO mappings (key = logical name, value = IO config) |
| `control` | no | Optional control algorithm (Phase 5) |

### IO Entry Fields Reference

| Field | Required | Description |
|-------|----------|-------------|
| `io_name` | yes | piCtory IO name (must match an exported IO in the coordinator) |
| `role` | yes | Semantic role (see roles table per device type below) |
| `direction` | yes | `input` or `output` |
| `data_type` | yes | `bool` or `analog` |
| `transform` | no | Transform config for analog values (omit for bool) |
| `description` | no | Human-readable label |

### Transform Fields Reference

| Field | Required | Default | Description |
|-------|----------|---------|-------------|
| `type` | yes | — | `linear`, `inverse_linear`, or `scale_offset` |
| `input_min` | yes (linear) | — | Raw value minimum (e.g., 0 mV) |
| `input_max` | yes (linear) | — | Raw value maximum (e.g., 10000 mV) |
| `output_min` | yes (linear) | — | Engineering value minimum (e.g., 0.0%) |
| `output_max` | yes (linear) | — | Engineering value maximum (e.g., 100.0%) |
| `scale` | yes (scale_offset) | 1.0 | Multiplier: `eng = raw * scale + offset` |
| `offset` | yes (scale_offset) | 0.0 | Offset: `eng = raw * scale + offset` |
| `unit` | no | — | Engineering unit string (`°C`, `%`, `RPM`) |
| `precision` | no | 1 | Decimal places for display |

### Roles Per Device Type

**AHU (`type: "ahu"`) → ClimateEntity**

| Role | Direction | Data type | Maps to |
|------|-----------|-----------|---------|
| `fan_command` | output | bool | `turn_on()`/`turn_off()` |
| `fan_status` | input | bool | `hvac_action` (heating/idle/off) |
| `current_temperature` | input | analog | `current_temperature` |
| `target_temperature` | output | analog | `target_temperature` (if PID enabled) |
| `heating_valve` | output | analog | exposed as extra sensor (valve %) |
| `cooling_valve` | output | analog | exposed as extra sensor (valve %) |
| `damper_position` | output | analog | exposed as extra sensor (damper %) |
| `filter_alarm` | input | bool | `binary_sensor` (problem class) |
| `frost_alarm` | input | bool | `binary_sensor` (problem class) |

**Fan (`type: "fan"`) → FanEntity**

| Role | Direction | Data type | Maps to |
|------|-----------|-----------|---------|
| `fan_command` | output | bool | `turn_on()`/`turn_off()` |
| `fan_status` | input | bool | `is_on` state |
| `speed_command` | output | analog | `percentage` (0-100%) |
| `speed_feedback` | input | analog | `percentage` read-back |

**Valve (`type: "valve"`) → NumberEntity (0-100%)**

| Role | Direction | Data type | Maps to |
|------|-----------|-----------|---------|
| `position_command` | output | analog | `native_value` / `set_native_value()` |
| `position_feedback` | input | analog | read-only sensor entity |

**Damper (`type: "damper"`) → CoverEntity**

| Role | Direction | Data type | Maps to |
|------|-----------|-----------|---------|
| `position_command` | output | analog | `current_cover_position` / `set_cover_position()` |
| `position_feedback` | input | analog | `current_cover_position` |
| `open_command` | output | bool | `open_cover()` (sets position to 100%) |
| `close_command` | output | bool | `close_cover()` (sets position to 0%) |

---

## Detailed Implementation Per File

### Phase 1: Foundation

#### `devices/transforms.py`

Value transformation functions. All transforms are bidirectional (raw ↔ engineering).

```python
"""Value transforms for building device IOs."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class TransformConfig:
    """Parsed transform configuration from JSON template."""

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
        """Create from JSON template dict."""
        return cls(
            type=data["type"],
            input_min=data.get("input_min", 0.0),
            input_max=data.get("input_max", 10000.0),
            output_min=data.get("output_min", 0.0),
            output_max=data.get("output_max", 100.0),
            scale=data.get("scale", 1.0),
            offset=data.get("offset", 0.0),
            unit=data.get("unit", ""),
            precision=data.get("precision", 1),
        )


def to_engineering(raw: int | float, config: TransformConfig) -> float:
    """Convert raw process image value to engineering units.

    linear:         Proportional mapping from [input_min..input_max] to [output_min..output_max]
    inverse_linear: Same but inverted (10V = 0%, 0V = 100%) for normally-open valves
    scale_offset:   Simple raw * scale + offset
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
    """Convert engineering units back to raw process image value.

    Inverse of to_engineering(). Returns int because RevPi process image
    uses integer values.
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

    # Clamp to input range and round to integer
    raw = max(config.input_min, min(config.input_max, raw))
    return int(round(raw))
```

#### `template_utils.py`

JSON template loading, listing, and validation. Follows the protocol_wizard pattern
with built-in + user template directories.

```python
"""Template utilities for building device JSON templates."""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from homeassistant.core import HomeAssistant

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

BUILTIN_TEMPLATES_DIR = "templates"
USER_TEMPLATES_DIR = "ha_revpi/templates"

# Required fields for validation
REQUIRED_TOP_LEVEL = {"schema_version", "name", "type", "ios"}
REQUIRED_IO_FIELDS = {"io_name", "role", "direction", "data_type"}
VALID_DEVICE_TYPES = {"ahu", "fan", "valve", "damper", "pump"}
VALID_DIRECTIONS = {"input", "output"}
VALID_DATA_TYPES = {"bool", "analog"}
VALID_TRANSFORM_TYPES = {"linear", "inverse_linear", "scale_offset"}


async def get_available_templates(
    hass: HomeAssistant,
) -> dict[str, dict[str, Any]]:
    """Get all available templates (built-in + user).

    Returns dict mapping template_id to info:
    {
        "builtin:ahu_basic": {
            "filename": "ahu_basic.json",
            "display_name": "AHU Basic (Built-in)",
            "source": "builtin",
            "path": "/path/to/file",
        },
        ...
    }
    """
    templates: dict[str, dict[str, Any]] = {}

    # Built-in templates
    builtin_dir = Path(__file__).parent / BUILTIN_TEMPLATES_DIR
    templates.update(
        await _list_templates_in_dir(hass, builtin_dir, "builtin")
    )

    # User templates
    user_dir = Path(hass.config.path(USER_TEMPLATES_DIR))
    templates.update(
        await _list_templates_in_dir(hass, user_dir, "user")
    )

    return templates


async def _list_templates_in_dir(
    hass: HomeAssistant,
    directory: Path,
    source: str,
) -> dict[str, dict[str, Any]]:
    """List JSON templates in a directory."""
    templates: dict[str, dict[str, Any]] = {}

    def _scan() -> list[tuple[str, Path]]:
        if not directory.exists():
            return []
        return [
            (f.stem, f)
            for f in directory.glob("*.json")
            if f.is_file()
        ]

    try:
        found = await hass.async_add_executor_job(_scan)
    except Exception as err:
        _LOGGER.warning("Failed to scan templates in %s: %s", directory, err)
        return templates

    for name, path in found:
        template_id = f"{source}:{name}"
        label = name.replace("_", " ").title()
        suffix = "Built-in" if source == "builtin" else "User"
        templates[template_id] = {
            "filename": f"{name}.json",
            "display_name": f"{label} ({suffix})",
            "source": source,
            "path": str(path),
        }

    return templates


async def load_template(
    hass: HomeAssistant,
    template_id: str,
) -> dict[str, Any] | None:
    """Load and validate a template by ID.

    Returns the parsed template dict, or None on failure.
    """
    templates = await get_available_templates(hass)
    info = templates.get(template_id)
    if not info:
        _LOGGER.error("Template not found: %s", template_id)
        return None

    def _read() -> dict[str, Any]:
        with open(info["path"], encoding="utf-8") as f:
            return json.load(f)

    try:
        data = await hass.async_add_executor_job(_read)
    except (FileNotFoundError, json.JSONDecodeError, OSError) as err:
        _LOGGER.error("Failed to load template %s: %s", template_id, err)
        return None

    errors = validate_template(data)
    if errors:
        _LOGGER.error(
            "Template %s validation failed: %s", template_id, "; ".join(errors)
        )
        return None

    return data


def validate_template(data: dict[str, Any]) -> list[str]:
    """Validate a template dict. Returns list of error strings (empty = valid)."""
    errors: list[str] = []

    # Top-level required fields
    missing = REQUIRED_TOP_LEVEL - set(data.keys())
    if missing:
        errors.append(f"Missing required fields: {missing}")
        return errors  # Can't validate further

    if data["type"] not in VALID_DEVICE_TYPES:
        errors.append(
            f"Unknown device type '{data['type']}', "
            f"must be one of {VALID_DEVICE_TYPES}"
        )

    ios = data.get("ios", {})
    if not isinstance(ios, dict) or not ios:
        errors.append("'ios' must be a non-empty dict")
        return errors

    for key, io_config in ios.items():
        prefix = f"ios.{key}"
        io_missing = REQUIRED_IO_FIELDS - set(io_config.keys())
        if io_missing:
            errors.append(f"{prefix}: missing fields {io_missing}")
            continue

        if io_config["direction"] not in VALID_DIRECTIONS:
            errors.append(f"{prefix}: invalid direction '{io_config['direction']}'")

        if io_config["data_type"] not in VALID_DATA_TYPES:
            errors.append(f"{prefix}: invalid data_type '{io_config['data_type']}'")

        # Validate transform if present
        transform = io_config.get("transform")
        if transform:
            if transform.get("type") not in VALID_TRANSFORM_TYPES:
                errors.append(
                    f"{prefix}.transform: invalid type '{transform.get('type')}'"
                )

    # Validate control block if present
    control = data.get("control")
    if control:
        if "type" not in control:
            errors.append("control: missing 'type'")
        if "input_role" not in control or "output_role" not in control:
            errors.append("control: missing 'input_role' or 'output_role'")

    return errors


def validate_io_mapping(
    template: dict[str, Any],
    available_ios: set[str],
) -> list[str]:
    """Validate that all io_name values in the template exist in the coordinator.

    Called during Options flow after the user confirms the mapping.
    Returns list of error strings (empty = valid).
    """
    errors: list[str] = []
    for key, io_config in template.get("ios", {}).items():
        io_name = io_config.get("io_name", "")
        if io_name not in available_ios:
            errors.append(
                f"IO '{io_name}' (role: {key}) not found in RevPi. "
                f"Available: {sorted(available_ios)}"
            )
    return errors


def get_template_dropdown(
    templates: dict[str, dict[str, Any]],
) -> dict[str, str]:
    """Convert templates dict to dropdown choices for vol.In()."""
    choices: dict[str, str] = {}
    builtin = {k: v for k, v in templates.items() if k.startswith("builtin:")}
    user = {k: v for k, v in templates.items() if k.startswith("user:")}

    for tid, info in sorted(builtin.items()):
        choices[tid] = info["display_name"]
    for tid, info in sorted(user.items()):
        choices[tid] = info["display_name"]

    return choices
```

#### `const.py` additions

```python
# Building device template constants
CONF_BUILDING_DEVICES: Final = "building_devices"
BUILDING_DEVICE_SUFFIX: Final = "_bld"

# Dispatcher signal for runtime entity sync
SIGNAL_BUILDING_DEVICE_SYNC: Final = f"{DOMAIN}_building_device_sync"
```

---

### Phase 2: Device Handlers and Climate Platform

#### `devices/__init__.py`

Device type registry. Maps `type` string from JSON to handler class.

```python
"""Building device type registry."""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .base import BuildingDeviceHandler

# Lazy imports to avoid circular dependencies
DEVICE_TYPE_REGISTRY: dict[str, str] = {
    "ahu": "ahu",
    "fan": "fan_device",
    "valve": "valve",
    "damper": "damper",
}


def get_handler_class(device_type: str) -> type[BuildingDeviceHandler] | None:
    """Get the handler class for a device type."""
    module_name = DEVICE_TYPE_REGISTRY.get(device_type)
    if not module_name:
        return None

    import importlib
    module = importlib.import_module(f".{module_name}", package=__name__)
    return getattr(module, "HANDLER_CLASS", None)


def create_handler(
    device_config: dict[str, Any],
    coordinator: Any,
    entry_id: str,
) -> BuildingDeviceHandler | None:
    """Create a device handler from a stored device config."""
    device_type = device_config.get("type")
    cls = get_handler_class(device_type)
    if cls is None:
        return None
    return cls(device_config, coordinator, entry_id)
```

#### `devices/base.py`

Base class that all device handlers inherit. Provides transform lookup and
entity creation interface.

```python
"""Base building device handler."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from homeassistant.helpers.entity import DeviceInfo

from ..const import BUILDING_DEVICE_SUFFIX, CORE_DEVICE_SUFFIX, DOMAIN
from .transforms import TransformConfig, to_engineering, to_raw

if TYPE_CHECKING:
    from ..coordinator import RevPiCoordinator

_LOGGER = logging.getLogger(__name__)


@dataclass
class IOMapping:
    """A single IO mapping within a building device."""

    logical_name: str       # Key in template ios dict (e.g., "supply_temp")
    io_name: str            # piCtory IO name (e.g., "AI_AHU1_SUPPLY_TEMP")
    role: str               # Semantic role (e.g., "current_temperature")
    direction: str          # "input" or "output"
    data_type: str          # "bool" or "analog"
    transform: TransformConfig | None = None
    description: str = ""


class BuildingDeviceHandler:
    """Base class for building device handlers.

    Subclasses implement get_entities() to return HA entity instances.
    """

    device_type: str = ""  # Override in subclass

    def __init__(
        self,
        device_config: dict[str, Any],
        coordinator: RevPiCoordinator,
        entry_id: str,
    ) -> None:
        self.config = device_config
        self.coordinator = coordinator
        self.entry_id = entry_id
        self.name: str = device_config["name"]
        self.device_type = device_config["type"]
        self.manufacturer: str = device_config.get("manufacturer", "")
        self.model: str = device_config.get("model", "")

        # Parse IO mappings
        self.ios: dict[str, IOMapping] = {}
        for key, io_conf in device_config.get("ios", {}).items():
            transform = None
            if "transform" in io_conf:
                transform = TransformConfig.from_dict(io_conf["transform"])
            self.ios[key] = IOMapping(
                logical_name=key,
                io_name=io_conf["io_name"],
                role=io_conf["role"],
                direction=io_conf["direction"],
                data_type=io_conf["data_type"],
                transform=transform,
                description=io_conf.get("description", ""),
            )

        # Unique device identifier
        self.device_id = (
            f"{entry_id}{BUILDING_DEVICE_SUFFIX}_{self.name.lower().replace(' ', '_')}"
        )

    @property
    def device_info(self) -> DeviceInfo:
        """Return DeviceInfo for this building device."""
        info = DeviceInfo(
            identifiers={(DOMAIN, self.device_id)},
            name=self.name,
            via_device=(DOMAIN, f"{self.entry_id}{CORE_DEVICE_SUFFIX}"),
        )
        if self.manufacturer:
            info["manufacturer"] = self.manufacturer
        if self.model:
            info["model"] = self.model
        return info

    def get_io_by_role(self, role: str) -> IOMapping | None:
        """Find the first IO mapping with the given role."""
        for mapping in self.ios.values():
            if mapping.role == role:
                return mapping
        return None

    def get_ios_by_role(self, role: str) -> list[IOMapping]:
        """Find all IO mappings with the given role."""
        return [m for m in self.ios.values() if m.role == role]

    def read_io_raw(self, io_name: str) -> Any:
        """Read raw IO value from coordinator data."""
        if self.coordinator.data is None:
            return None
        return self.coordinator.data.io_values.get(io_name)

    def read_io_engineering(self, mapping: IOMapping) -> float | bool | None:
        """Read IO value, applying transform if configured."""
        raw = self.read_io_raw(mapping.io_name)
        if raw is None:
            return None
        if mapping.data_type == "bool":
            return bool(raw)
        if mapping.transform:
            return to_engineering(raw, mapping.transform)
        return float(raw)

    async def write_io_engineering(
        self, mapping: IOMapping, value: float | bool
    ) -> None:
        """Write engineering value to IO, converting to raw first."""
        if mapping.data_type == "bool":
            await self.coordinator.async_write_io(mapping.io_name, bool(value))
        elif mapping.transform:
            raw = to_raw(value, mapping.transform)
            await self.coordinator.async_write_io(mapping.io_name, raw)
        else:
            await self.coordinator.async_write_io(mapping.io_name, int(value))

    def get_entities(self) -> list[Any]:
        """Return HA entity instances for this device.

        Override in subclasses. Each entity receives self (the handler)
        so it can call read_io_engineering / write_io_engineering.
        """
        raise NotImplementedError
```

#### `devices/ahu.py`

AHU device handler. Creates a ClimateEntity plus optional binary sensors.

```python
"""AHU building device handler → ClimateEntity."""
from __future__ import annotations

from typing import Any

from .base import BuildingDeviceHandler

_LOGGER = __import__("logging").getLogger(__name__)


class AHUHandler(BuildingDeviceHandler):
    """Handler for Air Handling Unit devices."""

    device_type = "ahu"

    def get_entities(self) -> list[Any]:
        """Create HA entities for this AHU."""
        # Import here to avoid circular imports
        from ..climate import RevPiBuildingClimate

        entities: list[Any] = []

        # Primary climate entity
        entities.append(RevPiBuildingClimate(self))

        # Optional binary sensors for alarms
        from ..sensor import RevPiBuildingBinarySensor, RevPiBuildingAnalogSensor

        for mapping in self.ios.values():
            if mapping.role in ("filter_alarm", "frost_alarm"):
                entities.append(
                    RevPiBuildingBinarySensor(self, mapping, device_class="problem")
                )
            elif mapping.role in ("heating_valve", "cooling_valve", "damper_position"):
                # Expose valve/damper positions as monitoring sensors
                if mapping.direction == "output":
                    entities.append(
                        RevPiBuildingAnalogSensor(self, mapping)
                    )

        return entities


HANDLER_CLASS = AHUHandler
```

#### `climate.py`

New HA climate platform for building devices.

```python
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
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from .coordinator import RevPiCoordinator
    from .devices.base import BuildingDeviceHandler

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up climate entities from building device handlers."""
    hub_data = hass.data[DOMAIN][entry.entry_id]
    handlers: list[BuildingDeviceHandler] = hub_data.get("building_handlers", [])

    entities = []
    for handler in handlers:
        for entity in handler.get_entities():
            if isinstance(entity, ClimateEntity):
                entities.append(entity)

    if entities:
        async_add_entities(entities)


class RevPiBuildingClimate(CoordinatorEntity, ClimateEntity):
    """Climate entity backed by a building device handler."""

    _attr_has_entity_name = True
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_hvac_modes = [HVACMode.OFF, HVACMode.HEAT, HVACMode.AUTO]
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.TURN_ON
        | ClimateEntityFeature.TURN_OFF
    )
    _attr_target_temperature_step = 0.5
    _attr_min_temp = 10.0
    _attr_max_temp = 35.0

    def __init__(self, handler: BuildingDeviceHandler) -> None:
        super().__init__(handler.coordinator)
        self._handler = handler
        self._attr_unique_id = f"{handler.device_id}_climate"
        self._attr_name = "Climate"
        self._attr_device_info = handler.device_info

        # Internal state
        self._target_temp: float = 21.0
        self._hvac_mode: HVACMode = HVACMode.OFF

        # Resolve IO mappings for this climate entity
        self._temp_mapping = handler.get_io_by_role("current_temperature")
        self._fan_cmd_mapping = handler.get_io_by_role("fan_command")
        self._fan_status_mapping = handler.get_io_by_role("fan_status")
        self._heating_valve_mapping = handler.get_io_by_role("heating_valve")

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
        """Return current HVAC action based on fan status and valve position."""
        if self._hvac_mode == HVACMode.OFF:
            return HVACAction.OFF

        # Check fan status
        if self._fan_status_mapping:
            fan_on = self._handler.read_io_engineering(self._fan_status_mapping)
            if not fan_on:
                return HVACAction.IDLE

        # Check heating valve
        if self._heating_valve_mapping:
            valve_pct = self._handler.read_io_engineering(self._heating_valve_mapping)
            if valve_pct and valve_pct > 5:
                return HVACAction.HEATING

        return HVACAction.IDLE

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set target temperature."""
        temp = kwargs.get("temperature")
        if temp is not None:
            self._target_temp = temp
            self.async_write_ha_state()

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set HVAC mode (off/heat/auto)."""
        self._hvac_mode = hvac_mode

        if hvac_mode == HVACMode.OFF:
            # Turn off fan
            if self._fan_cmd_mapping:
                await self._handler.write_io_engineering(
                    self._fan_cmd_mapping, False
                )
            # Close heating valve
            if self._heating_valve_mapping:
                await self._handler.write_io_engineering(
                    self._heating_valve_mapping, 0.0
                )
        elif hvac_mode in (HVACMode.HEAT, HVACMode.AUTO):
            # Turn on fan
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
```

---

### Phase 3: Options Flow — Adding Building Devices at Runtime

#### Changes to `config_flow.py`

The options flow gains new steps for building device management:

```
User opens Options
    │
    ▼
async_step_init (existing: poll_interval, configrsc)
    + new menu item: "Manage Building Devices"
    │
    ▼
async_step_building_menu
    ├── "Add device from template"  → async_step_add_building_device
    ├── "Remove device"             → async_step_remove_building_device
    └── "Back"                      → async_step_init
    │
    ▼
async_step_add_building_device
    1. Show dropdown of available templates (builtin + user)
    2. User selects template
    │
    ▼
async_step_confirm_building_device
    1. Show template name and IO mapping
    2. User can rename the device
    3. User can remap IO names (text inputs pre-filled from template)
    4. Validate all io_names exist in coordinator
    5. On success: save to entry.options["building_devices"]
    6. Fire dispatcher signal → entities created without restart
```

**Persistence in `entry.options`:**

```python
# entry.options["building_devices"] is a list of device configs:
[
    {
        "template_id": "builtin:ahu_basic",
        "name": "AHU Supply 1",
        "type": "ahu",
        "manufacturer": "Custom",
        "model": "AHU-2000",
        "ios": {
            "supply_fan_command": {
                "io_name": "DO_AHU1_FAN",
                "role": "fan_command",
                "direction": "output",
                "data_type": "bool"
            },
            ...
        },
        "control": { ... }  # if present
    }
]
```

The options flow stores the **resolved** device config (not just a reference to the
template). This means the template file is only needed at import time. After that,
the device config is fully self-contained in `entry.options`.

---

### Phase 4: Integration Setup + Entity Sync

#### Changes to `__init__.py`

On startup (`async_setup_entry`), after the existing module setup:

```python
# Existing code (unchanged):
await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

# NEW: Create building device handlers from persisted config
building_configs = entry.options.get(CONF_BUILDING_DEVICES, [])
handlers: list[BuildingDeviceHandler] = []
for dev_config in building_configs:
    handler = create_handler(dev_config, coordinator, entry.entry_id)
    if handler:
        handlers.append(handler)
        # Register device in HA registry
        device_registry.async_get_or_create(
            config_entry_id=entry.entry_id,
            identifiers={(DOMAIN, handler.device_id)},
            name=handler.name,
            manufacturer=handler.manufacturer or "Custom",
            model=handler.model or handler.device_type.upper(),
            via_device=core_identifier,
        )

hass.data[DOMAIN][entry.entry_id]["building_handlers"] = handlers

# Forward to new platforms
new_platforms = [Platform.CLIMATE]  # Add COVER, FAN as implemented
await hass.config_entries.async_forward_entry_setups(entry, new_platforms)
```

**PLATFORMS list update:**

```python
PLATFORMS: list[Platform] = [
    Platform.SENSOR,
    Platform.SWITCH,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.CLIMATE,   # NEW
    # Platform.FAN,     # Phase 6
    # Platform.COVER,   # Phase 6
]
```

#### Runtime entity sync (no restart required)

When a user adds a building device via Options flow:

1. Options flow saves device config to `entry.options["building_devices"]`
2. Options flow calls `async_dispatcher_send(hass, SIGNAL_BUILDING_DEVICE_SYNC_{entry_id})`
3. Each platform has a listener that calls `sync_entities()`
4. `sync_entities()` compares current handlers with stored configs, creates new
   entities for new devices, removes entities for deleted devices

However, for simplicity in Phase 4, we can rely on the existing `update_listener`
which already reloads the integration on options change:

```python
async def update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update — reload if structural settings changed."""
    await hass.config_entries.async_reload(entry.entry_id)
```

This means adding a building device triggers a full reload (< 2 seconds). This is
acceptable for Phase 4. The dispatcher pattern can be added later for smoother UX
if needed.

---

### Phase 5: Optional PID Controller

#### `devices/pid.py`

Simple discrete PID controller that runs inside the coordinator poll loop.

```python
"""Simple discrete PID controller for building devices."""
from __future__ import annotations

import time
from dataclasses import dataclass


@dataclass
class PIDParams:
    """PID controller parameters."""

    kp: float = 3.0
    ti: float = 180.0       # Integral time (seconds), 0 = disabled
    td: float = 0.0         # Derivative time (seconds), 0 = disabled
    setpoint: float = 21.0
    output_min: float = 0.0
    output_max: float = 100.0
    sample_time: float = 5.0  # Minimum seconds between calculations


class PIDController:
    """Discrete PID with anti-windup clamping."""

    def __init__(self, params: PIDParams) -> None:
        self.params = params
        self._integral: float = 0.0
        self._prev_error: float = 0.0
        self._prev_time: float = 0.0
        self._output: float = 0.0

    @property
    def output(self) -> float:
        return self._output

    def compute(self, measured: float) -> float:
        """Compute PID output. Call this every poll cycle."""
        now = time.monotonic()
        dt = now - self._prev_time if self._prev_time else self.params.sample_time
        if dt < self.params.sample_time:
            return self._output

        error = self.params.setpoint - measured

        # Proportional
        p_term = self.params.kp * error

        # Integral (with anti-windup: only integrate if output is not saturated)
        if self.params.ti > 0:
            self._integral += error * dt
            i_term = (self.params.kp / self.params.ti) * self._integral
        else:
            i_term = 0.0

        # Derivative
        if self.params.td > 0 and dt > 0:
            d_term = self.params.kp * self.params.td * (error - self._prev_error) / dt
        else:
            d_term = 0.0

        # Sum and clamp
        output = p_term + i_term + d_term
        output = max(self.params.output_min, min(self.params.output_max, output))

        # Anti-windup: if output is clamped, don't let integral grow further
        if output == self.params.output_max or output == self.params.output_min:
            self._integral -= error * dt  # Undo last integral step

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
```

PID integration into the AHU handler: when `control.enabled` is `true` in the
template, the AHU handler creates a `PIDController` and calls `compute()` during
each coordinator update. The computed output is written to the output role IO.

The climate entity's `async_set_temperature()` updates the PID setpoint. When
`hvac_mode` is `AUTO`, the PID runs automatically. When `HEAT`, the user controls
the valve directly.

---

### Phase 6: Additional Device Types

#### `devices/fan_device.py` → FanEntity

```python
class FanHandler(BuildingDeviceHandler):
    device_type = "fan"

    def get_entities(self):
        from ..fan import RevPiBuildingFan
        return [RevPiBuildingFan(self)]
```

#### `devices/valve.py` → NumberEntity (0-100%)

```python
class ValveHandler(BuildingDeviceHandler):
    device_type = "valve"

    def get_entities(self):
        from ..number import RevPiBuildingValveNumber
        entities = [RevPiBuildingValveNumber(self)]
        # Add feedback sensor if present
        fb = self.get_io_by_role("position_feedback")
        if fb:
            from ..sensor import RevPiBuildingAnalogSensor
            entities.append(RevPiBuildingAnalogSensor(self, fb))
        return entities
```

#### `devices/damper.py` → CoverEntity

```python
class DamperHandler(BuildingDeviceHandler):
    device_type = "damper"

    def get_entities(self):
        from ..cover import RevPiBuildingCover
        return [RevPiBuildingCover(self)]
```

---

## Data Flow Summary

### Reading (every poll cycle)

```
RevPi process image
    │
    ▼
coordinator._read_all_io()
    │
    ▼
coordinator.data.io_values["AO_AHU1_HTG_VALVE"] = 5000  (raw mV)
    │
    ▼
BuildingDeviceHandler.read_io_engineering(heating_valve_mapping)
    │  transforms.to_engineering(5000, linear config)
    │  = 50.0%
    ▼
ClimateEntity.hvac_action → checks valve > 5% → HEATING
```

### Writing (user action in HA)

```
User sets HVAC mode to OFF in HA dashboard
    │
    ▼
ClimateEntity.async_set_hvac_mode(HVACMode.OFF)
    │
    ▼
handler.write_io_engineering(fan_cmd_mapping, False)
    │  coordinator.async_write_io("DO_AHU1_FAN", False)
    │
handler.write_io_engineering(heating_valve_mapping, 0.0)
    │  transforms.to_raw(0.0, linear config) = 0
    │  coordinator.async_write_io("AO_AHU1_HTG_VALVE", 0)
    │
    ▼
coordinator.async_request_refresh()  → next poll reads back values
```

### PID control (Phase 5, when enabled)

```
coordinator poll fires
    │
    ▼
AHU handler reads current_temperature = 19.5°C
    │
    ▼
PIDController.compute(19.5)
    │  setpoint = 21.0, error = 1.5
    │  output = 65.0%
    │
    ▼
handler.write_io_engineering(heating_valve_mapping, 65.0)
    │  transforms.to_raw(65.0) = 6500 mV
    │  coordinator.async_write_io("AO_AHU1_HTG_VALVE", 6500)
```

---

## Proprietary Control Considerations

### What is standard (safe to assume)

| Signal | Convention | Source |
|--------|-----------|--------|
| 0-10V analogue | Linear mapping to 0-100% actuator position | IEC 60381, de facto industry standard |
| MIO 0-10V output | 0-10000 mV integer in process image | KUNBUS MIO documentation |
| AIO 0-10V output | 0-32767 (15-bit DAC) in process image | KUNBUS AIO documentation |
| Valve actuators | Accept 0-10V, respond with proportional position | Belimo, Siemens, Honeywell |
| VFDs | Accept 0-10V for 0-100% speed | ABB, Danfoss, Siemens |

### What varies per project (handled by template)

| What varies | Where configured | Example |
|-------------|-----------------|---------|
| Temperature sensor range | `transform` block | 0-10V = -20..+80°C (NTC sensor) |
| Valve fail-safe direction | `transform.type` | `inverse_linear` for normally-open heating valve |
| PID tuning | `control.params` | kp=3, ti=180 for slow thermal system |
| Sequencing breakpoints | `control.type: "sequence"` | 0-33% heating, 33-66% damper (future) |
| Sensor scaling | `transform` with `scale_offset` | 4-20mA sensor via AIO (future) |

### The transform layer makes it work

The `transform` block in each IO mapping is the key abstraction. It decouples the
integration from any specific sensor/actuator model. The user (or template author)
specifies the conversion, and the integration applies it bidirectionally.

For the vast majority of HVAC installations, only `linear` transforms are needed.
The `inverse_linear` type handles normally-open valves. The `scale_offset` type is
a future escape hatch for unusual sensors.

---

## Testing Strategy

### Unit Tests for transforms.py

```python
def test_linear_to_engineering():
    cfg = TransformConfig(type="linear", input_min=0, input_max=10000,
                          output_min=0.0, output_max=100.0)
    assert to_engineering(0, cfg) == 0.0
    assert to_engineering(5000, cfg) == 50.0
    assert to_engineering(10000, cfg) == 100.0

def test_linear_to_raw():
    cfg = TransformConfig(type="linear", input_min=0, input_max=10000,
                          output_min=0.0, output_max=100.0)
    assert to_raw(0.0, cfg) == 0
    assert to_raw(50.0, cfg) == 5000
    assert to_raw(100.0, cfg) == 10000

def test_inverse_linear():
    cfg = TransformConfig(type="inverse_linear", input_min=0, input_max=10000,
                          output_min=0.0, output_max=100.0)
    assert to_engineering(0, cfg) == 100.0      # 0V = fully open
    assert to_engineering(10000, cfg) == 0.0     # 10V = fully closed

def test_roundtrip():
    cfg = TransformConfig(type="linear", input_min=0, input_max=10000,
                          output_min=-20.0, output_max=80.0, precision=1)
    for raw in [0, 2500, 5000, 7500, 10000]:
        eng = to_engineering(raw, cfg)
        assert to_raw(eng, cfg) == raw
```

### Unit Tests for template_utils.py

```python
def test_validate_valid_template():
    template = {
        "schema_version": 1, "name": "Test", "type": "ahu",
        "ios": {
            "fan": {"io_name": "DO_1", "role": "fan_command",
                    "direction": "output", "data_type": "bool"}
        }
    }
    assert validate_template(template) == []

def test_validate_missing_fields():
    template = {"name": "Test"}
    errors = validate_template(template)
    assert len(errors) > 0

def test_validate_io_mapping():
    template = {"ios": {"fan": {"io_name": "DO_MISSING", ...}}}
    errors = validate_io_mapping(template, {"DO_1", "DI_1"})
    assert "DO_MISSING" in errors[0]
```

### Integration Tests for Climate Entity

```python
async def test_ahu_climate_entity(hass, mock_coordinator):
    """Test AHU climate entity reads temperature and controls fan."""
    handler = AHUHandler(ahu_config, mock_coordinator, "test_entry")
    entities = handler.get_entities()
    climate = [e for e in entities if isinstance(e, ClimateEntity)][0]

    # Verify temperature reading
    mock_coordinator.data.io_values["AI_AHU1_TEMP"] = 5000  # 50% of range
    assert climate.current_temperature == 30.0  # With -20..+80 mapping

    # Verify turn off writes to fan and valve
    await climate.async_set_hvac_mode(HVACMode.OFF)
    mock_coordinator.async_write_io.assert_any_call("DO_AHU1_FAN", False)
    mock_coordinator.async_write_io.assert_any_call("AO_AHU1_HTG_VALVE", 0)
```

---

## Implementation Phases Summary

| Phase | Files | Deliverable |
|-------|-------|-------------|
| **1** | `devices/transforms.py`, `template_utils.py`, `const.py` additions, `templates/*.json` | Transform engine + template loading + validation |
| **2** | `devices/__init__.py`, `devices/base.py`, `devices/ahu.py`, `climate.py` | AHU as working ClimateEntity end-to-end |
| **3** | `config_flow.py` modifications, `strings.json` updates | Options flow: add/remove building devices at runtime |
| **4** | `__init__.py` modifications | Startup persistence, device registry, platform forwarding |
| **5** | `devices/pid.py`, `devices/ahu.py` PID integration | Optional PID closed-loop control |
| **6** | `devices/fan_device.py`, `devices/valve.py`, `devices/damper.py`, `fan.py`, `cover.py` | Additional device types |

Each phase is independently testable and deployable. Phase 1-4 delivers a working
AHU climate entity that can be added at runtime via Options flow and survives
reboots. Phase 5 adds autonomous temperature control. Phase 6 extends to other
building device types.
