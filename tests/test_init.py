"""Tests for the Revolution Pi integration setup."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

from homeassistant.config_entries import ConfigEntryState

from . import create_config_entry

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant


async def test_setup_entry(
    hass: HomeAssistant,
    mock_revpi_io: MagicMock,
    mock_setup_revpi: MagicMock,
) -> None:
    """Test successful setup of a config entry."""
    entry = create_config_entry(hass)

    with patch(
        "custom_components.revpi._async_create_revpi",
        return_value=mock_revpi_io,
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED


async def test_unload_entry(
    hass: HomeAssistant,
    mock_revpi_io: MagicMock,
    mock_setup_revpi: MagicMock,
) -> None:
    """Test unloading a config entry."""
    entry = create_config_entry(hass)

    with patch(
        "custom_components.revpi._async_create_revpi",
        return_value=mock_revpi_io,
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        result = await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()

    assert result is True
    assert entry.state is ConfigEntryState.NOT_LOADED
