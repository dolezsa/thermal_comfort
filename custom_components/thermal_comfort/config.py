"""Thermal Comfort config validator."""

import voluptuous as vol

from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.config import async_log_exception, config_without_domain
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

from . import sensor as sensor_platform
from .const import DOMAIN
from .sensor import PLATFORM_OPTIONS_SCHEMA as SENSOR_OPTIONS_SCHEMA

PACKAGE_MERGE_HINT = "list"

OPTIONS_SCHEMA = vol.Schema({}).extend(
    SENSOR_OPTIONS_SCHEMA.schema,
    extra=vol.REMOVE_EXTRA,
)

CONFIG_SECTION_SCHEMA = vol.Schema(
    {
        vol.Optional(SENSOR_DOMAIN): vol.All(
            cv.ensure_list, [sensor_platform.SENSOR_SCHEMA]
        ),
    }
).extend(OPTIONS_SCHEMA.schema)


async def async_validate_config(hass: HomeAssistant, config: ConfigType) -> ConfigType:
    """Validate config."""
    if DOMAIN not in config:
        return config

    config_sections = []

    for cfg in cv.ensure_list(config[DOMAIN]):
        try:
            cfg = CONFIG_SECTION_SCHEMA(cfg)

        except vol.Invalid as err:
            async_log_exception(err, DOMAIN, cfg, hass)
            continue

        config_sections.append(cfg)

    # Create a copy of the configuration with all config for current
    # component removed and add validated config back in.
    config = config_without_domain(config, DOMAIN)
    config[DOMAIN] = config_sections

    return config
