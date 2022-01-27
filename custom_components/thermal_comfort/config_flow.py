"""Tests for config flows."""
from __future__ import annotations

import logging

from homeassistant import config_entries
from homeassistant.const import (
    CONF_NAME,
    DEVICE_CLASS_HUMIDITY,
    DEVICE_CLASS_TEMPERATURE,
    Platform,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry
from homeassistant.helpers.entity_registry import EntityRegistry
import voluptuous as vol

from .const import (
    CONF_HUMIDITY_SENSOR,
    CONF_POLL,
    CONF_TEMPERATURE_SENSOR,
    DEFAULT_NAME,
    DOMAIN,
)
from .sensor import DEFAULT_SENSOR_TYPES, SensorType

_LOGGER = logging.getLogger(__name__)


def get_sensors_by_device_class(
    _entity_registry_instance: EntityRegistry,
    _hass: HomeAssistant,
    device_class: str,
    include_not_in_registry: bool = False,
) -> list:
    """Get sensors of required class from entity registry."""

    result = [
        entity.values()
        for entity in _entity_registry_instance.async_get_device_class_lookup(
            {(Platform.SENSOR, device_class)}
        ).values()
    ]

    if include_not_in_registry:
        result += list(
            {e.entity_id for e in _hass.states.async_all()}
            - set(_entity_registry_instance.entities)
        )
    return result


def get_value(
    config_entry: config_entries.ConfigEntry | None, param: str, default=None
):
    """Get current value for configuration parameter.

    :param config_entry: config_entries|None: config entry from Flow
    :param param: str: parameter name for getting value
    :param default: default value for parameter, defaults to None
    :returns: parameter value, or default value or None
    """
    if config_entry is not None:
        return config_entry.options.get(param, config_entry.data.get(param, default))
    else:
        return default


def build_schema(
    config_entry: config_entries | None,
    hass: HomeAssistant,
    show_advanced: bool = False,
    step: str = "user",
) -> vol.Schema:
    """Build configuration schema.

    :param config_entry: config entry for getting current parameters on None
    :param hass: Home Assistant instance
    :param show_advanced: bool: should we show advanced options?
    :param step: for which step we should build schema
    :return: Configuration schema with default parameters
    """
    entity_registry_instance = entity_registry.async_get(hass)
    humidity_sensors = get_sensors_by_device_class(
        entity_registry_instance, hass, DEVICE_CLASS_HUMIDITY, show_advanced
    )
    temperature_sensors = get_sensors_by_device_class(
        entity_registry_instance, hass, DEVICE_CLASS_TEMPERATURE, show_advanced
    )

    schema = vol.Schema(
        {
            vol.Required(
                CONF_NAME, default=get_value(config_entry, CONF_NAME, DEFAULT_NAME)
            ): str,
            vol.Required(
                CONF_TEMPERATURE_SENSOR,
                default=get_value(
                    config_entry, CONF_TEMPERATURE_SENSOR, temperature_sensors[0]
                ),
            ): vol.In(temperature_sensors),
            vol.Required(
                CONF_HUMIDITY_SENSOR,
                default=get_value(
                    config_entry, CONF_HUMIDITY_SENSOR, humidity_sensors[0]
                ),
            ): vol.In(humidity_sensors),
        },
    )
    if show_advanced:
        schema = schema.extend(
            {
                vol.Optional(
                    CONF_POLL, default=get_value(config_entry, CONF_POLL, False)
                ): bool,
            }
        )
        if step == "user":
            for st in SensorType:
                default_enable = st in DEFAULT_SENSOR_TYPES
                schema = schema.extend(
                    {
                        vol.Optional(
                            str(st),
                            default=get_value(config_entry, str(st), default_enable),
                        ): bool
                    }
                )

    return schema


def check_input(hass: HomeAssistant, user_input: dict) -> dict:
    """Check that we may use suggested configuration.

    :param hass: hass instance
    :param user_input: user input
    :returns: dict with error.
    """

    # ToDo: user_input have ConfigType type, but it in codebase since 2021.12.10

    result = {}

    t_sensor = hass.states.get(user_input[CONF_TEMPERATURE_SENSOR])
    p_sensor = hass.states.get(user_input[CONF_HUMIDITY_SENSOR])

    if t_sensor is None:
        result["base"] = "temperature_not_found"

    if p_sensor is None:
        result["base"] = "humidity_not_found"

    # ToDo: we should not trust user and check:
    #  - that CONF_TEMPERATURE_SENSOR is temperature sensor and have state_class measurement
    #  - that CONF_HUMIDITY_SENSOR is humidity sensor and have state_class measurement
    return result


class ThermalComfortConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Configuration flow for setting up new thermal_comfort entry."""

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Get the options flow for this handler."""
        return ThermalComfortOptionsFlow(config_entry)

    async def async_step_user(self, user_input=None):
        """Handle a flow initialized by the user."""
        errors = {}

        if user_input is not None:
            if not (errors := check_input(self.hass, user_input)):
                er = entity_registry.async_get(self.hass)

                t_sensor = er.async_get(user_input[CONF_TEMPERATURE_SENSOR])
                p_sensor = er.async_get(user_input[CONF_HUMIDITY_SENSOR])
                _LOGGER.debug(f"Going to use t_sensor {t_sensor}")
                _LOGGER.debug(f"Going to use p_sensor {p_sensor}")

                if t_sensor is not None and p_sensor is not None:
                    unique_id = f"{t_sensor.unique_id}-{p_sensor.unique_id}"
                    await self.async_set_unique_id(unique_id)
                    self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title=user_input[CONF_NAME], data=user_input
                )

        return self.async_show_form(
            step_id="user",
            data_schema=build_schema(
                config_entry=None,
                hass=self.hass,
                show_advanced=self.show_advanced_options,
            ),
            errors=errors,
        )


class ThermalComfortOptionsFlow(config_entries.OptionsFlow):
    """Handle options."""

    def __init__(self, config_entry):
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        """Manage the options."""

        errors = {}
        if user_input is not None:
            _LOGGER.debug(f"OptionsFlow: going to update configuration {user_input}")
            if not (errors := check_input(self.hass, user_input)):
                return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=build_schema(
                config_entry=self.config_entry,
                hass=self.hass,
                show_advanced=self.show_advanced_options,
                step="init",
            ),
            errors=errors,
        )
