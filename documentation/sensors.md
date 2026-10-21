# Sensors:

All sensors are calculated from one temperature and one relative humidity
sensor.

<dl>
  <dt><strong>Absolute Humidity</strong> <code>absolute_humidity</code></dt>
  <dd>
    Absolute humidity is a measure of the actual amount of water vapor
      (moisture) in the air.
    Source: <a href="https://carnotcycle.wordpress.com/2012/08/04/how-to-convert-relative-humidity-to-absolute-humidity/">Carnot Cycle</a>
  </dd>
  <dt><strong>Heat Index</strong> <code>heat_index</code></dt>
  <dd>
    The heat index combines air temperature and relative humidity to posit a
    human-perceived equivalent temperature.
    The calculation follows the <a href="http://www.wpc.ncep.noaa.gov/html/heatindex_equation.shtml">NWS procedure</a>:
    a simple formula is used first and the full regression only applies once
    that result exceeds 26.1°C (79°F), so the value can show a small step at
    that point. Above 85 % relative humidity a further humidity adjustment
    applies between 26.7°C and 30.6°C (80°F and 87°F), which makes the value
    jump again at 26.7°C.
  </dd>
  <dt><strong>Humidex + Perception</strong> <code>humidex</code> <code>humidex_perception</code></dt>
  <dd>
    The humidex (humidity index) describes how hot the weather feels to an average person as a result of the combined effect of heat and humidity. It is calculated from the dew point.
    Source: <a href="https://simple.wikipedia.org/wiki/Humidex#Humidex_formula">Wikipedia</a>
  </dd>
  <dt><strong>Dew Point + Perception</strong> <code>dew_point</code> <code>dew_point_perception</code></dt>
  <dd>
    The dew point is the temperature to which air must be cooled to become
    saturated with water vapor and dew forms on surfaces.
    Sources: <a href="http://wahiduddin.net/calc/density_algorithms.htm">calculation</a>,
    <a href="https://en.wikipedia.org/wiki/Dew_point">perception levels</a>.
    The perception follows a general, mainly outdoor scale, it is not tuned for
    indoor comfort targets. Use the numeric dew point or the absolute humidity
    for indoor humidity automations.
  </dd>
  <dt><strong>Frost Point</strong> <code>frost_point</code></dt>
  <dd>
    Frost point, temperature, below 0° C (32° F), at which moisture in the air 
    will condense as a layer of frost on any exposed surface.
    Source: <a href="https://pon.fr/dzvents-alerte-givre-et-calcul-humidite-absolue/">pon.fr</a>
  </dd>
  <dt><strong>Frost Risk</strong> <code>frost_risk</code></dt>
  <dd>
    Risk of Frost based on current temperature, frost point and absolute humidity.
    It only knows the current values and cannot anticipate an overnight minimum,
    so don't rely on it alone to protect plants or equipment.
  </dd>
  <dt><strong>Relative Strain Perception</strong> <code>relative_strain_perception</code></dt>
  <dd>
    A measure of discomfort resulting from the combined effect of temperature and humidity. It assumes a person dressed in a light business suit, walking at a moderate pace in a very light air motion. It is applicable to assess heat stress of manual workers under shelter at various metabolic rates. Valid for temperatures between 26 and 35°C (79 to 95°F).
  </dd>
  <dt><strong>Summer Simmer Index + Perception</strong> <code>summer_simmer_index</code> <code>summer_simmer_perception</code></dt>
  <dd>
    Provides a proven indicator of heat stress concerns and discomfort using meaningful equivalent temperature values for general public acceptance and awareness.
    Sources: <a href="https://www.vcalc.com/wiki/rklarsen/Summer+Simmer+Index">index</a>,
    <a href="http://summersimmer.com/default.asp">perception</a>.
  </dd>
  <dt><strong>Moist Air Enthalpy</strong> <code>moist_air_enthalpy</code></dt>
  <dd>
    The enthalpy of moist air is the sum of the enthalpy of the dry air and the enthalpy of the water vapour. Enthalpy is the total energy of a thermodynamic system.
    It depends on the atmospheric pressure, from the optional pressure sensor, otherwise the standard pressure of 101325 Pa is used, see the configuration docs.
  </dd>
  <dt><strong>Summer Scharlau Perception</strong> <code>summer_scharlau_perception</code></dt>
  <dd>
    The summer Scharlau index describes a bioclimatic thermal comfort when temperature values are higher than 0°C. Valid for temperatures 17° to 39°C (63° to 102°F) and humidity >= 30%.
    Source: <a href="https://revistadechimie.ro/pdf/16%20RUSANESCU%204%2019.pdf">Rusanescu et al.</a>
  </dd>
  <dt><strong>Winter Scharlau Perception</strong> <code>winter_scharlau_perception</code></dt>
  <dd>
    Reflects the level of human discomfort caused by cooling. Valid for: temperatures -5 to +6°C (23 to 43°F) and humidity >= 40%.
    Source: <a href="https://revistadechimie.ro/pdf/16%20RUSANESCU%204%2019.pdf">Rusanescu et al.</a>
  </dd>
  <dt><strong>Wet-Bulb Temperature</strong> <code>wet_bulb_temperature</code></dt>
  <dd>
    The lowest temperature the air can reach by evaporative cooling. It is calculated with the
    approximation of <a href="https://doi.org/10.1175/JAMC-D-11-0143.1">Stull (2011)</a>,
    which is valid for 5 to 99 % relative humidity and -20 to 50°C (-4 to 122°F) with an error of
    about 0.3°C on average, and assumes the pressure at sea level. The pressure sensor is not used.
    Outside the valid range the formula can give a value above the air temperature or below the
    dew point, the sensor limits the value to that range, but the accuracy is lower there.
  </dd>
  <dt><strong>Thoms discomfort Index + Perception</strong> <code>thoms_discomfort_index</code> <code>thoms_discomfort_perception</code></dt>
  <dd>
    Thom's discomfort index shows the discomfort as a result of high temperature and the combined effect with
    relative humidity. The index is calculated with the relative humidity form
    <code>DI = T - 0.55 (1 - 0.01 RH) (T - 14.5)</code>, with the temperature in °C and the relative humidity in %.
    The perception uses the categories that belong to this form
    (<a href="https://thermofeel.readthedocs.io/en/2.3.0/guide/discomfortindex/">Giles et al., 1990</a>,
    <a href="https://doi.org/10.2486/indhealth.44.388">Epstein and Moran, 2006</a>):
    below 21 no discomfort, 21 to 24 less than half of the population feels discomfort, 24 to 27 more than half,
    27 to 29 most, 29 to 32 everyone, 32 and above a state of medical emergency.
    The categories are meant for warm weather, the index has no meaning in the cold,
    where the term <code>T - 14.5</code> changes its sign.<br>
    The index sensor has the attribute <code>epstein_moran_discomfort_index</code> with the
    form of Epstein and Moran, the mean of the air temperature and the wet-bulb temperature,
    <code>DI = 0.5 Tw + 0.5 T</code>. It gives other values, in dry air up to several °C, and has its own
    categories (below 22 no heat stress, 22 to 24 mild, 24 to 28 moderate, above 28 severe),
    which this integration does not use.
    The perception sensor shows the value of the index in the attribute <code>thoms_discomfort_index</code>.
    The index has no device class, it is shown in °C, also if the system uses °F.
  </dd>
</dl>

## Diagnostic sensors

The sensors with a temperature device class (dew point, frost point, heat index, humidex,
summer simmer index and wet-bulb temperature) have the `diagnostic` entity category.
Home Assistant does not use diagnostic entities for the temperature of an area, for area
targeted temperature triggers and conditions and, by default, for voice assistants, so these derived
values do not mix with the measured air temperature. The sensors are listed in the diagnostic
section of the device. Dashboards, automations and templates can use them as before.

## Input values

The sensors need a valid value from both source sensors:

* The temperature is converted to °C and has to be between -89.2°C and 56.7°C.
* The relative humidity has to be above 0% and at most 100%. Readings up to 105%
  are treated as 100%.
* If a source is `unavailable`, `unknown` or outside these ranges, all sensors of
  the device become `unavailable` until both sources are valid again.

### Values in attributes

The value of a source can be in an attribute of its entity instead of its state:

* The attributes of a weather entity (`temperature`, `humidity`) and of a climate
  entity (`current_temperature`, `current_humidity`) are used automatically. Their
  state is never a number (the condition of the weather, the mode of the thermostat).
* For another entity, or another attribute, set the temperature or humidity attribute
  in the [advanced options](https://github.com/dolezsa/thermal_comfort/blob/master/documentation/config_flow.md)
  or in [YAML](https://github.com/dolezsa/thermal_comfort/blob/master/documentation/yaml.md).
* The temperature in an attribute uses the unit in the `temperature_unit` attribute (weather
  entities have it), otherwise the unit of the state, if that is a temperature unit,
  otherwise the unit system of Home Assistant (climate entities use it).
* The ranges above apply to the attributes too. The attribute must be a number, a text with a
  number is accepted. The state of the entity does not matter, except that
  an `unavailable` entity has no attributes.
* A weather entity can be the source of both values. Its values are rounded (the temperature
  to the precision of the entity, the humidity to whole percents), and are weather data of a
  provider, not measured at your home, so the sensors are less accurate than with your own
  sensors.

