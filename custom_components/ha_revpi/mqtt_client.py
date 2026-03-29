"""Standalone paho-mqtt client wrapper for Revolution Pi MQTT publishing."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)

# Reconnect backoff: 2, 4, 8, 16, 30, 30, 30, ... seconds
_INITIAL_BACKOFF = 2
_MAX_BACKOFF = 30


class MQTTClient:
    """Thin wrapper around paho-mqtt for async usage via HA executor.

    The paho-mqtt library is imported lazily inside executor-run methods
    to avoid blocking I/O in the event loop (reading dist-info metadata).

    Self-healing: if the initial connection fails or the connection drops,
    a background task retries with exponential backoff until connected.
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
        self._message_callback: Callable[[str, str], None] | None = None
        self._reconnect_task: asyncio.Task | None = None
        self._stopped = False

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
        _LOGGER.warning("MQTT disconnected from %s:%s", self._broker, self._port)

    def _on_message(
        self,
        client: Any,
        userdata: Any,
        msg: Any,
    ) -> None:
        """Handle incoming message (runs in paho thread)."""
        if self._message_callback is not None:
            try:
                payload = msg.payload.decode("utf-8")
                self._message_callback(msg.topic, payload)
            except Exception:
                _LOGGER.debug(
                    "Error handling MQTT message on %s", msg.topic, exc_info=True
                )

    @property
    def is_connected(self) -> bool:
        """Return True if currently connected."""
        return self._connected

    def set_message_callback(
        self, callback: Callable[[str, str], None]
    ) -> None:
        """Register callback for incoming messages."""
        self._message_callback = callback
        if self._client is not None:
            self._client.on_message = self._on_message

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
        if self._message_callback is not None:
            self._client.on_message = self._on_message
        self._client.reconnect_delay_set(min_delay=1, max_delay=60)

    def _connect(self) -> None:
        """Connect and start the network loop (blocking, runs in executor)."""
        self._ensure_client()
        self._client.connect(self._broker, self._port, keepalive=60)
        self._client.loop_start()

    def _try_connect(self) -> bool:
        """Attempt to connect. Returns True on success, False on failure."""
        try:
            self._ensure_client()
            self._client.connect(self._broker, self._port, keepalive=60)
            self._client.loop_start()
            return True
        except OSError as exc:
            _LOGGER.debug("MQTT connect attempt failed: %s", exc)
            return False

    def _disconnect(self) -> None:
        """Stop the network loop and disconnect (blocking, runs in executor)."""
        if self._client is None:
            return
        self._client.loop_stop()
        self._client.disconnect()
        self._connected = False

    async def async_connect(self, hass: HomeAssistant) -> None:
        """Connect in the executor, with background retry on failure."""
        self._stopped = False
        success = await hass.async_add_executor_job(self._try_connect)
        if not success:
            _LOGGER.warning(
                "MQTT initial connection to %s:%s failed, will retry in background",
                self._broker,
                self._port,
            )
            self._start_reconnect_loop(hass)

    def _start_reconnect_loop(self, hass: HomeAssistant) -> None:
        """Start a background reconnect task if not already running."""
        if self._reconnect_task is not None and not self._reconnect_task.done():
            return
        self._reconnect_task = hass.async_create_background_task(
            self._reconnect_loop(hass),
            "mqtt_reconnect",
        )

    async def _reconnect_loop(self, hass: HomeAssistant) -> None:
        """Retry connecting with exponential backoff."""
        backoff = _INITIAL_BACKOFF
        while not self._stopped:
            _LOGGER.info(
                "MQTT reconnecting to %s:%s in %ds",
                self._broker,
                self._port,
                backoff,
            )
            await asyncio.sleep(backoff)
            if self._stopped:
                break
            success = await hass.async_add_executor_job(self._try_connect)
            if success:
                _LOGGER.info("MQTT reconnect successful")
                return
            backoff = min(backoff * 2, _MAX_BACKOFF)

    async def async_disconnect(self, hass: HomeAssistant) -> None:
        """Disconnect and cancel any reconnect task."""
        self._stopped = True
        if self._reconnect_task is not None and not self._reconnect_task.done():
            self._reconnect_task.cancel()
            self._reconnect_task = None
        await hass.async_add_executor_job(self._disconnect)

    def publish(
        self, topic: str, payload: str, qos: int = 0, retain: bool = True
    ) -> None:
        """Publish a message (blocking, call from executor)."""
        self._client.publish(topic, payload, qos=qos, retain=retain)

    def subscribe(self, topic: str, qos: int = 0) -> None:
        """Subscribe to a topic (blocking, call from executor)."""
        self._client.subscribe(topic, qos=qos)
