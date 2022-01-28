"""Tests for config flows."""
from __future__ import annotations

import logging

from homeassistant import config_entries
from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.const import CONF_NAME, Platform
from homeassistant.core import HomeAssistant, State, callback
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
    _er: EntityRegistry,
    _hass: HomeAssistant,
    device_class: SensorDeviceClass,
    include_all: bool = False,
) -> list:
    """Get sensors of required class from entity registry."""

    def filter_by_device_class(
        _state: State, _list: list[SensorDeviceClass], should_be_in: bool = True
    ) -> bool:
        collected_device_class = _state.attributes.get(
            "device_class", _state.attributes.get("original_device_class")
        )
        # XNOR
        return not ((collected_device_class in _list) ^ should_be_in)

    def filter_for_device_class_sensor(state: State) -> bool:
        """Filter states by Platform.SENSOR and SensorDeviceClass.TEMPERATURE."""
        return state.domain == Platform.SENSOR and filter_by_device_class(
            state, [device_class], should_be_in=True
        )

    def filter_useless_device_class(state: State) -> bool:
        device_class_for_exclude = [
            SensorDeviceClass.AQI,
            SensorDeviceClass.BATTERY,
            SensorDeviceClass.CO,
            SensorDeviceClass.CO2,
            SensorDeviceClass.CURRENT,
            SensorDeviceClass.DATE,
            SensorDeviceClass.ENERGY,
            SensorDeviceClass.FREQUENCY,
            SensorDeviceClass.GAS,
            SensorDeviceClass.ILLUMINANCE,
            SensorDeviceClass.MONETARY,
            SensorDeviceClass.NITROGEN_DIOXIDE,
            SensorDeviceClass.NITROGEN_MONOXIDE,
            SensorDeviceClass.NITROUS_OXIDE,
            SensorDeviceClass.OZONE,
            SensorDeviceClass.PM1,
            SensorDeviceClass.PM10,
            SensorDeviceClass.PM25,
            SensorDeviceClass.POWER_FACTOR,
            SensorDeviceClass.POWER,
            SensorDeviceClass.PRESSURE,
            SensorDeviceClass.SIGNAL_STRENGTH,
            SensorDeviceClass.SULPHUR_DIOXIDE,
            SensorDeviceClass.TIMESTAMP,
            SensorDeviceClass.VOLATILE_ORGANIC_COMPOUNDS,
            SensorDeviceClass.VOLTAGE,
        ]
        """We are sure that this device classes could not be useful as data source in any case"""
        return filter_by_device_class(
            state, device_class_for_exclude, should_be_in=False
        )

    def filter_useless_domain(state: State) -> bool:
        domains_for_exclude = [
            Platform.AIR_QUALITY,
            Platform.ALARM_CONTROL_PANEL,
            Platform.BINARY_SENSOR,
            Platform.BUTTON,
            Platform.CALENDAR,
            Platform.CAMERA,
            Platform.COVER,
            Platform.DEVICE_TRACKER,
            Platform.FAN,
            Platform.GEO_LOCATION,
            Platform.IMAGE_PROCESSING,
            Platform.LIGHT,
            Platform.LOCK,
            Platform.MAILBOX,
            Platform.MEDIA_PLAYER,
            Platform.NOTIFY,
            Platform.REMOTE,
            Platform.SCENE,
            Platform.SIREN,
            Platform.STT,
            Platform.TTS,
            Platform.VACUUM,
            "automation",
            "person",
            "script",
            "scene",
            "timer",
            "zone",
        ]
        """We are sure that this domains could not be useful as data source in any case"""
        return state.domain not in domains_for_exclude

    def filter_useless_units(state: State) -> bool:
        units_for_exclude = [
            # Electric
            "W",
            "kW",
            "VA",
            "BTU/h" "Wh",
            "kWh",
            "MWh",
            "mA",
            "A",
            "mV",
            "V",
            # Degree units
            "°",
            # Currency units
            "€",
            "$",
            "¢",
            # Time units
            "μs",
            "ms",
            "s",
            "min",
            "h",
            "d",
            "w",
            "m",
            "y",
            # Length units
            "mm",
            "cm",
            "m",
            "km",
            "in",
            "ft",
            "yd",
            "mi",
            # Frequency units
            "Hz",
            "kHz",
            "MHz",
            "GHz",
            # Pressure units
            "Pa",
            "hPa",
            "kPa",
            "bar",
            "cbar",
            "mbar",
            "mmHg",
            "inHg",
            "psi",
            # Sound pressure units
            "dB",
            "dBa",
            # Volume units
            "L",
            "mL",
            "m³",
            "ft³",
            "gal",
            "fl. oz.",
            # Volume Flow Rate units
            "m³/h",
            "ft³/m",
            # Area units
            "m²",
            # Mass
            "g",
            "kg",
            "mg",
            "µg",
            "oz",
            "lb",
            #
            "µS/cm",
            "lx",
            "UV index",
            "W/m²",
            "BTU/(h×ft²)",
            # Precipitation units
            "mm/h",
            "in",
            "in/h",
            # Concentration units
            "µg/m³",
            "mg/m³",
            "μg/ft³",
            "p/m³",
            "ppm",
            "ppb",
            # Speed units
            "mm/d",
            "in/d",
            "m/s",
            "in/h",
            "km/h",
            "mph",
            # Signal_strength units
            "dB",
            "dBm",
            # Data units
            "bit",
            "kbit",
            "Mbit",
            "Gbit",
            "B",
            "kB",
            "MB",
            "GB",
            "TB",
            "PB",
            "EB",
            "ZB",
            "YB",
            "KiB",
            "MiB",
            "GiB",
            "TiB",
            "PiB",
            "EiB",
            "ZiB",
            "YiB",
            "bit/s",
            "kbit/s",
            "Mbit/s",
            "Gbit/s",
            "B/s",
            "kB/s",
            "MB/s",
            "GB/s",
            "KiB/s",
            "MiB/s",
            "GiB/s",
        ]
        """We are sure that entities with this units could not be useful as data source in any case"""
        unit_of_measurement = state.attributes.get(
            "unit_of_measurement", state.attributes.get("native_unit_of_measurement")
        )
        return unit_of_measurement not in units_for_exclude

    def filter_thermal_comfort_ids(entity_id: str) -> bool:
        """Filter out device_ids containing our SensorType."""
        return all(
            sensor_type.to_shortform() not in entity_id for sensor_type in SensorType
        )

    filters_for_additional_sensors: list[callable] = [
        filter_useless_device_class,
        filter_useless_domain,
        filter_useless_units,
    ]

    result = [
        state.entity_id
        for state in filter(
            filter_for_device_class_sensor,
            _hass.states.async_all(),
        )
    ]

    result.sort()
    _LOGGER.debug(f"Results for {device_class} based on device class: {result}")

    if include_all:
        additional_sensors = _hass.states.async_all()
        for f in filters_for_additional_sensors:
            additional_sensors = list(filter(f, additional_sensors))

        additional_entity_ids = [state.entity_id for state in additional_sensors]
        additional_entity_ids = list(set(additional_entity_ids) - set(result))
        additional_entity_ids.sort()
        _LOGGER.debug(f"Additional results: {additional_entity_ids}")
        result += additional_entity_ids

    result = list(
        filter(
            filter_thermal_comfort_ids,
            result,
        )
    )

    _LOGGER.debug(f"Results after cleaning own entities: {result}")

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
        entity_registry_instance, hass, SensorDeviceClass.HUMIDITY, show_advanced
    )
    temperature_sensors = get_sensors_by_device_class(
        entity_registry_instance, hass, SensorDeviceClass.TEMPERATURE, show_advanced
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
