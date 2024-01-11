"""The test for the Thermal Comfort sensor platform."""

from collections.abc import Callable
import logging

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.thermal_comfort.const import DOMAIN
from custom_components.thermal_comfort.sensor import (
    ATTR_FROST_POINT,
    ATTR_HUMIDITY,
    ATTR_RELATIVE_STRAIN_INDEX,
    ATTR_SUMMER_SCHARLAU_INDEX,
    ATTR_THOMS_DISCOMFORT_INDEX,
    ATTR_WINTER_SCHARLAU_INDEX,
    CONF_CUSTOM_ICONS,
    CONF_SENSOR_TYPES,
    DEFAULT_SENSOR_TYPES,
    DewPointPerception,
    FrostRisk,
    HumidexPerception,
    RelativeStrainPerception,
    ScharlauPerception,
    SensorType,
    SummerSimmerPerception,
    ThomsDiscomfortPerception,
    id_generator,
)
from homeassistant.components.command_line.const import DOMAIN as COMMAND_LINE_DOMAIN
from homeassistant.components.sensor import DOMAIN as PLATFORM_DOMAIN
from homeassistant.const import ATTR_TEMPERATURE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .const import ADVANCED_USER_INPUT

_LOGGER = logging.getLogger(__name__)

TEST_NAME = "sensor.test_thermal_comfort"

TEMPERATURE_TEST_SENSOR = {
    PLATFORM_DOMAIN: {
        "command": "echo 0",
        "name": "test_temperature_sensor",
        "value_template": "{{ 25.0 | float }}",
    },
}

HUMIDITY_TEST_SENSOR = {
    PLATFORM_DOMAIN: {
        "command": "echo 0",
        "name": "test_humidity_sensor",
        "value_template": "{{ 50.0 | float }}",
    },
}

DEFAULT_TEST_SENSORS = [
    "domains, config",
    [
        (
            [(COMMAND_LINE_DOMAIN, 2), (DOMAIN, 1)],
            {
                COMMAND_LINE_DOMAIN: [
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
    """Test if absolute humidity is calculted correctly."""
    assert get_sensor(hass, SensorType.ABSOLUTE_HUMIDITY) is not None
    assert get_sensor(hass, SensorType.ABSOLUTE_HUMIDITY).state == "11.5128065738593"

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
        == 25.21
    )
    assert (
        get_sensor(hass, SensorType.WINTER_SCHARLAU_PERCEPTION).state
        == ScharlauPerception.OUTSIDE_CALCULABLE_RANGE
    )

    hass.states.async_set("sensor.test_temperature_sensor", "3.54")
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

    hass.states.async_set("sensor.test_temperature_sensor", "3.53")
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

    hass.states.async_set("sensor.test_temperature_sensor", "-0.06")
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
        == ScharlauPerception.MODERATELY_UNCOMFORTABLE
    )

    hass.states.async_set("sensor.test_temperature_sensor", "-0.07")
    hass.states.async_set("sensor.test_humidity_sensor", "71.00")
    await hass.async_block_till_done()
    assert (
        get_sensor(hass, SensorType.WINTER_SCHARLAU_PERCEPTION).attributes[
            ATTR_WINTER_SCHARLAU_INDEX
        ]
        == -3.01
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
        == 20.94
    )
    assert (
        get_sensor(hass, SensorType.THOMS_DISCOMFORT_PERCEPTION).state
        == ThomsDiscomfortPerception.NO_DISCOMFORT
    )

    hass.states.async_set("sensor.test_temperature_sensor", "25.06")
    hass.states.async_set("sensor.test_humidity_sensor", "50.05")
    await hass.async_block_till_done()
    assert (
        get_sensor(hass, SensorType.THOMS_DISCOMFORT_PERCEPTION).attributes[
            ATTR_THOMS_DISCOMFORT_INDEX
        ]
        == 21
    )
    assert (
        get_sensor(hass, SensorType.THOMS_DISCOMFORT_PERCEPTION).state
        == ThomsDiscomfortPerception.LESS_THAN_HALF
    )

    hass.states.async_set("sensor.test_temperature_sensor", "27.50")
    hass.states.async_set("sensor.test_humidity_sensor", "63.80")
    await hass.async_block_till_done()
    assert (
        get_sensor(hass, SensorType.THOMS_DISCOMFORT_PERCEPTION).attributes[
            ATTR_THOMS_DISCOMFORT_INDEX
        ]
        == 24
    )
    assert (
        get_sensor(hass, SensorType.THOMS_DISCOMFORT_PERCEPTION).state
        == ThomsDiscomfortPerception.MORE_THAN_HALF
    )

    hass.states.async_set("sensor.test_temperature_sensor", "30.70")
    hass.states.async_set("sensor.test_humidity_sensor", "62.70")
    await hass.async_block_till_done()
    assert (
        get_sensor(hass, SensorType.THOMS_DISCOMFORT_PERCEPTION).attributes[
            ATTR_THOMS_DISCOMFORT_INDEX
        ]
        == 27
    )
    assert (
        get_sensor(hass, SensorType.THOMS_DISCOMFORT_PERCEPTION).state
        == ThomsDiscomfortPerception.MOST
    )

    hass.states.async_set("sensor.test_temperature_sensor", "32.30")
    hass.states.async_set("sensor.test_humidity_sensor", "71.50")
    await hass.async_block_till_done()
    assert (
        get_sensor(hass, SensorType.THOMS_DISCOMFORT_PERCEPTION).attributes[
            ATTR_THOMS_DISCOMFORT_INDEX
        ]
        == 29
    )
    assert (
        get_sensor(hass, SensorType.THOMS_DISCOMFORT_PERCEPTION).state
        == ThomsDiscomfortPerception.EVERYONE
    )

    hass.states.async_set("sensor.test_temperature_sensor", "35.20")
    hass.states.async_set("sensor.test_humidity_sensor", "75.10")
    await hass.async_block_till_done()
    assert (
        get_sensor(hass, SensorType.THOMS_DISCOMFORT_PERCEPTION).attributes[
            ATTR_THOMS_DISCOMFORT_INDEX
        ]
        == 32
    )
    assert (
        get_sensor(hass, SensorType.THOMS_DISCOMFORT_PERCEPTION).state
        == ThomsDiscomfortPerception.DANGEROUS
    )


@pytest.mark.parametrize(
    "domains, config",
    [
        (
            [(COMMAND_LINE_DOMAIN, 2), (DOMAIN, 1)],
            {
                COMMAND_LINE_DOMAIN: [
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
            [(COMMAND_LINE_DOMAIN, 2), (DOMAIN, 1)],
            {
                COMMAND_LINE_DOMAIN: [
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
            [(COMMAND_LINE_DOMAIN, 2), (DOMAIN, 1)],
            {
                COMMAND_LINE_DOMAIN: [
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
async def get_sensor_types(hass, start_ha):
    """Test if configure sensor_types only creates the sensors specified."""
    assert len(hass.states.async_all(PLATFORM_DOMAIN)) == 4

    assert get_sensor(hass, SensorType.HEAT_INDEX) is None
    assert get_sensor(hass, SensorType.DEW_POINT_PERCEPTION) is None

    assert get_sensor(hass, SensorType.ABSOLUTE_HUMIDITY) is not None
    assert get_sensor(hass, SensorType.DEW_POINT) is not None


@pytest.mark.parametrize(
    "domains, config",
    [
        (
            [(COMMAND_LINE_DOMAIN, 2), (DOMAIN, 1)],
            {
                COMMAND_LINE_DOMAIN: [
                    {
                        PLATFORM_DOMAIN: {
                            "command": "echo 0",
                            "name": "test_temperature_sensor",
                            "value_template": "{{ NaN | float }}",
                        },
                    },
                    {
                        PLATFORM_DOMAIN: {
                            "command": "echo 0",
                            "name": "test_humidity_sensor",
                            "value_template": "{{ NaN | float }}",
                        },
                    },
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
)
async def get_sensor_is_nan(hass, start_ha):
    """Test if we correctly handle input sensors with NaN as state value."""
    assert len(hass.states.async_all(PLATFORM_DOMAIN)) == LEN_DEFAULT_SENSORS + 2
    for sensor_type in DEFAULT_SENSOR_TYPES:
        assert ATTR_TEMPERATURE not in get_sensor(hass, sensor_type).attributes
        assert ATTR_HUMIDITY not in get_sensor(hass, sensor_type).attributes


@pytest.mark.parametrize(
    "domains, config",
    [
        (
            [(COMMAND_LINE_DOMAIN, 2), (DOMAIN, 1)],
            {
                COMMAND_LINE_DOMAIN: [
                    {
                        PLATFORM_DOMAIN: {
                            "command": "echo 0",
                            "name": "test_temperature_sensor",
                            "value_template": "{{ NaN | float }}",
                        }
                    },
                    {
                        PLATFORM_DOMAIN: {
                            "command": "echo 0",
                            "name": "test_humidity_sensor",
                            "value_template": "{{ NaN | float }}",
                        }
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
async def get_sensor_unknown(hass, start_ha):
    """Test handling input sensors with unknown state."""
    assert len(hass.states.async_all(PLATFORM_DOMAIN)) == LEN_DEFAULT_SENSORS + 2
    for sensor_type in DEFAULT_SENSOR_TYPES:
        assert ATTR_TEMPERATURE not in get_sensor(hass, sensor_type).attributes
        assert ATTR_HUMIDITY not in get_sensor(hass, sensor_type).attributes


@pytest.mark.parametrize(*DEFAULT_TEST_SENSORS)
async def get_sensor_unavailable(hass, start_ha):
    """Test handling unavailable sensors."""
    assert len(hass.states.async_all(PLATFORM_DOMAIN)) == LEN_DEFAULT_SENSORS + 2
    hass.states.async_remove("sensor.test_temperature_sensor")
    hass.states.async_remove("sensor.test_humidity_sensor")
    await hass.async_block_till_done()
    assert len(hass.states.async_all(PLATFORM_DOMAIN)) == LEN_DEFAULT_SENSORS
    for sensor_type in DEFAULT_SENSOR_TYPES:
        assert ATTR_TEMPERATURE in get_sensor(hass, sensor_type).attributes
        assert ATTR_HUMIDITY in get_sensor(hass, sensor_type).attributes
        assert get_sensor(hass, sensor_type).attributes[ATTR_TEMPERATURE] == 25.0
        assert get_sensor(hass, sensor_type).attributes[ATTR_HUMIDITY] == 50.0


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
