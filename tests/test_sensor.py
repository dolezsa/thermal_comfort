"""The test for the Thermal Comfort sensor platform."""

import logging

from homeassistant.components.command_line.const import DOMAIN as COMMAND_LINE_DOMAIN
from homeassistant.components.sensor import DOMAIN as PLATFORM_DOMAIN
from homeassistant.const import ATTR_TEMPERATURE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.thermal_comfort.const import DOMAIN
from custom_components.thermal_comfort.sensor import (
    ATTR_FROST_RISK_LEVEL,
    ATTR_HUMIDITY,
    DEFAULT_SENSOR_TYPES,
    SensorType,
    SimmerZone,
    ThermalPerception,
    id_generator,
)

from .const import USER_INPUT

_LOGGER = logging.getLogger(__name__)

TEST_NAME = "sensor.test_thermal_comfort"

TEMPERATURE_TEST_SENSOR = {
    "platform": COMMAND_LINE_DOMAIN,
    "command": "echo 0",
    "name": "test_temperature_sensor",
    "value_template": "{{ 25.0 | float }}",
}

HUMIDITY_TEST_SENSOR = {
    "platform": COMMAND_LINE_DOMAIN,
    "command": "echo 0",
    "name": "test_humidity_sensor",
    "value_template": "{{ 50.0 | float }}",
}

DEFAULT_TEST_SENSORS = [
    "domains, config",
    [
        (
            [(PLATFORM_DOMAIN, 3)],
            {
                PLATFORM_DOMAIN: [
                    TEMPERATURE_TEST_SENSOR,
                    HUMIDITY_TEST_SENSOR,
                    {
                        "platform": DOMAIN,
                        "sensors": {
                            "test_thermal_comfort": {
                                "temperature_sensor": "sensor.test_temperature_sensor",
                                "humidity_sensor": "sensor.test_humidity_sensor",
                            },
                        },
                    },
                ],
            },
        ),
        (
            [(PLATFORM_DOMAIN, 2), (DOMAIN, 1)],
            {
                PLATFORM_DOMAIN: [
                    TEMPERATURE_TEST_SENSOR,
                    HUMIDITY_TEST_SENSOR,
                ],
                DOMAIN: {
                    PLATFORM_DOMAIN: {
                        "name": "test_thermal_comfort",
                        "temperature_sensor": "sensor.test_temperature_sensor",
                        "humidity_sensor": "sensor.test_humidity_sensor",
                    },
                },
            },
        ),
    ],
]

LEN_DEFAULT_SENSORS = len(DEFAULT_SENSOR_TYPES)


@pytest.mark.parametrize(*DEFAULT_TEST_SENSORS)
async def test_config(hass, start_ha):
    """Test basic config."""
    assert len(hass.states.async_all(PLATFORM_DOMAIN)) == LEN_DEFAULT_SENSORS + 2


@pytest.mark.parametrize(*DEFAULT_TEST_SENSORS)
async def test_properties(hass, start_ha):
    """Test if properties are set up correctly."""
    for sensor_type in DEFAULT_SENSOR_TYPES:
        assert (
            ATTR_TEMPERATURE in hass.states.get(f"{TEST_NAME}_{sensor_type}").attributes
        )
        assert ATTR_HUMIDITY in hass.states.get(f"{TEST_NAME}_{sensor_type}").attributes
        assert (
            hass.states.get(f"{TEST_NAME}_{sensor_type}").attributes[ATTR_TEMPERATURE]
            == 25.0
        )
        assert (
            hass.states.get(f"{TEST_NAME}_{sensor_type}").attributes[ATTR_HUMIDITY]
            == 50.0
        )


@pytest.mark.parametrize(*DEFAULT_TEST_SENSORS)
async def test_absolutehumidity(hass, start_ha):
    """Test if absolute humidity is calculted correctly."""
    assert hass.states.get(f"{TEST_NAME}_{SensorType.ABSOLUTEHUMIDITY}") is not None
    assert (
        hass.states.get(f"{TEST_NAME}_{SensorType.ABSOLUTEHUMIDITY}").state == "11.51"
    )

    hass.states.async_set("sensor.test_temperature_sensor", "15.0")
    await hass.async_block_till_done()
    assert hass.states.get(f"{TEST_NAME}_{SensorType.ABSOLUTEHUMIDITY}").state == "6.41"

    hass.states.async_set("sensor.test_humidity_sensor", "25.0")
    await hass.async_block_till_done()
    assert hass.states.get(f"{TEST_NAME}_{SensorType.ABSOLUTEHUMIDITY}").state == "3.2"


@pytest.mark.parametrize(*DEFAULT_TEST_SENSORS)
async def test_heatindex(hass, start_ha):
    """Test if heat index is calculated correctly."""
    assert hass.states.get(f"{TEST_NAME}_{SensorType.HEATINDEX}") is not None
    assert hass.states.get(f"{TEST_NAME}_{SensorType.HEATINDEX}").state == "24.86"

    hass.states.async_set("sensor.test_temperature_sensor", "15.0")
    await hass.async_block_till_done()
    assert hass.states.get(f"{TEST_NAME}_{SensorType.HEATINDEX}").state == "13.86"

    hass.states.async_set("sensor.test_humidity_sensor", "25.0")
    await hass.async_block_till_done()
    assert hass.states.get(f"{TEST_NAME}_{SensorType.HEATINDEX}").state == "13.21"

    hass.states.async_set("sensor.test_humidity_sensor", "12.0")
    await hass.async_block_till_done()
    hass.states.async_set("sensor.test_temperature_sensor", "28.0")
    await hass.async_block_till_done()
    assert hass.states.get(f"{TEST_NAME}_{SensorType.HEATINDEX}").state == "26.55"


@pytest.mark.parametrize(*DEFAULT_TEST_SENSORS)
async def test_dew_point(hass, start_ha):
    """Test if dew point is calculated correctly."""
    assert hass.states.get(f"{TEST_NAME}_{SensorType.DEWPOINT}") is not None
    assert hass.states.get(f"{TEST_NAME}_{SensorType.DEWPOINT}").state == "13.88"

    hass.states.async_set("sensor.test_temperature_sensor", "15.0")
    await hass.async_block_till_done()
    assert hass.states.get(f"{TEST_NAME}_{SensorType.DEWPOINT}").state == "4.68"

    hass.states.async_set("sensor.test_humidity_sensor", "25.0")
    await hass.async_block_till_done()
    assert hass.states.get(f"{TEST_NAME}_{SensorType.DEWPOINT}").state == "-4.86"


@pytest.mark.parametrize(*DEFAULT_TEST_SENSORS)
async def test_perception(hass, start_ha):
    """Test if perception is calculated correctly."""
    hass.states.async_set("sensor.test_temperature_sensor", "20.77")
    await hass.async_block_till_done()
    assert hass.states.get(f"{TEST_NAME}_{SensorType.THERMALPERCEPTION}") is not None
    assert hass.states.get(f"{TEST_NAME}_{SensorType.DEWPOINT}").state == "9.99"
    assert (
        hass.states.get(f"{TEST_NAME}_{SensorType.THERMALPERCEPTION}").state
        == ThermalPerception.DRY
    )

    hass.states.async_set("sensor.test_temperature_sensor", "24.0")
    await hass.async_block_till_done()
    assert hass.states.get(f"{TEST_NAME}_{SensorType.DEWPOINT}").state == "12.96"
    assert (
        hass.states.get(f"{TEST_NAME}_{SensorType.THERMALPERCEPTION}").state
        == ThermalPerception.VERY_COMFORTABLE
    )

    hass.states.async_set("sensor.test_humidity_sensor", "60.82")
    await hass.async_block_till_done()
    assert hass.states.get(f"{TEST_NAME}_{SensorType.DEWPOINT}").state == "15.99"
    assert (
        hass.states.get(f"{TEST_NAME}_{SensorType.THERMALPERCEPTION}").state
        == ThermalPerception.COMFORTABLE
    )

    hass.states.async_set("sensor.test_temperature_sensor", "24.01")
    await hass.async_block_till_done()
    assert hass.states.get(f"{TEST_NAME}_{SensorType.DEWPOINT}").state == "16.0"
    assert (
        hass.states.get(f"{TEST_NAME}_{SensorType.THERMALPERCEPTION}").state
        == ThermalPerception.OK_BUT_HUMID
    )

    hass.states.async_set("sensor.test_humidity_sensor", "69.03")
    await hass.async_block_till_done()
    assert hass.states.get(f"{TEST_NAME}_{SensorType.DEWPOINT}").state == "18.0"
    assert (
        hass.states.get(f"{TEST_NAME}_{SensorType.THERMALPERCEPTION}").state
        == ThermalPerception.SOMEWHAT_UNCOMFORTABLE
    )

    hass.states.async_set("sensor.test_humidity_sensor", "79.6")
    await hass.async_block_till_done()
    hass.states.async_set("sensor.test_temperature_sensor", "26.0")
    await hass.async_block_till_done()
    assert hass.states.get(f"{TEST_NAME}_{SensorType.DEWPOINT}").state == "22.22"
    assert (
        hass.states.get(f"{TEST_NAME}_{SensorType.THERMALPERCEPTION}").state
        == ThermalPerception.QUITE_UNCOMFORTABLE
    )

    hass.states.async_set("sensor.test_humidity_sensor", "85.0")
    await hass.async_block_till_done()
    hass.states.async_set("sensor.test_temperature_sensor", "26.85")
    await hass.async_block_till_done()
    assert hass.states.get(f"{TEST_NAME}_{SensorType.DEWPOINT}").state == "24.13"
    assert (
        hass.states.get(f"{TEST_NAME}_{SensorType.THERMALPERCEPTION}").state
        == ThermalPerception.EXTREMELY_UNCOMFORTABLE
    )

    hass.states.async_set("sensor.test_humidity_sensor", "95.0")
    await hass.async_block_till_done()
    hass.states.async_set("sensor.test_temperature_sensor", "26.85")
    await hass.async_block_till_done()
    assert hass.states.get(f"{TEST_NAME}_{SensorType.DEWPOINT}").state == "26.0"
    assert (
        hass.states.get(f"{TEST_NAME}_{SensorType.THERMALPERCEPTION}").state
        == ThermalPerception.SEVERELY_HIGH
    )


@pytest.mark.parametrize(*DEFAULT_TEST_SENSORS)
async def test_frost_point(hass, start_ha):
    """Test if frost point is calculated correctly."""
    assert hass.states.get(f"{TEST_NAME}_{SensorType.FROSTPOINT}") is not None
    assert hass.states.get(f"{TEST_NAME}_{SensorType.FROSTPOINT}").state == "10.43"

    hass.states.async_set("sensor.test_temperature_sensor", "15.0")
    await hass.async_block_till_done()
    assert hass.states.get(f"{TEST_NAME}_{SensorType.FROSTPOINT}").state == "2.73"

    hass.states.async_set("sensor.test_humidity_sensor", "25.0")
    await hass.async_block_till_done()
    assert hass.states.get(f"{TEST_NAME}_{SensorType.FROSTPOINT}").state == "-6.81"


@pytest.mark.parametrize(*DEFAULT_TEST_SENSORS)
async def test_frost_risk(hass, start_ha):
    """Test if frost risk is calculated correctly."""
    assert hass.states.get(f"{TEST_NAME}_{SensorType.FROSTRISK}") is not None
    assert hass.states.get(f"{TEST_NAME}_{SensorType.FROSTRISK}").state == "no_risk"
    assert (
        hass.states.get(f"{TEST_NAME}_{SensorType.FROSTRISK}").attributes[
            ATTR_FROST_RISK_LEVEL
        ]
        == 0
    )

    hass.states.async_set("sensor.test_temperature_sensor", "0")
    hass.states.async_set("sensor.test_humidity_sensor", "57.7")
    await hass.async_block_till_done()
    assert hass.states.get(f"{TEST_NAME}_{SensorType.FROSTRISK}").state == "unlikely"
    assert (
        hass.states.get(f"{TEST_NAME}_{SensorType.FROSTRISK}").attributes[
            ATTR_FROST_RISK_LEVEL
        ]
        == 1
    )

    hass.states.async_set("sensor.test_temperature_sensor", "4.0")
    hass.states.async_set("sensor.test_humidity_sensor", "80.65")
    await hass.async_block_till_done()
    assert hass.states.get(f"{TEST_NAME}_{SensorType.FROSTRISK}").state == "probable"
    assert (
        hass.states.get(f"{TEST_NAME}_{SensorType.FROSTRISK}").attributes[
            ATTR_FROST_RISK_LEVEL
        ]
        == 2
    )

    hass.states.async_set("sensor.test_temperature_sensor", "1.0")
    hass.states.async_set("sensor.test_humidity_sensor", "90.00")
    await hass.async_block_till_done()
    assert hass.states.get(f"{TEST_NAME}_{SensorType.FROSTRISK}").state == "high"
    assert (
        hass.states.get(f"{TEST_NAME}_{SensorType.FROSTRISK}").attributes[
            ATTR_FROST_RISK_LEVEL
        ]
        == 3
    )


@pytest.mark.parametrize(*DEFAULT_TEST_SENSORS)
async def test_simmer_index(hass, start_ha):
    """Test if simmer index is calculated correctly."""
    assert hass.states.get(f"{TEST_NAME}_{SensorType.SIMMERINDEX}") is not None
    assert hass.states.get(f"{TEST_NAME}_{SensorType.SIMMERINDEX}").state == "29.6"

    hass.states.async_set("sensor.test_temperature_sensor", "15.0")
    await hass.async_block_till_done()
    assert hass.states.get(f"{TEST_NAME}_{SensorType.SIMMERINDEX}").state == "15.0"

    hass.states.async_set("sensor.test_humidity_sensor", "35.0")
    await hass.async_block_till_done()
    hass.states.async_set("sensor.test_temperature_sensor", "25.0")
    await hass.async_block_till_done()
    assert hass.states.get(f"{TEST_NAME}_{SensorType.SIMMERINDEX}").state == "27.88"


@pytest.mark.parametrize(*DEFAULT_TEST_SENSORS)
async def test_simmer_zone(hass, start_ha):
    """Test if simmer zone is calculated correctly."""
    hass.states.async_set("sensor.test_temperature_sensor", "20.77")
    await hass.async_block_till_done()
    assert hass.states.get(f"{TEST_NAME}_{SensorType.SIMMERZONE}") is not None
    assert hass.states.get(f"{TEST_NAME}_{SensorType.SIMMERINDEX}").state == "20.77"
    assert (
        hass.states.get(f"{TEST_NAME}_{SensorType.SIMMERZONE}").state == SimmerZone.COOL
    )

    hass.states.async_set("sensor.test_temperature_sensor", "24.0")
    await hass.async_block_till_done()
    assert hass.states.get(f"{TEST_NAME}_{SensorType.SIMMERINDEX}").state == "28.17"
    assert (
        hass.states.get(f"{TEST_NAME}_{SensorType.SIMMERZONE}").state
        == SimmerZone.COMFORTABLE
    )

    hass.states.async_set("sensor.test_humidity_sensor", "60.82")
    await hass.async_block_till_done()
    assert hass.states.get(f"{TEST_NAME}_{SensorType.SIMMERINDEX}").state == "29.29"
    assert (
        hass.states.get(f"{TEST_NAME}_{SensorType.SIMMERZONE}").state
        == SimmerZone.SLIGHTLY_WARM
    )

    hass.states.async_set("sensor.test_temperature_sensor", "24.01")
    await hass.async_block_till_done()
    assert hass.states.get(f"{TEST_NAME}_{SensorType.SIMMERINDEX}").state == "29.31"
    assert (
        hass.states.get(f"{TEST_NAME}_{SensorType.SIMMERZONE}").state
        == SimmerZone.SLIGHTLY_WARM
    )

    hass.states.async_set("sensor.test_humidity_sensor", "69.03")
    await hass.async_block_till_done()
    assert hass.states.get(f"{TEST_NAME}_{SensorType.SIMMERINDEX}").state == "30.16"
    assert (
        hass.states.get(f"{TEST_NAME}_{SensorType.SIMMERZONE}").state
        == SimmerZone.SLIGHTLY_WARM
    )

    hass.states.async_set("sensor.test_humidity_sensor", "79.6")
    await hass.async_block_till_done()
    hass.states.async_set("sensor.test_temperature_sensor", "26.0")
    await hass.async_block_till_done()
    assert hass.states.get(f"{TEST_NAME}_{SensorType.SIMMERINDEX}").state == "34.76"
    assert (
        hass.states.get(f"{TEST_NAME}_{SensorType.SIMMERZONE}").state
        == SimmerZone.INCREASING_DISCOMFORT
    )

    hass.states.async_set("sensor.test_humidity_sensor", "85.0")
    await hass.async_block_till_done()
    hass.states.async_set("sensor.test_temperature_sensor", "26.85")
    await hass.async_block_till_done()
    assert hass.states.get(f"{TEST_NAME}_{SensorType.SIMMERINDEX}").state == "36.99"
    assert (
        hass.states.get(f"{TEST_NAME}_{SensorType.SIMMERZONE}").state
        == SimmerZone.INCREASING_DISCOMFORT
    )

    hass.states.async_set("sensor.test_humidity_sensor", "80.0")
    await hass.async_block_till_done()
    hass.states.async_set("sensor.test_temperature_sensor", "29.0")
    await hass.async_block_till_done()
    assert hass.states.get(f"{TEST_NAME}_{SensorType.SIMMERINDEX}").state == "40.1"
    assert (
        hass.states.get(f"{TEST_NAME}_{SensorType.SIMMERZONE}").state
        == SimmerZone.EXTREMELY_WARM
    )

    hass.states.async_set("sensor.test_humidity_sensor", "45.0")
    await hass.async_block_till_done()
    hass.states.async_set("sensor.test_temperature_sensor", "40.0")
    await hass.async_block_till_done()
    assert hass.states.get(f"{TEST_NAME}_{SensorType.SIMMERINDEX}").state == "49.74"
    assert (
        hass.states.get(f"{TEST_NAME}_{SensorType.SIMMERZONE}").state
        == SimmerZone.DANGER_OF_HEATSTROKE
    )


@pytest.mark.parametrize(
    "domains, config",
    [
        (
            [(PLATFORM_DOMAIN, 3)],
            {
                PLATFORM_DOMAIN: [
                    TEMPERATURE_TEST_SENSOR,
                    HUMIDITY_TEST_SENSOR,
                    {
                        "platform": DOMAIN,
                        "sensors": {
                            "test_thermal_comfort": {
                                "temperature_sensor": "sensor.test_temperature_sensor",
                                "humidity_sensor": "sensor.test_humidity_sensor",
                                "unique_id": "unique",
                            },
                            "test_thermal_comfort_not_unique1": {
                                "temperature_sensor": "sensor.test_temperature_sensor",
                                "humidity_sensor": "sensor.test_humidity_sensor",
                                "unique_id": "not-so-unique-anymore",
                            },
                            "test_thermal_comfort_not_unique2": {
                                "temperature_sensor": "sensor.test_temperature_sensor",
                                "humidity_sensor": "sensor.test_humidity_sensor",
                                "unique_id": "not-so-unique-anymore",
                            },
                        },
                    },
                ],
            },
        ),
        (
            [(PLATFORM_DOMAIN, 2), (DOMAIN, 1)],
            {
                PLATFORM_DOMAIN: [
                    TEMPERATURE_TEST_SENSOR,
                    HUMIDITY_TEST_SENSOR,
                ],
                DOMAIN: {
                    PLATFORM_DOMAIN: [
                        {
                            "name": "test_thermal_comfort",
                            "temperature_sensor": "sensor.test_temperature_sensor",
                            "humidity_sensor": "sensor.test_humidity_sensor",
                            "unique_id": "unique",
                        },
                        {
                            "name": "test_thermal_comfort_not_unique1",
                            "temperature_sensor": "sensor.test_temperature_sensor",
                            "humidity_sensor": "sensor.test_humidity_sensor",
                            "unique_id": "not-so-unique-anymore",
                        },
                        {
                            "name": "test_thermal_comfort_not_unique2",
                            "temperature_sensor": "sensor.test_temperature_sensor",
                            "humidity_sensor": "sensor.test_humidity_sensor",
                            "unique_id": "not-so-unique-anymore",
                        },
                    ]
                },
            },
        ),
    ],
)
async def test_unique_id(hass, start_ha):
    """Test if unique id is working as expected."""
    assert len(hass.states.async_all()) == 2 * LEN_DEFAULT_SENSORS + 2

    ent_reg = entity_registry.async_get(hass)

    assert len(ent_reg.entities) == 2 * LEN_DEFAULT_SENSORS

    for sensor_type in DEFAULT_SENSOR_TYPES:
        assert (
            ent_reg.async_get_entity_id(
                PLATFORM_DOMAIN, "thermal_comfort", f"unique{sensor_type}"
            )
            is not None
        )
        assert (
            ent_reg.async_get_entity_id(
                PLATFORM_DOMAIN,
                "thermal_comfort",
                f"not-so-unique-anymore{sensor_type}",
            )
            is not None
        )


@pytest.mark.parametrize(
    "domains, config",
    [
        (
            [(PLATFORM_DOMAIN, 3)],
            {
                PLATFORM_DOMAIN: [
                    TEMPERATURE_TEST_SENSOR,
                    HUMIDITY_TEST_SENSOR,
                    {
                        "platform": DOMAIN,
                        "sensors": {
                            "test_thermal_comfort": {
                                "temperature_sensor": "sensor.test_temperature_sensor",
                                "humidity_sensor": "sensor.test_humidity_sensor",
                                "icon_template": "mdi:thermometer",
                            },
                        },
                    },
                ],
            },
        ),
        (
            [(PLATFORM_DOMAIN, 2), (DOMAIN, 1)],
            {
                PLATFORM_DOMAIN: [
                    TEMPERATURE_TEST_SENSOR,
                    HUMIDITY_TEST_SENSOR,
                ],
                DOMAIN: {
                    PLATFORM_DOMAIN: {
                        "name": "test_thermal_comfort",
                        "temperature_sensor": "sensor.test_temperature_sensor",
                        "humidity_sensor": "sensor.test_humidity_sensor",
                        "icon_template": "mdi:thermometer",
                    },
                },
            },
        ),
    ],
)
async def test_valid_icon_template(hass, start_ha):
    """Test if icon template is working as expected."""
    assert len(hass.states.async_all(PLATFORM_DOMAIN)) == LEN_DEFAULT_SENSORS + 2


@pytest.mark.parametrize(*DEFAULT_TEST_SENSORS)
async def test_zero_degree_celcius(hass, start_ha):
    """Test if zero degree celsius does not cause any errors."""
    assert len(hass.states.async_all(PLATFORM_DOMAIN)) == LEN_DEFAULT_SENSORS + 2
    hass.states.async_set("sensor.test_temperature_sensor", "0")
    await hass.async_block_till_done()
    assert hass.states.get(f"{TEST_NAME}_{SensorType.DEWPOINT}") is not None
    assert hass.states.get(f"{TEST_NAME}_{SensorType.DEWPOINT}").state == "-9.19"
    assert hass.states.get(f"{TEST_NAME}_{SensorType.SIMMERINDEX}") is not None
    assert hass.states.get(f"{TEST_NAME}_{SensorType.SIMMERINDEX}").state == "0.0"


@pytest.mark.parametrize(
    "domains, config",
    [
        (
            [(PLATFORM_DOMAIN, 3)],
            {
                PLATFORM_DOMAIN: [
                    TEMPERATURE_TEST_SENSOR,
                    HUMIDITY_TEST_SENSOR,
                    {
                        "platform": "thermal_comfort",
                        "sensors": {
                            "test_thermal_comfort": {
                                "temperature_sensor": "sensor.test_temperature_sensor",
                                "humidity_sensor": "sensor.test_humidity_sensor",
                                "sensor_types": [
                                    "absolutehumidity",
                                    "dewpoint",
                                ],
                            },
                        },
                    },
                ],
            },
        ),
        (
            [(PLATFORM_DOMAIN, 2), (DOMAIN, 1)],
            {
                PLATFORM_DOMAIN: [
                    TEMPERATURE_TEST_SENSOR,
                    HUMIDITY_TEST_SENSOR,
                ],
                DOMAIN: {
                    PLATFORM_DOMAIN: {
                        "name": "test_thermal_comfort",
                        "temperature_sensor": "sensor.test_temperature_sensor",
                        "humidity_sensor": "sensor.test_humidity_sensor",
                        "sensor_types": [
                            "absolutehumidity",
                            "dewpoint",
                        ],
                    },
                },
            },
        ),
    ],
)
async def test_sensor_types(hass, start_ha):
    """Test if configure sensor_types only creates the sensors specified."""
    assert len(hass.states.async_all(PLATFORM_DOMAIN)) == 4

    assert hass.states.get(f"{TEST_NAME}_{SensorType.HEATINDEX}") is None
    assert hass.states.get(f"{TEST_NAME}_{SensorType.THERMALPERCEPTION}") is None

    assert hass.states.get(f"{TEST_NAME}_{SensorType.ABSOLUTEHUMIDITY}") is not None
    assert hass.states.get(f"{TEST_NAME}_{SensorType.DEWPOINT}") is not None


@pytest.mark.parametrize(
    "domains, config",
    [
        (
            [(PLATFORM_DOMAIN, 3)],
            {
                PLATFORM_DOMAIN: [
                    {
                        "platform": COMMAND_LINE_DOMAIN,
                        "command": "echo 0",
                        "name": "test_temperature_sensor",
                        "value_template": "{{ NaN | float }}",
                    },
                    {
                        "platform": COMMAND_LINE_DOMAIN,
                        "command": "echo 0",
                        "name": "test_humidity_sensor",
                        "value_template": "{{ NaN | float }}",
                    },
                    {
                        "platform": DOMAIN,
                        "sensors": {
                            "test_thermal_comfort": {
                                "temperature_sensor": "sensor.test_temperature_sensor",
                                "humidity_sensor": "sensor.test_humidity_sensor",
                            },
                        },
                    },
                ],
            },
        ),
        (
            [(PLATFORM_DOMAIN, 2), (DOMAIN, 1)],
            {
                PLATFORM_DOMAIN: [
                    {
                        "platform": COMMAND_LINE_DOMAIN,
                        "command": "echo 0",
                        "name": "test_temperature_sensor",
                        "value_template": "{{ NaN | float }}",
                    },
                    {
                        "platform": COMMAND_LINE_DOMAIN,
                        "command": "echo 0",
                        "name": "test_humidity_sensor",
                        "value_template": "{{ NaN | float }}",
                    },
                ],
                DOMAIN: {
                    PLATFORM_DOMAIN: {
                        "name": "test_thermal_comfort",
                        "temperature_sensor": "sensor.test_temperature_sensor",
                        "humidity_sensor": "sensor.test_humidity_sensor",
                    },
                },
            },
        ),
    ],
)
async def test_sensor_is_nan(hass, start_ha):
    """Test if we correctly handle input sensors with NaN as state value."""
    assert len(hass.states.async_all(PLATFORM_DOMAIN)) == LEN_DEFAULT_SENSORS + 2
    for sensor_type in DEFAULT_SENSOR_TYPES:
        assert (
            ATTR_TEMPERATURE
            not in hass.states.get(f"{TEST_NAME}_{sensor_type}").attributes
        )
        assert (
            ATTR_HUMIDITY
            not in hass.states.get(f"{TEST_NAME}_{sensor_type}").attributes
        )


@pytest.mark.parametrize(
    "domains, config",
    [
        (
            [(PLATFORM_DOMAIN, 3)],
            {
                PLATFORM_DOMAIN: [
                    {
                        "platform": COMMAND_LINE_DOMAIN,
                        "command": "echo 0",
                        "name": "test_temperature_sensor",
                        "value_template": "{{ 'Unknown' }}",
                    },
                    {
                        "platform": COMMAND_LINE_DOMAIN,
                        "command": "echo 0",
                        "name": "test_humidity_sensor",
                        "value_template": "{{ 'asdf' }}",
                    },
                    {
                        "platform": DOMAIN,
                        "sensors": {
                            "test_thermal_comfort": {
                                "temperature_sensor": "sensor.test_temperature_sensor",
                                "humidity_sensor": "sensor.test_humidity_sensor",
                            },
                        },
                    },
                ],
            },
        ),
        (
            [(PLATFORM_DOMAIN, 2), (DOMAIN, 1)],
            {
                PLATFORM_DOMAIN: [
                    {
                        "platform": COMMAND_LINE_DOMAIN,
                        "command": "echo 0",
                        "name": "test_temperature_sensor",
                        "value_template": "{{ NaN | float }}",
                    },
                    {
                        "platform": COMMAND_LINE_DOMAIN,
                        "command": "echo 0",
                        "name": "test_humidity_sensor",
                        "value_template": "{{ NaN | float }}",
                    },
                ],
                DOMAIN: {
                    PLATFORM_DOMAIN: {
                        "name": "test_thermal_comfort",
                        "temperature_sensor": "sensor.test_temperature_sensor",
                        "humidity_sensor": "sensor.test_humidity_sensor",
                    },
                },
            },
        ),
    ],
)
async def test_sensor_unknown(hass, start_ha):
    """Test handling input sensors with unknown state."""
    assert len(hass.states.async_all(PLATFORM_DOMAIN)) == LEN_DEFAULT_SENSORS + 2
    for sensor_type in DEFAULT_SENSOR_TYPES:
        assert (
            ATTR_TEMPERATURE
            not in hass.states.get(f"{TEST_NAME}_{sensor_type}").attributes
        )
        assert (
            ATTR_HUMIDITY
            not in hass.states.get(f"{TEST_NAME}_{sensor_type}").attributes
        )


@pytest.mark.parametrize(*DEFAULT_TEST_SENSORS)
async def test_sensor_unavailable(hass, start_ha):
    """Test handling unavailable sensors."""
    assert len(hass.states.async_all(PLATFORM_DOMAIN)) == LEN_DEFAULT_SENSORS + 2
    hass.states.async_remove("sensor.test_temperature_sensor")
    hass.states.async_remove("sensor.test_humidity_sensor")
    await hass.async_block_till_done()
    assert len(hass.states.async_all(PLATFORM_DOMAIN)) == LEN_DEFAULT_SENSORS
    for sensor_type in DEFAULT_SENSOR_TYPES:
        assert (
            ATTR_TEMPERATURE in hass.states.get(f"{TEST_NAME}_{sensor_type}").attributes
        )
        assert ATTR_HUMIDITY in hass.states.get(f"{TEST_NAME}_{sensor_type}").attributes
        assert (
            hass.states.get(f"{TEST_NAME}_{sensor_type}").attributes[ATTR_TEMPERATURE]
            == 25.0
        )
        assert (
            hass.states.get(f"{TEST_NAME}_{sensor_type}").attributes[ATTR_HUMIDITY]
            == 50.0
        )


async def test_create_sensors(hass: HomeAssistant):
    """Test sensors update engine.

    When user remove sensor in integration config, then we should remove it from system
    :param hass: HomeAssistant: Home Assistant object
    """

    def get_eid(registry: entity_registry, _id):
        return registry.async_get_entity_id(
            domain="sensor", platform=DOMAIN, unique_id=_id
        )

    er = entity_registry.async_get(hass)

    entry = MockConfigEntry(
        domain=DOMAIN, data=USER_INPUT, entry_id="test", unique_id="uniqueid"
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # Make sure that sensors in registry
    for s in SensorType:
        assert get_eid(er, id_generator(entry.unique_id, s)) is not None
