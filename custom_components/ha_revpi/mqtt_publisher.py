"""MQTT publisher — publishes RevPi values on change with rate limiting."""

from __future__ import annotations

import logging
import re
import time
from typing import TYPE_CHECKING, Any

from .const import (
    CONF_MQTT_MAIN_TOPIC,
    CONF_MQTT_PUBLISH_CORE,
    CONF_MQTT_PUBLISH_DEVICES,
    CONF_MQTT_PUBLISH_INTERVAL,
    DEFAULT_MQTT_MAIN_TOPIC,
    DEFAULT_MQTT_PUBLISH_INTERVAL,
)

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

    from .coordinator import RevPiCoordinator
    from .devices.base import BuildingDeviceHandler
    from .mqtt_client import MQTTClient

_LOGGER = logging.getLogger(__name__)

_SLUG_RE = re.compile(r"[^a-z0-9]+")


def _slugify(name: str) -> str:
    """Convert a name to a topic-safe slug."""
    return _SLUG_RE.sub("_", name.lower()).strip("_")


def _format_payload(value: Any) -> str:
    """Format a value as a scalar MQTT payload string."""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, float):
        return f"{value:.2f}" if abs(value) < 1e6 else str(value)
    return str(value)


class MQTTPublisher:
    """Watches coordinator updates and publishes changed values via MQTT."""

    def __init__(
        self,
        hass: HomeAssistant,
        client: MQTTClient,
        mqtt_config: dict[str, Any],
        coordinator: RevPiCoordinator,
        handlers: list[BuildingDeviceHandler],
    ) -> None:
        """Initialize the publisher."""
        self._hass = hass
        self._client = client
        self._coordinator = coordinator
        self._handlers = {h.name: h for h in handlers}
        self._main_topic = mqtt_config.get(
            CONF_MQTT_MAIN_TOPIC, DEFAULT_MQTT_MAIN_TOPIC
        )
        self._publish_interval: float = mqtt_config.get(
            CONF_MQTT_PUBLISH_INTERVAL, DEFAULT_MQTT_PUBLISH_INTERVAL
        )
        self._publish_core: bool = mqtt_config.get(CONF_MQTT_PUBLISH_CORE, False)
        self._publish_devices: list[str] = mqtt_config.get(
            CONF_MQTT_PUBLISH_DEVICES, []
        )
        self._last_values: dict[str, Any] = {}
        self._last_publish_time: dict[str, float] = {}
        self._unsub: Any = None

    async def async_start(self) -> None:
        """Connect the client and register as coordinator listener."""
        try:
            await self._client.async_connect(self._hass)
        except Exception:
            _LOGGER.exception("Failed to connect MQTT client")
            return
        self._unsub = self._coordinator.async_add_listener(self._on_update)
        _LOGGER.info(
            "MQTT publisher started (topic=%s, interval=%ss, core=%s, devices=%s)",
            self._main_topic,
            self._publish_interval,
            self._publish_core,
            self._publish_devices,
        )

    async def async_stop(self) -> None:
        """Unregister listener and disconnect."""
        if self._unsub:
            self._unsub()
            self._unsub = None
        try:
            await self._client.async_disconnect(self._hass)
        except Exception:
            _LOGGER.debug("Error disconnecting MQTT client", exc_info=True)
        _LOGGER.info("MQTT publisher stopped")

    def _on_update(self) -> None:
        """Called synchronously by the coordinator after each data refresh."""
        if not self._client.is_connected:
            return
        now = time.monotonic()
        to_publish: list[tuple[str, str]] = []

        if self._publish_core:
            to_publish.extend(self._collect_core(now))

        for device_name in self._publish_devices:
            handler = self._handlers.get(device_name)
            if handler is None:
                continue
            to_publish.extend(self._collect_device(handler, now))

        if to_publish:
            self._hass.async_add_executor_job(self._do_publish, to_publish)

    def _should_publish(self, topic: str, value: Any, now: float) -> bool:
        """Return True if the value changed and the rate limit has passed."""
        last_val = self._last_values.get(topic)
        if last_val == value and topic in self._last_publish_time:
            return False
        last_time = self._last_publish_time.get(topic, 0.0)
        if now - last_time < self._publish_interval:
            return False
        return True

    def _mark_published(self, topic: str, value: Any, now: float) -> None:
        """Record that a topic was published."""
        self._last_values[topic] = value
        self._last_publish_time[topic] = now

    def _collect_core(self, now: float) -> list[tuple[str, str]]:
        """Collect changed core diagnostic values."""
        data = self._coordinator.data
        if data is None:
            return []
        result: list[tuple[str, str]] = []
        for key, value in data.core_values.items():
            if value is None:
                continue
            topic = f"{self._main_topic}/revpi/core/{key}"
            if self._should_publish(topic, value, now):
                result.append((topic, _format_payload(value)))
                self._mark_published(topic, value, now)
        return result

    def _collect_device(
        self, handler: BuildingDeviceHandler, now: float
    ) -> list[tuple[str, str]]:
        """Collect changed values for a building device."""
        result: list[tuple[str, str]] = []
        slug = _slugify(handler.name)
        base = f"{self._main_topic}/revpi/devices/{slug}"

        # Publish all IO mappings by role
        for _key, mapping in handler.ios.items():
            value = handler.read_io_engineering(mapping)
            if value is None:
                continue
            # Use role-based sub-topics; alarm roles get an alarms/ prefix
            role = mapping.role
            if role.endswith("_alarm"):
                topic = f"{base}/alarms/{role}"
            else:
                topic = f"{base}/{role}"
            if self._should_publish(topic, value, now):
                result.append((topic, _format_payload(value)))
                self._mark_published(topic, value, now)

        # Publish PID output if controller exists
        pid = getattr(handler, "pid_controller", None)
        if pid is not None:
            pid_task = getattr(handler, "_pid_task", None)
            if pid_task is not None and not pid_task.done():
                value = round(pid.output, 1)
                topic = f"{base}/pid_output"
                if self._should_publish(topic, value, now):
                    result.append((topic, _format_payload(value)))
                    self._mark_published(topic, value, now)

        return result

    def _do_publish(self, messages: list[tuple[str, str]]) -> None:
        """Publish all collected messages (runs in executor)."""
        for topic, payload in messages:
            try:
                self._client.publish(topic, payload)
            except Exception:
                _LOGGER.debug("Failed to publish %s", topic, exc_info=True)
