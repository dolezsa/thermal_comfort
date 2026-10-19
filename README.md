# [![thermal_comfort](https://raw.githubusercontent.com/dolezsa/thermal_comfort/master/icons/logo.png)](https://github.com/dolezsa/thermal_comfort)
[![hacs_badge](https://img.shields.io/badge/HACS-Default-41BDF5.svg?style=for-the-badge)](https://github.com/hacs/integration)
![GitHub release (latest by date)](https://img.shields.io/github/downloads/dolezsa/thermal_comfort/latest/total?style=for-the-badge&color=f55041)

Thermal Comfort provides a variety of thermal indices and thermal perceptions including feels like temperatures in numeric and textual representation for Home Assistant.

## Sensors:

**[Full list](https://github.com/dolezsa/thermal_comfort/blob/master/documentation/sensors.md)**

### Numeric Indices

Thermal Comfort provides numerical indices like `dew point`, `frost point`, `absolute humidity` and `moist air enthalpy` that are numeric values usable for further automations but also human readable. e.g. dew point tells the temperature to which air must be cooled to produce dew on a surface.

### Bio Indices / Perception

Thermal Comfort also provides a variety of bio indices like `humidex` or `heat index` giving numeric values of human perceived temperatures (feels like temperature). In addition we also provide textual perception sensors that describe the range of an index in human readable form e.g. comfortable or uncomfortable.

![Custom Icons](https://raw.githubusercontent.com/dolezsa/thermal_comfort/master/screenshots/outside.png)

## Usage
To use Thermal Comfort check the documentation for your preferred way to setup
sensors.

**[UI/Frontend (Config Flow)](https://github.com/dolezsa/thermal_comfort/blob/master/documentation/config_flow.md)**

**[YAML](https://github.com/dolezsa/thermal_comfort/blob/master/documentation/yaml.md)**

## Installation

### Requirements

Home Assistant 2025.8.0 or newer (which needs Python 3.13 or newer).

Older Home Assistant versions can keep using the 2.2 releases (Home Assistant
2023.12.0 or newer,
 [documentation](https://github.com/dolezsa/thermal_comfort/tree/2.2/documentation))
or the 1.5 releases for even older versions
 ([documentation](https://github.com/dolezsa/thermal_comfort/tree/1.5/documentation)).

### Using [HACS](https://hacs.xyz/) (recommended)

This integration can be installed using HACS. Open HACS, search for Thermal Comfort, download it and restart Home Assistant.

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

* Download `thermal_comfort.zip` from the [latest release](https://github.com/dolezsa/thermal_comfort/releases/latest) and extract it into the `custom_components/thermal_comfort` folder of your Home Assistant config folder.

Finally you need to restart home assistant before you can use it.

### Custom Icons
The [icon pack](https://github.com/rautesamtr/thermal_comfort_icons) is no longer
available in the HACS default repositories, follow the installation instructions
in its repository to install it.

Enable the custom icons options for your sensor in the
 [frontend](https://github.com/dolezsa/thermal_comfort/blob/master/documentation/config_flow.md#configuration-options)
 or in [yaml](https://github.com/dolezsa/thermal_comfort/blob/master/documentation/yaml.md#sensor-configuration-variables).

## Upgrading from 2.x to 3.0

* Home Assistant 2025.8.0 or newer is required.
* The calculated sensors are `unavailable` while a source sensor is unavailable, unknown or out of range
  (see [input values](https://github.com/dolezsa/thermal_comfort/blob/master/documentation/sensors.md#input-values)),
  instead of keeping the last value. They also start as `unavailable` instead of `unknown` until both sources are valid.
  Adjust automations or templates that relied on the old behavior.
* Humidity readings up to 105 % are treated as 100 %.
* Corrected formulas change the values of two attributes: `thoms_discomfort_index` (typically about 0.4 to 1.1 °C
  higher at 40 to 70 % humidity, more at higher humidity) and, from 3.0.1 on, `winter_scharlau_index`.
  The state of the Thom's discomfort and winter Scharlau perception sensors changes with them.
* Polling, the poll interval, custom icons and the enabled sensors are in a collapsed "Advanced options" section,
  advanced mode is no longer needed. Existing entries keep working unchanged.
* Any sensor entity can be chosen as a temperature or humidity source, sensors with a matching device class are listed first.
* The absolute humidity sensor has the `absolute_humidity` device class, and the `temperature` and `humidity`
  attributes are no longer stored in the recorder.

## Localization 🌎🗺
Contribute translations directly with PRs or via inlang's web-editor.

[![translation badge](https://inlang.com/badge?url=github.com/dolezsa/thermal_comfort)](https://inlang.com/editor/github.com/dolezsa/thermal_comfort?ref=badge)

## Support and Contributing
Please report bugs and ask questions in the [issues](https://github.com/dolezsa/thermal_comfort/issues),
see [CONTRIBUTING.md](CONTRIBUTING.md) if you want to contribute.
Thermal Comfort is licensed under the [MIT license](LICENSE), credits are listed in [CREDITS.md](CREDITS.md).
