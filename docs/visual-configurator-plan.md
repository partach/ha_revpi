# Visual Device Configurator — Implementation Plan

## Overview

Replace manual JSON template editing with a visual UI for configuring building devices (AHU, Fan, Valve, Damper, Pump). Users should be able to wire RevPi IOs to device roles, configure transforms, and set up PID control — all from within Home Assistant.

## Current Flow (Template-Based)

1. User writes a JSON template file (or uses a built-in one)
2. Config flow: pick template → name device → map each IO slot to real RevPi hardware
3. Template defines: device type, IO slots (role, direction, data_type, transform), optional PID control

## Architecture

Three layers need to be built:

---

### Layer 1: Backend WebSocket API

Endpoints the frontend needs that don't exist yet:

| Endpoint | Purpose |
|---|---|
| `ha_revpi/get_available_ios` | List all RevPi IOs with their module, direction, data type — for the IO picker |
| `ha_revpi/get_device_type_roles` | For a given device type, return expected/optional roles with metadata |
| `ha_revpi/validate_device_config` | Live validation of a partial config as the user builds it |
| `ha_revpi/save_template` | Save a user template JSON to `config/ha_revpi/templates/` |
| `ha_revpi/save_device` | Save directly as a building device (skip template, write to config entry) |
| `ha_revpi/get_io_preview` | Read current live value of an IO (helps user verify correct wiring) |

---

### Layer 2: Frontend — Visual Device Builder

A HA panel (custom panel or full-page card) built with Lit, using these steps:

#### Step 1 — Device Basics
- Pick device type (AHU, Fan, Valve, Damper, Pump) — cards with icons and descriptions
- Name, manufacturer, model fields

#### Step 2 — IO Wiring
- **Left panel**: Available RevPi IOs grouped by module, filterable by direction/type
- **Center**: Device schematic showing IO slots for the chosen type
  - AHU: fan, temp sensor, heating valve, cooling valve, damper, alarms
  - Fan: motor command, speed control, feedback
  - Valve/Damper: position command + feedback
- Each slot shows: role name, direction badge (IN/OUT), data type badge (DIGITAL/ANALOG)
- Incompatible IOs greyed out (can't assign digital input to analog output slot)
- Live value preview when IO is hovered/selected
- "Add custom IO slot" for non-standard roles

#### Step 3 — Transform Configuration
For each analog IO:
- Type picker: Linear / Inverse Linear / Scale+Offset
- Input range ↔ Output range fields
- Unit picker (°C, %, bar, m³/h, etc.)
- Precision selector (decimal places)
- Live preview: "Raw value X → Engineering value Y" calculator
- Optional: mini graph showing the mapping curve

#### Step 4 — PID Control (Optional)
- Toggle to enable PID section
- Input role dropdown (from configured input IOs)
- Output role dropdown (from configured output IOs)
- PID parameter fields with sensible defaults: Kp, Ti, Td
- Output limits: min/max %
- Sample interval
- Visual PID block diagram preview (reuse the building card's PID diagram)

#### Step 5 — Review & Save
- Summary view showing complete configuration
- Save as: **template** (reusable for future devices) or **device** (one-off, added directly)
- Export as JSON option

---

### Layer 3: Predefined Role Catalogs

Data structure mapping each device type to its standard IO roles. Drives the visual schematic and validation.

```
AHU:
  ├─ fan_command        (output, bool, REQUIRED)
  ├─ fan_status         (input, bool, optional)
  ├─ current_temperature (input, analog, REQUIRED)
  ├─ heating_valve      (output, analog, REQUIRED)
  ├─ cooling_valve      (output, analog, optional)
  ├─ damper_position    (output, analog, optional)
  ├─ filter_alarm       (input, bool, optional)
  └─ frost_alarm        (input, bool, optional)

Fan:
  ├─ fan_command        (output, bool, REQUIRED)
  ├─ fan_status         (input, bool, optional)
  └─ speed_command      (output, analog, optional)

Valve:
  ├─ position_command   (output, analog, REQUIRED)
  └─ position_feedback  (input, analog, optional)

Damper:
  ├─ position_command   (output, analog, REQUIRED)
  └─ position_feedback  (input, analog, optional)

Pump:
  ├─ pump_command       (output, bool, REQUIRED)
  ├─ pump_status        (input, bool, optional)
  └─ speed_command      (output, analog, optional)
```

---

## Phased Implementation

| Phase | Scope | Complexity | Description |
|---|---|---|---|
| **Phase 1** | Backend WebSocket API | Medium | Expose IO listing, role catalogs, validation, save endpoints |
| **Phase 2** | Form-based wizard | Medium-High | Step-by-step wizard using standard HA form elements (dropdowns, toggles, number inputs). No drag-drop yet — already a big improvement over JSON editing |
| **Phase 3** | Transform visual editor | Medium | Live preview with range sliders, unit picker, test calculator |
| **Phase 4** | Drag-and-drop IO wiring | High | Device schematic SVGs, drag IOs from module list onto slots, visual wiring lines |
| **Phase 5** | Live preview & polish | Medium | Live IO value readout, PID tuning preview, animations, mobile support |

**Recommended starting point:** Phase 1 + 2 delivers the core value — replacing JSON with a guided UI. Phase 4 is the flashy visual wiring but also the most complex.

---

## File Structure (Proposed)

```
custom_components/ha_revpi/
├── api.py                          # NEW: WebSocket API handlers
├── role_catalog.py                 # NEW: Device type → role definitions
├── frontend/
│   ├── revpi-building-card.js      # Existing building device card
│   ├── revpi-device-configurator.js # NEW: Visual configurator panel
│   ├── components/
│   │   ├── io-picker.js            # NEW: IO selection/drag-drop component
│   │   ├── transform-editor.js     # NEW: Transform configuration UI
│   │   ├── pid-configurator.js     # NEW: PID setup UI
│   │   └── device-schematic.js     # NEW: SVG device diagrams
│   └── assets/
│       ├── ahu-schematic.svg       # NEW: Device type schematics
│       ├── fan-schematic.svg
│       ├── valve-schematic.svg
│       └── damper-schematic.svg
```

---

## Key Design Decisions To Make

1. **Panel vs Card**: Custom HA panel (sidebar entry) gives more screen space; a card keeps it inside dashboards. Panel is better for this use case.
2. **Drag-and-drop library**: Native HTML5 DnD vs a library like Sortable.js / interact.js
3. **SVG schematics**: Hand-drawn per device type vs generated from role catalog
4. **Validation strategy**: Client-side only vs server-side validation via WebSocket
5. **Template vs direct save**: Support both, or push users toward one approach
6. **Mobile support**: Full parity or desktop-only for the configurator
