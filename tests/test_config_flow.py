"""Tests for the Revolution Pi config flow."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResultType

from custom_components.revpi.const import CONF_HOST, CONF_POLL_INTERVAL, DOMAIN

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant


async def test_form_user_step(hass: HomeAssistant) -> None:
    """Test that the user step form is served."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}


async def test_form_connection_success(
    hass: HomeAssistant,
    mock_setup_revpi: MagicMock,
) -> None:
    """Test successful connection creates an entry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: "localhost",
            CONF_POLL_INTERVAL: 1,
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Revolution Pi (localhost)"
    assert result["data"] == {
        CONF_HOST: "localhost",
        CONF_POLL_INTERVAL: 1,
    }


async def test_form_connection_failure(hass: HomeAssistant) -> None:
    """Test connection failure shows error."""
    with patch(
        "custom_components.revpi.config_flow.RevPiConfigFlow._test_connection",
        return_value=False,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: "192.168.1.100",
                CONF_POLL_INTERVAL: 1,
            },
        )

        assert result["type"] is FlowResultType.FORM
        assert result["errors"] == {"base": "cannot_connect"}


async def test_form_already_configured(
    hass: HomeAssistant,
    mock_setup_revpi: MagicMock,
) -> None:
    """Test that duplicate hosts are rejected."""
    # First entry
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: "localhost", CONF_POLL_INTERVAL: 1},
    )

    # Second entry with same host
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: "localhost", CONF_POLL_INTERVAL: 1},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
