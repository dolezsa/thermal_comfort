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
      unique_id: 2f842c63-051a-4c49-9da2-4f04ee677514
    - name: Bathroom
      poll: true
      temperature_sensor: sensor.temperature_bathroom
      humidity_sensor: sensor.humidity_bathroom
      sensor_types:
        - absolute_humidity
        - heat_index
        - dew_point_perception
      unique_id: 11adccb5-5029-4d26-bbec-c1b45910c27c
    - name: Bedroom
…
```
### Sensor Configuration Variables

#### Sensor Options
<dl>
  <dt><strong>sensor_types</strong> <code>list</code> <code>(optional)</code></dt>
  <dd>
    A list of sensors to create. If omitted all will be created.
    <a href="https://github.com/dolezsa/thermal_comfort/blob/master/documentation/sensors.md">Available sensors</a>
  </dd>
  <dt><strong>poll</strong> <code>boolean</code> <code>(optional, default: false)</code></dt>
  <dd>
    Set to true if you want the sensors to be polled. This can avoid double
    calculated values if your input sensors split change updates for humidity
    and temperature.
  </dd>
  <dt><strong>scan_interval</strong> <code>time period</code> <code>(optional, default: 30 seconds)</code></dt>
  <dd>
    If polling is enabled this sets the interval, as a number of seconds
    (e.g. <code>60</code>) or as a time (e.g. <code>00:01:00</code>).
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
    `sensor.kitchen_absolute_humidity` and Kitchen Absolute humidity.</dd>
  <dt><strong>temperature_sensor</strong> <code>string</code> <code>REQUIRED</code></dt>
  <dd>ID of temperature sensor entity to be used for calculations.</dd>
  <dt><strong>humidity_sensor</strong>  <code>string</code> <code>REQUIRED</code></dt>
  <dd>ID of humidity sensor entity to be used for calculations.</dd>
  <dt><strong>temperature_attribute</strong> and <strong>humidity_attribute</strong> <code>string</code> <code>(optional)</code></dt>
  <dd>
    Name of the attribute of the source entity that has the value, instead of its state.
    Weather entities (<code>temperature</code>, <code>humidity</code>) and climate entities
    (<code>current_temperature</code>, <code>current_humidity</code>) do not need it, the
    attributes are used for them. Use it for another entity, or to use another attribute of one of
    them. See <a href="https://github.com/dolezsa/thermal_comfort/blob/master/documentation/sensors.md#input-values">input values</a>.
    <pre>
    - name: Outside
      temperature_sensor: weather.home
      humidity_sensor: weather.home
      unique_id: 3a6dd7e9-6b9d-4fd0-a0e3-0c3a1c4c9b7e
    </pre>
  </dd>
  <dt><strong>outdoor_temperature_sensor</strong> and <strong>outdoor_humidity_sensor</strong> <code>string</code> <code>(optional)</code></dt>
  <dd>
    IDs of the sensors of the outdoor temperature and the outdoor humidity. Both are needed. A weather entity can be both,
    its attributes are used. With them the sensors that compare the room with the outdoor air are created
    (<code>moisture_excess</code>, <code>ventilation_advice</code> and <code>ventilation_need</code>), by default or
    when they are in <code>sensor_types</code>. Without them these sensor types are left out. The two can be given
    once in the entry for all the rooms, instead of the room.
    See <a href="https://github.com/dolezsa/thermal_comfort/blob/master/documentation/ventilation.md">ventilation</a>.
  </dd>
  <dt><strong>pressure_sensor</strong> <code>string</code> <code>(optional)</code></dt>
  <dd>
    ID of an atmospheric pressure sensor entity, used for the moist air enthalpy.
    Without it, or while its value is unusable (unavailable or outside 300 to
    1100 hPa), the standard pressure of 101325 Pa is used. Use the station
    pressure, not a pressure reduced to sea level.
  </dd>
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

### Applying changes

Changes to the `thermal_comfort` section take effect after a restart, or after
calling the `thermal_comfort.reload` action (Developer tools, Actions), which
reloads the YAML configuration and the entities created from it. Entries set up
in the UI are not affected.

Sensors set up with YAML are not attached to a device. Use the
[UI](https://github.com/dolezsa/thermal_comfort/blob/master/documentation/config_flow.md)
if you want a device for each temperature and humidity pair.
