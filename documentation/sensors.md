# Sensors:

All sensors are calculated from one temperature and one relative humidity
sensor. The ventilation sensors also need the optional
[outdoor sensors](https://github.com/dolezsa/thermal_comfort/blob/master/documentation/ventilation.md),
the moist air enthalpy and the humidity ratio can use an optional pressure sensor.
Sensors with a text value (the perceptions, the frost risk, the ventilation
advice and the ventilation need) have fixed English state names, like `comfortable`, which
Home Assistant shows translated. Use the English names in automations and templates.

## Which sensor do I need?

| I want to ... | Use |
| --- | --- |
| know how much water the air holds, independent of the temperature | `dew_point`, `absolute_humidity` |
| compare the water content of two rooms or of the room and the outdoors, per kg of dry air | `humidity_ratio` |
| see how strongly the air dries things (laundry, wood, plants) | `vapor_pressure_deficit` |
| see if windows or walls will get wet | `dew_point` (condensation starts on a surface colder than the dew point) |
| see how hot it feels in warm weather | `humidex`, `heat_index`, `summer_simmer_index`, or their perception sensors, `thoms_discomfort_perception` |
| see if cool, damp weather is uncomfortable | `winter_scharlau_perception` (only between -5 and 6°C and above 40 % humidity, otherwise `outside_calculable_range`; there is no wind chill) |
| know the risk of frost | `frost_risk`, `frost_point` |
| judge heat stress or evaporative cooling | `wet_bulb_temperature` |
| decide if airing dries or humidifies the room | `moisture_excess`, `ventilation_advice` (outdoor sensors needed) |
| check if the ventilation of a dwelling is sufficient | `ventilation_need` (outdoor sensors needed) |
| know the energy content of the air, for example to compare two rooms or the room and the outdoors (one device each) | `moist_air_enthalpy` |

## Humidity and dew

<dl>
  <dt><strong>Absolute Humidity</strong> <code>absolute_humidity</code></dt>
  <dd>
    Absolute humidity is a measure of the actual amount of water vapor
    (moisture) in the air, the mass of the water vapor in one cubic meter of air, in g/m³.
    Unlike the relative humidity it changes only a little when the air is heated or cooled
    (the air expands a bit, and water condenses only below the dew point), so it tells how much water
    there really is in a room. Use it to compare rooms or the room and the outdoors,
    or to follow a dehumidifier. In a dwelling the value is mostly between about 4 and 14 g/m³,
    lowest in the heating season and highest in summer.
    Source: <a href="https://carnotcycle.wordpress.com/2012/08/04/how-to-convert-relative-humidity-to-absolute-humidity/">Carnot Cycle</a>
  </dd>
  <dt><strong>Humidity Ratio</strong> <code>humidity_ratio</code></dt>
  <dd>
    The mass of water vapor in the air in grams per kilogram of <em>dry</em> air (g/kg), also called the mixing ratio,
    the humidity axis of the Mollier chart. It is not the absolute humidity (g/m³, per volume of air) and
    not the specific humidity, which is per kilogram of moist air and about 1 % lower.
    Air that is heated or cooled without gaining or losing water keeps its humidity ratio, so
    values of different rooms or of the room and the outdoors compare directly, and the change
    of the value shows how much water a dehumidifier, a humidifier or the airing moves.
    It depends on the atmospheric pressure (about 1.2 % per 100 m of elevation), from the optional
    pressure sensor, otherwise 101325 Pa is used, see the configuration docs. With a pressure sensor the
    <code>pressure</code> attribute shows the pressure in use.
    The saturation vapor pressure comes from the equation of ASHRAE Fundamentals 2021 (Hyland and Wexler), the ratio from
    the ideal gas relation, which stays within about 0.5 % of the tabulated real gas values. The relative humidity is taken over water also below 0°C, as the
    sensors and the weather services report it.
  </dd>
  <dt><strong>Vapor Pressure Deficit</strong> <code>vapor_pressure_deficit</code></dt>
  <dd>
    How much more water vapor the air could take up, as a pressure in kPa: the saturation vapor pressure minus the vapor pressure
    of the air, <code>VPD = pws × (1 - RH / 100)</code>. A high value means dry air that takes up moisture quickly (laundry
    dries, plants transpire strongly), a low value damp air where things dry slowly.
    Growers use it to judge the climate of a greenhouse or grow tent.
    The attributes are the <code>vapor_pressure</code> and the <code>saturation_vapor_pressure</code> of the air in kPa.<br>
    This is the vapor pressure deficit of the <em>air</em>. The charts of growers are made for the deficit of the leaf, and a leaf is
    usually 1 to 3°C cooler than the air, so their values are roughly 0.15 to 0.5 kPa lower than this sensor at room
    conditions. The leaf deficit needs the temperature of the leaf and is not calculated, and the sensor does not
    give target ranges, they depend on the plant, its stage and on whether they are meant for the leaf or the air.
    The pressure sensor is not used, the deficit is a pressure difference. The relative humidity is taken over water
    also below 0°C.
  </dd>
  <dt><strong>Dew Point + Perception</strong> <code>dew_point</code> <code>dew_point_perception</code></dt>
  <dd>
    The dew point is the temperature to which air must be cooled to become
    saturated with water vapor and dew forms on surfaces, in °C.
    Water condenses on every surface that is colder than the dew point, so it is the
    number to watch for wet windows and cold walls.
    It depends only on the amount of water in the air, not on how warm the air is.
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
    Risk of frost based on current temperature, frost point and absolute humidity.
    The states are <code>no_risk</code>, <code>unlikely</code>, <code>probable</code>
    and <code>high</code>. It is meant for the outdoor air, for example for plants or the windscreen of the car,
    its thresholds (air temperature up to 4°C) are never reached in a heated room.
    It only knows the current values and cannot anticipate an overnight minimum,
    so don't rely on it alone to protect plants or equipment.
  </dd>
</dl>

## Feels-like temperatures and perceptions

These indices describe how a person feels the combination of temperature and humidity.
Most of them are meant for warm weather. The perception sensors translate the number
into text states, for dashboards and automations ("it is uncomfortable").

<dl>
  <dt><strong>Heat Index</strong> <code>heat_index</code></dt>
  <dd>
    The heat index combines air temperature and relative humidity to posit a
    human-perceived equivalent temperature, in °C. It is meant for warm weather
    (the National Weather Service uses it from 27°C, 80°F), at lower temperatures the value roughly follows the air temperature.
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
    It is a Canadian index for warm weather, the perception ranges from <code>comfortable</code> to <code>heat_stroke</code>.
    Source: <a href="https://simple.wikipedia.org/wiki/Humidex#Humidex_formula">Wikipedia</a>
  </dd>
  <dt><strong>Summer Simmer Index + Perception</strong> <code>summer_simmer_index</code> <code>summer_simmer_perception</code></dt>
  <dd>
    Provides an indicator of heat stress concerns and discomfort using equivalent temperature values for general public acceptance and awareness.
    It is meant for warm weather, the perception ranges from <code>cool</code> to <code>circulatory_collapse_imminent</code>.
    Below 14.4°C (58°F) the index is the air temperature.
    Sources: <a href="https://www.vcalc.com/wiki/rklarsen/Summer+Simmer+Index">index</a>,
    <a href="http://summersimmer.com/default.asp">perception</a>.
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
  <dt><strong>Relative Strain Perception</strong> <code>relative_strain_perception</code></dt>
  <dd>
    A measure of discomfort resulting from the combined effect of temperature and humidity. It assumes a person dressed in a light business suit, walking at a moderate pace in a very light air motion. It is applicable to assess heat stress of manual workers under shelter at various metabolic rates. Valid for temperatures between 26 and 35°C (79 to 95°F).
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
</dl>

## Heat stress and energy

<dl>
  <dt><strong>Wet-Bulb Temperature</strong> <code>wet_bulb_temperature</code></dt>
  <dd>
    The lowest temperature the air can reach by evaporative cooling, in °C. It tells how well sweating or an
    evaporative cooler works: the closer it is to the air temperature, the less they cool. A wet-bulb
    temperature above about 30°C is dangerous even at rest, 35°C is considered the limit of survival.
    It is calculated with the
    approximation of <a href="https://doi.org/10.1175/JAMC-D-11-0143.1">Stull (2011)</a>,
    which is valid for 5 to 99 % relative humidity and -20 to 50°C (-4 to 122°F) with an error of
    about 0.3°C on average, and assumes the pressure at sea level. The pressure sensor is not used.
    Outside the valid range the formula can give a value above the air temperature or below the
    dew point, the sensor limits the value to that range, but the accuracy is lower there.
  </dd>
  <dt><strong>Moist Air Enthalpy</strong> <code>moist_air_enthalpy</code></dt>
  <dd>
    The enthalpy of moist air is the sum of the enthalpy of the dry air and the enthalpy of the water vapour. Enthalpy is the total energy of a thermodynamic system.
    It is shown in kJ/kg of dry air and includes the heat of the water vapor, so humid air has more
    energy than dry air of the same temperature. With a second device for the outdoor air, compare the two
    values to see if airing or a ventilation unit brings heat in or takes it out, or use it for cooling calculations.
    It depends on the atmospheric pressure, from the optional pressure sensor, otherwise the standard pressure of 101325 Pa is used, see the configuration docs.
    Below 0°C the saturation vapor pressure is taken over ice, unlike in the humidity ratio, which uses water at all temperatures.
  </dd>
</dl>

## Ventilation

These sensors compare the room with the outdoor air, they need the
[outdoor sensors](https://github.com/dolezsa/thermal_comfort/blob/master/documentation/ventilation.md).

<dl>
  <dt><strong>Moisture Excess</strong> <code>moisture_excess</code></dt>
  <dd>
    The absolute humidity of the room minus the absolute humidity of the outdoor air, in g/m³.
    A positive value means that airing makes the room drier, a negative value that it makes it more humid.
    The attributes are the outdoor temperature (<code>outdoor_temperature</code>, in °C also if the source is in another unit),
    the outdoor humidity, the absolute humidity (g/m³) and the dew point (<code>outdoor_dew_point</code>, in °C) of the outdoor air,
    and <code>ventilated_relative_humidity</code>, the relative humidity the room would have right
    after the air is exchanged completely, as the outdoor air keeps its vapor pressure when it is warmed to the temperature
    of the room (capped at 100 %).
    It needs the <a href="https://github.com/dolezsa/thermal_comfort/blob/master/documentation/ventilation.md">outdoor temperature and humidity sensors</a>.
    The relative humidity is taken over water also below 0°C, as the sensors and the weather services report it.
  </dd>
  <dt><strong>Ventilation Advice</strong> <code>ventilation_advice</code></dt>
  <dd>
    What airing would do to the humidity of the room:
    <code>drier_outside</code> (the moisture excess is above 1 g/m³), <code>similar</code> (between -1 and 1 g/m³),
    <code>more_humid_outside</code> (below -1 g/m³) and <code>condensation_risk</code>.
    The last one is shown, before the others, if the outdoor air would have a relative humidity of 80 % or more
    after it is warmed to the temperature of the room (<code>ventilated_relative_humidity</code>): it is near saturation on
    the cooler surfaces of the room, like a cellar in summer. 80 % is the surface humidity of the criterion of EN ISO 13788 for mould.<br>
    The sensor knows nothing about earlier values, the states are bands. The band of 1 g/m³ is about the uncertainty
    of two simple sensors (two sensors of ±3 % relative humidity add up to about ±1 g/m³ at 21°C), so the state
    changes back and forth in spring and autumn. Use it in automations with the outer states and a duration, see the
    <a href="https://github.com/dolezsa/thermal_comfort/blob/master/documentation/ventilation.md">recipes</a>.
    It answers one question, what happens to the humidity of the room. It does not say if airing is worth the heat
    it loses, if it cools the room, or if the air is fresh (the carbon dioxide is another thing).
  </dd>
  <dt><strong>Ventilation Need</strong> <code>ventilation_need</code></dt>
  <dd>
    Compares the moisture excess to the limit of the Swedish Public Health Agency:
    <a href="https://www.folkhalsomyndigheten.se/contentassets/641784832543443ea4eebe9b300c244e/fohmfs-2014-18.pdf">FoHMFS 2014:18</a>
    says that in dwellings the difference of the absolute humidity between outdoors and indoors under winter conditions
    should not regularly exceed 3 g/m³, an indication that the ventilation is not satisfactory
    (<a href="https://www.folkhalsomyndigheten.se/contentassets/26ea6c0d999742c0a5351c63e70cb0ce/fohmfs-2014-14.pdf">FoHMFS 2014:14</a>
    uses it as one of the reasons for an investigation of a building). The states are <code>above_limit</code> (the moisture excess is
    above 3 g/m³ and the outdoor temperature is below 10°C), <code>within_limit</code> and <code>not_winter</code> (the outdoor temperature
    is 10°C or more). The advice does not define winter, 10°C is the choice of this integration.<br>
    The sensor shows the moment, the rule is about the usual values: the Swedish surveys use the mean of about two weeks of the
    winter half-year. A shower or cooking brings the sensor above the limit for a while. Look at the mean of the
    moisture excess, or at the share of the time above the limit, as in the
    <a href="https://github.com/dolezsa/thermal_comfort/blob/master/documentation/ventilation.md">recipes</a>.
    It is not the limit of the advice for opening a window, it says that the ventilation is not enough, not when to air.
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

