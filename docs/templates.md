# Building Device Templates

Templates are JSON files that describe how a building device (AHU, fan, valve, damper) is wired to Revolution Pi IOs and how raw signals are converted to meaningful engineering values. They are loaded at runtime through the Options flow — no restart of the integration setup is required.

## Table of Contents

- [Overview](#overview)
- [Template Locations](#template-locations)
- [Template Schema](#template-schema)
  - [Top-Level Fields](#top-level-fields)
  - [IO Definitions](#io-definitions)
  - [Transforms](#transforms)
  - [Control Block (PID)](#control-block-pid)
- [Device Types and Roles](#device-types-and-roles)
  - [AHU (Air Handling Unit)](#ahu-air-handling-unit)
  - [Fan](#fan)
  - [Valve](#valve)
  - [Damper](#damper)
- [How Templates are Used](#how-templates-are-used)
  - [Adding a Device via Options Flow](#adding-a-device-via-options-flow)
  - [IO Remapping](#io-remapping)
  - [Persistence](#persistence)
- [Transforms In Depth](#transforms-in-depth)
  - [Linear](#linear)
  - [Inverse Linear](#inverse-linear)
  - [Scale + Offset](#scale--offset)
  - [No Transform (bool)](#no-transform-bool)
- [PID Controller In Depth](#pid-controller-in-depth)
  - [Parameters](#parameters)
  - [How It Runs](#how-it-runs)
  - [Tuning](#tuning)
- [Creating Your Own Templates](#creating-your-own-templates)
  - [Step-by-Step Guide](#step-by-step-guide)
  - [Validation Rules](#validation-rules)
  - [Example: Custom Cooling AHU](#example-custom-cooling-ahu)
  - [Example: Normally-Closed Valve](#example-normally-closed-valve)
- [Full Reference Example](#full-reference-example)

---

## Overview

A template is a single `.json` file that describes:

1. **What** the device is (type, name, manufacturer)
2. **Which IOs** it uses and what role each IO plays
3. **How** raw millivolt values from the process image are converted to engineering units (°C, %, RPM)
4. **Optionally**, a control algorithm (PID) that reads a sensor input and writes to an actuator output

The integration loads the template, lets the user remap IO names to match their actual RevPi configuration, and then creates the appropriate Home Assistant entities (climate, fan, cover, number, sensor).

---

## Template Locations

Templates are discovered from two directories:

| Location | ID Prefix | Description |
|---|---|---|
| `custom_components/ha_revpi/templates/` | `builtin:` | Ships with the integration. Do not modify these directly. |
| `<config_dir>/ha_revpi/templates/` | `user:` | Your custom templates. Create this directory to add your own. |

- `<config_dir>` is your Home Assistant configuration directory (where `configuration.yaml` lives).
- Files must have the `.json` extension.
- The template ID is formed as `<source>:<filename_without_extension>`, e.g. `builtin:ahu_basic` or `user:my_custom_ahu`.
- User templates with the same filename as a built-in template appear separately — they do not override built-ins.

---

## Template Schema

### Top-Level Fields

```json
{
  "schema_version": 1,
  "name": "AHU Supply Unit",
  "type": "ahu",
  "manufacturer": "Swegon",
  "model": "Gold RX",
  "description": "Supply AHU with heating coil and fresh air damper",
  "ios": { ... },
  "control": { ... }
}
```

| Field | Required | Type | Description |
|---|---|---|---|
| `schema_version` | Yes | `int` | Always `1` for now. Reserved for future schema migrations. |
| `name` | Yes | `string` | Display name shown in Home Assistant. Can be changed during the Options flow. |
| `type` | Yes | `string` | Device type: `ahu`, `fan`, `valve`, `damper`, or `pump`. Determines which handler processes the template and which HA entities are created. |
| `manufacturer` | No | `string` | Shown in the HA device info panel. |
| `model` | No | `string` | Shown in the HA device info panel. |
| `description` | No | `string` | Human-readable description. Not shown in HA, useful for documentation. |
| `ios` | Yes | `object` | IO mapping definitions. Must contain at least one entry. |
| `control` | No | `object` | PID control loop configuration. Omit if no automatic control is needed. |

### IO Definitions

Each key in the `ios` object is a **logical name** (your label for the IO). The value describes the physical mapping:

```json
"supply_temp": {
  "io_name": "AI_AHU_SUPPLY_TEMP",
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
}
```

| Field | Required | Type | Description |
|---|---|---|---|
| `io_name` | Yes | `string` | The RevPi IO name as configured in PiCtory. This is the default — the user can remap it during the Options flow. |
| `role` | Yes | `string` | Semantic role that tells the handler what this IO does. See [Device Types and Roles](#device-types-and-roles). |
| `direction` | Yes | `string` | `"input"` (sensor/feedback) or `"output"` (command/actuator). |
| `data_type` | Yes | `string` | `"bool"` (digital on/off) or `"analog"` (0-10V signal via process image integer). |
| `transform` | No | `object` | Value conversion between raw and engineering units. Only relevant for `"analog"` data types. See [Transforms](#transforms). |
| `description` | No | `string` | Human-readable description of this IO point. |

### Transforms

Transforms convert between the raw integer in the RevPi process image (typically 0-10000, representing 0-10V in millivolts) and engineering units that humans understand (°C, %, RPM).

```json
"transform": {
  "type": "linear",
  "input_min": 0,
  "input_max": 10000,
  "output_min": -20.0,
  "output_max": 80.0,
  "unit": "°C",
  "precision": 1
}
```

| Field | Required | Default | Description |
|---|---|---|---|
| `type` | Yes | — | `"linear"`, `"inverse_linear"`, or `"scale_offset"` |
| `input_min` | No | `0` | Raw value lower bound (usually 0 mV) |
| `input_max` | No | `10000` | Raw value upper bound (usually 10000 mV = 10V) |
| `output_min` | No | `0.0` | Engineering value at `input_min` |
| `output_max` | No | `100.0` | Engineering value at `input_max` |
| `scale` | No | `1.0` | Multiplier (only for `scale_offset` type) |
| `offset` | No | `0.0` | Addition (only for `scale_offset` type) |
| `unit` | No | `""` | Engineering unit string (°C, %, RPM, Pa, etc.) |
| `precision` | No | `1` | Decimal places for rounding the engineering value |

See [Transforms In Depth](#transforms-in-depth) for formulas and examples.

### Control Block (PID)

Optional. When present and enabled, the integration will start a separate async task that continuously reads a sensor, computes a PID output, and writes to an actuator.<br>
Later in the integration this can be overruled (PID started or stopped for example)

```json
"control": {
  "type": "pid",
  "enabled": false,
  "params": {
    "kp": 3.0,
    "ti": 180,
    "td": 0,
    "setpoint_default": 21.0,
    "output_min": 0.0,
    "output_max": 100.0
  },
  "sample_interval": 1.0,
  "input_role": "current_temperature",
  "output_role": "heating_valve"
}
```

| Field | Required | Default | Description |
|---|---|---|---|
| `type` | Yes | — | Control algorithm type. Currently only `"pid"` is supported. |
| `enabled` | No | `false` | Set to `true` to start the control loop on integration load. (or enable later in device UI) |
| `params` | No | `{}` | PID tuning parameters (see [PID Controller In Depth](#pid-controller-in-depth)). |
| `sample_interval` | No | `1.0` | Loop execution interval in seconds. How often the controller reads and writes. |
| `input_role` | Yes | — | The `role` of the IO to read as the process variable (must match an IO role in `ios`). |
| `output_role` | Yes | — | The `role` of the IO to write as the control output (must match an IO role in `ios`). |

---

## Device Types and Roles

Each device type expects certain IO roles. Roles determine which Home Assistant entity type is created and how the entity behaves.

### AHU (Air Handling Unit)

Type: `"ahu"` — Creates a **Climate** entity as the primary control, plus sensor entities for monitoring.

| Role | Direction | Data Type | Required | HA Entity | Description |
|---|---|---|---|---|---|
| `fan_command` | output | bool | Yes | (part of Climate) | Start/stop the supply fan |
| `fan_status` | input | bool | No | (part of Climate) | Fan running feedback |
| `current_temperature` | input | analog | Yes | (part of Climate) | Supply/return air temperature sensor |
| `heating_valve` | output | analog | No | Sensor (monitoring) | Heating coil valve position |
| `cooling_valve` | output | analog | No | Sensor (monitoring) | Cooling coil valve position |
| `damper_position` | output | analog | No | Sensor (monitoring) | Fresh air damper position |
| `filter_alarm` | input | bool | No | Binary Sensor | Filter differential pressure alarm |
| `frost_alarm` | input | bool | No | Binary Sensor | Frost protection alarm |

The Climate entity supports HVAC modes OFF, HEAT, and AUTO (when PID is enabled). When a `cooling_valve` IO is present, the COOL mode is also available. The `hvac_action` is derived from fan status and valve positions — reporting COOLING when the cooling valve is open (>5%), HEATING when the heating valve is open, or IDLE otherwise.

### Fan

Type: `"fan"` — Creates a **Fan** entity with on/off and optional speed percentage.

| Role | Direction | Data Type | Required | HA Entity | Description |
|---|---|---|---|---|---|
| `fan_command` | output | bool | Yes | (part of Fan) | Start/stop command |
| `fan_status` | input | bool | No | Binary Sensor | Running feedback |
| `speed_command` | output | analog | No | (part of Fan) | Speed setpoint 0-100% |

When `speed_command` is present, the Fan entity gains speed percentage control (slider). Without it, only on/off is available.

### Valve

Type: `"valve"` — Creates a **Number** entity (slider 0-100%) for modulating valve position.

| Role | Direction | Data Type | Required | HA Entity | Description |
|---|---|---|---|---|---|
| `position_command` | output | analog | Yes | Number (slider) | Valve position command 0-100% |
| `position_feedback` | input | analog | No | Sensor | Actual valve position feedback |

### Damper

Type: `"damper"` — Creates a **Cover** entity with position control (0-100%), using the `damper` device class.

| Role | Direction | Data Type | Required | HA Entity | Description |
|---|---|---|---|---|---|
| `position_command` | output | analog | Yes | (part of Cover) | Damper position command 0-100% |
| `position_feedback` | input | analog | No | Sensor | Actual damper position feedback |

---

## How Templates are Used

### Adding a Device via Options Flow

1. Open the integration in Home Assistant → Configure
2. Select **"Add building device"** from the action dropdown
3. Pick a template from the dropdown (shows both built-in and user templates)
4. On the confirmation screen:
   - **Name** the device (defaults to the template's name)
   - **Remap IOs** — each IO from the template is shown with its default `io_name`, and you can change it to match your actual PiCtory configuration
5. The integration validates that all IO names exist in your RevPi
6. On save, the integration reloads and the new device + entities appear

### IO Remapping

The `io_name` values in a template are defaults (placeholders). During the Options flow, every IO is presented for remapping. For example, if your template says `"io_name": "AI_AHU_SUPPLY_TEMP"` but your PiCtory config uses `"SupplyTemp_1"`, you replace it in the confirmation step.

This means a single template works across different RevPi installations regardless of IO naming conventions.

### Persistence

Building device configurations are stored in `entry.options["building_devices"]` — a list of fully resolved template dicts (with remapped IO names). This persists across reboots. When the integration loads, it reads this list, creates handlers for each device, and registers the corresponding HA entities.

Changing options triggers a full integration reload via the existing `update_listener`.

---

## Transforms In Depth

All transforms are **bidirectional**. Reading an input uses the forward direction (raw → engineering). Writing an output uses the inverse direction (engineering → raw). The raw value written to the process image is always an integer.

### Linear

The standard and most common transform. Maps a raw range to an engineering range proportionally.

**Forward** (reading):
```
ratio = (raw - input_min) / (input_max - input_min)
engineering = output_min + ratio * (output_max - output_min)
```

**Inverse** (writing):
```
ratio = (engineering - output_min) / (output_max - output_min)
raw = input_min + ratio * (input_max - input_min)
```

**Example — Temperature sensor (0-10V = -20°C to +80°C):**
```json
{
  "type": "linear",
  "input_min": 0,
  "input_max": 10000,
  "output_min": -20.0,
  "output_max": 80.0,
  "unit": "°C",
  "precision": 1
}
```
- Raw 0 → -20.0°C
- Raw 5000 → 30.0°C
- Raw 10000 → 80.0°C

**Example — Valve/damper position (0-10V = 0-100%):**
```json
{
  "type": "linear",
  "input_min": 0,
  "input_max": 10000,
  "output_min": 0.0,
  "output_max": 100.0,
  "unit": "%",
  "precision": 0
}
```
- 50% → writes raw 5000 (5V)
- Raw 7500 → reads as 75%

### Inverse Linear

For actuators where the signal is inverted — typically normally-open valves where 10V means fully closed and 0V means fully open.

**Forward** (reading):
```
ratio = (raw - input_min) / (input_max - input_min)
engineering = output_max - ratio * (output_max - output_min)
```

**Inverse** (writing):
```
ratio = (output_max - engineering) / (output_max - output_min)
raw = input_min + ratio * (input_max - input_min)
```

**Example — Normally-open heating valve:**
```json
{
  "type": "inverse_linear",
  "input_min": 0,
  "input_max": 10000,
  "output_min": 0.0,
  "output_max": 100.0,
  "unit": "%",
  "precision": 0
}
```
- Command 100% open → writes raw 0 (0V)
- Command 0% open (closed) → writes raw 10000 (10V)
- Raw 5000 → reads as 50% open

This is common in HVAC: normally-open valves fail to the open position on signal loss (safety feature for heating coils to prevent freeze damage).

### Scale + Offset

A simple `y = x * scale + offset` transform. Useful when the relationship is already in convenient units or for sensors that output a direct proportional signal.

**Forward**: `engineering = raw * scale + offset`
**Inverse**: `raw = (engineering - offset) / scale`

**Example — Pressure sensor where 1 mV = 1 Pa:**
```json
{
  "type": "scale_offset",
  "scale": 1.0,
  "offset": 0.0,
  "unit": "Pa",
  "precision": 0
}
```

**Example — Sensor with offset calibration:**
```json
{
  "type": "scale_offset",
  "scale": 0.01,
  "offset": -5.0,
  "unit": "bar",
  "precision": 2
}
```

### No Transform (bool)

Digital IOs with `"data_type": "bool"` do not use transforms. The raw value is read/written as a boolean directly (truthy/falsy). No `transform` field is needed.

---

## PID Controller In Depth

### Parameters

| Parameter | Default | Description |
|---|---|---|
| `kp` | `3.0` | Proportional gain. Higher = more aggressive response. |
| `ti` | `180.0` | Integral time in seconds. Time to eliminate steady-state error. Set to `0` to disable integral action. |
| `td` | `0.0` | Derivative time in seconds. Dampens overshoot. Usually `0` for HVAC (slow processes). |
| `setpoint_default` | `21.0` | Initial setpoint when the integration starts. The user can change it live via the Climate entity. |
| `output_min` | `0.0` | Minimum output value (clamped). |
| `output_max` | `100.0` | Maximum output value (clamped). |

The controller uses **anti-windup clamping**: when the output saturates (hits min or max), the integral term stops accumulating to prevent windup.

### How It Runs

1. The PID loop runs as a **separate `asyncio` task**, decoupled from the coordinator's poll interval
2. Every `sample_interval` seconds (default 1.0s, configurable per template):
   - Reads the measured value from the `input_role` IO (e.g., `current_temperature`)
   - Applies the forward transform to get engineering units
   - Computes PID output
   - Applies the inverse transform to get raw value
   - Writes to the `output_role` IO (e.g., `heating_valve`)
3. When the user changes the target temperature in the Climate entity, the setpoint is updated immediately on the controller instance
4. The task is cancelled cleanly when the integration unloads

### Tuning

For typical HVAC heating control:

- Start with `kp = 2.0`, `ti = 300`, `td = 0`
- If the temperature settles below the setpoint: increase `kp` or decrease `ti`
- If the temperature oscillates: decrease `kp` or increase `ti`
- `td` is rarely needed for HVAC — thermal processes are slow and noisy, derivative action amplifies noise
- `sample_interval` of 1-5 seconds is typical; faster than the process dynamics is fine, it just means most samples result in small corrections

---

## Creating Your Own Templates

### Step-by-Step Guide

1. **Create the user templates directory** (if it doesn't exist):
   ```
   mkdir -p <config_dir>/ha_revpi/templates
   ```

2. **Create a new JSON file**, e.g. `my_ahu.json`:
   ```json
   {
     "schema_version": 1,
     "name": "My Custom AHU",
     "type": "ahu",
     "manufacturer": "Systemair",
     "model": "VTC 300",
     "description": "Compact AHU with electric heating",
     "ios": {
       "fan_command": {
         "io_name": "O_1",
         "role": "fan_command",
         "direction": "output",
         "data_type": "bool",
         "description": "Fan relay output"
       },
       "supply_temp": {
         "io_name": "I_1",
         "role": "current_temperature",
         "direction": "input",
         "data_type": "analog",
         "transform": {
           "type": "linear",
           "input_min": 0,
           "input_max": 10000,
           "output_min": -30.0,
           "output_max": 70.0,
           "unit": "°C",
           "precision": 1
         }
       },
       "heating_valve": {
         "io_name": "O_2",
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
         }
       }
     }
   }
   ```

3. **Reload the integration** (or go to Configure → Add building device) — your template appears in the dropdown as `"My Custom Ahu (User)"`

4. **Remap the IO names** in the confirmation step to match your PiCtory configuration

### Validation Rules

When a template is loaded, the following validation is applied:

- **Required top-level fields**: `schema_version`, `name`, `type`, `ios`
- **Valid device types**: `ahu`, `fan`, `valve`, `damper`, `pump`
- **Each IO must have**: `io_name`, `role`, `direction`, `data_type`
- **Valid directions**: `input`, `output`
- **Valid data types**: `bool`, `analog`
- **Valid transform types**: `linear`, `inverse_linear`, `scale_offset`
- **Control block** (if present): must have `type`, `input_role`, and `output_role`
- **IO mapping validation** (at Options flow time): every `io_name` must exist in the RevPi process image

If validation fails, the template is rejected with an error message indicating what's wrong.

### Example: Custom Cooling AHU

An AHU with both heating and cooling valves, where the cooling valve is normally-open (inverse signal):

```json
{
  "schema_version": 1,
  "name": "AHU with Cooling",
  "type": "ahu",
  "description": "4-pipe AHU with heating and cooling coils",
  "ios": {
    "fan_cmd": {
      "io_name": "DO_FAN",
      "role": "fan_command",
      "direction": "output",
      "data_type": "bool"
    },
    "fan_fb": {
      "io_name": "DI_FAN_RUN",
      "role": "fan_status",
      "direction": "input",
      "data_type": "bool"
    },
    "supply_temp": {
      "io_name": "AI_SUPPLY",
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
      }
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
        "precision": 0
      }
    },
    "clg_valve": {
      "io_name": "AO_CLG",
      "role": "cooling_valve",
      "direction": "output",
      "data_type": "analog",
      "transform": {
        "type": "inverse_linear",
        "input_min": 0,
        "input_max": 10000,
        "output_min": 0.0,
        "output_max": 100.0,
        "unit": "%",
        "precision": 0
      },
      "description": "Normally-open cooling valve (0V=open, 10V=closed)"
    },
    "filter": {
      "io_name": "DI_FILTER",
      "role": "filter_alarm",
      "direction": "input",
      "data_type": "bool"
    },
    "frost": {
      "io_name": "DI_FROST",
      "role": "frost_alarm",
      "direction": "input",
      "data_type": "bool"
    }
  },
  "control": {
    "type": "pid",
    "enabled": true,
    "params": {
      "kp": 2.5,
      "ti": 240,
      "td": 0,
      "setpoint_default": 21.0,
      "output_min": 0.0,
      "output_max": 100.0
    },
    "sample_interval": 2.0,
    "input_role": "current_temperature",
    "output_role": "heating_valve"
  }
}
```

### Example: Normally-Closed Valve

A simple 2-wire valve that opens with increasing signal (standard behaviour):

```json
{
  "schema_version": 1,
  "name": "Hot Water Valve",
  "type": "valve",
  "manufacturer": "Belimo",
  "model": "LR24A-SR",
  "ios": {
    "position": {
      "io_name": "AO_HW_VALVE",
      "role": "position_command",
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
      }
    },
    "feedback": {
      "io_name": "AI_HW_VALVE_FB",
      "role": "position_feedback",
      "direction": "input",
      "data_type": "analog",
      "transform": {
        "type": "linear",
        "input_min": 0,
        "input_max": 10000,
        "output_min": 0.0,
        "output_max": 100.0,
        "unit": "%",
        "precision": 0
      }
    }
  }
}
```

---

## Full Reference Example

Below is a fully annotated AHU template using every available feature:

```json
{
  "schema_version": 1,
  "name": "AHU Supply Unit",
  "type": "ahu",
  "manufacturer": "Swegon",
  "model": "Gold RX 04",
  "description": "Full-featured supply AHU with heating, damper, and alarms",

  "ios": {
    "supply_fan_command": {
      "io_name": "DO_AHU_FAN",
      "role": "fan_command",
      "direction": "output",
      "data_type": "bool",
      "description": "Supply fan start/stop relay"
    },
    "supply_fan_status": {
      "io_name": "DI_AHU_FAN_FB",
      "role": "fan_status",
      "direction": "input",
      "data_type": "bool",
      "description": "Supply fan running feedback (aux contact)"
    },
    "supply_temp": {
      "io_name": "AI_AHU_SUPPLY_TEMP",
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
      "description": "Supply air NTC sensor via transmitter (0-10V = -20..+80°C)"
    },
    "heating_valve": {
      "io_name": "AO_AHU_HTG_VALVE",
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
      "description": "Hot water heating coil valve (0-10V = 0-100% open)"
    },
    "damper_position": {
      "io_name": "AO_AHU_DAMPER",
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
      "description": "Fresh air damper actuator (0-10V = 0-100% open)"
    },
    "filter_alarm": {
      "io_name": "DI_AHU_FILTER",
      "role": "filter_alarm",
      "direction": "input",
      "data_type": "bool",
      "description": "Filter differential pressure switch (NO contact)"
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
      "output_max": 100.0
    },
    "sample_interval": 1.0,
    "input_role": "current_temperature",
    "output_role": "heating_valve"
  }
}
```

This template:
- Creates a **Climate** entity (the main AHU control) with OFF/HEAT/AUTO modes (COOL is added when a `cooling_valve` IO is defined)
- Creates a **Binary Sensor** for the filter alarm
- Creates **Sensor** entities monitoring heating valve and damper positions
- Can optionally run a **PID controller** that reads `supply_temp` and drives `heating_valve` (set `"enabled": true` to activate)
- All IO names can be remapped during the Options flow to match your PiCtory
