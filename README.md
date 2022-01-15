# [![thermal_comfort](https://raw.githubusercontent.com/dolezsa/thermal_comfort/master/icons/logo.png)](https://github.com/dolezsa/thermal_comfort)
[![hacs_badge](https://img.shields.io/badge/HACS-Default-41BDF5.svg?style=for-the-badge)](https://github.com/hacs/integration)

Thermal Comfort provides the following calculated sensors for Home Assistant:

 * Absolute Humidity `absolutehumidity`
 * Heat Index `heatindex`
 * Dew Point `dewpoint`
 * Thermal Perception `perception`
 * Frost point `frostpoint`
 * Frost Risk `frostrisk`
 * Simmer Index `simmerindex`
 * Simmer Zone `simmerzone`

## Usage

To use, add the following to your `configuration.yaml` file:

```yaml
sensor:
  - platform: thermal_comfort
    poll: true
    scan_interval: 300
    sensors:
      livingroom:
        friendly_name: Living Room
        temperature_sensor: sensor.temperature_livingroom
        humidity_sensor: sensor.humidity_livingroom
      bathroom:
        temperature_sensor: sensor.temperature_bathroom
        humidity_sensor: sensor.humidity_bathroom
        sensor_types:
          - absolutehumidity
          - heatindex
      bedroom:
…
```
### Platform Configuration Variables
<dl>
  <dt><strong>poll</strong> <code>boolean</code> <code>(optional, default: false)</code></dt>
  <dd>Set to true if you want the sensors to be polled. This can avoid double calculated values if your input sensors split change updates for humidity and temperature.</dd>
  <dt><strong>scan_interval</strong> <code>boolean</code> <code>(optional, default: 30)</code></dt>
  <dd>Change the polling interval in seconds if <code>poll</code> is set to true.</dd>
</dl>

### Sensor Configuration Variables
<dl>
  <dt><strong>temperature_sensor</strong> <code>string</code> <code>REQUIRED</code></dt>
  <dd>ID of temperature sensor entity to be used for calculations.</dd>
  <dt><strong>humidity_sensor</strong>  <code>string</code> <code>REQUIRED</code></dt>
  <dd>ID of humidity sensor entity to be used for calculations..</dd>
  <dt><strong>friendly_name</strong> <code>string</code> <code>(optional)</code></dt>
  <dd>Name to use in the frontend.</dd>
  <dt><strong>icon_template</strong> <code>template</code> <code>(optional)</code></dt>
  <dd>Defines a template for the icon of the sensor.</dd>
  <dt><strong>entity_picture_template</strong> <code>template</code> <code>(optional)</code></dt>
  <dd>Defines a template for the entity picture of the sensor.</dd>
  <dt><strong>unique_id</strong> <code>string</code> <code>(optional)</code></dt>
  <dd>An ID that uniquely identifies the sensors. Set this to a unique value to allow customization through the UI.</dd>
  <dt><strong>sensor_types</strong> <code>list</code> <code>(optional)</code></dt>
  <dd>A list of sensors to create. If omitted all will be created. Available sensors: <code>absolutehumidity</code>, <code>heatindex</code>, <code>dewpoint</code>, <code>perception</code>, <code>frostpoint</code>, <code>frostrisk</code>, <code>simmerindex</code>, <code>simmerzone</code></dd>
</dl>

## Installation

### Using [HACS](https://hacs.xyz/) (recommended)

This integration can be installed using HACS. To do it search for Thermal Comfort in the integrations section.

### Manual

To install this integration manually you can either

* Use git:

```sh
git clone https://github.com/dolezsa/thermal_comfort.git
cd thermal_comfort
# if you want a specific version checkout its tag
# e.g. git checkout 1.0.0

# replace $hacs_config_folder with your home assistant config folder path
cp -r custom_components $hacs_config_folder
```

* Download the source release and extract the custom_components folder into your home assistant config folder.

Finally you need to restart home assistant before you can use it.

## Screenshots

#### Absolute Humidity
![Absolute Humidity](https://raw.githubusercontent.com/dolezsa/thermal_comfort/master/screenshots/absolute_humidity.png)

#### Dew Point
![Dew Point](https://raw.githubusercontent.com/dolezsa/thermal_comfort/master/screenshots/dew_point.png)

#### Heat Index
![Heat Index](https://raw.githubusercontent.com/dolezsa/thermal_comfort/master/screenshots/heat_index.png)

#### Thermal Perception
![Thermal Perception](https://raw.githubusercontent.com/dolezsa/thermal_comfort/master/screenshots/perception.png)
