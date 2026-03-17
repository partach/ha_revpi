"""Tests for the Revolution Pi coordinator."""

from __future__ import annotations

from typing import TYPE_CHECKING

from custom_components.ha_revpi.const import MODULE_TYPE_AIO, MODULE_TYPE_DIO, MODULE_TYPE_RELAY
from custom_components.ha_revpi.coordinator import RevPiCoordinator, _classify_module

if TYPE_CHECKING:
    from unittest.mock import MagicMock


class TestClassifyModule:
    """Tests for module classification."""

    def test_dio_module(self) -> None:
        assert _classify_module("RevPiDIO") == MODULE_TYPE_DIO

    def test_di_module(self) -> None:
        assert _classify_module("RevPiDI") == MODULE_TYPE_DIO

    def test_do_module(self) -> None:
        assert _classify_module("RevPiDO") == MODULE_TYPE_DIO

    def test_aio_module(self) -> None:
        assert _classify_module("RevPiAIO") == MODULE_TYPE_AIO

    def test_relay_module(self) -> None:
        assert _classify_module("RevPiRO") == MODULE_TYPE_RELAY

    def test_core_module(self) -> None:
        assert _classify_module("RevPiCore") == "core"

    def test_unknown_module(self) -> None:
        assert _classify_module("SomeOther") == "someother"


class TestCoordinatorDiscovery:
    """Tests for module discovery."""

    def test_discover_modules(self, mock_revpi_io: MagicMock) -> None:
        """Test that modules are discovered correctly."""
        coordinator = RevPiCoordinator.__new__(RevPiCoordinator)
        coordinator._revpi = mock_revpi_io
        coordinator._modules = {}
        coordinator._io_map = {}

        modules = coordinator.discover_modules()

        assert "dio01" in modules
        assert "aio01" in modules
        assert "ro01" in modules

        # DIO module should have inputs and outputs
        dio = modules["dio01"]
        assert dio.module_type == MODULE_TYPE_DIO
        assert len(dio.inputs) == 2
        assert len(dio.outputs) == 2

        # AIO module
        aio = modules["aio01"]
        assert aio.module_type == MODULE_TYPE_AIO
        assert len(aio.inputs) == 1
        assert len(aio.outputs) == 1

        # Relay module
        ro = modules["ro01"]
        assert ro.module_type == MODULE_TYPE_RELAY
        assert len(ro.inputs) == 0
        assert len(ro.outputs) == 1

    def test_discover_digital_io(self, mock_revpi_io: MagicMock) -> None:
        """Test that digital IOs are identified correctly."""
        coordinator = RevPiCoordinator.__new__(RevPiCoordinator)
        coordinator._revpi = mock_revpi_io
        coordinator._modules = {}
        coordinator._io_map = {}

        coordinator.discover_modules()

        i1 = coordinator.get_io_info("I_1")
        assert i1 is not None
        assert i1.is_digital is True
        assert i1.device_name == "dio01"

    def test_discover_analogue_io(self, mock_revpi_io: MagicMock) -> None:
        """Test that analogue IOs are identified correctly."""
        coordinator = RevPiCoordinator.__new__(RevPiCoordinator)
        coordinator._revpi = mock_revpi_io
        coordinator._modules = {}
        coordinator._io_map = {}

        coordinator.discover_modules()

        ai1 = coordinator.get_io_info("AI_1")
        assert ai1 is not None
        assert ai1.is_digital is False
        assert ai1.device_name == "aio01"

    def test_read_io_values(self, mock_revpi_io: MagicMock) -> None:
        """Test reading IO values from process image."""
        coordinator = RevPiCoordinator.__new__(RevPiCoordinator)
        coordinator._revpi = mock_revpi_io
        coordinator._modules = {}
        coordinator._io_map = {}

        coordinator.discover_modules()
        values = coordinator._read_all_io()

        assert values["I_1"] is True
        assert values["I_2"] is False
        assert values["AI_1"] == 1500
        assert values["AO_1"] == 2500
        mock_revpi_io.readprocimg.assert_called_once()

    def test_write_io(self, mock_revpi_io: MagicMock) -> None:
        """Test writing an IO value."""
        coordinator = RevPiCoordinator.__new__(RevPiCoordinator)
        coordinator._revpi = mock_revpi_io
        coordinator._modules = {}
        coordinator._io_map = {}

        coordinator.discover_modules()
        coordinator.write_io("O_1", True)

        mock_revpi_io.io["O_1"].__setattr__("value", True)
        mock_revpi_io.writeprocimg.assert_called_once()
