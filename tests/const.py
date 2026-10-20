"""General test constants."""

from custom_components.thermal_comfort.const import (
    CONF_HUMIDITY_SENSOR,
    CONF_POLL,
    CONF_TEMPERATURE_SENSOR,
)
from custom_components.thermal_comfort.sensor import (
    CONF_CUSTOM_ICONS,
    CONF_ENABLED_SENSORS,
    CONF_SCAN_INTERVAL,
    LegacySensorType,
    SensorType,
)
from homeassistant.const import CONF_NAME

USER_INPUT = {
    CONF_NAME: "New name",
    CONF_TEMPERATURE_SENSOR: "sensor.test_temperature_sensor",
    CONF_HUMIDITY_SENSOR: "sensor.test_humidity_sensor",
    CONF_POLL: False,
    CONF_CUSTOM_ICONS: False,
    CONF_SCAN_INTERVAL: 30,
}

ADVANCED_USER_INPUT = {
    **USER_INPUT,
    CONF_NAME: "test_thermal_comfort",
    CONF_ENABLED_SENSORS: [],
}


# sensors renamed in thermal comfort 2.0, their unique_ids are migrated
RENAMED_SENSOR_TYPES = {
    LegacySensorType.THERMAL_PERCEPTION: SensorType.DEW_POINT_PERCEPTION,
    LegacySensorType.SIMMER_INDEX: SensorType.SUMMER_SIMMER_INDEX,
    LegacySensorType.SIMMER_ZONE: SensorType.SUMMER_SIMMER_PERCEPTION,
}


def form_input(flat_input: dict) -> dict:
    """Turn flat options into the nested input of the config and options forms."""
    advanced = (CONF_POLL, CONF_SCAN_INTERVAL, CONF_CUSTOM_ICONS, CONF_ENABLED_SENSORS)
    return {k: v for k, v in flat_input.items() if k not in advanced} | {
        "advanced": {k: v for k, v in flat_input.items() if k in advanced}
    }
