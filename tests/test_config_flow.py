"""Test integration_blueprint config flow."""
import json
from unittest.mock import MagicMock, patch

from homeassistant import config_entries, data_entry_flow
from homeassistant.const import CONF_NAME
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.thermal_comfort.const import (
    CONF_HUMIDITY_SENSOR,
    CONF_TEMPERATURE_SENSOR,
    DOMAIN,
)

from .const import USER_INPUT, USER_NEW_INPUT
from .test_sensor import DEFAULT_TEST_SENSORS


@pytest.fixture(autouse=True)
def bypass_setup_fixture():
    """Prevent setup."""
    with patch(
        "custom_components.thermal_comfort.async_setup_entry",
        return_value=True,
    ):
        yield


async def _flow_init(hass, advanced_options=True):
    return await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_USER,
            "show_advanced_options": advanced_options,
        },
    )


async def _flow_configure(hass, r, _input=USER_INPUT):
    with patch(
        "homeassistant.helpers.entity_registry.EntityRegistry.async_get",
        return_value=MagicMock(unique_id="foo"),
    ):
        return await hass.config_entries.flow.async_configure(
            r["flow_id"], user_input=_input
        )


@pytest.mark.parametrize("domains", DEFAULT_TEST_SENSORS)
async def test_successful_config_flow(hass, start_ha):
    """Test a successful config flow."""
    # Initialize a config flow
    result = await _flow_init(hass)

    # Check that the config flow shows the user form as the first step
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"

    result = await _flow_configure(hass, result)

    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY

    assert result["title"] == USER_INPUT[CONF_NAME]
    assert result["data"] == USER_INPUT
    assert result["result"]


@pytest.mark.parametrize("domains", DEFAULT_TEST_SENSORS)
async def test_failed_config_flow(hass, start_ha):
    """Config flow should fail if ..."""

    # We try to set up second instance for same temperature and humidity sensors
    for _ in [0, 1]:
        result = await _flow_init(hass)
        result = await _flow_configure(hass, result)

    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.parametrize("domains", DEFAULT_TEST_SENSORS)
async def test_options_flow(hass, start_ha):
    """Test flow for options changes."""
    # setup entry
    entry = MockConfigEntry(domain=DOMAIN, data=USER_INPUT, entry_id="test")
    entry.add_to_hass(hass)

    # Initialize an options flow for entry
    result = await hass.config_entries.options.async_init(
        entry.entry_id, context={"show_advanced_options": True}
    )

    # Verify that the first options step is a user form
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "init"

    # Enter some data into the form
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input=USER_NEW_INPUT,
    )

    # Verify that the flow finishes
    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == ""

    # Verify that the options were updated

    assert entry.options == USER_NEW_INPUT


async def test_config_flow_enabled():
    """Test is manifest.json have 'config_flow': true."""
    with open("custom_components/thermal_comfort/manifest.json") as f:
        manifest = json.load(f)
        assert manifest.get("config_flow") is True


@pytest.mark.parametrize("domains", DEFAULT_TEST_SENSORS)
@pytest.mark.parametrize("sensor", [CONF_TEMPERATURE_SENSOR, CONF_HUMIDITY_SENSOR])
async def test_missed_sensors(hass, sensor, start_ha):
    """Test is we show message if sensor missed."""

    result = await _flow_init(hass)

    # Check that the config flow shows the user form as the first step
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"

    no_sensor = dict(USER_INPUT)
    no_sensor[sensor] = "foo"
    result = await _flow_configure(hass, result, no_sensor)

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
