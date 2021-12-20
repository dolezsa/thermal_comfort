"""The test for the Thermal Comfort sensor platform."""

import pytest
import logging

from homeassistant.components import sensor
from homeassistant.helpers import entity_registry, entity_component

from homeassistant.const import (
        ATTR_TEMPERATURE,
)

from custom_components.thermal_comfort.sensor import (
        ATTR_HUMIDITY,
        ATTR_FROST_RISK_LEVEL,
        DEFAULT_SENSOR_TYPES,
        PERCEPTION_DRY,
        PERCEPTION_VERY_COMFORTABLE,
        PERCEPTION_COMFORTABLE,
        PERCEPTION_DEWPOINT_OK_BUT_HUMID,
        PERCEPTION_SOMEWHAT_UNCOMFORTABLE,
        PERCEPTION_QUITE_UNCOMFORTABLE,
        PERCEPTION_EXTREMELY_UNCOMFORTABLE,
        PERCEPTION_SEVERELY_HIGH,
)

_LOGGER = logging.getLogger(__name__)

TEST_NAME = "sensor.test_thermal_comfort"
DEFAULT_TEST_SENSORS = [({
    sensor.DOMAIN: {
        "count": 3,
        "config": {
            sensor.DOMAIN: [
                {
                    "platform": 'command_line',
                    "command": 'echo 0',
                    "name": "test_temperature_sensor",
                    "value_template": "{{ 25.0 | float }}",
                },
                {
                    "platform": 'command_line',
                    "command": 'echo 0',
                    "name": "test_humidity_sensor",
                    "value_template": "{{ 50.0 | float }}",
                },
                {
                    "platform": "thermal_comfort",
                    "sensors": {
                        "test_thermal_comfort": {
                            "temperature_sensor": "sensor.test_temperature_sensor",
                            "humidity_sensor": "sensor.test_humidity_sensor",
                        },
                    },
                },
            ],
        },
    },
})]

@pytest.mark.parametrize("domains", DEFAULT_TEST_SENSORS)
async def test_config(hass, start_ha):
    assert len(hass.states.async_all(sensor.DOMAIN)) == 8


@pytest.mark.parametrize("domains", DEFAULT_TEST_SENSORS)
async def test_properties(hass, start_ha):
    for sensor_type in DEFAULT_SENSOR_TYPES:
        assert ATTR_TEMPERATURE in hass.states.get(f"{TEST_NAME}_{sensor_type}").attributes
        assert ATTR_HUMIDITY in hass.states.get(f"{TEST_NAME}_{sensor_type}").attributes
        assert hass.states.get(f"{TEST_NAME}_{sensor_type}").attributes[ATTR_TEMPERATURE] == 25.0
        assert hass.states.get(f"{TEST_NAME}_{sensor_type}").attributes[ATTR_HUMIDITY] == 50.0


@pytest.mark.parametrize("domains", DEFAULT_TEST_SENSORS)
async def test_absolutehumidity(hass, start_ha):
    assert hass.states.get(f"{TEST_NAME}_absolutehumidity") is not None
    assert hass.states.get(f"{TEST_NAME}_absolutehumidity").state == "11.51"

    hass.states.async_set("sensor.test_temperature_sensor", "15.0")
    await hass.async_block_till_done()
    assert hass.states.get(f"{TEST_NAME}_absolutehumidity").state == "6.41"

    hass.states.async_set("sensor.test_humidity_sensor", "25.0")
    await hass.async_block_till_done()
    assert hass.states.get(f"{TEST_NAME}_absolutehumidity").state == "3.2"


@pytest.mark.parametrize("domains", DEFAULT_TEST_SENSORS)
async def test_heatindex(hass, start_ha):
    assert hass.states.get(f"{TEST_NAME}_heatindex") is not None
    assert hass.states.get(f"{TEST_NAME}_heatindex").state == "24.86"

    hass.states.async_set("sensor.test_temperature_sensor", "15.0")
    await hass.async_block_till_done()
    assert hass.states.get(f"{TEST_NAME}_heatindex").state == "13.86"

    hass.states.async_set("sensor.test_humidity_sensor", "25.0")
    await hass.async_block_till_done()
    assert hass.states.get(f"{TEST_NAME}_heatindex").state == "13.21"

    hass.states.async_set("sensor.test_humidity_sensor", "12.0")
    hass.states.async_set("sensor.test_temperature_sensor", "28.0")
    await hass.async_block_till_done()
    assert hass.states.get(f"{TEST_NAME}_heatindex").state == "26.55"


@pytest.mark.parametrize("domains", DEFAULT_TEST_SENSORS)
async def test_dew_point(hass, start_ha):
    assert hass.states.get(f"{TEST_NAME}_dewpoint") is not None
    assert hass.states.get(f"{TEST_NAME}_dewpoint").state == "13.88"

    hass.states.async_set("sensor.test_temperature_sensor", "15.0")
    await hass.async_block_till_done()
    assert hass.states.get(f"{TEST_NAME}_dewpoint").state == "4.68"

    hass.states.async_set("sensor.test_humidity_sensor", "25.0")
    await hass.async_block_till_done()
    assert hass.states.get(f"{TEST_NAME}_dewpoint").state == "-4.86"


@pytest.mark.parametrize("domains", DEFAULT_TEST_SENSORS)
async def test_perception(hass, start_ha):
    hass.states.async_set("sensor.test_temperature_sensor", "20.77")
    await hass.async_block_till_done()
    assert hass.states.get(f"{TEST_NAME}_perception") is not None
    assert hass.states.get(f"{TEST_NAME}_dewpoint").state == "9.99"
    assert hass.states.get(f"{TEST_NAME}_perception").state == PERCEPTION_DRY

    hass.states.async_set("sensor.test_temperature_sensor", "24.0")
    await hass.async_block_till_done()
    assert hass.states.get(f"{TEST_NAME}_dewpoint").state == "12.96"
    assert hass.states.get(f"{TEST_NAME}_perception").state == PERCEPTION_VERY_COMFORTABLE

    hass.states.async_set("sensor.test_humidity_sensor", "60.82")
    await hass.async_block_till_done()
    assert hass.states.get(f"{TEST_NAME}_dewpoint").state == "15.99"
    assert hass.states.get(f"{TEST_NAME}_perception").state == PERCEPTION_COMFORTABLE

    hass.states.async_set("sensor.test_temperature_sensor", "24.01")
    await hass.async_block_till_done()
    assert hass.states.get(f"{TEST_NAME}_dewpoint").state == "16.0"
    assert hass.states.get(f"{TEST_NAME}_perception").state == PERCEPTION_DEWPOINT_OK_BUT_HUMID

    hass.states.async_set("sensor.test_humidity_sensor", "69.03")
    await hass.async_block_till_done()
    assert hass.states.get(f"{TEST_NAME}_dewpoint").state == "18.0"
    assert hass.states.get(f"{TEST_NAME}_perception").state == PERCEPTION_SOMEWHAT_UNCOMFORTABLE

    hass.states.async_set("sensor.test_humidity_sensor", "79.6")
    await hass.async_block_till_done()
    hass.states.async_set("sensor.test_temperature_sensor", "26.0")
    await hass.async_block_till_done()
    assert hass.states.get(f"{TEST_NAME}_dewpoint").state == "22.22"
    assert hass.states.get(f"{TEST_NAME}_perception").state == PERCEPTION_QUITE_UNCOMFORTABLE

    hass.states.async_set("sensor.test_humidity_sensor", "85.0")
    await hass.async_block_till_done()
    hass.states.async_set("sensor.test_temperature_sensor", "26.85")
    await hass.async_block_till_done()
    assert hass.states.get(f"{TEST_NAME}_dewpoint").state == "24.13"
    assert hass.states.get(f"{TEST_NAME}_perception").state == PERCEPTION_EXTREMELY_UNCOMFORTABLE

    hass.states.async_set("sensor.test_humidity_sensor", "95.0")
    await hass.async_block_till_done()
    hass.states.async_set("sensor.test_temperature_sensor", "26.85")
    await hass.async_block_till_done()
    assert hass.states.get(f"{TEST_NAME}_dewpoint").state == "26.0"
    assert hass.states.get(f"{TEST_NAME}_perception").state == PERCEPTION_SEVERELY_HIGH


@pytest.mark.parametrize("domains", DEFAULT_TEST_SENSORS)
async def test_frost_point(hass, start_ha):
    assert hass.states.get(f"{TEST_NAME}_frostpoint") is not None
    assert hass.states.get(f"{TEST_NAME}_frostpoint").state == "10.43"

    hass.states.async_set("sensor.test_temperature_sensor", "15.0")
    await hass.async_block_till_done()
    assert hass.states.get(f"{TEST_NAME}_frostpoint").state == "2.73"

    hass.states.async_set("sensor.test_humidity_sensor", "25.0")
    await hass.async_block_till_done()
    assert hass.states.get(f"{TEST_NAME}_frostpoint").state == "-6.81"


@pytest.mark.parametrize("domains", DEFAULT_TEST_SENSORS)
async def test_frost_risk(hass, start_ha):
    assert hass.states.get(f"{TEST_NAME}_frostrisk") is not None
    assert hass.states.get(f"{TEST_NAME}_frostrisk").state == "no_risk"
    assert hass.states.get(f"{TEST_NAME}_frostrisk").attributes[ATTR_FROST_RISK_LEVEL] == 0

    hass.states.async_set("sensor.test_temperature_sensor", "0")
    hass.states.async_set("sensor.test_humidity_sensor", "57.7")
    await hass.async_block_till_done()
    assert hass.states.get(f"{TEST_NAME}_frostrisk").state == "unlikely"
    assert hass.states.get(f"{TEST_NAME}_frostrisk").attributes[ATTR_FROST_RISK_LEVEL] == 1

    hass.states.async_set("sensor.test_temperature_sensor", "4.0")
    hass.states.async_set("sensor.test_humidity_sensor", "80.65")
    await hass.async_block_till_done()
    assert hass.states.get(f"{TEST_NAME}_frostrisk").state == "probable"
    assert hass.states.get(f"{TEST_NAME}_frostrisk").attributes[ATTR_FROST_RISK_LEVEL] == 2

    hass.states.async_set("sensor.test_temperature_sensor", "1.0")
    hass.states.async_set("sensor.test_humidity_sensor", "90.00")
    await hass.async_block_till_done()
    assert hass.states.get(f"{TEST_NAME}_frostrisk").state == "high"
    assert hass.states.get(f"{TEST_NAME}_frostrisk").attributes[ATTR_FROST_RISK_LEVEL] == 3


@pytest.mark.parametrize("domains", [({
    sensor.DOMAIN: {
        "count": 3,
        "config": {
            sensor.DOMAIN: [
                {
                    "platform": 'command_line',
                    "command": 'echo 0',
                    "name": "test_temperature_sensor",
                    "value_template": "{{ 25.0 | float }}",
                },
                {
                    "platform": 'command_line',
                    "command": 'echo 0',
                    "name": "test_humidity_sensor",
                    "value_template": "{{ 50.0 | float }}",
                },
                {
                    "platform": "thermal_comfort",
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
    },
})])
async def test_unique_id(hass, start_ha):
    assert len(hass.states.async_all()) == 14

    ent_reg = entity_registry.async_get(hass)

    assert len(ent_reg.entities) == 12

    for sensor_type in DEFAULT_SENSOR_TYPES:
        assert ent_reg.async_get_entity_id(sensor.DOMAIN, "thermal_comfort", f"unique{sensor_type}") is not None
        assert (
            ent_reg.async_get_entity_id(sensor.DOMAIN, "thermal_comfort", f"not-so-unique-anymore{sensor_type}")
            is not None
        )


@pytest.mark.parametrize("domains", [({
    sensor.DOMAIN: {
        "count": 3,
        "config": {
            sensor.DOMAIN: [
                {
                    "platform": 'command_line',
                    "command": 'echo 0',
                    "name": "test_temperature_sensor",
                    "value_template": "{{ 25.0 | float }}",
                },
                {
                    "platform": 'command_line',
                    "command": 'echo 0',
                    "name": "test_humidity_sensor",
                    "value_template": "{{ 50.0 | float }}",
                },
                {
                    "platform": "thermal_comfort",
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
    },
})])
async def test_valid_icon_template(hass, start_ha):
    assert len(hass.states.async_all(sensor.DOMAIN)) == 8

    
@pytest.mark.parametrize("domains", DEFAULT_TEST_SENSORS)
async def test_zero_degree_celcius(hass, start_ha):
    assert len(hass.states.async_all(sensor.DOMAIN)) == 8
    hass.states.async_set("sensor.test_temperature_sensor", "0")
    await hass.async_block_till_done()
    assert hass.states.get(f"{TEST_NAME}_dewpoint") is not None
    assert hass.states.get(f"{TEST_NAME}_dewpoint").state == "-9.19"


@pytest.mark.parametrize("domains", [({
    sensor.DOMAIN: {
        "count": 3,
        "config": {
            sensor.DOMAIN: [
                {
                    "platform": 'command_line',
                    "command": 'echo 0',
                    "name": "test_temperature_sensor",
                    "value_template": "{{ 25.0 | float }}",
                },
                {
                    "platform": 'command_line',
                    "command": 'echo 0',
                    "name": "test_humidity_sensor",
                    "value_template": "{{ 50.0 | float }}",
                },
                {
                    "platform": "thermal_comfort",
                    "sensors": {
                        "test_thermal_comfort": {
                            "temperature_sensor": "sensor.test_temperature_sensor",
                            "humidity_sensor": "sensor.test_humidity_sensor",
                            "sensor_types": ["absolutehumidity", "dewpoint"],
                        },
                    },
                },
            ],
        },
    },
})])
async def test_sensor_types(hass, start_ha):
    assert len(hass.states.async_all(sensor.DOMAIN)) == 4

    assert hass.states.get(f"{TEST_NAME}_heatindex") is None
    assert hass.states.get(f"{TEST_NAME}_perception") is None

    assert hass.states.get(f"{TEST_NAME}_absolutehumidity") is not None
    assert hass.states.get(f"{TEST_NAME}_dewpoint") is not None

@pytest.mark.parametrize("domains", [({
sensor.DOMAIN: {
    "count": 3,
    "config": {
        sensor.DOMAIN: [
            {
                "platform": 'command_line',
                "command": 'echo 0',
                "name": "test_temperature_sensor",
                "value_template": "{{ NaN | float }}",
            },
            {
                "platform": 'command_line',
                "command": 'echo 0',
                "name": "test_humidity_sensor",
                "value_template": "{{ NaN | float }}",
            },
            {
                "platform": "thermal_comfort",
                "sensors": {
                    "test_thermal_comfort": {
                        "temperature_sensor": "sensor.test_temperature_sensor",
                        "humidity_sensor": "sensor.test_humidity_sensor",
                    },
                },
            },
        ],
    },
},
})])
async def test_sensor_is_nan(hass, start_ha):
    assert len(hass.states.async_all(sensor.DOMAIN)) == 8
    for sensor_type in DEFAULT_SENSOR_TYPES:
        assert ATTR_TEMPERATURE in hass.states.get(f"{TEST_NAME}_{sensor_type}").attributes
        assert ATTR_HUMIDITY in hass.states.get(f"{TEST_NAME}_{sensor_type}").attributes
        assert hass.states.get(f"{TEST_NAME}_{sensor_type}").attributes[ATTR_TEMPERATURE] == None
        assert hass.states.get(f"{TEST_NAME}_{sensor_type}").attributes[ATTR_HUMIDITY] == None


@pytest.mark.parametrize("domains", [({
sensor.DOMAIN: {
    "count": 3,
    "config": {
        sensor.DOMAIN: [
            {
                "platform": 'command_line',
                "command": 'echo 0',
                "name": "test_temperature_sensor",
                "value_template": "{{ 'Unknown' }}",
            },
            {
                "platform": 'command_line',
                "command": 'echo 0',
                "name": "test_humidity_sensor",
                "value_template": "{{ 'asdf' }}",
            },
            {
                "platform": "thermal_comfort",
                "sensors": {
                    "test_thermal_comfort": {
                        "temperature_sensor": "sensor.test_temperature_sensor",
                        "humidity_sensor": "sensor.test_humidity_sensor",
                    },
                },
            },
        ],
    },
},
})])
async def test_sensor_unknown(hass, start_ha):
    assert len(hass.states.async_all(sensor.DOMAIN)) == 8
    for sensor_type in DEFAULT_SENSOR_TYPES:
        assert ATTR_TEMPERATURE in hass.states.get(f"{TEST_NAME}_{sensor_type}").attributes
        assert ATTR_HUMIDITY in hass.states.get(f"{TEST_NAME}_{sensor_type}").attributes
        assert hass.states.get(f"{TEST_NAME}_{sensor_type}").attributes[ATTR_TEMPERATURE] == None
        assert hass.states.get(f"{TEST_NAME}_{sensor_type}").attributes[ATTR_HUMIDITY] == None


@pytest.mark.parametrize("domains", DEFAULT_TEST_SENSORS)
async def test_sensor_unavailable(hass, start_ha):
    assert len(hass.states.async_all(sensor.DOMAIN)) == 8
    hass.states.async_remove("sensor.test_temperature_sensor")
    hass.states.async_remove("sensor.test_humidity_sensor")
    await hass.async_block_till_done()
    assert len(hass.states.async_all(sensor.DOMAIN)) == 6
    for sensor_type in DEFAULT_SENSOR_TYPES:
        assert ATTR_TEMPERATURE in hass.states.get(f"{TEST_NAME}_{sensor_type}").attributes
        assert ATTR_HUMIDITY in hass.states.get(f"{TEST_NAME}_{sensor_type}").attributes
        assert hass.states.get(f"{TEST_NAME}_{sensor_type}").attributes[ATTR_TEMPERATURE] == 25.0
        assert hass.states.get(f"{TEST_NAME}_{sensor_type}").attributes[ATTR_HUMIDITY] == 50.0
