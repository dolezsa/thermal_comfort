"""General thermal_comfort constants."""
from homeassistant.const import Platform

DOMAIN = "thermal_comfort"
PLATFORMS = [Platform.SENSOR]
CONF_TEMPERATURE_SENSOR = "temperature_sensor"
CONF_HUMIDITY_SENSOR = "humidity_sensor"
CONF_POLL = "poll"

DEFAULT_NAME = "Thermal comfort"
UPDATE_LISTENER = "update_listener"
