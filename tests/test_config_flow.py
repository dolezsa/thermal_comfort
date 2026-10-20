"""Test integration_blueprint config flow."""

from unittest.mock import MagicMock, patch

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.thermal_comfort.config_flow import (
    check_input,
    get_sensors_by_device_class,
    get_value,
)
from custom_components.thermal_comfort.const import (
    CONF_HUMIDITY_SENSOR,
    CONF_PRESSURE_SENSOR,
    CONF_TEMPERATURE_SENSOR,
    DOMAIN,
)
from homeassistant import config_entries
from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.const import CONF_NAME
from homeassistant.data_entry_flow import FlowResultType, InvalidData
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component

from .const import ADVANCED_USER_INPUT, USER_INPUT, form_input
from .test_sensor import DEFAULT_TEST_SENSORS, PRESSURE_TEST_SENSORS


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


@pytest.mark.parametrize(*DEFAULT_TEST_SENSORS)
@pytest.mark.parametrize("sensor", [CONF_TEMPERATURE_SENSOR, CONF_HUMIDITY_SENSOR])
@pytest.mark.parametrize("missing", ["foo", "sensor.not_existing"])
async def test_missed_sensors(hass, sensor, missing, start_ha):
    """Test that the form refuses a source sensor that does not exist."""
    result = await _flow_init(hass)
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"

    no_sensor = {**ADVANCED_USER_INPUT, sensor: missing}
    with pytest.raises(InvalidData):
        await _flow_configure(hass, result, no_sensor)

    assert not hass.config_entries.async_entries(DOMAIN)


@pytest.mark.parametrize(
    "missing, error",
    [
        (CONF_TEMPERATURE_SENSOR, "temperature_not_found"),
        (CONF_HUMIDITY_SENSOR, "humidity_not_found"),
        (CONF_PRESSURE_SENSOR, "pressure_not_found"),
    ],
)
async def test_check_input_reports_missing_sensors(hass, missing, error):
    """Test that a source sensor that vanished is reported by its own error."""
    user_input = {
        CONF_TEMPERATURE_SENSOR: "sensor.test_temperature_sensor",
        CONF_HUMIDITY_SENSOR: "sensor.test_humidity_sensor",
        CONF_PRESSURE_SENSOR: "sensor.test_pressure_sensor",
    }
    for entity_id in user_input.values():
        hass.states.async_set(entity_id, "1")
    assert check_input(hass, user_input) == {}

    hass.states.async_remove(user_input[missing])
    assert check_input(hass, user_input) == {"base": error}


async def test_no_sensors_aborts(hass):
    """Test that the flow aborts when there is no temperature or humidity sensor."""
    result = await _flow_init(hass)
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "no_sensors"


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


@pytest.mark.parametrize(*PRESSURE_TEST_SENSORS)
async def test_config_flow_with_pressure_sensor(hass, start_ha):
    """Test that the pressure sensor is optional and stored when given."""
    # without it nothing is stored, like before
    result = await _flow_configure(hass, await _flow_init(hass))
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert CONF_PRESSURE_SENSOR not in result["data"]

    with_pressure = {
        **ADVANCED_USER_INPUT,
        CONF_TEMPERATURE_SENSOR: "sensor.other_temperature_sensor",
        CONF_PRESSURE_SENSOR: "sensor.test_pressure_sensor",
    }
    hass.states.async_set(with_pressure[CONF_TEMPERATURE_SENSOR], "20")
    result = await _flow_configure(hass, await _flow_init(hass), with_pressure)
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["data"] == with_pressure


@pytest.mark.parametrize(*PRESSURE_TEST_SENSORS)
async def test_config_flow_pressure_sensor_not_found(hass, start_ha):
    """Test that an unknown pressure sensor is refused."""
    missing = {**ADVANCED_USER_INPUT, CONF_PRESSURE_SENSOR: "sensor.no_such_sensor"}
    result = await _flow_configure(hass, await _flow_init(hass), missing)
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": "pressure_not_found"}


@pytest.mark.parametrize(*PRESSURE_TEST_SENSORS)
async def test_pressure_sensor_selector(hass, start_ha, hass_client):
    """Test the pressure field as the frontend receives it, outside of the advanced section."""
    assert await async_setup_component(hass, "config", {})
    client = await hass_client()

    response = await client.post(
        "/api/config/config_entries/flow", json={"handler": DOMAIN}
    )
    form = await response.json()
    field = next(f for f in form["data_schema"] if f["name"] == "pressure_sensor")
    assert field["optional"] is True
    assert field["selector"]["entity"]["domain"] == ["sensor"]
    assert set(field["selector"]["entity"]["device_class"]) == {
        "pressure",
        "atmospheric_pressure",
    }
    advanced = next(f for f in form["data_schema"] if f["name"] == "advanced")
    assert "pressure_sensor" not in [f["name"] for f in advanced["schema"]]

    response = await client.post(
        f"/api/config/config_entries/flow/{form['flow_id']}",
        json=form_input(
            {**ADVANCED_USER_INPUT, CONF_PRESSURE_SENSOR: "sensor.test_pressure_sensor"}
        ),
    )
    assert (await response.json())["type"] == "create_entry"
    (entry,) = hass.config_entries.async_entries(DOMAIN)
    assert entry.data[CONF_PRESSURE_SENSOR] == "sensor.test_pressure_sensor"


@pytest.mark.parametrize(*PRESSURE_TEST_SENSORS)
async def test_options_flow_pressure_sensor(hass, start_ha):
    """Test adding, keeping and removing the pressure sensor in the options flow."""
    entry = MockConfigEntry(domain=DOMAIN, data=ADVANCED_USER_INPUT, entry_id="test")
    entry.add_to_hass(hass)

    async def submit(user_input):
        result = await hass.config_entries.options.async_init(entry.entry_id)
        with patch.object(hass.config_entries, "async_schedule_reload"):
            return await hass.config_entries.options.async_configure(
                result["flow_id"], user_input=form_input(user_input)
            )

    # add
    with_pressure = {**USER_INPUT, CONF_PRESSURE_SENSOR: "sensor.test_pressure_sensor"}
    result = await submit(with_pressure)
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert entry.options == with_pressure

    # the stored value is offered again
    result = await hass.config_entries.options.async_init(entry.entry_id)
    schema = result["data_schema"].schema
    key = next(k for k in schema if k == CONF_PRESSURE_SENSOR)
    assert key.description["suggested_value"] == "sensor.test_pressure_sensor"
    hass.config_entries.options.async_abort(result["flow_id"])

    # unknown sensor
    result = await submit({**USER_INPUT, CONF_PRESSURE_SENSOR: "sensor.no_such"})
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": "pressure_not_found"}

    # remove: the options win over the data, so the old value must not come back
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            **ADVANCED_USER_INPUT,
            CONF_PRESSURE_SENSOR: "sensor.test_pressure_sensor",
        },
        entry_id="test2",
    )
    entry.add_to_hass(hass)
    result = await submit(USER_INPUT)
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert get_value(entry, CONF_PRESSURE_SENSOR) is None


@pytest.mark.parametrize(
    "unit",
    ["\u00b5g/m³", "\u03bcg/m³", "\u00b5g/ft³", "\u03bcg/ft³", "\u00b5g", "\u03bcg"]
    + ["\u00b5S/cm", "\u03bcS/cm", "\u00b5s", "\u03bcs"],
)
async def test_micro_units_are_excluded_in_both_spellings(hass, unit):
    """Units with micro are excluded whether spelled U+00B5 or U+03BC."""
    hass.states.async_set("sensor.useless", "1", {"unit_of_measurement": unit})
    hass.states.async_set("sensor.useful", "1", {"unit_of_measurement": "°C"})

    sensors = get_sensors_by_device_class(
        er.async_get(hass), hass, SensorDeviceClass.TEMPERATURE, include_all=True
    )

    assert "sensor.useful" in sensors
    assert "sensor.useless" not in sensors
