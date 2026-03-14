"""Tests for the Revolution Pi integration."""

from __future__ import annotations

from typing import TYPE_CHECKING

from custom_components.revpi.const import CONF_HOST, CONF_POLL_INTERVAL, DOMAIN

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant


def create_config_entry(hass: HomeAssistant) -> object:
    """Create and add a mock config entry."""
    from homeassistant.config_entries import ConfigEntry

    entry = ConfigEntry(
        version=1,
        minor_version=1,
        domain=DOMAIN,
        title="Revolution Pi (localhost)",
        data={
            CONF_HOST: "localhost",
            CONF_POLL_INTERVAL: 1,
        },
        source="user",
        unique_id="localhost",
    )
    entry.add_to_hass(hass)
    return entry
