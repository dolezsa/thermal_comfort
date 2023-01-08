# YAML Configuration

To use, add according to the following example to your `configuration.yaml` file:

```yaml
thermal_comfort:
  - custom_icons: true  # global option for the entry
    sensor:
    - name: Living Room
      temperature_sensor: sensor.temperature_livingroom
      humidity_sensor: sensor.humidity_livingroom
      custom_icons: false  # override entry option for sensor
    - name: Bathroom
      poll: true
      temperature_sensor: sensor.temperature_bathroom
      humidity_sensor: sensor.humidity_bathroom
      sensor_types:
        - absolute_humidity
        - heat_index
        - dew_point_perception
    - name: Bedroom
…
```
### Sensor Configuration Variables

#### Sensor Options
<dl>
  <dt><strong>sensor_types</strong> <code>list</code> <code>(optional)</code></dt>
  <dd>
    A list of sensors to create. If omitted all will be created.
    <a href="https://github.com/dolezsa/thermal_comfort/blob/2.0.0/documentation/sensors.md">Available sensors</a>
  </dd>
  <dt><strong>poll</strong> <code>boolean</code> <code>(optional, default: false)</code></dt>
  <dd>
    Set to true if you want the sensors to be polled. This can avoid double
    calculated values if your input sensors split change updates for humidity
    and temperature.
  </dd>
  <dt><strong>scan_interval</strong> <code>boolean</code> <code>(optional, default: 30)</code></dt>
  <dd>
    If polling is enabled this sets the interval in seconds.
  </dd>
  <dt><strong>custom_icons</strong> <code>boolean</code> <code>(optional, default: false)</code></dt>
  <dd>Set to true if you have the <a href="https://github.com/dolezsa/thermal_comfort/blob/master/README.md#custom-icons">custom icon pack</a>
    installed and want to use it as default icons for the sensors.
  </dd>
</dl>

#### Sensor Configuration
<dl>
  <dt><strong>name</strong> <code>string</code> <code>(optional)</code></dt>
  <dd>
    Name of the sensor will be used both for the friendly name and entity id
    combined with the sensor type. e.g. Kitchen would get your
    `sensor.kitchen_absolutehumidity` and Kichten Absolute Humidity.</dd>
  <dt><strong>temperature_sensor</strong> <code>string</code> <code>REQUIRED</code></dt>
  <dd>ID of temperature sensor entity to be used for calculations.</dd>
  <dt><strong>humidity_sensor</strong>  <code>string</code> <code>REQUIRED</code></dt>
  <dd>ID of humidity sensor entity to be used for calculations..</dd>
  <dt><strong>icon_template</strong> <code>template</code> <code>(optional)</code></dt>
  <dd>Defines a template for the icon of the sensor.</dd>
  <dt><strong>entity_picture_template</strong> <code>template</code> <code>(optional)</code></dt>
  <dd>Defines a template for the entity picture of the sensor.</dd>
  <dt><strong>unique_id</strong> <code>string</code> <code>REQUIRED</code></dt>
  <dd>
    An ID that uniquely identifies the sensors. Set this to a unique value to
    allow customization through the UI.
    <p> Make sure this is a unique value. Home assistant uses this internally and you
    will not see it in the frontend.
    A good tool to get a unique value is the `uuidgen` command line tool or your can
    use a <a href="https://www.uuidgenerator.net/">online uuid generator</a></p>
    Internally we add the sensor type name to the unique id you set for each sensor.
    e.g. with a unique id of `0ee4d8a7-c610-4afa-855d-0b2c2c265e11` for a absolute humidity
    sensor you would get `0ee4d8a7-c610-4afa-855d-0b2c2c265e11absolute_humidity`.
  </dd>
</dl>
