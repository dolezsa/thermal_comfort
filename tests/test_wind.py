"""Test the sensors that need the wind speed."""

from datetime import timedelta
import logging
import math
from unittest.mock import patch

import pytest
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_capture_events,
    async_fire_time_changed,
)
import voluptuous as vol

from custom_components.thermal_comfort.config_flow import (
    build_schema,
    check_input,
    get_sensors_by_device_class,
    get_value,
)
from custom_components.thermal_comfort.const import DOMAIN
from custom_components.thermal_comfort.sensor import (
    CONF_ENABLED_SENSORS,
    CONF_HUMIDITY_SENSOR,
    CONF_OUTDOOR_HUMIDITY_SENSOR,
    CONF_OUTDOOR_TEMPERATURE_SENSOR,
    CONF_TEMPERATURE_SENSOR,
    CONF_WIND_SPEED_SENSOR,
    DEFAULT_SENSOR_TYPES,
    OUTDOOR_SENSOR_TYPES,
    WIND_SENSOR_TYPES,
    DeviceThermalComfort,
    SensorThermalComfort,
    SensorType,
)
from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.const import (
    CONF_NAME,
    EVENT_STATE_CHANGED,
    STATE_UNAVAILABLE,
    EntityCategory,
)
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util
from homeassistant.util.unit_system import US_CUSTOMARY_SYSTEM

from .const import ADVANCED_USER_INPUT, form_input
from .test_attribute_source import WEATHER, weather
from .test_ventilation import set_outdoor, yaml_config

NAME = "test_thermal_comfort"
WIND = "sensor.wind"


def reference_wind_chill(temperature, wind_speed):
    """Wind chill of JAG/TI (2001) in C, the wind speed in km/h, independent of the code."""
    if temperature > 10 or wind_speed <= 4.8:
        return temperature
    factor = wind_speed**0.16
    return 13.12 + 0.6215 * temperature - 11.37 * factor + 0.3965 * temperature * factor


def reference_apparent_temperature(temperature, humidity, wind_speed):
    """Apparent temperature of the BoM in C, the wind speed in m/s, independent of the code."""
    vapor_pressure = (
        humidity / 100 * 6.105 * math.exp(17.27 * temperature / (237.7 + temperature))
    )
    return temperature + 0.33 * vapor_pressure - 0.70 * wind_speed - 4.0


def sensor(hass, sensor_type, name=NAME):
    """Return the state of a sensor."""
    return hass.states.get(f"sensor.{name}_{sensor_type}")


def value(hass, sensor_type, name=NAME):
    """Return the value of a sensor."""
    return float(sensor(hass, sensor_type, name).state)


def dump(hass, name=NAME, sensor_types=DEFAULT_SENSOR_TYPES):
    """Return the states and the attributes of sensors of a device."""
    result = {}
    for sensor_type in sensor_types:
        state = sensor(hass, sensor_type, name)
        attributes = dict(state.attributes)
        attributes.pop("friendly_name", None)
        result[sensor_type] = (state.state, attributes)
    return result


def set_sources(hass, temperature=-10, humidity=50, wind="5", unit="m/s"):
    """Set the sources of the device, the temperature in C."""
    hass.states.async_set("sensor.t", str(temperature), {"unit_of_measurement": "°C"})
    hass.states.async_set("sensor.h", str(humidity))
    if wind is not None:
        hass.states.async_set(WIND, wind, {"unit_of_measurement": unit} if unit else {})


async def setup_entry(hass, wind=WIND, name=NAME, **extra):
    """Set up a device, with the wind speed if wanted."""
    data = {
        **ADVANCED_USER_INPUT,
        CONF_NAME: name,
        CONF_TEMPERATURE_SENSOR: "sensor.t",
        CONF_HUMIDITY_SENSOR: "sensor.h",
        CONF_ENABLED_SENSORS: list(DEFAULT_SENSOR_TYPES),
    }
    if wind:
        data[CONF_WIND_SPEED_SENSOR] = wind
    data |= extra
    entry = MockConfigEntry(domain=DOMAIN, data=data, entry_id=name, unique_id=name)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


@pytest.mark.parametrize(
    ("temperature", "wind_speed", "expected"),
    [
        (-10, 20, -17.86),
        (-20, 30, -32.57),
        (-25, 40, -40.82),
        (0, 10, -3.31),
        # the limits: up to 10 C, above 4.8 km/h
        (10, 5, 9.76),
        # 4.8 km/h converted to m/s and back is exactly 4.8, keep the test of the limit
        (10, 4.8, 10.0),
        (10.01, 30, 10.01),
        (-10, 0, -10.0),
    ],
)
async def test_wind_chill(hass, temperature, wind_speed, expected):
    """Test the wind chill with known values, out of its range it is the air temperature."""
    set_sources(hass, temperature, 50, str(wind_speed), "km/h")
    await setup_entry(hass)
    state = sensor(hass, SensorType.WIND_CHILL)
    assert float(state.state) == pytest.approx(expected, abs=0.005)
    assert float(state.state) == pytest.approx(
        reference_wind_chill(temperature, wind_speed), abs=1e-9
    )
    assert state.attributes["wind_speed"] == wind_speed


async def test_wind_chill_of_sources_in_fahrenheit_and_mph(hass):
    """Test the wind chill of -5 F and 15 mph, -25.86 F in the table of the NWS (-26 F)."""
    hass.states.async_set("sensor.t", "-5", {"unit_of_measurement": "°F"})
    hass.states.async_set("sensor.h", "50")
    hass.states.async_set(WIND, "15", {"unit_of_measurement": "mph"})
    await setup_entry(hass)
    assert value(hass, SensorType.WIND_CHILL) == pytest.approx(-32.14, abs=0.005)
    attributes = sensor(hass, SensorType.WIND_CHILL).attributes
    assert attributes["wind_speed"] == 24.14


@pytest.mark.parametrize(
    ("temperature", "humidity", "wind_speed", "expected"),
    [
        (30, 50, 2, 31.58),
        (35, 70, 0, 43.94),
        (20, 50, 5, 16.35),
        (10, 80, 10, 2.24),
        # calm weather is a valid wind speed
        (0, 50, 0, -2.99),
    ],
)
async def test_apparent_temperature(hass, temperature, humidity, wind_speed, expected):
    """Test the apparent temperature with known values."""
    set_sources(hass, temperature, humidity, str(wind_speed), "m/s")
    await setup_entry(hass)
    state = sensor(hass, SensorType.APPARENT_TEMPERATURE)
    assert float(state.state) == pytest.approx(expected, abs=0.005)
    assert float(state.state) == pytest.approx(
        reference_apparent_temperature(temperature, humidity, wind_speed), abs=1e-9
    )
    assert state.attributes["wind_speed"] == round(wind_speed * 3.6, 2)


@pytest.mark.parametrize(
    ("wind", "unit", "meters_per_second"),
    [
        ("5", "m/s", 5.0),
        ("18", "km/h", 5.0),
        ("10", "mph", 4.4704),
        ("10", "kn", 1852 / 360),
        ("0", "Beaufort", 0.0),
        ("4", "Beaufort", 0.836 * 4**1.5),
        ("12", "Beaufort", 0.836 * 12**1.5),
        # without a unit the unit system of Home Assistant, metric here
        ("5", None, 5.0),
    ],
)
async def test_wind_speed_units(hass, wind, unit, meters_per_second):
    """Test that the wind speed is converted from its unit."""
    set_sources(hass, -10, 50, wind, unit)
    await setup_entry(hass)
    assert value(hass, SensorType.WIND_CHILL) == pytest.approx(
        reference_wind_chill(-10, meters_per_second * 3.6), abs=1e-6
    )
    assert value(hass, SensorType.APPARENT_TEMPERATURE) == pytest.approx(
        reference_apparent_temperature(-10, 50, meters_per_second), abs=1e-6
    )
    for sensor_type in WIND_SENSOR_TYPES:
        assert sensor(hass, sensor_type).attributes["wind_speed"] == round(
            meters_per_second * 3.6, 2
        )


async def test_wind_speed_without_unit_in_us_customary_units(hass):
    """Test that a wind speed without a unit is in mph in the US customary system."""
    hass.config.units = US_CUSTOMARY_SYSTEM
    set_sources(hass, -10, 50, "10", None)
    await setup_entry(hass)
    attributes = sensor(hass, SensorType.WIND_CHILL).attributes
    assert attributes["wind_speed"] == 16.09
    # the sensor is shown in F, the wind chill is computed in C
    assert value(hass, SensorType.WIND_CHILL) == pytest.approx(
        reference_wind_chill(-10, 16.09344) * 9 / 5 + 32, abs=0.01
    )


async def test_properties(hass):
    """Test the entity properties and that the wind speed is only on the sensors of the wind."""
    set_sources(hass)
    await setup_entry(hass)
    registry = er.async_get(hass)

    for sensor_type, icon in (
        (SensorType.WIND_CHILL, "mdi:snowflake-thermometer"),
        (SensorType.APPARENT_TEMPERATURE, "mdi:thermometer-lines"),
    ):
        state = sensor(hass, sensor_type)
        assert state.attributes["device_class"] == SensorDeviceClass.TEMPERATURE
        assert state.attributes["unit_of_measurement"] == "°C"
        assert state.attributes["state_class"] == "measurement"
        assert state.attributes["icon"] == icon
        assert state.attributes["wind_speed"] == 18.0
        assert state.attributes["temperature"] == -10.0
        assert state.attributes["humidity"] == 50.0
        entry = registry.async_get(f"sensor.{NAME}_{sensor_type}")
        assert entry.entity_category is EntityCategory.DIAGNOSTIC
        assert entry.disabled_by is None
    for sensor_type in DEFAULT_SENSOR_TYPES:
        assert "wind_speed" not in sensor(hass, sensor_type).attributes
    assert "wind_speed" in SensorThermalComfort._unrecorded_attributes


async def test_created_only_with_the_wind_speed(hass):
    """Test that the sensors of the wind exist only for devices that have the sensor."""
    set_sources(hass)
    await setup_entry(hass, wind=None, name="without")
    await setup_entry(hass, name="with")
    registry = er.async_get(hass)

    for sensor_type in WIND_SENSOR_TYPES:
        assert registry.async_get(f"sensor.without_{sensor_type}") is None
        assert sensor(hass, sensor_type, "without") is None
        assert sensor(hass, sensor_type, "with") is not None
    assert SensorType.WIND_CHILL not in DEFAULT_SENSOR_TYPES
    assert SensorType.APPARENT_TEMPERATURE not in DEFAULT_SENSOR_TYPES


@pytest.mark.parametrize("outdoor", [False, True])
@pytest.mark.parametrize(
    ("temperature", "humidity"), [(-10, 50), (21, 50), (35, 70), (0, 100)]
)
async def test_existing_sensors_are_unchanged(hass, temperature, humidity, outdoor):
    """Test that the other sensors have the same states and attributes with the wind speed."""
    set_sources(hass, temperature, humidity)
    set_outdoor(hass, 0, 90)
    extra = (
        {
            CONF_OUTDOOR_TEMPERATURE_SENSOR: "sensor.out_t",
            CONF_OUTDOOR_HUMIDITY_SENSOR: "sensor.out_h",
        }
        if outdoor
        else {}
    )
    await setup_entry(hass, wind=None, name="without", **extra)
    await setup_entry(hass, name="with", **extra)
    sensor_types = DEFAULT_SENSOR_TYPES + (OUTDOOR_SENSOR_TYPES if outdoor else [])

    assert dump(hass, "with", sensor_types) == dump(hass, "without", sensor_types)
    # and after a change of the wind speed
    hass.states.async_set(WIND, "15", {"unit_of_measurement": "m/s"})
    await hass.async_block_till_done()
    assert dump(hass, "with", sensor_types) == dump(hass, "without", sensor_types)


async def test_wind_sensors_are_enabled_whatever_was_chosen(hass):
    """Test that the sensors of the wind are not among the sensors to choose."""
    set_sources(hass)
    await setup_entry(hass, **{CONF_ENABLED_SENSORS: []})
    registry = er.async_get(hass)

    assert registry.async_get(f"sensor.{NAME}_dew_point").disabled_by is not None
    for sensor_type in WIND_SENSOR_TYPES:
        assert registry.async_get(f"sensor.{NAME}_{sensor_type}").disabled_by is None


@pytest.mark.parametrize(
    ("wind", "unit"),
    [
        ("unavailable", "m/s"),
        ("unknown", "m/s"),
        ("abc", "m/s"),
        ("-1", "m/s"),
        ("-1", "Beaufort"),
        ("inf", "m/s"),
        ("nan", "m/s"),
        ("121", "m/s"),
        ("5", "°C"),
        ("5", "mm/h"),
        ("5", ["m/s"]),
    ],
)
async def test_invalid_wind_speed_does_not_touch_the_others(hass, wind, unit):
    """Test that an invalid wind speed makes only the sensors of the wind unavailable."""
    set_sources(hass)
    await setup_entry(hass)
    others = dump(hass)
    assert STATE_UNAVAILABLE not in [state for state, _ in others.values()]

    hass.states.async_set(WIND, wind, {"unit_of_measurement": unit})
    await hass.async_block_till_done()
    for sensor_type in WIND_SENSOR_TYPES:
        assert sensor(hass, sensor_type).state == STATE_UNAVAILABLE
    assert dump(hass) == others

    # and back
    hass.states.async_set(WIND, "5", {"unit_of_measurement": "m/s"})
    await hass.async_block_till_done()
    assert value(hass, SensorType.WIND_CHILL) == pytest.approx(
        reference_wind_chill(-10, 18), abs=1e-9
    )
    assert dump(hass) == others


async def test_highest_wind_speed(hass):
    """Test that a wind speed of 120 m/s is still valid."""
    set_sources(hass, -10, 50, "120")
    await setup_entry(hass)
    assert sensor(hass, SensorType.WIND_CHILL).state != STATE_UNAVAILABLE


async def test_room_failure_makes_the_wind_sensors_unavailable(hass):
    """Test that the sensors of the wind need the temperature and the humidity too."""
    set_sources(hass)
    await setup_entry(hass)

    hass.states.async_set("sensor.h", "unavailable")
    await hass.async_block_till_done()
    for sensor_type in WIND_SENSOR_TYPES + DEFAULT_SENSOR_TYPES:
        assert sensor(hass, sensor_type).state == STATE_UNAVAILABLE

    hass.states.async_set("sensor.h", "50")
    await hass.async_block_till_done()
    for sensor_type in WIND_SENSOR_TYPES + DEFAULT_SENSOR_TYPES:
        assert sensor(hass, sensor_type).state != STATE_UNAVAILABLE


@pytest.mark.parametrize("poll", [False, True])
async def test_wind_speed_that_comes_later(hass, poll):
    """Test that the sensors of the wind follow a source that is not there at the start."""
    set_sources(hass, wind=None)
    await setup_entry(hass, poll=poll, scan_interval=30)
    for sensor_type in WIND_SENSOR_TYPES:
        assert sensor(hass, sensor_type).state == STATE_UNAVAILABLE
    assert sensor(hass, SensorType.DEW_POINT).state != STATE_UNAVAILABLE

    hass.states.async_set(WIND, "5", {"unit_of_measurement": "m/s"})
    await hass.async_block_till_done()
    # the change of the availability is shown at once, also when polling
    assert value(hass, SensorType.WIND_CHILL) == pytest.approx(
        reference_wind_chill(-10, 18), abs=1e-9
    )
    assert value(hass, SensorType.APPARENT_TEMPERATURE) == pytest.approx(
        reference_apparent_temperature(-10, 50, 5), abs=1e-9
    )


async def test_wind_change_updates_only_the_sensors_of_the_wind(hass):
    """Test that a change of the wind speed does not compute the other sensors."""
    set_sources(hass)
    await setup_entry(hass)

    events = async_capture_events(hass, EVENT_STATE_CHANGED)
    with (
        patch.object(
            DeviceThermalComfort,
            "async_update",
            autospec=True,
            side_effect=DeviceThermalComfort.async_update,
        ) as update,
        patch.object(
            SensorThermalComfort,
            "async_update",
            autospec=True,
            side_effect=SensorThermalComfort.async_update,
        ) as entity_update,
    ):
        hass.states.async_set(WIND, "10", {"unit_of_measurement": "m/s"})
        await hass.async_block_till_done()
        assert update.call_count == 0
        assert {call.args[0]._sensor_type for call in entity_update.call_args_list} == (
            set(WIND_SENSOR_TYPES)
        )

    written = {
        event.data["entity_id"]
        for event in events
        if event.data["entity_id"].startswith(f"sensor.{NAME}_")
    }
    assert written == {f"sensor.{NAME}_{t}" for t in WIND_SENSOR_TYPES}
    assert value(hass, SensorType.WIND_CHILL) == pytest.approx(
        reference_wind_chill(-10, 36), abs=1e-9
    )


async def test_polling_wind_speed(hass):
    """Test that a polled device shows the changes of the wind speed with the timer."""
    set_sources(hass)
    await setup_entry(hass, poll=True, scan_interval=30)
    old = sensor(hass, SensorType.WIND_CHILL).state
    others = dump(hass)

    hass.states.async_set(WIND, "10", {"unit_of_measurement": "m/s"})
    await hass.async_block_till_done()
    assert sensor(hass, SensorType.WIND_CHILL).state == old

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=60))
    await hass.async_block_till_done()
    assert value(hass, SensorType.WIND_CHILL) == pytest.approx(
        reference_wind_chill(-10, 36), abs=1e-9
    )
    assert dump(hass) == others

    # availability changes are not waiting for the timer
    hass.states.async_set(WIND, "unavailable")
    await hass.async_block_till_done()
    assert sensor(hass, SensorType.WIND_CHILL).state == STATE_UNAVAILABLE


async def test_weather_entity_as_the_wind_speed(hass):
    """Test the wind speed of a weather entity, in its wind speed unit."""
    set_sources(hass, wind=None)
    hass.states.async_set(
        WEATHER, *weather(temperature=0, wind_speed=36, wind_speed_unit="km/h")
    )
    await setup_entry(hass, wind=WEATHER)
    assert value(hass, SensorType.WIND_CHILL) == pytest.approx(
        reference_wind_chill(-10, 36), abs=1e-9
    )

    hass.states.async_set(
        WEATHER, *weather(temperature=0, wind_speed=10, wind_speed_unit="m/s")
    )
    await hass.async_block_till_done()
    assert value(hass, SensorType.WIND_CHILL) == pytest.approx(
        reference_wind_chill(-10, 36), abs=1e-9
    )
    assert sensor(hass, SensorType.WIND_CHILL).attributes["wind_speed"] == 36.0

    # without a unit the unit system of Home Assistant
    hass.states.async_set(WEATHER, *weather(temperature=0, wind_speed=5))
    await hass.async_block_till_done()
    assert sensor(hass, SensorType.WIND_CHILL).attributes["wind_speed"] == 18.0

    # the other attributes of the weather do not update anything
    with patch.object(
        DeviceThermalComfort,
        "_wind_updated",
        autospec=True,
        side_effect=DeviceThermalComfort._wind_updated,
    ) as updated:
        hass.states.async_set(WEATHER, *weather(temperature=3, wind_speed=5))
        await hass.async_block_till_done()
        assert updated.call_count == 0

    hass.states.async_set(WEATHER, *weather(temperature=0))
    await hass.async_block_till_done()
    assert sensor(hass, SensorType.WIND_CHILL).state == STATE_UNAVAILABLE


def written_states(events, sensor_type):
    """Return the states written for a sensor."""
    return [
        event.data["new_state"].state
        for event in events
        if event.data["entity_id"] == f"sensor.{NAME}_{sensor_type}"
    ]


async def test_one_weather_entity_for_everything(hass):
    """Test one weather entity as all sources, no state is written for a mix."""
    hass.states.async_set(
        WEATHER,
        *weather(temperature=-10, humidity=50, wind_speed=5, wind_speed_unit="m/s"),
    )
    await setup_entry(
        hass,
        wind=WEATHER,
        **{CONF_TEMPERATURE_SENSOR: WEATHER, CONF_HUMIDITY_SENSOR: WEATHER},
    )
    assert value(hass, SensorType.APPARENT_TEMPERATURE) == pytest.approx(
        reference_apparent_temperature(-10, 50, 5), abs=1e-9
    )

    events = async_capture_events(hass, EVENT_STATE_CHANGED)
    hass.states.async_set(
        WEATHER,
        *weather(temperature=0, humidity=80, wind_speed=10, wind_speed_unit="m/s"),
    )
    await hass.async_block_till_done()
    written = written_states(events, SensorType.APPARENT_TEMPERATURE)
    assert len(written) == 1
    assert float(written[0]) == pytest.approx(
        reference_apparent_temperature(0, 80, 10), abs=1e-9
    )

    # a change of the wind speed only updates the sensors of the wind
    with patch.object(
        DeviceThermalComfort,
        "async_update",
        autospec=True,
        side_effect=DeviceThermalComfort.async_update,
    ) as update:
        hass.states.async_set(
            WEATHER,
            *weather(temperature=0, humidity=80, wind_speed=2, wind_speed_unit="m/s"),
        )
        await hass.async_block_till_done()
        assert update.call_count == 0
    assert value(hass, SensorType.APPARENT_TEMPERATURE) == pytest.approx(
        reference_apparent_temperature(0, 80, 2), abs=1e-9
    )


@pytest.mark.parametrize("poll", [False, True])
async def test_weather_entity_for_the_temperature_and_the_wind(hass, poll):
    """Test one weather entity as the source of the temperature and the wind, not of the humidity."""
    hass.states.async_set("sensor.h", "50")
    hass.states.async_set(
        WEATHER, *weather(temperature=-10, wind_speed=5, wind_speed_unit="m/s")
    )
    await setup_entry(
        hass,
        wind=WEATHER,
        poll=poll,
        scan_interval=30,
        **{CONF_TEMPERATURE_SENSOR: WEATHER},
    )
    assert value(hass, SensorType.WIND_CHILL) == pytest.approx(
        reference_wind_chill(-10, 18), abs=1e-9
    )

    events = async_capture_events(hass, EVENT_STATE_CHANGED)
    hass.states.async_set(
        WEATHER, *weather(temperature=-20, wind_speed=10, wind_speed_unit="m/s")
    )
    await hass.async_block_till_done()
    if poll:
        async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=60))
        await hass.async_block_till_done()
    written = written_states(events, SensorType.WIND_CHILL)
    assert len(written) == 1
    assert float(written[0]) == pytest.approx(reference_wind_chill(-20, 36), abs=1e-9)

    # the temperature and the availability of the wind change together
    hass.states.async_set(WEATHER, *weather(temperature=-5))
    await hass.async_block_till_done()
    for sensor_type in WIND_SENSOR_TYPES:
        assert sensor(hass, sensor_type).state == STATE_UNAVAILABLE
    assert sensor(hass, SensorType.DEW_POINT).state != STATE_UNAVAILABLE

    # and the wind alone
    hass.states.async_set(
        WEATHER, *weather(temperature=-5, wind_speed=5, wind_speed_unit="m/s")
    )
    await hass.async_block_till_done()
    assert value(hass, SensorType.WIND_CHILL) == pytest.approx(
        reference_wind_chill(-5, 18), abs=1e-9
    )


async def test_weather_entity_for_the_humidity_and_the_wind(hass):
    """Test one weather entity as the source of the humidity and the wind."""
    hass.states.async_set("sensor.t", "-10", {"unit_of_measurement": "°C"})
    hass.states.async_set(
        WEATHER, *weather(humidity=50, wind_speed=5, wind_speed_unit="m/s")
    )
    await setup_entry(hass, wind=WEATHER, **{CONF_HUMIDITY_SENSOR: WEATHER})
    events = async_capture_events(hass, EVENT_STATE_CHANGED)
    hass.states.async_set(
        WEATHER, *weather(humidity=80, wind_speed=10, wind_speed_unit="m/s")
    )
    await hass.async_block_till_done()
    written = written_states(events, SensorType.APPARENT_TEMPERATURE)
    assert len(written) == 1
    assert float(written[0]) == pytest.approx(
        reference_apparent_temperature(-10, 80, 10), abs=1e-9
    )


async def test_unload_unsubscribes_the_wind_speed(hass):
    """Test that nothing listens to the wind speed after the entry is gone."""
    set_sources(hass)
    entry = await setup_entry(hass)

    with patch.object(
        DeviceThermalComfort,
        "_wind_updated",
        autospec=True,
        side_effect=DeviceThermalComfort._wind_updated,
    ) as updated:
        hass.states.async_set(WIND, "6", {"unit_of_measurement": "m/s"})
        await hass.async_block_till_done()
        assert updated.call_count == 1

        assert await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()
        updated.reset_mock()
        hass.states.async_set(WIND, "7", {"unit_of_measurement": "m/s"})
        await hass.async_block_till_done()
        assert updated.call_count == 0


async def test_options_flow_adds_and_removes_the_wind_speed(hass):
    """Test the wind speed in the options flow, entities stay for later."""
    set_sources(hass)
    entry = await setup_entry(hass, wind=None, **{CONF_ENABLED_SENSORS: []})
    registry = er.async_get(hass)
    eid = f"sensor.{NAME}_wind_chill"
    assert registry.async_get(eid) is None

    async def submit(user_input):
        result = await hass.config_entries.options.async_init(entry.entry_id)
        result = await hass.config_entries.options.async_configure(
            result["flow_id"], user_input=form_input(user_input)
        )
        await hass.async_block_till_done()
        return result

    sources = {
        CONF_NAME: NAME,
        CONF_TEMPERATURE_SENSOR: "sensor.t",
        CONF_HUMIDITY_SENSOR: "sensor.h",
    }
    result = await submit({**sources, CONF_WIND_SPEED_SENSOR: WIND})
    assert result["type"] == "create_entry"
    # the entry reloaded, the sensors are there and enabled, also for an entry
    # that has no other sensor enabled
    for sensor_type in WIND_SENSOR_TYPES:
        assert registry.async_get(f"sensor.{NAME}_{sensor_type}").disabled_by is None
    assert float(hass.states.get(eid).state) == pytest.approx(
        reference_wind_chill(-10, 18), abs=1e-9
    )

    # the stored value is offered again
    result = await hass.config_entries.options.async_init(entry.entry_id)
    key = next(k for k in result["data_schema"].schema if k == CONF_WIND_SPEED_SENSOR)
    assert key.description["suggested_value"] == WIND
    hass.config_entries.options.async_abort(result["flow_id"])

    # unknown sensor
    result = await submit({**sources, CONF_WIND_SPEED_SENSOR: "sensor.no_such"})
    assert result["type"] == "form"
    assert result["errors"] == {"base": "wind_speed_not_found"}

    # cleared by the form: the sensors are not provided any more, the registry
    # keeps them
    result = await submit(sources)
    assert result["type"] == "create_entry"
    assert entry.options.get(CONF_WIND_SPEED_SENSOR) is None
    assert get_value(entry, CONF_WIND_SPEED_SENSOR) is None
    assert registry.async_get(eid) is not None
    assert hass.states.get(eid).state == STATE_UNAVAILABLE

    # and back, the same entities work again
    await submit({**sources, CONF_WIND_SPEED_SENSOR: WIND})
    assert float(hass.states.get(eid).state) == pytest.approx(
        reference_wind_chill(-10, 18), abs=1e-9
    )
    assert len(registry.entities.get_entries_for_config_entry_id(entry.entry_id)) == (
        len(DEFAULT_SENSOR_TYPES) + len(WIND_SENSOR_TYPES)
    )


async def test_options_flow_clears_the_wind_speed_of_the_data(hass):
    """Test that a wind speed of the setup is removed, the data must not bring it back."""
    set_sources(hass)
    entry = await setup_entry(hass)
    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input=form_input(
            {
                CONF_NAME: NAME,
                CONF_TEMPERATURE_SENSOR: "sensor.t",
                CONF_HUMIDITY_SENSOR: "sensor.h",
            }
        ),
    )
    await hass.async_block_till_done()
    assert result["type"] == "create_entry"
    assert entry.data[CONF_WIND_SPEED_SENSOR] == WIND
    assert entry.options[CONF_WIND_SPEED_SENSOR] is None
    assert get_value(entry, CONF_WIND_SPEED_SENSOR) is None
    assert hass.states.get(f"sensor.{NAME}_wind_chill").state == STATE_UNAVAILABLE


async def test_options_flow_keeps_a_wind_speed_that_is_missing_now(hass):
    """Test that unrelated options can be saved while the wind speed is not there."""
    set_sources(hass, wind=None)
    entry = await setup_entry(hass)
    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input=form_input(
            {
                CONF_NAME: "renamed",
                CONF_TEMPERATURE_SENSOR: "sensor.t",
                CONF_HUMIDITY_SENSOR: "sensor.h",
                CONF_WIND_SPEED_SENSOR: WIND,
            }
        ),
    )
    await hass.async_block_till_done()
    assert result["type"] == "create_entry"


async def test_options_flow_keeps_a_source_the_filters_hide(hass):
    """Test that a source of the entry that is not offered any more stays selectable."""
    set_sources(hass)
    entry = await setup_entry(hass)
    hass.config_entries.async_update_entry(
        entry,
        data={
            **entry.data,
            CONF_TEMPERATURE_SENSOR: "sensor.renamed_own_temperature",
            CONF_HUMIDITY_SENSOR: "sensor.renamed_own_humidity",
        },
    )
    schema = build_schema(entry, hass, step="init")
    included = {
        str(key): key.default()
        for key in schema.schema
        if key.default is not vol.UNDEFINED
    }
    assert included[CONF_TEMPERATURE_SENSOR] == "sensor.renamed_own_temperature"
    for key, value in schema.schema.items():
        if key in (CONF_TEMPERATURE_SENSOR, CONF_HUMIDITY_SENSOR):
            # the default has to be valid for the selector, or the form cannot be saved
            value(included[str(key)])


async def test_check_input_wind_speed(hass):
    """Test the error of the wind speed sensor."""
    set_sources(hass)
    hass.states.async_set(WEATHER, *weather(wind_speed=3))
    sources = {CONF_TEMPERATURE_SENSOR: "sensor.t", CONF_HUMIDITY_SENSOR: "sensor.h"}

    assert check_input(hass, sources) == {}
    assert check_input(hass, {**sources, CONF_WIND_SPEED_SENSOR: WIND}) == {}
    assert check_input(hass, {**sources, CONF_WIND_SPEED_SENSOR: WEATHER}) == {}
    assert check_input(hass, {**sources, CONF_WIND_SPEED_SENSOR: "sensor.no"}) == {
        "base": "wind_speed_not_found"
    }

    # a sensor the entry has already can be missing for a while
    hass.states.async_remove(WIND)
    with_wind = {**sources, CONF_WIND_SPEED_SENSOR: WIND}
    assert check_input(hass, with_wind) == {"base": "wind_speed_not_found"}
    assert check_input(hass, with_wind, with_wind) == {}
    assert check_input(
        hass, with_wind, {**with_wind, CONF_WIND_SPEED_SENSOR: "sensor.old"}
    ) == {"base": "wind_speed_not_found"}


async def test_wind_speed_selector(hass, hass_client):
    """Test the wind speed field as the frontend receives it, and the setup with it."""
    set_sources(hass)
    assert await async_setup_component(hass, "config", {})
    client = await hass_client()

    response = await client.post(
        "/api/config/config_entries/flow", json={"handler": DOMAIN}
    )
    form = await response.json()
    names = [f["name"] for f in form["data_schema"]]
    assert names.index("pressure_sensor") < names.index("wind_speed_sensor")
    field = next(f for f in form["data_schema"] if f["name"] == "wind_speed_sensor")
    assert field["optional"] is True
    filters = field["selector"]["entity"]["filter"]
    assert len(filters) == 2
    assert filters[0]["domain"] == ["sensor"]
    assert set(filters[0]["device_class"]) == {"wind_speed", "speed"}
    assert filters[1]["domain"] == ["weather"]
    advanced = next(f for f in form["data_schema"] if f["name"] == "advanced")
    assert "wind_speed_sensor" not in [f["name"] for f in advanced["schema"]]
    enabled = next(f for f in advanced["schema"] if f["name"] == "enabled_sensors")
    assert not set(enabled["options"]) & set(map(str, WIND_SENSOR_TYPES))

    response = await client.post(
        f"/api/config/config_entries/flow/{form['flow_id']}",
        json=form_input(
            {
                **ADVANCED_USER_INPUT,
                CONF_TEMPERATURE_SENSOR: "sensor.t",
                CONF_HUMIDITY_SENSOR: "sensor.h",
                CONF_WIND_SPEED_SENSOR: WIND,
            }
        ),
    )
    assert (await response.json())["type"] == "create_entry"
    (entry,) = hass.config_entries.async_entries(DOMAIN)
    assert entry.data[CONF_WIND_SPEED_SENSOR] == WIND
    await hass.async_block_till_done()
    registry = er.async_get(hass)
    for sensor_type in WIND_SENSOR_TYPES:
        entity_id = registry.async_get_entity_id(
            "sensor", DOMAIN, f"{entry.unique_id}{sensor_type}"
        )
        assert registry.async_get(entity_id).disabled_by is None
        assert hass.states.get(entity_id).state != STATE_UNAVAILABLE


async def test_own_sensors_are_recognized_by_the_registry(hass):
    """Test that sensors of other integrations with the name of a sensor type can be chosen."""
    set_sources(hass)
    await setup_entry(hass)
    registry = er.async_get(hass)
    # a sensor of another integration with the name of one of the sensors
    other = registry.async_get_or_create(
        "sensor", "other", "outdoor", suggested_object_id="outdoor_wind_chill"
    )
    hass.states.async_set(other.entity_id, "-5", {"unit_of_measurement": "°C"})
    # an own sensor with another name
    renamed = registry.async_get_or_create(
        "sensor", DOMAIN, "renamed", suggested_object_id="balcony_feel"
    )
    hass.states.async_set(renamed.entity_id, "-5", {"unit_of_measurement": "°C"})
    # without a registry entry the name decides
    hass.states.async_set("sensor.balcony_apparent_temperature", "-5")

    offered = get_sensors_by_device_class(
        registry, hass, SensorDeviceClass.TEMPERATURE, include_all=True
    )
    assert other.entity_id in offered
    assert "sensor.t" in offered
    assert renamed.entity_id not in offered
    assert "sensor.balcony_apparent_temperature" not in offered
    for sensor_type in DEFAULT_SENSOR_TYPES + WIND_SENSOR_TYPES:
        assert f"sensor.{NAME}_{sensor_type}" not in offered


async def test_yaml_with_and_without_the_wind_speed(hass, caplog):
    """Test the sensors of the wind in YAML, by default, for a device and for all of them."""
    set_sources(hass)
    with caplog.at_level(logging.WARNING):
        assert await async_setup_component(
            hass,
            DOMAIN,
            {
                DOMAIN: [
                    {
                        "sensor": [
                            {
                                "name": "yaml_with",
                                CONF_TEMPERATURE_SENSOR: "sensor.t",
                                CONF_HUMIDITY_SENSOR: "sensor.h",
                                CONF_WIND_SPEED_SENSOR: WIND,
                                "unique_id": "with",
                            },
                            {
                                "name": "yaml_without",
                                CONF_TEMPERATURE_SENSOR: "sensor.t",
                                CONF_HUMIDITY_SENSOR: "sensor.h",
                                "unique_id": "without",
                            },
                        ]
                    },
                    {
                        CONF_WIND_SPEED_SENSOR: WIND,
                        "sensor": [
                            {
                                "name": "yaml_global",
                                CONF_TEMPERATURE_SENSOR: "sensor.t",
                                CONF_HUMIDITY_SENSOR: "sensor.h",
                                "unique_id": "global",
                            },
                        ],
                    },
                ]
            },
        )
        await hass.async_block_till_done()
    assert "wind" not in caplog.text.lower()
    for sensor_type in WIND_SENSOR_TYPES:
        assert sensor(hass, sensor_type, "yaml_without") is None
        for name in ("yaml_with", "yaml_global"):
            assert sensor(hass, sensor_type, name).state != STATE_UNAVAILABLE
    for name in ("yaml_with", "yaml_global"):
        assert value(hass, SensorType.WIND_CHILL, name) == pytest.approx(
            reference_wind_chill(-10, 18), abs=1e-9
        )
    assert dump(hass, "yaml_with") == dump(hass, "yaml_without")


@pytest.mark.parametrize("wind", [False, True])
async def test_yaml_sensor_types_with_the_wind_types(hass, caplog, wind):
    """Test that sensor_types with the wind types need the wind speed, with a warning otherwise."""
    set_sources(hass)
    device = {CONF_TEMPERATURE_SENSOR: "sensor.t", CONF_HUMIDITY_SENSOR: "sensor.h"}
    if wind:
        device[CONF_WIND_SPEED_SENSOR] = WIND
    with caplog.at_level(logging.WARNING):
        assert await async_setup_component(
            hass,
            DOMAIN,
            yaml_config(
                device=device,
                sensor_types=["dew_point", "wind_chill", "apparent_temperature"],
            ),
        )
        await hass.async_block_till_done()
    assert sensor(hass, SensorType.DEW_POINT, "yaml_room") is not None
    assert sensor(hass, SensorType.HEAT_INDEX, "yaml_room") is None
    for sensor_type in WIND_SENSOR_TYPES:
        assert (sensor(hass, sensor_type, "yaml_room") is not None) is wind
    assert ("wind_chill, apparent_temperature" in caplog.text) is not wind
