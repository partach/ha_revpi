"""Tests for the MQTT publisher."""

from __future__ import annotations

import time
from typing import Any
from unittest.mock import MagicMock, call, patch

import pytest

from custom_components.ha_revpi.mqtt_publisher import (
    MQTTPublisher,
    _format_payload,
    _slugify,
)


def _make_mqtt_config(
    publish_core: bool = False,
    publish_devices: list[str] | None = None,
    publish_interval: int = 5,
    main_topic: str = "site1",
) -> dict[str, Any]:
    """Build a minimal MQTT config dict."""
    return {
        "main_topic": main_topic,
        "publish_interval": publish_interval,
        "publish_core": publish_core,
        "publish_devices": publish_devices or [],
    }


def _make_mock_coordinator(
    core_values: dict[str, Any] | None = None,
    io_values: dict[str, Any] | None = None,
) -> MagicMock:
    """Create a mock coordinator with data."""
    coordinator = MagicMock()
    data = MagicMock()
    data.core_values = core_values or {}
    data.io_values = io_values or {}
    coordinator.data = data
    coordinator.async_add_listener = MagicMock(return_value=MagicMock())
    return coordinator


def _make_mock_handler(
    name: str,
    ios: dict[str, dict[str, Any]] | None = None,
    pid_output: float | None = None,
    pid_running: bool = False,
) -> MagicMock:
    """Create a mock building device handler."""
    handler = MagicMock()
    handler.name = name

    # Build IOMapping mocks
    io_mappings: dict[str, MagicMock] = {}
    engineering_values: dict[str, Any] = {}

    for key, conf in (ios or {}).items():
        mapping = MagicMock()
        mapping.role = conf["role"]
        mapping.io_name = conf.get("io_name", key)
        io_mappings[key] = mapping
        engineering_values[id(mapping)] = conf.get("value")

    handler.ios = io_mappings

    def _read_engineering(m: Any) -> Any:
        return engineering_values.get(id(m))

    handler.read_io_engineering = MagicMock(side_effect=_read_engineering)

    # PID controller
    if pid_output is not None:
        pid = MagicMock()
        pid.output = pid_output
        handler.pid_controller = pid
        if pid_running:
            task = MagicMock()
            task.done.return_value = False
            handler._pid_task = task
        else:
            handler._pid_task = None
    else:
        handler.pid_controller = None
        handler._pid_task = None

    return handler


class TestSlugify:
    """Test _slugify helper."""

    def test_basic(self) -> None:
        assert _slugify("Test AHU") == "test_ahu"

    def test_special_chars(self) -> None:
        assert _slugify("AHU-01 (main)") == "ahu_01_main"

    def test_already_clean(self) -> None:
        assert _slugify("ahu01") == "ahu01"


class TestFormatPayload:
    """Test _format_payload helper."""

    def test_bool_true(self) -> None:
        assert _format_payload(True) == "true"

    def test_bool_false(self) -> None:
        assert _format_payload(False) == "false"

    def test_float(self) -> None:
        assert _format_payload(21.5) == "21.50"

    def test_int(self) -> None:
        assert _format_payload(42) == "42"


class TestChangeDetection:
    """Test that publisher only publishes on value change."""

    def test_no_publish_when_value_unchanged(self) -> None:
        """Same value should not trigger a second publish."""
        hass = MagicMock()
        client = MagicMock()
        client.is_connected = True
        coordinator = _make_mock_coordinator(
            core_values={"cpu_temperature": 52.3}
        )
        config = _make_mqtt_config(publish_core=True, publish_interval=0)
        publisher = MQTTPublisher(hass, client, config, coordinator, [])

        # First update — should publish
        publisher._on_update()
        assert hass.async_add_executor_job.call_count == 1
        messages_1 = hass.async_add_executor_job.call_args[0][1]
        assert len(messages_1) == 1
        assert messages_1[0][0] == "site1/revpi/core/cpu_temperature"

        hass.async_add_executor_job.reset_mock()

        # Second update with same value — should NOT publish
        publisher._on_update()
        assert hass.async_add_executor_job.call_count == 0

    def test_publish_when_value_changes(self) -> None:
        """Changed value should trigger a publish."""
        hass = MagicMock()
        client = MagicMock()
        client.is_connected = True
        coordinator = _make_mock_coordinator(
            core_values={"cpu_temperature": 52.3}
        )
        config = _make_mqtt_config(publish_core=True, publish_interval=0)
        publisher = MQTTPublisher(hass, client, config, coordinator, [])

        # First update
        publisher._on_update()
        hass.async_add_executor_job.reset_mock()

        # Change value
        coordinator.data.core_values["cpu_temperature"] = 53.0
        publisher._on_update()
        assert hass.async_add_executor_job.call_count == 1
        messages = hass.async_add_executor_job.call_args[0][1]
        assert messages[0][1] == "53.00"


class TestRateLimiting:
    """Test publish rate limiting."""

    def test_rate_limit_blocks_rapid_changes(self) -> None:
        """Changes within the interval should be skipped."""
        hass = MagicMock()
        client = MagicMock()
        client.is_connected = True
        coordinator = _make_mock_coordinator(
            core_values={"cpu_temperature": 50.0}
        )
        config = _make_mqtt_config(publish_core=True, publish_interval=5)
        publisher = MQTTPublisher(hass, client, config, coordinator, [])

        # First publish
        publisher._on_update()
        assert hass.async_add_executor_job.call_count == 1
        hass.async_add_executor_job.reset_mock()

        # Immediate change — within rate limit
        coordinator.data.core_values["cpu_temperature"] = 51.0
        publisher._on_update()
        assert hass.async_add_executor_job.call_count == 0

    def test_rate_limit_allows_after_interval(self) -> None:
        """Changes after the interval has elapsed should publish."""
        hass = MagicMock()
        client = MagicMock()
        client.is_connected = True
        coordinator = _make_mock_coordinator(
            core_values={"cpu_temperature": 50.0}
        )
        config = _make_mqtt_config(publish_core=True, publish_interval=5)
        publisher = MQTTPublisher(hass, client, config, coordinator, [])

        # First publish
        publisher._on_update()
        hass.async_add_executor_job.reset_mock()

        # Simulate time passing by manipulating the last publish time
        topic = "site1/revpi/core/cpu_temperature"
        publisher._last_publish_time[topic] = time.monotonic() - 6

        # Now change value — should publish
        coordinator.data.core_values["cpu_temperature"] = 51.0
        publisher._on_update()
        assert hass.async_add_executor_job.call_count == 1


class TestCorePublishing:
    """Test Tier 2 core diagnostics publishing."""

    def test_publishes_all_core_values(self) -> None:
        """All core values should be published on first update."""
        hass = MagicMock()
        client = MagicMock()
        client.is_connected = True
        coordinator = _make_mock_coordinator(
            core_values={
                "cpu_temperature": 52.3,
                "cpu_frequency": 1500,
                "io_cycle": 8,
                "picontrol_running": True,
            }
        )
        config = _make_mqtt_config(publish_core=True, publish_interval=0)
        publisher = MQTTPublisher(hass, client, config, coordinator, [])

        publisher._on_update()
        messages = hass.async_add_executor_job.call_args[0][1]
        topics = {m[0] for m in messages}
        assert topics == {
            "site1/revpi/core/cpu_temperature",
            "site1/revpi/core/cpu_frequency",
            "site1/revpi/core/io_cycle",
            "site1/revpi/core/picontrol_running",
        }

    def test_skips_none_values(self) -> None:
        """None values should not be published."""
        hass = MagicMock()
        client = MagicMock()
        client.is_connected = True
        coordinator = _make_mock_coordinator(
            core_values={"cpu_temperature": None, "cpu_frequency": 1500}
        )
        config = _make_mqtt_config(publish_core=True, publish_interval=0)
        publisher = MQTTPublisher(hass, client, config, coordinator, [])

        publisher._on_update()
        messages = hass.async_add_executor_job.call_args[0][1]
        topics = {m[0] for m in messages}
        assert "site1/revpi/core/cpu_temperature" not in topics
        assert "site1/revpi/core/cpu_frequency" in topics

    def test_core_disabled_no_publish(self) -> None:
        """When publish_core is False, no core values should publish."""
        hass = MagicMock()
        client = MagicMock()
        client.is_connected = True
        coordinator = _make_mock_coordinator(
            core_values={"cpu_temperature": 52.3}
        )
        config = _make_mqtt_config(publish_core=False, publish_interval=0)
        publisher = MQTTPublisher(hass, client, config, coordinator, [])

        publisher._on_update()
        assert hass.async_add_executor_job.call_count == 0


class TestDevicePublishing:
    """Test Tier 1 building device publishing."""

    def test_publishes_device_ios(self) -> None:
        """Device IO values should be published by role."""
        hass = MagicMock()
        client = MagicMock()
        client.is_connected = True
        coordinator = _make_mock_coordinator()

        handler = _make_mock_handler(
            "Test AHU",
            ios={
                "supply_temp": {
                    "role": "current_temperature",
                    "value": 21.5,
                },
                "heating_valve": {
                    "role": "heating_valve",
                    "value": 45.0,
                },
                "filter_alarm": {
                    "role": "filter_alarm",
                    "value": False,
                },
            },
        )

        config = _make_mqtt_config(
            publish_devices=["Test AHU"], publish_interval=0
        )
        publisher = MQTTPublisher(
            hass, client, config, coordinator, [handler]
        )

        publisher._on_update()
        messages = hass.async_add_executor_job.call_args[0][1]
        topic_payloads = {m[0]: m[1] for m in messages}

        assert topic_payloads["site1/revpi/devices/test_ahu/current_temperature"] == "21.50"
        assert topic_payloads["site1/revpi/devices/test_ahu/heating_valve"] == "45.00"
        assert topic_payloads["site1/revpi/devices/test_ahu/alarms/filter_alarm"] == "false"

    def test_publishes_pid_output(self) -> None:
        """PID output should be published when controller is running."""
        hass = MagicMock()
        client = MagicMock()
        client.is_connected = True
        coordinator = _make_mock_coordinator()

        handler = _make_mock_handler(
            "Test AHU",
            ios={},
            pid_output=62.5,
            pid_running=True,
        )

        config = _make_mqtt_config(
            publish_devices=["Test AHU"], publish_interval=0
        )
        publisher = MQTTPublisher(
            hass, client, config, coordinator, [handler]
        )

        publisher._on_update()
        messages = hass.async_add_executor_job.call_args[0][1]
        topic_payloads = {m[0]: m[1] for m in messages}
        assert topic_payloads["site1/revpi/devices/test_ahu/pid_output"] == "62.50"

    def test_skips_pid_when_not_running(self) -> None:
        """PID output should not be published when task is not running."""
        hass = MagicMock()
        client = MagicMock()
        client.is_connected = True
        coordinator = _make_mock_coordinator()

        handler = _make_mock_handler(
            "Test AHU",
            ios={},
            pid_output=62.5,
            pid_running=False,
        )

        config = _make_mqtt_config(
            publish_devices=["Test AHU"], publish_interval=0
        )
        publisher = MQTTPublisher(
            hass, client, config, coordinator, [handler]
        )

        publisher._on_update()
        assert hass.async_add_executor_job.call_count == 0

    def test_only_publishes_opted_in_devices(self) -> None:
        """Only devices in publish_devices list should be published."""
        hass = MagicMock()
        client = MagicMock()
        client.is_connected = True
        coordinator = _make_mock_coordinator()

        handler1 = _make_mock_handler(
            "AHU 1",
            ios={"temp": {"role": "temperature", "value": 20.0}},
        )
        handler2 = _make_mock_handler(
            "AHU 2",
            ios={"temp": {"role": "temperature", "value": 22.0}},
        )

        config = _make_mqtt_config(
            publish_devices=["AHU 1"], publish_interval=0
        )
        publisher = MQTTPublisher(
            hass, client, config, coordinator, [handler1, handler2]
        )

        publisher._on_update()
        messages = hass.async_add_executor_job.call_args[0][1]
        topics = {m[0] for m in messages}
        assert "site1/revpi/devices/ahu_1/temperature" in topics
        assert "site1/revpi/devices/ahu_2/temperature" not in topics


class TestTopicStructure:
    """Test topic naming conventions."""

    def test_main_topic_prefix(self) -> None:
        """Custom main topic should be used as prefix."""
        hass = MagicMock()
        client = MagicMock()
        client.is_connected = True
        coordinator = _make_mock_coordinator(
            core_values={"cpu_temperature": 50.0}
        )
        config = _make_mqtt_config(
            publish_core=True, publish_interval=0, main_topic="mysite"
        )
        publisher = MQTTPublisher(hass, client, config, coordinator, [])

        publisher._on_update()
        messages = hass.async_add_executor_job.call_args[0][1]
        assert messages[0][0] == "mysite/revpi/core/cpu_temperature"

    def test_alarm_subtopic(self) -> None:
        """Alarm roles should get alarms/ prefix in topic."""
        hass = MagicMock()
        client = MagicMock()
        client.is_connected = True
        coordinator = _make_mock_coordinator()

        handler = _make_mock_handler(
            "AHU",
            ios={
                "frost": {"role": "frost_alarm", "value": True},
                "temp": {"role": "current_temperature", "value": 21.0},
            },
        )

        config = _make_mqtt_config(
            publish_devices=["AHU"], publish_interval=0
        )
        publisher = MQTTPublisher(
            hass, client, config, coordinator, [handler]
        )

        publisher._on_update()
        messages = hass.async_add_executor_job.call_args[0][1]
        topics = {m[0] for m in messages}
        assert "site1/revpi/devices/ahu/alarms/frost_alarm" in topics
        assert "site1/revpi/devices/ahu/current_temperature" in topics


class TestDoPublish:
    """Test the actual publish execution."""

    def test_do_publish_calls_client(self) -> None:
        """_do_publish should call client.publish for each message."""
        client = MagicMock()
        hass = MagicMock()
        coordinator = _make_mock_coordinator()
        config = _make_mqtt_config()
        publisher = MQTTPublisher(hass, client, config, coordinator, [])

        messages = [
            ("topic/a", "1"),
            ("topic/b", "2"),
        ]
        publisher._do_publish(messages)

        assert client.publish.call_count == 2
        client.publish.assert_any_call("topic/a", "1")
        client.publish.assert_any_call("topic/b", "2")


class TestDisconnected:
    """Test behavior when MQTT client is not connected."""

    def test_no_publish_when_disconnected(self) -> None:
        """No messages should be queued when client is disconnected."""
        hass = MagicMock()
        client = MagicMock()
        client.is_connected = False
        coordinator = _make_mock_coordinator(
            core_values={"cpu_temperature": 50.0}
        )
        config = _make_mqtt_config(publish_core=True, publish_interval=0)
        publisher = MQTTPublisher(hass, client, config, coordinator, [])

        publisher._on_update()
        assert hass.async_add_executor_job.call_count == 0
