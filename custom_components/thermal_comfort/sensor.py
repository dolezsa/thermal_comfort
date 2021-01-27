import logging
from typing import Optional

import voluptuous as vol

from homeassistant import util
from homeassistant.core import callback
from homeassistant.components.sensor import ENTITY_ID_FORMAT, \
    PLATFORM_SCHEMA, DEVICE_CLASSES_SCHEMA
from homeassistant.const import (
    ATTR_FRIENDLY_NAME, ATTR_UNIT_OF_MEASUREMENT, CONF_ICON_TEMPLATE,
    CONF_ENTITY_PICTURE_TEMPLATE, CONF_SENSORS, EVENT_HOMEASSISTANT_START,
    MATCH_ALL, CONF_DEVICE_CLASS, DEVICE_CLASS_TEMPERATURE, STATE_UNKNOWN,
    STATE_UNAVAILABLE, DEVICE_CLASS_HUMIDITY, ATTR_TEMPERATURE, TEMP_FAHRENHEIT,
    CONF_UNIQUE_ID,
)
from homeassistant.exceptions import TemplateError
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity, async_generate_entity_id
from homeassistant.helpers.event import async_track_state_change

import math
from enum import Enum

_LOGGER = logging.getLogger(__name__)

CONF_TEMPERATURE_SENSOR = 'temperature_sensor'
CONF_HUMIDITY_SENSOR = 'humidity_sensor'
CONF_SENSOR_TYPES = 'sensor_types'
ATTR_HUMIDITY = 'humidity'

DEFAULT_SENSOR_TYPES = ["absolutehumidity", "heatindex", "dewpoint", "perception"]

SENSOR_SCHEMA = vol.Schema({
    vol.Required(CONF_TEMPERATURE_SENSOR): cv.entity_id,
    vol.Required(CONF_HUMIDITY_SENSOR): cv.entity_id,
    vol.Optional(CONF_SENSOR_TYPES, default=DEFAULT_SENSOR_TYPES): cv.ensure_list,
    vol.Optional(CONF_ICON_TEMPLATE): cv.template,
    vol.Optional(CONF_ENTITY_PICTURE_TEMPLATE): cv.template,
    vol.Optional(ATTR_FRIENDLY_NAME): cv.string,
    vol.Optional(CONF_UNIQUE_ID): cv.string,
})

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_SENSORS): cv.schema_with_slug_keys(SENSOR_SCHEMA),
})

SENSOR_TYPES = {
    'absolutehumidity': [DEVICE_CLASS_HUMIDITY, 'Absolute Humidity', 'g/m³'],
    'heatindex': [DEVICE_CLASS_TEMPERATURE, 'Heat Index', '°C'],
    'dewpoint': [DEVICE_CLASS_TEMPERATURE, 'Dew Point', '°C'],
    'perception': [None, 'Thermal Perception', None],
}

PERCEPTION_DRY = "dry"
PERCEPTION_VERY_COMFORTABLE = "very_comfortable"
PERCEPTION_COMFORTABLE = "comfortable"
PERCEPTION_DEWPOINT_OK_BUT_HUMID = "ok_but_humid"
PERCEPTION_SOMEWHAT_UNCOMFORTABLE = "somewhat_uncomfortable"
PERCEPTION_QUITE_UNCOMFORTABLE = "quite_uncomfortable"
PERCEPTION_EXTREMELY_UNCOMFORTABLE = "extremely_uncomfortable"
PERCEPTION_SEVERELY_HIGH = "severely_high"

async def async_setup_platform(hass, config, async_add_entities,
                               discovery_info=None):
    """Set up the Thermal Comfort sensors."""
    sensors = []

    for device, device_config in config[CONF_SENSORS].items():
        temperature_entity = device_config.get(CONF_TEMPERATURE_SENSOR)
        humidity_entity = device_config.get(CONF_HUMIDITY_SENSOR)
        config_sensor_types = device_config.get(CONF_SENSOR_TYPES)
        icon_template = device_config.get(CONF_ICON_TEMPLATE)
        entity_picture_template = device_config.get(CONF_ENTITY_PICTURE_TEMPLATE)
        friendly_name = device_config.get(ATTR_FRIENDLY_NAME, device)
        unique_id = device_config.get(CONF_UNIQUE_ID)

        for sensor_type in SENSOR_TYPES:
            if sensor_type in config_sensor_types :
                sensors.append(
                        SensorThermalComfort(
                                hass,
                                device,
                                temperature_entity,
                                humidity_entity,
                                friendly_name,
                                icon_template,
                                entity_picture_template,
                                sensor_type,
                                unique_id,
                        )
                )
    if not sensors:
        _LOGGER.error("No sensors added")
        return False

    async_add_entities(sensors)
    return True


class SensorThermalComfort(Entity):
    """Representation of a Thermal Comfort Sensor."""

    def __init__(self, hass, device_id, temperature_entity, humidity_entity,
                 friendly_name, icon_template, entity_picture_template, sensor_type, unique_id=None):
        """Initialize the sensor."""
        self.hass = hass
        self.entity_id = async_generate_entity_id(ENTITY_ID_FORMAT, "{}_{}".format(device_id, sensor_type), hass=hass)
        self._attr_name = "{} {}".format(friendly_name, SENSOR_TYPES[sensor_type][1])
        self._attr_unit_of_measurement = SENSOR_TYPES[sensor_type][2]
        self._attr_state = None
        self._attr_extra_state_attributes = {}
        self._icon_template = icon_template
        self._entity_picture_template = entity_picture_template
        self._attr_icon = None
        self._attr_entity_picture = None
        self._temperature_entity = temperature_entity
        self._humidity_entity = humidity_entity
        self._attr_device_class = SENSOR_TYPES[sensor_type][0]
        self._sensor_type = sensor_type
        self._temperature = None
        self._humidity = None
        self._attr_unique_id = None
        if unique_id is not None:
            self._attr_unique_id = unique_id + sensor_type
        self._attr_should_poll = False

        temperature_state = hass.states.get(temperature_entity)
        if _is_valid_state(temperature_state):
            self._temperature = float(temperature_state.state)

        humidity_state = hass.states.get(humidity_entity)
        if _is_valid_state(humidity_state):
            self._humidity = float(humidity_state.state)

    def temperature_state_listener(self, entity, old_state, new_state):
        """Handle temperature device state changes."""
        if _is_valid_state(new_state):
            unit = new_state.attributes.get(ATTR_UNIT_OF_MEASUREMENT)
            temp = util.convert(new_state.state, float)
            # convert to celsius if necessary
            if unit == TEMP_FAHRENHEIT:
                temp = util.temperature.fahrenheit_to_celsius(temp)
            self._temperature = temp

        self.async_schedule_update_ha_state(True)

    def humidity_state_listener(self, entity, old_state, new_state):
        """Handle humidity device state changes."""
        if _is_valid_state(new_state):
            self._humidity = float(new_state.state)

        self.async_schedule_update_ha_state(True)

    def computeDewPoint(self, temperature, humidity):
        """http://wahiduddin.net/calc/density_algorithms.htm"""
        A0 = 373.15 / (273.15 + temperature)
        SUM = -7.90298 * (A0 - 1)
        SUM += 5.02808 * math.log(A0, 10)
        SUM += -1.3816e-7 * (pow(10, (11.344 * (1 - 1 / A0))) - 1)
        SUM += 8.1328e-3 * (pow(10, (-3.49149 * (A0 - 1))) - 1)
        SUM += math.log(1013.246, 10)
        VP = pow(10, SUM - 3) * humidity
        Td = math.log(VP / 0.61078)
        Td = (241.88 * Td) / (17.558 - Td)
        return round(Td, 2)

    def toFahrenheit(self, celsius):
        """celsius to fahrenheit"""
        return 1.8 * celsius + 32.0

    def toCelsius(self, fahrenheit):
        """fahrenheit to celsius"""
        return (fahrenheit - 32.0) / 1.8

    def computeHeatIndex(self, temperature, humidity):
        """http://www.wpc.ncep.noaa.gov/html/heatindex_equation.shtml"""
        fahrenheit = self.toFahrenheit(temperature)
        hi = 0.5 * (fahrenheit + 61.0 + ((fahrenheit - 68.0) * 1.2) + (humidity * 0.094));

        if hi > 79:
            hi = -42.379 + 2.04901523 * fahrenheit
            hi = hi + 10.14333127 * humidity
            hi = hi + -0.22475541 * fahrenheit * humidity
            hi = hi + -0.00683783 * pow(fahrenheit, 2)
            hi = hi + -0.05481717 * pow(humidity, 2)
            hi = hi + 0.00122874 * pow(fahrenheit, 2) * humidity
            hi = hi + 0.00085282 * fahrenheit * pow(humidity, 2)
            hi = hi + -0.00000199 * pow(fahrenheit, 2) * pow(humidity, 2);

        if humidity < 13 and fahrenheit >= 80 and fahrenheit <= 112:
            hi = hi - ((13 - humidity) * 0.25) * math.sqrt((17 - abs(fahrenheit - 95)) * 0.05882)
        elif humidity > 85 and fahrenheit >= 80 and fahrenheit <= 87:
            hi = hi + ((humidity - 85) * 0.1) * ((87 - fahrenheit) * 0.2)

        return round(self.toCelsius(hi), 2)

    def computePerception(self, temperature, humidity):
        """https://en.wikipedia.org/wiki/Dew_point"""
        dewPoint = self.computeDewPoint(temperature, humidity)
        if dewPoint < 10:
            return PERCEPTION_DRY
        elif dewPoint < 13:
            return PERCEPTION_VERY_COMFORTABLE
        elif dewPoint < 16:
            return PERCEPTION_COMFORTABLE
        elif dewPoint < 18:
            return PERCEPTION_DEWPOINT_OK_BUT_HUMID
        elif dewPoint < 21:
            return PERCEPTION_SOMEWHAT_UNCOMFORTABLE
        elif dewPoint < 24:
            return PERCEPTION_QUITE_UNCOMFORTABLE
        elif dewPoint < 26:
            return PERCEPTION_EXTREMELY_UNCOMFORTABLE
        return PERCEPTION_SEVERELY_HIGH

    def computeAbsoluteHumidity(self, temperature, humidity):
        """https://carnotcycle.wordpress.com/2012/08/04/how-to-convert-relative-humidity-to-absolute-humidity/"""
        absTemperature = temperature + 273.15;
        absHumidity = 6.112;
        absHumidity *= math.exp((17.67 * temperature) / (243.5 + temperature));
        absHumidity *= humidity;
        absHumidity *= 2.1674;
        absHumidity /= absTemperature;
        return round(absHumidity, 2)

    async def async_added_to_hass(self):
        async_track_state_change(
            self.hass, self._temperature_entity, self.temperature_state_listener)

        async_track_state_change(
            self.hass, self._humidity_entity, self.humidity_state_listener)

    async def async_update(self):
        """Update the state."""
        value = None
        if self._temperature is not None and self._humidity is not None:
            if self._sensor_type == "dewpoint":
                value = self.computeDewPoint(self._temperature, self._humidity)
            if self._sensor_type == "heatindex":
                value = self.computeHeatIndex(self._temperature, self._humidity)
            elif self._sensor_type == "perception":
                value = self.computePerception(self._temperature, self._humidity)
            elif self._sensor_type == "absolutehumidity":
                value = self.computeAbsoluteHumidity(self._temperature, self._humidity)
            elif self._sensor_type == "comfortratio":
                value = "comfortratio"

        self._attr_state = value
        self._attr_extra_state_attributes[ATTR_TEMPERATURE] = self._temperature
        self._attr_extra_state_attributes[ATTR_HUMIDITY] = self._humidity

        for property_name, template in (
                ('_icon', self._icon_template),
                ('_entity_picture', self._entity_picture_template)):
            if template is None:
                continue

            try:
                setattr(self, property_name, template.async_render())
            except TemplateError as ex:
                friendly_property_name = property_name[1:].replace('_', ' ')
                if ex.args and ex.args[0].startswith(
                        "UndefinedError: 'None' has no attribute"):
                    # Common during HA startup - so just a warning
                    _LOGGER.warning('Could not render %s template %s,'
                                    ' the state is unknown.',
                                    friendly_property_name, self._attr_name)
                    continue

                try:
                    setattr(self, property_name,
                            getattr(super(), property_name))
                except AttributeError:
                    _LOGGER.error('Could not render %s template %s: %s',
                                  friendly_property_name, self._attr_name, ex)


def _is_valid_state(state) -> bool:
    return state and state.state != STATE_UNKNOWN and state.state != STATE_UNAVAILABLE and not math.isnan(float(state.state))
