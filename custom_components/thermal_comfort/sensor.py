"""Sensor platform for thermal_comfort."""
from asyncio import Lock
from dataclasses import dataclass
from datetime import timedelta
from functools import wraps
import logging
import math
from typing import Any

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
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_TEMPERATURE,
    ATTR_UNIT_OF_MEASUREMENT,
    CONF_ENTITY_PICTURE_TEMPLATE,
    CONF_FRIENDLY_NAME,
    CONF_ICON_TEMPLATE,
    CONF_NAME,
    CONF_SENSORS,
    CONF_UNIQUE_ID,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    TEMP_CELSIUS,
    TEMP_FAHRENHEIT,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import TemplateError
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import DeviceInfo, async_generate_entity_id
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import (
    async_track_state_change_event,
    async_track_time_interval,
)
from homeassistant.helpers.template import Template
from homeassistant.loader import async_get_custom_components
import voluptuous as vol

from .const import DEFAULT_NAME, DOMAIN

_LOGGER = logging.getLogger(__name__)

ATTR_HUMIDITY = "humidity"
ATTR_FROST_RISK_LEVEL = "frost_risk_level"
CONF_ENABLED_SENSORS = "enabled_sensors"
CONF_SENSOR_TYPES = "sensor_types"
CONF_CUSTOM_ICONS = "custom_icons"
CONF_SCAN_INTERVAL = "scan_interval"

CONF_TEMPERATURE_SENSOR = "temperature_sensor"
CONF_HUMIDITY_SENSOR = "humidity_sensor"
CONF_POLL = "poll"
# Default values
POLL_DEFAULT = False
SCAN_INTERVAL_DEFAULT = 30


class ThermalComfortDeviceClass(StrEnum):
    """State class for thermal comfort sensors."""

    FROST_RISK = "thermal_comfort__frost_risk"
    SIMMER_ZONE = "thermal_comfort__simmer_zone"
    THERMAL_PERCEPTION = "thermal_comfort__thermal_perception"


# Deprecate shortform in 2.0
class SensorType(StrEnum):
    """Sensor type enum."""

    ABSOLUTE_HUMIDITY = "absolute_humidity"
    DEW_POINT = "dew_point"
    FROST_POINT = "frost_point"
    FROST_RISK = "frost_risk"
    HEAT_INDEX = "heat_index"
    SIMMER_INDEX = "simmer_index"
    SIMMER_ZONE = "simmer_zone"
    THERMAL_PERCEPTION = "thermal_perception"

    def to_title(self) -> str:
        """Return the title of the sensor type."""
        return self.value.replace("_", " ").title()

    def to_shortform(self) -> str:
        """Return the shortform of the sensor type."""
        if self.value == "thermal_perception":
            return "perception"
        else:
            return self.value.replace("_", "")

    @classmethod
    def from_string(cls, string: str) -> "SensorType":
        """Return the sensor type from string."""
        if string in list(cls):
            return cls(string)
        else:
            _LOGGER.warning(
                "Sensor type shortform and legacy YAML will be removed in 2.0. You should update to the new yaml format: https://github.com/dolezsa/thermal_comfort/blob/master/documentation/yaml.md"
            )
            if string == "absolutehumidity":
                return cls.ABSOLUTE_HUMIDITY
            elif string == "dewpoint":
                return cls.DEW_POINT
            elif string == "frostpoint":
                return cls.FROST_POINT
            elif string == "frostrisk":
                return cls.FROST_RISK
            elif string == "heatindex":
                return cls.HEAT_INDEX
            elif string == "simmerindex":
                return cls.SIMMER_INDEX
            elif string == "simmerzone":
                return cls.SIMMER_ZONE
            elif string == "perception":
                return cls.THERMAL_PERCEPTION
            else:
                raise ValueError(f"Unknown sensor type: {string}")


SENSOR_TYPES = {
    SensorType.ABSOLUTE_HUMIDITY: {
        "key": SensorType.ABSOLUTE_HUMIDITY,
        "device_class": SensorDeviceClass.HUMIDITY,
        "native_unit_of_measurement": "g/m³",
        "state_class": SensorStateClass.MEASUREMENT,
        "icon": "mdi:water",
    },
    SensorType.DEW_POINT: {
        "key": SensorType.DEW_POINT,
        "device_class": SensorDeviceClass.TEMPERATURE,
        "native_unit_of_measurement": TEMP_CELSIUS,
        "state_class": SensorStateClass.MEASUREMENT,
        "icon": "tc:dew-point",
    },
    SensorType.FROST_POINT: {
        "key": SensorType.FROST_POINT,
        "device_class": SensorDeviceClass.TEMPERATURE,
        "native_unit_of_measurement": TEMP_CELSIUS,
        "state_class": SensorStateClass.MEASUREMENT,
        "icon": "tc:frost-point",
    },
    SensorType.FROST_RISK: {
        "key": SensorType.FROST_RISK,
        "device_class": ThermalComfortDeviceClass.FROST_RISK,
        "icon": "mdi:snowflake-alert",
    },
    SensorType.HEAT_INDEX: {
        "key": SensorType.HEAT_INDEX,
        "device_class": SensorDeviceClass.TEMPERATURE,
        "native_unit_of_measurement": TEMP_CELSIUS,
        "state_class": SensorStateClass.MEASUREMENT,
        "icon": "tc:heat-index",
    },
    SensorType.SIMMER_INDEX: {
        "key": SensorType.SIMMER_INDEX,
        "device_class": SensorDeviceClass.TEMPERATURE,
        "native_unit_of_measurement": TEMP_CELSIUS,
        "state_class": SensorStateClass.MEASUREMENT,
        "icon": "tc:simmer-index",
    },
    SensorType.SIMMER_ZONE: {
        "key": SensorType.SIMMER_ZONE,
        "device_class": ThermalComfortDeviceClass.SIMMER_ZONE,
        "icon": "tc:simmer-zone",
    },
    SensorType.THERMAL_PERCEPTION: {
        "key": SensorType.THERMAL_PERCEPTION,
        "device_class": ThermalComfortDeviceClass.THERMAL_PERCEPTION,
        "icon": "tc:thermal-perception",
    },
}

DEFAULT_SENSOR_TYPES = list(SENSOR_TYPES.keys())

PLATFORM_OPTIONS_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_POLL): cv.boolean,
        vol.Optional(CONF_SCAN_INTERVAL): cv.time_period,
        vol.Optional(CONF_CUSTOM_ICONS): cv.boolean,
        vol.Optional(CONF_SENSOR_TYPES): cv.ensure_list,
    },
    extra=vol.REMOVE_EXTRA,
)

LEGACY_SENSOR_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_TEMPERATURE_SENSOR): cv.entity_id,
        vol.Required(CONF_HUMIDITY_SENSOR): cv.entity_id,
        vol.Optional(CONF_ICON_TEMPLATE): cv.template,
        vol.Optional(CONF_ENTITY_PICTURE_TEMPLATE): cv.template,
        vol.Optional(CONF_FRIENDLY_NAME): cv.string,
        vol.Optional(CONF_UNIQUE_ID): cv.string,
    }
)

SENSOR_SCHEMA = LEGACY_SENSOR_SCHEMA.extend(
    {
        vol.Optional(CONF_NAME): cv.string,
    }
).extend(PLATFORM_OPTIONS_SCHEMA.schema)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_SENSORS): cv.schema_with_slug_keys(SENSOR_SCHEMA),
    }
).extend(PLATFORM_OPTIONS_SCHEMA.schema)


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

    COOL = "cool"
    SLIGHTLY_COOL = "slightly_cool"
    COMFORTABLE = "comfortable"
    SLIGHTLY_WARM = "slightly_warm"
    INCREASING_DISCOMFORT = "increasing_discomfort"
    EXTREMELY_WARM = "extremely_warm"
    DANGER_OF_HEATSTROKE = "danger_of_heatstroke"
    EXTREME_DANGER_OF_HEATSTROKE = "extreme_danger_of_heatstroke"
    CIRCULATORY_COLLAPSE_IMMINENT = "circulatory_collapse_imminent"


def compute_once_lock(sensor_type):
    """Only compute if sensor_type needs update, return just the value otherwise."""

    def wrapper(func):
        @wraps(func)
        async def wrapped(self, *args, **kwargs):
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
            "Legacy YAML configuration support will be removed in 2.0. You should update to the new yaml format: https://github.com/dolezsa/thermal_comfort/blob/master/documentation/yaml.md"
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
        compute_device = DeviceThermalComfort(
            hass=hass,
            name=device_config.get(CONF_NAME),
            unique_id=device_config.get(CONF_UNIQUE_ID),
            temperature_entity=device_config.get(CONF_TEMPERATURE_SENSOR),
            humidity_entity=device_config.get(CONF_HUMIDITY_SENSOR),
            should_poll=device_config.get(CONF_POLL, POLL_DEFAULT),
            scan_interval=device_config.get(
                CONF_SCAN_INTERVAL, timedelta(seconds=SCAN_INTERVAL_DEFAULT)
            ),
        )

        sensors += [
            SensorThermalComfort(
                device=compute_device,
                entity_description=SensorEntityDescription(
                    **SENSOR_TYPES[SensorType.from_string(sensor_type)]
                ),
                icon_template=device_config.get(CONF_ICON_TEMPLATE),
                entity_picture_template=device_config.get(CONF_ENTITY_PICTURE_TEMPLATE),
                sensor_type=SensorType.from_string(sensor_type),
                friendly_name=device_config.get(CONF_FRIENDLY_NAME),
                custom_icons=device_config.get(CONF_CUSTOM_ICONS, False),
            )
            for sensor_type in device_config.get(
                CONF_SENSOR_TYPES, DEFAULT_SENSOR_TYPES
            )
        ]

    async_add_entities(sensors)
    return True


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up entity configured via user interface.

    Called via async_setup_platforms(, SENSOR) from __init__.py
    """
    data = hass.data[DOMAIN][config_entry.entry_id]
    if data.get(CONF_SCAN_INTERVAL) is None:
        hass.data[DOMAIN][config_entry.entry_id][
            CONF_SCAN_INTERVAL
        ] = SCAN_INTERVAL_DEFAULT
        data[CONF_SCAN_INTERVAL] = SCAN_INTERVAL_DEFAULT

    _LOGGER.debug(f"async_setup_entry: {data}")
    compute_device = DeviceThermalComfort(
        hass=hass,
        name=data[CONF_NAME],
        unique_id=f"{config_entry.unique_id}",
        temperature_entity=data[CONF_TEMPERATURE_SENSOR],
        humidity_entity=data[CONF_HUMIDITY_SENSOR],
        should_poll=data[CONF_POLL],
        scan_interval=timedelta(
            seconds=data.get(CONF_SCAN_INTERVAL, SCAN_INTERVAL_DEFAULT)
        ),
    )

    entities: list[SensorThermalComfort] = [
        SensorThermalComfort(
            device=compute_device,
            entity_description=SensorEntityDescription(**SENSOR_TYPES[sensor_type]),
            sensor_type=sensor_type,
            custom_icons=data[CONF_CUSTOM_ICONS],
        )
        for sensor_type in SensorType
    ]
    if CONF_ENABLED_SENSORS in data:
        for entity in entities:
            if entity.entity_description.key not in data[CONF_ENABLED_SENSORS]:
                entity.entity_description.entity_registry_enabled_default = False

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

    def __init__(
        self,
        device: "DeviceThermalComfort",
        sensor_type: SensorType,
        entity_description: SensorEntityDescription,
        icon_template: Template = None,
        entity_picture_template: Template = None,
        friendly_name: str = None,
        custom_icons: bool = False,
    ) -> None:
        """Initialize the sensor."""
        self._device = device
        # TODO deprecate shortform in 2.0
        self._sensor_type = sensor_type
        self.entity_description = entity_description
        if friendly_name is None:
            self.entity_description.name = (
                f"{self._device.name} {self._sensor_type.to_title()}"
            )
        else:
            self.entity_description.name = (
                f"{friendly_name} {self._sensor_type.to_title()}"
            )
        # TODO deprecate shortform in 2.0
        self.entity_id = async_generate_entity_id(
            ENTITY_ID_FORMAT,
            f"{self._device.name}_{self._sensor_type.to_shortform()}",
            hass=self._device.hass,
        )
        if not custom_icons:
            if "tc" in self.entity_description.icon:
                self._attr_icon = None
        self._icon_template = icon_template
        self._entity_picture_template = entity_picture_template
        self._attr_native_value = None
        self._attr_extra_state_attributes = {}
        if self._device.unique_id is not None:
            self._attr_unique_id = id_generator(self._device.unique_id, sensor_type)
        self._attr_should_poll = False

    @property
    def device_info(self) -> dict[str, Any]:
        """Return device information."""
        return self._device.device_info

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

    async def async_update(self):
        """Update the state of the sensor."""
        value = await getattr(self._device, self._sensor_type)()
        if value is None:  # can happen during startup
            return

        if self._sensor_type == SensorType.FROST_RISK:
            self._attr_extra_state_attributes[ATTR_FROST_RISK_LEVEL] = value
            self._attr_native_value = list(FrostRisk)[value]
        else:
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
                        "Could not render %s template %s," " the state is unknown.",
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
        self._temperature = None
        self._humidity = None
        self._should_poll = should_poll
        self.sensors = []
        self._compute_states = {
            sensor_type: ComputeState(lock=Lock())
            for sensor_type in SENSOR_TYPES.keys()
        }

        async_track_state_change_event(
            self.hass, self._temperature_entity, self.temperature_state_listener
        )

        async_track_state_change_event(
            self.hass, self._humidity_entity, self.humidity_state_listener
        )

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
            async_track_time_interval(
                self.hass,
                self.async_update_sensors,
                scan_interval,
            )

    async def _set_version(self):
        self._device_info["sw_version"] = (
            await async_get_custom_components(self.hass)
        )[DOMAIN].version.string

    async def temperature_state_listener(self, event):
        """Handle temperature device state changes."""
        await self._new_temperature_state(event.data.get("new_state"))

    async def _new_temperature_state(self, state):
        if _is_valid_state(state):
            unit = state.attributes.get(ATTR_UNIT_OF_MEASUREMENT)
            temp = util.convert(state.state, float)
            self.extra_state_attributes[ATTR_TEMPERATURE] = temp
            # convert to celsius if necessary
            if unit == TEMP_FAHRENHEIT:
                temp = util.temperature.fahrenheit_to_celsius(temp)
            self._temperature = temp
            await self.async_update()

    async def humidity_state_listener(self, event):
        """Handle humidity device state changes."""
        await self._new_humidity_state(event.data.get("new_state"))

    async def _new_humidity_state(self, state):
        if _is_valid_state(state):
            self._humidity = float(state.state)
            self.extra_state_attributes[ATTR_HUMIDITY] = self._humidity
            await self.async_update()

    @compute_once_lock(SensorType.DEW_POINT)
    async def dew_point(self) -> float:
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

    @compute_once_lock(SensorType.HEAT_INDEX)
    async def heat_index(self) -> float:
        """Heat Index <http://www.wpc.ncep.noaa.gov/html/heatindex_equation.shtml>."""
        fahrenheit = util.temperature.celsius_to_fahrenheit(self._temperature)
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

        return round(util.temperature.fahrenheit_to_celsius(hi), 2)

    @compute_once_lock(SensorType.THERMAL_PERCEPTION)
    async def thermal_perception(self) -> ThermalPerception:
        """Dew Point <https://en.wikipedia.org/wiki/Dew_point>."""
        dewpoint = await self.dew_point()
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

    @compute_once_lock(SensorType.ABSOLUTE_HUMIDITY)
    async def absolute_humidity(self) -> float:
        """Absolute Humidity <https://carnotcycle.wordpress.com/2012/08/04/how-to-convert-relative-humidity-to-absolute-humidity/>."""
        abs_temperature = self._temperature + 273.15
        abs_humidity = 6.112
        abs_humidity *= math.exp(
            (17.67 * self._temperature) / (243.5 + self._temperature)
        )
        abs_humidity *= self._humidity
        abs_humidity *= 2.1674
        abs_humidity /= abs_temperature
        return round(abs_humidity, 2)

    @compute_once_lock(SensorType.FROST_POINT)
    async def frost_point(self) -> float:
        """Frost Point <https://pon.fr/dzvents-alerte-givre-et-calcul-humidite-absolue/>."""
        dewpoint = await self.dew_point()
        T = self._temperature + 273.15
        Td = dewpoint + 273.15
        return round(
            (Td + (2671.02 / ((2954.61 / T) + 2.193665 * math.log(T) - 13.3448)) - T)
            - 273.15,
            2,
        )

    @compute_once_lock(SensorType.FROST_RISK)
    async def frost_risk(self) -> int:
        """Frost Risk Level."""
        thresholdAbsHumidity = 2.8
        absolutehumidity = await self.absolute_humidity()
        frostpoint = await self.frost_point()
        if self._temperature <= 1 and frostpoint <= 0:
            if absolutehumidity <= thresholdAbsHumidity:
                return 1  # Frost unlikely despite the temperature
            else:
                return 3  # high probability of frost
        elif (
            self._temperature <= 4
            and frostpoint <= 0.5
            and absolutehumidity > thresholdAbsHumidity
        ):
            return 2  # Frost probable despite the temperature
        return 0  # No risk of frost

    @compute_once_lock(SensorType.SIMMER_INDEX)
    async def simmer_index(self) -> float:
        """<https://www.vcalc.com/wiki/rklarsen/Summer+Simmer+Index>."""
        fahrenheit = util.temperature.celsius_to_fahrenheit(self._temperature)

        si = (
            1.98
            * (fahrenheit - (0.55 - (0.0055 * self._humidity)) * (fahrenheit - 58.0))
            - 56.83
        )

        if fahrenheit < 70:
            si = fahrenheit

        return round(util.temperature.fahrenheit_to_celsius(si), 2)

    @compute_once_lock(SensorType.SIMMER_ZONE)
    async def simmer_zone(self) -> SimmerZone:
        """<http://summersimmer.com/default.asp>."""
        si = await self.simmer_index()
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
            if not self._should_poll:
                await self.async_update_sensors(True)

    async def async_update_sensors(self, force_refresh: bool = False) -> None:
        """Update the state of the sensors."""
        for sensor in self.sensors:
            sensor.async_schedule_update_ha_state(force_refresh)

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


def _is_valid_state(state) -> bool:
    if state is not None:
        if state.state not in (STATE_UNKNOWN, STATE_UNAVAILABLE):
            try:
                return not math.isnan(float(state.state))
            except ValueError:
                pass
    return False
