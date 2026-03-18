"""Template utilities for building device JSON templates."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)

BUILTIN_TEMPLATES_DIR = "templates"
USER_TEMPLATES_DIR = "ha_revpi/templates"

REQUIRED_TOP_LEVEL = {"schema_version", "name", "type", "ios"}
REQUIRED_IO_FIELDS = {"io_name", "role", "direction", "data_type"}
VALID_DEVICE_TYPES = {"ahu", "fan", "valve", "damper", "pump"}
VALID_DIRECTIONS = {"input", "output"}
VALID_DATA_TYPES = {"bool", "analog"}
VALID_TRANSFORM_TYPES = {"linear", "inverse_linear", "scale_offset"}


async def get_available_templates(
    hass: HomeAssistant,
) -> dict[str, dict[str, Any]]:
    """Get all available templates (built-in + user).

    Returns dict mapping template_id to info:
    {
        "builtin:ahu_basic": {
            "filename": "ahu_basic.json",
            "display_name": "Ahu Basic (Built-in)",
            "source": "builtin",
            "path": "/path/to/file",
        },
    }
    """
    templates: dict[str, dict[str, Any]] = {}

    builtin_dir = Path(__file__).parent / BUILTIN_TEMPLATES_DIR
    templates.update(
        await _list_templates_in_dir(hass, builtin_dir, "builtin")
    )

    user_dir = Path(hass.config.path(USER_TEMPLATES_DIR))
    templates.update(
        await _list_templates_in_dir(hass, user_dir, "user")
    )

    return templates


async def _list_templates_in_dir(
    hass: HomeAssistant,
    directory: Path,
    source: str,
) -> dict[str, dict[str, Any]]:
    """List JSON templates in a directory."""
    templates: dict[str, dict[str, Any]] = {}

    def _scan() -> list[tuple[str, Path]]:
        if not directory.exists():
            return []
        return [
            (f.stem, f)
            for f in directory.glob("*.json")
            if f.is_file()
        ]

    try:
        found = await hass.async_add_executor_job(_scan)
    except Exception as err:
        _LOGGER.warning("Failed to scan templates in %s: %s", directory, err)
        return templates

    for name, path in found:
        template_id = f"{source}:{name}"
        label = name.replace("_", " ").title()
        suffix = "Built-in" if source == "builtin" else "User"
        templates[template_id] = {
            "filename": f"{name}.json",
            "display_name": f"{label} ({suffix})",
            "source": source,
            "path": str(path),
        }

    return templates


async def load_template(
    hass: HomeAssistant,
    template_id: str,
) -> dict[str, Any] | None:
    """Load and validate a template by ID.

    Returns the parsed template dict, or None on failure.
    """
    templates = await get_available_templates(hass)
    info = templates.get(template_id)
    if not info:
        _LOGGER.error("Template not found: %s", template_id)
        return None

    template_path = info["path"]

    def _read() -> dict[str, Any]:
        with open(template_path, encoding="utf-8") as f:
            return json.load(f)

    try:
        data = await hass.async_add_executor_job(_read)
    except (FileNotFoundError, json.JSONDecodeError, OSError) as err:
        _LOGGER.error("Failed to load template %s: %s", template_id, err)
        return None

    errors = validate_template(data)
    if errors:
        _LOGGER.error(
            "Template %s validation failed: %s",
            template_id,
            "; ".join(errors),
        )
        return None

    return data


def validate_template(data: dict[str, Any]) -> list[str]:
    """Validate a template dict. Returns list of error strings (empty = valid)."""
    errors: list[str] = []

    missing = REQUIRED_TOP_LEVEL - set(data.keys())
    if missing:
        errors.append(f"Missing required fields: {missing}")
        return errors

    if data["type"] not in VALID_DEVICE_TYPES:
        errors.append(
            f"Unknown device type '{data['type']}', "
            f"must be one of {VALID_DEVICE_TYPES}"
        )

    ios = data.get("ios", {})
    if not isinstance(ios, dict) or not ios:
        errors.append("'ios' must be a non-empty dict")
        return errors

    for key, io_config in ios.items():
        prefix = f"ios.{key}"
        io_missing = REQUIRED_IO_FIELDS - set(io_config.keys())
        if io_missing:
            errors.append(f"{prefix}: missing fields {io_missing}")
            continue

        if io_config["direction"] not in VALID_DIRECTIONS:
            errors.append(f"{prefix}: invalid direction '{io_config['direction']}'")

        if io_config["data_type"] not in VALID_DATA_TYPES:
            errors.append(f"{prefix}: invalid data_type '{io_config['data_type']}'")

        transform = io_config.get("transform")
        if transform and transform.get("type") not in VALID_TRANSFORM_TYPES:
            errors.append(
                f"{prefix}.transform: invalid type '{transform.get('type')}'"
            )

    control = data.get("control")
    if control:
        if "type" not in control:
            errors.append("control: missing 'type'")
        if "input_role" not in control or "output_role" not in control:
            errors.append("control: missing 'input_role' or 'output_role'")

    return errors


def validate_io_mapping(
    template: dict[str, Any],
    available_ios: set[str],
) -> list[str]:
    """Validate that all io_name values exist in the coordinator.

    Called during Options flow after user confirms the mapping.
    """
    errors: list[str] = []
    for key, io_config in template.get("ios", {}).items():
        io_name = io_config.get("io_name", "")
        if io_name not in available_ios:
            errors.append(
                f"IO '{io_name}' (role: {key}) not found in RevPi. "
                f"Available: {sorted(available_ios)}"
            )
    return errors


def get_template_dropdown(
    templates: dict[str, dict[str, Any]],
) -> dict[str, str]:
    """Convert templates dict to dropdown choices for vol.In()."""
    choices: dict[str, str] = {}
    builtin = {k: v for k, v in templates.items() if k.startswith("builtin:")}
    user = {k: v for k, v in templates.items() if k.startswith("user:")}

    for tid, info in sorted(builtin.items()):
        choices[tid] = info["display_name"]
    for tid, info in sorted(user.items()):
        choices[tid] = info["display_name"]

    return choices
