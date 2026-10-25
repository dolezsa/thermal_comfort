"""Test the sensors that compare the room with the outdoor air."""

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

from custom_components.thermal_comfort import sensor as sensor_module
from custom_components.thermal_comfort.const import DOMAIN
from custom_components.thermal_comfort.sensor import (
    CONF_ENABLED_SENSORS,
    CONF_HUMIDITY_SENSOR,
    CONF_OUTDOOR_HUMIDITY_SENSOR,
    CONF_OUTDOOR_TEMPERATURE_SENSOR,
    CONF_TEMPERATURE_SENSOR,
    DEFAULT_SENSOR_TYPES,
    OUTDOOR_SENSOR_TYPES,
    DeviceThermalComfort,
    SensorThermalComfort,
    SensorType,
    VentilationAdvice,
    VentilationNeed,
    _absolute_humidity,
)
from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.const import CONF_NAME, EVENT_STATE_CHANGED, STATE_UNAVAILABLE
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

from .const import ADVANCED_USER_INPUT, form_input
from .test_attribute_source import WEATHER, all_states, weather

NAME = "test_thermal_comfort"


def reference_absolute_humidity(temperature, humidity):
    """Absolute humidity from the gas law, independent of the code (g/m3)."""
    saturation = 6.112 * math.exp(17.62 * temperature / (243.12 + temperature))
    return saturation * humidity / 100 * 100 / (461.5 * (temperature + 273.15)) * 1000


def sensor(hass, sensor_type, name=NAME):
    """Return the state of a sensor."""
    return hass.states.get(f"sensor.{name}_{sensor_type}")


def set_indoor(hass, temperature, humidity):
    """Set the sources of the room."""
    hass.states.async_set("sensor.in_t", str(temperature))
    hass.states.async_set("sensor.in_h", str(humidity))


def set_outdoor(hass, temperature, humidity):
    """Set the sources of the outdoor air."""
    hass.states.async_set("sensor.out_t", str(temperature))
    hass.states.async_set("sensor.out_h", str(humidity))


async def setup_entry(hass, outdoor=True, name=NAME, **extra):
    """Set up a device, with the sensors of the outdoor air if wanted."""
    data = {
        **ADVANCED_USER_INPUT,
        CONF_NAME: name,
        CONF_TEMPERATURE_SENSOR: "sensor.in_t",
        CONF_HUMIDITY_SENSOR: "sensor.in_h",
        CONF_ENABLED_SENSORS: list(DEFAULT_SENSOR_TYPES),
        **extra,
    }
    if outdoor:
        data |= {
            CONF_OUTDOOR_TEMPERATURE_SENSOR: "sensor.out_t",
            CONF_OUTDOOR_HUMIDITY_SENSOR: "sensor.out_h",
        }
    entry = MockConfigEntry(domain=DOMAIN, data=data, entry_id=name, unique_id=name)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


def humidity_for_excess(indoor, outdoor_temperature, excess):
    """Return the outdoor humidity that gives a moisture excess."""
    low, high = 0.5, 100.0
    for _ in range(60):
        middle = (low + high) / 2
        if indoor - _absolute_humidity(outdoor_temperature, middle) > excess:
            low = middle
        else:
            high = middle
    return round((low + high) / 2, 6)


# indoor temperature and humidity, outdoor temperature and humidity, then what
# the sensors show: the excess, the outdoor dew point, the relative humidity
# after airing, the advice and the need
CASES = {
    "winter": (
        (21, 50, 0, 90),
        (
            4.79,
            -1.45,
            22.1,
            VentilationAdvice.DRIER_OUTSIDE,
            VentilationNeed.ABOVE_LIMIT,
        ),
    ),
    "spring": (
        (21, 60, 15, 85),
        (0.09, 12.5, 58.3, VentilationAdvice.SIMILAR, VentilationNeed.NOT_WINTER),
    ),
    "summer evening": (
        (24, 60, 30, 70),
        (
            -8.19,
            23.9,
            99.6,
            VentilationAdvice.CONDENSATION_RISK,
            VentilationNeed.NOT_WINTER,
        ),
    ),
    "cellar": (
        (15, 70, 28, 65),
        (
            -8.72,
            20.8,
            100.0,
            VentilationAdvice.CONDENSATION_RISK,
            VentilationNeed.NOT_WINTER,
        ),
    ),
    "after a shower": (
        (23, 70, 2, 80),
        (
            9.94,
            -1.1,
            20.1,
            VentilationAdvice.DRIER_OUTSIDE,
            VentilationNeed.ABOVE_LIMIT,
        ),
    ),
    "within the limit": (
        (20, 40, 5, 60),
        (
            2.83,
            -2.1,
            22.4,
            VentilationAdvice.DRIER_OUTSIDE,
            VentilationNeed.WITHIN_LIMIT,
        ),
    ),
}


@pytest.mark.parametrize(("indoor_outdoor", "expected"), CASES.values(), ids=CASES)
async def test_values(hass, indoor_outdoor, expected):
    """Test the sensors of the outdoor air with the values of known situations."""
    temperature, humidity, outdoor_temperature, outdoor_humidity = indoor_outdoor
    excess, dew_point, ventilated, advice, need = expected
    set_indoor(hass, temperature, humidity)
    set_outdoor(hass, outdoor_temperature, outdoor_humidity)
    await setup_entry(hass)

    # the absolute humidity of the gas law agrees with the formula of the code
    reference = reference_absolute_humidity(
        temperature, humidity
    ) - reference_absolute_humidity(outdoor_temperature, outdoor_humidity)
    state = sensor(hass, SensorType.MOISTURE_EXCESS)
    assert float(state.state) == pytest.approx(excess, abs=0.01)
    assert float(state.state) == pytest.approx(reference, abs=0.1)
    attributes = state.attributes
    assert attributes["outdoor_temperature"] == outdoor_temperature
    assert attributes["outdoor_humidity"] == outdoor_humidity
    assert attributes["outdoor_dew_point"] == pytest.approx(dew_point, abs=0.1)
    assert attributes["ventilated_relative_humidity"] == pytest.approx(
        ventilated, abs=0.1
    )
    assert attributes["outdoor_absolute_humidity"] == pytest.approx(
        reference_absolute_humidity(outdoor_temperature, outdoor_humidity), abs=0.1
    )
    assert sensor(hass, SensorType.VENTILATION_ADVICE).state == advice
    assert sensor(hass, SensorType.VENTILATION_NEED).state == need
    for sensor_type in (SensorType.VENTILATION_ADVICE, SensorType.VENTILATION_NEED):
        attributes = sensor(hass, sensor_type).attributes
        assert attributes["outdoor_temperature"] == outdoor_temperature
        assert attributes["outdoor_humidity"] == outdoor_humidity


async def test_ventilated_humidity_is_not_the_ratio_of_the_absolute_humidity(hass):
    """Test that the warmed outdoor air keeps its vapor pressure, not its mass of water."""
    set_indoor(hass, 21, 50)
    set_outdoor(hass, 0, 90)
    await setup_entry(hass)

    ratio_of_absolute_humidity = (
        reference_absolute_humidity(0, 90) / reference_absolute_humidity(21, 100) * 100
    )
    ventilated = sensor(hass, SensorType.MOISTURE_EXCESS).attributes[
        "ventilated_relative_humidity"
    ]
    assert ratio_of_absolute_humidity == pytest.approx(23.8, abs=0.1)
    assert ventilated == pytest.approx(22.1, abs=0.1)


@pytest.mark.parametrize("inside", [True, False])
@pytest.mark.parametrize("edge", [1.0, -1.0])
async def test_band_of_the_advice(hass, edge, inside):
    """Test that the air is similar up to a difference of 1 g/m3 and not at it."""
    set_indoor(hass, 21, 50)
    # the outdoor air at 15 C, no condensation risk for the room at 21 C
    target = edge * (0.98 if inside else 1.02)
    set_outdoor(hass, 15, humidity_for_excess(_absolute_humidity(21, 50), 15, target))
    await setup_entry(hass)

    excess = float(sensor(hass, SensorType.MOISTURE_EXCESS).state)
    assert excess == pytest.approx(target, abs=0.005)
    advice = sensor(hass, SensorType.VENTILATION_ADVICE).state
    if inside:
        assert advice == VentilationAdvice.SIMILAR
    elif edge > 0:
        assert advice == VentilationAdvice.DRIER_OUTSIDE
    else:
        assert advice == VentilationAdvice.MORE_HUMID_OUTSIDE


async def test_more_humid_outside_without_condensation_risk(hass):
    """Test the third state of the advice, outdoor air that is more humid and not near saturation."""
    set_indoor(hass, 21, 40)
    set_outdoor(hass, 21, 60)
    await setup_entry(hass)

    assert float(sensor(hass, SensorType.MOISTURE_EXCESS).state) < -1
    attributes = sensor(hass, SensorType.MOISTURE_EXCESS).attributes
    assert attributes["ventilated_relative_humidity"] == pytest.approx(60, abs=0.1)
    assert (
        sensor(hass, SensorType.VENTILATION_ADVICE).state
        == VentilationAdvice.MORE_HUMID_OUTSIDE
    )


@pytest.mark.parametrize(
    ("humidity", "expected"),
    [
        (79.0, VentilationAdvice.MORE_HUMID_OUTSIDE),
        (80.0, VentilationAdvice.CONDENSATION_RISK),
        (81.0, VentilationAdvice.CONDENSATION_RISK),
    ],
)
async def test_condensation_risk_limit(hass, humidity, expected):
    """Test that the advice warns from 80 % relative humidity after airing."""
    set_indoor(hass, 21, 30)
    set_outdoor(hass, 21, humidity)
    await setup_entry(hass)
    assert sensor(hass, SensorType.VENTILATION_ADVICE).state == expected


@pytest.mark.parametrize("above", [True, False])
async def test_limit_of_the_need(hass, above):
    """Test that the need is above the limit for more than 3 g/m3."""
    set_indoor(hass, 21, 42)
    humidity = humidity_for_excess(
        _absolute_humidity(21, 42), 0, 3.0 + (0.02 if above else -0.02)
    )
    set_outdoor(hass, 0, humidity)
    await setup_entry(hass)

    excess = float(sensor(hass, SensorType.MOISTURE_EXCESS).state)
    assert (excess > 3) is above
    assert sensor(hass, SensorType.VENTILATION_NEED).state == (
        VentilationNeed.ABOVE_LIMIT if above else VentilationNeed.WITHIN_LIMIT
    )


@pytest.mark.parametrize(
    ("outdoor_temperature", "expected"),
    [
        (9.9, VentilationNeed.ABOVE_LIMIT),
        (10.0, VentilationNeed.NOT_WINTER),
        (10.1, VentilationNeed.NOT_WINTER),
    ],
)
async def test_winter_of_the_need(hass, outdoor_temperature, expected):
    """Test that the need is only looked at below an outdoor temperature of 10 C."""
    set_indoor(hass, 22, 70)
    set_outdoor(hass, outdoor_temperature, 20)
    await setup_entry(hass)
    assert float(sensor(hass, SensorType.MOISTURE_EXCESS).state) > 3
    assert sensor(hass, SensorType.VENTILATION_NEED).state == expected


async def test_properties(hass):
    """Test the entity properties of the sensors."""
    set_indoor(hass, 21, 50)
    set_outdoor(hass, 0, 90)
    await setup_entry(hass)
    registry = er.async_get(hass)

    excess = sensor(hass, SensorType.MOISTURE_EXCESS)
    assert excess.attributes["unit_of_measurement"] == "g/m³"
    assert "device_class" not in excess.attributes
    assert excess.attributes["state_class"] == "measurement"
    for sensor_type, options in (
        (SensorType.VENTILATION_ADVICE, list(map(str, VentilationAdvice))),
        (SensorType.VENTILATION_NEED, list(map(str, VentilationNeed))),
    ):
        state = sensor(hass, sensor_type)
        assert state.attributes["device_class"] == SensorDeviceClass.ENUM
        assert state.attributes["options"] == options
    for sensor_type in OUTDOOR_SENSOR_TYPES:
        entry = registry.async_get(f"sensor.{NAME}_{sensor_type}")
        assert entry.entity_category is None
        assert entry.disabled_by is None
    assert {
        "outdoor_temperature",
        "outdoor_humidity",
        "outdoor_absolute_humidity",
        "outdoor_dew_point",
    } <= SensorThermalComfort._unrecorded_attributes


async def test_created_only_with_the_outdoor_sensors(hass):
    """Test that the sensors of the outdoor air exist for devices that have the sensors."""
    set_indoor(hass, 21, 50)
    set_outdoor(hass, 0, 90)
    await setup_entry(hass, outdoor=False, name="without")
    await setup_entry(hass, name="with")
    registry = er.async_get(hass)

    for sensor_type in OUTDOOR_SENSOR_TYPES:
        assert registry.async_get(f"sensor.without_{sensor_type}") is None
        assert sensor(hass, sensor_type, "without") is None
        assert sensor(hass, sensor_type, "with") is not None
    for sensor_type in DEFAULT_SENSOR_TYPES:
        assert sensor(hass, sensor_type, "without") is not None
        assert sensor(hass, sensor_type, "with") is not None
    # the sensors of the room are the same with and without the outdoor air
    assert all_states(hass, "with") == all_states(hass, "without")


async def test_outdoor_sensors_are_enabled_whatever_was_chosen(hass):
    """Test that the sensors of the outdoor air are not among the sensors to choose."""
    set_indoor(hass, 21, 50)
    set_outdoor(hass, 0, 90)
    await setup_entry(hass, **{CONF_ENABLED_SENSORS: []})
    registry = er.async_get(hass)

    assert registry.async_get(f"sensor.{NAME}_dew_point").disabled_by is not None
    for sensor_type in OUTDOOR_SENSOR_TYPES:
        assert registry.async_get(f"sensor.{NAME}_{sensor_type}").disabled_by is None


async def test_outdoor_failure_does_not_touch_the_room(hass):
    """Test that the sensors of the room do not depend on the outdoor air."""
    set_indoor(hass, 21, 50)
    set_outdoor(hass, 0, 90)
    await setup_entry(hass)
    room = all_states(hass)

    for state in ("unavailable", "unknown", "abc"):
        hass.states.async_set("sensor.out_t", state)
        await hass.async_block_till_done()
        for sensor_type in OUTDOOR_SENSOR_TYPES:
            assert sensor(hass, sensor_type).state == STATE_UNAVAILABLE
        assert all_states(hass) == room

    hass.states.async_set("sensor.out_t", "0")
    await hass.async_block_till_done()
    assert float(sensor(hass, SensorType.MOISTURE_EXCESS).state) == pytest.approx(
        4.79, abs=0.01
    )

    hass.states.async_set("sensor.out_h", "120")
    await hass.async_block_till_done()
    assert sensor(hass, SensorType.VENTILATION_NEED).state == STATE_UNAVAILABLE
    assert all_states(hass) == room


async def test_room_failure_makes_everything_unavailable(hass):
    """Test that the sensors of the outdoor air need the room too."""
    set_indoor(hass, 21, 50)
    set_outdoor(hass, 0, 90)
    await setup_entry(hass)

    hass.states.async_set("sensor.in_t", "unavailable")
    await hass.async_block_till_done()
    for sensor_type in OUTDOOR_SENSOR_TYPES + DEFAULT_SENSOR_TYPES:
        assert sensor(hass, sensor_type).state == STATE_UNAVAILABLE

    hass.states.async_set("sensor.in_t", "21")
    await hass.async_block_till_done()
    for sensor_type in OUTDOOR_SENSOR_TYPES + DEFAULT_SENSOR_TYPES:
        assert sensor(hass, sensor_type).state != STATE_UNAVAILABLE


@pytest.mark.parametrize("poll", [False, True])
async def test_outdoor_air_that_comes_later(hass, poll):
    """Test that the sensors of the outdoor air follow the sources that are not there at the start."""
    set_indoor(hass, 21, 50)
    await setup_entry(hass, poll=poll, scan_interval=30)
    for sensor_type in OUTDOOR_SENSOR_TYPES:
        assert sensor(hass, sensor_type).state == STATE_UNAVAILABLE
    assert sensor(hass, SensorType.DEW_POINT).state != STATE_UNAVAILABLE

    set_outdoor(hass, 0, 90)
    await hass.async_block_till_done()
    # the change of the availability is shown at once, also when polling
    assert (
        sensor(hass, SensorType.VENTILATION_NEED).state == VentilationNeed.ABOVE_LIMIT
    )
    assert float(sensor(hass, SensorType.MOISTURE_EXCESS).state) == pytest.approx(
        4.79, abs=0.01
    )


async def test_outdoor_air_that_is_there_at_the_start(hass):
    """Test that the first computation already has the outdoor air."""
    set_indoor(hass, 21, 50)
    set_outdoor(hass, 0, 90)
    await setup_entry(hass)
    assert float(sensor(hass, SensorType.MOISTURE_EXCESS).state) == pytest.approx(
        4.79, abs=0.01
    )


async def test_outdoor_change_updates_only_the_sensors_of_the_outdoor_air(hass):
    """Test that a change of the outdoor air does not compute the sensors of the room."""
    set_indoor(hass, 21, 50)
    set_outdoor(hass, 0, 90)
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
        patch.object(
            sensor_module,
            "_dew_point",
            side_effect=sensor_module._dew_point,
        ) as dew_point,
    ):
        set_outdoor(hass, 5, 80)
        await hass.async_block_till_done()
        assert update.call_count == 0
        # only the sensors of the outdoor air are asked for a new state
        assert {call.args[0]._sensor_type for call in entity_update.call_args_list} == (
            set(OUTDOOR_SENSOR_TYPES)
        )
        # the dew point of the outdoor air only, the room has its own. The
        # temperature and the humidity are two entities, so there is one
        # computation for each, like for the room.
        assert [call.args for call in dew_point.call_args_list] == [
            (5.0, 90.0),
            (5.0, 80.0),
        ]

    written = {
        event.data["entity_id"]
        for event in events
        if event.data["entity_id"].startswith("sensor.test_thermal_comfort_")
    }
    assert written == {f"sensor.{NAME}_{t}" for t in OUTDOOR_SENSOR_TYPES}


async def test_polling_outdoor_air(hass):
    """Test that a polled device shows the changes of the outdoor air with the timer."""
    set_indoor(hass, 21, 50)
    set_outdoor(hass, 0, 90)
    await setup_entry(hass, poll=True, scan_interval=30)
    old = sensor(hass, SensorType.MOISTURE_EXCESS).state

    set_outdoor(hass, 5, 80)
    await hass.async_block_till_done()
    assert sensor(hass, SensorType.MOISTURE_EXCESS).state == old

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=60))
    await hass.async_block_till_done()
    assert sensor(hass, SensorType.MOISTURE_EXCESS).state != old

    # availability changes are not waiting for the timer
    hass.states.async_set("sensor.out_t", "unavailable")
    await hass.async_block_till_done()
    assert sensor(hass, SensorType.MOISTURE_EXCESS).state == STATE_UNAVAILABLE


async def test_weather_entity_as_the_outdoor_air(hass):
    """Test that one weather entity is the source of both outdoor values."""
    set_indoor(hass, 21, 50)
    hass.states.async_set(WEATHER, *weather(temperature=0, humidity=90))
    await setup_entry(
        hass,
        outdoor=False,
        **{
            CONF_OUTDOOR_TEMPERATURE_SENSOR: WEATHER,
            CONF_OUTDOOR_HUMIDITY_SENSOR: WEATHER,
        },
    )
    assert float(sensor(hass, SensorType.MOISTURE_EXCESS).state) == pytest.approx(
        4.79, abs=0.01
    )

    # both values change with one event, no state is written for a mix
    events = async_capture_events(hass, EVENT_STATE_CHANGED)
    hass.states.async_set(WEATHER, *weather(temperature=10, humidity=40))
    await hass.async_block_till_done()
    written = [
        event.data["new_state"].state
        for event in events
        if event.data["entity_id"] == f"sensor.{NAME}_moisture_excess"
    ]
    assert len(written) == 1
    assert float(written[0]) == pytest.approx(
        reference_absolute_humidity(21, 50) - reference_absolute_humidity(10, 40),
        abs=0.05,
    )

    # the other attributes of the weather do not update anything
    with patch.object(
        DeviceThermalComfort,
        "_outdoor_updated",
        autospec=True,
        side_effect=DeviceThermalComfort._outdoor_updated,
    ) as updated:
        hass.states.async_set(WEATHER, *weather(temperature=10, humidity=40, wind=3))
        await hass.async_block_till_done()
        assert updated.call_count == 0


async def test_unload_unsubscribes_the_outdoor_air(hass):
    """Test that nothing listens to the outdoor air after the entry is gone."""
    set_indoor(hass, 21, 50)
    set_outdoor(hass, 0, 90)
    entry = await setup_entry(hass)

    with patch.object(
        DeviceThermalComfort,
        "_outdoor_updated",
        autospec=True,
        side_effect=DeviceThermalComfort._outdoor_updated,
    ) as updated:
        set_outdoor(hass, 1, 90)
        await hass.async_block_till_done()
        assert updated.call_count == 1

        assert await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()
        updated.reset_mock()
        set_outdoor(hass, 2, 90)
        await hass.async_block_till_done()
        assert updated.call_count == 0


async def test_options_flow_adds_and_removes_the_outdoor_air(hass):
    """Test the outdoor sensors in the options flow, entities stay for later."""
    set_indoor(hass, 21, 50)
    set_outdoor(hass, 0, 90)
    entry = await setup_entry(hass, outdoor=False)
    registry = er.async_get(hass)
    eid = f"sensor.{NAME}_moisture_excess"
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
        CONF_TEMPERATURE_SENSOR: "sensor.in_t",
        CONF_HUMIDITY_SENSOR: "sensor.in_h",
    }
    result = await submit(
        {
            **sources,
            CONF_OUTDOOR_TEMPERATURE_SENSOR: "sensor.out_t",
            CONF_OUTDOOR_HUMIDITY_SENSOR: "sensor.out_h",
        }
    )
    assert result["type"] == "create_entry"
    # the entry reloaded, the sensors are there and enabled
    assert registry.async_get(eid) is not None
    assert registry.async_get(eid).disabled_by is None
    assert float(hass.states.get(eid).state) == pytest.approx(4.79, abs=0.01)

    # removed again: the sensors are not provided any more, the registry keeps them
    result = await submit(sources)
    assert result["type"] == "create_entry"
    assert entry.options.get(CONF_OUTDOOR_TEMPERATURE_SENSOR) is None
    assert registry.async_get(eid) is not None
    assert hass.states.get(eid).state == STATE_UNAVAILABLE
    assert hass.states.get(f"sensor.{NAME}_dew_point").state != STATE_UNAVAILABLE

    # and back, the same entities work again
    await submit(
        {
            **sources,
            CONF_OUTDOOR_TEMPERATURE_SENSOR: "sensor.out_t",
            CONF_OUTDOOR_HUMIDITY_SENSOR: "sensor.out_h",
        }
    )
    assert float(hass.states.get(eid).state) == pytest.approx(4.79, abs=0.01)
    assert len(registry.entities.get_entries_for_config_entry_id(entry.entry_id)) == 22


def yaml_config(**options):
    """Return the YAML configuration with a room."""
    device = {
        "name": "yaml_room",
        CONF_TEMPERATURE_SENSOR: "sensor.in_t",
        CONF_HUMIDITY_SENSOR: "sensor.in_h",
        "unique_id": "yaml_room_id",
    }
    device |= options.pop("device", {})
    return {DOMAIN: [{"sensor": [device], **options}]}


async def test_yaml_with_and_without_the_outdoor_air(hass, caplog):
    """Test the sensors of the outdoor air in YAML, by default and with sensor_types."""
    set_indoor(hass, 21, 50)
    set_outdoor(hass, 0, 90)
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
                                CONF_TEMPERATURE_SENSOR: "sensor.in_t",
                                CONF_HUMIDITY_SENSOR: "sensor.in_h",
                                CONF_OUTDOOR_TEMPERATURE_SENSOR: "sensor.out_t",
                                CONF_OUTDOOR_HUMIDITY_SENSOR: "sensor.out_h",
                                "unique_id": "with",
                            },
                            {
                                "name": "yaml_without",
                                CONF_TEMPERATURE_SENSOR: "sensor.in_t",
                                CONF_HUMIDITY_SENSOR: "sensor.in_h",
                                "unique_id": "without",
                            },
                        ]
                    }
                ]
            },
        )
        await hass.async_block_till_done()
    # no warning for the devices that did not ask for them
    assert "outdoor" not in caplog.text.lower()
    for sensor_type in OUTDOOR_SENSOR_TYPES:
        assert sensor(hass, sensor_type, "yaml_with") is not None
        assert sensor(hass, sensor_type, "yaml_without") is None
    assert float(sensor(hass, SensorType.MOISTURE_EXCESS, "yaml_with").state) == (
        pytest.approx(4.79, abs=0.01)
    )


async def test_yaml_sensor_types_with_the_outdoor_types_need_the_outdoor_air(
    hass, caplog
):
    """Test that sensor_types with the outdoor types are skipped, with a warning, for a room without."""
    set_indoor(hass, 21, 50)
    set_outdoor(hass, 0, 90)
    with caplog.at_level(logging.WARNING):
        assert await async_setup_component(
            hass,
            DOMAIN,
            yaml_config(
                sensor_types=["dew_point", "moisture_excess", "ventilation_need"]
            ),
        )
        await hass.async_block_till_done()
    assert "moisture_excess, ventilation_need" in caplog.text
    assert sensor(hass, SensorType.DEW_POINT, "yaml_room") is not None
    assert sensor(hass, SensorType.MOISTURE_EXCESS, "yaml_room") is None
    assert sensor(hass, SensorType.VENTILATION_NEED, "yaml_room") is None


async def test_yaml_global_outdoor_sensors(hass):
    """Test that the outdoor sensors can be given once for all the rooms."""
    set_indoor(hass, 21, 50)
    set_outdoor(hass, 0, 90)
    assert await async_setup_component(
        hass,
        DOMAIN,
        yaml_config(
            **{
                CONF_OUTDOOR_TEMPERATURE_SENSOR: "sensor.out_t",
                CONF_OUTDOOR_HUMIDITY_SENSOR: "sensor.out_h",
            }
        ),
    )
    await hass.async_block_till_done()
    assert float(sensor(hass, SensorType.MOISTURE_EXCESS, "yaml_room").state) == (
        pytest.approx(4.79, abs=0.01)
    )


async def test_yaml_one_outdoor_sensor_is_not_enough(hass, caplog):
    """Test that only one of the outdoor sensors is reported and not used."""
    set_indoor(hass, 21, 50)
    set_outdoor(hass, 0, 90)
    with caplog.at_level(logging.WARNING):
        assert await async_setup_component(
            hass,
            DOMAIN,
            yaml_config(device={CONF_OUTDOOR_TEMPERATURE_SENSOR: "sensor.out_t"}),
        )
        await hass.async_block_till_done()
    assert "both needed" in caplog.text
    assert sensor(hass, SensorType.MOISTURE_EXCESS, "yaml_room") is None
    assert sensor(hass, SensorType.DEW_POINT, "yaml_room") is not None


async def test_attributes_are_rounded_and_in_celsius(hass):
    """Test the attributes of a source in another unit and that they have two decimals."""
    set_indoor(hass, 21, 50)
    hass.states.async_set("sensor.out_t", "32", {"unit_of_measurement": "°F"})
    hass.states.async_set("sensor.out_h", "90")
    await setup_entry(hass)

    attributes = sensor(hass, SensorType.MOISTURE_EXCESS).attributes
    assert attributes["outdoor_temperature"] == 0.0
    for key in (
        "outdoor_absolute_humidity",
        "outdoor_dew_point",
        "ventilated_relative_humidity",
    ):
        assert attributes[key] == round(attributes[key], 2)
    assert (
        sensor(hass, SensorType.VENTILATION_ADVICE).attributes["outdoor_temperature"]
        == 0.0
    )
