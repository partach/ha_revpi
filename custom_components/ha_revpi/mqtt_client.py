"""Standalone paho-mqtt client wrapper for Revolution Pi MQTT publishing."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)


class MQTTClient:
    """Thin wrapper around paho-mqtt for async usage via HA executor.

    The paho-mqtt library is imported lazily inside executor-run methods
    to avoid blocking I/O in the event loop (reading dist-info metadata).
    """

    def __init__(
        self,
        broker: str,
        port: int = 1883,
        username: str = "",
        password: str = "",
        client_id: str = "",
    ) -> None:
        """Initialize the MQTT client (no paho import here)."""
        self._broker = broker
        self._port = port
        self._username = username
        self._password = password
        self._client_id = client_id
        self._client: Any = None
        self._connected = False

    def _on_connect(
        self,
        client: Any,
        userdata: Any,
        flags: Any,
        rc: Any,
        properties: Any = None,
    ) -> None:
        """Handle connection callback."""
        if hasattr(rc, "value"):
            rc_val = rc.value
        else:
            rc_val = rc
        if rc_val == 0:
            self._connected = True
            _LOGGER.info("MQTT connected to %s:%s", self._broker, self._port)
        else:
            self._connected = False
            _LOGGER.warning("MQTT connection failed: rc=%s", rc_val)

    def _on_disconnect(
        self,
        client: Any,
        userdata: Any,
        flags: Any = None,
        rc: Any = None,
        properties: Any = None,
    ) -> None:
        """Handle disconnection callback."""
        self._connected = False
        _LOGGER.info("MQTT disconnected from %s:%s", self._broker, self._port)

    @property
    def is_connected(self) -> bool:
        """Return True if currently connected."""
        return self._connected

    def _ensure_client(self) -> None:
        """Create the paho client if not yet created (runs in executor)."""
        if self._client is not None:
            return
        import paho.mqtt.client as mqtt

        self._client = mqtt.Client(
            callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
            client_id=self._client_id or None,
        )
        if self._username:
            self._client.username_pw_set(
                self._username, self._password or None
            )
        self._client.on_connect = self._on_connect
        self._client.on_disconnect = self._on_disconnect
        self._client.reconnect_delay_set(min_delay=1, max_delay=60)

    def _connect(self) -> None:
        """Connect and start the network loop (blocking, runs in executor)."""
        self._ensure_client()
        self._client.connect(self._broker, self._port, keepalive=60)
        self._client.loop_start()

    def _disconnect(self) -> None:
        """Stop the network loop and disconnect (blocking, runs in executor)."""
        if self._client is None:
            return
        self._client.loop_stop()
        self._client.disconnect()
        self._connected = False

    async def async_connect(self, hass: HomeAssistant) -> None:
        """Connect in the executor."""
        await hass.async_add_executor_job(self._connect)

    async def async_disconnect(self, hass: HomeAssistant) -> None:
        """Disconnect in the executor."""
        await hass.async_add_executor_job(self._disconnect)

    def publish(
        self, topic: str, payload: str, qos: int = 0, retain: bool = True
    ) -> None:
        """Publish a message (blocking, call from executor)."""
        self._client.publish(topic, payload, qos=qos, retain=retain)
