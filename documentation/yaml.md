# YAML Configuration

To use, add the following to your `configuration.yaml` file:

```yaml
thermal_comfort:
  - sensor:
    - name: Living Room
      temperature_sensor: sensor.temperature_livingroom
      humidity_sensor: sensor.humidity_livingroom
    - name: Bathroom
      polling: true
      custom_icons: true
      temperature_sensor: sensor.temperature_bathroom
      humidity_sensor: sensor.humidity_bathroom
      sensor_types:
        - absolutehumidity
        - heatindex
    - name: Bedroom
…
```
### Sensor Configuration Variables
<dl>
  <dt><strong>temperature_sensor</strong> <code>string</code> <code>REQUIRED</code></dt>
  <dd>ID of temperature sensor entity to be used for calculations.</dd>
  <dt><strong>humidity_sensor</strong>  <code>string</code> <code>REQUIRED</code></dt>
  <dd>ID of humidity sensor entity to be used for calculations..</dd>
  <dt><strong>icon_template</strong> <code>template</code> <code>(optional)</code></dt>
  <dd>Defines a template for the icon of the sensor.</dd>
  <dt><strong>entity_picture_template</strong> <code>template</code> <code>(optional)</code></dt>
  <dd>Defines a template for the entity picture of the sensor.</dd>
  <dt><strong>unique_id</strong> <code>string</code> <code>(optional)</code></dt>
  <dd>
    An ID that uniquely identifies the sensors. Set this to a unique value to 
    allow customization through the UI.
  </dd>
  <dt><strong>sensor_types</strong> <code>list</code> <code>(optional)</code></dt>
  <dd>
    A list of sensors to create. If omitted all will be created.
    Available sensors: <code>absolute_humidity</code>,
    <code>heat_index</code>, <code>dew_point</code>,
    <code>thermal_perception</code>, <code>frost_point</code>,
    <code>frost_risk</code>, <code>simmer_index</code>,
    <code>simmer_zone</code>
  </dd>
  <dt><strong>poll</strong> <code>boolean</code> <code>(optional, default: false)</code></dt>
  <dd>
    Set to true if you want the sensors to be polled. This can avoid double
    calculated values if your input sensors split change updates for humidity
    and temperature.
  </dd>
  <dt><strong>custom_icons</strong> <code>boolean</code> <code>(optional, default: false)</code></dt>
  <dd>Set to true if you have the <a href="../README.md#custom-icons">custom icon pack</a>
    installed and want to use it as default icons for the sensors.
  </dd>
</dl>
