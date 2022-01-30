"""General test constants."""
from homeassistant.const import CONF_NAME

from custom_components.thermal_comfort.const import (
    CONF_HUMIDITY_SENSOR,
    CONF_POLL,
    CONF_TEMPERATURE_SENSOR,
)
from custom_components.thermal_comfort.sensor import (
    CONF_CUSTOM_ICONS,
    CONF_ENABLED_SENSORS,
)

USER_INPUT = {
    CONF_NAME: "New name",
    CONF_TEMPERATURE_SENSOR: "sensor.test_temperature_sensor",
    CONF_HUMIDITY_SENSOR: "sensor.test_humidity_sensor",
    CONF_POLL: False,
    CONF_CUSTOM_ICONS: False,
}

ADVANCED_USER_INPUT = {
    **USER_INPUT,
    CONF_NAME: "test_thermal_comfort",
    CONF_ENABLED_SENSORS: [],
}
