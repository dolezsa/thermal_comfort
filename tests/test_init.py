"""Test setup process."""

from unittest.mock import AsyncMock, patch

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.thermal_comfort import async_setup_entry, async_unload_entry
from custom_components.thermal_comfort.const import DOMAIN, PLATFORMS
from custom_components.thermal_comfort.sensor import SensorType, id_generator
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.helpers import entity_registry as er

from .const import ADVANCED_USER_INPUT, RENAMED_SENSOR_TYPES

ENGLISH_ENTITY_IDS = {
    f"sensor.test_thermal_comfort_{sensor_type}" for sensor_type in SensorType
}


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
    entity_ids = {}
    for legacy_type in RENAMED_SENSOR_TYPES:
        entity_ids[legacy_type] = registry.async_get_or_create(
            SENSOR_DOMAIN,
            DOMAIN,
            id_generator("uid", legacy_type),
            config_entry=config_entry,
        ).entity_id

    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.version == 2
    for legacy_type, sensor_type in RENAMED_SENSOR_TYPES.items():
        entry = registry.async_get(entity_ids[legacy_type])
        assert entry.unique_id == id_generator("uid", sensor_type)


@pytest.mark.parametrize(
    ("language", "name"),
    [
        ("en", "Moist air enthalpy"),
        ("it", "Entalpia dell'aria umida"),
        ("de", "Enthalpie feuchter Luft"),
    ],
)
async def test_entity_ids_are_english(hass, language, name):
    """Test that the entity_ids are English, only the names are translated."""
    hass.config.language = language
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={**ADVANCED_USER_INPUT, "enabled_sensors": list(SensorType)},
        entry_id="test",
        unique_id="uid",
        version=2,
    )
    config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    registry = er.async_get(hass)
    entries = er.async_entries_for_config_entry(registry, config_entry.entry_id)
    assert {entry.entity_id for entry in entries} == ENGLISH_ENTITY_IDS
    state = hass.states.get("sensor.test_thermal_comfort_moist_air_enthalpy")
    assert state.attributes["friendly_name"] == f"test_thermal_comfort {name}"


async def test_registered_entity_id_is_kept(hass):
    """Test that an entity_id registered before is not renamed."""
    hass.config.language = "it"
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data=ADVANCED_USER_INPUT,
        entry_id="test",
        unique_id="uid",
        version=2,
    )
    config_entry.add_to_hass(hass)
    registry = er.async_get(hass)
    old_entity_id = "sensor.test_thermal_comfort_entalpia_dell_aria_umida"
    registry.async_get_or_create(
        SENSOR_DOMAIN,
        DOMAIN,
        id_generator("uid", SensorType.MOIST_AIR_ENTHALPY),
        config_entry=config_entry,
        suggested_object_id="test_thermal_comfort_entalpia_dell_aria_umida",
    )

    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    entry = registry.async_get(old_entity_id)
    assert entry.unique_id == id_generator("uid", SensorType.MOIST_AIR_ENTHALPY)
    assert registry.async_get("sensor.test_thermal_comfort_dew_point") is not None
