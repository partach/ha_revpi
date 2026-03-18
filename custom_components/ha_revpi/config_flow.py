"""Config flow for Revolution Pi integration."""

from __future__ import annotations

import logging
from typing import Any
from urllib.parse import urlparse

import voluptuous as vol
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_HOST
from homeassistant.core import callback

from .const import (
    CONF_BUILDING_DEVICES,
    CONF_CONFIGRSC,
    CONF_CONNECTION_TYPE,
    CONF_POLL_INTERVAL,
    CONNECTION_TYPE_LOCAL,
    CONNECTION_TYPE_TCP,
    DEFAULT_CONFIGRSC,
    DEFAULT_HOST,
    DEFAULT_POLL_INTERVAL,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


def _sanitize_host(host: str) -> str:
    """Strip scheme, port, and path from a host input."""
    host = host.strip().rstrip("/")
    if "://" in host:
        parsed = urlparse(host)
        host = parsed.hostname or host
    return host


STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(
            CONF_CONNECTION_TYPE, default=CONNECTION_TYPE_LOCAL
        ): vol.In(
            {
                CONNECTION_TYPE_LOCAL: "Local (same device)",
                CONNECTION_TYPE_TCP: "TCP/IP (remote RevPi)",
            }
        ),
        vol.Optional(CONF_CONFIGRSC, default=DEFAULT_CONFIGRSC): str,
        vol.Optional(
            CONF_POLL_INTERVAL, default=DEFAULT_POLL_INTERVAL
        ): vol.All(vol.Coerce(int), vol.Range(min=1, max=60)),
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
        self._configrsc: str = DEFAULT_CONFIGRSC

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> RevPiOptionsFlowHandler:
        """Get the options flow handler."""
        return RevPiOptionsFlowHandler()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step — choose connection type."""
        errors: dict[str, str] = {}

        if user_input is not None:
            self._connection_type = user_input[CONF_CONNECTION_TYPE]
            self._poll_interval = user_input.get(
                CONF_POLL_INTERVAL, DEFAULT_POLL_INTERVAL
            )
            self._configrsc = user_input.get(
                CONF_CONFIGRSC, DEFAULT_CONFIGRSC
            )

            if self._connection_type == CONNECTION_TYPE_TCP:
                return await self.async_step_tcp()

            host = DEFAULT_HOST
            await self.async_set_unique_id(host)
            self._abort_if_unique_id_configured()

            if await self._test_connection(host, self._configrsc):
                return self.async_create_entry(
                    title="Revolution Pi (local)",
                    data={
                        CONF_HOST: host,
                        CONF_CONNECTION_TYPE: CONNECTION_TYPE_LOCAL,
                        CONF_POLL_INTERVAL: self._poll_interval,
                        CONF_CONFIGRSC: self._configrsc,
                    },
                )
            errors["base"] = "cannot_connect"

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )

    async def async_step_tcp(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the TCP connection step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            host = _sanitize_host(user_input[CONF_HOST])
            await self.async_set_unique_id(host)
            self._abort_if_unique_id_configured()

            if await self._test_connection(host, self._configrsc):
                return self.async_create_entry(
                    title=f"Revolution Pi ({host})",
                    data={
                        CONF_HOST: host,
                        CONF_CONNECTION_TYPE: CONNECTION_TYPE_TCP,
                        CONF_POLL_INTERVAL: self._poll_interval,
                        CONF_CONFIGRSC: self._configrsc,
                    },
                )
            errors["base"] = "cannot_connect"

        return self.async_show_form(
            step_id="tcp",
            data_schema=STEP_TCP_DATA_SCHEMA,
            errors=errors,
        )

    async def _test_connection(self, host: str, configrsc: str) -> bool:
        """Test if we can connect to the Revolution Pi."""
        try:

            def _test() -> bool:
                import revpimodio2

                if host in (DEFAULT_HOST, "localhost"):
                    rpi = revpimodio2.RevPiModIO(
                        autorefresh=False,
                        configrsc=configrsc,
                    )
                else:
                    rpi = revpimodio2.RevPiNetIO(host, autorefresh=False)
                rpi.exit()
                return True

            return await self.hass.async_add_executor_job(_test)
        except Exception:
            _LOGGER.exception(
                "Failed to connect to Revolution Pi at %s", host
            )
            return False


# -----------------------------------------------------------------------
# Options Flow
# -----------------------------------------------------------------------

MENU_ADD_DEVICE = "add_building_device"
MENU_REMOVE_DEVICE = "remove_building_device"


class RevPiOptionsFlowHandler(OptionsFlow):
    """Handle options flow for Revolution Pi."""

    def __init__(self) -> None:
        """Initialize."""
        self._selected_template: dict[str, Any] | None = None

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Main options menu."""
        if user_input is not None:
            action = user_input.get("action")
            if action == MENU_ADD_DEVICE:
                return await self.async_step_add_building_device()
            if action == MENU_REMOVE_DEVICE:
                return await self.async_step_remove_building_device()

            # Save general settings (preserve building_devices)
            new_options = dict(self.config_entry.options)
            new_options[CONF_POLL_INTERVAL] = user_input.get(
                CONF_POLL_INTERVAL, DEFAULT_POLL_INTERVAL
            )
            new_options[CONF_CONFIGRSC] = user_input.get(
                CONF_CONFIGRSC, DEFAULT_CONFIGRSC
            )
            return self.async_create_entry(title="", data=new_options)

        current_poll = self.config_entry.options.get(
            CONF_POLL_INTERVAL,
            self.config_entry.data.get(
                CONF_POLL_INTERVAL, DEFAULT_POLL_INTERVAL
            ),
        )
        current_configrsc = self.config_entry.options.get(
            CONF_CONFIGRSC,
            self.config_entry.data.get(CONF_CONFIGRSC, DEFAULT_CONFIGRSC),
        )

        devices = self.config_entry.options.get(CONF_BUILDING_DEVICES, [])
        device_count = len(devices)

        actions = {
            MENU_ADD_DEVICE: f"Add building device ({device_count} configured)",
        }
        if device_count > 0:
            actions[MENU_REMOVE_DEVICE] = "Remove building device"

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_POLL_INTERVAL,
                        default=current_poll,
                    ): vol.All(
                        vol.Coerce(int), vol.Range(min=1, max=60)
                    ),
                    vol.Optional(
                        CONF_CONFIGRSC,
                        default=current_configrsc,
                    ): str,
                    vol.Optional("action"): vol.In(actions),
                }
            ),
        )

    async def async_step_add_building_device(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Select a template to add as a building device."""
        from .template_utils import (
            get_available_templates,
            get_template_dropdown,
            load_template,
        )

        if user_input is not None:
            template_id = user_input["template"]
            template = await load_template(self.hass, template_id)
            if template is None:
                return self.async_show_form(
                    step_id="add_building_device",
                    data_schema=vol.Schema(
                        {vol.Required("template"): str}
                    ),
                    errors={"base": "template_load_failed"},
                )
            self._selected_template = template
            self._selected_template["_template_id"] = template_id
            return await self.async_step_confirm_building_device()

        templates = await get_available_templates(self.hass)
        dropdown = get_template_dropdown(templates)

        if not dropdown:
            return self.async_abort(reason="no_templates")

        return self.async_show_form(
            step_id="add_building_device",
            data_schema=vol.Schema(
                {vol.Required("template"): vol.In(dropdown)}
            ),
        )

    async def async_step_confirm_building_device(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm and optionally remap IOs for the selected template."""
        template = self._selected_template
        if template is None:
            return await self.async_step_init()

        if user_input is not None:
            from .template_utils import validate_io_mapping

            device_name = user_input.get(
                "device_name", template["name"]
            )

            # Update io_name values from user input
            for key in template.get("ios", {}):
                input_key = f"io_{key}"
                if input_key in user_input:
                    template["ios"][key]["io_name"] = user_input[input_key]

            # Validate IO names exist in coordinator
            hub_data = self.hass.data.get(DOMAIN, {}).get(
                self.config_entry.entry_id, {}
            )
            coordinator = hub_data.get("coordinator")
            available_ios: set[str] = set()
            if coordinator and coordinator.data:
                available_ios = set(coordinator.data.io_values.keys())

            if available_ios:
                errors_list = validate_io_mapping(template, available_ios)
                if errors_list:
                    _LOGGER.warning(
                        "IO mapping validation: %s", errors_list
                    )
                    # Extract just the missing IO names for a clean message
                    missing_names = []
                    for key, io_conf in template.get("ios", {}).items():
                        io_name = io_conf.get("io_name", "")
                        if io_name not in available_ios:
                            missing_names.append(
                                f"**{io_name}** ({key})"
                            )
                    details = (
                        "Not found: " + ", ".join(missing_names)
                        if missing_names
                        else ""
                    )
                    return self.async_show_form(
                        step_id="confirm_building_device",
                        data_schema=self._build_confirm_schema(template),
                        errors={"base": "io_not_found"},
                        description_placeholders={"errors": details},
                    )

            # Build device config to persist
            device_config = {
                "template_id": template.get("_template_id", ""),
                "name": device_name,
                "type": template["type"],
                "manufacturer": template.get("manufacturer", ""),
                "model": template.get("model", ""),
                "ios": template["ios"],
            }
            if "control" in template:
                device_config["control"] = template["control"]

            # Append to existing building devices
            new_options = dict(self.config_entry.options)
            devices = list(
                new_options.get(CONF_BUILDING_DEVICES, [])
            )
            devices.append(device_config)
            new_options[CONF_BUILDING_DEVICES] = devices

            self._selected_template = None
            return self.async_create_entry(title="", data=new_options)

        return self.async_show_form(
            step_id="confirm_building_device",
            data_schema=self._build_confirm_schema(template),
            description_placeholders={"errors": ""},
        )

    def _build_confirm_schema(
        self, template: dict[str, Any]
    ) -> vol.Schema:
        """Build schema for confirming/remapping a template."""
        schema_dict: dict[Any, Any] = {
            vol.Optional(
                "device_name", default=template["name"]
            ): str,
        }

        for key, io_conf in template.get("ios", {}).items():
            label = io_conf.get("description") or key
            schema_dict[
                vol.Optional(
                    f"io_{key}",
                    default=io_conf.get("io_name", ""),
                    description={"suffix": f"({label})"},
                )
            ] = str

        return vol.Schema(schema_dict)

    async def async_step_remove_building_device(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Remove a building device."""
        devices = list(
            self.config_entry.options.get(CONF_BUILDING_DEVICES, [])
        )

        if user_input is not None:
            index = int(user_input["device_index"])
            if 0 <= index < len(devices):
                removed = devices.pop(index)
                _LOGGER.info(
                    "Removed building device: %s", removed.get("name")
                )
                new_options = dict(self.config_entry.options)
                new_options[CONF_BUILDING_DEVICES] = devices
                return self.async_create_entry(
                    title="", data=new_options
                )

        if not devices:
            return self.async_abort(reason="no_building_devices")

        choices = {
            str(i): dev.get("name", f"Device {i}")
            for i, dev in enumerate(devices)
        }

        return self.async_show_form(
            step_id="remove_building_device",
            data_schema=vol.Schema(
                {vol.Required("device_index"): vol.In(choices)}
            ),
        )
