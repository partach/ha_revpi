"""Config flow for Revolution Pi integration."""

from __future__ import annotations

import copy
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
from homeassistant.helpers import selector

from .const import (
    CONF_BUILDING_DEVICES,
    CONF_CONFIGRSC,
    CONF_CONNECTION_TYPE,
    CONF_MQTT,
    CONF_MQTT_BROKER,
    CONF_MQTT_ENABLED,
    CONF_MQTT_MAIN_TOPIC,
    CONF_MQTT_PASSWORD,
    CONF_MQTT_PORT,
    CONF_MQTT_PUBLISH_CORE,
    CONF_MQTT_PUBLISH_DEVICES,
    CONF_MQTT_PUBLISH_INTERVAL,
    CONF_MQTT_USERNAME,
    CONF_POLL_INTERVAL,
    CONNECTION_TYPE_LOCAL,
    CONNECTION_TYPE_TCP,
    DEFAULT_CONFIGRSC,
    DEFAULT_HOST,
    DEFAULT_MQTT_MAIN_TOPIC,
    DEFAULT_MQTT_PORT,
    DEFAULT_MQTT_PUBLISH_INTERVAL,
    DEFAULT_POLL_INTERVAL,
    DOMAIN,
    IO_TYPE_INP,
    IO_TYPE_OUT,
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
MENU_EDIT_DEVICE = "edit_building_device"
MENU_REMOVE_DEVICE = "remove_building_device"
MENU_MQTT = "configure_mqtt"


class RevPiOptionsFlowHandler(OptionsFlow):
    """Handle options flow for Revolution Pi."""

    def __init__(self) -> None:
        """Initialize."""
        self._selected_template: dict[str, Any] | None = None
        self._edit_device_index: int | None = None

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Main options menu."""
        if user_input is not None:
            action = user_input.get("action")
            if action == MENU_ADD_DEVICE:
                return await self.async_step_add_building_device()
            if action == MENU_EDIT_DEVICE:
                return await self.async_step_edit_building_device()
            if action == MENU_REMOVE_DEVICE:
                return await self.async_step_remove_building_device()
            if action == MENU_MQTT:
                return await self.async_step_mqtt()

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

        mqtt_conf = self.config_entry.options.get(CONF_MQTT, {})
        mqtt_status = "enabled" if mqtt_conf.get(CONF_MQTT_ENABLED) else "disabled"

        actions = {
            MENU_ADD_DEVICE: f"Add building device ({device_count} configured)",
        }
        if device_count > 0:
            actions[MENU_EDIT_DEVICE] = "Edit building device IO mapping"
            actions[MENU_REMOVE_DEVICE] = "Remove building device"
        actions[MENU_MQTT] = f"Configure MQTT publishing ({mqtt_status})"

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
            coordinator = self._get_coordinator()
            available_ios: set[str] = set()
            if coordinator and coordinator.data:
                available_ios = set(coordinator.data.io_values.keys())

            # Check for unselected IOs (empty string from placeholder)
            unmapped = [
                key
                for key, io_conf in template.get("ios", {}).items()
                if not io_conf.get("io_name", "").strip()
            ]
            if unmapped:
                details = "Not mapped: " + ", ".join(
                    f"**{k}**" for k in unmapped
                )
                return self.async_show_form(
                    step_id="confirm_building_device",
                    data_schema=self._build_confirm_schema(template),
                    errors={"base": "io_not_found"},
                    description_placeholders={"errors": details},
                )

            if available_ios:
                errors_list = validate_io_mapping(template, available_ios)
                if errors_list:
                    _LOGGER.warning(
                        "IO mapping validation: %s", errors_list
                    )
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

    def _get_coordinator(self) -> Any:
        """Get the RevPi coordinator from hass data."""
        hub_data = self.hass.data.get(DOMAIN, {}).get(
            self.config_entry.entry_id, {}
        )
        return hub_data.get("coordinator")

    def _get_compatible_ios(
        self, io_conf: dict[str, Any]
    ) -> dict[str, str]:
        """Get IOs compatible with a template IO slot as dropdown choices.

        Filters by direction (input/output) and data_type (bool/analog).
        Returns {io_name: "io_name (module - type)"} for vol.In().
        """
        coordinator = self._get_coordinator()
        if not coordinator:
            return {}

        all_ios = coordinator.get_all_io_info()
        if not all_ios:
            return {}

        # Map template fields to coordinator fields
        want_input = io_conf.get("direction") == "input"
        want_digital = io_conf.get("data_type") == "bool"

        choices: dict[str, str] = {}
        for name, info in sorted(all_ios.items()):
            # Filter by direction
            if want_input and info.io_type != IO_TYPE_INP:
                continue
            if not want_input and info.io_type != IO_TYPE_OUT:
                continue
            # Filter by signal type
            if want_digital and not info.is_digital:
                continue
            if not want_digital and info.is_digital:
                continue

            kind = "digital" if info.is_digital else "analog"
            direction = "input" if info.io_type == IO_TYPE_INP else "output"
            choices[name] = f"{name} ({info.device_name} - {kind} {direction})"

        return choices

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
            default_io = io_conf.get("io_name", "")
            compatible = self._get_compatible_ios(io_conf)

            if compatible:
                # Use the template default if it's in the list, otherwise
                # don't pre-select anything
                if default_io not in compatible:
                    default_io = ""
                schema_dict[
                    vol.Optional(
                        f"io_{key}",
                        default=default_io,
                        description={"suffix": f"({label})"},
                    )
                ] = vol.In({"": f"-- Select {label} --", **compatible})
            else:
                # Fallback to free text if no coordinator data available
                schema_dict[
                    vol.Optional(
                        f"io_{key}",
                        default=default_io,
                        description={"suffix": f"({label})"},
                    )
                ] = str

        return vol.Schema(schema_dict)

    async def async_step_edit_building_device(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Select a building device to edit."""
        devices = list(
            self.config_entry.options.get(CONF_BUILDING_DEVICES, [])
        )

        if user_input is not None:
            index = int(user_input["device_index"])
            if 0 <= index < len(devices):
                self._edit_device_index = index
                return await self.async_step_edit_building_device_ios()
            return await self.async_step_init()

        if not devices:
            return self.async_abort(reason="no_building_devices")

        choices = {
            str(i): dev.get("name", f"Device {i}")
            for i, dev in enumerate(devices)
        }

        return self.async_show_form(
            step_id="edit_building_device",
            data_schema=vol.Schema(
                {vol.Required("device_index"): vol.In(choices)}
            ),
        )

    async def async_step_edit_building_device_ios(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Edit IO mappings for an existing building device."""
        # Deep-copy so in-place mutations don't alter entry.options before
        # the new options are saved — otherwise HA may see old == new and
        # skip firing the update listener.
        devices = copy.deepcopy(
            self.config_entry.options.get(CONF_BUILDING_DEVICES, [])
        )
        index = self._edit_device_index
        if index is None or index >= len(devices):
            return await self.async_step_init()

        device = devices[index]

        if user_input is not None:
            from .template_utils import validate_io_mapping

            device_name = user_input.get("device_name", device["name"])

            # Update io_name values from user input
            for key in device.get("ios", {}):
                input_key = f"io_{key}"
                if input_key in user_input:
                    device["ios"][key]["io_name"] = user_input[input_key]

            # Validate: check for unmapped IOs
            unmapped = [
                key
                for key, io_conf in device.get("ios", {}).items()
                if not io_conf.get("io_name", "").strip()
            ]
            if unmapped:
                details = "Not mapped: " + ", ".join(
                    f"**{k}**" for k in unmapped
                )
                return self.async_show_form(
                    step_id="edit_building_device_ios",
                    data_schema=self._build_edit_schema(device),
                    errors={"base": "io_not_found"},
                    description_placeholders={"errors": details},
                )

            # Validate IO names exist in coordinator
            coordinator = self._get_coordinator()
            available_ios: set[str] = set()
            if coordinator and coordinator.data:
                available_ios = set(coordinator.data.io_values.keys())

            if available_ios:
                errors_list = validate_io_mapping(device, available_ios)
                if errors_list:
                    _LOGGER.warning(
                        "IO mapping validation: %s", errors_list
                    )
                    missing_names = []
                    for key, io_conf in device.get("ios", {}).items():
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
                        step_id="edit_building_device_ios",
                        data_schema=self._build_edit_schema(device),
                        errors={"base": "io_not_found"},
                        description_placeholders={"errors": details},
                    )

            # Save updated device
            device["name"] = device_name
            devices[index] = device
            new_options = dict(self.config_entry.options)
            new_options[CONF_BUILDING_DEVICES] = devices
            self._edit_device_index = None
            return self.async_create_entry(title="", data=new_options)

        return self.async_show_form(
            step_id="edit_building_device_ios",
            data_schema=self._build_edit_schema(device),
            description_placeholders={"errors": ""},
        )

    def _build_edit_schema(
        self, device: dict[str, Any]
    ) -> vol.Schema:
        """Build schema for editing an existing device's IO mappings.

        Same dropdown logic as _build_confirm_schema but for saved devices.
        """
        schema_dict: dict[Any, Any] = {
            vol.Optional(
                "device_name", default=device["name"]
            ): str,
        }

        for key, io_conf in device.get("ios", {}).items():
            label = io_conf.get("description") or key
            current_io = io_conf.get("io_name", "")
            compatible = self._get_compatible_ios(io_conf)

            if compatible:
                # Pre-select the currently mapped IO if it's compatible
                default_io = current_io if current_io in compatible else ""
                schema_dict[
                    vol.Optional(
                        f"io_{key}",
                        default=default_io,
                        description={"suffix": f"({label})"},
                    )
                ] = vol.In({"": f"-- Select {label} --", **compatible})
            else:
                schema_dict[
                    vol.Optional(
                        f"io_{key}",
                        default=current_io,
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

    async def _async_test_mqtt_connection(self, config: dict) -> None:
        """Test MQTT broker connection."""
        from .mqtt_client import MQTTClient

        client = MQTTClient(
            broker=config[CONF_MQTT_BROKER],
            port=config[CONF_MQTT_PORT],
            username=config.get(CONF_MQTT_USERNAME) or "",
            password=config.get(CONF_MQTT_PASSWORD) or "",
        )
        try:
            await client.async_connect(self.hass)
            if not client.is_connected:
                raise Exception("Could not connect to MQTT broker")
            _LOGGER.info(
                "MQTT connection test successful to %s:%s",
                config[CONF_MQTT_BROKER],
                config[CONF_MQTT_PORT],
            )
        except Exception as err:
            _LOGGER.error("MQTT connection test failed: %s", err)
            raise Exception(
                f"Cannot connect to MQTT broker at "
                f"{config[CONF_MQTT_BROKER]}:{config[CONF_MQTT_PORT]}. "
                "Check broker address, port, and credentials."
            ) from err
        finally:
            try:
                await client.async_disconnect(self.hass)
            except Exception:
                _LOGGER.debug("Error disconnecting MQTT test client")

    async def async_step_mqtt(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Configure MQTT publishing settings."""
        errors: dict[str, str] = {}
        mqtt_conf = dict(
            self.config_entry.options.get(CONF_MQTT, {})
        )

        if user_input is not None:
            mqtt_conf[CONF_MQTT_ENABLED] = user_input.get(
                CONF_MQTT_ENABLED, False
            )
            mqtt_conf[CONF_MQTT_BROKER] = user_input.get(
                CONF_MQTT_BROKER, ""
            )
            mqtt_conf[CONF_MQTT_PORT] = user_input.get(
                CONF_MQTT_PORT, DEFAULT_MQTT_PORT
            )
            mqtt_conf[CONF_MQTT_USERNAME] = user_input.get(
                CONF_MQTT_USERNAME, ""
            )
            mqtt_conf[CONF_MQTT_PASSWORD] = user_input.get(
                CONF_MQTT_PASSWORD, ""
            )
            mqtt_conf[CONF_MQTT_MAIN_TOPIC] = user_input.get(
                CONF_MQTT_MAIN_TOPIC, DEFAULT_MQTT_MAIN_TOPIC
            )
            mqtt_conf[CONF_MQTT_PUBLISH_INTERVAL] = user_input.get(
                CONF_MQTT_PUBLISH_INTERVAL, DEFAULT_MQTT_PUBLISH_INTERVAL
            )
            mqtt_conf[CONF_MQTT_PUBLISH_CORE] = user_input.get(
                CONF_MQTT_PUBLISH_CORE, False
            )
            mqtt_conf[CONF_MQTT_PUBLISH_DEVICES] = user_input.get(
                CONF_MQTT_PUBLISH_DEVICES, []
            )

            # Test connection if enabled
            if mqtt_conf[CONF_MQTT_ENABLED] and mqtt_conf[CONF_MQTT_BROKER]:
                try:
                    await self._async_test_mqtt_connection(mqtt_conf)
                except Exception:
                    errors["base"] = "cannot_connect"

            if not errors:
                new_options = dict(self.config_entry.options)
                new_options[CONF_MQTT] = mqtt_conf
                return self.async_create_entry(title="", data=new_options)

        # Build device name choices from configured building devices
        devices = self.config_entry.options.get(CONF_BUILDING_DEVICES, [])
        device_names = [
            dev.get("name", f"Device {i}")
            for i, dev in enumerate(devices)
        ]

        cur_enabled = mqtt_conf.get(CONF_MQTT_ENABLED, False)
        cur_broker = mqtt_conf.get(CONF_MQTT_BROKER, "")
        cur_port = mqtt_conf.get(CONF_MQTT_PORT, DEFAULT_MQTT_PORT)
        cur_username = mqtt_conf.get(CONF_MQTT_USERNAME, "")
        cur_password = mqtt_conf.get(CONF_MQTT_PASSWORD, "")
        cur_main_topic = mqtt_conf.get(
            CONF_MQTT_MAIN_TOPIC, DEFAULT_MQTT_MAIN_TOPIC
        )
        cur_interval = mqtt_conf.get(
            CONF_MQTT_PUBLISH_INTERVAL, DEFAULT_MQTT_PUBLISH_INTERVAL
        )
        cur_publish_core = mqtt_conf.get(CONF_MQTT_PUBLISH_CORE, False)
        cur_publish_devices = mqtt_conf.get(CONF_MQTT_PUBLISH_DEVICES, [])

        schema_dict: dict[Any, Any] = {
            vol.Optional(
                CONF_MQTT_ENABLED, default=cur_enabled
            ): bool,
            vol.Optional(
                CONF_MQTT_BROKER, default=cur_broker
            ): str,
            vol.Optional(
                CONF_MQTT_PORT, default=cur_port
            ): vol.All(vol.Coerce(int), vol.Range(min=1, max=65535)),
            vol.Optional(
                CONF_MQTT_USERNAME, default=cur_username
            ): str,
            vol.Optional(
                CONF_MQTT_PASSWORD, default=cur_password
            ): selector.TextSelector(
                selector.TextSelectorConfig(
                    type=selector.TextSelectorType.PASSWORD
                )
            ),
            vol.Optional(
                CONF_MQTT_MAIN_TOPIC, default=cur_main_topic
            ): str,
            vol.Optional(
                CONF_MQTT_PUBLISH_INTERVAL, default=cur_interval
            ): vol.All(vol.Coerce(int), vol.Range(min=1, max=60)),
            vol.Optional(
                CONF_MQTT_PUBLISH_CORE, default=cur_publish_core
            ): bool,
        }

        if device_names:
            device_options = [
                selector.SelectOptionDict(value=name, label=name)
                for name in device_names
            ]
            schema_dict[
                vol.Optional(
                    CONF_MQTT_PUBLISH_DEVICES,
                    default=cur_publish_devices,
                )
            ] = selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=device_options,
                    multiple=True,
                    mode=selector.SelectSelectorMode.DROPDOWN,
                )
            )

        return self.async_show_form(
            step_id="mqtt",
            data_schema=vol.Schema(schema_dict),
            errors=errors,
        )
