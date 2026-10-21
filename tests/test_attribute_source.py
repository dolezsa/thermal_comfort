"""Test sources that have the temperature or the humidity in an attribute."""

from datetime import timedelta
from unittest.mock import patch

import pytest
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_capture_events,
    async_fire_time_changed,
)
import voluptuous as vol

from custom_components.thermal_comfort import CONFIG_SCHEMA
from custom_components.thermal_comfort.const import DOMAIN
from custom_components.thermal_comfort.sensor import (
    CONF_HUMIDITY_ATTRIBUTE,
    CONF_HUMIDITY_SENSOR,
    CONF_TEMPERATURE_ATTRIBUTE,
    CONF_TEMPERATURE_SENSOR,
    DEFAULT_TEMPERATURE_ATTRIBUTES,
    DeviceThermalComfort,
    SensorType,
    source_attribute,
)
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.const import CONF_NAME, EVENT_STATE_CHANGED, STATE_UNAVAILABLE
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

from .const import ADVANCED_USER_INPUT
from .test_sensor import CONF_ENABLED_SENSORS

WEATHER = "weather.home"
CLIMATE = "climate.living_room"


async def setup_device(
    hass, temperature, humidity, name="test_thermal_comfort", **extra
):
    """Set up a device with all sensors enabled."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            **ADVANCED_USER_INPUT,
            CONF_NAME: name,
            CONF_TEMPERATURE_SENSOR: temperature,
            CONF_HUMIDITY_SENSOR: humidity,
            CONF_ENABLED_SENSORS: list(SensorType),
            **extra,
        },
        entry_id=name,
        unique_id=name,
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


def sensor_state(hass, sensor_type, name="test_thermal_comfort"):
    """Return the state of a sensor of a device."""
    return hass.states.get(f"sensor.{name}_{sensor_type}")


def all_states(hass, name="test_thermal_comfort"):
    """Return the states of all sensors of a device."""
    return {
        sensor_type: sensor_state(hass, sensor_type, name).state
        for sensor_type in SensorType
    }


async def reference_states(hass, temperature, humidity, unit=None, name="reference"):
    """Return the states of a device with plain sensors as sources."""
    attributes = {"unit_of_measurement": unit} if unit else {}
    hass.states.async_set(f"sensor.{name}_t", str(temperature), attributes)
    hass.states.async_set(f"sensor.{name}_h", str(humidity))
    await setup_device(hass, f"sensor.{name}_t", f"sensor.{name}_h", name)
    return all_states(hass, name)


def weather(temperature=21.5, humidity=50, unit="°C", state="clear-night", **extra):
    """Return state and attributes of a weather entity."""
    return state, {
        "temperature": temperature,
        "humidity": humidity,
        "temperature_unit": unit,
        **extra,
    }


async def test_weather_source_without_configuration(hass):
    """Test that a weather entity works as both sources, as reported in 412."""
    hass.states.async_set(WEATHER, *weather())
    await setup_device(hass, WEATHER, WEATHER)

    states = all_states(hass)
    assert STATE_UNAVAILABLE not in states.values()
    assert states == await reference_states(hass, 21.5, 50)


async def test_weather_temperature_unit(hass):
    """Test that the temperature unit of the weather entity is used."""
    hass.states.async_set(WEATHER, *weather(temperature=70.7, unit="°F"))
    await setup_device(hass, WEATHER, WEATHER)

    assert all_states(hass) == await reference_states(hass, 70.7, 50, "°F")


async def test_unknown_state_with_attributes_is_valid(hass):
    """Test that an unknown state does not matter if the attributes are there."""
    hass.states.async_set(WEATHER, "unknown", weather()[1])
    await setup_device(hass, WEATHER, WEATHER)

    assert STATE_UNAVAILABLE not in all_states(hass).values()


async def test_unavailable_source_and_recovery(hass):
    """Test that an unavailable source makes the sensors unavailable until it is back."""
    hass.states.async_set(WEATHER, STATE_UNAVAILABLE)
    await setup_device(hass, WEATHER, WEATHER)
    assert sensor_state(hass, SensorType.DEW_POINT).state == STATE_UNAVAILABLE

    hass.states.async_set(WEATHER, *weather())
    await hass.async_block_till_done()
    assert STATE_UNAVAILABLE not in all_states(hass).values()

    hass.states.async_set(WEATHER, STATE_UNAVAILABLE)
    await hass.async_block_till_done()
    assert sensor_state(hass, SensorType.DEW_POINT).state == STATE_UNAVAILABLE

    hass.states.async_set(WEATHER, *weather())
    await hass.async_block_till_done()
    assert STATE_UNAVAILABLE not in all_states(hass).values()


@pytest.mark.parametrize(
    "value", [None, [21.5], {"a": 1}, True, "warm", float("nan"), float("inf"), 10**400]
)
async def test_unusable_attribute_values(hass, value):
    """Test that an attribute that is no number makes the sensors unavailable."""
    hass.states.async_set(WEATHER, *weather(temperature=value))
    await setup_device(hass, WEATHER, WEATHER)
    assert sensor_state(hass, SensorType.DEW_POINT).state == STATE_UNAVAILABLE

    hass.states.async_set(WEATHER, *weather(humidity=value))
    await hass.async_block_till_done()
    assert sensor_state(hass, SensorType.DEW_POINT).state == STATE_UNAVAILABLE

    hass.states.async_set(WEATHER, *weather())
    await hass.async_block_till_done()
    assert sensor_state(hass, SensorType.DEW_POINT).state != STATE_UNAVAILABLE


async def test_numeric_string_attribute(hass):
    """Test that a number in a string is accepted, like the state of a sensor."""
    hass.states.async_set(WEATHER, *weather(temperature="21.5", humidity="50"))
    await setup_device(hass, WEATHER, WEATHER)

    assert all_states(hass) == await reference_states(hass, 21.5, 50)


@pytest.mark.parametrize("humidity", [100, 105])
async def test_humidity_range_of_an_attribute(hass, humidity):
    """Test that the humidity of an attribute is limited like the one of a state."""
    hass.states.async_set(WEATHER, *weather(humidity=humidity))
    await setup_device(hass, WEATHER, WEATHER)
    assert sensor_state(hass, SensorType.DEW_POINT).state != STATE_UNAVAILABLE

    hass.states.async_set(WEATHER, *weather(humidity=106))
    await hass.async_block_till_done()
    assert sensor_state(hass, SensorType.DEW_POINT).state == STATE_UNAVAILABLE

    hass.states.async_set(WEATHER, *weather(humidity=0))
    await hass.async_block_till_done()
    assert sensor_state(hass, SensorType.DEW_POINT).state == STATE_UNAVAILABLE


async def test_temperature_range_of_an_attribute(hass):
    """Test that the temperature of an attribute has the same limits as a state."""
    hass.states.async_set(WEATHER, *weather(temperature=56.8))
    await setup_device(hass, WEATHER, WEATHER)
    assert sensor_state(hass, SensorType.DEW_POINT).state == STATE_UNAVAILABLE

    hass.states.async_set(WEATHER, *weather(temperature=-89.3))
    await hass.async_block_till_done()
    assert sensor_state(hass, SensorType.DEW_POINT).state == STATE_UNAVAILABLE


async def test_climate_source(hass):
    """Test that a climate entity works as both sources."""
    hass.states.async_set(
        CLIMATE,
        "heat",
        {"current_temperature": 22.8, "current_humidity": 42, "temperature": 22.5},
    )
    await setup_device(hass, CLIMATE, CLIMATE)

    assert all_states(hass) == await reference_states(hass, 22.8, 42)

    # the humidity is not always there
    hass.states.async_set(CLIMATE, "heat", {"current_temperature": 22.8})
    await hass.async_block_till_done()
    assert sensor_state(hass, SensorType.DEW_POINT).state == STATE_UNAVAILABLE


async def test_separate_temperature_and_humidity_entities(hass):
    """Test an attribute source for one value and a sensor for the other."""
    hass.states.async_set(CLIMATE, "heat", {"current_temperature": 22.8})
    hass.states.async_set("sensor.humidity", "42")
    await setup_device(hass, CLIMATE, "sensor.humidity")

    assert all_states(hass) == await reference_states(hass, 22.8, 42)

    hass.states.async_set(CLIMATE, "heat", {"current_temperature": 25})
    await hass.async_block_till_done()
    assert all_states(hass) == await reference_states(hass, 25, 42, name="second")


async def test_configured_attribute(hass):
    """Test an attribute of an entity without a default and one that replaces the default."""
    # the unit of the state is no unit of a temperature
    hass.states.async_set(
        "sensor.thermostat", "45", {"unit_of_measurement": "%", "temp": 25}
    )
    await setup_device(
        hass,
        "sensor.thermostat",
        "sensor.thermostat",
        **{CONF_TEMPERATURE_ATTRIBUTE: "temp"},
    )
    # the state is the humidity
    assert all_states(hass) == await reference_states(hass, 25, 45)

    # replaces the default of the weather entity
    hass.states.async_set(WEATHER, *weather(temperature=21.5, feel=18.0))
    await setup_device(
        hass,
        WEATHER,
        WEATHER,
        name="feels_like",
        **{CONF_TEMPERATURE_ATTRIBUTE: " feel "},
    )
    assert all_states(hass, "feels_like") == await reference_states(
        hass, 18.0, 50, name="reference_feel"
    )


async def test_unit_of_the_state_is_used_for_a_plain_source(hass):
    """Test that a plain source keeps converting with the unit of its state."""
    hass.states.async_set("sensor.temp_f", "70.7", {"unit_of_measurement": "°F"})
    hass.states.async_set("sensor.hum", "50")
    await setup_device(hass, "sensor.temp_f", "sensor.hum")

    assert all_states(hass) == await reference_states(hass, 21.5, 50)


async def test_no_mixed_state_with_one_source_for_both_values(hass):
    """Test that a change of both values does not compute the new one with the old."""
    hass.states.async_set(WEATHER, *weather(temperature=20, humidity=20))
    await setup_device(hass, WEATHER, WEATHER)
    expected_old = sensor_state(hass, SensorType.DEW_POINT).state
    hass.states.async_set(WEATHER, *weather(temperature=30, humidity=30))
    await hass.async_block_till_done()
    expected_new = sensor_state(hass, SensorType.DEW_POINT).state
    assert expected_old != expected_new

    # back and forth, and watch every state that is written
    hass.states.async_set(WEATHER, *weather(temperature=20, humidity=20))
    await hass.async_block_till_done()
    events = async_capture_events(hass, EVENT_STATE_CHANGED)
    hass.states.async_set(WEATHER, *weather(temperature=30, humidity=30))
    await hass.async_block_till_done()

    written = [
        event.data["new_state"].state
        for event in events
        if event.data["entity_id"] == "sensor.test_thermal_comfort_dew_point"
    ]
    assert written == [expected_new]


async def test_other_attributes_do_not_update_the_sensors(hass):
    """Test that the other attributes of the source do not recompute everything."""
    hass.states.async_set(WEATHER, *weather(wind_speed=1))
    await setup_device(hass, WEATHER, WEATHER)

    with patch.object(
        DeviceThermalComfort,
        "async_update",
        autospec=True,
        side_effect=DeviceThermalComfort.async_update,
    ) as update:
        hass.states.async_set(WEATHER, *weather(wind_speed=5))
        await hass.async_block_till_done()
        assert update.call_count == 0

        hass.states.async_set(WEATHER, *weather(temperature=23, wind_speed=5))
        await hass.async_block_till_done()
        assert update.call_count == 1


async def test_plain_source_update_on_new_value_only(hass):
    """Test that a plain source updates for every new value and again after a failure."""
    hass.states.async_set("sensor.t", "20")
    hass.states.async_set("sensor.h", "50")
    await setup_device(hass, "sensor.t", "sensor.h")
    old = sensor_state(hass, SensorType.DEW_POINT).state

    hass.states.async_set("sensor.t", "unknown")
    await hass.async_block_till_done()
    assert sensor_state(hass, SensorType.DEW_POINT).state == STATE_UNAVAILABLE

    # the same value as before the failure
    hass.states.async_set("sensor.t", "20")
    await hass.async_block_till_done()
    assert sensor_state(hass, SensorType.DEW_POINT).state == old


async def test_yaml_attribute_source(hass):
    """Test the attributes in the YAML configuration."""
    hass.states.async_set(WEATHER, *weather(feel=18.0))
    assert await async_setup_component(
        hass,
        DOMAIN,
        {
            DOMAIN: {
                SENSOR_DOMAIN: [
                    {
                        "name": "yaml_weather",
                        CONF_TEMPERATURE_SENSOR: WEATHER,
                        CONF_HUMIDITY_SENSOR: WEATHER,
                        "unique_id": "yaml_weather",
                    },
                    {
                        "name": "yaml_feel",
                        CONF_TEMPERATURE_SENSOR: WEATHER,
                        CONF_TEMPERATURE_ATTRIBUTE: " feel ",
                        CONF_HUMIDITY_SENSOR: WEATHER,
                        CONF_HUMIDITY_ATTRIBUTE: "humidity",
                        "unique_id": "yaml_feel",
                    },
                ],
            },
        },
    )
    await hass.async_block_till_done()

    assert all_states(hass, "yaml_weather") == await reference_states(hass, 21.5, 50)
    assert all_states(hass, "yaml_feel") == await reference_states(
        hass, 18.0, 50, name="reference_feel"
    )


def test_yaml_schema():
    """Test the attribute options of the YAML schema."""
    config = CONFIG_SCHEMA(
        {
            DOMAIN: [
                {
                    SENSOR_DOMAIN: [
                        {
                            CONF_TEMPERATURE_SENSOR: WEATHER,
                            CONF_HUMIDITY_SENSOR: WEATHER,
                            CONF_TEMPERATURE_ATTRIBUTE: " feel ",
                            "unique_id": "id",
                        }
                    ]
                }
            ]
        }
    )
    sensor = config[DOMAIN][0][SENSOR_DOMAIN][0]
    assert sensor[CONF_TEMPERATURE_ATTRIBUTE] == "feel"
    assert CONF_HUMIDITY_ATTRIBUTE not in sensor

    with pytest.raises(vol.Invalid):
        CONFIG_SCHEMA(
            {
                DOMAIN: [
                    {
                        SENSOR_DOMAIN: [
                            {
                                CONF_TEMPERATURE_SENSOR: WEATHER,
                                CONF_HUMIDITY_SENSOR: WEATHER,
                                CONF_TEMPERATURE_ATTRIBUTE: ["feel"],
                                "unique_id": "id",
                            }
                        ]
                    }
                ]
            }
        )


@pytest.mark.parametrize(
    ("entity_id", "configured", "expected"),
    [
        ("sensor.t", None, None),
        ("sensor.t", "", None),
        ("sensor.t", "  ", None),
        ("sensor.t", "temp", "temp"),
        ("weather.home", None, "temperature"),
        ("weather.home", "", "temperature"),
        ("weather.home", " feel ", "feel"),
        ("climate.x", None, "current_temperature"),
        ("climate.x", "temperature", "temperature"),
    ],
)
def test_source_attribute(entity_id, configured, expected):
    """Test which attribute is used for a source."""
    assert (
        source_attribute(entity_id, configured, DEFAULT_TEMPERATURE_ATTRIBUTES)
        == expected
    )


async def test_plain_source_updates_for_every_change(hass):
    """Test that a plain source updates for every change, as it always did."""
    hass.states.async_set("sensor.t", "20", {"battery": 90})
    hass.states.async_set("sensor.h", "50")
    await setup_device(hass, "sensor.t", "sensor.h")

    with patch.object(
        DeviceThermalComfort,
        "async_update",
        autospec=True,
        side_effect=DeviceThermalComfort.async_update,
    ) as update:
        hass.states.async_set("sensor.t", "20", {"battery": 80})
        await hass.async_block_till_done()
        assert update.call_count == 1


async def test_plain_source_for_both_values(hass):
    """Test that one plain sensor can be both sources, for odd but valid setups."""
    hass.states.async_set("sensor.both", "45")
    await setup_device(hass, "sensor.both", "sensor.both")
    assert sensor_state(hass, SensorType.DEW_POINT).state != STATE_UNAVAILABLE

    hass.states.async_set("sensor.both", "unknown")
    await hass.async_block_till_done()
    assert sensor_state(hass, SensorType.DEW_POINT).state == STATE_UNAVAILABLE

    hass.states.async_set("sensor.both", "45")
    await hass.async_block_till_done()
    assert sensor_state(hass, SensorType.DEW_POINT).state != STATE_UNAVAILABLE


async def test_attribute_source_with_polling(hass):
    """Test that a polled attribute source is updated on the timer."""
    hass.states.async_set(WEATHER, *weather())
    await setup_device(hass, WEATHER, WEATHER, poll=True, scan_interval=30)
    assert all_states(hass) == await reference_states(hass, 21.5, 50)

    old = all_states(hass)
    hass.states.async_set(WEATHER, *weather(temperature=25))
    await hass.async_block_till_done()
    assert all_states(hass) == old

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=60))
    await hass.async_block_till_done()
    assert all_states(hass) == await reference_states(hass, 25, 50, name="second")
