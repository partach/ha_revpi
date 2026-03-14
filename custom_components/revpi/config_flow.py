"""Config flow for Revolution Pi integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST

from .const import (
    CONF_POLL_INTERVAL,
    DEFAULT_HOST,
    DEFAULT_POLL_INTERVAL,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST, default=DEFAULT_HOST): str,
        vol.Optional(CONF_POLL_INTERVAL, default=DEFAULT_POLL_INTERVAL): vol.All(
            vol.Coerce(int), vol.Range(min=1, max=60)
        ),
    }
)


class RevPiConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Revolution Pi."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            host = user_input[CONF_HOST]

            # Prevent duplicate entries for the same host
            await self.async_set_unique_id(host)
            self._abort_if_unique_id_configured()

            # Test connection
            if await self._test_connection(host):
                return self.async_create_entry(
                    title=f"Revolution Pi ({host})",
                    data=user_input,
                )
            errors["base"] = "cannot_connect"

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )

    async def _test_connection(self, host: str) -> bool:
        """Test if we can connect to the Revolution Pi."""
        try:

            def _test() -> bool:
                import revpimodio2

                if host == DEFAULT_HOST or host == "localhost":
                    rpi = revpimodio2.RevPiModIO(autorefresh=False)
                else:
                    rpi = revpimodio2.RevPiNetIO(host, autorefresh=False)
                rpi.exit()
                return True

            return await self.hass.async_add_executor_job(_test)
        except Exception:
            _LOGGER.exception("Failed to connect to Revolution Pi at %s", host)
            return False
