"""Fixtures for Revolution Pi integration tests."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock, patch

import pytest

from custom_components.ha_revpi.const import CONF_HOST, CONF_POLL_INTERVAL

if TYPE_CHECKING:
    from collections.abc import Generator


@pytest.fixture
def mock_revpi_io() -> MagicMock:
    """Create a mock RevPiModIO instance with DIO, AIO, and Relay modules."""
    revpi = MagicMock()

    # Create mock digital IO
    di_1 = _make_io("I_1", address=0, length=0, io_type=300, value=True)
    di_2 = _make_io("I_2", address=0, length=0, io_type=300, value=False)
    do_1 = _make_io("O_1", address=1, length=0, io_type=301, value=False)
    do_2 = _make_io("O_2", address=1, length=0, io_type=301, value=True)

    # Create mock analogue IO
    ai_1 = _make_io("AI_1", address=10, length=2, io_type=300, value=1500)
    ao_1 = _make_io("AO_1", address=12, length=2, io_type=301, value=2500)

    # Create mock relay IO
    relay_1 = _make_io("Relay_1", address=20, length=0, io_type=301, value=False)

    # DIO module
    dio_device = MagicMock()
    dio_device.name = "dio01"
    dio_device.position = 32
    dio_device.catalogNr = "RevPiDIO"
    dio_device.get_inputs.return_value = [di_1, di_2]
    dio_device.get_outputs.return_value = [do_1, do_2]

    # AIO module
    aio_device = MagicMock()
    aio_device.name = "aio01"
    aio_device.position = 33
    aio_device.catalogNr = "RevPiAIO"
    aio_device.get_inputs.return_value = [ai_1]
    aio_device.get_outputs.return_value = [ao_1]

    # Relay module
    ro_device = MagicMock()
    ro_device.name = "ro01"
    ro_device.position = 34
    ro_device.catalogNr = "RevPiRO"
    ro_device.get_inputs.return_value = []
    ro_device.get_outputs.return_value = [relay_1]

    # MIO module — 4 physical digital IOs plus reserved IOs that should be filtered
    mio_di_1 = _make_io("InputValue_1", address=30, length=0, io_type=300, value=True)
    mio_di_2 = _make_io("InputValue_2", address=30, length=0, io_type=300, value=False)
    mio_do_1 = _make_io("OutputValue_1", address=31, length=0, io_type=301, value=False)
    mio_do_2 = _make_io("OutputValue_2", address=31, length=0, io_type=301, value=True)
    mio_reserved_1 = _make_io(
        "InputValue_1_reserved", address=32, length=0, io_type=300, value=False,
    )
    mio_reserved_2 = _make_io(
        "OutputValue_1_reserved", address=33, length=0, io_type=301, value=False,
    )
    mio_ai_1 = _make_io("InputValue_3", address=34, length=2, io_type=300, value=500)

    mio_device = MagicMock()
    mio_device.name = "mio01"
    mio_device.position = 35
    mio_device.catalogNr = "RevPiMIO"
    mio_device.get_inputs.return_value = [mio_di_1, mio_di_2, mio_reserved_1, mio_ai_1]
    mio_device.get_outputs.return_value = [mio_do_1, mio_do_2, mio_reserved_2]

    # Device iteration — revpimodio2 iterates device objects directly
    devs = [dio_device, aio_device, ro_device, mio_device]
    revpi.device.__iter__ = MagicMock(return_value=iter(devs))
    dev_map = {
        "dio01": dio_device,
        "aio01": aio_device,
        "ro01": ro_device,
        "mio01": mio_device,
    }
    revpi.device.__getitem__ = MagicMock(
        side_effect=lambda k: dev_map[k]
    )

    # IO access
    io_map = {
        "I_1": di_1,
        "I_2": di_2,
        "O_1": do_1,
        "O_2": do_2,
        "AI_1": ai_1,
        "AO_1": ao_1,
        "Relay_1": relay_1,
        "InputValue_1": mio_di_1,
        "InputValue_2": mio_di_2,
        "OutputValue_1": mio_do_1,
        "OutputValue_2": mio_do_2,
        "InputValue_1_reserved": mio_reserved_1,
        "OutputValue_1_reserved": mio_reserved_2,
        "InputValue_3": mio_ai_1,
    }
    revpi.io.__getitem__ = MagicMock(side_effect=lambda k: io_map[k])

    revpi.readprocimg.return_value = True
    revpi.writeprocimg.return_value = True
    revpi.exit.return_value = None

    return revpi


@pytest.fixture
def mock_config_entry() -> dict[str, Any]:
    """Return mock config entry data."""
    return {
        CONF_HOST: "localhost",
        CONF_POLL_INTERVAL: 1,
    }


@pytest.fixture
def mock_setup_revpi(mock_revpi_io: MagicMock) -> Generator[MagicMock]:
    """Mock the RevPiModIO2 import and instantiation."""
    mock_module = MagicMock()
    mock_module.RevPiModIO.return_value = mock_revpi_io
    mock_module.RevPiNetIO.return_value = mock_revpi_io

    with patch.dict("sys.modules", {"revpimodio2": mock_module}):
        yield mock_module


def _make_io(
    name: str,
    address: int,
    length: int,
    io_type: int,
    value: Any,
    signed: bool = False,
    export: bool = True,
    bmk: str = "",
) -> MagicMock:
    """Create a mock IO object."""
    io_obj = MagicMock()
    io_obj.name = name
    io_obj.address = address
    io_obj.length = length
    io_obj.type = io_type
    io_obj.value = value
    io_obj.signed = signed
    io_obj.defaultvalue = 0
    io_obj.export = export
    io_obj.bmk = bmk
    return io_obj
