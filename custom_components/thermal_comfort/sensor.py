"""Sensor platform for thermal_comfort."""
from asyncio import Lock
from dataclasses import dataclass
from functools import wraps
import logging
import math

from homeassistant import util
from homeassistant.backports.enum import StrEnum
from homeassistant.components.sensor import (
    ENTITY_ID_FORMAT,
    PLATFORM_SCHEMA,
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    ATTR_TEMPERATURE,
    ATTR_UNIT_OF_MEASUREMENT,
    CONF_ENTITY_PICTURE_TEMPLATE,
    CONF_FRIENDLY_NAME,
    CONF_ICON_TEMPLATE,
    CONF_SENSORS,
    CONF_UNIQUE_ID,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    TEMP_CELSIUS,
    TEMP_FAHRENHEIT,
)
from homeassistant.exceptions import TemplateError
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity, async_generate_entity_id
from homeassistant.helpers.event import async_track_state_change_event
import voluptuous as vol

_LOGGER = logging.getLogger(__name__)

ATTR_HUMIDITY = 'humidity'
ATTR_FROST_RISK_LEVEL = 'frost_risk_level'
CONF_HUMIDITY_SENSOR = 'humidity_sensor'
CONF_POLL = 'poll'
CONF_SENSOR_TYPES = 'sensor_types'
CONF_TEMPERATURE_SENSOR = 'temperature_sensor'

class ThermalComfortDeviceClass(StrEnum):
    """State class for thermal comfort sensors."""
    FROST_RISK = 'thermal_comfort__frost_risk'
    SIMMER_ZONE = 'thermal_comfort__simmer_zone'
    THERMAL_PERCEPTION = 'thermal_comfort__thermal_perception'

class SensorType(StrEnum):
    """Sensor type enum."""
    ABSOLUTEHUMIDITY = 'absolutehumidity'
    DEWPOINT = 'dewpoint'
    FROSTPOINT = 'frostpoint'
    FROSTRISK = 'frostrisk'
    HEATINDEX = 'heatindex'
    SIMMERINDEX = 'simmerindex'
    SIMMERZONE = 'simmerzone'
    THERMALPERCEPTION = 'perception'

SENSOR_TYPES = {
    SensorType.ABSOLUTEHUMIDITY: dict(
        key = SensorType.ABSOLUTEHUMIDITY,
        name = '{} Absolute Humidity',
        device_class = SensorDeviceClass.HUMIDITY,
        native_unit_of_measurement = 'g/m³',
        state_class = SensorStateClass.MEASUREMENT,
    ),
    SensorType.DEWPOINT: dict(
        key = SensorType.DEWPOINT,
        name = '{} Dew Point',
        device_class = SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement = TEMP_CELSIUS,
        state_class = SensorStateClass.MEASUREMENT,
    ),
    SensorType.FROSTPOINT: dict(
        key = SensorType.FROSTPOINT,
        name = '{} Frost Point',
        device_class = SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement = TEMP_CELSIUS,
        state_class = SensorStateClass.MEASUREMENT,
    ),
    SensorType.FROSTRISK: dict(
        key = SensorType.FROSTRISK,
        name = '{} Frost Risk',
        device_class = ThermalComfortDeviceClass.FROST_RISK,
    ),
    SensorType.HEATINDEX: dict(
        key = SensorType.HEATINDEX,
        name = '{} Heat Index',
        device_class = SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement = TEMP_CELSIUS,
        state_class = SensorStateClass.MEASUREMENT,
    ),
    SensorType.SIMMERINDEX: dict(
        key = SensorType.SIMMERINDEX,
        name='{} Simmer Index',
        device_class = SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement = TEMP_CELSIUS,
        state_class = SensorStateClass.MEASUREMENT,
    ),
    SensorType.SIMMERZONE: dict(
        key = SensorType.SIMMERZONE,
        name='{} Simmer Zone',
        device_class = ThermalComfortDeviceClass.SIMMER_ZONE,
    ),
    SensorType.THERMALPERCEPTION: dict(
        key = SensorType.THERMALPERCEPTION,
        name = '{} Thermal Perception',
        device_class = ThermalComfortDeviceClass.THERMAL_PERCEPTION,
    ),
}

DEFAULT_SENSOR_TYPES = list(SENSOR_TYPES.keys())

SENSOR_SCHEMA = vol.Schema({
    vol.Required(CONF_TEMPERATURE_SENSOR): cv.entity_id,
    vol.Required(CONF_HUMIDITY_SENSOR): cv.entity_id,
    vol.Optional(CONF_SENSOR_TYPES, default=DEFAULT_SENSOR_TYPES): cv.ensure_list,
    vol.Optional(CONF_ICON_TEMPLATE): cv.template,
    vol.Optional(CONF_ENTITY_PICTURE_TEMPLATE): cv.template,
    vol.Optional(CONF_FRIENDLY_NAME): cv.string,
    vol.Optional(CONF_UNIQUE_ID): cv.string,
})

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_SENSORS): cv.schema_with_slug_keys(SENSOR_SCHEMA),
    vol.Optional(CONF_POLL, default=False): cv.boolean,
})

class ThermalPerception(StrEnum):
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

class SimmerZone(StrEnum):
    """Simmer Zone."""
    COOL= 'cool'
    SLIGHTLY_COOL = 'slightly_cool'
    COMFORTABLE = 'comfortable'
    SLIGHTLY_WARM = 'slightly_warm'
    INCREASING_DISCOMFORT = 'increasing_discomfort'
    EXTREMELY_WARM = 'extremely_warm'
    DANGER_OF_HEATSTROKE = 'danger_of_heatstroke'
    EXTREME_DANGER_OF_HEATSTROKE = 'extreme_danger_of_heatstroke'
    CIRCULATORY_COLLAPSE_IMMINENT = 'circulatory_collapse_imminent'


def compute_once_lock(sensor_type):
    def wrapper(func):
        @wraps(func)
        async def wrapped(self, *args, **kwargs):
            async with self._compute_states[sensor_type].lock:
                if self._compute_states[sensor_type].needs_update:
                    setattr(self, f'_{sensor_type}', await func(self, *args, **kwargs))
                    self._compute_states[sensor_type].needs_update = False
                return getattr(self, f'_{sensor_type}')
        return wrapped
    return wrapper


async def async_setup_platform(hass, config, async_add_entities,
                               discovery_info=None):
    """Set up the Thermal Comfort sensors."""
    sensors = []

    should_poll = config.get(CONF_POLL)
    for device, device_config in config[CONF_SENSORS].items():
        temperature_entity = device_config.get(CONF_TEMPERATURE_SENSOR)
        humidity_entity = device_config.get(CONF_HUMIDITY_SENSOR)
        sensor_types = device_config.get(CONF_SENSOR_TYPES)
        icon_template = device_config.get(CONF_ICON_TEMPLATE)
        entity_picture_template = device_config.get(CONF_ENTITY_PICTURE_TEMPLATE)
        friendly_name = device_config.get(CONF_FRIENDLY_NAME, device)
        unique_id = device_config.get(CONF_UNIQUE_ID)

        compute_device = DeviceThermalComfort(
            hass,
            temperature_entity,
            humidity_entity,
            sensor_types,
            should_poll,
        )

        for sensor_type in sensor_types:
            sensors.append(
                SensorThermalComfort(
                    compute_device,
                    device,
                    friendly_name,
                    SensorEntityDescription(**SENSOR_TYPES[sensor_type]),
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


class SensorThermalComfort(SensorEntity):
    """Representation of a Thermal Comfort Sensor."""
    def __init__(self, device, device_id, friendly_name, entity_description, icon_template, entity_picture_template, sensor_type, unique_id):
        self._device = device
        self.entity_description = entity_description
        self.entity_description.name = entity_description.name.format(friendly_name)
        self.entity_id = async_generate_entity_id(ENTITY_ID_FORMAT, f"{device_id}_{sensor_type}", hass=device.hass)
        self._icon_template = icon_template
        self._entity_picture_template = entity_picture_template
        self._attr_icon = None
        self._attr_entity_picture = None
        self._sensor_type = sensor_type
        self._attr_native_value = None
        self._attr_extra_state_attributes = {}
        if unique_id is not None:
            self._attr_unique_id = unique_id + sensor_type
        self._attr_should_poll = self._device.should_poll

    @property
    def extra_state_attributes(self):
        return dict(self._device.extra_state_attributes, **self._attr_extra_state_attributes)

    async def async_added_to_hass(self):
        """Register callbacks."""
        self._device.sensors.append(self)

    async def async_update(self):
        """Update the state of the sensor."""
        if self._sensor_type == SensorType.FROSTRISK:
            level = await getattr(self._device, self._sensor_type)()
            self._attr_extra_state_attributes[ATTR_FROST_RISK_LEVEL] = level
            self._attr_native_value = list(FrostRisk)[level]
        else:
            self._attr_native_value = await getattr(self._device, self._sensor_type)()

        for property_name, template in (
                ('_attr_icon', self._icon_template),
                ('_attr_entity_picture', self._entity_picture_template)):
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
                                    friendly_property_name, self.name)
                    continue

                try:
                    setattr(self, property_name,
                            getattr(super(), property_name))
                except AttributeError:
                    _LOGGER.error('Could not render %s template %s: %s',
                                  friendly_property_name, self.name, ex)


@dataclass
class ComputeState():
    """Thermal Comfort Calculation State."""
    needs_update: bool = True
    lock: Lock = None


class DeviceThermalComfort():
    """Representation of a Thermal Comfort Sensor."""
    def __init__(self,
            hass,
            temperature_entity,
            humidity_entity,
            sensor_types,
            should_poll,
    ):
        """Initialize the sensor."""
        self.hass = hass
        self.extra_state_attributes = {}
        self._temperature_entity = temperature_entity
        self._humidity_entity = humidity_entity
        self._temperature = None
        self._humidity = None
        self._sensor_types = sensor_types
        self.should_poll = should_poll
        self.sensors = []
        self._compute_states = { sensor_type: ComputeState(lock=Lock()) for sensor_type in SENSOR_TYPES.keys() }

        temperature_state = hass.states.get(temperature_entity)
        if _is_valid_state(temperature_state):
            self._temperature = float(temperature_state.state)

        humidity_state = hass.states.get(humidity_entity)
        if _is_valid_state(humidity_state):
            self._humidity = float(humidity_state.state)

        async_track_state_change_event(
            self.hass, self._temperature_entity, self.temperature_state_listener)

        async_track_state_change_event(
            self.hass, self._humidity_entity, self.humidity_state_listener)

    async def temperature_state_listener(self, event):
        """Handle temperature device state changes."""
        new_state = event.data.get("new_state")
        if _is_valid_state(new_state):
            unit = new_state.attributes.get(ATTR_UNIT_OF_MEASUREMENT)
            temp = util.convert(new_state.state, float)
            # convert to celsius if necessary
            if unit == TEMP_FAHRENHEIT:
                temp = util.temperature.fahrenheit_to_celsius(temp)
            self._temperature = temp
            self.extra_state_attributes[ATTR_TEMPERATURE] = self._temperature
            await self.async_update()

    async def humidity_state_listener(self, event):
        """Handle humidity device state changes."""
        new_state = event.data.get("new_state")
        if _is_valid_state(new_state):
            self._humidity = float(new_state.state)
            self.extra_state_attributes[ATTR_HUMIDITY] = self._humidity
            await self.async_update()

    @compute_once_lock(SensorType.DEWPOINT)
    async def dewpoint(self):
        """Dew Point <http://wahiduddin.net/calc/density_algorithms.htm>."""
        A0 = 373.15 / (273.15 + self._temperature)
        SUM = -7.90298 * (A0 - 1)
        SUM += 5.02808 * math.log(A0, 10)
        SUM += -1.3816e-7 * (pow(10, (11.344 * (1 - 1 / A0))) - 1)
        SUM += 8.1328e-3 * (pow(10, (-3.49149 * (A0 - 1))) - 1)
        SUM += math.log(1013.246, 10)
        VP = pow(10, SUM - 3) * self._humidity
        Td = math.log(VP / 0.61078)
        Td = (241.88 * Td) / (17.558 - Td)
        return round(Td, 2)

    @compute_once_lock(SensorType.HEATINDEX)
    async def heatindex(self):
        """Heat Index <http://www.wpc.ncep.noaa.gov/html/heatindex_equation.shtml>."""
        fahrenheit = util.temperature.celsius_to_fahrenheit(self._temperature)
        hi = 0.5 * (fahrenheit + 61.0 + ((fahrenheit - 68.0) * 1.2) + (self._humidity * 0.094))

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
            hi = hi - ((13 - self._humidity) * 0.25) * math.sqrt((17 - abs(fahrenheit - 95)) * 0.05882)
        elif self._humidity > 85 and fahrenheit >= 80 and fahrenheit <= 87:
            hi = hi + ((self._humidity - 85) * 0.1) * ((87 - fahrenheit) * 0.2)

        return round(util.temperature.fahrenheit_to_celsius(hi), 2)

    @compute_once_lock(SensorType.THERMALPERCEPTION)
    async def perception(self):
        """Dew Point <https://en.wikipedia.org/wiki/Dew_point>."""
        dewpoint = await self.dewpoint()
        if dewpoint < 10:
            return ThermalPerception.DRY
        elif dewpoint < 13:
            return ThermalPerception.VERY_COMFORTABLE
        elif dewpoint < 16:
            return ThermalPerception.COMFORTABLE
        elif dewpoint < 18:
            return ThermalPerception.OK_BUT_HUMID
        elif dewpoint < 21:
            return ThermalPerception.SOMEWHAT_UNCOMFORTABLE
        elif dewpoint < 24:
            return ThermalPerception.QUITE_UNCOMFORTABLE
        elif dewpoint < 26:
            return ThermalPerception.EXTREMELY_UNCOMFORTABLE
        else:
            return ThermalPerception.SEVERELY_HIGH

    @compute_once_lock(SensorType.ABSOLUTEHUMIDITY)
    async def absolutehumidity(self):
        """Absolute Humidity <https://carnotcycle.wordpress.com/2012/08/04/how-to-convert-relative-humidity-to-absolute-humidity/>."""
        abs_temperature = self._temperature + 273.15
        abs_humidity = 6.112
        abs_humidity *= math.exp((17.67 * self._temperature) / (243.5 + self._temperature))
        abs_humidity *= self._humidity
        abs_humidity *= 2.1674
        abs_humidity /= abs_temperature
        return round(abs_humidity,2)

    @compute_once_lock(SensorType.FROSTPOINT)
    async def frostpoint(self):
        """Frost Point <https://pon.fr/dzvents-alerte-givre-et-calcul-humidite-absolue/>."""
        dewpoint = await self.dewpoint()
        T = self._temperature + 273.15
        Td = dewpoint + 273.15
        return round((Td + (2671.02 / ((2954.61 / T) + 2.193665 * math.log(T) - 13.3448)) - T) - 273.15, 2)

    @compute_once_lock(SensorType.FROSTRISK)
    async def frostrisk(self):
        """Frost Risk Level."""
        thresholdAbsHumidity = 2.8
        absolutehumidity = await self.absolutehumidity()
        frostpoint = await self.frostpoint()
        if self._temperature <= 1 and frostpoint <= 0:
            if absolutehumidity <= thresholdAbsHumidity:
                return 1  # Frost unlikely despite the temperature
            else:
                return 3  # high probability of frost
        elif self._temperature <= 4 and frostpoint <= 0.5 and absolutehumidity > thresholdAbsHumidity:
            return 2  # Frost probable despite the temperature
        return 0  # No risk of frost

    @compute_once_lock(SensorType.SIMMERINDEX)
    async def simmerindex(self):
        """https://www.vcalc.com/wiki/rklarsen/Summer+Simmer+Index"""
        fahrenheit = util.temperature.celsius_to_fahrenheit(self._temperature)

        si = (1.98 * (fahrenheit - (0.55 - (0.0055 * self._humidity)) * (fahrenheit - 58.0)) - 56.83)

        if fahrenheit < 70:
            si = fahrenheit

        return round(util.temperature.fahrenheit_to_celsius(si), 2)

    @compute_once_lock(SensorType.SIMMERZONE)
    async def simmerzone(self):
        """http://summersimmer.com/default.asp"""
        si = await self.simmerindex()
        if si < 21.1:
            return SimmerZone.COOL
        elif si < 25.0:
            return SimmerZone.SLIGHTLY_COOL
        elif si < 28.3:
            return SimmerZone.COMFORTABLE
        elif si < 32.8:
            return SimmerZone.SLIGHTLY_WARM
        elif si < 37.8:
            return SimmerZone.INCREASING_DISCOMFORT
        elif si < 44.4:
            return SimmerZone.EXTREMELY_WARM
        elif si < 51.7:
            return SimmerZone.DANGER_OF_HEATSTROKE
        elif si < 65.6:
            return SimmerZone.EXTREME_DANGER_OF_HEATSTROKE
        else:
            return SimmerZone.CIRCULATORY_COLLAPSE_IMMINENT

    async def async_update(self):
        """Update the state."""
        if self._temperature is not None and self._humidity is not None:
            for sensor_type in SENSOR_TYPES.keys():
                self._compute_states[sensor_type].needs_update = True
            if not self.should_poll:
                for sensor in self.sensors:
                    sensor.async_schedule_update_ha_state(True)


def _is_valid_state(state) -> bool:
    if state is not None:
        if state.state not in (STATE_UNKNOWN, STATE_UNAVAILABLE):
            try:
                return not math.isnan(float(state.state))
            except ValueError:
                pass
    return False
