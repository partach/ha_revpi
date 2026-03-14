"""DataUpdateCoordinator for Revolution Pi."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import timedelta
from typing import TYPE_CHECKING, Any

from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    CATALOG_AIO_PREFIXES,
    CATALOG_CORE_PREFIXES,
    CATALOG_DIO_PREFIXES,
    CATALOG_RELAY_PREFIXES,
    DEFAULT_POLL_INTERVAL,
    DOMAIN,
    IO_TYPE_INP,
    IO_TYPE_OUT,
    MODULE_TYPE_AIO,
    MODULE_TYPE_CORE,
    MODULE_TYPE_DIO,
    MODULE_TYPE_RELAY,
)

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)


@dataclass
class RevPiIOInfo:
    """Describes a single IO point on a Revolution Pi module."""

    name: str
    device_name: str
    module_type: str
    io_type: int  # IO_TYPE_INP, IO_TYPE_OUT, IO_TYPE_MEM
    is_digital: bool
    address: int
    length: int
    value: Any = None
    signed: bool = False
    default_value: Any = None


@dataclass
class RevPiModuleInfo:
    """Describes a Revolution Pi module."""

    name: str
    position: int
    catalog_nr: str
    module_type: str
    is_core: bool = False
    inputs: list[RevPiIOInfo] = field(default_factory=list)
    outputs: list[RevPiIOInfo] = field(default_factory=list)


@dataclass
class RevPiCoreInfo:
    """Describes the Revolution Pi core (CPU) module."""

    name: str
    position: int
    catalog_nr: str
    module_type: str = MODULE_TYPE_CORE


@dataclass
class RevPiData:
    """Container for all Revolution Pi data."""

    modules: dict[str, RevPiModuleInfo] = field(default_factory=dict)
    io_values: dict[str, Any] = field(default_factory=dict)
    core_values: dict[str, Any] = field(default_factory=dict)


def _classify_module(catalog_nr: str) -> str:
    """Classify a module by its catalog number."""
    if catalog_nr.startswith(CATALOG_DIO_PREFIXES):
        return MODULE_TYPE_DIO
    if catalog_nr.startswith(CATALOG_AIO_PREFIXES):
        return MODULE_TYPE_AIO
    if catalog_nr.startswith(CATALOG_RELAY_PREFIXES):
        return MODULE_TYPE_RELAY
    if catalog_nr.startswith(CATALOG_CORE_PREFIXES):
        return MODULE_TYPE_CORE
    return catalog_nr.lower()


class RevPiCoordinator(DataUpdateCoordinator[RevPiData]):
    """Coordinator to manage polling Revolution Pi I/O data."""

    config_entry: ConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        revpi_module: Any,
        poll_interval: int = DEFAULT_POLL_INTERVAL,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{config_entry.entry_id}",
            update_interval=timedelta(seconds=poll_interval),
        )
        self.config_entry = config_entry
        self._revpi = revpi_module
        self._poll_interval = poll_interval
        self._modules: dict[str, RevPiModuleInfo] = {}
        self._io_map: dict[str, RevPiIOInfo] = {}
        self._core_info: RevPiCoreInfo | None = None

    @property
    def revpi(self) -> Any:
        """Return the revpimodio2 instance."""
        return self._revpi

    @property
    def core_info(self) -> RevPiCoreInfo | None:
        """Return the core module info."""
        return self._core_info

    def discover_modules(self) -> dict[str, RevPiModuleInfo]:
        """Discover all connected modules and their IOs (runs in executor)."""
        modules: dict[str, RevPiModuleInfo] = {}
        io_map: dict[str, RevPiIOInfo] = {}

        for dev in self._revpi.device:
            device = self._revpi.device[dev]
            catalog_nr = getattr(device, "catalogNr", "") or ""
            module_type = _classify_module(catalog_nr)

            is_core = module_type == MODULE_TYPE_CORE

            mod_info = RevPiModuleInfo(
                name=device.name,
                position=device.position,
                catalog_nr=catalog_nr,
                module_type=module_type,
                is_core=is_core,
            )

            if is_core:
                self._core_info = RevPiCoreInfo(
                    name=device.name,
                    position=device.position,
                    catalog_nr=catalog_nr,
                    module_type=module_type,
                )

            # Discover inputs
            for io_obj in device.get_inputs():
                is_digital = io_obj.length == 0  # bit-length = 0 means digital (1 bit)
                io_info = RevPiIOInfo(
                    name=io_obj.name,
                    device_name=device.name,
                    module_type=module_type,
                    io_type=IO_TYPE_INP,
                    is_digital=is_digital,
                    address=io_obj.address,
                    length=io_obj.length,
                    signed=getattr(io_obj, "signed", False),
                    default_value=getattr(io_obj, "defaultvalue", None),
                )
                mod_info.inputs.append(io_info)
                io_map[io_obj.name] = io_info

            # Discover outputs
            for io_obj in device.get_outputs():
                is_digital = io_obj.length == 0
                io_info = RevPiIOInfo(
                    name=io_obj.name,
                    device_name=device.name,
                    module_type=module_type,
                    io_type=IO_TYPE_OUT,
                    is_digital=is_digital,
                    address=io_obj.address,
                    length=io_obj.length,
                    signed=getattr(io_obj, "signed", False),
                    default_value=getattr(io_obj, "defaultvalue", None),
                )
                mod_info.outputs.append(io_info)
                io_map[io_obj.name] = io_info

            modules[device.name] = mod_info

        self._modules = modules
        self._io_map = io_map
        return modules

    async def async_discover_modules(self) -> dict[str, RevPiModuleInfo]:
        """Discover modules in the executor."""
        return await self.hass.async_add_executor_job(self.discover_modules)

    def _read_core_values(self) -> dict[str, Any]:
        """Read core module system values (runs in executor)."""
        values: dict[str, Any] = {}
        core = getattr(self._revpi, "core", None)
        if core is None:
            return values

        # CPU temperature
        try:
            values["cpu_temperature"] = core.temperature
        except Exception:
            _LOGGER.debug("Could not read CPU temperature")

        # CPU frequency
        try:
            values["cpu_frequency"] = core.frequency
        except Exception:
            _LOGGER.debug("Could not read CPU frequency")

        # IO cycle time
        try:
            values["io_cycle"] = core.iocycle
        except Exception:
            _LOGGER.debug("Could not read IO cycle time")

        # IO error count
        try:
            values["io_error_count"] = core.ioerrorcount
        except Exception:
            _LOGGER.debug("Could not read IO error count")

        # piControl driver status
        try:
            values["picontrol_running"] = core.picontrolrunning
        except Exception:
            _LOGGER.debug("Could not read piControl status")

        return values

    def _read_all_io(self) -> dict[str, Any]:
        """Read all IO values from the process image (runs in executor)."""
        self._revpi.readprocimg()
        values: dict[str, Any] = {}
        for io_name in self._io_map:
            try:
                values[io_name] = self._revpi.io[io_name].value
            except Exception:
                _LOGGER.debug("Failed to read IO %s", io_name)
                values[io_name] = None
        return values

    async def _async_update_data(self) -> RevPiData:
        """Fetch data from Revolution Pi."""
        try:
            io_values = await self.hass.async_add_executor_job(self._read_all_io)
            core_values = await self.hass.async_add_executor_job(self._read_core_values)
        except Exception as err:
            raise UpdateFailed(f"Error reading Revolution Pi process image: {err}") from err

        return RevPiData(
            modules=self._modules,
            io_values=io_values,
            core_values=core_values,
        )

    def write_io(self, io_name: str, value: Any) -> None:
        """Write a value to an IO point (runs in executor)."""
        self._revpi.io[io_name].value = value
        self._revpi.writeprocimg()

    async def async_write_io(self, io_name: str, value: Any) -> None:
        """Write a value to an IO point."""
        await self.hass.async_add_executor_job(self.write_io, io_name, value)
        await self.async_request_refresh()

    def get_io_info(self, io_name: str) -> RevPiIOInfo | None:
        """Get IO info by name."""
        return self._io_map.get(io_name)

    def get_modules(self) -> dict[str, RevPiModuleInfo]:
        """Return discovered modules."""
        return self._modules

    def get_io_modules(self) -> dict[str, RevPiModuleInfo]:
        """Return only non-core (IO expansion) modules."""
        return {k: v for k, v in self._modules.items() if not v.is_core}

    def get_core_module(self) -> RevPiModuleInfo | None:
        """Return the core module if discovered."""
        for mod in self._modules.values():
            if mod.is_core:
                return mod
        return None
