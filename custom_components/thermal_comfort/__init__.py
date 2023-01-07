"""
Custom integration to integrate thermal_comfort with Home Assistant.

For more details about this integration, please refer to
https://github.com/dolezsa/thermal_comfort
"""
from __future__ import annotations

import logging

from homeassistant.config import async_hass_config_yaml, async_process_component_config
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME, SERVICE_RELOAD
from homeassistant.core import Event, HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import discovery
from homeassistant.helpers.entity_registry import RegistryEntry, async_migrate_entries
from homeassistant.helpers.reload import async_reload_integration_platforms
from homeassistant.helpers.typing import ConfigType
from homeassistant.loader import async_get_integration

from .config import OPTIONS_SCHEMA
from .config_flow import get_value
from .const import DOMAIN, PLATFORMS, UPDATE_LISTENER
from .sensor import (
    CONF_CUSTOM_ICONS,
    CONF_ENABLED_SENSORS,
    CONF_HUMIDITY_SENSOR,
    CONF_POLL,
    CONF_SCAN_INTERVAL,
    CONF_TEMPERATURE_SENSOR,
    LegacySensorType,
    SensorType,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up entry configured from user interface."""
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        CONF_NAME: get_value(entry, CONF_NAME),
        CONF_TEMPERATURE_SENSOR: get_value(entry, CONF_TEMPERATURE_SENSOR),
        CONF_HUMIDITY_SENSOR: get_value(entry, CONF_HUMIDITY_SENSOR),
        CONF_POLL: get_value(entry, CONF_POLL),
        CONF_SCAN_INTERVAL: get_value(entry, CONF_SCAN_INTERVAL),
        CONF_CUSTOM_ICONS: get_value(entry, CONF_CUSTOM_ICONS),
    }
    if get_value(entry, CONF_ENABLED_SENSORS):
        hass.data[DOMAIN][entry.entry_id][CONF_ENABLED_SENSORS] = get_value(
            entry, CONF_ENABLED_SENSORS
        )
        data = dict(entry.data)
        data.pop(CONF_ENABLED_SENSORS)
        hass.config_entries.async_update_entry(entry, data=data)

    if entry.unique_id is None:
        # We have no unique_id yet, let's use backup.
        hass.config_entries.async_update_entry(entry, unique_id=entry.entry_id)

    hass.async_create_task(
        hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    )
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


async def async_migrate_entry(hass: HomeAssistant, config_entry: ConfigEntry):
    """Migrate old entry."""
    _LOGGER.debug("Migrating from version %s", config_entry.version)

    if config_entry.version == 1:

        def update_unique_id(entry: RegistryEntry):
            """Update unique_id of changed sensor names"""
            if LegacySensorType.THERMAL_PERCEPTION in entry.unique_id:
                return {"new_unique_id": entry.unique_id.replace(LegacySensorType.THERMAL_PERCEPTION, SensorType.DEW_POINT_PERCEPTION)}
            if LegacySensorType.SIMMER_INDEX in entry.unique_id:
                return {"new_unique_id": entry.unique_id.replace(LegacySensorType.SIMMER_INDEX, SensorType.SUMMER_SIMMER_INDEX)}
            if LegacySensorType.SIMMER_ZONE in entry.unique_id:
                return {"new_unique_id": entry.unique_id.replace(LegacySensorType.SIMMER_ZONE, SensorType.SUMMER_SIMMER_PERCEPTION)}

        await async_migrate_entries(hass, config_entry.entry_id, update_unique_id)
        config_entry.version = 2

    _LOGGER.info("Migration to version %s successful", config_entry.version)

    return True


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the thermal_comfort integration."""
    if DOMAIN in config:
        await _process_config(hass, config)

    async def _reload_config(call: Event | ServiceCall) -> None:
        """Reload top-level + platforms."""
        try:
            unprocessed_conf = await async_hass_config_yaml(hass)
        except HomeAssistantError as err:
            _LOGGER.error(err)
            return

        conf = await async_process_component_config(
            hass, unprocessed_conf, await async_get_integration(hass, DOMAIN)
        )

        if conf is None:
            return

        await async_reload_integration_platforms(hass, DOMAIN, PLATFORMS)

        if DOMAIN in conf:
            await _process_config(hass, conf)

        hass.bus.async_fire(f"event_{DOMAIN}_reloaded", context=call.context)

    hass.helpers.service.async_register_admin_service(
        DOMAIN, SERVICE_RELOAD, _reload_config
    )

    return True


async def _process_config(hass: HomeAssistant, hass_config: ConfigType) -> None:
    """Process config."""
    for conf_section in hass_config[DOMAIN]:
        for platform_domain in PLATFORMS:
            if platform_domain in conf_section:
                hass.async_create_task(
                    discovery.async_load_platform(
                        hass,
                        platform_domain,
                        DOMAIN,
                        {
                            "devices": conf_section[platform_domain],
                            "options": OPTIONS_SCHEMA(conf_section),
                        },
                        hass_config,
                    )
                )
