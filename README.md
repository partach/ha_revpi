[![Home Assistant](https://img.shields.io/badge/Home_Assistant-00A1DF?style=flat-square&logo=home-assistant&logoColor=white)](https://www.home-assistant.io)
[![HACS](https://img.shields.io/badge/HACS-Default-41BDF5?style=flat-square)](https://hacs.xyz)
[![HACS Action](https://img.shields.io/github/actions/workflow/status/partach/ha_revpi/validate-hacs.yml?label=HACS%20Action&style=flat-square)](https://github.com/partach/ha_revpi/actions)
[![License](https://img.shields.io/github/license/partach/ha_revpi?color=ffca28&style=flat-square)](https://github.com/partach/ha_revpi/blob/main/LICENSE)
[![HACS validated](https://img.shields.io/badge/HACS-validated-41BDF5?style=flat-square)](https://github.com/hacs/integration)
# RevPI for Home Assistant: ha_revpi
RevPI CPU and RevPI module support for Home Assistant


<p align="center">
<img src="https://github.com/partach/ha_revpi/blob/main/pictures/revpi-connect-5.png" width="400" style="vertical-align: middle; margin: 0 10px;"/>
<br><em>RevPi connect 5 with expansion modules</em>
</p>


<p align="center">
  <img src="https://github.com/partach/ha_revpi/blob/main/pictures/screenshot-pictory.png" width="500"/>
  <br><em>Pictory tool embedded in RevPi needed to setup your configuration</em>
</p>

## Features
- Integration runs directly on RevPi or on a remote HA installation on the same network
- Full control read / write of IOs via HA integration and via Card!
- Comes with automatic HA card installation. Ready to be used on your dashboard.
- No need for any yaml configuration!

## Installation of Integration
Options:
1. Install via HACS
   * coming
   * After HA reboot (Needed for new integrations): choose 'add integration' (in devices and services) and choose `ha_revpi` in the list.
2. Install manually:
   * The integration: In UI go to `HACS`--> `custom repositories` --> `Repo`: partach/ha_revpi, `Type`: Integration
   * After HA reboot (Needed for new integrations): choose 'add integration' (in devices and services) and choose `ha_revpi` in the list.
     
Let the install config of the integration guide you as it asks you for the needed data.

## Setting up RevPI CPU
1. unbox your goodies. Pay special attention to right side of CPU. It states the **URL and password** to connect to your CPU!
2. Write it down ** URL and password** as you need it later.
3. Best to use a DIN rail; Connect 24V power supply to CPU and module(s), see picture
<p align="center">
  <img src="https://github.com/partach/ha_revpi/blob/main/pictures/revpi-power.png" width="200"/>
  <br><em>Connect power supply 24V DC</em>
</p>
3. Connect network (wired out of the box, wireless is option). We assume now wired in this example
4. Use browser on same network. Use the data gathered in step 1. Example: https://revpi123456.local:41443 (see right side of CPU housing for actual serial number)
5. If all ok you get a login screen. User: pi , Password: as written down during unboxing in step 1.
6. You are now logged in! If not, repeat previous steps to see if you missed anything
7. On the right side of the menu, go to 'Software update' (if you are linux savvy you can use apt in the terminal...) 
<p align="center">
  <img src="https://github.com/partach/ha_revpi/blob/main/pictures/revpi-power.png" width="200"/>
  <br><em>Connect power supply 24V DC</em>
</p>

## Installation of Home Assistant on RevPI CPU
