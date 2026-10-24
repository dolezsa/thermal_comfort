# Ventilation

With the sensors of the outdoor air a device compares the room with the air outside. Choose an outdoor temperature
sensor and an outdoor humidity sensor for the device (in the
[UI](https://github.com/dolezsa/thermal_comfort/blob/master/documentation/config_flow.md) or in
[YAML](https://github.com/dolezsa/thermal_comfort/blob/master/documentation/yaml.md)). A weather entity can be both, but its values
are rounded by Home Assistant and are data of a weather provider, not measured at your home. Then the device has three more sensors:

| Sensor | What it shows |
|---|---|
| `moisture_excess` | the absolute humidity of the room minus the one outdoors, in g/m³ |
| `ventilation_advice` | what airing does to the humidity of the room: `drier_outside`, `similar`, `more_humid_outside`, `condensation_risk` |
| `ventilation_need` | the moisture excess compared to the Swedish limit for winter: `above_limit`, `within_limit`, `not_winter` |

The [sensor documentation](https://github.com/dolezsa/thermal_comfort/blob/master/documentation/sensors.md) has the details and the sources.

## What to expect, and what not

* It tells what happens to the **humidity** of the room if you exchange the air. It does not tell if airing is worth the heat
  it loses, if it cools the room, or how long to air.
* It has no memory. "Not aired for hours", quiet hours, a window contact, wind or rain are for an automation, see below.
* The carbon dioxide is another matter, a dry room can have stale air. Use a CO₂ sensor for that.
* It is not a mould index. The mould depends on the humidity at the coldest surface and on time, a sensor in the room does not know it.
* The sensors are as good as the outdoor values. Two simple sensors (±3 % relative humidity) give a moisture excess with an
  uncertainty of about ±1 g/m³, so `similar` is a wide state. Use the outer states and a duration in automations.
* `ventilation_need` shows the moment, the Swedish limit is about usual values. A shower is enough to exceed it for a while.

## Recipes

The first reminds you to air the room when the outdoor air is clearly drier and the room is humid, in the daytime, with the window closed.
It uses the outer state of the advice and a duration, so it does not flip with the noise. The second reminds you to close the window.

```yaml
automation:
  - alias: "Living room: airing reminder"
    mode: single
    triggers:
      - trigger: numeric_state
        entity_id: sensor.living_room_moisture_excess
        above: 2             # the outer band, not the 1 g/m³ edge of the advice
        for: "00:15:00"
    conditions:
      - condition: numeric_state
        entity_id: sensor.living_room_humidity
        above: 60
      - condition: state
        entity_id: sensor.living_room_ventilation_advice
        state: drier_outside
      - condition: time
        after: "07:00:00"
        before: "22:00:00"
      - condition: state
        entity_id: binary_sensor.living_room_window
        state: "off"
    actions:
      - action: notify.notify
        data:
          message: >-
            Open the living room window: the outdoor air would bring the humidity to
            {{ state_attr('sensor.living_room_moisture_excess', 'ventilated_relative_humidity') | round(0) }} %
            (now {{ states('sensor.living_room_humidity') }} %).

  - alias: "Living room: close the window"
    triggers:
      - trigger: numeric_state
        entity_id: sensor.living_room_moisture_excess
        below: 0.5           # it re-arms when the excess has really dropped
        for: "00:10:00"
      - trigger: state
        entity_id: sensor.living_room_ventilation_advice
        to: condensation_risk
    conditions:
      - condition: state
        entity_id: binary_sensor.living_room_window
        state: "on"
    actions:
      - action: notify.notify
        data:
          message: "Close the living room window."
```

The Swedish limit is about a mean, not a moment. The mean of the moisture excess over a day, and the share of the time
above the limit in the last week:

```yaml
sensor:
  - platform: statistics
    name: "Living room moisture excess, 24 h mean"
    entity_id: sensor.living_room_moisture_excess
    state_characteristic: mean
    max_age:
      hours: 24
    sampling_size: 2000
  - platform: history_stats
    name: "Living room share of time above the limit"
    entity_id: sensor.living_room_ventilation_need
    state: above_limit
    type: ratio
    start: "{{ now() - timedelta(days=7) }}"
    end: "{{ now() }}"
```

A mean of the moisture excess over a few weeks in the winter, above 3 g/m³, is a reason to look at the ventilation of the room.

To air a hot room in a summer night, the outdoor air has to be cooler and must not bring condensation:

```yaml
template:
  - binary_sensor:
      - name: "Living room, cool outdoor air"
        state: >-
          {{ states('sensor.living_room_temperature') | float(0)
             - states('sensor.outdoor_temperature') | float(0) > 2
             and not is_state('sensor.living_room_ventilation_advice', 'condensation_risk') }}
```

More complete solutions, with windows, CO₂ and more, are the community blueprints and integrations for ventilation.
The sensors here can be their input.

## The outdoor sensors are removed again

The entities stay in the entity registry, Home Assistant shows them as not provided any more. Delete them there if you do not
want them. They work again, with their names and settings, when you add the outdoor sensors again.
