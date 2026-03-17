"""DataUpdateCoordinator for Revolution Pi."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import timedelta
from typing import TYPE_CHECKING, Any

from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    AIO_NAME_KEYWORDS,
    CATALOG_AIO_PREFIXES,
    CATALOG_CORE_PREFIXES,
    CATALOG_DIO_PREFIXES,
    CATALOG_MIO_PREFIXES,
    CATALOG_RELAY_PREFIXES,
    CORE_NAME_KEYWORDS,
    DEFAULT_POLL_INTERVAL,
    DIO_NAME_KEYWORDS,
    DOMAIN,
    IO_TYPE_INP,
    IO_TYPE_OUT,
    MIO_NAME_KEYWORDS,
    MODULE_TYPE_AIO,
    MODULE_TYPE_CORE,
    MODULE_TYPE_DIO,
    MODULE_TYPE_MIO,
    MODULE_TYPE_RELAY,
    RELAY_NAME_KEYWORDS,
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
    export: bool = False
    comment: str = ""


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


def _is_digital_io(io_obj: Any) -> bool:
    """Determine whether an IO point is digital (boolean).

    revpimodio2 uses ``length == 0`` for individual bit IOs, but the first
    bit at a byte boundary may report ``length == 1`` (the containing byte).
    We also check the current value type: revpimodio2 returns ``bool`` for
    bit-type IOs even when they span a full byte in the process image.
    """
    if io_obj.length == 0:
        return True
    if isinstance(io_obj.value, bool):
        return True
    return False


def _is_reserved_io(io_obj: Any) -> bool:
    """Check if an IO is marked as reserved (e.g. unused pins on MIO modules)."""
    name = getattr(io_obj, "name", "") or ""
    return "reserved" in name.lower()


def _make_io_info(
    io_obj: Any, device_name: str, module_type: str, io_type: int
) -> RevPiIOInfo:
    """Create a RevPiIOInfo from a revpimodio2 IO object."""
    is_digital = _is_digital_io(io_obj)
    export = getattr(io_obj, "export", False)
    comment = getattr(io_obj, "bmk", "") or ""
    _LOGGER.debug(
        "IO %s: length=%s, value=%r (%s), is_digital=%s, export=%s, comment=%s",
        io_obj.name, io_obj.length, io_obj.value,
        type(io_obj.value).__name__, is_digital, export, comment,
    )
    return RevPiIOInfo(
        name=io_obj.name,
        device_name=device_name,
        module_type=module_type,
        io_type=io_type,
        is_digital=is_digital,
        address=io_obj.address,
        length=io_obj.length,
        signed=getattr(io_obj, "signed", False),
        default_value=getattr(io_obj, "defaultvalue", None),
        export=export,
        comment=comment,
    )


def _classify_module(catalog_nr: str, device_name: str = "") -> str:
    """Classify a module by its catalog number, falling back to device name.

    On real hardware, catalogNr is often a product code (e.g. 'PR100xxx')
    that doesn't match the expected prefixes. We fall back to checking
    the piCtory device name (e.g. 'RevPi Connect 5').
    """
    # First try catalog number (works in tests and some firmware versions)
    if catalog_nr.startswith(CATALOG_DIO_PREFIXES):
        return MODULE_TYPE_DIO
    if catalog_nr.startswith(CATALOG_MIO_PREFIXES):
        return MODULE_TYPE_MIO
    if catalog_nr.startswith(CATALOG_AIO_PREFIXES):
        return MODULE_TYPE_AIO
    if catalog_nr.startswith(CATALOG_RELAY_PREFIXES):
        return MODULE_TYPE_RELAY
    if catalog_nr.startswith(CATALOG_CORE_PREFIXES):
        return MODULE_TYPE_CORE

    # Fallback: check device name (handles spaces, e.g. "RevPi Connect 5")
    name_lower = device_name.lower()
    # Check core BEFORE DIO/AIO to avoid "RevPi Connect" matching " co" etc.
    if any(kw in name_lower for kw in CORE_NAME_KEYWORDS):
        return MODULE_TYPE_CORE
    # Check MIO before AIO (MIO contains "io" but is its own type)
    if any(kw in name_lower for kw in MIO_NAME_KEYWORDS):
        return MODULE_TYPE_MIO
    if any(kw in name_lower for kw in DIO_NAME_KEYWORDS):
        return MODULE_TYPE_DIO
    if any(kw in name_lower for kw in AIO_NAME_KEYWORDS):
        return MODULE_TYPE_AIO
    if any(kw in name_lower for kw in RELAY_NAME_KEYWORDS):
        return MODULE_TYPE_RELAY

    _LOGGER.warning(
        "Unknown module type: catalog_nr=%s, name=%s", catalog_nr, device_name
    )
    return catalog_nr.lower() if catalog_nr else device_name.lower()


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
            device = dev
            catalog_nr = getattr(device, "catalogNr", "") or ""
            module_type = _classify_module(catalog_nr, device.name)
            _LOGGER.info(
                "Module %s (pos=%s, catalog=%s) classified as %s",
                device.name, device.position, catalog_nr, module_type,
            )

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

            # Discover inputs — only piCtory-exported IOs
            for io_obj in device.get_inputs(export=True):
                if _is_reserved_io(io_obj):
                    continue
                io_info = _make_io_info(io_obj, device.name, module_type, IO_TYPE_INP)
                mod_info.inputs.append(io_info)
                io_map[io_obj.name] = io_info

            # Discover outputs — only piCtory-exported IOs
            for io_obj in device.get_outputs(export=True):
                if _is_reserved_io(io_obj):
                    continue
                io_info = _make_io_info(io_obj, device.name, module_type, IO_TYPE_OUT)
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
        _LOGGER.debug(
            "Writing IO %s = %r (type=%s)", io_name, value, type(value).__name__
        )
        self._revpi.io[io_name].value = value
        self._revpi.writeprocimg()
        # Read back to verify the write took effect
        readback = self._revpi.io[io_name].value
        _LOGGER.debug("IO %s readback after write: %r", io_name, readback)

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
