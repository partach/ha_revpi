"""Binary sensor platform for Revolution Pi integration."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.helpers.entity import DeviceInfo, EntityCategory
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CORE_DEVICE_SUFFIX, DOMAIN
from .coordinator import RevPiCoordinator

if TYPE_CHECKING:
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

    entities: list[BinarySensorEntity] = []

    if publisher is not None:
        core_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{entry.entry_id}{CORE_DEVICE_SUFFIX}")},
        )
        entities.append(
            RevPiMQTTStatusSensor(
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
