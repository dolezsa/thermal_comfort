# [![thermal_comfort](https://raw.githubusercontent.com/dolezsa/thermal_comfort/master/icons/logo.png)](https://github.com/dolezsa/thermal_comfort)
Thermal Comfort sensor for HA (absolute humidity, heat index, dew point, thermal perception)

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)

## Usage

To use, add the following to your `configuration.yaml` file:

```
sensor:
  - platform: thermal_comfort
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
        ...

```

#### Required
- temperature_sensor
- humidity_sensor

#### Optional
- friendly_name
- icon_template
- entity_picture_template
- unique_id
- sensor_types

`sensor_types` is a list of sensors that must be created.
It can be any of: "absolutehumidity", "heatindex", "dewpoint", "perception".
If not provided, all sensors will be created.

## Screenshots

#### Absolute Humidity
![Absolute Humidity](https://raw.githubusercontent.com/dolezsa/thermal_comfort/master/screenshots/absolute_humidity.png)

#### Dew Point
![Dew Point](https://raw.githubusercontent.com/dolezsa/thermal_comfort/master/screenshots/dew_point.png)

#### Heat Index
![Heat Index](https://raw.githubusercontent.com/dolezsa/thermal_comfort/master/screenshots/heat_index.png)

#### Thermal Perception
![Thermal Perception](https://raw.githubusercontent.com/dolezsa/thermal_comfort/master/screenshots/perception.png)
