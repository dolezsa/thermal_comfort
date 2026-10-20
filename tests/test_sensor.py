"""The test for the Thermal Comfort sensor platform."""

from collections.abc import Callable
import copy
from datetime import timedelta
import logging
import math
from unittest.mock import patch

import pytest
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    assert_setup_component,
    async_capture_events,
    async_fire_time_changed,
)

from custom_components.thermal_comfort.const import DOMAIN
from custom_components.thermal_comfort.sensor import (
    ATTR_FROST_POINT,
    ATTR_HUMIDITY,
    ATTR_PRESSURE,
    ATTR_RELATIVE_STRAIN_INDEX,
    ATTR_SUMMER_SCHARLAU_INDEX,
    ATTR_THOMS_DISCOMFORT_INDEX,
    ATTR_WINTER_SCHARLAU_INDEX,
    CONF_CUSTOM_ICONS,
    CONF_ENABLED_SENSORS,
    CONF_POLL,
    CONF_PRESSURE_SENSOR,
    CONF_SCAN_INTERVAL,
    CONF_SENSOR_TYPES,
    DEFAULT_SENSOR_TYPES,
    DeviceThermalComfort,
    DewPointPerception,
    FrostRisk,
    HumidexPerception,
    LegacySensorType,
    RelativeStrainPerception,
    ScharlauPerception,
    SensorThermalComfort,
    SensorType,
    SummerSimmerPerception,
    ThomsDiscomfortPerception,
    id_generator,
)
from homeassistant.components.sensor import DOMAIN as PLATFORM_DOMAIN, SensorDeviceClass
from homeassistant.components.template.const import DOMAIN as TEMPLATE_DOMAIN
from homeassistant.const import (
    ATTR_TEMPERATURE,
    SERVICE_RELOAD,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

from .const import ADVANCED_USER_INPUT

_LOGGER = logging.getLogger(__name__)

TEST_NAME = "sensor.test_thermal_comfort"

TEMPERATURE_TEST_SENSOR = {
    PLATFORM_DOMAIN: {
        "name": "test_temperature_sensor",
        "state": "{{ 25.0 | float }}",
    },
}

HUMIDITY_TEST_SENSOR = {
    PLATFORM_DOMAIN: {
        "name": "test_humidity_sensor",
        "state": "{{ 50.0 | float }}",
    },
}

DEFAULT_TEST_SENSORS = [
    "domains, config",
    [
        (
            [(TEMPLATE_DOMAIN, 2), (DOMAIN, 1)],
            {
                TEMPLATE_DOMAIN: [
                    TEMPERATURE_TEST_SENSOR,
                    HUMIDITY_TEST_SENSOR,
                ],
                DOMAIN: {
                    PLATFORM_DOMAIN: {
                        "name": "test_thermal_comfort",
                        "temperature_sensor": "sensor.test_temperature_sensor",
                        "humidity_sensor": "sensor.test_humidity_sensor",
                        "unique_id": "unique_thermal_comfort_id",
                    },
                },
            },
        ),
    ],
]

PRESSURE_TEST_SENSOR = {
    PLATFORM_DOMAIN: {
        "name": "test_pressure_sensor",
        "state": "{{ 1000.0 | float }}",
        "unit_of_measurement": "hPa",
        "device_class": "pressure",
    },
}

PRESSURE_TEST_SENSORS = [
    "domains, config",
    [
        (
            [(TEMPLATE_DOMAIN, 3), (DOMAIN, 1)],
            {
                TEMPLATE_DOMAIN: [
                    TEMPERATURE_TEST_SENSOR,
                    HUMIDITY_TEST_SENSOR,
                    PRESSURE_TEST_SENSOR,
                ],
                DOMAIN: {
                    PLATFORM_DOMAIN: {
                        "name": "test_thermal_comfort",
                        "temperature_sensor": "sensor.test_temperature_sensor",
                        "humidity_sensor": "sensor.test_humidity_sensor",
                        "pressure_sensor": "sensor.test_pressure_sensor",
                        "unique_id": "unique_thermal_comfort_id",
                    },
                },
            },
        ),
    ],
]

LEN_DEFAULT_SENSORS = len(DEFAULT_SENSOR_TYPES)


def get_sensor(hass, sensor_type: SensorType) -> str:
    """Get test sensor id."""
    return hass.states.get(f"{TEST_NAME}_{sensor_type}")


@pytest.mark.parametrize(*DEFAULT_TEST_SENSORS)
async def test_config(hass, start_ha):
    """Test basic config."""
    assert len(hass.states.async_all(PLATFORM_DOMAIN)) == LEN_DEFAULT_SENSORS + 2


@pytest.mark.parametrize(*DEFAULT_TEST_SENSORS)
async def test_properties(hass, start_ha):
    """Test if properties are set up correctly."""
    for sensor_type in DEFAULT_SENSOR_TYPES:
        assert ATTR_TEMPERATURE in get_sensor(hass, sensor_type).attributes
        assert ATTR_HUMIDITY in get_sensor(hass, sensor_type).attributes
        assert get_sensor(hass, sensor_type).attributes[ATTR_TEMPERATURE] == 25.0
        assert get_sensor(hass, sensor_type).attributes[ATTR_HUMIDITY] == 50.0


@pytest.mark.parametrize(*DEFAULT_TEST_SENSORS)
async def test_absolutehumidity(hass, start_ha):
    """Test if absolute humidity is calculated correctly."""
    assert get_sensor(hass, SensorType.ABSOLUTE_HUMIDITY) is not None
    assert get_sensor(hass, SensorType.ABSOLUTE_HUMIDITY).state == "11.5128065738593"
    assert (
        get_sensor(hass, SensorType.ABSOLUTE_HUMIDITY).attributes["device_class"]
        == SensorDeviceClass.ABSOLUTE_HUMIDITY
    )

    hass.states.async_set("sensor.test_temperature_sensor", "15.0")
    await hass.async_block_till_done()
    assert get_sensor(hass, SensorType.ABSOLUTE_HUMIDITY).state == "6.40873986839343"

    hass.states.async_set("sensor.test_humidity_sensor", "25.0")
    await hass.async_block_till_done()
    assert get_sensor(hass, SensorType.ABSOLUTE_HUMIDITY).state == "3.20436993419671"


@pytest.mark.parametrize(*DEFAULT_TEST_SENSORS)
async def test_heatindex(hass, start_ha):
    """Test if heat index is calculated correctly."""
    assert get_sensor(hass, SensorType.HEAT_INDEX) is not None
    assert get_sensor(hass, SensorType.HEAT_INDEX).state == "24.8611111111111"

    hass.states.async_set("sensor.test_temperature_sensor", "15.0")
    await hass.async_block_till_done()
    assert get_sensor(hass, SensorType.HEAT_INDEX).state == "13.8611111111111"

    hass.states.async_set("sensor.test_humidity_sensor", "25.0")
    await hass.async_block_till_done()
    assert get_sensor(hass, SensorType.HEAT_INDEX).state == "13.2083333333333"

    hass.states.async_set("sensor.test_humidity_sensor", "12.0")
    await hass.async_block_till_done()
    hass.states.async_set("sensor.test_temperature_sensor", "28.0")
    await hass.async_block_till_done()
    assert get_sensor(hass, SensorType.HEAT_INDEX).state == "26.5451914107181"


@pytest.mark.parametrize(*DEFAULT_TEST_SENSORS)
async def test_humidex(hass, start_ha):
    """Test if humidex is calculated correctly."""
    assert get_sensor(hass, SensorType.HUMIDEX) is not None
    assert get_sensor(hass, SensorType.HUMIDEX).state == "28.2925656121491"

    hass.states.async_set("sensor.test_temperature_sensor", "15.0")
    await hass.async_block_till_done()
    assert get_sensor(hass, SensorType.HUMIDEX).state == "14.18042805384"

    hass.states.async_set("sensor.test_humidity_sensor", "25.0")
    await hass.async_block_till_done()
    assert get_sensor(hass, SensorType.HUMIDEX).state == "11.8124622223777"

    hass.states.async_set("sensor.test_humidity_sensor", "12.0")
    await hass.async_block_till_done()
    hass.states.async_set("sensor.test_temperature_sensor", "28.0")
    await hass.async_block_till_done()
    assert get_sensor(hass, SensorType.HUMIDEX).state == "24.9644772432578"


@pytest.mark.parametrize(*DEFAULT_TEST_SENSORS)
async def test_humidex_perception(hass, start_ha):
    """Test if humidex perception is calculated correctly."""
    assert get_sensor(hass, SensorType.HUMIDEX_PERCEPTION) is not None
    assert (
        get_sensor(hass, SensorType.HUMIDEX_PERCEPTION).state
        == HumidexPerception.COMFORTABLE
    )

    hass.states.async_set("sensor.test_temperature_sensor", "26.1")
    hass.states.async_set("sensor.test_humidity_sensor", "50.03")
    await hass.async_block_till_done()
    assert get_sensor(hass, SensorType.HUMIDEX).state == "30.0035339225107"
    assert (
        get_sensor(hass, SensorType.HUMIDEX_PERCEPTION).state
        == HumidexPerception.NOTICABLE_DISCOMFORT
    )

    hass.states.async_set("sensor.test_temperature_sensor", "29.06")
    hass.states.async_set("sensor.test_humidity_sensor", "51.0")
    await hass.async_block_till_done()
    assert get_sensor(hass, SensorType.HUMIDEX).state == "35.0014998241678"
    assert (
        get_sensor(hass, SensorType.HUMIDEX_PERCEPTION).state
        == HumidexPerception.EVIDENT_DISCOMFORT
    )

    hass.states.async_set("sensor.test_temperature_sensor", "34.67")
    await hass.async_block_till_done()
    assert get_sensor(hass, SensorType.HUMIDEX).state == "45.0017649028272"
    assert (
        get_sensor(hass, SensorType.HUMIDEX_PERCEPTION).state
        == HumidexPerception.DANGEROUS_DISCOMFORT
    )

    hass.states.async_set("sensor.test_temperature_sensor", "35.95")
    hass.states.async_set("sensor.test_humidity_sensor", "70")
    await hass.async_block_till_done()
    assert get_sensor(hass, SensorType.HUMIDEX).state == "54.0070687092117"
    assert (
        get_sensor(hass, SensorType.HUMIDEX_PERCEPTION).state
        == HumidexPerception.HEAT_STROKE
    )


@pytest.mark.parametrize(*DEFAULT_TEST_SENSORS)
async def test_dew_point(hass, start_ha):
    """Test if dew point is calculated correctly."""
    assert get_sensor(hass, SensorType.DEW_POINT) is not None
    assert get_sensor(hass, SensorType.DEW_POINT).state == "13.8753224672013"

    hass.states.async_set("sensor.test_temperature_sensor", "15.0")
    await hass.async_block_till_done()
    assert get_sensor(hass, SensorType.DEW_POINT).state == "4.67503901377299"

    hass.states.async_set("sensor.test_humidity_sensor", "25.0")
    await hass.async_block_till_done()
    assert get_sensor(hass, SensorType.DEW_POINT).state == "-4.86267786296348"


@pytest.mark.parametrize(*DEFAULT_TEST_SENSORS)
async def test_dew_point_perception(hass, start_ha):
    """Test if dew point perception is calculated correctly."""
    hass.states.async_set("sensor.test_temperature_sensor", "20.77")
    await hass.async_block_till_done()
    assert get_sensor(hass, SensorType.DEW_POINT_PERCEPTION) is not None
    assert get_sensor(hass, SensorType.DEW_POINT).state == "9.98817292919442"
    assert (
        get_sensor(hass, SensorType.DEW_POINT_PERCEPTION).state
        == DewPointPerception.DRY
    )

    hass.states.async_set("sensor.test_temperature_sensor", "24.0")
    await hass.async_block_till_done()
    assert get_sensor(hass, SensorType.DEW_POINT).state == "12.9570044368822"
    assert (
        get_sensor(hass, SensorType.DEW_POINT_PERCEPTION).state
        == DewPointPerception.VERY_COMFORTABLE
    )

    hass.states.async_set("sensor.test_humidity_sensor", "60.83")
    await hass.async_block_till_done()
    assert get_sensor(hass, SensorType.DEW_POINT).state == "15.9907471577538"
    assert (
        get_sensor(hass, SensorType.DEW_POINT_PERCEPTION).state
        == DewPointPerception.COMFORTABLE
    )

    hass.states.async_set("sensor.test_temperature_sensor", "24.01")
    await hass.async_block_till_done()
    assert get_sensor(hass, SensorType.DEW_POINT).state == "16.0001522929822"
    assert (
        get_sensor(hass, SensorType.DEW_POINT_PERCEPTION).state
        == DewPointPerception.OK_BUT_HUMID
    )

    hass.states.async_set("sensor.test_humidity_sensor", "69.05")
    await hass.async_block_till_done()
    assert get_sensor(hass, SensorType.DEW_POINT).state == "18.0002749607952"
    assert (
        get_sensor(hass, SensorType.DEW_POINT_PERCEPTION).state
        == DewPointPerception.SOMEWHAT_UNCOMFORTABLE
    )

    hass.states.async_set("sensor.test_humidity_sensor", "79.6")
    await hass.async_block_till_done()
    hass.states.async_set("sensor.test_temperature_sensor", "26.00")
    await hass.async_block_till_done()
    assert get_sensor(hass, SensorType.DEW_POINT).state == "22.2150631359531"
    assert (
        get_sensor(hass, SensorType.DEW_POINT_PERCEPTION).state
        == DewPointPerception.QUITE_UNCOMFORTABLE
    )

    hass.states.async_set("sensor.test_humidity_sensor", "85.0")
    await hass.async_block_till_done()
    hass.states.async_set("sensor.test_temperature_sensor", "26.85")
    await hass.async_block_till_done()
    assert get_sensor(hass, SensorType.DEW_POINT).state == "24.1299575993527"
    assert (
        get_sensor(hass, SensorType.DEW_POINT_PERCEPTION).state
        == DewPointPerception.EXTREMELY_UNCOMFORTABLE
    )

    hass.states.async_set("sensor.test_humidity_sensor", "95.0")
    await hass.async_block_till_done()
    hass.states.async_set("sensor.test_temperature_sensor", "26.856")
    await hass.async_block_till_done()
    assert get_sensor(hass, SensorType.DEW_POINT).state == "26.0021323711165"
    assert (
        get_sensor(hass, SensorType.DEW_POINT_PERCEPTION).state
        == DewPointPerception.SEVERELY_HIGH
    )


@pytest.mark.parametrize(*DEFAULT_TEST_SENSORS)
async def test_frost_point(hass, start_ha):
    """Test if frost point is calculated correctly."""
    assert get_sensor(hass, SensorType.FROST_POINT) is not None
    assert get_sensor(hass, SensorType.FROST_POINT).state == "10.4218508495602"

    hass.states.async_set("sensor.test_temperature_sensor", "15.0")
    await hass.async_block_till_done()
    assert get_sensor(hass, SensorType.FROST_POINT).state == "2.72509864924086"

    hass.states.async_set("sensor.test_humidity_sensor", "25.0")
    await hass.async_block_till_done()
    assert get_sensor(hass, SensorType.FROST_POINT).state == "-6.8126182274957"


@pytest.mark.parametrize(*DEFAULT_TEST_SENSORS)
async def test_frost_risk(hass, start_ha):
    """Test if frost risk is calculated correctly."""
    assert get_sensor(hass, SensorType.FROST_RISK) is not None
    assert get_sensor(hass, SensorType.FROST_RISK).state == FrostRisk.NONE
    assert (
        get_sensor(hass, SensorType.FROST_RISK).attributes[ATTR_FROST_POINT]
        == 10.421850849560201
    )

    hass.states.async_set("sensor.test_temperature_sensor", "0")
    hass.states.async_set("sensor.test_humidity_sensor", "57.7")
    await hass.async_block_till_done()
    assert get_sensor(hass, SensorType.FROST_RISK).state == FrostRisk.LOW
    assert (
        get_sensor(hass, SensorType.FROST_RISK).attributes[ATTR_FROST_POINT]
        == -7.346077951913912
    )

    hass.states.async_set("sensor.test_temperature_sensor", "4.0")
    hass.states.async_set("sensor.test_humidity_sensor", "80.65")
    await hass.async_block_till_done()
    assert get_sensor(hass, SensorType.FROST_RISK).state == FrostRisk.MEDIUM
    assert (
        get_sensor(hass, SensorType.FROST_RISK).attributes[ATTR_FROST_POINT]
        == 0.4945717077964673
    )

    hass.states.async_set("sensor.test_temperature_sensor", "1.0")
    hass.states.async_set("sensor.test_humidity_sensor", "90.00")
    await hass.async_block_till_done()
    assert get_sensor(hass, SensorType.FROST_RISK).state == FrostRisk.HIGH
    assert (
        get_sensor(hass, SensorType.FROST_RISK).attributes[ATTR_FROST_POINT]
        == -0.5732593367861227
    )


@pytest.mark.parametrize(*DEFAULT_TEST_SENSORS)
async def test_summer_simmer_index(hass, start_ha):
    """Test if simmer index is calculated correctly."""
    assert get_sensor(hass, SensorType.SUMMER_SIMMER_INDEX) is not None
    assert get_sensor(hass, SensorType.SUMMER_SIMMER_INDEX).state == "29.6025"

    hass.states.async_set("sensor.test_temperature_sensor", "15.0")
    await hass.async_block_till_done()
    assert get_sensor(hass, SensorType.SUMMER_SIMMER_INDEX).state == "15.2475"

    hass.states.async_set("sensor.test_humidity_sensor", "35.0")
    await hass.async_block_till_done()
    hass.states.async_set("sensor.test_temperature_sensor", "25.0")
    await hass.async_block_till_done()
    assert get_sensor(hass, SensorType.SUMMER_SIMMER_INDEX).state == "27.87825"


@pytest.mark.parametrize(*DEFAULT_TEST_SENSORS)
async def test_summer_simmer_perception(hass, start_ha):
    """Test if simmer zone is calculated correctly."""
    hass.states.async_set("sensor.test_temperature_sensor", "20.77")
    await hass.async_block_till_done()
    assert get_sensor(hass, SensorType.SUMMER_SIMMER_PERCEPTION) is not None
    assert get_sensor(hass, SensorType.SUMMER_SIMMER_INDEX).state == "23.530335"
    assert (
        get_sensor(hass, SensorType.SUMMER_SIMMER_PERCEPTION).state
        == SummerSimmerPerception.SLIGHTLY_COOL
    )

    hass.states.async_set("sensor.test_temperature_sensor", "24.0")
    await hass.async_block_till_done()
    assert get_sensor(hass, SensorType.SUMMER_SIMMER_INDEX).state == "28.167"
    assert (
        get_sensor(hass, SensorType.SUMMER_SIMMER_PERCEPTION).state
        == SummerSimmerPerception.COMFORTABLE
    )

    hass.states.async_set("sensor.test_humidity_sensor", "60.82")
    await hass.async_block_till_done()
    assert get_sensor(hass, SensorType.SUMMER_SIMMER_INDEX).state == "29.2929292"
    assert (
        get_sensor(hass, SensorType.SUMMER_SIMMER_PERCEPTION).state
        == SummerSimmerPerception.SLIGHTLY_WARM
    )

    hass.states.async_set("sensor.test_temperature_sensor", "24.01")
    await hass.async_block_till_done()
    assert get_sensor(hass, SensorType.SUMMER_SIMMER_INDEX).state == "29.308462498"
    assert (
        get_sensor(hass, SensorType.SUMMER_SIMMER_PERCEPTION).state
        == SummerSimmerPerception.SLIGHTLY_WARM
    )

    hass.states.async_set("sensor.test_humidity_sensor", "69.03")
    await hass.async_block_till_done()
    assert get_sensor(hass, SensorType.SUMMER_SIMMER_INDEX).state == "30.163689167"
    assert (
        get_sensor(hass, SensorType.SUMMER_SIMMER_PERCEPTION).state
        == SummerSimmerPerception.SLIGHTLY_WARM
    )

    hass.states.async_set("sensor.test_humidity_sensor", "79.6")
    await hass.async_block_till_done()
    hass.states.async_set("sensor.test_temperature_sensor", "26.0")
    await hass.async_block_till_done()
    assert get_sensor(hass, SensorType.SUMMER_SIMMER_INDEX).state == "34.762864"
    assert (
        get_sensor(hass, SensorType.SUMMER_SIMMER_PERCEPTION).state
        == SummerSimmerPerception.INCREASING_DISCOMFORT
    )

    hass.states.async_set("sensor.test_humidity_sensor", "85.0")
    await hass.async_block_till_done()
    hass.states.async_set("sensor.test_temperature_sensor", "26.85")
    await hass.async_block_till_done()
    assert get_sensor(hass, SensorType.SUMMER_SIMMER_INDEX).state == "36.9865525"
    assert (
        get_sensor(hass, SensorType.SUMMER_SIMMER_PERCEPTION).state
        == SummerSimmerPerception.INCREASING_DISCOMFORT
    )

    hass.states.async_set("sensor.test_humidity_sensor", "80.0")
    await hass.async_block_till_done()
    hass.states.async_set("sensor.test_temperature_sensor", "29.0")
    await hass.async_block_till_done()
    assert get_sensor(hass, SensorType.SUMMER_SIMMER_INDEX).state == "40.0998"
    assert (
        get_sensor(hass, SensorType.SUMMER_SIMMER_PERCEPTION).state
        == SummerSimmerPerception.EXTREMELY_WARM
    )

    hass.states.async_set("sensor.test_humidity_sensor", "45.0")
    await hass.async_block_till_done()
    hass.states.async_set("sensor.test_temperature_sensor", "40.0")
    await hass.async_block_till_done()
    assert get_sensor(hass, SensorType.SUMMER_SIMMER_INDEX).state == "49.7435"
    assert (
        get_sensor(hass, SensorType.SUMMER_SIMMER_PERCEPTION).state
        == SummerSimmerPerception.DANGER_OF_HEATSTROKE
    )

    hass.states.async_set("sensor.test_temperature_sensor", "45.0")
    await hass.async_block_till_done()
    assert (
        get_sensor(hass, SensorType.SUMMER_SIMMER_PERCEPTION).state
        == SummerSimmerPerception.EXTREME_DANGER_OF_HEATSTROKE
    )

    hass.states.async_set("sensor.test_humidity_sensor", "100.0")
    await hass.async_block_till_done()
    hass.states.async_set("sensor.test_temperature_sensor", "56.0")
    await hass.async_block_till_done()
    assert (
        get_sensor(hass, SensorType.SUMMER_SIMMER_PERCEPTION).state
        == SummerSimmerPerception.CIRCULATORY_COLLAPSE_IMMINENT
    )


@pytest.mark.parametrize(*DEFAULT_TEST_SENSORS)
async def test_moist_air_enthalpy(hass, start_ha):
    """Test if moist air enthalpy is calculated correctly."""
    assert get_sensor(hass, SensorType.MOIST_AIR_ENTHALPY) is not None
    assert get_sensor(hass, SensorType.MOIST_AIR_ENTHALPY).state == "50.3219588021847"

    hass.states.async_set("sensor.test_temperature_sensor", "20.77")
    hass.states.async_set("sensor.test_humidity_sensor", "60.82")
    await hass.async_block_till_done()
    assert get_sensor(hass, SensorType.MOIST_AIR_ENTHALPY) is not None
    assert get_sensor(hass, SensorType.MOIST_AIR_ENTHALPY).state == "44.4961886780509"


@pytest.mark.parametrize(*DEFAULT_TEST_SENSORS)
async def test_relative_strain_perception(hass, start_ha):
    """Test if relative strain perception is calculated correctly."""
    assert get_sensor(hass, SensorType.RELATIVE_STRAIN_PERCEPTION) is not None
    assert (
        get_sensor(hass, SensorType.RELATIVE_STRAIN_PERCEPTION).attributes[
            ATTR_RELATIVE_STRAIN_INDEX
        ]
        == 0.09
    )
    assert (
        get_sensor(hass, SensorType.RELATIVE_STRAIN_PERCEPTION).state
        == RelativeStrainPerception.OUTSIDE_CALCULABLE_RANGE
    )

    hass.states.async_set("sensor.test_temperature_sensor", "35.01")
    await hass.async_block_till_done()
    assert get_sensor(hass, SensorType.RELATIVE_STRAIN_PERCEPTION) is not None
    assert (
        get_sensor(hass, SensorType.RELATIVE_STRAIN_PERCEPTION).attributes[
            ATTR_RELATIVE_STRAIN_INDEX
        ]
        == 0.47
    )
    assert (
        get_sensor(hass, SensorType.RELATIVE_STRAIN_PERCEPTION).state
        == RelativeStrainPerception.OUTSIDE_CALCULABLE_RANGE
    )

    hass.states.async_set("sensor.test_temperature_sensor", "26.00")
    hass.states.async_set("sensor.test_humidity_sensor", "70.00")
    await hass.async_block_till_done()
    assert (
        get_sensor(hass, SensorType.RELATIVE_STRAIN_PERCEPTION).attributes[
            ATTR_RELATIVE_STRAIN_INDEX
        ]
        == 0.14
    )
    assert (
        get_sensor(hass, SensorType.RELATIVE_STRAIN_PERCEPTION).state
        == RelativeStrainPerception.COMFORTABLE
    )

    hass.states.async_set("sensor.test_temperature_sensor", "27.00")
    hass.states.async_set("sensor.test_humidity_sensor", "50.00")
    await hass.async_block_till_done()
    assert (
        get_sensor(hass, SensorType.RELATIVE_STRAIN_PERCEPTION).attributes[
            ATTR_RELATIVE_STRAIN_INDEX
        ]
        == 0.15
    )
    assert (
        get_sensor(hass, SensorType.RELATIVE_STRAIN_PERCEPTION).state
        == RelativeStrainPerception.SLIGHT_DISCOMFORT
    )

    hass.states.async_set("sensor.test_temperature_sensor", "31.00")
    hass.states.async_set("sensor.test_humidity_sensor", "38.40")
    await hass.async_block_till_done()
    assert (
        get_sensor(hass, SensorType.RELATIVE_STRAIN_PERCEPTION).attributes[
            ATTR_RELATIVE_STRAIN_INDEX
        ]
        == 0.25
    )
    assert (
        get_sensor(hass, SensorType.RELATIVE_STRAIN_PERCEPTION).state
        == RelativeStrainPerception.DISCOMFORT
    )

    hass.states.async_set("sensor.test_temperature_sensor", "32.00")
    hass.states.async_set("sensor.test_humidity_sensor", "56.00")
    await hass.async_block_till_done()
    assert (
        get_sensor(hass, SensorType.RELATIVE_STRAIN_PERCEPTION).attributes[
            ATTR_RELATIVE_STRAIN_INDEX
        ]
        == 0.35
    )
    assert (
        get_sensor(hass, SensorType.RELATIVE_STRAIN_PERCEPTION).state
        == RelativeStrainPerception.SIGNIFICANT_DISCOMFORT
    )

    hass.states.async_set("sensor.test_temperature_sensor", "31.50")
    hass.states.async_set("sensor.test_humidity_sensor", "75.00")
    await hass.async_block_till_done()
    assert (
        get_sensor(hass, SensorType.RELATIVE_STRAIN_PERCEPTION).attributes[
            ATTR_RELATIVE_STRAIN_INDEX
        ]
        == 0.45
    )
    assert (
        get_sensor(hass, SensorType.RELATIVE_STRAIN_PERCEPTION).state
        == RelativeStrainPerception.EXTREME_DISCOMFORT
    )


@pytest.mark.parametrize(*DEFAULT_TEST_SENSORS)
async def test_summer_scharlau_perception(hass, start_ha):
    """Test if summer scharlau perception is calculated correctly."""
    assert get_sensor(hass, SensorType.SUMMER_SCHARLAU_PERCEPTION) is not None
    assert (
        get_sensor(hass, SensorType.SUMMER_SCHARLAU_PERCEPTION).attributes[
            ATTR_SUMMER_SCHARLAU_INDEX
        ]
        == 3.13
    )
    assert (
        get_sensor(hass, SensorType.SUMMER_SCHARLAU_PERCEPTION).state
        == ScharlauPerception.COMFORTABLE
    )

    hass.states.async_set("sensor.test_temperature_sensor", "36.291")
    hass.states.async_set("sensor.test_humidity_sensor", "31.00")
    await hass.async_block_till_done()
    assert (
        get_sensor(hass, SensorType.SUMMER_SCHARLAU_PERCEPTION).attributes[
            ATTR_SUMMER_SCHARLAU_INDEX
        ]
        == 0
    )
    assert (
        get_sensor(hass, SensorType.SUMMER_SCHARLAU_PERCEPTION).state
        == ScharlauPerception.COMFORTABLE
    )

    hass.states.async_set("sensor.test_temperature_sensor", "36.31")
    hass.states.async_set("sensor.test_humidity_sensor", "31.00")
    await hass.async_block_till_done()
    assert (
        get_sensor(hass, SensorType.SUMMER_SCHARLAU_PERCEPTION).attributes[
            ATTR_SUMMER_SCHARLAU_INDEX
        ]
        == -0.01
    )
    assert (
        get_sensor(hass, SensorType.SUMMER_SCHARLAU_PERCEPTION).state
        == ScharlauPerception.SLIGHTLY_UNCOMFORTABLE
    )

    hass.states.async_set("sensor.test_temperature_sensor", "36.23")
    hass.states.async_set("sensor.test_humidity_sensor", "33.00")
    await hass.async_block_till_done()
    assert (
        get_sensor(hass, SensorType.SUMMER_SCHARLAU_PERCEPTION).attributes[
            ATTR_SUMMER_SCHARLAU_INDEX
        ]
        == -1.0
    )
    assert (
        get_sensor(hass, SensorType.SUMMER_SCHARLAU_PERCEPTION).state
        == ScharlauPerception.MODERATELY_UNCOMFORTABLE
    )

    hass.states.async_set("sensor.test_temperature_sensor", "35.82")
    hass.states.async_set("sensor.test_humidity_sensor", "38.00")
    await hass.async_block_till_done()
    assert (
        get_sensor(hass, SensorType.SUMMER_SCHARLAU_PERCEPTION).attributes[
            ATTR_SUMMER_SCHARLAU_INDEX
        ]
        == -3.0
    )
    assert (
        get_sensor(hass, SensorType.SUMMER_SCHARLAU_PERCEPTION).state
        == ScharlauPerception.HIGHLY_UNCOMFORTABLE
    )

    hass.states.async_set("sensor.test_temperature_sensor", "39.01")
    await hass.async_block_till_done()
    assert (
        get_sensor(hass, SensorType.SUMMER_SCHARLAU_PERCEPTION).state
        == ScharlauPerception.OUTSIDE_CALCULABLE_RANGE
    )

    hass.states.async_set("sensor.test_temperature_sensor", "15.99")
    await hass.async_block_till_done()
    assert (
        get_sensor(hass, SensorType.SUMMER_SCHARLAU_PERCEPTION).state
        == ScharlauPerception.OUTSIDE_CALCULABLE_RANGE
    )

    hass.states.async_set("sensor.test_temperature_sensor", "30.00")
    hass.states.async_set("sensor.test_humidity_sensor", "29.99")
    await hass.async_block_till_done()
    assert (
        get_sensor(hass, SensorType.SUMMER_SCHARLAU_PERCEPTION).state
        == ScharlauPerception.OUTSIDE_CALCULABLE_RANGE
    )


@pytest.mark.parametrize(*DEFAULT_TEST_SENSORS)
async def test_winter_scharlau_perception(hass, start_ha):
    """Test if winter scharlau perception is calculated correctly."""
    assert get_sensor(hass, SensorType.WINTER_SCHARLAU_PERCEPTION) is not None
    assert (
        get_sensor(hass, SensorType.WINTER_SCHARLAU_PERCEPTION).attributes[
            ATTR_WINTER_SCHARLAU_INDEX
        ]
        == 25.98
    )
    assert (
        get_sensor(hass, SensorType.WINTER_SCHARLAU_PERCEPTION).state
        == ScharlauPerception.OUTSIDE_CALCULABLE_RANGE
    )

    hass.states.async_set("sensor.test_temperature_sensor", "1.83")
    hass.states.async_set("sensor.test_humidity_sensor", "75.00")
    await hass.async_block_till_done()
    assert (
        get_sensor(hass, SensorType.WINTER_SCHARLAU_PERCEPTION).attributes[
            ATTR_WINTER_SCHARLAU_INDEX
        ]
        == 0
    )
    assert (
        get_sensor(hass, SensorType.WINTER_SCHARLAU_PERCEPTION).state
        == ScharlauPerception.COMFORTABLE
    )

    hass.states.async_set("sensor.test_temperature_sensor", "1.82")
    await hass.async_block_till_done()
    assert (
        get_sensor(hass, SensorType.WINTER_SCHARLAU_PERCEPTION).attributes[
            ATTR_WINTER_SCHARLAU_INDEX
        ]
        == -0.01
    )
    assert (
        get_sensor(hass, SensorType.WINTER_SCHARLAU_PERCEPTION).state
        == ScharlauPerception.SLIGHTLY_UNCOMFORTABLE
    )

    hass.states.async_set("sensor.test_temperature_sensor", "-1.59")
    hass.states.async_set("sensor.test_humidity_sensor", "71.00")
    await hass.async_block_till_done()
    assert (
        get_sensor(hass, SensorType.WINTER_SCHARLAU_PERCEPTION).attributes[
            ATTR_WINTER_SCHARLAU_INDEX
        ]
        == -2.99
    )
    assert (
        get_sensor(hass, SensorType.WINTER_SCHARLAU_PERCEPTION).state
        == ScharlauPerception.MODERATELY_UNCOMFORTABLE
    )

    hass.states.async_set("sensor.test_temperature_sensor", "-1.60")
    hass.states.async_set("sensor.test_humidity_sensor", "71.00")
    await hass.async_block_till_done()
    assert (
        get_sensor(hass, SensorType.WINTER_SCHARLAU_PERCEPTION).attributes[
            ATTR_WINTER_SCHARLAU_INDEX
        ]
        == -3.0
    )
    assert (
        get_sensor(hass, SensorType.WINTER_SCHARLAU_PERCEPTION).state
        == ScharlauPerception.HIGHLY_UNCOMFORTABLE
    )

    hass.states.async_set("sensor.test_temperature_sensor", "-6.01")
    await hass.async_block_till_done()
    assert (
        get_sensor(hass, SensorType.WINTER_SCHARLAU_PERCEPTION).state
        == ScharlauPerception.OUTSIDE_CALCULABLE_RANGE
    )

    hass.states.async_set("sensor.test_temperature_sensor", "6.01")
    await hass.async_block_till_done()
    assert (
        get_sensor(hass, SensorType.WINTER_SCHARLAU_PERCEPTION).state
        == ScharlauPerception.OUTSIDE_CALCULABLE_RANGE
    )

    hass.states.async_set("sensor.test_temperature_sensor", "6.00")
    hass.states.async_set("sensor.test_humidity_sensor", "39.00")
    await hass.async_block_till_done()
    assert (
        get_sensor(hass, SensorType.WINTER_SCHARLAU_PERCEPTION).state
        == ScharlauPerception.OUTSIDE_CALCULABLE_RANGE
    )


@pytest.mark.parametrize(*DEFAULT_TEST_SENSORS)
async def test_thoms_discomfort_perception(hass, start_ha):
    """Test if thoms discomfort perception is calculated correctly."""
    assert get_sensor(hass, SensorType.THOMS_DISCOMFORT_PERCEPTION) is not None
    assert (
        get_sensor(hass, SensorType.THOMS_DISCOMFORT_PERCEPTION).attributes[
            ATTR_THOMS_DISCOMFORT_INDEX
        ]
        == 21.5
    )
    assert (
        get_sensor(hass, SensorType.THOMS_DISCOMFORT_PERCEPTION).state
        == ThomsDiscomfortPerception.LESS_THAN_HALF
    )

    hass.states.async_set("sensor.test_temperature_sensor", "22.00")
    hass.states.async_set("sensor.test_humidity_sensor", "50.00")
    await hass.async_block_till_done()
    assert (
        get_sensor(hass, SensorType.THOMS_DISCOMFORT_PERCEPTION).attributes[
            ATTR_THOMS_DISCOMFORT_INDEX
        ]
        == 18.71
    )
    assert (
        get_sensor(hass, SensorType.THOMS_DISCOMFORT_PERCEPTION).state
        == ThomsDiscomfortPerception.NO_DISCOMFORT
    )

    hass.states.async_set("sensor.test_temperature_sensor", "24.47")
    hass.states.async_set("sensor.test_humidity_sensor", "50.05")
    await hass.async_block_till_done()
    assert (
        get_sensor(hass, SensorType.THOMS_DISCOMFORT_PERCEPTION).attributes[
            ATTR_THOMS_DISCOMFORT_INDEX
        ]
        == 21.01
    )
    assert (
        get_sensor(hass, SensorType.THOMS_DISCOMFORT_PERCEPTION).state
        == ThomsDiscomfortPerception.LESS_THAN_HALF
    )

    hass.states.async_set("sensor.test_temperature_sensor", "26.55")
    hass.states.async_set("sensor.test_humidity_sensor", "63.80")
    await hass.async_block_till_done()
    assert (
        get_sensor(hass, SensorType.THOMS_DISCOMFORT_PERCEPTION).attributes[
            ATTR_THOMS_DISCOMFORT_INDEX
        ]
        == 24.01
    )
    assert (
        get_sensor(hass, SensorType.THOMS_DISCOMFORT_PERCEPTION).state
        == ThomsDiscomfortPerception.MORE_THAN_HALF
    )

    hass.states.async_set("sensor.test_temperature_sensor", "29.78")
    hass.states.async_set("sensor.test_humidity_sensor", "62.70")
    await hass.async_block_till_done()
    assert (
        get_sensor(hass, SensorType.THOMS_DISCOMFORT_PERCEPTION).attributes[
            ATTR_THOMS_DISCOMFORT_INDEX
        ]
        == 27.01
    )
    assert (
        get_sensor(hass, SensorType.THOMS_DISCOMFORT_PERCEPTION).state
        == ThomsDiscomfortPerception.MOST
    )

    hass.states.async_set("sensor.test_temperature_sensor", "31.13")
    hass.states.async_set("sensor.test_humidity_sensor", "71.50")
    await hass.async_block_till_done()
    assert (
        get_sensor(hass, SensorType.THOMS_DISCOMFORT_PERCEPTION).attributes[
            ATTR_THOMS_DISCOMFORT_INDEX
        ]
        == 29.01
    )
    assert (
        get_sensor(hass, SensorType.THOMS_DISCOMFORT_PERCEPTION).state
        == ThomsDiscomfortPerception.EVERYONE
    )

    hass.states.async_set("sensor.test_temperature_sensor", "33.92")
    hass.states.async_set("sensor.test_humidity_sensor", "75.10")
    await hass.async_block_till_done()
    assert (
        get_sensor(hass, SensorType.THOMS_DISCOMFORT_PERCEPTION).attributes[
            ATTR_THOMS_DISCOMFORT_INDEX
        ]
        == 32.01
    )
    assert (
        get_sensor(hass, SensorType.THOMS_DISCOMFORT_PERCEPTION).state
        == ThomsDiscomfortPerception.DANGEROUS
    )


@pytest.mark.parametrize(
    "domains, config",
    [
        (
            [(TEMPLATE_DOMAIN, 2), (DOMAIN, 1)],
            {
                TEMPLATE_DOMAIN: [
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

    ent_reg = er.async_get(hass)

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
            [(TEMPLATE_DOMAIN, 2), (DOMAIN, 1)],
            {
                TEMPLATE_DOMAIN: [
                    TEMPERATURE_TEST_SENSOR,
                    HUMIDITY_TEST_SENSOR,
                ],
                DOMAIN: {
                    PLATFORM_DOMAIN: {
                        "name": "test_thermal_comfort",
                        "temperature_sensor": "sensor.test_temperature_sensor",
                        "humidity_sensor": "sensor.test_humidity_sensor",
                        "icon_template": "mdi:thermometer",
                        "unique_id": "unique_thermal_comfort_id",
                    },
                },
            },
        ),
    ],
)
async def test_valid_icon_template(hass, start_ha):
    """Test if icon template is working as expected."""
    assert len(hass.states.async_all(PLATFORM_DOMAIN)) == LEN_DEFAULT_SENSORS + 2
    for sensor_type in DEFAULT_SENSOR_TYPES:
        assert get_sensor(hass, sensor_type).attributes["icon"] == "mdi:thermometer"


@pytest.mark.parametrize(*DEFAULT_TEST_SENSORS)
async def test_zero_degree_celcius(hass, start_ha):
    """Test if zero degree celsius does not cause any errors."""
    assert len(hass.states.async_all(PLATFORM_DOMAIN)) == LEN_DEFAULT_SENSORS + 2
    hass.states.async_set("sensor.test_temperature_sensor", "0")
    await hass.async_block_till_done()
    assert get_sensor(hass, SensorType.DEW_POINT) is not None
    assert get_sensor(hass, SensorType.DEW_POINT).state == "-9.18867399785112"
    assert get_sensor(hass, SensorType.SUMMER_SIMMER_INDEX) is not None
    assert get_sensor(hass, SensorType.SUMMER_SIMMER_INDEX).state == "0.0"


@pytest.mark.parametrize(
    "domains, config",
    [
        (
            [(TEMPLATE_DOMAIN, 2), (DOMAIN, 1)],
            {
                TEMPLATE_DOMAIN: [
                    TEMPERATURE_TEST_SENSOR,
                    HUMIDITY_TEST_SENSOR,
                ],
                DOMAIN: {
                    PLATFORM_DOMAIN: {
                        "name": "test_thermal_comfort",
                        "temperature_sensor": "sensor.test_temperature_sensor",
                        "humidity_sensor": "sensor.test_humidity_sensor",
                        "sensor_types": [
                            SensorType.ABSOLUTE_HUMIDITY,
                            SensorType.DEW_POINT,
                        ],
                        "unique_id": "unique_thermal_comfort_id",
                    },
                },
            },
        ),
    ],
)
async def test_sensor_types(hass, start_ha):
    """Test if configure sensor_types only creates the sensors specified."""
    assert len(hass.states.async_all(PLATFORM_DOMAIN)) == 4

    assert get_sensor(hass, SensorType.HEAT_INDEX) is None
    assert get_sensor(hass, SensorType.DEW_POINT_PERCEPTION) is None

    assert get_sensor(hass, SensorType.ABSOLUTE_HUMIDITY) is not None
    assert get_sensor(hass, SensorType.DEW_POINT) is not None


def test_sensor_type_from_string_rejects_unknown():
    """Test that an unknown sensor type in the YAML options is refused."""
    assert SensorType.from_string("dew_point") == SensorType.DEW_POINT
    with pytest.raises(ValueError, match="Unknown sensor type: bogus"):
        SensorType.from_string("bogus")


async def test_create_sensors(hass: HomeAssistant):
    """Test sensors update engine.

    When user remove sensor in integration config, then we should remove it from system
    :param hass: HomeAssistant: Home Assistant object
    """

    def get_eid(registry: er, _id):
        return registry.async_get_entity_id(
            domain="sensor", platform=DOMAIN, unique_id=_id
        )

    registry = er.async_get(hass)

    entry = MockConfigEntry(
        domain=DOMAIN, data=ADVANCED_USER_INPUT, entry_id="test", unique_id="uniqueid"
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # Make sure that sensors in registry
    for s in SensorType:
        assert get_eid(registry, id_generator(entry.unique_id, s)) is not None


@pytest.mark.parametrize(
    "domains, config",
    [
        (
            [(DOMAIN, 1)],
            {
                DOMAIN: {
                    PLATFORM_DOMAIN: {
                        "name": "test_thermal_comfort",
                        "temperature_sensor": "sensor.test_temperature_sensor",
                        "humidity_sensor": "sensor.test_humidity_sensor",
                        "sensor_types": [
                            SensorType.DEW_POINT_PERCEPTION,
                            SensorType.ABSOLUTE_HUMIDITY,
                        ],
                        "unique_id": "unique_thermal_comfort_id",
                    },
                },
            },
        ),
    ],
)
async def test_sensor_type_names(hass: HomeAssistant, start_ha: Callable) -> None:
    """Test if sensor types shortform can be used."""
    assert len(hass.states.async_all(PLATFORM_DOMAIN)) == 2
    assert (
        SensorType.DEW_POINT_PERCEPTION.to_name()
        in get_sensor(hass, SensorType.DEW_POINT_PERCEPTION).name
    )


@pytest.mark.parametrize(
    "domains, config",
    [
        (
            [(DOMAIN, 1)],
            {
                DOMAIN: {
                    CONF_SENSOR_TYPES: [
                        SensorType.ABSOLUTE_HUMIDITY,
                    ],
                    CONF_CUSTOM_ICONS: True,
                    PLATFORM_DOMAIN: [
                        {
                            "name": "test_thermal_comfort",
                            "temperature_sensor": "sensor.test_temperature_sensor",
                            "humidity_sensor": "sensor.test_humidity_sensor",
                            "sensor_types": [
                                SensorType.DEW_POINT_PERCEPTION,
                                SensorType.ABSOLUTE_HUMIDITY,
                            ],
                            "unique_id": "unique_thermal_comfort_id",
                        },
                        {
                            "name": "test_thermal_comfort2",
                            "temperature_sensor": "sensor.test_temperature_sensor",
                            "humidity_sensor": "sensor.test_humidity_sensor",
                            "unique_id": "unique_thermal_comfort_id2",
                        },
                    ],
                },
            },
        ),
    ],
)
async def test_global_options(hass: HomeAssistant, start_ha: Callable) -> None:
    """Test if global options are correctly set."""
    assert len(hass.states.async_all(PLATFORM_DOMAIN)) == 3
    assert (
        get_sensor(hass, SensorType.DEW_POINT_PERCEPTION).attributes["icon"]
        == "tc:thermal-perception"
    )


def remove_platform_entities(hass: HomeAssistant) -> None:
    """Remove all entities of the integration from the entity registry."""
    registry = er.async_get(hass)
    for entity in list(registry.entities.values()):
        if entity.platform == DOMAIN:
            registry.async_remove(entity.entity_id)


@pytest.mark.parametrize(*DEFAULT_TEST_SENSORS)
async def test_invalid_source_makes_sensors_unavailable(hass, start_ha):
    """Test that invalid source states make the sensors unavailable until they recover."""
    assert get_sensor(hass, SensorType.DEW_POINT).state != STATE_UNAVAILABLE

    for entity_id, bad_state in (
        ("sensor.test_temperature_sensor", STATE_UNAVAILABLE),
        ("sensor.test_temperature_sensor", STATE_UNKNOWN),
        ("sensor.test_temperature_sensor", "nan"),
        ("sensor.test_temperature_sensor", "100"),
        ("sensor.test_humidity_sensor", STATE_UNAVAILABLE),
        ("sensor.test_humidity_sensor", "0"),
        ("sensor.test_humidity_sensor", "110"),
    ):
        hass.states.async_set(entity_id, bad_state)
        await hass.async_block_till_done()
        for sensor_type in DEFAULT_SENSOR_TYPES:
            assert get_sensor(hass, sensor_type).state == STATE_UNAVAILABLE
        hass.states.async_set(entity_id, "25" if "temperature" in entity_id else "50")
        await hass.async_block_till_done()
        for sensor_type in DEFAULT_SENSOR_TYPES:
            assert get_sensor(hass, sensor_type).state != STATE_UNAVAILABLE

    assert get_sensor(hass, SensorType.DEW_POINT).attributes[ATTR_TEMPERATURE] == 25.0


@pytest.mark.parametrize(*DEFAULT_TEST_SENSORS)
async def test_humidity_overshoot_is_clipped(hass, start_ha):
    """Test that a small humidity overshoot is clipped to 100 percent."""
    hass.states.async_set("sensor.test_humidity_sensor", "103.5")
    await hass.async_block_till_done()
    sensor = get_sensor(hass, SensorType.DEW_POINT)
    assert sensor.state != STATE_UNAVAILABLE
    assert sensor.attributes[ATTR_HUMIDITY] == 100.0
    assert float(sensor.state) == pytest.approx(25.0, abs=0.1)


@pytest.mark.parametrize(
    "domains, config",
    [
        (
            [(DOMAIN, 1)],
            {
                DOMAIN: {
                    PLATFORM_DOMAIN: {
                        "name": "test_thermal_comfort",
                        "temperature_sensor": "sensor.test_temperature_sensor",
                        "humidity_sensor": "sensor.test_humidity_sensor",
                        "poll": True,
                        "scan_interval": 3600,
                        "unique_id": "unique_thermal_comfort_id",
                    },
                },
            },
        ),
    ],
)
async def test_poll_updates_right_after_first_valid_values(hass, start_ha):
    """Test that polling sensors do not wait for the next poll after the sources appear."""
    assert get_sensor(hass, SensorType.DEW_POINT).state == STATE_UNAVAILABLE

    hass.states.async_set("sensor.test_temperature_sensor", "25")
    await hass.async_block_till_done()
    assert get_sensor(hass, SensorType.DEW_POINT).state == STATE_UNAVAILABLE

    hass.states.async_set("sensor.test_humidity_sensor", "50")
    await hass.async_block_till_done()
    assert get_sensor(hass, SensorType.DEW_POINT).state != STATE_UNAVAILABLE
    first = get_sensor(hass, SensorType.DEW_POINT).state

    # further valid values wait for the poll
    hass.states.async_set("sensor.test_temperature_sensor", "30")
    await hass.async_block_till_done()
    assert get_sensor(hass, SensorType.DEW_POINT).state == first

    # going invalid shows up immediately, and so does recovery
    hass.states.async_set("sensor.test_temperature_sensor", STATE_UNAVAILABLE)
    await hass.async_block_till_done()
    assert get_sensor(hass, SensorType.DEW_POINT).state == STATE_UNAVAILABLE
    hass.states.async_set("sensor.test_temperature_sensor", "30")
    await hass.async_block_till_done()
    assert get_sensor(hass, SensorType.DEW_POINT).state not in (
        first,
        STATE_UNAVAILABLE,
    )

    remove_platform_entities(hass)
    await hass.async_block_till_done()


@pytest.mark.parametrize("poll", [False, True])
@pytest.mark.parametrize("enabled_sensors", [[], list(SensorType)])
async def test_entry_unload_unsubscribes(
    hass: HomeAssistant, poll: bool, enabled_sensors: list
) -> None:
    """Test that nothing keeps listening to the sources after the entry is gone."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            **ADVANCED_USER_INPUT,
            CONF_POLL: poll,
            CONF_SCAN_INTERVAL: 30,
            CONF_ENABLED_SENSORS: enabled_sensors,
        },
        entry_id="test",
        unique_id="uniqueid",
    )
    entry.add_to_hass(hass)
    hass.states.async_set("sensor.test_temperature_sensor", "25")
    hass.states.async_set("sensor.test_humidity_sensor", "50")

    with (
        patch.object(
            DeviceThermalComfort,
            "_new_temperature_state",
            autospec=True,
            side_effect=DeviceThermalComfort._new_temperature_state,
        ) as new_temperature,
        patch.object(
            DeviceThermalComfort,
            "async_update_sensors",
            autospec=True,
            side_effect=DeviceThermalComfort.async_update_sensors,
        ) as update_sensors,
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        assert await hass.config_entries.async_reload(entry.entry_id)
        await hass.async_block_till_done()

        new_temperature.reset_mock()
        update_sensors.reset_mock()
        hass.states.async_set("sensor.test_temperature_sensor", "26")
        await hass.async_block_till_done()
        # one live device after the reload, not two
        assert new_temperature.call_count == 1

        assert await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()

        new_temperature.reset_mock()
        update_sensors.reset_mock()
        hass.states.async_set("sensor.test_temperature_sensor", "27")
        async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=120))
        await hass.async_block_till_done()
        assert new_temperature.call_count == 0
        assert update_sensors.call_count == 0


@pytest.mark.parametrize(*DEFAULT_TEST_SENSORS)
async def test_yaml_entities_removed_unsubscribes(hass, start_ha):
    """Test that the YAML device stops listening when its last entity is removed."""
    with patch.object(
        DeviceThermalComfort,
        "_new_temperature_state",
        autospec=True,
        side_effect=DeviceThermalComfort._new_temperature_state,
    ) as new_temperature:
        remove_platform_entities(hass)
        await hass.async_block_till_done()
        assert get_sensor(hass, SensorType.DEW_POINT) is None

        hass.states.async_set("sensor.test_temperature_sensor", "27")
        await hass.async_block_till_done()
        assert new_temperature.call_count == 0


def test_source_values_are_not_recorded():
    """Test that the frequently changing source attributes are kept out of the database."""
    assert {
        ATTR_TEMPERATURE,
        ATTR_HUMIDITY,
    } <= SensorThermalComfort._unrecorded_attributes


def reference_enthalpy(temperature: float, humidity: float, patm: float) -> float:
    """Moist air enthalpy (ASHRAE 2021) above 0 degrees, independent of the code."""
    t = temperature + 273.15
    p_ws = math.exp(
        -5.8002206e03 / t
        + 1.3914993
        - 4.8640239e-02 * t
        + 4.1764768e-05 * t**2
        - 1.4452093e-08 * t**3
        + 6.5459673 * math.log(t)
    )
    p_w = humidity / 100 * p_ws
    w = 0.621945 * p_w / (patm - p_w)
    return 1.006 * temperature + w * (2501 + 1.86 * temperature)


def enthalpy(hass) -> float:
    """Return the state of the enthalpy sensor."""
    return float(get_sensor(hass, SensorType.MOIST_AIR_ENTHALPY).state)


@pytest.mark.parametrize(*DEFAULT_TEST_SENSORS)
async def test_enthalpy_ignores_elevation(hass, start_ha):
    """Test that without a pressure sensor the standard pressure is used at any elevation."""
    hass.config.elevation = 500
    hass.states.async_set("sensor.test_temperature_sensor", "25.0001")
    await hass.async_block_till_done()
    sensor = get_sensor(hass, SensorType.MOIST_AIR_ENTHALPY)
    assert float(sensor.state) == pytest.approx(reference_enthalpy(25.0001, 50, 101325))
    assert ATTR_PRESSURE not in sensor.attributes


@pytest.mark.parametrize(*PRESSURE_TEST_SENSORS)
async def test_enthalpy_with_pressure_sensor(hass, start_ha):
    """Test that the enthalpy follows the measured pressure, also on the first state."""
    sensor = get_sensor(hass, SensorType.MOIST_AIR_ENTHALPY)
    assert float(sensor.state) == pytest.approx(reference_enthalpy(25, 50, 100000))
    assert sensor.attributes[ATTR_PRESSURE] == 1000.0

    hass.states.async_set(
        "sensor.test_pressure_sensor", "900", {"unit_of_measurement": "hPa"}
    )
    await hass.async_block_till_done()
    sensor = get_sensor(hass, SensorType.MOIST_AIR_ENTHALPY)
    assert float(sensor.state) == pytest.approx(reference_enthalpy(25, 50, 90000))
    assert sensor.attributes[ATTR_PRESSURE] == 900.0

    # a state change that leaves the pressure as it is changes nothing
    hass.states.async_set(
        "sensor.test_pressure_sensor", "900", {"unit_of_measurement": "hPa", "x": 1}
    )
    await hass.async_block_till_done()
    assert get_sensor(hass, SensorType.MOIST_AIR_ENTHALPY).state == sensor.state

    # only the enthalpy shows the pressure
    assert ATTR_PRESSURE not in get_sensor(hass, SensorType.DEW_POINT).attributes


@pytest.mark.parametrize(*PRESSURE_TEST_SENSORS)
@pytest.mark.parametrize(
    "value, unit",
    [
        ("100000", "Pa"),
        ("1000", "hPa"),
        ("1000", "mbar"),
        ("100", "kPa"),
        ("1", "bar"),
        ("100", "cbar"),
        ("29.5300", "inHg"),
        ("750.062", "mmHg"),
    ],
)
async def test_pressure_units(hass, start_ha, value, unit):
    """Test that every pressure unit gives the same result for the same pressure."""
    hass.states.async_set(
        "sensor.test_pressure_sensor", "1100", {"unit_of_measurement": "hPa"}
    )
    await hass.async_block_till_done()
    assert enthalpy(hass) == pytest.approx(reference_enthalpy(25, 50, 110000))

    hass.states.async_set(
        "sensor.test_pressure_sensor", value, {"unit_of_measurement": unit}
    )
    await hass.async_block_till_done()
    assert enthalpy(hass) == pytest.approx(reference_enthalpy(25, 50, 100000), abs=0.01)


@pytest.mark.parametrize(*PRESSURE_TEST_SENSORS)
@pytest.mark.parametrize(
    "value, attributes",
    [
        (STATE_UNAVAILABLE, {}),
        (STATE_UNKNOWN, {}),
        ("not a number", {}),
        ("nan", {}),
        ("0", {"unit_of_measurement": "hPa"}),
        ("299", {"unit_of_measurement": "hPa"}),
        ("1101", {"unit_of_measurement": "hPa"}),
        ("-5", {"unit_of_measurement": "hPa"}),
        ("101325", {"unit_of_measurement": "hPa"}),  # a Pa value with the wrong unit
        ("1000", {"unit_of_measurement": "%"}),  # not a pressure unit
        ("1000", {"unit_of_measurement": "°C"}),
    ],
)
async def test_invalid_pressure_falls_back_to_standard(
    hass, start_ha, value, attributes
):
    """Test that an unusable pressure means 101325 Pa, and nothing becomes unavailable."""
    hass.config.elevation = 500  # must not matter
    hass.states.async_set(
        "sensor.test_pressure_sensor", "950", {"unit_of_measurement": "hPa"}
    )
    await hass.async_block_till_done()
    assert enthalpy(hass) == pytest.approx(reference_enthalpy(25, 50, 95000))

    hass.states.async_set("sensor.test_pressure_sensor", value, attributes)
    await hass.async_block_till_done()
    for sensor_type in DEFAULT_SENSOR_TYPES:
        assert get_sensor(hass, sensor_type).state != STATE_UNAVAILABLE
    # not the stale 950 hPa
    sensor = get_sensor(hass, SensorType.MOIST_AIR_ENTHALPY)
    assert float(sensor.state) == pytest.approx(reference_enthalpy(25, 50, 101325))
    assert sensor.attributes[ATTR_PRESSURE] == 1013.25

    # and it recovers
    hass.states.async_set(
        "sensor.test_pressure_sensor", "950", {"unit_of_measurement": "hPa"}
    )
    await hass.async_block_till_done()
    assert enthalpy(hass) == pytest.approx(reference_enthalpy(25, 50, 95000))


@pytest.mark.parametrize(*PRESSURE_TEST_SENSORS)
async def test_pressure_does_not_gate_availability_or_other_sensors(hass, start_ha):
    """Test that the pressure only touches the enthalpy sensor."""
    others = [t for t in DEFAULT_SENSOR_TYPES if t != SensorType.MOIST_AIR_ENTHALPY]
    before = {t: get_sensor(hass, t).state for t in others}
    hass.states.async_set(
        "sensor.test_pressure_sensor", "800", {"unit_of_measurement": "hPa"}
    )
    await hass.async_block_till_done()
    assert {t: get_sensor(hass, t).state for t in others} == before

    hass.states.async_set("sensor.test_temperature_sensor", STATE_UNAVAILABLE)
    await hass.async_block_till_done()
    assert get_sensor(hass, SensorType.MOIST_AIR_ENTHALPY).state == STATE_UNAVAILABLE
    hass.states.async_set(
        "sensor.test_pressure_sensor", "850", {"unit_of_measurement": "hPa"}
    )
    await hass.async_block_till_done()
    hass.states.async_set("sensor.test_temperature_sensor", "25")
    await hass.async_block_till_done()
    assert enthalpy(hass) == pytest.approx(reference_enthalpy(25, 50, 85000))


@pytest.mark.parametrize(
    "domains, config",
    [
        (
            [(DOMAIN, 1)],
            {
                DOMAIN: {
                    PLATFORM_DOMAIN: {
                        "name": "test_thermal_comfort",
                        "temperature_sensor": "sensor.test_temperature_sensor",
                        "humidity_sensor": "sensor.test_humidity_sensor",
                        "pressure_sensor": "sensor.test_pressure_sensor",
                        "poll": True,
                        "scan_interval": 3600,
                        "unique_id": "unique_thermal_comfort_id",
                    },
                },
            },
        ),
    ],
)
async def test_pressure_with_polling(hass, start_ha):
    """Test that a polling device picks up a new pressure on the next poll only."""
    hass.states.async_set(
        "sensor.test_pressure_sensor", "1000", {"unit_of_measurement": "hPa"}
    )
    await hass.async_block_till_done()
    hass.states.async_set("sensor.test_temperature_sensor", "25")
    hass.states.async_set("sensor.test_humidity_sensor", "50")
    await hass.async_block_till_done()
    assert enthalpy(hass) == pytest.approx(reference_enthalpy(25, 50, 100000))

    hass.states.async_set(
        "sensor.test_pressure_sensor", "900", {"unit_of_measurement": "hPa"}
    )
    await hass.async_block_till_done()
    assert enthalpy(hass) == pytest.approx(reference_enthalpy(25, 50, 100000))

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=3601))
    await hass.async_block_till_done()
    assert enthalpy(hass) == pytest.approx(reference_enthalpy(25, 50, 90000))

    remove_platform_entities(hass)
    await hass.async_block_till_done()


@pytest.mark.parametrize("poll", [False, True])
async def test_entry_with_pressure_sensor(hass: HomeAssistant, poll: bool) -> None:
    """Test a config entry with a pressure sensor, and that unloading stops listening to it."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            **ADVANCED_USER_INPUT,
            CONF_PRESSURE_SENSOR: "sensor.test_pressure_sensor",
            CONF_POLL: poll,
            CONF_SCAN_INTERVAL: 30,
            CONF_ENABLED_SENSORS: list(SensorType),
        },
        entry_id="test",
        unique_id="uniqueid",
    )
    entry.add_to_hass(hass)
    hass.states.async_set("sensor.test_temperature_sensor", "25")
    hass.states.async_set("sensor.test_humidity_sensor", "50")
    hass.states.async_set(
        "sensor.test_pressure_sensor", "950", {"unit_of_measurement": "hPa"}
    )

    with patch.object(
        DeviceThermalComfort,
        "_new_pressure_state",
        autospec=True,
        side_effect=DeviceThermalComfort._new_pressure_state,
    ) as new_pressure:
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        state = hass.states.get("sensor.test_thermal_comfort_moist_air_enthalpy")
        assert float(state.state) == pytest.approx(reference_enthalpy(25, 50, 95000))

        # a reload does not leave a second listener behind
        assert await hass.config_entries.async_reload(entry.entry_id)
        await hass.async_block_till_done()
        new_pressure.reset_mock()
        hass.states.async_set(
            "sensor.test_pressure_sensor", "960", {"unit_of_measurement": "hPa"}
        )
        await hass.async_block_till_done()
        assert new_pressure.call_count == 1

        assert await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()
        new_pressure.reset_mock()
        hass.states.async_set(
            "sensor.test_pressure_sensor", "970", {"unit_of_measurement": "hPa"}
        )
        await hass.async_block_till_done()
        assert new_pressure.call_count == 0


@pytest.mark.parametrize(*PRESSURE_TEST_SENSORS)
async def test_yaml_entities_removed_unsubscribes_pressure(hass, start_ha):
    """Test that the YAML device stops listening to the pressure sensor too."""
    with patch.object(
        DeviceThermalComfort,
        "_new_pressure_state",
        autospec=True,
        side_effect=DeviceThermalComfort._new_pressure_state,
    ) as new_pressure:
        remove_platform_entities(hass)
        await hass.async_block_till_done()
        hass.states.async_set(
            "sensor.test_pressure_sensor", "970", {"unit_of_measurement": "hPa"}
        )
        await hass.async_block_till_done()
        assert new_pressure.call_count == 0


def test_pressure_is_not_recorded():
    """Test that the pressure attribute is kept out of the database."""
    assert ATTR_PRESSURE in SensorThermalComfort._unrecorded_attributes


@pytest.mark.parametrize(*DEFAULT_TEST_SENSORS)
async def test_reload_service(hass, start_ha):
    """Test that the reload service applies the changed YAML configuration."""
    assert (
        get_sensor(hass, SensorType.DEW_POINT).name == "test_thermal_comfort Dew point"
    )
    events = async_capture_events(hass, f"event_{DOMAIN}_reloaded")
    changed = {
        TEMPLATE_DOMAIN: [TEMPERATURE_TEST_SENSOR, HUMIDITY_TEST_SENSOR],
        DOMAIN: {
            PLATFORM_DOMAIN: {
                "name": "renamed",
                "temperature_sensor": "sensor.test_temperature_sensor",
                "humidity_sensor": "sensor.test_humidity_sensor",
                "unique_id": "unique_thermal_comfort_id",
            },
        },
    }

    with patch("homeassistant.config.async_hass_config_yaml", return_value=changed):
        await hass.services.async_call(DOMAIN, SERVICE_RELOAD, blocking=True)
    await hass.async_block_till_done()

    assert len(events) == 1
    sensor = get_sensor(hass, SensorType.DEW_POINT)
    assert sensor.name == "renamed Dew point"
    assert len(hass.states.async_all(PLATFORM_DOMAIN)) == LEN_DEFAULT_SENSORS + 2


async def test_yaml_renames_legacy_unique_ids(hass):
    """Test that YAML sensors take over the entities named before thermal comfort 2.0."""
    registry = er.async_get(hass)
    renamed = {
        LegacySensorType.THERMAL_PERCEPTION: SensorType.DEW_POINT_PERCEPTION,
        LegacySensorType.SIMMER_INDEX: SensorType.SUMMER_SIMMER_INDEX,
        LegacySensorType.SIMMER_ZONE: SensorType.SUMMER_SIMMER_PERCEPTION,
    }
    entity_ids = {
        legacy_type: registry.async_get_or_create(
            PLATFORM_DOMAIN, DOMAIN, id_generator("legacy", legacy_type)
        ).entity_id
        for legacy_type in renamed
    }

    domains, config = DEFAULT_TEST_SENSORS[1][0]
    config = copy.deepcopy(config)
    config[DOMAIN][PLATFORM_DOMAIN]["unique_id"] = "legacy"
    for domain, count in domains:
        with assert_setup_component(count, domain):
            assert await async_setup_component(hass, domain, config)
        await hass.async_block_till_done()

    for legacy_type, sensor_type in renamed.items():
        entry = registry.async_get(entity_ids[legacy_type])
        assert entry.unique_id == id_generator("legacy", sensor_type)
