"""Test integration_blueprint config flow."""

import json
from unittest.mock import MagicMock, patch

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.thermal_comfort.const import (
    CONF_HUMIDITY_SENSOR,
    CONF_TEMPERATURE_SENSOR,
    DOMAIN,
)
from homeassistant import config_entries
from homeassistant.const import CONF_NAME
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.setup import async_setup_component

from .const import ADVANCED_USER_INPUT, USER_INPUT, form_input
from .test_sensor import DEFAULT_TEST_SENSORS


@pytest.fixture(autouse=True)
def bypass_setup_fixture():
    """Prevent setup."""
    with patch(
        "custom_components.thermal_comfort.async_setup_entry",
        return_value=True,
    ):
        yield


async def _flow_init(hass):
    return await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )


async def _flow_configure(hass, r, _input=ADVANCED_USER_INPUT, registry_entry=None):
    with patch(
        "homeassistant.helpers.entity_registry.EntityRegistry.async_get",
        side_effect=registry_entry,
        return_value=MagicMock(unique_id="foo"),
    ):
        return await hass.config_entries.flow.async_configure(
            r["flow_id"], user_input=form_input(_input)
        )


@pytest.mark.parametrize(*DEFAULT_TEST_SENSORS)
async def test_successful_config_flow(hass, start_ha):
    """Test a successful config flow."""
    # Initialize a config flow
    result = await _flow_init(hass)

    # Check that the config flow shows the user form as the first step
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await _flow_configure(hass, result)

    assert result["type"] == FlowResultType.CREATE_ENTRY

    assert result["title"] == ADVANCED_USER_INPUT[CONF_NAME]
    assert result["data"] == ADVANCED_USER_INPUT
    assert result["result"]


@pytest.mark.parametrize(*DEFAULT_TEST_SENSORS)
async def test_failed_config_flow(hass, start_ha):
    """Config flow should fail if ..."""

    # We try to set up second instance for same temperature and humidity sensors
    for _ in [0, 1]:
        result = await _flow_init(hass)
        result = await _flow_configure(hass, result)

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.parametrize(*DEFAULT_TEST_SENSORS)
async def test_options_flow(hass, start_ha):
    """Test flow for options changes."""
    # setup entry
    entry = MockConfigEntry(domain=DOMAIN, data=ADVANCED_USER_INPUT, entry_id="test")
    entry.add_to_hass(hass)

    # Initialize an options flow for entry
    result = await hass.config_entries.options.async_init(entry.entry_id)

    # Verify that the first options step is a user form
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "init"

    # Enter some data into the form
    with patch.object(hass.config_entries, "async_schedule_reload") as reload:
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input=form_input(USER_INPUT),
        )

    # Changed options reload the entry
    reload.assert_called_once_with(entry.entry_id)

    # Verify that the flow finishes
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == ""

    # Verify that the options were updated

    assert entry.options == USER_INPUT


@pytest.mark.parametrize(*DEFAULT_TEST_SENSORS)
async def test_advanced_options_section(hass, start_ha, hass_client):
    """Test the form as the frontend receives it, with a section for the advanced options."""
    assert await async_setup_component(hass, "config", {})
    client = await hass_client()

    response = await client.post(
        "/api/config/config_entries/flow", json={"handler": DOMAIN}
    )
    form = await response.json()
    advanced = next(f for f in form["data_schema"] if f["name"] == "advanced")
    assert advanced["type"] == "expandable"
    assert [f["name"] for f in advanced["schema"]] == [
        "poll",
        "scan_interval",
        "custom_icons",
        "enabled_sensors",
    ]

    response = await client.post(
        f"/api/config/config_entries/flow/{form['flow_id']}",
        json=form_input(ADVANCED_USER_INPUT),
    )
    assert (await response.json())["type"] == "create_entry"
    (entry,) = hass.config_entries.async_entries(DOMAIN)
    assert entry.data == ADVANCED_USER_INPUT


async def test_config_flow_enabled():
    """Test is manifest.json have 'config_flow': true."""
    with open("custom_components/thermal_comfort/manifest.json") as f:
        manifest = json.load(f)
        assert manifest.get("config_flow") is True


# @pytest.mark.parametrize(*DEFAULT_TEST_SENSORS)
# @pytest.mark.parametrize("sensor", [CONF_TEMPERATURE_SENSOR, CONF_HUMIDITY_SENSOR])
# async def test_missed_sensors(hass, sensor, start_ha):
#    """Test is we show message if sensor missed."""
#
#    result = await _flow_init(hass)
#
#    # Check that the config flow shows the user form as the first step
#    assert result["type"] == FlowResultType.FORM
#    assert result["step_id"] == "user"
#
#    no_sensor = dict(ADVANCED_USER_INPUT)
#    no_sensor[sensor] = "foo"
#    with pytest.raises(vol.error.MultipleInvalid):
#        result = await _flow_configure(hass, result, no_sensor)
#
#    assert result["type"] == FlowResultType.FORM


def _registry_entry(entity_id):
    """Give every sensor a distinct unique_id."""
    return MagicMock(unique_id=f"uid_{entity_id}")


@pytest.mark.parametrize(*DEFAULT_TEST_SENSORS)
async def test_duplicate_check_uses_current_sensors(hass, start_ha):
    """Test that the duplicate check follows sensors changed by the options flow."""
    pair_a = ADVANCED_USER_INPUT
    pair_b = {
        **ADVANCED_USER_INPUT,
        CONF_TEMPERATURE_SENSOR: "sensor.other_temperature_sensor",
        CONF_HUMIDITY_SENSOR: "sensor.other_humidity_sensor",
    }
    hass.states.async_set(pair_b[CONF_TEMPERATURE_SENSOR], "20")
    hass.states.async_set(pair_b[CONF_HUMIDITY_SENSOR], "40")

    original_unique_id = (
        f"{_registry_entry(pair_a[CONF_TEMPERATURE_SENSOR]).unique_id}-"
        f"{_registry_entry(pair_a[CONF_HUMIDITY_SENSOR]).unique_id}"
    )
    entry = MockConfigEntry(
        domain=DOMAIN, data=pair_a, entry_id="test", unique_id=original_unique_id
    )
    entry.add_to_hass(hass)

    # switch the entry from pair A to pair B with the options flow
    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input=form_input({k: v for k, v in pair_b.items() if k in USER_INPUT}),
    )
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert entry.unique_id == original_unique_id

    # pair B is taken now, although its unique_id was never used
    result = await _flow_configure(
        hass, await _flow_init(hass), pair_b, _registry_entry
    )
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "already_configured"

    # pair A is free again, and the new entry must not replace the old one
    result = await _flow_configure(
        hass, await _flow_init(hass), pair_a, _registry_entry
    )
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id != original_unique_id
    assert hass.config_entries.async_get_entry(entry.entry_id) is entry
    assert len(hass.config_entries.async_entries(DOMAIN)) == 2

    # and now pair A is a duplicate again
    result = await _flow_configure(
        hass, await _flow_init(hass), pair_a, _registry_entry
    )
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.parametrize(*DEFAULT_TEST_SENSORS)
async def test_duplicate_check_sensors_not_in_registry(hass, start_ha):
    """Test that sensors without a registry entry are checked for duplicates too."""
    for _ in [0, 1]:
        result = await _flow_init(hass)
        result = await _flow_configure(
            hass, result, ADVANCED_USER_INPUT, lambda entity_id: None
        )

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "already_configured"
