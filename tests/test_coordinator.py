"""Tests for the Revolution Pi coordinator."""

from __future__ import annotations

from typing import TYPE_CHECKING

from custom_components.ha_revpi.const import MODULE_TYPE_AIO, MODULE_TYPE_CORE, MODULE_TYPE_DIO, MODULE_TYPE_MIO, MODULE_TYPE_RELAY
from custom_components.ha_revpi.coordinator import RevPiCoordinator, _classify_module, _is_reserved_io

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

    # Device name fallback tests (real hardware uses product codes as catalogNr)
    def test_core_by_device_name_connect(self) -> None:
        assert _classify_module("PR100xxx", "RevPi Connect 5") == MODULE_TYPE_CORE

    def test_core_by_device_name_core(self) -> None:
        assert _classify_module("PR100yyy", "RevPi Core S") == MODULE_TYPE_CORE

    def test_core_by_device_name_flat(self) -> None:
        assert _classify_module("PR100zzz", "RevPi Flat") == MODULE_TYPE_CORE

    def test_dio_by_device_name(self) -> None:
        assert _classify_module("PR200xxx", "RevPi DIO") == MODULE_TYPE_DIO

    def test_aio_by_device_name(self) -> None:
        assert _classify_module("PR200yyy", "RevPi AIO") == MODULE_TYPE_AIO

    def test_relay_by_device_name(self) -> None:
        assert _classify_module("PR200zzz", "RevPi RO") == MODULE_TYPE_RELAY

    def test_mio_module(self) -> None:
        assert _classify_module("RevPiMIO") == MODULE_TYPE_MIO


class TestReservedIO:
    """Tests for reserved IO filtering."""

    def test_reserved_io_detected(self) -> None:
        from unittest.mock import MagicMock

        io_obj = MagicMock()
        io_obj.name = "InputValue_1_reserved"
        assert _is_reserved_io(io_obj) is True

    def test_reserved_io_case_insensitive(self) -> None:
        from unittest.mock import MagicMock

        io_obj = MagicMock()
        io_obj.name = "OutputValue_Reserved_3"
        assert _is_reserved_io(io_obj) is True

    def test_normal_io_not_reserved(self) -> None:
        from unittest.mock import MagicMock

        io_obj = MagicMock()
        io_obj.name = "InputValue_1"
        assert _is_reserved_io(io_obj) is False


class TestCoordinatorDiscovery:
    """Tests for module discovery."""

    def test_discover_modules(self, mock_revpi_io: MagicMock) -> None:
        """Test that modules are discovered correctly."""
        coordinator = RevPiCoordinator.__new__(RevPiCoordinator)
        coordinator._revpi = mock_revpi_io
        coordinator._modules = {}
        coordinator._io_map = {}
        coordinator._core_info = None

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

    def test_discover_mio_filters_reserved(self, mock_revpi_io: MagicMock) -> None:
        """Test that reserved IOs are filtered out during MIO discovery."""
        coordinator = RevPiCoordinator.__new__(RevPiCoordinator)
        coordinator._revpi = mock_revpi_io
        coordinator._modules = {}
        coordinator._io_map = {}
        coordinator._core_info = None

        modules = coordinator.discover_modules()

        mio = modules["mio01"]
        assert mio.module_type == MODULE_TYPE_MIO
        # 2 digital inputs + 1 analogue input (reserved filtered out)
        assert len(mio.inputs) == 3
        # 2 digital outputs (reserved filtered out)
        assert len(mio.outputs) == 2
        # Reserved IOs should not be in the io_map
        assert coordinator.get_io_info("InputValue_1_reserved") is None
        assert coordinator.get_io_info("OutputValue_1_reserved") is None
        # Normal IOs should be present
        assert coordinator.get_io_info("InputValue_1") is not None
        assert coordinator.get_io_info("OutputValue_1") is not None

    def test_discover_digital_io(self, mock_revpi_io: MagicMock) -> None:
        """Test that digital IOs are identified correctly."""
        coordinator = RevPiCoordinator.__new__(RevPiCoordinator)
        coordinator._revpi = mock_revpi_io
        coordinator._modules = {}
        coordinator._io_map = {}
        coordinator._core_info = None

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
        coordinator._core_info = None

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
        coordinator._core_info = None

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
        coordinator._core_info = None

        coordinator.discover_modules()
        coordinator.write_io("O_1", True)

        mock_revpi_io.io["O_1"].__setattr__("value", True)
        mock_revpi_io.writeprocimg.assert_called_once()
