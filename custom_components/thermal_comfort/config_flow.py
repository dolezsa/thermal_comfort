"""Tests for config flows."""
from __future__ import annotations

import logging

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.const import CONF_NAME, Platform
from homeassistant.core import HomeAssistant, State, callback
from homeassistant.data_entry_flow import section
from homeassistant.helpers import entity_registry as er
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_registry import EntityRegistry
from homeassistant.helpers.selector import selector

from .const import DEFAULT_NAME, DOMAIN
from .sensor import (
    CONF_CUSTOM_ICONS,
    CONF_ENABLED_SENSORS,
    CONF_HUMIDITY_SENSOR,
    CONF_POLL,
    CONF_PRESSURE_SENSOR,
    CONF_SCAN_INTERVAL,
    CONF_TEMPERATURE_SENSOR,
    POLL_DEFAULT,
    SCAN_INTERVAL_DEFAULT,
    SensorType,
)

_LOGGER = logging.getLogger(__name__)

SECTION_ADVANCED = "advanced"
PRESSURE_DEVICE_CLASSES = [
    SensorDeviceClass.ATMOSPHERIC_PRESSURE,
    SensorDeviceClass.PRESSURE,
]


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
        """Filter state objects by device class.

        :param _state: state object for examination
        :param _list: list of device classes
        :param should_be_in: should the object's device_class be in the list to pass the filter or not
        """
        collected_device_class = _state.attributes.get(
            "device_class", _state.attributes.get("original_device_class")
        )
        # XNOR
        return not ((collected_device_class in _list) ^ should_be_in)

    def filter_for_device_class_sensor(state: State) -> bool:
        """Filter states by Platform.SENSOR and required device class."""
        return state.domain == Platform.SENSOR and filter_by_device_class(
            state, [device_class], should_be_in=True
        )

    def filter_useless_device_class(state: State) -> bool:
        """Filter out states with useless for us device class."""
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
        """Filter states with useless for us domains."""
        domains_for_exclude = [
            Platform.AIR_QUALITY,
            Platform.ALARM_CONTROL_PANEL,
            Platform.BINARY_SENSOR,
            Platform.BUTTON,
            Platform.CALENDAR,
            Platform.CAMERA,
            Platform.CLIMATE,
            Platform.COVER,
            Platform.DEVICE_TRACKER,
            Platform.FAN,
            Platform.GEO_LOCATION,
            Platform.IMAGE_PROCESSING,
            Platform.LIGHT,
            Platform.LOCK,
            Platform.MEDIA_PLAYER,
            Platform.NOTIFY,
            Platform.REMOTE,
            Platform.SCENE,
            Platform.SIREN,
            Platform.STT,
            Platform.SWITCH,
            Platform.TTS,
            Platform.VACUUM,
            "automation",
            "person",
            "script",
            "scene",
            "sun",
            "timer",
            "zone",
        ]
        """We are sure that this domains could not be useful as data source in any case"""
        return state.domain not in domains_for_exclude

    def filter_useless_units(state: State) -> bool:
        """Filter out states with useless for us units of measurements."""
        units_for_exclude = [
            # Electric
            "W",
            "kW",
            "VA",
            "BTU/h",
            "Wh",
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
            "µs",
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
            "µg/ft³",
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
        additional_units = {
            SensorDeviceClass.HUMIDITY: ["°C", "°F", "K"],
            SensorDeviceClass.TEMPERATURE: ["%"],
        }
        units_for_exclude += additional_units.get(device_class, [])

        unit_of_measurement = state.attributes.get(
            "unit_of_measurement", state.attributes.get("native_unit_of_measurement")
        )
        if isinstance(unit_of_measurement, str):
            # The list spells micro as U+00B5, the Home Assistant unit
            # enumerators use U+03BC, so compare them as the same character.
            unit_of_measurement = unit_of_measurement.replace("\u03bc", "\u00b5")
        return unit_of_measurement not in units_for_exclude

    def filter_thermal_comfort_ids(entity_id: str) -> bool:
        """Filter out device_ids containing our SensorType."""
        return all(sensor_type not in entity_id for sensor_type in SensorType)

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
    _LOGGER.debug("Results for %s based on device class: %s", device_class, result)

    if include_all:
        additional_sensors = _hass.states.async_all()
        for f in filters_for_additional_sensors:
            additional_sensors = list(filter(f, additional_sensors))

        additional_entity_ids = [state.entity_id for state in additional_sensors]
        additional_entity_ids = list(set(additional_entity_ids) - set(result))
        additional_entity_ids.sort()
        _LOGGER.debug("Additional results: %s", additional_entity_ids)
        result += additional_entity_ids

    result = list(
        filter(
            filter_thermal_comfort_ids,
            result,
        )
    )

    _LOGGER.debug("Results after cleaning own entities: %s", result)

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
    step: str = "user",
) -> vol.Schema:
    """Build configuration schema.

    :param config_entry: config entry for getting current parameters on None
    :param hass: Home Assistant instance
    :param step: for which step we should build schema
    :return: Configuration schema with default parameters
    """
    registry = er.async_get(hass)
    humidity_sensors = get_sensors_by_device_class(
        registry, hass, SensorDeviceClass.HUMIDITY, include_all=True
    )
    temperature_sensors = get_sensors_by_device_class(
        registry, hass, SensorDeviceClass.TEMPERATURE, include_all=True
    )

    if not temperature_sensors or not humidity_sensors:
        return None

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
            ): selector(
                {
                    "entity": {
                        "include_entities": temperature_sensors,
                    }
                }
            ),
            vol.Required(
                CONF_HUMIDITY_SENSOR,
                default=get_value(
                    config_entry, CONF_HUMIDITY_SENSOR, humidity_sensors[0]
                ),
            ): selector(
                {
                    "entity": {
                        "include_entities": humidity_sensors,
                    }
                }
            ),
            # Optional, without it the standard pressure of 101325 Pa is used
            vol.Optional(
                CONF_PRESSURE_SENSOR,
                description={
                    "suggested_value": get_value(config_entry, CONF_PRESSURE_SENSOR)
                },
            ): selector(
                {
                    "entity": {
                        "domain": Platform.SENSOR,
                        "device_class": PRESSURE_DEVICE_CLASSES,
                    }
                }
            ),
        },
    )
    advanced = {
        vol.Optional(
            CONF_POLL, default=get_value(config_entry, CONF_POLL, POLL_DEFAULT)
        ): bool,
        vol.Optional(
            CONF_SCAN_INTERVAL,
            default=get_value(config_entry, CONF_SCAN_INTERVAL, SCAN_INTERVAL_DEFAULT),
        ): vol.All(vol.Coerce(int), vol.Range(min=1)),
        vol.Optional(
            CONF_CUSTOM_ICONS,
            default=get_value(config_entry, CONF_CUSTOM_ICONS, False),
        ): bool,
    }
    if step == "user":
        advanced[
            vol.Optional(CONF_ENABLED_SENSORS, default=list(SensorType))
        ] = cv.multi_select(
            {sensor_type: sensor_type.to_name() for sensor_type in SensorType}
        )

    return schema.extend(
        {
            vol.Required(SECTION_ADVANCED): section(
                vol.Schema(advanced), {"collapsed": True}
            )
        }
    )


def flatten_input(user_input: dict) -> dict:
    """Move the options of the advanced section up to the top level.

    The config entry keeps the flat layout it always had.

    :param user_input: input of a form built by build_schema
    :return: flat dict with all options
    """
    flat = {k: v for k, v in user_input.items() if k != SECTION_ADVANCED}
    return flat | user_input.get(SECTION_ADVANCED, {})


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

    if (
        user_input.get(CONF_PRESSURE_SENSOR)
        and hass.states.get(user_input[CONF_PRESSURE_SENSOR]) is None
    ):
        result["base"] = "pressure_not_found"

    # ToDo: we should not trust user and check:
    #  - that CONF_TEMPERATURE_SENSOR is temperature sensor and have state_class measurement
    #  - that CONF_HUMIDITY_SENSOR is humidity sensor and have state_class measurement
    return result


class ThermalComfortConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Configuration flow for setting up new thermal_comfort entry."""

    VERSION = 2

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Get the options flow for this handler."""
        return ThermalComfortOptionsFlow()

    async def async_step_user(self, user_input=None):
        """Handle a flow initialized by the user."""
        errors = {}

        if user_input is not None:
            user_input = flatten_input(user_input)
            if not (errors := check_input(self.hass, user_input)):
                # The options flow can change the sensors of an entry later, so
                # compare with the current ones instead of the unique_id.
                sensors = (
                    user_input[CONF_TEMPERATURE_SENSOR],
                    user_input[CONF_HUMIDITY_SENSOR],
                )
                for entry in self._async_current_entries():
                    if sensors == (
                        get_value(entry, CONF_TEMPERATURE_SENSOR),
                        get_value(entry, CONF_HUMIDITY_SENSOR),
                    ):
                        return self.async_abort(reason="already_configured")

                registry = er.async_get(self.hass)

                t_sensor = registry.async_get(user_input[CONF_TEMPERATURE_SENSOR])
                p_sensor = registry.async_get(user_input[CONF_HUMIDITY_SENSOR])
                _LOGGER.debug("Going to use t_sensor %s", t_sensor)
                _LOGGER.debug("Going to use p_sensor %s", p_sensor)

                if t_sensor is not None and p_sensor is not None:
                    unique_id = f"{t_sensor.unique_id}-{p_sensor.unique_id}"
                    # An entry that was switched to other sensors by the options
                    # flow still owns its unique_id. Reusing it would make
                    # Home Assistant replace that entry, so use the entry_id
                    # fallback (see async_setup_entry) instead.
                    if (
                        self.hass.config_entries.async_entry_for_domain_unique_id(
                            DOMAIN, unique_id
                        )
                        is None
                    ):
                        await self.async_set_unique_id(unique_id)

                return self.async_create_entry(
                    title=user_input[CONF_NAME],
                    data=user_input,
                )

        schema = build_schema(config_entry=None, hass=self.hass)

        if schema is None:
            return self.async_abort(reason="no_sensors")

        return self.async_show_form(
            step_id="user",
            data_schema=schema,
            errors=errors,
        )


class ThermalComfortOptionsFlow(config_entries.OptionsFlowWithReload):
    """Handle options, the entry reloads when they change."""

    async def async_step_init(self, user_input=None):
        """Manage the options."""

        errors = {}
        if user_input is not None:
            user_input = flatten_input(user_input)
            if not user_input.get(CONF_PRESSURE_SENSOR) and get_value(
                self.config_entry, CONF_PRESSURE_SENSOR
            ):
                # The options win over the data, so removing the sensor must
                # be stored, the missing key would bring back the old one.
                user_input[CONF_PRESSURE_SENSOR] = None
            _LOGGER.debug("OptionsFlow: going to update configuration %s", user_input)
            if not (errors := check_input(self.hass, user_input)):
                return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=build_schema(
                config_entry=self.config_entry,
                hass=self.hass,
                step="init",
            ),
            errors=errors,
        )
