"""Test setup process."""

import logging
from unittest.mock import AsyncMock, patch

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.thermal_comfort import async_setup_entry, async_unload_entry
from custom_components.thermal_comfort.const import DOMAIN, PLATFORMS
from custom_components.thermal_comfort.sensor import (
    DEFAULT_SENSOR_TYPES,
    SensorType,
    id_generator,
)
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component

from .const import ADVANCED_USER_INPUT, RENAMED_SENSOR_TYPES

ENGLISH_ENTITY_IDS = {
    f"sensor.test_thermal_comfort_{sensor_type}" for sensor_type in DEFAULT_SENSOR_TYPES
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
        data={**ADVANCED_USER_INPUT, "enabled_sensors": list(DEFAULT_SENSOR_TYPES)},
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


ICONS_PATH = "/thermal_comfort/thermal_comfort_icons.js"


async def test_icons_are_served_and_loaded_in_the_frontend(hass, hass_client, caplog):
    """Test that the tc: icon set is served and added to the frontend once."""
    assert await async_setup_component(hass, "http", {})
    hass.config.components.add("frontend")
    with patch("custom_components.thermal_comfort.add_extra_js_url") as add:
        assert await async_setup_component(hass, DOMAIN, {})
        await hass.async_block_till_done()

        # more entries do not register it again
        for index in range(2):
            entry = MockConfigEntry(
                domain=DOMAIN,
                data={**ADVANCED_USER_INPUT, "temperature_sensor": f"sensor.t{index}"},
                entry_id=f"test{index}",
                unique_id=f"uid{index}",
            )
            entry.add_to_hass(hass)
            assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    add.assert_called_once()
    assert "Could not register the custom icons" not in caplog.text
    url = add.call_args.args[1]
    assert url.startswith(f"{ICONS_PATH}?v=")

    client = await hass_client()
    response = await client.get(url)
    assert response.status == 200
    body = await response.text()
    assert 'window.customIconsets["tc"]' in body
    for name in ("dew-point", "frost-point", "thermal-perception"):
        assert f'"{name}"' in body


async def test_icons_are_skipped_without_the_frontend(hass, caplog):
    """Test that a setup without the frontend works and does not serve the icons."""
    assert await async_setup_component(hass, "http", {})
    with (
        caplog.at_level(logging.INFO),
        patch("custom_components.thermal_comfort.add_extra_js_url") as add,
    ):
        assert await async_setup_component(hass, DOMAIN, {})
    add.assert_not_called()
    assert "custom icons (tc:) are not available" in caplog.text


async def test_icons_are_skipped_without_http(hass):
    """Test that a setup without the http component works."""
    hass.config.components.add("frontend")
    with patch("custom_components.thermal_comfort.add_extra_js_url") as add:
        assert await async_setup_component(hass, DOMAIN, {})
    add.assert_not_called()


async def test_icon_registration_failure_does_not_break_the_setup(hass, caplog):
    """Test that an error while registering the icons only logs a warning."""
    assert await async_setup_component(hass, "http", {})
    hass.config.components.add("frontend")
    with patch(
        "custom_components.thermal_comfort.add_extra_js_url",
        side_effect=RuntimeError("boom"),
    ):
        assert await async_setup_component(hass, DOMAIN, {})
    assert "Could not register the custom icons" in caplog.text


@pytest.mark.parametrize(
    ("stored", "icon"),
    [(True, "tc:thermal-perception"), (False, "mdi:"), (None, "mdi:")],
)
async def test_entry_icons_follow_the_stored_option(hass, stored, icon):
    """Test that only an entry that has the option on gets the tc: icons."""
    data = {k: v for k, v in ADVANCED_USER_INPUT.items() if k != "custom_icons"}
    data["enabled_sensors"] = [SensorType.DEW_POINT_PERCEPTION]
    if stored is not None:
        data["custom_icons"] = stored
    entry = MockConfigEntry(
        domain=DOMAIN, data=data, entry_id="test", unique_id="uid", version=2
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    registry = er.async_get(hass)
    entity_id = registry.async_get_entity_id(
        SENSOR_DOMAIN, DOMAIN, id_generator("uid", SensorType.DEW_POINT_PERCEPTION)
    )
    entity = hass.data["entity_components"]["sensor"].get_entity(entity_id)
    # the standard icons are mdi: ones
    assert entity.entity_description.icon.startswith(icon)
