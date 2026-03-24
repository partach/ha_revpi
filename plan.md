# Implementation Plan: Building Device Card, MQTT Status & Subscribe

## Overview
Four enhancements, implemented in order:
1. **Building Device + PID Visualization Card** — combined dashboard per building device
2. **MQTT Status Entity** — binary_sensor + diagnostics for MQTT connection health
3. **MQTT Setpoint Subscribe** — external systems can write setpoints via MQTT
4. (Future) Template editor UI

---

## 1. Building Device + PID Visualization Card

### New file: `custom_components/ha_revpi/frontend/revpi-building-card.js`

A Lit-Element card (same patterns as revpi-ports-card.js) that shows a complete
building device overview with PID visualization.

### Config editor
- **Device selector**: filtered to building devices only (device identifiers contain `_bld`)
- **Trend window**: dropdown for time window (5min, 15min, 30min, 1hr) — default 15min
- No other config needed; the card auto-discovers everything from the device's entities

### Card layout (top to bottom)

#### A. Header
- Device type badge (AHU/Fan/Valve/Damper) with icon + device name
- HVAC mode badge: **Heating** (orange) / **Cooling** (blue) / **Idle** (grey)
  derived from PID output direction and magnitude

#### B. Current Values Strip
- Horizontal bar showing key values as labeled boxes:
  - Temperature (measured value) — large font
  - Setpoint — editable on click (calls number.set_value on the climate entity)
  - PID Output % — with color gradient bar (0=blue, 50=grey, 100=orange)
  - Error (setpoint - measured) — green if small, red if large
- For non-PID devices (valve, damper, fan): show position/speed/status instead

#### C. PID Trend Chart (only shown if PID entities exist)
- Canvas-based rolling chart, three lines:
  - **Setpoint** — dashed orange line
  - **Measured** — solid blue line
  - **PID Output** — solid green line (right Y-axis, 0-100%)
- Left Y-axis: temperature scale (auto-ranged from data)
- Right Y-axis: output % (fixed 0-100)
- X-axis: time labels (relative: -15m, -10m, -5m, now)
- Data accumulation:
  - On each `hass` update, push current values into a ring buffer
  - Buffer size = (time_window_seconds / coordinator_poll_interval)
  - Stored per card instance (client-side only, resets on page reload)
- Saturation band: light red/blue shading when output is at min or max

#### D. IO Status Grid
- 2-column grid showing all device IOs with their current engineering values:
  - Fan command/status (toggle switch if output)
  - Heating valve % (editable number if output)
  - Cooling valve % (editable number if output)
  - Damper position % (editable if output, cover controls)
  - Any other mapped IOs
- Same interactive patterns as existing card (click to edit numbers, toggle switches)

#### E. Alarm Strip
- Horizontal bar at bottom, one cell per alarm IO (filter_alarm, frost_alarm, etc.)
- Green when false, red pulsing when true
- Label + icon per alarm

#### F. PID Tuning Panel (collapsible)
- Collapsed by default, expand via "Tuning" button
- Shows PID parameters as inline-editable number fields:
  - Kp, Ti, Td, Output Min, Output Max, Sample Interval
- PID Enable toggle switch
- All use hass.callService("number", "set_value", ...) and
  hass.callService("switch", "turn_on/off", ...)

### Entity discovery logic
```
Filter hass.entities by device_id → categorize:
  - climate.*         → main climate entity (setpoint + hvac mode)
  - sensor.*pid_output* → PID output value
  - switch.*pid_enable* → PID enable toggle
  - number.*pid_*     → PID parameters
  - sensor.*          → input sensors (temperature, feedback)
  - switch.*          → output switches (fan command)
  - number.*          → output numbers (valve position) — exclude PID params
  - fan.*             → fan entity
  - cover.*           → damper/cover entity
  - binary_sensor.*alarm* → alarm entities (future)
```

### Registration
- In `__init__.py` `_async_install_frontend_resource`: copy new JS file alongside existing one
- In `_async_register_card`: register as second custom card resource
- Card type name: `revpi-building-card`

### Trend data structure (in-memory, per card instance)
```javascript
this._trendData = {
  timestamps: [],      // Date objects
  setpoint: [],        // float array
  measured: [],        // float array
  pidOutput: [],       // float array (0-100)
  maxPoints: 900,      // 15min at 1s interval
};
```

---

## 2. MQTT Status Entity

### Goal
Expose MQTT connection health as HA entities so users can see status in dashboards
and create automations on connection loss.

### New file: `custom_components/ha_revpi/mqtt_entities.py`

#### Entities created (only when MQTT is enabled in config):

1. **RevPiMQTTStatusSensor** (binary_sensor)
   - `unique_id`: `{entry_id}_mqtt_status`
   - `device_class`: BinarySensorDeviceClass.CONNECTIVITY
   - `entity_category`: EntityCategory.DIAGNOSTIC
   - `is_on`: reads `mqtt_publisher.client.is_connected`
   - Attached to the core device

2. **RevPiMQTTMessageCountSensor** (sensor)
   - `unique_id`: `{entry_id}_mqtt_message_count`
   - `state_class`: SensorStateClass.TOTAL_INCREASING
   - `entity_category`: EntityCategory.DIAGNOSTIC
   - `native_value`: reads `mqtt_publisher.message_count`

3. **RevPiMQTTLastPublishSensor** (sensor)
   - `unique_id`: `{entry_id}_mqtt_last_publish`
   - `device_class`: SensorDeviceClass.TIMESTAMP
   - `entity_category`: EntityCategory.DIAGNOSTIC
   - `native_value`: reads `mqtt_publisher.last_publish_time` as datetime

### Changes to `mqtt_publisher.py`
Add tracking attributes:
```python
self._message_count: int = 0
self._last_publish_time: datetime | None = None

@property
def message_count(self) -> int: ...

@property
def last_publish_time(self) -> datetime | None: ...
```
Increment `_message_count` and update `_last_publish_time` in `_do_publish()`.

### Changes to `__init__.py`
- Store `mqtt_publisher` in hub_data (already done)
- MQTT entities read from hub_data at coordinator update time

### Changes to platform files
- Add `binary_sensor.py` platform (new file, or extend sensor.py)
- Add Platform.BINARY_SENSOR to PLATFORMS list
- In `async_setup_entry` for binary_sensor: check if MQTT publisher exists,
  create status entity

### Coordinator listener for entity updates
MQTT entities register as coordinator listeners so they update on each poll cycle.
The binary_sensor reads `client.is_connected`, the sensors read publisher stats.

---

## 3. MQTT Setpoint Subscribe

### Design principle (from user)
> The integration/automations should be normally in control.
> Only setpoints are OK to override — they are master/slave agnostic.

This means:
- **Subscribe to setpoint topics only** — no fan commands, no valve overrides
- **Validate range** before applying (respect PID output_min/output_max for setpoint bounds)
- **Log all external writes** at INFO level for auditability
- **Publish back** the confirmed value so the external system knows it was accepted

### Subscribe topics
```
{main_topic}/revpi/devices/{device_slug}/set/setpoint    → PID setpoint (float)
{main_topic}/revpi/devices/{device_slug}/set/pid_enable   → PID on/off ("true"/"false")
```

Using `set/` prefix convention (common in HA MQTT) to separate commands from state topics.

### Changes to `mqtt_client.py`
Add subscribe and message callback support:
```python
def _on_message(self, client, userdata, msg) -> None:
    """Forward received messages to registered callback."""
    if self._message_callback:
        self._message_callback(msg.topic, msg.payload.decode("utf-8"))

def set_message_callback(self, callback: Callable[[str, str], None]) -> None:
    """Register callback for incoming messages."""
    self._message_callback = callback
    if self._client is not None:
        self._client.on_message = self._on_message

def subscribe(self, topic: str, qos: int = 0) -> None:
    """Subscribe to a topic (blocking, call from executor)."""
    self._client.subscribe(topic, qos=qos)
```

### Changes to `mqtt_publisher.py` → rename concept to `mqtt_bridge.py`?
Or keep as `mqtt_publisher.py` and add subscribe handling:

```python
async def _setup_subscriptions(self) -> None:
    """Subscribe to setpoint command topics for enabled devices."""
    self._client.set_message_callback(self._on_mqtt_message)
    for device_name in self._publish_devices:
        slug = self._slugify(device_name)
        topic = f"{self._main_topic}/revpi/devices/{slug}/set/+"
        await self.hass.async_add_executor_job(
            self._client.subscribe, topic
        )
    _LOGGER.info("MQTT subscribed to setpoint topics for %d devices",
                 len(self._publish_devices))

def _on_mqtt_message(self, topic: str, payload: str) -> None:
    """Handle incoming MQTT message (runs in paho thread)."""
    # Parse topic: {main_topic}/revpi/devices/{slug}/set/{command}
    # Schedule coroutine on HA event loop
    self.hass.loop.call_soon_threadsafe(
        self.hass.async_create_task,
        self._async_handle_command(topic, payload)
    )

async def _async_handle_command(self, topic: str, payload: str) -> None:
    """Process a setpoint command from MQTT."""
    parts = topic.split("/")
    # Expected: [main_topic, "revpi", "devices", slug, "set", command]
    if len(parts) < 6 or parts[-2] != "set":
        return

    slug = parts[-3]
    command = parts[-1]
    handler = self._find_handler_by_slug(slug)
    if handler is None:
        _LOGGER.warning("MQTT command for unknown device: %s", slug)
        return

    if command == "setpoint":
        await self._handle_setpoint(handler, payload)
    elif command == "pid_enable":
        await self._handle_pid_enable(handler, payload)
    else:
        _LOGGER.warning("MQTT unknown command: %s", command)

async def _handle_setpoint(self, handler, payload: str) -> None:
    """Apply setpoint from MQTT to PID controller."""
    try:
        value = float(payload)
    except ValueError:
        _LOGGER.warning("MQTT invalid setpoint value: %s", payload)
        return

    pid = getattr(handler, "pid_controller", None)
    if pid is None:
        _LOGGER.warning("MQTT setpoint for %s but no PID controller", handler.name)
        return

    # Validate range (use reasonable bounds, not output_min/max which is for output)
    # Setpoint bounds could be added to template config; for now accept any float
    old = pid.setpoint
    pid.setpoint = value
    _LOGGER.info(
        "MQTT setpoint for %s changed: %.1f → %.1f (external)",
        handler.name, old, value
    )

    # Publish confirmed value back
    slug = self._slugify(handler.name)
    topic = f"{self._main_topic}/revpi/devices/{slug}/setpoint"
    await self.hass.async_add_executor_job(
        self._client.publish, topic, str(value)
    )
```

### Config flow change
Add option in MQTT config step:
- **Allow external setpoints** — boolean toggle (default: False)
- Only subscribes when explicitly enabled by user (safety-first)

### Safety considerations
- Subscribe feature is opt-in (disabled by default)
- Only setpoint and PID enable are writable — no direct IO writes
- All external writes logged at INFO level
- Confirmed value published back for verification
- If PID is disabled externally via MQTT, it can be re-enabled the same way
  or via the HA UI (no lock-out)

---

## 4. Implementation Order

### Phase 1: MQTT Status Entity
- Smallest scope, foundational for Phase 3
- Files: mqtt_entities.py (new), binary_sensor.py (new), mqtt_publisher.py (modify),
  __init__.py (modify), const.py (modify)
- Tests: test_mqtt_entities.py

### Phase 2: MQTT Subscribe for Setpoints
- Extends MQTT client and publisher
- Files: mqtt_client.py (modify), mqtt_publisher.py (modify),
  config_flow.py (modify), const.py (modify), strings.json (modify)
- Tests: test_mqtt_subscribe.py

### Phase 3: Building Device + PID Card
- Largest scope, purely frontend
- Files: revpi-building-card.js (new), __init__.py (modify for registration)
- No Python tests needed (JS card), but manual testing required

### Phase 4: (Future) Template editor UI
- Deferred per user request

---

## File Summary

### New files
1. `custom_components/ha_revpi/frontend/revpi-building-card.js`
2. `custom_components/ha_revpi/mqtt_entities.py`
3. `custom_components/ha_revpi/binary_sensor.py`
4. `tests/test_mqtt_entities.py`
5. `tests/test_mqtt_subscribe.py`

### Modified files
1. `custom_components/ha_revpi/mqtt_client.py` — add subscribe + message callback
2. `custom_components/ha_revpi/mqtt_publisher.py` — add stats tracking + subscribe handling
3. `custom_components/ha_revpi/__init__.py` — register new card, add BINARY_SENSOR platform
4. `custom_components/ha_revpi/config_flow.py` — add "allow external setpoints" toggle
5. `custom_components/ha_revpi/const.py` — new constants
6. `custom_components/ha_revpi/strings.json` — new UI strings
7. `custom_components/ha_revpi/translations/en.json` — translations
