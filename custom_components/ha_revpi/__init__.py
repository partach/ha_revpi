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
    CONF_BUILDING_DEVICES,
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
from .devices import create_handler

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant, ServiceCall

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [
    Platform.SENSOR,
    Platform.SWITCH,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.CLIMATE,
    Platform.FAN,
    Platform.COVER,
]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Revolution Pi from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    host = entry.data.get(CONF_HOST, DEFAULT_HOST)
    poll_interval = entry.options.get(
        CONF_POLL_INTERVAL,
        entry.data.get(CONF_POLL_INTERVAL, DEFAULT_POLL_INTERVAL),
    )
    configrsc = entry.options.get(
        CONF_CONFIGRSC,
        entry.data.get(CONF_CONFIGRSC, DEFAULT_CONFIGRSC),
    )

    # Create the ModIO connection
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

    # Create building device handlers from persisted config
    _setup_building_devices(hass, entry, coordinator)

    # Forward setup to all platforms (including building device platforms)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Register services
    _register_services(hass)

    # Install and register frontend resources
    await _async_install_frontend_resource(hass)
    await _async_register_card(hass)

    # Start PID controllers for building devices
    await _start_pid_controllers(hass, entry)

    # Listen for option changes
    entry.async_on_unload(entry.add_update_listener(update_listener))

    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: ConfigEntry
) -> bool:
    """Unload a Revolution Pi config entry."""
    # Stop PID controllers
    hub_data = hass.data[DOMAIN].get(entry.entry_id, {})
    pid_tasks = hub_data.get("pid_tasks", [])
    for task in pid_tasks:
        task.cancel()

    unload_ok = await hass.config_entries.async_unload_platforms(
        entry, PLATFORMS
    )

    if unload_ok:
        hub_data = hass.data[DOMAIN].pop(entry.entry_id)
        coordinator: RevPiCoordinator = hub_data["coordinator"]
        revpi = coordinator.revpi
        await hass.async_add_executor_job(_cleanup_revpi, revpi)

    return unload_ok


async def update_listener(
    hass: HomeAssistant, entry: ConfigEntry
) -> None:
    """Handle options update — reload if structural settings changed."""
    _LOGGER.info("Options updated for %s, reloading", entry.title)
    await hass.config_entries.async_reload(entry.entry_id)


def _setup_building_devices(
    hass: HomeAssistant,
    entry: ConfigEntry,
    coordinator: RevPiCoordinator,
) -> None:
    """Create building device handlers from persisted options."""
    building_configs = entry.options.get(CONF_BUILDING_DEVICES, [])
    if not building_configs:
        hass.data[DOMAIN][entry.entry_id]["building_handlers"] = []
        return

    device_registry = dr.async_get(hass)
    core_identifier = (DOMAIN, f"{entry.entry_id}{CORE_DEVICE_SUFFIX}")
    handlers = []

    for dev_config in building_configs:
        handler = create_handler(dev_config, coordinator, entry.entry_id)
        if handler is None:
            _LOGGER.warning(
                "Failed to create handler for building device: %s",
                dev_config.get("name", "unknown"),
            )
            continue

        handlers.append(handler)

        # Register in HA device registry as child of core
        device_registry.async_get_or_create(
            config_entry_id=entry.entry_id,
            identifiers={(DOMAIN, handler.device_id)},
            name=handler.name,
            manufacturer=handler.manufacturer or "Custom",
            model=handler.model or handler.device_type.upper(),
            via_device=core_identifier,
        )
        _LOGGER.info(
            "Created building device handler: %s (%s)",
            handler.name,
            handler.device_type,
        )

    hass.data[DOMAIN][entry.entry_id]["building_handlers"] = handlers


async def _start_pid_controllers(
    hass: HomeAssistant, entry: ConfigEntry
) -> None:
    """Start PID controller async tasks for building devices that have them."""
    from .devices.pid import start_pid_task

    hub_data = hass.data[DOMAIN][entry.entry_id]
    handlers = hub_data.get("building_handlers", [])
    pid_tasks = []

    for handler in handlers:
        control = handler.config.get("control", {})
        if control.get("enabled"):
            task = start_pid_task(hass, handler)
            if task:
                pid_tasks.append(task)
                _LOGGER.info(
                    "Started PID controller for %s", handler.name
                )

    hub_data["pid_tasks"] = pid_tasks


async def _async_create_revpi(
    hass: HomeAssistant, host: str, configrsc: str
) -> Any:
    """Create and return a RevPiModIO2 instance."""

    def _create() -> Any:
        import revpimodio2

        if host in (DEFAULT_HOST, "localhost"):
            rpi = revpimodio2.RevPiModIO(
                autorefresh=False,
                syncoutputs=True,
                configrsc=configrsc,
            )
        else:
            rpi = revpimodio2.RevPiNetIO(
                host, autorefresh=False, syncoutputs=True
            )

        for dev in rpi.device:
            for io_obj in dev.get_outputs(export=True):
                _LOGGER.info(
                    "Startup sync — output %s = %r (length=%s)",
                    io_obj.name,
                    io_obj.value,
                    io_obj.length,
                )
        return rpi

    return await hass.async_add_executor_job(_create)


def _cleanup_revpi(revpi: Any) -> None:
    """Clean up RevPiModIO instance."""
    try:
        revpi.exit()
    except Exception:
        _LOGGER.debug(
            "Error closing RevPiModIO connection", exc_info=True
        )


def _register_devices(
    hass: HomeAssistant,
    entry: ConfigEntry,
    coordinator: RevPiCoordinator,
) -> None:
    """Register core device (parent) and IO module devices (children)."""
    device_registry = dr.async_get(hass)
    core_info = coordinator.core_info
    core_identifier = (DOMAIN, f"{entry.entry_id}{CORE_DEVICE_SUFFIX}")

    if core_info is not None:
        device_registry.async_get_or_create(
            config_entry_id=entry.entry_id,
            identifiers={core_identifier},
            name=core_info.name,
            manufacturer="KUNBUS GmbH",
            model=core_info.catalog_nr or "RevPi Core",
            hw_version="CORE",
            configuration_url=(
                f"http://{entry.data.get(CONF_HOST, DEFAULT_HOST)}"
            ),
        )
    else:
        device_registry.async_get_or_create(
            config_entry_id=entry.entry_id,
            identifiers={core_identifier},
            name=entry.title or "Revolution Pi",
            manufacturer="KUNBUS GmbH",
            model="RevPi",
            hw_version="CORE",
            configuration_url=(
                f"http://{entry.data.get(CONF_HOST, DEFAULT_HOST)}"
            ),
        )

    for mod_name, mod_info in coordinator.get_io_modules().items():
        device_registry.async_get_or_create(
            config_entry_id=entry.entry_id,
            identifiers={(DOMAIN, f"{entry.entry_id}_{mod_name}")},
            name=mod_name,
            manufacturer="KUNBUS GmbH",
            model=mod_info.catalog_nr or "Unknown",
            hw_version=mod_info.module_type.upper(),
            via_device=core_identifier,
        )

    core_mod = coordinator.get_core_module()
    if core_mod and (core_mod.inputs or core_mod.outputs):
        _LOGGER.debug(
            "Core module %s has %d inputs and %d outputs",
            core_mod.name,
            len(core_mod.inputs),
            len(core_mod.outputs),
        )


def get_core_device_info(
    entry: ConfigEntry, coordinator: RevPiCoordinator
) -> DeviceInfo:
    """Build DeviceInfo for the core (parent) device."""
    core_info = coordinator.core_info
    return DeviceInfo(
        identifiers={
            (DOMAIN, f"{entry.entry_id}{CORE_DEVICE_SUFFIX}")
        },
        name=(
            core_info.name
            if core_info
            else (entry.title or "Revolution Pi")
        ),
        manufacturer="KUNBUS GmbH",
        model=(
            (core_info.catalog_nr if core_info else "RevPi") or "RevPi"
        ),
        configuration_url=(
            f"http://{entry.data.get(CONF_HOST, DEFAULT_HOST)}"
        ),
    )


def get_module_device_info(
    entry: ConfigEntry, mod_name: str, mod_info: Any
) -> DeviceInfo:
    """Build DeviceInfo for an IO module (child device)."""
    return DeviceInfo(
        identifiers={(DOMAIN, f"{entry.entry_id}_{mod_name}")},
        name=mod_name,
        manufacturer="KUNBUS GmbH",
        model=mod_info.catalog_nr or "Unknown",
        via_device=(
            DOMAIN,
            f"{entry.entry_id}{CORE_DEVICE_SUFFIX}",
        ),
    )


def _register_services(hass: HomeAssistant) -> None:
    """Register integration services (idempotent)."""
    if hass.services.has_service(DOMAIN, "write_io"):
        return

    async def handle_write_io(call: ServiceCall) -> None:
        """Handle the write_io service call."""
        io_name = call.data["io_name"]
        value = call.data["value"]

        for hub_data in hass.data[DOMAIN].values():
            if not isinstance(hub_data, dict):
                continue
            coordinator = hub_data.get("coordinator")
            if coordinator is None or not isinstance(
                coordinator, RevPiCoordinator
            ):
                continue
            io_info = coordinator.get_io_info(io_name)
            if io_info is not None:
                await coordinator.async_write_io(io_name, value)
                return

        _LOGGER.warning(
            "IO '%s' not found in any configured Revolution Pi", io_name
        )

    hass.services.async_register(DOMAIN, "write_io", handle_write_io)


async def _async_install_frontend_resource(
    hass: HomeAssistant,
) -> None:
    """Ensure the frontend JS file is copied to the www/community folder."""

    def _install() -> None:
        target_dir = hass.config.path("www", "community", DOMAIN)
        try:
            if not os.path.exists(target_dir):
                os.makedirs(target_dir, exist_ok=True)
            js_file = "revpi-ports-card.js"
            source_path = os.path.join(
                os.path.dirname(__file__), "frontend", js_file
            )
            target_path = os.path.join(target_dir, js_file)
            if os.path.exists(source_path):
                shutil.copy2(source_path, target_path)
                _LOGGER.info(
                    "Updated frontend resource: %s", target_path
                )
            else:
                _LOGGER.warning(
                    "Frontend source file missing at %s", source_path
                )
        except Exception as err:
            _LOGGER.error(
                "Failed to install frontend resource: %s", err
            )

    await hass.async_add_executor_job(_install)


async def _async_register_card(hass: HomeAssistant) -> None:
    """Register the custom card as a Lovelace resource."""
    lovelace_data = hass.data.get("lovelace")
    if not lovelace_data:
        return

    resources = lovelace_data.resources
    if not resources:
        return

    if not resources.loaded:
        await resources.async_load()

    card_url = f"/hacsfiles/{DOMAIN}/revpi-ports-card.js"
    already_registered = any(
        item["url"] == card_url for item in resources.async_items()
    )
    if already_registered:
        return

    await resources.async_create_item(
        {
            "res_type": "module",
            "url": card_url,
        }
    )
    _LOGGER.debug("Card registered: %s", card_url)
