"""Revolution Pi integration for Home Assistant."""

from __future__ import annotations

import logging
import os
import shutil
from typing import TYPE_CHECKING, Any

from homeassistant.const import Platform
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.entity import DeviceInfo

from .const import (
    CONF_HOST,
    CONF_POLL_INTERVAL,
    DEFAULT_HOST,
    DEFAULT_POLL_INTERVAL,
    DOMAIN,
)
from .coordinator import RevPiCoordinator

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant, ServiceCall

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.SWITCH, Platform.NUMBER, Platform.SELECT]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Revolution Pi from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    host = entry.data.get(CONF_HOST, DEFAULT_HOST)
    poll_interval = entry.data.get(CONF_POLL_INTERVAL, DEFAULT_POLL_INTERVAL)

    # Create the RevPiModIO connection
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

    # Store coordinator in hass.data (same pattern as ha_felicity)
    hass.data[DOMAIN][entry.entry_id] = coordinator

    # Register devices for each discovered module
    _register_devices(hass, entry, coordinator)

    # Forward setup to platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Register services
    _register_services(hass)

    # Copy frontend resources
    await _async_setup_frontend(hass)

    # Listen for option changes
    entry.async_on_unload(entry.add_update_listener(update_listener))

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a Revolution Pi config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        coordinator: RevPiCoordinator = hass.data[DOMAIN].pop(entry.entry_id)
        revpi = coordinator.revpi
        await hass.async_add_executor_job(_cleanup_revpi, revpi)

    return unload_ok


async def update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update — reload if structural settings changed."""
    _LOGGER.info("Options updated for %s, reloading", entry.title)
    await hass.config_entries.async_reload(entry.entry_id)


async def _async_create_revpi(hass: HomeAssistant, host: str) -> Any:
    """Create and return a RevPiModIO2 instance."""

    def _create() -> Any:
        import revpimodio2

        if host in (DEFAULT_HOST, "localhost"):
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
            configuration_url=f"homeassistant://config/integrations/integration/{entry.entry_id}",
        )


def get_device_info(entry: ConfigEntry, mod_name: str, mod_info: Any) -> DeviceInfo:
    """Build a DeviceInfo dict for an entity belonging to a RevPi module."""
    return DeviceInfo(
        identifiers={(DOMAIN, f"{entry.entry_id}_{mod_name}")},
        name=f"RevPi {mod_name}",
        manufacturer="KUNBUS GmbH",
        model=mod_info.catalog_nr or "Unknown",
        configuration_url=f"homeassistant://config/integrations/integration/{entry.entry_id}",
    )


def _register_services(hass: HomeAssistant) -> None:
    """Register integration services (idempotent)."""
    if hass.services.has_service(DOMAIN, "write_io"):
        return

    async def handle_write_io(call: ServiceCall) -> None:
        """Handle the write_io service call."""
        io_name = call.data["io_name"]
        value = call.data["value"]

        # Find the coordinator that owns this IO
        for coordinator in hass.data[DOMAIN].values():
            if not isinstance(coordinator, RevPiCoordinator):
                continue
            io_info = coordinator.get_io_info(io_name)
            if io_info is not None:
                await coordinator.async_write_io(io_name, value)
                return

        _LOGGER.warning("IO '%s' not found in any configured Revolution Pi", io_name)

    hass.services.async_register(DOMAIN, "write_io", handle_write_io)


async def _async_setup_frontend(hass: HomeAssistant) -> None:
    """Copy frontend card JS to www directory for Lovelace."""
    src = os.path.join(os.path.dirname(__file__), "frontend", "revpi-ports-card.js")
    dst_dir = hass.config.path("www", "community", "revpi")
    dst = os.path.join(dst_dir, "revpi-ports-card.js")

    def _copy() -> None:
        os.makedirs(dst_dir, exist_ok=True)
        shutil.copy2(src, dst)

    if not os.path.exists(dst) or os.path.getmtime(src) > os.path.getmtime(dst):
        await hass.async_add_executor_job(_copy)

    # Register as a Lovelace resource
    hass.http.register_static_path(
        "/local/community/revpi/revpi-ports-card.js",
        dst,
        cache_headers=False,
    )
