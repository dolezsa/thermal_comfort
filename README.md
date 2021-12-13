# ![thermal_comfort](./icons/logo.png)
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
![Absolute Humidity](https://user-images.githubusercontent.com/37278442/55691083-8d2ec900-599a-11e9-9b5b-867fc4551092.png)

#### Dew Point
![Dew Point](https://user-images.githubusercontent.com/37278442/55691084-8dc75f80-599a-11e9-9cad-001ea9bb16fd.png)

#### Heat Index
![Heat Index](https://user-images.githubusercontent.com/37278442/55691085-8dc75f80-599a-11e9-9baf-8e003d09bf0c.png)

#### Thermal Perception
![Thermal Perception](https://user-images.githubusercontent.com/37278442/55691086-8dc75f80-599a-11e9-89f0-fb88e79f722f.png)
