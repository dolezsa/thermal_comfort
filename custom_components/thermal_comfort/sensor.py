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
    DOMAIN as SENSOR_DOMAIN,
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
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import TemplateError
from homeassistant.helpers import entity_registry
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import (
    async_track_state_change_event,
    async_track_time_interval,
)
from homeassistant.helpers.template import Template
from homeassistant.loader import async_get_custom_components
from homeassistant.util.unit_conversion import TemperatureConverter
import voluptuous as vol

from .const import DEFAULT_NAME, DOMAIN

_LOGGER = logging.getLogger(__name__)

ATTR_DEW_POINT = "dew_point"
ATTR_HUMIDITY = "humidity"
ATTR_HUMIDEX = "humidex"
ATTR_FROST_POINT = "frost_point"
ATTR_RELATIVE_STRAIN_INDEX = "relative_strain_index"
ATTR_SUMMER_SCHARLAU_INDEX = "summer_scharlau_index"
ATTR_WINTER_SCHARLAU_INDEX = "winter_scharlau_index"
ATTR_SUMMER_SIMMER_INDEX = "summer_simmer_index"
ATTR_THOMS_DISCOMFORT_INDEX = "thoms_discomfort_index"
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
DISPLAY_PRECISION = 2


class LegacySensorType(StrEnum):
    THERMAL_PERCEPTION = "thermal_perception"
    SIMMER_INDEX = "simmer_index"
    SIMMER_ZONE = "simmer_zone"


class SensorType(StrEnum):
    """Sensor type enum."""

    ABSOLUTE_HUMIDITY = "absolute_humidity"
    DEW_POINT = "dew_point"
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
    DEW_POINT_PERCEPTION = "dew_point_perception"
    THOMS_DISCOMFORT_PERCEPTION = "thoms_discomfort_perception"

    def to_name(self) -> str:
        """Return the title of the sensor type."""
        return self.value.replace("_", " ").capitalize()

    @classmethod
    def from_string(cls, string: str) -> "SensorType":
        """Return the sensor type from string."""
        if string in list(cls):
            return cls(string)
        else:
            raise ValueError(
                f"Unknown sensor type: {string}. Please check https://github.com/dolezsa/thermal_comfort/blob/master/documentation/yaml.md#sensor-options for valid options."
            )


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
    MODERATLY_UNCOMFORTABLE = "moderatly_uncomfortable"
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
    LESS_THEN_HALF = "less_then_half"
    MORE_THEN_HALF = "more_then_half"
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
        "name": SensorType.ABSOLUTE_HUMIDITY.to_name(),
        "suggested_display_precision": DISPLAY_PRECISION,
        "native_unit_of_measurement": "g/m³",
        "state_class": SensorStateClass.MEASUREMENT,
        "icon": "mdi:water",
    },
    SensorType.DEW_POINT: {
        "key": SensorType.DEW_POINT,
        "name": SensorType.DEW_POINT.to_name(),
        "device_class": SensorDeviceClass.TEMPERATURE,
        "suggested_display_precision": DISPLAY_PRECISION,
        "native_unit_of_measurement": UnitOfTemperature.CELSIUS,
        "state_class": SensorStateClass.MEASUREMENT,
        "icon": "mdi:thermometer-water",
    },
    SensorType.FROST_POINT: {
        "key": SensorType.FROST_POINT,
        "name": SensorType.FROST_POINT.to_name(),
        "device_class": SensorDeviceClass.TEMPERATURE,
        "suggested_display_precision": DISPLAY_PRECISION,
        "native_unit_of_measurement": UnitOfTemperature.CELSIUS,
        "state_class": SensorStateClass.MEASUREMENT,
        "icon": "mdi:snowflake-thermometer",
    },
    SensorType.FROST_RISK: {
        "key": SensorType.FROST_RISK,
        "name": SensorType.FROST_RISK.to_name(),
        "device_class": SensorDeviceClass.ENUM,
        "options": list(map(str, FrostRisk)),
        "translation_key": SensorType.FROST_RISK,
        "icon": "mdi:snowflake-alert",
    },
    SensorType.HEAT_INDEX: {
        "key": SensorType.HEAT_INDEX,
        "name": SensorType.HEAT_INDEX.to_name(),
        "device_class": SensorDeviceClass.TEMPERATURE,
        "suggested_display_precision": DISPLAY_PRECISION,
        "native_unit_of_measurement": UnitOfTemperature.CELSIUS,
        "state_class": SensorStateClass.MEASUREMENT,
        "icon": "mdi:sun-thermometer",
    },
    SensorType.HUMIDEX: {
        "key": SensorType.HUMIDEX,
        "name": SensorType.HUMIDEX.to_name(),
        "device_class": SensorDeviceClass.TEMPERATURE,
        "suggested_display_precision": DISPLAY_PRECISION,
        "native_unit_of_measurement": UnitOfTemperature.CELSIUS,
        "state_class": SensorStateClass.MEASUREMENT,
        "icon": "mdi:sun-thermometer",
    },
    SensorType.HUMIDEX_PERCEPTION: {
        "key": SensorType.HUMIDEX_PERCEPTION,
        "name": SensorType.HUMIDEX_PERCEPTION.to_name(),
        "device_class": SensorDeviceClass.ENUM,
        "options": list(map(str, HumidexPerception)),
        "translation_key": SensorType.HUMIDEX_PERCEPTION,
        "icon": "mdi:sun-thermometer",
    },
    SensorType.MOIST_AIR_ENTHALPY: {
        "key": SensorType.MOIST_AIR_ENTHALPY,
        "name": SensorType.MOIST_AIR_ENTHALPY.to_name(),
        "translation_key": SensorType.MOIST_AIR_ENTHALPY,
        "suggested_display_precision": DISPLAY_PRECISION,
        "native_unit_of_measurement": "kJ/kg",
        "state_class": SensorStateClass.MEASUREMENT,
        "icon": "mdi:water-circle",
    },
    SensorType.RELATIVE_STRAIN_PERCEPTION: {
        "key": SensorType.RELATIVE_STRAIN_PERCEPTION,
        "name": SensorType.RELATIVE_STRAIN_PERCEPTION.to_name(),
        "device_class": SensorDeviceClass.ENUM,
        "options": list(map(str, RelativeStrainPerception)),
        "translation_key": SensorType.RELATIVE_STRAIN_PERCEPTION,
        "icon": "mdi:sun-thermometer",
    },
    SensorType.SUMMER_SCHARLAU_PERCEPTION: {
        "key": SensorType.SUMMER_SCHARLAU_PERCEPTION,
        "name": SensorType.SUMMER_SCHARLAU_PERCEPTION.to_name(),
        "device_class": SensorDeviceClass.ENUM,
        "options": list(map(str, ScharlauPerception)),
        "translation_key": "scharlau_perception",
        "icon": "mdi:sun-thermometer",
    },
    SensorType.WINTER_SCHARLAU_PERCEPTION: {
        "key": SensorType.WINTER_SCHARLAU_PERCEPTION,
        "name": SensorType.WINTER_SCHARLAU_PERCEPTION.to_name(),
        "device_class": SensorDeviceClass.ENUM,
        "options": list(map(str, ScharlauPerception)),
        "translation_key": "scharlau_perception",
        "icon": "mdi:snowflake-thermometer",
    },
    SensorType.SUMMER_SIMMER_INDEX: {
        "key": SensorType.SUMMER_SIMMER_INDEX,
        "name": SensorType.SUMMER_SIMMER_INDEX.to_name(),
        "device_class": SensorDeviceClass.TEMPERATURE,
        "suggested_display_precision": DISPLAY_PRECISION,
        "native_unit_of_measurement": UnitOfTemperature.CELSIUS,
        "state_class": SensorStateClass.MEASUREMENT,
        "icon": "mdi:sun-thermometer",
    },
    SensorType.SUMMER_SIMMER_PERCEPTION: {
        "key": SensorType.SUMMER_SIMMER_PERCEPTION,
        "name": SensorType.SUMMER_SIMMER_PERCEPTION.to_name(),
        "device_class": SensorDeviceClass.ENUM,
        "options": list(map(str, SummerSimmerPerception)),
        "translation_key": SensorType.SUMMER_SIMMER_PERCEPTION,
        "icon": "mdi:sun-thermometer",
    },
    SensorType.DEW_POINT_PERCEPTION: {
        "key": SensorType.DEW_POINT_PERCEPTION,
        "name": SensorType.DEW_POINT_PERCEPTION.to_name(),
        "device_class": SensorDeviceClass.ENUM,
        "options": list(map(str, DewPointPerception)),
        "translation_key": SensorType.DEW_POINT_PERCEPTION,
        "icon": "mdi:sun-thermometer",
    },
    SensorType.THOMS_DISCOMFORT_PERCEPTION: {
        "key": SensorType.THOMS_DISCOMFORT_PERCEPTION,
        "name": SensorType.THOMS_DISCOMFORT_PERCEPTION.to_name(),
        "device_class": SensorDeviceClass.ENUM,
        "options": list(map(str, ThomsDiscomfortPerception)),
        "translation_key": SensorType.THOMS_DISCOMFORT_PERCEPTION,
        "icon": "mdi:sun-thermometer",
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
        vol.Required(CONF_UNIQUE_ID): cv.string,
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
            "Legacy YAML configuration is unsupported in 2.0. You should update to the new yaml format: https://github.com/dolezsa/thermal_comfort/blob/master/documentation/yaml.md"
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
                custom_icons=device_config.get(CONF_CUSTOM_ICONS, False),
                is_config_entry=False,
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

    Called via async_forward_entry_setups(, SENSOR) from __init__.py
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
        custom_icons: bool = False,
        is_config_entry: bool = True,
    ) -> None:
        """Initialize the sensor."""
        self._device = device
        self._sensor_type = sensor_type
        self.entity_description = entity_description
        self.entity_description.has_entity_name = is_config_entry
        if not is_config_entry:
            self.entity_description.name = (
                f"{self._device.name} {self.entity_description.name}"
            )
            if sensor_type in [SensorType.DEW_POINT_PERCEPTION, SensorType.SUMMER_SIMMER_INDEX, SensorType.SUMMER_SIMMER_PERCEPTION]:
                registry = entity_registry.async_get(self._device.hass)
                if sensor_type is SensorType.DEW_POINT_PERCEPTION:
                    unique_id = id_generator(self._device.unique_id, LegacySensorType.THERMAL_PERCEPTION)
                    entity_id = registry.async_get_entity_id(SENSOR_DOMAIN, DOMAIN, unique_id)
                elif sensor_type is SensorType.SUMMER_SIMMER_INDEX:
                    unique_id = id_generator(self._device.unique_id, LegacySensorType.SIMMER_INDEX)
                    entity_id = registry.async_get_entity_id(SENSOR_DOMAIN, DOMAIN, unique_id)
                elif sensor_type is SensorType.SUMMER_SIMMER_PERCEPTION:
                    unique_id = id_generator(self._device.unique_id, LegacySensorType.SIMMER_ZONE)
                    entity_id = registry.async_get_entity_id(SENSOR_DOMAIN, DOMAIN, unique_id)
                if entity_id is not None:
                    registry.async_update_entity(entity_id, new_unique_id=id_generator(self._device.unique_id, sensor_type))
        if custom_icons:
            if self.entity_description.key in TC_ICONS:
                self.entity_description.icon = TC_ICONS[self.entity_description.key]
        self._icon_template = icon_template
        self._entity_picture_template = entity_picture_template
        self._attr_native_value = None
        self._attr_extra_state_attributes = {}
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

        if type(value) == tuple and len(value) == 2:
            if self._sensor_type == SensorType.HUMIDEX_PERCEPTION:
                self._attr_extra_state_attributes[ATTR_HUMIDEX] = value[1]
            elif self._sensor_type == SensorType.DEW_POINT_PERCEPTION:
                self._attr_extra_state_attributes[ATTR_DEW_POINT] = value[1]
            elif self._sensor_type == SensorType.FROST_RISK:
                self._attr_extra_state_attributes[ATTR_FROST_POINT] = value[1]
            elif self._sensor_type == SensorType.RELATIVE_STRAIN_PERCEPTION:
                self._attr_extra_state_attributes[ATTR_RELATIVE_STRAIN_INDEX] = value[1]
            elif self._sensor_type == SensorType.SUMMER_SCHARLAU_PERCEPTION:
                self._attr_extra_state_attributes[ATTR_SUMMER_SCHARLAU_INDEX] = value[1]
            elif self._sensor_type == SensorType.WINTER_SCHARLAU_PERCEPTION:
                self._attr_extra_state_attributes[ATTR_WINTER_SCHARLAU_INDEX] = value[1]
            elif self._sensor_type == SensorType.SUMMER_SIMMER_PERCEPTION:
                self._attr_extra_state_attributes[ATTR_SUMMER_SIMMER_INDEX] = value[1]
            elif self._sensor_type == SensorType.THOMS_DISCOMFORT_PERCEPTION:
                self._attr_extra_state_attributes[ATTR_THOMS_DISCOMFORT_INDEX] = value[
                    1
                ]
            self._attr_native_value = value[0]
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
            hass = self.hass
            unit = state.attributes.get(ATTR_UNIT_OF_MEASUREMENT, hass.config.units.temperature_unit)
            temp = util.convert(state.state, float)
            # convert to celsius if necessary
            temperature = TemperatureConverter.convert(temp, unit, UnitOfTemperature.CELSIUS)
            if -89.2 <= temperature <= 56.7:
                self.extra_state_attributes[ATTR_TEMPERATURE] = temp
                self._temperature = temperature
                await self.async_update()
        else:
            _LOGGER.info(f"Temperature has an invalid value: {state}. Can't calculate new states.")

    async def humidity_state_listener(self, event):
        """Handle humidity device state changes."""
        await self._new_humidity_state(event.data.get("new_state"))

    async def _new_humidity_state(self, state):
        if _is_valid_state(state):
            humidity = float(state.state)
            if 0 < humidity <= 100:
                self._humidity = float(state.state)
                self.extra_state_attributes[ATTR_HUMIDITY] = self._humidity
                await self.async_update()
        else:
            _LOGGER.info(f"Relative humidity has an invalid value: {state}. Can't calculate new states.")

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
        return Td

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
    async def humidex_perception(self) -> (HumidexPerception, float):
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

        return perception, humidex

    @compute_once_lock(SensorType.DEW_POINT_PERCEPTION)
    async def dew_point_perception(self) -> (DewPointPerception, float):
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

        return perception, dewpoint

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
        return abs_humidity

    @compute_once_lock(SensorType.FROST_POINT)
    async def frost_point(self) -> float:
        """Frost Point <https://pon.fr/dzvents-alerte-givre-et-calcul-humidite-absolue/>."""
        dewpoint = await self.dew_point()
        T = self._temperature + 273.15
        Td = dewpoint + 273.15
        return (Td + (2671.02 / ((2954.61 / T) + 2.193665 * math.log(T) - 13.3448)) - T) - 273.15

    @compute_once_lock(SensorType.FROST_RISK)
    async def frost_risk(self) -> (FrostRisk, float):
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

        return frost_risk, frostpoint

    @compute_once_lock(SensorType.RELATIVE_STRAIN_PERCEPTION)
    async def relative_strain_perception(self) -> (RelativeStrainPerception, float):
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

        return perception, rsi

    @compute_once_lock(SensorType.SUMMER_SCHARLAU_PERCEPTION)
    async def summer_scharlau_perception(self) -> (ScharlauPerception, float):
        """<https://revistadechimie.ro/pdf/16%20RUSANESCU%204%2019.pdf>."""
        tc = -17.089 * math.log(self._humidity) + 94.979
        ise = tc - self._temperature

        if self._temperature < 17 or self._temperature > 39 or self._humidity < 30:
            perception = ScharlauPerception.OUTSIDE_CALCULABLE_RANGE
        elif ise <= -3:
            perception = ScharlauPerception.HIGHLY_UNCOMFORTABLE
        elif ise <= -1:
            perception = ScharlauPerception.MODERATLY_UNCOMFORTABLE
        elif ise < 0:
            perception = ScharlauPerception.SLIGHTLY_UNCOMFORTABLE
        else:
            perception = ScharlauPerception.COMFORTABLE

        return perception, round(ise, 2)

    @compute_once_lock(SensorType.WINTER_SCHARLAU_PERCEPTION)
    async def winter_scharlau_perception(self) -> (ScharlauPerception, float):
        """<https://revistadechimie.ro/pdf/16%20RUSANESCU%204%2019.pdf>."""
        tc = (0.0003 * self._humidity) + (0.1497 * self._humidity) - 7.7133
        ish = self._temperature - tc
        if self._temperature < -5 or self._temperature > 6 or self._humidity < 40:
            perception = ScharlauPerception.OUTSIDE_CALCULABLE_RANGE
        elif ish <= -3:
            perception = ScharlauPerception.HIGHLY_UNCOMFORTABLE
        elif ish <= -1:
            perception = ScharlauPerception.MODERATLY_UNCOMFORTABLE
        elif ish < 0:
            perception = ScharlauPerception.SLIGHTLY_UNCOMFORTABLE
        else:
            perception = ScharlauPerception.COMFORTABLE

        return perception, round(ish, 2)

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
    async def summer_simmer_perception(self) -> (SummerSimmerPerception, float):
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

        return summer_simmer_perception, si

    @compute_once_lock(SensorType.MOIST_AIR_ENTHALPY)
    async def moist_air_enthalpy(self) -> float:
        """Calculate the enthalpy of moist air."""
        patm = 101325
        c_to_k = 273.15
        h_fg = 2501000
        cp_vapour = 1805.0

        # calculate vapour pressure
        ta_k = self._temperature + c_to_k
        c1 = -5674.5359
        c2 = 6.3925247
        c3 = -0.9677843 * math.pow(10, -2)
        c4 = 0.62215701 * math.pow(10, -6)
        c5 = 0.20747825 * math.pow(10, -8)
        c6 = -0.9484024 * math.pow(10, -12)
        c7 = 4.1635019
        c8 = -5800.2206
        c9 = 1.3914993
        c10 = -0.048640239
        c11 = 0.41764768 * math.pow(10, -4)
        c12 = -0.14452093 * math.pow(10, -7)
        c13 = 6.5459673

        if ta_k < c_to_k:
            pascals = math.exp(
                c1 / ta_k
                + c2
                + ta_k * (c3 + ta_k * (c4 + ta_k * (c5 + c6 * ta_k)))
                + c7 * math.log(ta_k)
            )
        else:
            pascals = math.exp(
                c8 / ta_k
                + c9
                + ta_k * (c10 + ta_k * (c11 + ta_k * c12))
                + c13 * math.log(ta_k)
            )

        # calculate humidity ratio
        p_saturation = pascals
        p_vap = self._humidity / 100 * p_saturation
        hr = 0.62198 * p_vap / (patm - p_vap)

        # calculate enthalpy
        cp_air = 1004
        h_dry_air = cp_air * self._temperature
        h_sat_vap = h_fg + cp_vapour * self._temperature
        h = h_dry_air + hr * h_sat_vap

        return h / 1000

    @compute_once_lock(SensorType.THOMS_DISCOMFORT_PERCEPTION)
    async def thoms_discomfort_perception(self) -> (ThomsDiscomfortPerception, float):
        """Calculate Thom's discomfort index and perception."""
        tw = (
            self._temperature
            * math.atan(0.151977 * pow(self._humidity + 8.313659, 1 / 2))
            + math.atan(self._temperature + self._humidity)
            - math.atan(self._humidity - 1.676331)
            + pow(0.00391838 * self._humidity, 3 / 2)
            * math.atan(0.023101 * self._humidity)
            - 4.686035
        )
        tdi = 0.5 * tw + 0.5 * self._temperature

        if tdi >= 32:
            perception = ThomsDiscomfortPerception.DANGEROUS
        elif tdi >= 29:
            perception = ThomsDiscomfortPerception.EVERYONE
        elif tdi >= 27:
            perception = ThomsDiscomfortPerception.MOST
        elif tdi >= 24:
            perception = ThomsDiscomfortPerception.MORE_THEN_HALF
        elif tdi >= 21:
            perception = ThomsDiscomfortPerception.LESS_THEN_HALF
        else:
            perception = ThomsDiscomfortPerception.NO_DISCOMFORT

        return perception, round(tdi, 2)

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
