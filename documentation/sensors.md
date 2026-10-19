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
  <dt><strong>Thoms discomfort Perception</strong> <code>thoms_discomfort_perception</code></dt>
  <dd>
    Indicates the level of discomfort as a result of high temperature and the combined effect with relative humidity.
    It is the discomfort index of Epstein and Moran, the mean of the air temperature and the wet-bulb temperature,
    which is calculated with the formula of Stull (2011).
  </dd>
</dl>

## Input values

The sensors need a valid value from both source sensors:

* The temperature is converted to °C and has to be between -89.2°C and 56.7°C.
* The relative humidity has to be above 0% and at most 100%. Readings up to 105%
  are treated as 100%.
* If a source is `unavailable`, `unknown` or outside these ranges, all sensors of
  the device become `unavailable` until both sources are valid again.

