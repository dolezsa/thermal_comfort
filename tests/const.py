"""General test constants."""
from homeassistant.const import CONF_NAME

from custom_components.thermal_comfort.const import (
    CONF_HUMIDITY_SENSOR,
    CONF_POLL,
    CONF_TEMPERATURE_SENSOR,
)
from custom_components.thermal_comfort.sensor import CONF_CUSTOM_ICONS, SensorType

USER_INPUT = {
    CONF_NAME: "test_thermal_comfort",
    CONF_TEMPERATURE_SENSOR: "sensor.test_temperature_sensor",
    CONF_HUMIDITY_SENSOR: "sensor.test_humidity_sensor",
    CONF_POLL: False,
    CONF_CUSTOM_ICONS: False,
}

USER_NEW_INPUT = dict(USER_INPUT)
USER_NEW_INPUT[CONF_NAME] = "New name"

for i in SensorType:
    USER_INPUT[i] = True
