"""Binary sensor platform for Revolution Pi integration."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.helpers.entity import DeviceInfo, EntityCategory
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CORE_DEVICE_SUFFIX, DOMAIN
from .coordinator import RevPiCoordinator

if TYPE_CHECKING:
    from datetime import datetime

    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from .mqtt_publisher import MQTTPublisher

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Revolution Pi binary sensors."""
    hub_data = hass.data[DOMAIN][entry.entry_id]
    coordinator: RevPiCoordinator = hub_data["coordinator"]
    publisher: MQTTPublisher | None = hub_data.get("mqtt_publisher")

    entities: list[BinarySensorEntity | SensorEntity] = []

    if publisher is not None:
        core_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{entry.entry_id}{CORE_DEVICE_SUFFIX}")},
        )
        entities.append(
            RevPiMQTTStatusSensor(
                coordinator, entry, publisher, core_device_info
            )
        )
        entities.append(
            RevPiMQTTMessageCountSensor(
                coordinator, entry, publisher, core_device_info
            )
        )
        entities.append(
            RevPiMQTTLastPublishSensor(
                coordinator, entry, publisher, core_device_info
            )
        )

    async_add_entities(entities)


class RevPiMQTTStatusSensor(
    CoordinatorEntity[RevPiCoordinator], BinarySensorEntity
):
    """Binary sensor showing MQTT broker connection status."""

    _attr_has_entity_name = True
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = "mdi:mqtt"

    def __init__(
        self,
        coordinator: RevPiCoordinator,
        entry: ConfigEntry,
        publisher: MQTTPublisher,
        device_info: DeviceInfo,
    ) -> None:
        """Initialize."""
        super().__init__(coordinator)
        self._publisher = publisher
        self._attr_unique_id = f"{entry.entry_id}_mqtt_status"
        self._attr_name = "MQTT Status"
        self._attr_device_info = device_info

    @property
    def is_on(self) -> bool:
        """Return True if MQTT is connected."""
        return self._publisher.client.is_connected


class RevPiMQTTMessageCountSensor(
    CoordinatorEntity[RevPiCoordinator], SensorEntity
):
    """Sensor showing total MQTT messages published."""

    _attr_has_entity_name = True
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = "mdi:counter"

    def __init__(
        self,
        coordinator: RevPiCoordinator,
        entry: ConfigEntry,
        publisher: MQTTPublisher,
        device_info: DeviceInfo,
    ) -> None:
        """Initialize."""
        super().__init__(coordinator)
        self._publisher = publisher
        self._attr_unique_id = f"{entry.entry_id}_mqtt_message_count"
        self._attr_name = "MQTT Messages Published"
        self._attr_device_info = device_info

    @property
    def native_value(self) -> int:
        """Return the message count."""
        return self._publisher.message_count


class RevPiMQTTLastPublishSensor(
    CoordinatorEntity[RevPiCoordinator], SensorEntity
):
    """Sensor showing timestamp of last MQTT publish."""

    _attr_has_entity_name = True
    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = "mdi:clock-outline"

    def __init__(
        self,
        coordinator: RevPiCoordinator,
        entry: ConfigEntry,
        publisher: MQTTPublisher,
        device_info: DeviceInfo,
    ) -> None:
        """Initialize."""
        super().__init__(coordinator)
        self._publisher = publisher
        self._attr_unique_id = f"{entry.entry_id}_mqtt_last_publish"
        self._attr_name = "MQTT Last Publish"
        self._attr_device_info = device_info

    @property
    def native_value(self) -> datetime | None:
        """Return the last publish timestamp."""
        return self._publisher.last_publish_time
