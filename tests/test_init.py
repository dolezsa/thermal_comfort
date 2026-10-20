"""Test setup process."""

from unittest.mock import AsyncMock, patch

from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.thermal_comfort import async_setup_entry, async_unload_entry
from custom_components.thermal_comfort.const import DOMAIN, PLATFORMS
from custom_components.thermal_comfort.sensor import (
    LegacySensorType,
    SensorType,
    id_generator,
)
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.helpers import entity_registry as er

from .const import ADVANCED_USER_INPUT


async def test_setup_unload_entry(hass):
    """Test entry setup and unload."""

    hass.config_entries.async_forward_entry_setups = AsyncMock()
    with patch.object(hass.config_entries, "async_update_entry") as p:
        config_entry = MockConfigEntry(
            domain=DOMAIN, data=ADVANCED_USER_INPUT, entry_id="test", unique_id=None
        )
        await hass.config_entries.async_add(config_entry)
        assert p.called

    assert await async_setup_entry(hass, config_entry)
    assert DOMAIN in hass.data and config_entry.entry_id in hass.data[DOMAIN]

    # without a unique_id the entry id is used
    assert config_entry.unique_id == config_entry.entry_id

    # check user input is in config
    for key in ADVANCED_USER_INPUT:
        if key in hass.data[DOMAIN][config_entry.entry_id]:
            assert (
                hass.data[DOMAIN][config_entry.entry_id][key]
                == ADVANCED_USER_INPUT[key]
            )

    hass.config_entries.async_forward_entry_setups.assert_called_with(
        config_entry, PLATFORMS
    )

    # Unload the entry and verify that the data has been removed
    assert await async_unload_entry(hass, config_entry)
    assert config_entry.entry_id not in hass.data[DOMAIN]


async def test_migrate_entry_renames_legacy_unique_ids(hass):
    """Test that a version 1 entry gets the unique_ids of the sensors renamed in 2.0."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data=ADVANCED_USER_INPUT,
        entry_id="test",
        unique_id="uid",
        version=1,
    )
    config_entry.add_to_hass(hass)
    registry = er.async_get(hass)
    renamed = {
        LegacySensorType.THERMAL_PERCEPTION: SensorType.DEW_POINT_PERCEPTION,
        LegacySensorType.SIMMER_INDEX: SensorType.SUMMER_SIMMER_INDEX,
        LegacySensorType.SIMMER_ZONE: SensorType.SUMMER_SIMMER_PERCEPTION,
    }
    entity_ids = {}
    for legacy_type in renamed:
        entity_ids[legacy_type] = registry.async_get_or_create(
            SENSOR_DOMAIN,
            DOMAIN,
            id_generator("uid", legacy_type),
            config_entry=config_entry,
        ).entity_id

    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.version == 2
    for legacy_type, sensor_type in renamed.items():
        entry = registry.async_get(entity_ids[legacy_type])
        assert entry.unique_id == id_generator("uid", sensor_type)
