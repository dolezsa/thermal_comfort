# thermal_comfort
Thermal Comfort sensor for HA (absolute humidity, heat index, dew point, thermal perception)

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
      bedroom:
        ...

```

## Required
- temperature_sensor
- humidity_sensor

## Optional
- friendly_name
- icon_template
- entity_picture_template
