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

    # Device iteration — revpimodio2 iterates device objects directly
    revpi.device.__iter__ = MagicMock(return_value=iter([dio_device, aio_device, ro_device]))
    revpi.device.__getitem__ = MagicMock(
        side_effect=lambda k: {"dio01": dio_device, "aio01": aio_device, "ro01": ro_device}[k]
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
    return io_obj
