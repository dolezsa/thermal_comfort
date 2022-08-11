# [![thermal_comfort](https://raw.githubusercontent.com/dolezsa/thermal_comfort/master/icons/logo.png)](https://github.com/dolezsa/thermal_comfort)
[![hacs_badge](https://img.shields.io/badge/HACS-Default-41BDF5.svg?style=for-the-badge)](https://github.com/hacs/integration)
![GitHub release (latest by date)](https://img.shields.io/github/downloads/dolezsa/thermal_comfort/latest/total?style=for-the-badge&color=f55041)

Thermal Comfort provides the following calculated sensors for Home Assistant.

## Sensors:

<dl>
  <dt><strong>Absolute Humidity</strong></dt>
  <dd>
    Absolute humidity is a measure of the actual amount of water vapor
      (moisture) in the air.
  </dd>
  <dt><strong>Heat Index</strong></dt>
  <dd>
    The heat index combines air temperature and relative humidity to posit a
    human-perceived equivalent temperature.
  </dd>
  <dt><strong>Humidex + Perception</strong></dt>
  <dd>
    The humidex (humidity index) describes how hot the weather feels to an average person as a result of the combined effect of heat and humidity. It is calculated from the dew point.
  </dd>
  <dt><strong>Dew Point</strong></dt>
  <dd>
    The dew point is the temperature to which air must be cooled to become
    saturated with water vapor and dew forms on surfaces.
  </dd>
  <dt><strong>Thermal Perception</strong></dt>
  <dd>
    Human perception of the dew point.
  </dd>
  <dt><strong>Frost Point</strong></dt>
  <dd>
    Frost point, temperature, below 0° C (32° F), at which moisture in the air 
    will condense as a layer of frost on any exposed surface.
  </dd>
  <dt><strong>Frost Risk</strong></dt>
  <dd>
    Risk of Frost based on current temperature, frost point and absolute humidity.
  </dd>
  <dt><strong>Simmer Index</strong></dt>
  <dd>
    An index that combines air temperature and relative humidity. In contrast to
    the Heat Index it describes the human-perceived equivalent temperature at
    night and describes a factor of discomfort.
  </dd>
  <dt><strong>Simmer Zone</strong></dt>
  <dd>
    Human perception of the simmer index.
  </dd>
  <dt><strong>Moist Air Enthalpy</strong></dt>
  <dd>
    The enthalpy of moist air is the sum of the enthalpy of the dry air and the enthalpy of the water vapour. Enthalpy is the total energy of a thermodynamic system.
  </dd>
  <dt><strong>Summer Scharlau Index/Perception</strong></dt>
  <dd>
    The summer Scharlau index describes a bioclimatic thermal comfort when temperature values are higher than 0°C. Valid for temperatures 17° to 39°C (63° to 102°F) and humidity >= 30%.
  </dd>
  <dt><strong>Winter Scharlau Index/Perception</strong></dt>
  <dd>
    Reflects the level of human discomfort caused by cooling. Valid for: temperatures -5 to +6°C (23 to 43°F) and humidity >= 40%.
  </dd>
</dl>

![Custom Icons](https://raw.githubusercontent.com/dolezsa/thermal_comfort/master/screenshots/living_room.png)

## Usage
To use Thermal Comfort check the documentation for your preferred way to setup
sensors.

**UI/Frontend (Config Flow)
 [1.5.2](https://github.com/dolezsa/thermal_comfort/blob/1.5.2/documentation/config_flow.md) /
 [master](https://github.com/dolezsa/thermal_comfort/blob/master/documentation/config_flow.md)**

**YAML
 [1.5.2](https://github.com/dolezsa/thermal_comfort/blob/1.5.2/documentation/yaml.md) /
 [master](https://github.com/dolezsa/thermal_comfort/blob/master/documentation/yaml.md)**

*Legacy YAML [1.5.2](https://github.com/dolezsa/thermal_comfort/blob/1.5.2/documentation/legacy_yaml.md)*

## Installation

### Requirements

Home Assistant >= 2021.12.0

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
