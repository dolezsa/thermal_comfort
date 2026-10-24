# Initial Configuration
## In your Home Assistant UI go to "Configuration", then click "Devices & Services"

![Config Dashboard](https://raw.githubusercontent.com/dolezsa/thermal_comfort/master/screenshots/config_dashboard.png)

## Make sure Integrations is selected and click the "+" button in the bottom right corner

![Config Integrations](https://raw.githubusercontent.com/dolezsa/thermal_comfort/master/screenshots/config_integrations.png)

## Search for or scroll down to find "Thermal Comfort" and select it

![Config Integrations Search](https://raw.githubusercontent.com/dolezsa/thermal_comfort/master/screenshots/config_integrations_search.png)

## Name your virtual device and select the temperature and humidity sensor you want to use

The name is used as the device name and as the prefix of the names of its sensors, so enter
the name of the room (or the location) to get distinctly named sensors for each of them.

The entity IDs of the sensors are always in English, for example `sensor.living_room_dew_point`,
independent of the language of Home Assistant. Only the names of the sensors are translated.
Existing entities keep their entity ID.

*Note: Additional options are available in the collapsed "Advanced options" section.
Sensors with the correct device class are listed first, but you can also select
sensors without a device class.*

![Config Thermal Comfort](https://raw.githubusercontent.com/dolezsa/thermal_comfort/master/screenshots/config_thermal_comfort.png)

## A virtual device is created to manage your calculated sensors

![Config Virtual Device](https://raw.githubusercontent.com/dolezsa/thermal_comfort/master/screenshots/config_devices_thermal_comfort.png)

# Configuration Options

## Click configure on the configuration to set additional options

The entry reloads when you save changed options.

![Config Virtual Device](https://raw.githubusercontent.com/dolezsa/thermal_comfort/master/screenshots/config_options_thermal_comfort.png)

<dl>
  <dt><strong>Temperature sensor</strong> and <strong>Humidity sensor</strong> <code>entity</code></dt>
  <dd>
    The sensors used for the calculations.
  </dd>
  <dt><strong>Temperature attribute</strong> and <strong>Humidity attribute</strong> <code>text</code> (optional, advanced options)</dt>
  <dd>
    The attribute of the source entity that has the value, instead of its state.
    Weather and climate entities can be chosen as a source without it: their
    attributes <code>temperature</code> and <code>humidity</code> (weather) and
    <code>current_temperature</code> and <code>current_humidity</code> (climate)
    are used. Fill in the field for another entity, or to use another attribute.
    See <a href="https://github.com/dolezsa/thermal_comfort/blob/master/documentation/sensors.md#input-values">input values</a>.
  </dd>
  <dt><strong>Outdoor temperature sensor</strong> and <strong>Outdoor humidity sensor</strong> <code>entity</code> (optional)</dt>
  <dd>
    The sensors of the outdoor air, both are needed. A weather entity can be both, its attributes are used.
    With them the sensors that compare the room with the outdoor air are created and enabled
    (moisture excess, ventilation advice and ventilation need), see
    <a href="https://github.com/dolezsa/thermal_comfort/blob/master/documentation/ventilation.md">ventilation</a>.
    If you remove the sensors the entities stay in the entity registry, they are not provided any more and
    work again when you add the sensors again.
  </dd>
  <dt><strong>Pressure sensor</strong> <code>entity</code> (optional)</dt>
  <dd>
    An atmospheric pressure sensor (device class <code>pressure</code> or
    <code>atmospheric_pressure</code>, any pressure unit). Only the moist air
    enthalpy uses the pressure. Without a sensor, or while its value is
    unavailable or implausible (outside 300 to 1100 hPa), the standard
    pressure of 101325 Pa (1013.25 hPa) is used. With a sensor, the enthalpy
    sensor shows the pressure in use in its <code>pressure</code> attribute.
    Use the station pressure, not a pressure reduced to sea level, otherwise the
    result is off at higher elevations.
  </dd>
</dl>

The following options are in the collapsed "Advanced options" section:

<dl>
  <dt><strong>Enable Polling</strong> <code>boolean</code></dt>
  <dd>
    Enable this if you want the sensors to be polled. This can avoid double
    calculated values if your input sensors split change updates for humidity
    and temperature.
  </dd>
  <dt><strong>Poll interval (seconds)</strong> <code>integer</code></dt>
  <dd>
    If polling is enabled this sets the interval in seconds (default: 30).
  </dd>
  <dt><strong>Use custom icons pack</strong>  <code>boolean</code></dt>
  <dd>
    Enable this if you have the <a href="https://github.com/dolezsa/thermal_comfort/blob/master/README.md#custom-icons">custom icon pack</a>
    installed and want to use it as default icons for the sensors
  </dd>
  <dt><strong>Enabled sensors</strong> <code>list</code> (initial setup only)</dt>
  <dd>
    The sensors that are enabled right after the setup, all are selected by
    default. The other sensors are created as well, but disabled, you can
    enable them later in the entity settings.
  </dd>
</dl>
