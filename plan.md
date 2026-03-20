# MQTT Publisher Implementation Plan

## Overview
Add optional MQTT publishing to ha_revpi. Publishes scalar values on change, rate-limited to a configurable minimum interval. Standalone paho-mqtt client. Disabled by default; user enables and configures via the options flow.

## Config Structure (entry.options)
```json
{
  "mqtt": {
    "enabled": false,
    "broker": "192.168.1.100",
    "port": 1883,
    "username": "",
    "password": "",
    "main_topic": "site1",
    "publish_interval": 5,
    "publish_core": false,
    "publish_devices": []
  }
}
```
- `publish_interval`: minimum seconds between publishes of the same topic (default 5, configurable 1–60)
- `publish_core`: enable Tier 2 core diagnostics (cpu_temperature, cpu_frequency, io_cycle, picontrol_running)
- `publish_devices`: list of building device names to publish (Tier 1+2)

## Topic Structure
```
{main_topic}/revpi/core/cpu_temperature          → 52.3
{main_topic}/revpi/core/cpu_frequency             → 1500
{main_topic}/revpi/core/io_cycle                  → 8
{main_topic}/revpi/core/picontrol_running         → true

{main_topic}/revpi/devices/{device_name}/temperature     → 21.5
{main_topic}/revpi/devices/{device_name}/heating_valve    → 45
{main_topic}/revpi/devices/{device_name}/cooling_valve    → 0
{main_topic}/revpi/devices/{device_name}/fan_status       → true
{main_topic}/revpi/devices/{device_name}/fan_command      → true
{main_topic}/revpi/devices/{device_name}/damper_position  → 80
{main_topic}/revpi/devices/{device_name}/pid_output       → 62.5
{main_topic}/revpi/devices/{device_name}/alarms/filter_alarm → false
{main_topic}/revpi/devices/{device_name}/alarms/frost_alarm  → false
```
- Device name is slugified (lowercased, spaces→underscores)
- All payloads are scalar strings (the number or true/false)

## New Files

### 1. `custom_components/ha_revpi/mqtt_client.py`
Thin paho-mqtt wrapper:
- `MQTTClient(broker, port, username, password)`
- `async connect(hass)` — runs `loop_start()` in executor
- `async disconnect(hass)` — runs `loop_stop()`+`disconnect()` in executor
- `async publish(hass, topic, payload, qos=0, retain=True)` — publishes in executor
- `is_connected` property
- Reconnection handled by paho's built-in `reconnect_on_failure`

### 2. `custom_components/ha_revpi/mqtt_publisher.py`
Core publishing logic:
- `MQTTPublisher(hass, client, config, coordinator, handlers)`
- Registers as a coordinator update listener via `coordinator.async_add_listener()`
- On each coordinator update callback:
  1. If `publish_core`: collect `coordinator.data.core_values`, compare to last published, publish changed values respecting `publish_interval`
  2. For each device name in `publish_devices`: find handler, read engineering values for all IO mappings, read PID output, compare, publish changed values
- Tracks `_last_values: dict[str, Any]` and `_last_publish_time: dict[str, float]` per topic
- `async start()` — connect client, register listener
- `async stop()` — unregister listener, disconnect client

## Modified Files

### 3. `custom_components/ha_revpi/const.py`
Add constants:
```python
CONF_MQTT = "mqtt"
CONF_MQTT_BROKER = "mqtt_broker"
CONF_MQTT_PORT = "mqtt_port"
CONF_MQTT_USERNAME = "mqtt_username"
CONF_MQTT_PASSWORD = "mqtt_password"
CONF_MQTT_MAIN_TOPIC = "mqtt_main_topic"
CONF_MQTT_PUBLISH_INTERVAL = "mqtt_publish_interval"
CONF_MQTT_PUBLISH_CORE = "mqtt_publish_core"
CONF_MQTT_PUBLISH_DEVICES = "mqtt_publish_devices"
DEFAULT_MQTT_PORT = 1883
DEFAULT_MQTT_PUBLISH_INTERVAL = 5
```

### 4. `custom_components/ha_revpi/config_flow.py`
Add to options flow:
- New action in `async_step_init`: "Configure MQTT publishing"
- New step `async_step_mqtt`: form with broker, port, username, password, main_topic, publish_interval, publish_core toggle, publish_devices multi-select (populated from existing building device names)
- Saves to `entry.options["mqtt"]`

### 5. `custom_components/ha_revpi/__init__.py`
- In `async_setup_entry`: after PID controllers start, call `_start_mqtt_publisher()`
- New `_start_mqtt_publisher(hass, entry)`: reads mqtt config from options, creates client + publisher, stores in `hub_data["mqtt_publisher"]`
- In `async_unload_entry`: call `publisher.stop()` before cleanup
- In `update_listener`: handle mqtt config changes (stop old publisher, start new one) without full reload — extend `skip_reload` pattern

### 6. `custom_components/ha_revpi/manifest.json`
Add `paho-mqtt>=2.0.0` to requirements.

### 7. `tests/test_mqtt_publisher.py`
- Test change detection (value same → no publish, value changed → publish)
- Test rate limiting (changed but within interval → skip, after interval → publish)
- Test core values publishing
- Test device values publishing (mock handler with IO mappings)
- Test topic structure
- Test connect/disconnect lifecycle

## Implementation Order
1. `const.py` — add constants
2. `manifest.json` — add paho-mqtt dependency
3. `mqtt_client.py` — paho wrapper
4. `mqtt_publisher.py` — change detection + publishing logic
5. `config_flow.py` — MQTT options step
6. `__init__.py` — wire up start/stop
7. `tests/test_mqtt_publisher.py` — tests
