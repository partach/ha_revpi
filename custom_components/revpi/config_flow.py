"""Config flow for Revolution Pi integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.const import CONF_HOST
from homeassistant.core import callback

from .const import (
    CONF_CONNECTION_TYPE,
    CONF_POLL_INTERVAL,
    CONNECTION_TYPE_LOCAL,
    CONNECTION_TYPE_TCP,
    DEFAULT_HOST,
    DEFAULT_POLL_INTERVAL,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_CONNECTION_TYPE, default=CONNECTION_TYPE_LOCAL): vol.In(
            {
                CONNECTION_TYPE_LOCAL: "Local (same device)",
                CONNECTION_TYPE_TCP: "TCP/IP (remote RevPi)",
            }
        ),
        vol.Optional(CONF_POLL_INTERVAL, default=DEFAULT_POLL_INTERVAL): vol.All(
            vol.Coerce(int), vol.Range(min=1, max=60)
        ),
    }
)

STEP_TCP_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
    }
)


class RevPiConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Revolution Pi."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._connection_type: str = CONNECTION_TYPE_LOCAL
        self._poll_interval: int = DEFAULT_POLL_INTERVAL

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> RevPiOptionsFlowHandler:
        """Get the options flow handler."""
        return RevPiOptionsFlowHandler(config_entry)

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Handle the initial step — choose connection type."""
        errors: dict[str, str] = {}

        if user_input is not None:
            self._connection_type = user_input[CONF_CONNECTION_TYPE]
            self._poll_interval = user_input.get(CONF_POLL_INTERVAL, DEFAULT_POLL_INTERVAL)

            if self._connection_type == CONNECTION_TYPE_TCP:
                return await self.async_step_tcp()

            # Local connection
            host = DEFAULT_HOST
            await self.async_set_unique_id(host)
            self._abort_if_unique_id_configured()

            if await self._test_connection(host):
                return self.async_create_entry(
                    title="Revolution Pi (local)",
                    data={
                        CONF_HOST: host,
                        CONF_CONNECTION_TYPE: CONNECTION_TYPE_LOCAL,
                        CONF_POLL_INTERVAL: self._poll_interval,
                    },
                )
            errors["base"] = "cannot_connect"

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )

    async def async_step_tcp(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Handle the TCP connection step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            host = user_input[CONF_HOST]
            await self.async_set_unique_id(host)
            self._abort_if_unique_id_configured()

            if await self._test_connection(host):
                return self.async_create_entry(
                    title=f"Revolution Pi ({host})",
                    data={
                        CONF_HOST: host,
                        CONF_CONNECTION_TYPE: CONNECTION_TYPE_TCP,
                        CONF_POLL_INTERVAL: self._poll_interval,
                    },
                )
            errors["base"] = "cannot_connect"

        return self.async_show_form(
            step_id="tcp",
            data_schema=STEP_TCP_DATA_SCHEMA,
            errors=errors,
        )

    async def _test_connection(self, host: str) -> bool:
        """Test if we can connect to the Revolution Pi."""
        try:

            def _test() -> bool:
                import revpimodio2

                if host in (DEFAULT_HOST, "localhost"):
                    rpi = revpimodio2.RevPiModIO(autorefresh=False)
                else:
                    rpi = revpimodio2.RevPiNetIO(host, autorefresh=False)
                rpi.exit()
                return True

            return await self.hass.async_add_executor_job(_test)
        except Exception:
            _LOGGER.exception("Failed to connect to Revolution Pi at %s", host)
            return False


class RevPiOptionsFlowHandler(OptionsFlow):
    """Handle options flow for Revolution Pi."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_POLL_INTERVAL,
                        default=self.config_entry.data.get(
                            CONF_POLL_INTERVAL, DEFAULT_POLL_INTERVAL
                        ),
                    ): vol.All(vol.Coerce(int), vol.Range(min=1, max=60)),
                }
            ),
        )
