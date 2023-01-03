# [![thermal_comfort](https://raw.githubusercontent.com/dolezsa/thermal_comfort/master/icons/logo.png)](https://github.com/dolezsa/thermal_comfort)
[![hacs_badge](https://img.shields.io/badge/HACS-Default-41BDF5.svg?style=for-the-badge)](https://github.com/hacs/integration)
![GitHub release (latest by date)](https://img.shields.io/github/downloads/dolezsa/thermal_comfort/latest/total?style=for-the-badge&color=f55041)

Thermal Comfort provides a variety of thermal indices and thermal perceptions including feels like temperatures in numeric and textual representation for Home Assistant.

## Sensors:

**Full list
 [1.5](https://github.com/dolezsa/thermal_comfort/blob/1.5/documentation/sensors.md) /
 [master](https://github.com/dolezsa/thermal_comfort/blob/master/documentation/sensors.md)**

### Numeric Indices

Thermal Comfort provides numerical indices like `dew point`, `frost point` and `absolute humidity` that are numeric values usable for further automations but also human readable. e.g. dew point tells the temperature to which air must be cooled to produce dew on a surface.

### Bio Indices / Perception

Thermal Comfort also provides a variety of bio indices like `heat index` giving numeric values of human perceived temperatures (feels like temperature). In addition we also provide textual perception sensors that describe the range of an index in human readable form e.g. comfortable or uncomfortable.

![Custom Icons](https://raw.githubusercontent.com/dolezsa/thermal_comfort/master/screenshots/living_room.png)

## Usage
To use Thermal Comfort check the documentation for your preferred way to setup
sensors.

**UI/Frontend (Config Flow)
 [1.5](https://github.com/dolezsa/thermal_comfort/blob/1.5/documentation/config_flow.md) /
 [master](https://github.com/dolezsa/thermal_comfort/blob/master/documentation/config_flow.md)**

**YAML
 [1.5](https://github.com/dolezsa/thermal_comfort/blob/1.5/documentation/yaml.md) /
 [master](https://github.com/dolezsa/thermal_comfort/blob/master/documentation/yaml.md)**

*Legacy YAML [1.5](https://github.com/dolezsa/thermal_comfort/blob/1.5/documentation/legacy_yaml.md)*

## Installation

### Requirements

#### 1.5
Home Assistant >= 2021.12.0

#### master
Home Assistant >= 2023.1.0

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

### Custom Icons
[Install](https://github.com/rautesamtr/thermal_comfort_icons#install) Thermal Comforts icon pack.

Enable the custom icons options for your sensor in the
 [frontend](https://github.com/dolezsa/thermal_comfort/blob/master/documentation/config_flow.md#configuration-options)
 or in [yaml](https://github.com/dolezsa/thermal_comfort/blob/master/documentation/yaml.md#sensor-configuration-variables).
