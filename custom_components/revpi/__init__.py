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
    CONF_CONFIGRSC,
    CONF_HOST,
    CONF_POLL_INTERVAL,
    CORE_DEVICE_SUFFIX,
    DEFAULT_CONFIGRSC,
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
    configrsc = entry.data.get(CONF_CONFIGRSC, DEFAULT_CONFIGRSC)

    # Create the RevPiModIO connection
    revpi = await _async_create_revpi(hass, host, configrsc)

    # Each config entry (hub) gets its own coordinator with its own poll loop
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

    # Store as hub dict — each entry_id is one hub with its own coordinator
    hass.data[DOMAIN][entry.entry_id] = {
        "coordinator": coordinator,
    }

    # Register core device (parent) and IO module devices (children)
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
        hub_data = hass.data[DOMAIN].pop(entry.entry_id)
        coordinator: RevPiCoordinator = hub_data["coordinator"]
        revpi = coordinator.revpi
        await hass.async_add_executor_job(_cleanup_revpi, revpi)

    return unload_ok


async def update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update — reload if structural settings changed."""
    _LOGGER.info("Options updated for %s, reloading", entry.title)
    await hass.config_entries.async_reload(entry.entry_id)


async def _async_create_revpi(hass: HomeAssistant, host: str, configrsc: str) -> Any:
    """Create and return a RevPiModIO2 instance."""

    def _create() -> Any:
        import revpimodio2

        if host in (DEFAULT_HOST, "localhost"):
            return revpimodio2.RevPiModIO(
                autorefresh=False,
                syncoutputs=True,
                configrsc=configrsc,
            )
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
    """Register core device (parent) and IO module devices (children via via_device)."""
    device_registry = dr.async_get(hass)
    core_info = coordinator.core_info
    core_identifier = (DOMAIN, f"{entry.entry_id}{CORE_DEVICE_SUFFIX}")

    # Register the core (CPU) module as the parent device
    if core_info is not None:
        device_registry.async_get_or_create(
            config_entry_id=entry.entry_id,
            identifiers={core_identifier},
            name=f"RevPi {core_info.name}",
            manufacturer="KUNBUS GmbH",
            model=core_info.catalog_nr or "RevPi Core",
            configuration_url=f"http://{entry.data.get(CONF_HOST, DEFAULT_HOST)}",
        )
    else:
        # Fallback: register a generic core device
        device_registry.async_get_or_create(
            config_entry_id=entry.entry_id,
            identifiers={core_identifier},
            name=entry.title or "Revolution Pi",
            manufacturer="KUNBUS GmbH",
            model="RevPi",
            configuration_url=f"http://{entry.data.get(CONF_HOST, DEFAULT_HOST)}",
        )

    # Register IO expansion modules as children linked via via_device
    for mod_name, mod_info in coordinator.get_io_modules().items():
        device_registry.async_get_or_create(
            config_entry_id=entry.entry_id,
            identifiers={(DOMAIN, f"{entry.entry_id}_{mod_name}")},
            name=f"RevPi {mod_name}",
            manufacturer="KUNBUS GmbH",
            model=mod_info.catalog_nr or "Unknown",
            via_device=core_identifier,
        )

    # Also register core module IO devices if the core has IOs (e.g., Connect relay)
    core_mod = coordinator.get_core_module()
    if core_mod and (core_mod.inputs or core_mod.outputs):
        _LOGGER.debug(
            "Core module %s has %d inputs and %d outputs",
            core_mod.name,
            len(core_mod.inputs),
            len(core_mod.outputs),
        )


def get_core_device_info(entry: ConfigEntry, coordinator: RevPiCoordinator) -> DeviceInfo:
    """Build DeviceInfo for the core (parent) device."""
    core_info = coordinator.core_info
    return DeviceInfo(
        identifiers={(DOMAIN, f"{entry.entry_id}{CORE_DEVICE_SUFFIX}")},
        name=f"RevPi {core_info.name}" if core_info else (entry.title or "Revolution Pi"),
        manufacturer="KUNBUS GmbH",
        model=(core_info.catalog_nr if core_info else "RevPi") or "RevPi",
        configuration_url=f"http://{entry.data.get(CONF_HOST, DEFAULT_HOST)}",
    )


def get_module_device_info(entry: ConfigEntry, mod_name: str, mod_info: Any) -> DeviceInfo:
    """Build DeviceInfo for an IO module (child device linked to core)."""
    return DeviceInfo(
        identifiers={(DOMAIN, f"{entry.entry_id}_{mod_name}")},
        name=f"RevPi {mod_name}",
        manufacturer="KUNBUS GmbH",
        model=mod_info.catalog_nr or "Unknown",
        via_device=(DOMAIN, f"{entry.entry_id}{CORE_DEVICE_SUFFIX}"),
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
        for hub_data in hass.data[DOMAIN].values():
            if not isinstance(hub_data, dict):
                continue
            coordinator = hub_data.get("coordinator")
            if coordinator is None or not isinstance(coordinator, RevPiCoordinator):
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
    from homeassistant.components.http import StaticPathConfig

    await hass.http.async_register_static_paths(
        [StaticPathConfig(
            "/local/community/revpi/revpi-ports-card.js",
            dst,
            cache_headers=False,
        )]
    )
