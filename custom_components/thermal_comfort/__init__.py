"""
Custom integration to integrate thermal_comfort with Home Assistant.

For more details about this integration, please refer to
https://github.com/dolezsa/thermal_comfort
"""

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant

from .config_flow import get_value
from .const import (
    CONF_HUMIDITY_SENSOR,
    CONF_POLL,
    CONF_TEMPERATURE_SENSOR,
    DOMAIN,
    PLATFORMS,
    UPDATE_LISTENER,
)
from .sensor import SensorType


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up entry configured from user interface."""
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        CONF_NAME: get_value(entry, CONF_NAME),
        CONF_TEMPERATURE_SENSOR: get_value(entry, CONF_TEMPERATURE_SENSOR),
        CONF_HUMIDITY_SENSOR: get_value(entry, CONF_HUMIDITY_SENSOR),
        CONF_POLL: get_value(entry, CONF_POLL),
    }
    if entry.unique_id is None:
        # We have no unique_id yet, let's use backup.
        hass.config_entries.async_update_entry(entry, unique_id=entry.entry_id)

    for st in SensorType:
        hass.data[DOMAIN][entry.entry_id][st] = get_value(entry, st)

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)
    update_listener = entry.add_update_listener(async_update_options)
    hass.data[DOMAIN][entry.entry_id][UPDATE_LISTENER] = update_listener
    return True


async def async_update_options(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Update options from user interface."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Remove entry via user interface."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        update_listener = hass.data[DOMAIN][entry.entry_id][UPDATE_LISTENER]
        update_listener()
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok
