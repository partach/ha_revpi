"""Revolution Pi integration for Home Assistant."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.helpers import device_registry as dr

from .const import CONF_HOST, CONF_POLL_INTERVAL, DEFAULT_HOST, DEFAULT_POLL_INTERVAL, DOMAIN
from .coordinator import RevPiCoordinator

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.SWITCH, Platform.NUMBER]

type RevPiConfigEntry = ConfigEntry[RevPiCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: RevPiConfigEntry) -> bool:
    """Set up Revolution Pi from a config entry."""
    host = entry.data.get(CONF_HOST, DEFAULT_HOST)
    poll_interval = entry.data.get(CONF_POLL_INTERVAL, DEFAULT_POLL_INTERVAL)

    revpi = await _async_create_revpi(hass, host)

    coordinator = RevPiCoordinator(
        hass,
        config_entry=entry,
        revpi_module=revpi,
        poll_interval=poll_interval,
    )

    # Discover all modules and IOs
    modules = await coordinator.async_discover_modules()
    _LOGGER.info("Discovered %d Revolution Pi modules", len(modules))

    # Initial data fetch
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator

    # Register devices for each module
    _register_devices(hass, entry, coordinator)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: RevPiConfigEntry) -> bool:
    """Unload a Revolution Pi config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        coordinator: RevPiCoordinator = entry.runtime_data
        revpi = coordinator.revpi
        await hass.async_add_executor_job(_cleanup_revpi, revpi)

    return unload_ok


async def _async_create_revpi(hass: HomeAssistant, host: str) -> Any:
    """Create and return a RevPiModIO2 instance."""

    def _create() -> Any:
        import revpimodio2

        if host == DEFAULT_HOST or host == "localhost":
            return revpimodio2.RevPiModIO(autorefresh=False, syncoutputs=True)
        return revpimodio2.RevPiNetIO(host, autorefresh=False, syncoutputs=True)

    return await hass.async_add_executor_job(_create)


def _cleanup_revpi(revpi: Any) -> None:
    """Clean up RevPiModIO instance."""
    try:
        revpi.exit()
    except Exception:
        _LOGGER.debug("Error closing RevPiModIO connection", exc_info=True)


def _register_devices(
    hass: HomeAssistant,
    entry: ConfigEntry,
    coordinator: RevPiCoordinator,
) -> None:
    """Register a HA device for each RevPi module."""
    device_registry = dr.async_get(hass)
    modules = coordinator.get_modules()

    for mod_name, mod_info in modules.items():
        device_registry.async_get_or_create(
            config_entry_id=entry.entry_id,
            identifiers={(DOMAIN, f"{entry.entry_id}_{mod_name}")},
            name=f"RevPi {mod_name}",
            manufacturer="KUNBUS GmbH",
            model=mod_info.catalog_nr or "Unknown",
            sw_version=None,
        )
