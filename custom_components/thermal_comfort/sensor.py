"""Sensor platform for thermal_comfort."""
from asyncio import Lock
import contextlib
from dataclasses import dataclass
from datetime import timedelta
from enum import StrEnum
from functools import wraps
import logging
import math
from typing import Self, override

import voluptuous as vol

from homeassistant import util
from homeassistant.components.sensor import (
    DOMAIN as SENSOR_DOMAIN,
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_TEMPERATURE,
    ATTR_UNIT_OF_MEASUREMENT,
    CONF_ENTITY_PICTURE_TEMPLATE,
    CONF_ICON_TEMPLATE,
    CONF_NAME,
    CONF_SENSORS,
    CONF_UNIQUE_ID,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    EntityCategory,
    UnitOfPressure,
    UnitOfSpeed,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError, TemplateError
from homeassistant.helpers import entity_registry as er
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import (
    async_track_state_change_event,
    async_track_time_interval,
)
from homeassistant.helpers.template import Template
from homeassistant.loader import async_get_custom_components
from homeassistant.util.unit_conversion import (
    PressureConverter,
    SpeedConverter,
    TemperatureConverter,
)

from .const import DEFAULT_NAME, DOMAIN

_LOGGER = logging.getLogger(__name__)

ATTR_DEW_POINT = "dew_point"
ATTR_HUMIDITY = "humidity"
ATTR_PRESSURE = "pressure"
ATTR_VAPOR_PRESSURE = "vapor_pressure"
ATTR_SATURATION_VAPOR_PRESSURE = "saturation_vapor_pressure"
ATTR_HUMIDEX = "humidex"
ATTR_FROST_POINT = "frost_point"
ATTR_RELATIVE_STRAIN_INDEX = "relative_strain_index"
ATTR_SUMMER_SCHARLAU_INDEX = "summer_scharlau_index"
ATTR_WINTER_SCHARLAU_INDEX = "winter_scharlau_index"
ATTR_SUMMER_SIMMER_INDEX = "summer_simmer_index"
ATTR_THOMS_DISCOMFORT_INDEX = "thoms_discomfort_index"
ATTR_EPSTEIN_MORAN_DISCOMFORT_INDEX = "epstein_moran_discomfort_index"
ATTR_OUTDOOR_TEMPERATURE = "outdoor_temperature"
ATTR_OUTDOOR_HUMIDITY = "outdoor_humidity"
ATTR_OUTDOOR_ABSOLUTE_HUMIDITY = "outdoor_absolute_humidity"
ATTR_OUTDOOR_DEW_POINT = "outdoor_dew_point"
ATTR_VENTILATED_RELATIVE_HUMIDITY = "ventilated_relative_humidity"
ATTR_WIND_SPEED = "wind_speed"
CONF_ENABLED_SENSORS = "enabled_sensors"
CONF_SENSOR_TYPES = "sensor_types"
CONF_CUSTOM_ICONS = "custom_icons"
CONF_SCAN_INTERVAL = "scan_interval"

CONF_TEMPERATURE_SENSOR = "temperature_sensor"
CONF_HUMIDITY_SENSOR = "humidity_sensor"
CONF_PRESSURE_SENSOR = "pressure_sensor"
CONF_OUTDOOR_TEMPERATURE_SENSOR = "outdoor_temperature_sensor"
CONF_OUTDOOR_HUMIDITY_SENSOR = "outdoor_humidity_sensor"
CONF_WIND_SPEED_SENSOR = "wind_speed_sensor"
CONF_TEMPERATURE_ATTRIBUTE = "temperature_attribute"
CONF_HUMIDITY_ATTRIBUTE = "humidity_attribute"
CONF_POLL = "poll"
# Default values
POLL_DEFAULT = False
SCAN_INTERVAL_DEFAULT = 30
DISPLAY_PRECISION = 2
HUMIDITY_MAX_OVERSHOOT = 105  # readings up to this are clipped to 100
STANDARD_PRESSURE = 101325  # Pa, standard pressure at sea level
# Plausible range of an atmospheric pressure reading, in Pa
PRESSURE_MIN = 30000
PRESSURE_MAX = 110000
# The state of these domains is never a number, the values are in attributes
DEFAULT_TEMPERATURE_ATTRIBUTES = {
    "weather": "temperature",
    "climate": "current_temperature",
}
DEFAULT_HUMIDITY_ATTRIBUTES = {
    "weather": "humidity",
    "climate": "current_humidity",
}
DEFAULT_WIND_SPEED_ATTRIBUTES = {
    "weather": "wind_speed",
}
# The attribute of a weather entity that has the unit of its temperature
ATTR_TEMPERATURE_UNIT = "temperature_unit"
# The attribute of a weather entity that has the unit of its wind speed
ATTR_WIND_SPEED_UNIT = "wind_speed_unit"
# Only the units of a speed, the converter of speeds also has the ones of
# the precipitation intensity
WIND_SPEED_UNITS = frozenset(UnitOfSpeed)
# Wind speeds above this (m/s) are no plausible reading of the wind
WIND_SPEED_MAX = 120.0
# The wind chill formula is valid up to this air temperature (C) and above
# this wind speed (km/h), otherwise the wind chill is the air temperature
WIND_CHILL_MAX_TEMPERATURE = 10.0
WIND_CHILL_MIN_WIND_SPEED = 4.8
# Ventilation, with a source of the outdoor air
# Differences of the absolute humidity (g/m3) below which the air is "similar"
VENTILATION_BAND = 1.0
# The indoor air should not regularly have more than this (g/m3) above the
# outdoor air in winter (Folkhälsomyndigheten, FoHMFS 2014:18)
VENTILATION_NEED_LIMIT = 3.0
# There is no definition of winter in it, this is the outdoor temperature (C)
# below which the limit is looked at
VENTILATION_NEED_MAX_OUTDOOR_TEMPERATURE = 10.0
# Outdoor air with this relative humidity (%) after it is warmed to the indoor
# temperature is near saturation on the cooler surfaces (EN ISO 13788)
CONDENSATION_RH_LIMIT = 80.0


class LegacySensorType(StrEnum):
    """Sensors names from thermal comfort < 2.0."""

    THERMAL_PERCEPTION = "thermal_perception"
    SIMMER_INDEX = "simmer_index"
    SIMMER_ZONE = "simmer_zone"


class SensorType(StrEnum):
    """Sensor type enum."""

    # A sensor must come after the sensors it computes from, otherwise it has no
    # initial state, see async_added_to_hass of SensorThermalComfort.
    ABSOLUTE_HUMIDITY = "absolute_humidity"
    DEW_POINT = "dew_point"
    DEW_POINT_PERCEPTION = "dew_point_perception"
    FROST_POINT = "frost_point"
    FROST_RISK = "frost_risk"
    HEAT_INDEX = "heat_index"
    HUMIDEX = "humidex"
    HUMIDEX_PERCEPTION = "humidex_perception"
    MOIST_AIR_ENTHALPY = "moist_air_enthalpy"
    RELATIVE_STRAIN_PERCEPTION = "relative_strain_perception"
    SUMMER_SCHARLAU_PERCEPTION = "summer_scharlau_perception"
    WINTER_SCHARLAU_PERCEPTION = "winter_scharlau_perception"
    SUMMER_SIMMER_INDEX = "summer_simmer_index"
    SUMMER_SIMMER_PERCEPTION = "summer_simmer_perception"
    WET_BULB_TEMPERATURE = "wet_bulb_temperature"
    THOMS_DISCOMFORT_INDEX = "thoms_discomfort_index"
    THOMS_DISCOMFORT_PERCEPTION = "thoms_discomfort_perception"
    HUMIDITY_RATIO = "humidity_ratio"
    VAPOR_PRESSURE_DEFICIT = "vapor_pressure_deficit"
    # These need the outdoor air, see OUTDOOR_SENSOR_TYPES
    MOISTURE_EXCESS = "moisture_excess"
    VENTILATION_ADVICE = "ventilation_advice"
    VENTILATION_NEED = "ventilation_need"
    # These need the wind speed, see WIND_SENSOR_TYPES
    WIND_CHILL = "wind_chill"
    APPARENT_TEMPERATURE = "apparent_temperature"

    def to_name(self) -> str:
        """Return the title of the sensor type."""
        return self.value.replace("_", " ").capitalize()

    @classmethod
    def from_string(cls, string: str) -> Self:
        """Return the sensor type from string."""
        if string in list(cls):
            return cls(string)
        else:
            raise ValueError(
                f"Unknown sensor type: {string}. Please check https://github.com/dolezsa/thermal_comfort/blob/master/documentation/yaml.md#sensor-options for valid options."
            )


class VentilationAdvice(StrEnum):
    """What airing does to the humidity of the room."""

    DRIER_OUTSIDE = "drier_outside"
    SIMILAR = "similar"
    MORE_HUMID_OUTSIDE = "more_humid_outside"
    CONDENSATION_RISK = "condensation_risk"


class VentilationNeed(StrEnum):
    """Where the moisture excess is compared to the limit for winter."""

    ABOVE_LIMIT = "above_limit"
    WITHIN_LIMIT = "within_limit"
    NOT_WINTER = "not_winter"


class DewPointPerception(StrEnum):
    """Thermal Perception."""

    DRY = "dry"
    VERY_COMFORTABLE = "very_comfortable"
    COMFORTABLE = "comfortable"
    OK_BUT_HUMID = "ok_but_humid"
    SOMEWHAT_UNCOMFORTABLE = "somewhat_uncomfortable"
    QUITE_UNCOMFORTABLE = "quite_uncomfortable"
    EXTREMELY_UNCOMFORTABLE = "extremely_uncomfortable"
    SEVERELY_HIGH = "severely_high"


class FrostRisk(StrEnum):
    """Frost Risk."""

    NONE = "no_risk"
    LOW = "unlikely"
    MEDIUM = "probable"
    HIGH = "high"


class SummerSimmerPerception(StrEnum):
    """Simmer Zone."""

    COOL = "cool"
    SLIGHTLY_COOL = "slightly_cool"
    COMFORTABLE = "comfortable"
    SLIGHTLY_WARM = "slightly_warm"
    INCREASING_DISCOMFORT = "increasing_discomfort"
    EXTREMELY_WARM = "extremely_warm"
    DANGER_OF_HEATSTROKE = "danger_of_heatstroke"
    EXTREME_DANGER_OF_HEATSTROKE = "extreme_danger_of_heatstroke"
    CIRCULATORY_COLLAPSE_IMMINENT = "circulatory_collapse_imminent"


class RelativeStrainPerception(StrEnum):
    """Relative Strain Perception."""

    OUTSIDE_CALCULABLE_RANGE = "outside_calculable_range"
    COMFORTABLE = "comfortable"
    SLIGHT_DISCOMFORT = "slight_discomfort"
    DISCOMFORT = "discomfort"
    SIGNIFICANT_DISCOMFORT = "significant_discomfort"
    EXTREME_DISCOMFORT = "extreme_discomfort"


class ScharlauPerception(StrEnum):
    """Scharlau Winter and Summer Index Perception."""

    OUTSIDE_CALCULABLE_RANGE = "outside_calculable_range"
    COMFORTABLE = "comfortable"
    SLIGHTLY_UNCOMFORTABLE = "slightly_uncomfortable"
    MODERATELY_UNCOMFORTABLE = "moderately_uncomfortable"
    HIGHLY_UNCOMFORTABLE = "highly_uncomfortable"


class HumidexPerception(StrEnum):
    """Humidex Perception."""

    COMFORTABLE = "comfortable"
    NOTICABLE_DISCOMFORT = "noticable_discomfort"
    EVIDENT_DISCOMFORT = "evident_discomfort"
    GREAT_DISCOMFORT = "great_discomfort"
    DANGEROUS_DISCOMFORT = "dangerous_discomfort"
    HEAT_STROKE = "heat_stroke"


class ThomsDiscomfortPerception(StrEnum):
    """Thoms Discomfort Perception."""

    NO_DISCOMFORT = "no_discomfort"
    LESS_THAN_HALF = "less_than_half"
    MORE_THAN_HALF = "more_than_half"
    MOST = "most"
    EVERYONE = "everyone"
    DANGEROUS = "dangerous"


TC_ICONS = {
    SensorType.DEW_POINT: "tc:dew-point",
    SensorType.FROST_POINT: "tc:frost-point",
    SensorType.HUMIDEX_PERCEPTION: "tc:thermal-perception",
    SensorType.RELATIVE_STRAIN_PERCEPTION: "tc:thermal-perception",
    SensorType.SUMMER_SCHARLAU_PERCEPTION: "tc:thermal-perception",
    SensorType.WINTER_SCHARLAU_PERCEPTION: "tc:thermal-perception",
    SensorType.SUMMER_SIMMER_PERCEPTION: "tc:thermal-perception",
    SensorType.DEW_POINT_PERCEPTION: "tc:thermal-perception",
    SensorType.THOMS_DISCOMFORT_PERCEPTION: "tc:thermal-perception",
}

SENSOR_TYPES = {
    SensorType.ABSOLUTE_HUMIDITY: {
        "key": SensorType.ABSOLUTE_HUMIDITY,
        "device_class": SensorDeviceClass.ABSOLUTE_HUMIDITY,
        "suggested_display_precision": DISPLAY_PRECISION,
        "native_unit_of_measurement": "g/m³",
        "state_class": SensorStateClass.MEASUREMENT,
        "icon": "mdi:water",
    },
    SensorType.DEW_POINT: {
        "key": SensorType.DEW_POINT,
        "entity_category": EntityCategory.DIAGNOSTIC,
        "device_class": SensorDeviceClass.TEMPERATURE,
        "suggested_display_precision": DISPLAY_PRECISION,
        "native_unit_of_measurement": UnitOfTemperature.CELSIUS,
        "state_class": SensorStateClass.MEASUREMENT,
        "icon": "mdi:thermometer-water",
    },
    SensorType.DEW_POINT_PERCEPTION: {
        "key": SensorType.DEW_POINT_PERCEPTION,
        "device_class": SensorDeviceClass.ENUM,
        "options": list(map(str, DewPointPerception)),
        "icon": "mdi:sun-thermometer",
    },
    SensorType.FROST_POINT: {
        "key": SensorType.FROST_POINT,
        "entity_category": EntityCategory.DIAGNOSTIC,
        "device_class": SensorDeviceClass.TEMPERATURE,
        "suggested_display_precision": DISPLAY_PRECISION,
        "native_unit_of_measurement": UnitOfTemperature.CELSIUS,
        "state_class": SensorStateClass.MEASUREMENT,
        "icon": "mdi:snowflake-thermometer",
    },
    SensorType.FROST_RISK: {
        "key": SensorType.FROST_RISK,
        "device_class": SensorDeviceClass.ENUM,
        "options": list(map(str, FrostRisk)),
        "icon": "mdi:snowflake-alert",
    },
    SensorType.HEAT_INDEX: {
        "key": SensorType.HEAT_INDEX,
        "entity_category": EntityCategory.DIAGNOSTIC,
        "device_class": SensorDeviceClass.TEMPERATURE,
        "suggested_display_precision": DISPLAY_PRECISION,
        "native_unit_of_measurement": UnitOfTemperature.CELSIUS,
        "state_class": SensorStateClass.MEASUREMENT,
        "icon": "mdi:sun-thermometer",
    },
    SensorType.HUMIDEX: {
        "key": SensorType.HUMIDEX,
        "entity_category": EntityCategory.DIAGNOSTIC,
        "device_class": SensorDeviceClass.TEMPERATURE,
        "suggested_display_precision": DISPLAY_PRECISION,
        "native_unit_of_measurement": UnitOfTemperature.CELSIUS,
        "state_class": SensorStateClass.MEASUREMENT,
        "icon": "mdi:sun-thermometer",
    },
    SensorType.HUMIDEX_PERCEPTION: {
        "key": SensorType.HUMIDEX_PERCEPTION,
        "device_class": SensorDeviceClass.ENUM,
        "options": list(map(str, HumidexPerception)),
        "icon": "mdi:sun-thermometer",
    },
    SensorType.MOIST_AIR_ENTHALPY: {
        "key": SensorType.MOIST_AIR_ENTHALPY,
        "suggested_display_precision": DISPLAY_PRECISION,
        "native_unit_of_measurement": "kJ/kg",
        "state_class": SensorStateClass.MEASUREMENT,
        "icon": "mdi:water-circle",
    },
    SensorType.RELATIVE_STRAIN_PERCEPTION: {
        "key": SensorType.RELATIVE_STRAIN_PERCEPTION,
        "device_class": SensorDeviceClass.ENUM,
        "options": list(map(str, RelativeStrainPerception)),
        "icon": "mdi:sun-thermometer",
    },
    SensorType.SUMMER_SCHARLAU_PERCEPTION: {
        "key": SensorType.SUMMER_SCHARLAU_PERCEPTION,
        "device_class": SensorDeviceClass.ENUM,
        "options": list(map(str, ScharlauPerception)),
        "icon": "mdi:sun-thermometer",
    },
    SensorType.WINTER_SCHARLAU_PERCEPTION: {
        "key": SensorType.WINTER_SCHARLAU_PERCEPTION,
        "device_class": SensorDeviceClass.ENUM,
        "options": list(map(str, ScharlauPerception)),
        "icon": "mdi:snowflake-thermometer",
    },
    SensorType.SUMMER_SIMMER_INDEX: {
        "key": SensorType.SUMMER_SIMMER_INDEX,
        "entity_category": EntityCategory.DIAGNOSTIC,
        "device_class": SensorDeviceClass.TEMPERATURE,
        "suggested_display_precision": DISPLAY_PRECISION,
        "native_unit_of_measurement": UnitOfTemperature.CELSIUS,
        "state_class": SensorStateClass.MEASUREMENT,
        "icon": "mdi:sun-thermometer",
    },
    SensorType.SUMMER_SIMMER_PERCEPTION: {
        "key": SensorType.SUMMER_SIMMER_PERCEPTION,
        "device_class": SensorDeviceClass.ENUM,
        "options": list(map(str, SummerSimmerPerception)),
        "icon": "mdi:sun-thermometer",
    },
    SensorType.WET_BULB_TEMPERATURE: {
        "key": SensorType.WET_BULB_TEMPERATURE,
        "device_class": SensorDeviceClass.TEMPERATURE,
        "entity_category": EntityCategory.DIAGNOSTIC,
        "suggested_display_precision": DISPLAY_PRECISION,
        "native_unit_of_measurement": UnitOfTemperature.CELSIUS,
        "state_class": SensorStateClass.MEASUREMENT,
        "icon": "mdi:water-thermometer",
    },
    SensorType.THOMS_DISCOMFORT_INDEX: {
        "key": SensorType.THOMS_DISCOMFORT_INDEX,
        "suggested_display_precision": DISPLAY_PRECISION,
        "native_unit_of_measurement": UnitOfTemperature.CELSIUS,
        "state_class": SensorStateClass.MEASUREMENT,
        "icon": "mdi:sun-thermometer",
    },
    SensorType.THOMS_DISCOMFORT_PERCEPTION: {
        "key": SensorType.THOMS_DISCOMFORT_PERCEPTION,
        "device_class": SensorDeviceClass.ENUM,
        "options": list(map(str, ThomsDiscomfortPerception)),
        "icon": "mdi:sun-thermometer",
    },
    SensorType.HUMIDITY_RATIO: {
        "key": SensorType.HUMIDITY_RATIO,
        "suggested_display_precision": DISPLAY_PRECISION,
        "native_unit_of_measurement": "g/kg",
        "state_class": SensorStateClass.MEASUREMENT,
        "icon": "mdi:water-outline",
    },
    SensorType.VAPOR_PRESSURE_DEFICIT: {
        "key": SensorType.VAPOR_PRESSURE_DEFICIT,
        "suggested_display_precision": DISPLAY_PRECISION,
        "native_unit_of_measurement": "kPa",
        "state_class": SensorStateClass.MEASUREMENT,
        "icon": "mdi:water-minus",
    },
    SensorType.MOISTURE_EXCESS: {
        "key": SensorType.MOISTURE_EXCESS,
        "suggested_display_precision": DISPLAY_PRECISION,
        "native_unit_of_measurement": "g/m³",
        "state_class": SensorStateClass.MEASUREMENT,
        "icon": "mdi:water-percent",
    },
    SensorType.VENTILATION_ADVICE: {
        "key": SensorType.VENTILATION_ADVICE,
        "device_class": SensorDeviceClass.ENUM,
        "options": list(map(str, VentilationAdvice)),
        "icon": "mdi:window-open-variant",
    },
    SensorType.VENTILATION_NEED: {
        "key": SensorType.VENTILATION_NEED,
        "device_class": SensorDeviceClass.ENUM,
        "options": list(map(str, VentilationNeed)),
        "icon": "mdi:home-alert",
    },
    SensorType.WIND_CHILL: {
        "key": SensorType.WIND_CHILL,
        "entity_category": EntityCategory.DIAGNOSTIC,
        "device_class": SensorDeviceClass.TEMPERATURE,
        "suggested_display_precision": DISPLAY_PRECISION,
        "native_unit_of_measurement": UnitOfTemperature.CELSIUS,
        "state_class": SensorStateClass.MEASUREMENT,
        "icon": "mdi:snowflake-thermometer",
    },
    SensorType.APPARENT_TEMPERATURE: {
        "key": SensorType.APPARENT_TEMPERATURE,
        "entity_category": EntityCategory.DIAGNOSTIC,
        "device_class": SensorDeviceClass.TEMPERATURE,
        "suggested_display_precision": DISPLAY_PRECISION,
        "native_unit_of_measurement": UnitOfTemperature.CELSIUS,
        "state_class": SensorStateClass.MEASUREMENT,
        "icon": "mdi:thermometer-lines",
    },
}

# The sensors that compare with the outdoor air, a device has them when it has
# the sensors of the outdoor temperature and humidity
OUTDOOR_SENSOR_TYPES = [
    SensorType.MOISTURE_EXCESS,
    SensorType.VENTILATION_ADVICE,
    SensorType.VENTILATION_NEED,
]
# The sensors that depend on the pressure of the optional pressure sensor
PRESSURE_SENSOR_TYPES = [
    SensorType.MOIST_AIR_ENTHALPY,
    SensorType.HUMIDITY_RATIO,
]
# The sensors that need the wind speed, a device has them when it has the
# sensor of the wind speed
WIND_SENSOR_TYPES = [
    SensorType.WIND_CHILL,
    SensorType.APPARENT_TEMPERATURE,
]
DEFAULT_SENSOR_TYPES = [
    sensor_type
    for sensor_type in SENSOR_TYPES
    if sensor_type not in OUTDOOR_SENSOR_TYPES
    and sensor_type not in WIND_SENSOR_TYPES
]

SENSOR_OPTIONS_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_POLL): cv.boolean,
        vol.Optional(CONF_SCAN_INTERVAL): cv.time_period,
        vol.Optional(CONF_CUSTOM_ICONS): cv.boolean,
        vol.Optional(CONF_SENSOR_TYPES): cv.ensure_list,
        vol.Optional(CONF_OUTDOOR_TEMPERATURE_SENSOR): cv.entity_id,
        vol.Optional(CONF_OUTDOOR_HUMIDITY_SENSOR): cv.entity_id,
        vol.Optional(CONF_WIND_SPEED_SENSOR): cv.entity_id,
    },
    extra=vol.REMOVE_EXTRA,
)

SENSOR_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_NAME): cv.string,
        vol.Required(CONF_TEMPERATURE_SENSOR): cv.entity_id,
        vol.Required(CONF_HUMIDITY_SENSOR): cv.entity_id,
        vol.Optional(CONF_PRESSURE_SENSOR): cv.entity_id,
        vol.Optional(CONF_TEMPERATURE_ATTRIBUTE): vol.All(cv.string, vol.Strip),
        vol.Optional(CONF_HUMIDITY_ATTRIBUTE): vol.All(cv.string, vol.Strip),
        vol.Optional(CONF_ICON_TEMPLATE): cv.template,
        vol.Optional(CONF_ENTITY_PICTURE_TEMPLATE): cv.template,
        vol.Required(CONF_UNIQUE_ID): cv.string,
    }
).extend(SENSOR_OPTIONS_SCHEMA.schema)


def compute_once_lock(sensor_type):
    """Only compute if sensor_type needs update, return just the value otherwise."""

    def wrapper(func):
        @wraps(func)
        async def wrapped(self, *args, **kwargs):
            if not self.type_available(sensor_type):
                return None
            async with self._compute_states[sensor_type].lock:
                if self._compute_states[sensor_type].needs_update:
                    setattr(self, f"_{sensor_type}", await func(self, *args, **kwargs))
                    self._compute_states[sensor_type].needs_update = False
                return getattr(self, f"_{sensor_type}", None)

        return wrapped

    return wrapper


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the Thermal Comfort sensors."""
    if discovery_info is None:
        _LOGGER.warning(
            "Legacy YAML configuration is unsupported since 2.0 and will stop working in the next release. You should update to the new yaml format: https://github.com/dolezsa/thermal_comfort/blob/master/documentation/yaml.md"
        )
        devices = [
            dict(device_config, **{CONF_NAME: device_name})
            for (device_name, device_config) in config[CONF_SENSORS].items()
        ]
        options = {}
    else:
        devices = discovery_info["devices"]
        options = discovery_info["options"]

    sensors = []

    for device_config in devices:
        device_config = options | device_config
        outdoor_temperature = device_config.get(CONF_OUTDOOR_TEMPERATURE_SENSOR)
        outdoor_humidity = device_config.get(CONF_OUTDOOR_HUMIDITY_SENSOR)
        if bool(outdoor_temperature) != bool(outdoor_humidity):
            _LOGGER.warning(
                "The sensors of the outdoor temperature and of the outdoor humidity are both needed, the outdoor air is not used for %s",
                device_config.get(CONF_NAME, device_config.get(CONF_UNIQUE_ID)),
            )
            outdoor_temperature = outdoor_humidity = None
        compute_device = DeviceThermalComfort(
            hass=hass,
            name=device_config.get(CONF_NAME),
            unique_id=device_config.get(CONF_UNIQUE_ID),
            temperature_entity=device_config.get(CONF_TEMPERATURE_SENSOR),
            humidity_entity=device_config.get(CONF_HUMIDITY_SENSOR),
            pressure_entity=device_config.get(CONF_PRESSURE_SENSOR),
            temperature_attribute=device_config.get(CONF_TEMPERATURE_ATTRIBUTE),
            humidity_attribute=device_config.get(CONF_HUMIDITY_ATTRIBUTE),
            outdoor_temperature_entity=outdoor_temperature,
            outdoor_humidity_entity=outdoor_humidity,
            wind_speed_entity=device_config.get(CONF_WIND_SPEED_SENSOR),
            should_poll=device_config.get(CONF_POLL, POLL_DEFAULT),
            scan_interval=device_config.get(
                CONF_SCAN_INTERVAL, timedelta(seconds=SCAN_INTERVAL_DEFAULT)
            ),
        )

        if CONF_SENSOR_TYPES in device_config:
            sensor_types = [
                SensorType.from_string(sensor_type)
                for sensor_type in device_config[CONF_SENSOR_TYPES]
            ]
            outdoor_types = [t for t in sensor_types if t in OUTDOOR_SENSOR_TYPES]
            if outdoor_types and not compute_device.has_outdoor:
                _LOGGER.warning(
                    "The sensor types %s need the sensors of the outdoor temperature and the outdoor humidity, they are not created for %s",
                    ", ".join(outdoor_types),
                    device_config.get(CONF_NAME, device_config.get(CONF_UNIQUE_ID)),
                )
                sensor_types = [t for t in sensor_types if t not in outdoor_types]
            wind_types = [t for t in sensor_types if t in WIND_SENSOR_TYPES]
            if wind_types and not compute_device.has_wind:
                _LOGGER.warning(
                    "The sensor types %s need the sensor of the wind speed, they are not created for %s",
                    ", ".join(wind_types),
                    device_config.get(CONF_NAME, device_config.get(CONF_UNIQUE_ID)),
                )
                sensor_types = [t for t in sensor_types if t not in wind_types]
        else:
            sensor_types = list(DEFAULT_SENSOR_TYPES)
            if compute_device.has_outdoor:
                sensor_types += OUTDOOR_SENSOR_TYPES
            if compute_device.has_wind:
                sensor_types += WIND_SENSOR_TYPES

        sensors += [
            SensorThermalComfort(
                device=compute_device,
                icon_template=device_config.get(CONF_ICON_TEMPLATE),
                entity_picture_template=device_config.get(CONF_ENTITY_PICTURE_TEMPLATE),
                sensor_type=sensor_type,
                custom_icons=device_config.get(CONF_CUSTOM_ICONS, False),
                is_config_entry=False,
            )
            for sensor_type in sensor_types
        ]

    async_add_entities(sensors)
    return True


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up entity configured via user interface.

    Called via async_forward_entry_setups(, SENSOR) from __init__.py
    """
    data = hass.data[DOMAIN][config_entry.entry_id]
    if data.get(CONF_SCAN_INTERVAL) is None:
        hass.data[DOMAIN][config_entry.entry_id][
            CONF_SCAN_INTERVAL
        ] = SCAN_INTERVAL_DEFAULT
        data[CONF_SCAN_INTERVAL] = SCAN_INTERVAL_DEFAULT

    _LOGGER.debug("async_setup_entry: %s", data)
    compute_device = DeviceThermalComfort(
        hass=hass,
        name=data[CONF_NAME],
        unique_id=f"{config_entry.unique_id}",
        temperature_entity=data[CONF_TEMPERATURE_SENSOR],
        humidity_entity=data[CONF_HUMIDITY_SENSOR],
        pressure_entity=data.get(CONF_PRESSURE_SENSOR),
        temperature_attribute=data.get(CONF_TEMPERATURE_ATTRIBUTE),
        humidity_attribute=data.get(CONF_HUMIDITY_ATTRIBUTE),
        outdoor_temperature_entity=data.get(CONF_OUTDOOR_TEMPERATURE_SENSOR),
        outdoor_humidity_entity=data.get(CONF_OUTDOOR_HUMIDITY_SENSOR),
        wind_speed_entity=data.get(CONF_WIND_SPEED_SENSOR),
        should_poll=data[CONF_POLL],
        scan_interval=timedelta(
            seconds=data.get(CONF_SCAN_INTERVAL, SCAN_INTERVAL_DEFAULT)
        ),
    )

    config_entry.async_on_unload(compute_device.async_unsubscribe)

    entities: list[SensorThermalComfort] = [
        SensorThermalComfort(
            device=compute_device,
            sensor_type=sensor_type,
            custom_icons=data[CONF_CUSTOM_ICONS],
            # The sensors of the outdoor air and of the wind are what their
            # sensors are for, and are not among the sensors that can be chosen
            is_enabled_default=sensor_type in OUTDOOR_SENSOR_TYPES
            or sensor_type in WIND_SENSOR_TYPES
            or sensor_type in data.get(CONF_ENABLED_SENSORS, {}),
        )
        for sensor_type in (
            DEFAULT_SENSOR_TYPES
            + (OUTDOOR_SENSOR_TYPES if compute_device.has_outdoor else [])
            + (WIND_SENSOR_TYPES if compute_device.has_wind else [])
        )
    ]

    if entities:
        async_add_entities(entities)


def id_generator(unique_id: str, sensor_type: str) -> str:
    """Generate id based on unique_id and sensor type.

    :param unique_id: str: common part of id for all entities, device unique_id, as a rule
    :param sensor_type: str: different part of id, sensor type, as s rule
    :returns: str: unique_id+sensor_type
    """
    return unique_id + sensor_type


class SensorThermalComfort(SensorEntity):
    """Representation of a Thermal Comfort Sensor."""

    # The source values change with almost every update, don't fill the
    # database with a new attribute row each time.
    _unrecorded_attributes = frozenset(
        {
            ATTR_TEMPERATURE,
            ATTR_HUMIDITY,
            ATTR_PRESSURE,
            ATTR_VAPOR_PRESSURE,
            ATTR_SATURATION_VAPOR_PRESSURE,
            ATTR_OUTDOOR_TEMPERATURE,
            ATTR_OUTDOOR_HUMIDITY,
            ATTR_OUTDOOR_ABSOLUTE_HUMIDITY,
            ATTR_OUTDOOR_DEW_POINT,
            ATTR_WIND_SPEED,
        }
    )

    def __init__(
        self,
        device: "DeviceThermalComfort",
        sensor_type: SensorType,
        icon_template: Template = None,
        entity_picture_template: Template = None,
        custom_icons: bool = False,
        is_config_entry: bool = True,
        is_enabled_default: bool = True,
    ) -> None:
        """Initialize the sensor."""
        self._device = device
        self._sensor_type = sensor_type
        self._is_config_entry = is_config_entry
        entity_description = dict(SENSOR_TYPES[sensor_type])
        entity_description["translation_key"] = sensor_type
        entity_description["has_entity_name"] = True
        if not is_config_entry:
            if self._device.name is not None:
                entity_description["has_entity_name"] = False
                entity_description["name"] = (
                    f"{self._device.name} {self._sensor_type.to_name()}"
                )
            if sensor_type in [SensorType.DEW_POINT_PERCEPTION, SensorType.SUMMER_SIMMER_INDEX, SensorType.SUMMER_SIMMER_PERCEPTION]:
                registry = er.async_get(self._device.hass)
                match sensor_type:
                    case SensorType.DEW_POINT_PERCEPTION:
                        unique_id = id_generator(self._device.unique_id, LegacySensorType.THERMAL_PERCEPTION)
                    case SensorType.SUMMER_SIMMER_INDEX:
                        unique_id = id_generator(self._device.unique_id, LegacySensorType.SIMMER_INDEX)
                    case SensorType.SUMMER_SIMMER_PERCEPTION:
                        unique_id = id_generator(self._device.unique_id, LegacySensorType.SIMMER_ZONE)
                entity_id = registry.async_get_entity_id(SENSOR_DOMAIN, DOMAIN, unique_id)
                if entity_id is not None:
                    registry.async_update_entity(entity_id, new_unique_id=id_generator(self._device.unique_id, sensor_type))
        if custom_icons:
            if entity_description["key"] in TC_ICONS:
                entity_description["icon"] = TC_ICONS[entity_description["key"]]
        entity_description["entity_registry_enabled_default"] = is_enabled_default
        self.entity_description = SensorEntityDescription(**entity_description)
        self._icon_template = icon_template
        self._entity_picture_template = entity_picture_template
        self._attr_native_value = None
        self._attr_extra_state_attributes = {}
        self._attr_unique_id = id_generator(self._device.unique_id, sensor_type)
        self._attr_should_poll = False

    @property
    @override
    def suggested_object_id(self) -> str | None:
        """Return the English sensor name as the base of the entity_id.

        The name of the entity is translated, without this the entity_id gets
        translated too in the languages that have native entity ids.
        """
        if self.has_entity_name:
            return self._sensor_type.to_name()
        return super().suggested_object_id

    @property
    def device_info(self) -> DeviceInfo | None:
        """Return device information, only config entries can have devices."""
        return self._device.device_info if self._is_config_entry else None

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        return dict(
            self._device.extra_state_attributes, **self._attr_extra_state_attributes
        )

    async def async_added_to_hass(self):
        """Register callbacks."""
        self._device.sensors.append(self)
        if self._icon_template is not None:
            self._icon_template.hass = self.hass
        if self._entity_picture_template is not None:
            self._entity_picture_template.hass = self.hass
        if self._device.compute_states[self._sensor_type].needs_update:
            self.async_schedule_update_ha_state(True)

    async def async_will_remove_from_hass(self):
        """Unregister callbacks."""
        if self in self._device.sensors:
            self._device.sensors.remove(self)
        if not self._device.sensors:
            self._device.async_unsubscribe()

    @property
    def available(self) -> bool:
        """Return True if the source values the sensor needs are valid."""
        return self._device.type_available(self._sensor_type)

    async def async_update(self):
        """Update the state of the sensor."""
        if not self._device.type_available(self._sensor_type):
            return

        value = await getattr(self._device, self._sensor_type)()
        if value is None:  # can happen during startup
            return

        if isinstance(value, tuple) and len(value) == 2:
            self._attr_extra_state_attributes.update(value[1])
            value = value[0]

        self._attr_native_value = value


        for property_name, template in (
            ("_attr_icon", self._icon_template),
            ("_attr_entity_picture", self._entity_picture_template),
        ):
            if template is None:
                continue

            try:
                setattr(self, property_name, template.async_render())
            except TemplateError as ex:
                friendly_property_name = property_name[1:].replace("_", " ")
                if ex.args and ex.args[0].startswith(
                    "UndefinedError: 'None' has no attribute"
                ):
                    # Common during HA startup - so just a warning
                    _LOGGER.warning(
                        "Could not render %s template %s, the state is unknown.",
                        friendly_property_name,
                        self.name,
                    )
                    continue

                try:
                    setattr(self, property_name, getattr(super(), property_name))
                except AttributeError:
                    _LOGGER.error(
                        "Could not render %s template %s: %s",
                        friendly_property_name,
                        self.name,
                        ex,
                    )


@dataclass
class ComputeState:
    """Thermal Comfort Calculation State."""

    needs_update: bool = False
    lock: Lock = None


class DeviceThermalComfort:
    """Representation of a Thermal Comfort Sensor."""

    def __init__(
        self,
        hass: HomeAssistant,
        name: str,
        unique_id: str,
        temperature_entity: str,
        humidity_entity: str,
        should_poll: bool,
        scan_interval: timedelta,
        pressure_entity: str | None = None,
        temperature_attribute: str | None = None,
        humidity_attribute: str | None = None,
        outdoor_temperature_entity: str | None = None,
        outdoor_humidity_entity: str | None = None,
        wind_speed_entity: str | None = None,
    ):
        """Initialize the sensor."""
        self.hass = hass
        self._unique_id = unique_id
        self._device_info = DeviceInfo(
            identifiers={(DOMAIN, self.unique_id)},
            name=name,
            manufacturer=DEFAULT_NAME,
            model="Virtual Device",
        )
        self.extra_state_attributes = {}
        self._temperature_entity = temperature_entity
        self._humidity_entity = humidity_entity
        self._pressure_entity = pressure_entity
        self._temperature_attribute = source_attribute(
            temperature_entity, temperature_attribute, DEFAULT_TEMPERATURE_ATTRIBUTES
        )
        self._humidity_attribute = source_attribute(
            humidity_entity, humidity_attribute, DEFAULT_HUMIDITY_ATTRIBUTES
        )
        self._temperature = None
        self._humidity = None
        self._pressure = None  # Pa, None means the standard pressure
        self._was_available = False
        # The outdoor air is used when both are given
        self._outdoor_temperature_entity = outdoor_temperature_entity
        self._outdoor_humidity_entity = outdoor_humidity_entity
        self._outdoor_temperature_attribute = source_attribute(
            outdoor_temperature_entity,
            None,
            DEFAULT_TEMPERATURE_ATTRIBUTES,
        )
        self._outdoor_humidity_attribute = source_attribute(
            outdoor_humidity_entity, None, DEFAULT_HUMIDITY_ATTRIBUTES
        )
        self._outdoor_temperature = None  # C
        self._outdoor_temperature_value = None  # as the source has it
        self._outdoor_humidity = None
        self._was_outdoor_available = False
        self._wind_speed_entity = wind_speed_entity
        self._wind_speed_attribute = source_attribute(
            wind_speed_entity, None, DEFAULT_WIND_SPEED_ATTRIBUTES
        )
        self._wind_speed = None  # m/s
        self._was_wind_available = False
        self._unsubscribers = []
        self._should_poll = should_poll
        self.sensors = []
        self._compute_states = {
            sensor_type: ComputeState(lock=Lock())
            for sensor_type in SENSOR_TYPES
        }

        if self._temperature_entity == self._humidity_entity:
            # One change updates both values, so they have to be read together,
            # otherwise the sensors are computed with the new value of the
            # one and the old value of the other.
            self._unsubscribers.append(
                async_track_state_change_event(
                    self.hass, self._temperature_entity, self.source_state_listener
                )
            )
        else:
            self._unsubscribers.append(
                async_track_state_change_event(
                    self.hass,
                    self._temperature_entity,
                    self.temperature_state_listener,
                )
            )

            self._unsubscribers.append(
                async_track_state_change_event(
                    self.hass, self._humidity_entity, self.humidity_state_listener
                )
            )

        if self._pressure_entity:
            # Read before the first computation, so it never starts with the
            # standard pressure when the sensor is already there.
            self._pressure = self._parse_pressure(hass.states.get(pressure_entity))
            self._unsubscribers.append(
                async_track_state_change_event(
                    self.hass, self._pressure_entity, self.pressure_state_listener
                )
            )

        if self.has_outdoor:
            # Read before the first computation, like the pressure
            self._apply_outdoor_temperature(hass.states.get(outdoor_temperature_entity))
            self._apply_outdoor_humidity(hass.states.get(outdoor_humidity_entity))
            if outdoor_temperature_entity == outdoor_humidity_entity:
                self._unsubscribers.append(
                    async_track_state_change_event(
                        self.hass,
                        outdoor_temperature_entity,
                        self.outdoor_source_state_listener,
                    )
                )
            else:
                self._unsubscribers.append(
                    async_track_state_change_event(
                        self.hass,
                        outdoor_temperature_entity,
                        self.outdoor_temperature_state_listener,
                    )
                )
                self._unsubscribers.append(
                    async_track_state_change_event(
                        self.hass,
                        outdoor_humidity_entity,
                        self.outdoor_humidity_state_listener,
                    )
                )

        if self.has_wind:
            # Read before the first computation, like the pressure
            self._apply_wind_speed(hass.states.get(wind_speed_entity))
            # A source of the temperature or the humidity that has the wind
            # speed too is read by its own listener, so one change is never
            # computed with the new value of the one and the old of the other.
            if wind_speed_entity not in (temperature_entity, humidity_entity):
                self._unsubscribers.append(
                    async_track_state_change_event(
                        self.hass, wind_speed_entity, self.wind_speed_state_listener
                    )
                )

        if self._temperature_entity == self._humidity_entity:
            hass.async_create_task(
                self._new_source_state(hass.states.get(temperature_entity))
            )
        else:
            hass.async_create_task(
                self._new_temperature_state(hass.states.get(temperature_entity))
            )
            hass.async_create_task(
                self._new_humidity_state(hass.states.get(humidity_entity))
            )

        hass.async_create_task(self._set_version())

        if self._should_poll:
            if scan_interval is None:
                scan_interval = timedelta(seconds=SCAN_INTERVAL_DEFAULT)
            self._unsubscribers.append(
                async_track_time_interval(
                    self.hass,
                    self.async_update_sensors,
                    scan_interval,
                )
            )

    @callback
    def async_unsubscribe(self) -> None:
        """Stop listening to the source entities and stop polling."""
        while self._unsubscribers:
            self._unsubscribers.pop()()

    async def _set_version(self):
        self._device_info["sw_version"] = (
            await async_get_custom_components(self.hass)
        )[DOMAIN].version.string

    async def temperature_state_listener(self, event):
        """Handle temperature device state changes."""
        await self._new_temperature_state(event.data.get("new_state"))

    async def source_state_listener(self, event):
        """Handle the state changes of an entity that is the source of both values."""
        await self._new_source_state(event.data.get("new_state"))

    async def _new_source_state(self, state):
        wind_changed = self._apply_shared_wind_speed(self._temperature_entity, state)
        # Both values have to be read, a bitwise or does not skip the second
        changed = self._apply_temperature(state) | self._apply_humidity(state)
        if changed:
            await self.async_update()
        elif wind_changed:
            await self._wind_updated()

    async def _new_temperature_state(self, state):
        wind_changed = self._apply_shared_wind_speed(self._temperature_entity, state)
        if self._apply_temperature(state):
            await self.async_update()
        elif wind_changed:
            await self._wind_updated()

    def _apply_temperature(self, state) -> bool:
        """Read the temperature of a source state.

        :returns: True if the sensors have to be updated, which is the case for
            a new value and for an invalid one.
        """
        temperature, value = _parse_temperature(
            self.hass, state, self._temperature_attribute
        )
        # A source with the value in an attribute changes its other attributes
        # often, plain sensors update for every change as they always did.
        changed = (
            self._temperature_attribute is None
            or temperature is None
            or temperature != self._temperature
            or value != self.extra_state_attributes.get(ATTR_TEMPERATURE)
        )
        if temperature is None:
            _LOGGER.info("Temperature has an invalid value: %s. Can't calculate new states.", state)
            self.extra_state_attributes.pop(ATTR_TEMPERATURE, None)
        else:
            self.extra_state_attributes[ATTR_TEMPERATURE] = value
        self._temperature = temperature
        return changed

    async def humidity_state_listener(self, event):
        """Handle humidity device state changes."""
        await self._new_humidity_state(event.data.get("new_state"))

    async def _new_humidity_state(self, state):
        wind_changed = self._apply_shared_wind_speed(self._humidity_entity, state)
        if self._apply_humidity(state):
            await self.async_update()
        elif wind_changed:
            await self._wind_updated()

    def _apply_humidity(self, state) -> bool:
        """Read the humidity of a source state.

        :returns: True if the sensors have to be updated, which is the case for
            a new value and for an invalid one.
        """
        humidity = _parse_humidity(state, self._humidity_attribute)
        changed = (
            self._humidity_attribute is None
            or humidity is None
            or humidity != self._humidity
        )
        if humidity is None:
            _LOGGER.info("Relative humidity has an invalid value: %s. Can't calculate new states.", state)
            self.extra_state_attributes.pop(ATTR_HUMIDITY, None)
        else:
            self.extra_state_attributes[ATTR_HUMIDITY] = humidity
        self._humidity = humidity
        return changed

    @property
    def has_outdoor(self) -> bool:
        """Return True if the sources of the outdoor air are set."""
        return bool(self._outdoor_temperature_entity) and bool(
            self._outdoor_humidity_entity
        )

    @property
    def outdoor_available(self) -> bool:
        """Return True if both values of the outdoor air are valid."""
        return (
            self.has_outdoor
            and self._outdoor_temperature is not None
            and self._outdoor_humidity is not None
        )

    def type_available(self, sensor_type: SensorType) -> bool:
        """Return True if the values a sensor type needs are valid.

        The sensors of the outdoor air need its values too, the other sensors
        never depend on them.
        """
        if sensor_type in OUTDOOR_SENSOR_TYPES:
            return self.available and self.outdoor_available
        if sensor_type in WIND_SENSOR_TYPES:
            return self.available and self.wind_available
        return self.available

    async def outdoor_temperature_state_listener(self, event):
        """Handle outdoor temperature state changes."""
        await self._new_outdoor_temperature_state(event.data.get("new_state"))

    async def outdoor_humidity_state_listener(self, event):
        """Handle outdoor humidity state changes."""
        await self._new_outdoor_humidity_state(event.data.get("new_state"))

    async def outdoor_source_state_listener(self, event):
        """Handle the state changes of an entity that is the source of both outdoor values."""
        state = event.data.get("new_state")
        changed = self._apply_outdoor_temperature(state) | self._apply_outdoor_humidity(
            state
        )
        if changed:
            await self._outdoor_updated()

    async def _new_outdoor_temperature_state(self, state):
        if self._apply_outdoor_temperature(state):
            await self._outdoor_updated()

    async def _new_outdoor_humidity_state(self, state):
        if self._apply_outdoor_humidity(state):
            await self._outdoor_updated()

    def _apply_outdoor_temperature(self, state) -> bool:
        """Read the outdoor temperature, True if the sensors need an update."""
        temperature, value = _parse_temperature(
            self.hass, state, self._outdoor_temperature_attribute
        )
        changed = (
            temperature is None
            or temperature != self._outdoor_temperature
            or value != self._outdoor_temperature_value
        )
        if temperature is None:
            _LOGGER.info("Outdoor temperature has an invalid value: %s. Can't calculate the sensors of the outdoor air.", state)
        self._outdoor_temperature = temperature
        self._outdoor_temperature_value = value
        return changed

    def _apply_outdoor_humidity(self, state) -> bool:
        """Read the outdoor humidity, True if the sensors need an update."""
        humidity = _parse_humidity(state, self._outdoor_humidity_attribute)
        changed = humidity is None or humidity != self._outdoor_humidity
        if humidity is None:
            _LOGGER.info("Outdoor relative humidity has an invalid value: %s. Can't calculate the sensors of the outdoor air.", state)
        self._outdoor_humidity = humidity
        return changed

    async def _outdoor_updated(self):
        """Update the sensors of the outdoor air, the others do not depend on it."""
        for sensor_type in OUTDOOR_SENSOR_TYPES:
            self._compute_states[sensor_type].needs_update = True
        available = self.type_available(OUTDOOR_SENSOR_TYPES[0])
        # Polling devices refresh on the timer, but not when availability changes
        if not self._should_poll or available != self._was_outdoor_available:
            for sensor in self.sensors:
                if sensor._sensor_type in OUTDOOR_SENSOR_TYPES:
                    sensor.async_schedule_update_ha_state(True)
        self._was_outdoor_available = available

    @property
    def has_wind(self) -> bool:
        """Return True if the source of the wind speed is set."""
        return bool(self._wind_speed_entity)

    @property
    def wind_available(self) -> bool:
        """Return True if the wind speed is valid."""
        return self.has_wind and self._wind_speed is not None

    async def wind_speed_state_listener(self, event):
        """Handle wind speed state changes."""
        if self._apply_wind_speed(event.data.get("new_state")):
            await self._wind_updated()

    def _apply_shared_wind_speed(self, entity_id: str, state) -> bool:
        """Read the wind speed of a source of the temperature or the humidity.

        :returns: True if the entity is the source of the wind speed too and
            the sensors of the wind need an update.
        """
        if not self.has_wind or entity_id != self._wind_speed_entity:
            return False
        return self._apply_wind_speed(state)

    def _apply_wind_speed(self, state) -> bool:
        """Read the wind speed, True if the sensors need an update."""
        speed = self._parse_wind_speed(state)
        changed = speed is None or speed != self._wind_speed
        if speed is None:
            _LOGGER.info("Wind speed has an invalid value: %s. Can't calculate the sensors of the wind.", state)
        self._wind_speed = speed
        return changed

    def _parse_wind_speed(self, state) -> float | None:
        """Return the wind speed of a source state in m/s, None if unusable."""
        value = None
        unit = None
        if self._wind_speed_attribute is None:
            if _is_valid_state(state):
                value = util.convert(state.state, float)
                unit = state.attributes.get(ATTR_UNIT_OF_MEASUREMENT)
        else:
            value = _attribute_value(state, self._wind_speed_attribute)
            if value is not None:
                unit = state.attributes.get(ATTR_WIND_SPEED_UNIT)
        if unit is None:
            unit = self.hass.config.units.wind_speed_unit
        # A negative Beaufort value can't even be converted
        if (
            value is None
            or not math.isfinite(value)
            or value < 0
            or not isinstance(unit, str)
            or unit not in WIND_SPEED_UNITS
        ):
            return None
        speed = None
        with contextlib.suppress(HomeAssistantError, TypeError, ValueError):
            speed = SpeedConverter.convert(value, unit, UnitOfSpeed.METERS_PER_SECOND)
        if speed is None or not math.isfinite(speed) or not 0 <= speed <= WIND_SPEED_MAX:
            return None
        return speed

    async def _wind_updated(self):
        """Update the sensors of the wind, the others do not depend on it."""
        for sensor_type in WIND_SENSOR_TYPES:
            self._compute_states[sensor_type].needs_update = True
        available = self.type_available(WIND_SENSOR_TYPES[0])
        # Polling devices refresh on the timer, but not when availability changes
        if not self._should_poll or available != self._was_wind_available:
            self._schedule_wind_sensors()
        self._was_wind_available = available

    def _schedule_wind_sensors(self) -> None:
        """Ask the sensors of the wind for a new state."""
        for sensor in self.sensors:
            if sensor._sensor_type in WIND_SENSOR_TYPES:
                sensor.async_schedule_update_ha_state(True)

    def _wind_attributes(self) -> dict:
        """Return the attributes of the sensors of the wind."""
        return {ATTR_WIND_SPEED: round(self._wind_speed * 3.6, 2)}

    async def pressure_state_listener(self, event):
        """Handle pressure device state changes."""
        await self._new_pressure_state(event.data.get("new_state"))

    def _parse_pressure(self, state) -> float | None:
        """Return the pressure of a source state in Pa, None if unusable."""
        pressure = None
        if _is_valid_state(state):
            unit = state.attributes.get(
                ATTR_UNIT_OF_MEASUREMENT, self.hass.config.units.pressure_unit
            )
            with contextlib.suppress(HomeAssistantError):
                pressure = PressureConverter.convert(
                    float(state.state), unit, UnitOfPressure.PA
                )
            if pressure is not None and not PRESSURE_MIN <= pressure <= PRESSURE_MAX:
                pressure = None
        if pressure is None:
            _LOGGER.info(
                "Pressure has an invalid value: %s. Using the standard pressure.",
                state,
            )
        return pressure

    async def _new_pressure_state(self, state):
        pressure = self._parse_pressure(state)
        if pressure == self._pressure:
            return
        self._pressure = pressure
        for sensor_type in PRESSURE_SENSOR_TYPES:
            self._compute_states[sensor_type].needs_update = True
        if self.available and not self._should_poll:
            for sensor in self.sensors:
                if sensor._sensor_type in PRESSURE_SENSOR_TYPES:
                    sensor.async_schedule_update_ha_state(True)

    def _actual_pressure(self) -> float:
        """Return the pressure in Pa to use for the calculations.

        The measured pressure when a valid one is available, otherwise the
        standard pressure at sea level.
        """
        if self._pressure is not None:
            return self._pressure
        return STANDARD_PRESSURE

    @compute_once_lock(SensorType.DEW_POINT)
    async def dew_point(self) -> float:
        """Dew Point <http://wahiduddin.net/calc/density_algorithms.htm>."""
        return _dew_point(self._temperature, self._humidity)

    @compute_once_lock(SensorType.HEAT_INDEX)
    async def heat_index(self) -> float:
        """Heat Index <http://www.wpc.ncep.noaa.gov/html/heatindex_equation.shtml>."""
        fahrenheit = TemperatureConverter.convert(
            self._temperature, UnitOfTemperature.CELSIUS, UnitOfTemperature.FAHRENHEIT
        )
        hi = 0.5 * (
            fahrenheit + 61.0 + ((fahrenheit - 68.0) * 1.2) + (self._humidity * 0.094)
        )

        if hi > 79:
            hi = -42.379 + 2.04901523 * fahrenheit
            hi = hi + 10.14333127 * self._humidity
            hi = hi + -0.22475541 * fahrenheit * self._humidity
            hi = hi + -0.00683783 * pow(fahrenheit, 2)
            hi = hi + -0.05481717 * pow(self._humidity, 2)
            hi = hi + 0.00122874 * pow(fahrenheit, 2) * self._humidity
            hi = hi + 0.00085282 * fahrenheit * pow(self._humidity, 2)
            hi = hi + -0.00000199 * pow(fahrenheit, 2) * pow(self._humidity, 2)

        if self._humidity < 13 and fahrenheit >= 80 and fahrenheit <= 112:
            hi = hi - ((13 - self._humidity) * 0.25) * math.sqrt(
                (17 - abs(fahrenheit - 95)) * 0.05882
            )
        elif self._humidity > 85 and fahrenheit >= 80 and fahrenheit <= 87:
            hi = hi + ((self._humidity - 85) * 0.1) * ((87 - fahrenheit) * 0.2)

        return TemperatureConverter.convert(hi, UnitOfTemperature.FAHRENHEIT, UnitOfTemperature.CELSIUS)

    @compute_once_lock(SensorType.HUMIDEX)
    async def humidex(self) -> int:
        """<https://simple.wikipedia.org/wiki/Humidex#Humidex_formula>."""
        dewpoint = await self.dew_point()
        e = 6.11 * math.exp(5417.7530 * ((1 / 273.16) - (1 / (dewpoint + 273.15))))
        h = (0.5555) * (e - 10.0)
        return self._temperature + h

    @compute_once_lock(SensorType.HUMIDEX_PERCEPTION)
    async def humidex_perception(self) -> (HumidexPerception, dict):
        """<https://simple.wikipedia.org/wiki/Humidex#Humidex_formula>."""
        humidex = await self.humidex()
        if humidex > 54:
            perception = HumidexPerception.HEAT_STROKE
        elif humidex >= 45:
            perception = HumidexPerception.DANGEROUS_DISCOMFORT
        elif humidex >= 40:
            perception = HumidexPerception.GREAT_DISCOMFORT
        elif humidex >= 35:
            perception = HumidexPerception.EVIDENT_DISCOMFORT
        elif humidex >= 30:
            perception = HumidexPerception.NOTICABLE_DISCOMFORT
        else:
            perception = HumidexPerception.COMFORTABLE

        return perception, {ATTR_HUMIDEX: humidex}

    @compute_once_lock(SensorType.DEW_POINT_PERCEPTION)
    async def dew_point_perception(self) -> (DewPointPerception, dict):
        """Dew Point <https://en.wikipedia.org/wiki/Dew_point>."""
        dewpoint = await self.dew_point()
        if dewpoint < 10:
            perception = DewPointPerception.DRY
        elif dewpoint < 13:
            perception = DewPointPerception.VERY_COMFORTABLE
        elif dewpoint < 16:
            perception = DewPointPerception.COMFORTABLE
        elif dewpoint < 18:
            perception = DewPointPerception.OK_BUT_HUMID
        elif dewpoint < 21:
            perception = DewPointPerception.SOMEWHAT_UNCOMFORTABLE
        elif dewpoint < 24:
            perception = DewPointPerception.QUITE_UNCOMFORTABLE
        elif dewpoint < 26:
            perception = DewPointPerception.EXTREMELY_UNCOMFORTABLE
        else:
            perception = DewPointPerception.SEVERELY_HIGH

        return perception, {ATTR_DEW_POINT: dewpoint}

    @compute_once_lock(SensorType.ABSOLUTE_HUMIDITY)
    async def absolute_humidity(self) -> float:
        """Absolute Humidity <https://carnotcycle.wordpress.com/2012/08/04/how-to-convert-relative-humidity-to-absolute-humidity/>."""
        return _absolute_humidity(self._temperature, self._humidity)

    @compute_once_lock(SensorType.FROST_POINT)
    async def frost_point(self) -> float:
        """Frost Point <https://pon.fr/dzvents-alerte-givre-et-calcul-humidite-absolue/>."""
        dewpoint = await self.dew_point()
        T = self._temperature + 273.15
        Td = dewpoint + 273.15
        return (Td + (2671.02 / ((2954.61 / T) + 2.193665 * math.log(T) - 13.3448)) - T) - 273.15

    @compute_once_lock(SensorType.FROST_RISK)
    async def frost_risk(self) -> (FrostRisk, dict):
        """Frost Risk Level."""
        thresholdAbsHumidity = 2.8
        absolutehumidity = await self.absolute_humidity()
        frostpoint = await self.frost_point()
        if self._temperature <= 1 and frostpoint <= 0:
            if absolutehumidity <= thresholdAbsHumidity:
                frost_risk = FrostRisk.LOW  # Frost unlikely despite the temperature
            else:
                frost_risk = FrostRisk.HIGH  # high probability of frost
        elif (
            self._temperature <= 4
            and frostpoint <= 0.5
            and absolutehumidity > thresholdAbsHumidity
        ):
            frost_risk = FrostRisk.MEDIUM  # Frost probable despite the temperature
        else:
            frost_risk = FrostRisk.NONE  # No risk of frost

        return frost_risk, {ATTR_FROST_POINT: frostpoint}

    @compute_once_lock(SensorType.RELATIVE_STRAIN_PERCEPTION)
    async def relative_strain_perception(self) -> (RelativeStrainPerception, dict):
        """Relative strain perception."""

        vp = 6.112 * pow(10, 7.5 * self._temperature / (237.7 + self._temperature))
        e = self._humidity * vp / 100
        rsi = round((self._temperature - 21) / (58 - e), 2)

        if self._temperature < 26 or self._temperature > 35:
            perception = RelativeStrainPerception.OUTSIDE_CALCULABLE_RANGE
        elif rsi >= 0.45:
            perception = RelativeStrainPerception.EXTREME_DISCOMFORT
        elif rsi >= 0.35:
            perception = RelativeStrainPerception.SIGNIFICANT_DISCOMFORT
        elif rsi >= 0.25:
            perception = RelativeStrainPerception.DISCOMFORT
        elif rsi >= 0.15:
            perception = RelativeStrainPerception.SLIGHT_DISCOMFORT
        else:
            perception = RelativeStrainPerception.COMFORTABLE

        return perception, {ATTR_RELATIVE_STRAIN_INDEX: rsi}

    @compute_once_lock(SensorType.SUMMER_SCHARLAU_PERCEPTION)
    async def summer_scharlau_perception(self) -> (ScharlauPerception, dict):
        """<https://revistadechimie.ro/pdf/16%20RUSANESCU%204%2019.pdf>."""
        tc = -17.089 * math.log(self._humidity) + 94.979
        ise = tc - self._temperature

        if self._temperature < 17 or self._temperature > 39 or self._humidity < 30:
            perception = ScharlauPerception.OUTSIDE_CALCULABLE_RANGE
        elif ise <= -3:
            perception = ScharlauPerception.HIGHLY_UNCOMFORTABLE
        elif ise <= -1:
            perception = ScharlauPerception.MODERATELY_UNCOMFORTABLE
        elif ise < 0:
            perception = ScharlauPerception.SLIGHTLY_UNCOMFORTABLE
        else:
            perception = ScharlauPerception.COMFORTABLE

        return perception, {ATTR_SUMMER_SCHARLAU_INDEX: round(ise, 2)}

    @compute_once_lock(SensorType.WINTER_SCHARLAU_PERCEPTION)
    async def winter_scharlau_perception(self) -> (ScharlauPerception, dict):
        """<https://revistadechimie.ro/pdf/16%20RUSANESCU%204%2019.pdf>."""
        tc = -0.0003 * pow(self._humidity, 2) + 0.1497 * self._humidity - 7.7133
        ish = self._temperature - tc
        if self._temperature < -5 or self._temperature > 6 or self._humidity < 40:
            perception = ScharlauPerception.OUTSIDE_CALCULABLE_RANGE
        elif ish <= -3:
            perception = ScharlauPerception.HIGHLY_UNCOMFORTABLE
        elif ish <= -1:
            perception = ScharlauPerception.MODERATELY_UNCOMFORTABLE
        elif ish < 0:
            perception = ScharlauPerception.SLIGHTLY_UNCOMFORTABLE
        else:
            perception = ScharlauPerception.COMFORTABLE

        return perception, {ATTR_WINTER_SCHARLAU_INDEX: round(ish, 2)}

    @compute_once_lock(SensorType.SUMMER_SIMMER_INDEX)
    async def summer_simmer_index(self) -> float:
        """<https://www.vcalc.com/wiki/rklarsen/Summer+Simmer+Index>."""
        fahrenheit = TemperatureConverter.convert(
            self._temperature, UnitOfTemperature.CELSIUS, UnitOfTemperature.FAHRENHEIT
        )

        si = (
            1.98
            * (fahrenheit - (0.55 - (0.0055 * self._humidity)) * (fahrenheit - 58.0))
            - 56.83
        )

        if fahrenheit < 58:  # Summer Simmer Index is only valid above 58°F
            si = fahrenheit

        return TemperatureConverter.convert(si, UnitOfTemperature.FAHRENHEIT, UnitOfTemperature.CELSIUS)

    @compute_once_lock(SensorType.SUMMER_SIMMER_PERCEPTION)
    async def summer_simmer_perception(self) -> (SummerSimmerPerception, dict):
        """<http://summersimmer.com/default.asp>."""
        si = await self.summer_simmer_index()
        if si < 21.1:
            summer_simmer_perception = SummerSimmerPerception.COOL
        elif si < 25.0:
            summer_simmer_perception = SummerSimmerPerception.SLIGHTLY_COOL
        elif si < 28.3:
            summer_simmer_perception = SummerSimmerPerception.COMFORTABLE
        elif si < 32.8:
            summer_simmer_perception = SummerSimmerPerception.SLIGHTLY_WARM
        elif si < 37.8:
            summer_simmer_perception = SummerSimmerPerception.INCREASING_DISCOMFORT
        elif si < 44.4:
            summer_simmer_perception = SummerSimmerPerception.EXTREMELY_WARM
        elif si < 51.7:
            summer_simmer_perception = SummerSimmerPerception.DANGER_OF_HEATSTROKE
        elif si < 65.6:
            summer_simmer_perception = SummerSimmerPerception.EXTREME_DANGER_OF_HEATSTROKE
        else:
            summer_simmer_perception = SummerSimmerPerception.CIRCULATORY_COLLAPSE_IMMINENT

        return summer_simmer_perception, {ATTR_SUMMER_SIMMER_INDEX: si}

    @compute_once_lock(SensorType.MOIST_AIR_ENTHALPY)
    async def moist_air_enthalpy(self) -> float | tuple[float, dict]:
        """Calculate the enthalpy of moist air."""
        patm = self._actual_pressure()  # Pa

        # calculate humidity ratio (ASHRAE fundamentals 2021 pg 1.9 eq 20)
        W = _humidity_ratio(self._temperature, self._humidity, patm)

        # calculate enthalpy (ASHRAE fundamentals 2021 pg 1.10 eq 30)
        enthalpy = 1.006 * self._temperature + W * (2501 + 1.86 * self._temperature)
        if self._pressure_entity:
            # Show the pressure in use, only where a sensor was configured
            return enthalpy, {ATTR_PRESSURE: patm / 100}
        return enthalpy

    @compute_once_lock(SensorType.HUMIDITY_RATIO)
    async def humidity_ratio(self) -> float | tuple[float, dict]:
        """Humidity ratio in g of water vapor per kg of dry air.

        The relative humidity is taken over water also below 0 °C, as the
        sensors and the weather services report it.
        """
        patm = self._actual_pressure()  # Pa
        ratio = (
            _humidity_ratio(self._temperature, self._humidity, patm, over_water=True)
            * 1000
        )
        if self._pressure_entity:
            # Show the pressure in use, only where a sensor was configured
            return ratio, {ATTR_PRESSURE: patm / 100}
        return ratio

    @compute_once_lock(SensorType.VAPOR_PRESSURE_DEFICIT)
    async def vapor_pressure_deficit(self) -> tuple[float, dict]:
        """Vapor pressure deficit of the air in kPa."""
        deficit, vapor_pressure, saturation = _vapor_pressure_deficit(
            self._temperature, self._humidity
        )
        return deficit, {
            ATTR_VAPOR_PRESSURE: round(vapor_pressure, 3),
            ATTR_SATURATION_VAPOR_PRESSURE: round(saturation, 3),
        }

    @compute_once_lock(SensorType.WET_BULB_TEMPERATURE)
    async def wet_bulb_temperature(self) -> float:
        """Wet-bulb temperature <https://doi.org/10.1175/JAMC-D-11-0143.1>.

        Stull (2011), valid for 5 to 99 % relative humidity and -20 to 50 °C
        at sea level pressure. Outside that range the formula can exceed the
        air temperature or fall below the dew point, so the result is limited
        to the physically possible range.
        """
        tw = (
            self._temperature
            * math.atan(0.151977 * pow(self._humidity + 8.313659, 1 / 2))
            + math.atan(self._temperature + self._humidity)
            - math.atan(self._humidity - 1.676331)
            + 0.00391838 * pow(self._humidity, 3 / 2)
            * math.atan(0.023101 * self._humidity)
            - 4.686035
        )
        dewpoint = await self.dew_point()
        return min(max(tw, dewpoint), self._temperature)

    @compute_once_lock(SensorType.THOMS_DISCOMFORT_INDEX)
    async def thoms_discomfort_index(self) -> (float, dict):
        """Thom's discomfort index <https://thermofeel.readthedocs.io/en/2.3.0/guide/discomfortindex/>.

        The relative humidity form, to which the perception categories belong.
        The Epstein-Moran form <https://doi.org/10.2486/indhealth.44.388>,
        the mean of the air and the wet-bulb temperature, is an attribute.
        """
        tdi = (
            self._temperature
            - 0.55 * (1 - 0.01 * self._humidity) * (self._temperature - 14.5)
        )
        tw = await self.wet_bulb_temperature()
        epstein_moran = 0.5 * tw + 0.5 * self._temperature
        return tdi, {ATTR_EPSTEIN_MORAN_DISCOMFORT_INDEX: round(epstein_moran, 2)}

    @compute_once_lock(SensorType.THOMS_DISCOMFORT_PERCEPTION)
    async def thoms_discomfort_perception(self) -> (ThomsDiscomfortPerception, dict):
        """Thom's discomfort perception, the categories belong to the relative humidity form."""
        tdi, _ = await self.thoms_discomfort_index()

        if tdi >= 32:
            perception = ThomsDiscomfortPerception.DANGEROUS
        elif tdi >= 29:
            perception = ThomsDiscomfortPerception.EVERYONE
        elif tdi >= 27:
            perception = ThomsDiscomfortPerception.MOST
        elif tdi >= 24:
            perception = ThomsDiscomfortPerception.MORE_THAN_HALF
        elif tdi >= 21:
            perception = ThomsDiscomfortPerception.LESS_THAN_HALF
        else:
            perception = ThomsDiscomfortPerception.NO_DISCOMFORT

        return perception, {ATTR_THOMS_DISCOMFORT_INDEX: round(tdi, 2)}

    @compute_once_lock(SensorType.MOISTURE_EXCESS)
    async def moisture_excess(self) -> (float, dict):
        """Moisture excess, the absolute humidity indoors above the one outdoors.

        <https://www.folkhalsomyndigheten.se/contentassets/641784832543443ea4eebe9b300c244e/fohmfs-2014-18.pdf>
        """
        indoor = await self.absolute_humidity()
        if indoor is None or not self.outdoor_available:
            return None
        outdoor = _absolute_humidity(self._outdoor_temperature, self._outdoor_humidity)
        # The vapor pressure stays when the outdoor air is warmed to the indoor
        # temperature, the relative humidity changes with the saturation
        ventilated = (
            self._outdoor_humidity
            * _saturation_vapor_pressure(self._outdoor_temperature)
            / _saturation_vapor_pressure(self._temperature)
        )
        return indoor - outdoor, {
            ATTR_OUTDOOR_TEMPERATURE: self._outdoor_temperature,
            ATTR_OUTDOOR_HUMIDITY: self._outdoor_humidity,
            ATTR_OUTDOOR_ABSOLUTE_HUMIDITY: round(outdoor, 2),
            ATTR_OUTDOOR_DEW_POINT: round(
                _dew_point(self._outdoor_temperature, self._outdoor_humidity), 2
            ),
            # The advice follows this value, so they never disagree
            ATTR_VENTILATED_RELATIVE_HUMIDITY: round(min(ventilated, 100.0), 2),
        }

    @compute_once_lock(SensorType.VENTILATION_ADVICE)
    async def ventilation_advice(self) -> (VentilationAdvice, dict):
        """Compare the humidity of the room with the one it would have after airing."""
        result = await self.moisture_excess()
        if result is None:
            return None
        excess, attributes = result
        if attributes[ATTR_VENTILATED_RELATIVE_HUMIDITY] >= CONDENSATION_RH_LIMIT:
            advice = VentilationAdvice.CONDENSATION_RISK
        elif excess > VENTILATION_BAND:
            advice = VentilationAdvice.DRIER_OUTSIDE
        elif excess < -VENTILATION_BAND:
            advice = VentilationAdvice.MORE_HUMID_OUTSIDE
        else:
            advice = VentilationAdvice.SIMILAR
        return advice, self._outdoor_attributes(attributes)

    @compute_once_lock(SensorType.VENTILATION_NEED)
    async def ventilation_need(self) -> (VentilationNeed, dict):
        """Compare the moisture excess with the limit for winter."""
        result = await self.moisture_excess()
        if result is None:
            return None
        excess, attributes = result
        if attributes[ATTR_OUTDOOR_TEMPERATURE] >= VENTILATION_NEED_MAX_OUTDOOR_TEMPERATURE:
            need = VentilationNeed.NOT_WINTER
        elif excess > VENTILATION_NEED_LIMIT:
            need = VentilationNeed.ABOVE_LIMIT
        else:
            need = VentilationNeed.WITHIN_LIMIT
        return need, self._outdoor_attributes(attributes)

    @compute_once_lock(SensorType.WIND_CHILL)
    async def wind_chill(self) -> tuple[float, dict]:
        """Wind chill temperature of Environment Canada and the NWS (JAG/TI 2001)."""
        speed = self._wind_speed * 3.6  # km/h
        return _wind_chill(self._temperature, speed), self._wind_attributes()

    @compute_once_lock(SensorType.APPARENT_TEMPERATURE)
    async def apparent_temperature(self) -> tuple[float, dict]:
        """Apparent temperature of Steadman (1994) without radiation, as the BoM uses it."""
        value = _apparent_temperature(
            self._temperature, self._humidity, self._wind_speed
        )
        return value, self._wind_attributes()

    @staticmethod
    def _outdoor_attributes(attributes: dict) -> dict:
        """Return the attributes of the outdoor air that all its sensors have."""
        return {
            key: attributes[key]
            for key in (ATTR_OUTDOOR_TEMPERATURE, ATTR_OUTDOOR_HUMIDITY)
        }

    async def async_update(self):
        """Update the state."""
        available = self.available
        if available:
            for sensor_type in SENSOR_TYPES:
                self._compute_states[sensor_type].needs_update = True
        wind_available = self.type_available(WIND_SENSOR_TYPES[0])
        # Polling devices refresh on the timer, but not when availability changes
        if not self._should_poll or available != self._was_available:
            await self.async_update_sensors(True)
        elif wind_available != self._was_wind_available:
            # The wind speed of a source of the temperature or the humidity
            self._schedule_wind_sensors()
        self._was_available = available
        self._was_outdoor_available = self.type_available(OUTDOOR_SENSOR_TYPES[0])
        self._was_wind_available = wind_available

    async def async_update_sensors(self, force_refresh: bool = False) -> None:
        """Update the state of the sensors."""
        for sensor in self.sensors:
            sensor.async_schedule_update_ha_state(force_refresh)

    @property
    def available(self) -> bool:
        """Return True if both source values are valid."""
        return self._temperature is not None and self._humidity is not None

    @property
    def compute_states(self) -> dict[SensorType, ComputeState]:
        """Compute states of configured sensors."""
        return self._compute_states

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        return self._unique_id

    @property
    def device_info(self) -> dict:
        """Return the device info."""
        return self._device_info

    @property
    def name(self) -> str:
        """Return the name."""
        return self._device_info["name"]


def _attribute_temperature_unit(hass: HomeAssistant, state) -> str:
    """Return the unit of a temperature that is an attribute of a source state."""
    for unit in (
        state.attributes.get(ATTR_TEMPERATURE_UNIT),
        # The unit of the state does not have to be a temperature unit
        state.attributes.get(ATTR_UNIT_OF_MEASUREMENT),
    ):
        if isinstance(unit, str) and unit in TemperatureConverter.VALID_UNITS:
            return unit
    return hass.config.units.temperature_unit


def _parse_temperature(
    hass: HomeAssistant, state, attribute: str | None
) -> tuple[float | None, float | None]:
    """Return the temperature of a source state in C and the value it has.

    :param attribute: the attribute that has the value, None for the state
    :returns: the temperature in C, None if it is unusable, and the value as the
        source has it, in its unit
    """
    temperature = None
    value = None
    if attribute is None:
        if _is_valid_state(state):
            unit = state.attributes.get(
                ATTR_UNIT_OF_MEASUREMENT, hass.config.units.temperature_unit
            )
            value = util.convert(state.state, float)
    else:
        value = _attribute_value(state, attribute)
        if value is not None:
            unit = _attribute_temperature_unit(hass, state)
    if value is not None:
        # convert to celsius if necessary
        with contextlib.suppress(HomeAssistantError):
            temperature = TemperatureConverter.convert(
                value, unit, UnitOfTemperature.CELSIUS
            )
        if temperature is not None and not -89.2 <= temperature <= 56.7:
            temperature = None
    return temperature, value


def _parse_humidity(state, attribute: str | None) -> float | None:
    """Return the relative humidity of a source state, None if it is unusable."""
    humidity = None
    if attribute is None:
        if _is_valid_state(state):
            humidity = float(state.state)
    else:
        humidity = _attribute_value(state, attribute)
    if humidity is not None:
        if 100 < humidity <= HUMIDITY_MAX_OVERSHOOT:
            humidity = 100.0
        if not 0 < humidity <= 100:
            humidity = None
    return humidity


def _saturation_vapor_pressure(temperature: float) -> float:
    """Return the saturation vapor pressure in hPa (Magnus)."""
    return 6.112 * math.exp((17.67 * temperature) / (243.5 + temperature))


def _saturation_vapor_pressure_ashrae(temperature: float, over_water: bool = False) -> float:
    """Return the saturation vapor pressure in Pa (ASHRAE fundamentals 2021 pg 1.5).

    Over ice below 0 °C (eq 5), over water otherwise (eq 6) or always with
    over_water.
    """
    c1 = -5.6745359e03
    c2 = 6.3925247e00
    c3 = -9.6778430e-03
    c4 = 6.2215701e-07
    c5 = 2.0747825e-09
    c6 = -9.4840240e-13
    c7 = 4.1635019e00
    c8 = -5.8002206e03
    c9 = 1.3914993e00
    c10 = -4.8640239e-02
    c11 = 4.1764768e-05
    c12 = -1.4452093e-08
    c13 = 6.5459673e00

    c_to_k = 273.15
    T = temperature + c_to_k
    if c_to_k > T and not over_water:
        return math.exp(c1 / T + c2 + c3 * T + c4 * T**2 + c5 * T**3 + c6 * T**4 + c7 * math.log(T))
    return math.exp(c8 / T + c9 + c10 * T + c11 * T**2 + c12 * T**3 + c13 * math.log(T))


def _humidity_ratio(temperature: float, humidity: float, pressure: float, over_water: bool = False) -> float:
    """Return the humidity ratio in kg of water vapor per kg of dry air.

    The pressure is in Pa. The denominator stays positive within the input
    ranges (the vapor pressure is at most 17 kPa at 56.7 °C, the pressure is
    limited to 30 kPa and up).
    """
    p_ws = _saturation_vapor_pressure_ashrae(temperature, over_water)

    # calculate vapor pressure for RH % (ASHRAE fundamentals 2021 pg 1.9 eq 22)
    p_w = humidity / 100 * p_ws

    # calculate humidity ratio (ASHRAE fundamentals 2021 pg 1.9 eq 20)
    return 0.621945 * p_w / (pressure - p_w)


def _vapor_pressure_deficit(
    temperature: float, humidity: float, leaf_temperature: float | None = None
) -> tuple[float, float, float]:
    """Return the vapor pressure deficit, the vapor pressure and the saturation vapor pressure in kPa.

    The deficit is the saturation vapor pressure at the leaf temperature
    minus the vapor pressure of the air. Without a leaf temperature it is the
    deficit of the air itself. The pressures are over water.
    """
    saturation = _saturation_vapor_pressure_ashrae(temperature, over_water=True) / 1000
    vapor_pressure = humidity / 100 * saturation
    if leaf_temperature is None:
        leaf_saturation = saturation
    else:
        leaf_saturation = _saturation_vapor_pressure_ashrae(leaf_temperature, over_water=True) / 1000
    return leaf_saturation - vapor_pressure, vapor_pressure, saturation


def _wind_chill(temperature: float, wind_speed: float) -> float:
    """Return the wind chill temperature in C <https://www.weather.gov/media/epz/wxcalc/windChill.pdf>.

    The formula of JAG/TI (2001), with the temperature in C and the wind speed
    in km/h at 10 m. It is valid up to 10 C and above 4.8 km/h, otherwise the
    air temperature is returned.
    """
    if (
        temperature > WIND_CHILL_MAX_TEMPERATURE
        or wind_speed <= WIND_CHILL_MIN_WIND_SPEED
    ):
        return temperature
    factor = pow(wind_speed, 0.16)
    return 13.12 + 0.6215 * temperature - 11.37 * factor + 0.3965 * temperature * factor


def _apparent_temperature(temperature: float, humidity: float, wind_speed: float) -> float:
    """Return the apparent temperature in C <http://www.bom.gov.au/info/thermal_stress/>.

    Steadman (1994) without the radiation, with the temperature in C, the
    relative humidity in % and the wind speed in m/s at 10 m.
    """
    vapor_pressure = (
        humidity / 100 * 6.105 * math.exp(17.27 * temperature / (237.7 + temperature))
    )
    return temperature + 0.33 * vapor_pressure - 0.70 * wind_speed - 4.00


def _absolute_humidity(temperature: float, humidity: float) -> float:
    """Absolute Humidity <https://carnotcycle.wordpress.com/2012/08/04/how-to-convert-relative-humidity-to-absolute-humidity/>."""
    abs_temperature = temperature + 273.15
    abs_humidity = _saturation_vapor_pressure(temperature)
    abs_humidity *= humidity
    abs_humidity *= 2.1674
    abs_humidity /= abs_temperature
    return abs_humidity


def _dew_point(temperature: float, humidity: float) -> float:
    """Dew Point <http://wahiduddin.net/calc/density_algorithms.htm>."""
    A0 = 373.15 / (273.15 + temperature)
    SUM = -7.90298 * (A0 - 1)
    SUM += 5.02808 * math.log(A0, 10)
    SUM += -1.3816e-7 * (pow(10, (11.344 * (1 - 1 / A0))) - 1)
    SUM += 8.1328e-3 * (pow(10, (-3.49149 * (A0 - 1))) - 1)
    SUM += math.log(1013.246, 10)
    VP = pow(10, SUM - 3) * humidity
    Td = math.log(VP / 0.61078)
    Td = (241.88 * Td) / (17.558 - Td)
    return Td


def source_attribute(
    entity_id: str, configured: str | None, defaults: dict[str, str]
) -> str | None:
    """Return the attribute of a source entity that has the value.

    :param entity_id: the source entity
    :param configured: the attribute configured by the user
    :param defaults: attribute by domain for the entities, that have the value
        in an attribute
    :returns: the attribute, None if the value is the state of the entity
    """
    if isinstance(configured, str) and configured.strip():
        return configured.strip()
    return defaults.get((entity_id or "").split(".", 1)[0])


def _attribute_value(state, attribute: str) -> float | None:
    """Return the value of an attribute of a source state, None if unusable."""
    # The attributes of an unavailable entity are gone, an unknown state (a
    # weather without a condition) can still have them
    if state is None or state.state == STATE_UNAVAILABLE:
        return None
    value = state.attributes.get(attribute)
    if isinstance(value, bool):
        return None
    try:
        value = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return value if math.isfinite(value) else None


def _is_valid_state(state) -> bool:
    if state is not None:
        if state.state not in (STATE_UNKNOWN, STATE_UNAVAILABLE):
            try:
                return not math.isnan(float(state.state))
            except ValueError:
                pass
    return False
