# Legacy YAML Configuration

*This way of configuring Thermal Comfort is deprecated and will be unsupported in
the future. Please migrate to either configuration in the frontend with
[config flow](./config_flow.md) or the [new yaml](./yaml.md) configuration.*

To use, add the following to your `configuration.yaml` file:

```yaml
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
