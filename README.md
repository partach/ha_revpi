[![Home Assistant](https://img.shields.io/badge/Home_Assistant-00A1DF?style=flat-square&logo=home-assistant&logoColor=white)](https://www.home-assistant.io)
[![HACS](https://img.shields.io/badge/HACS-Default-41BDF5?style=flat-square)](https://hacs.xyz)
[![HACS Action](https://img.shields.io/github/actions/workflow/status/partach/ha_revpi/validate-hacs.yml?label=HACS%20Action&style=flat-square)](https://github.com/partach/ha_revpi/actions)
[![License](https://img.shields.io/github/license/partach/ha_revpi?color=ffca28&style=flat-square)](https://github.com/partach/ha_revpi/blob/main/LICENSE)
[![HACS validated](https://img.shields.io/badge/HACS-validated-41BDF5?style=flat-square)](https://github.com/hacs/integration)
# Home Assistant on RevPI: ha_revpi
RevPI CPU and RevPI module support for Home Assistant<br>

The below tutorial is focussed on the main steps and skips details on standard RevPI knowledge or linux knowledge for that matter.<br>
It is beyond the goal of this tutorial to explain those. For RevPI basics look at https://revolutionpi.com/ for more help


<p align="center">
<img src="https://github.com/partach/ha_revpi/blob/main/pictures/revpi-connect-5.png" width="400" style="vertical-align: middle; margin: 0 10px;"/>
<br><em>RevPi connect 5 with expansion modules</em>
</p>


<p align="center">
  <img src="https://github.com/partach/ha_revpi/blob/main/pictures/screenshot-pictory.png" width="500"/>
  <br><em>Pictory tool embedded in RevPi needed to setup your configuration</em>
</p>

## Table of Contents

- [Features](#features)
- [Installation](#installation-of-the-integration)
- [General usage](#using-the-integration)
- [Usage of the Card](#using-the-home-assistant-lovelace-card)
- [Setup Revpi](#setting-up-revpi-cpu)
- [Use PiCtory](#use-pictory-for-enabling-your-setup-for-use-with-ha)
- [Installing HA on RevPI](#installation-of-home-assistant-on-revpi-cpu)
- [Install HACS on RevPI](#installation-of-hacs-for-home-assistant-on-revpi-cpu)
- [Integration on Remote HA client](#run-integration-on-other-ha-installation-in-the-network)
- [Equipment Templates](#equipment-templates)
- [MQTT publishing](#mqtt-publishing)


## Features
- Integration runs directly on RevPi or on a remote HA installation on the same network
- Full control read / write of IOs via HA integration and via Card!
- Comes with automatic HA card installation. Ready to be used on your dashboard.
- No need for any yaml configuration!

## Installation of the Integration
Options:
1. Install via HACS
   * coming (first install Home Assistant and HACS on RevPi, see below)
   * After Home Assistant reboot (Needed for new integrations): choose 'add integration' (in devices and services) and choose `ha_revpi` in the list.
2. Install manually:
   * First install Home Assistant and HACS on RevPi, see further below on RevPI installation steps
   * The integration: In UI go to `HACS`--> `custom repositories` --> `Repo`: partach/ha_revpi, `Type`: Integration
   * After HA reboot (Needed for new integrations): choose 'add integration' (in devices and services) and choose `ha_revpi` in the list.
     
Let the install config of the integration guide you as it asks you for the needed data, see next step.

## Using the integration
When following above steps with adding the integration, you are presented with the setup dialog of the integration:<br>
<p align="center">
  <img src="https://github.com/partach/ha_revpi/blob/main/pictures/revpi-install.png" width="300"/>
  <br><em>Installation screen of the integration</em>
</p>

Choose local (default) if you are running Home Assistant directly on the RevPI (installation steps below).<br>
(For remote connection see chapter below)<br>
<br>
The `config.rsc` file name and location should be filled in (how you saved the file in PiCtory, see below).<br>
`Submit` If all was done correctly the integration will automatically detect the CPU and modules.<br>
<br>

<p align="center">
  <img src="https://github.com/partach/ha_revpi/blob/main/pictures/revpi-integration1.png" width="500"/>
  <br><em>Each found module is a device in Home Assistant</em>
</p>

All entities can be used as normal in Home Assistant in any way you like.

## Using the Home Assistant Lovelace cards.
The cards are automatically installed and can be used on your dashboard.<br>
There are current 2 cards you can choose from:<br>
1. the module card. (Showing status of revpi modules configured)<br>
2. the device card. (Showing the additional configured equipment/devices via templates).<br>

When adding one of the cards, select the installed device in the visual setup of adding the card.<br>
You can choose all found devices and the card will show that information.<br>

<p align="center">
  <img src="https://github.com/partach/ha_revpi/blob/main/pictures/revpi-card.png" width="500"/>
  <img src="https://github.com/partach/ha_revpi/blob/main/pictures/revpi-device-card.png" width="240"/>
  <br><em>Dashboard revpi modules and equipment example</em>
</p>

The card is interactive so you can also change values here (depending on how you setup the module in PiCtory)<br>

## Setting up RevPI CPU
1. Unbox your goodies. Pay special attention to right side of CPU. It states the **URL and password** to connect to your CPU!<br>
2. Write it down **URL and password** as you need it later.<br>
3. Best to use a DIN rail; Connect 24V power supply to CPU and module(s), see picture<br>

<p align="center">
  <img src="https://github.com/partach/ha_revpi/blob/main/pictures/revpi-power.png" width="200"/>
  <br><em>Connect power supply 24V DC</em>
</p>

3. Connect network (wired out of the box, wireless is option). We assume now wired in this example<br>
4. Use browser on same network. Use the data gathered in step 1. Example: https://revpi123456.local:41443 <br>
     (see right side of CPU housing for actual serial number)<br>
5. If all ok you get a login screen. User: `pi` , Password: `as written down during unboxing in step 1`.<br>
6. You are now logged in! If not, repeat previous steps to see if you missed anything.<br>
7. On the left side menu, go to `Software update` (if you are linux savvy you can use apt in the terminal...) <br>
<br>

<p align="center">
  <img src="https://github.com/partach/ha_revpi/blob/main/pictures/revpi-main-web.png" width="600"/>
  <br><em>Main RevPI Web management page</em>
</p>

## Use PiCtory for enabling your setup for use with HA
Before you can use the integration in Home Assistant you need to make sure your RevPI setup is configured.
This goes via included PiCtory tool accessible via the URL of your RevPI CPU, see pictures above.
This tutorial is not meant for detailed RevPI knowledge, please use RevPI provided material for that.<br>
Make sure of the following: <br>
1. Choose `Open` button on top left to open Pictory in the Web default page (see picture above).<br>
2. In PiCtory: Drag and drop your devices (CPU and Modules) in the exact order in the setup<br>
3. Setup the module. For example MIO: make sure you mark `export` per register you want to see in HA!
3. Save your configuration (File, Save / Save as default config). The name of the rsc file you need for the integration setup!

## Installation of Home Assistant on RevPI CPU
Setting up Home Assistant on your RevPI goes via the terminal, accessible via the default web home page after login (menu on the left).<br>
See above how to login.<br>
First install Docker.<br>

```
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
```

create the file to run the Docker container (can be helpfull for later)<br>

```
sudo nano run-home-assistant.sh
```

Copy past this text in the nano editor:<br>

```
#!/usr/bin/env bash
sudo docker run -d \
  --name homeassistant \
  --privileged \
  --restart=unless-stopped \
  --device=/dev/piControl0 \
  -e TZ=Europe/Amsterdam \
  -v /home/pi/homeassistant:/config \
  -v /var/www/revpi/pictory/projects:/var/www/revpi/pictory/projects:ro \
  -v /dev:/dev \
  -p 8123:8123 \
  homeassistant/home-assistant:stable
```
Change the timezone above if needed for your installation.
Some items are passed on to the container to ensure we can execute...<br>
For example if you want to use a USB device in HA make sure you pass that via<br>
`--device=/dev/ttyTheRightPort`

To close nano: `ctrl-x` choose `y(es)` to write file.<br>
Make sure the file is executable: <br>

```
sudo chown +x run-home-assistant.sh
```
Now run the container to start HA (this is reboot safe due to options given when constructing the container).<br>
Meaning when all goes well you don't have to ever run this start up script again (unless you want to change parameters).

```
./run-home-assistant.sh
```

If you want to know your RevPI IP address use:
```
hostname -I
```

If you want to have the HA terminal:
```
sudo docker exec -it homeassistant bash
```

## Installation of HACS for Home Assistant on RevPI CPU
Setting up HACS on your RevPI goes via the terminal, accessible via the default web home page after login (menu on the left).<br>
See above how to login.<br>
First make sure you have installed HA and the container is running (step above).<br>
```
sudo docker exec -it homeassistant bash -c "wget -O - https://get.hacs.xyz | bash -"
sudo docker restart homeassistant
```
The rest is default HACS install 
In HA go to `settings --> devices and services --> button 'Add Integration' --> choose HACS --> follow rest of steps`


## Run integration on other HA installation in the network
With default settings of the RevPI this is not possible (yet).<br>
You need to adapt (via terminal) some settings.<br>

[PLCSERVER] is disabled — plcserver = 0. This is the service RevPiNetIO connects to.<br>
[XMLRPC] is bound to localhost — bindip = 127.0.0.1, so it only accepts local connections.<br>

To change both:
```
sudo nano /etc/revpipyload/revpipyload.conf
```

Change:

[PLCSERVER] section: plcserver = 0 → plcserver = 1<br>
[XMLRPC] section: bindip = 127.0.0.1 → bindip = *<br>
<br>
Now add your HA host to the allowed list:
```
sudo nano /etc/revpipyload/aclplcserver.conf
```
Add the IP and ACL level of your local HA instance there like 192.168.x.x,2<br>
ACL level 2 is read/write (1 is read only)

Then restart:
```
sudo systemctl restart revpipyload
```

But... did not get it working yet. Not sure if revpimodio2 2.8.1 (running on HA) is fully compatible with latest RevPI revpipyload?

## Equipment Templates
Beyond individual IOs, ha_revpi lets you group RevPi inputs and outputs into logical equipment (**building devices**) such as air handling units (AHUs), fans, valves, and dampers. Each building device maps raw RevPi IO points to meaningful roles and can apply transforms (e.g. converting a 0-10V raw value to 0-100%).

### Templates
Building devices are created from JSON templates. Several built-in templates are included:
- **ahu_basic** -- Air handling unit with supply fan, heating valve, damper, and filter alarm
- **fan_basic** -- Simple fan with start/stop command and running feedback
- **valve_basic** -- Modulating valve with position command and feedback
- **damper_basic** -- Damper with position control

Templates define the IO roles, data types, transforms, and optionally a PID control section. You can also create your own templates by placing JSON files in the `custom_components/ha_revpi/templates/` directory.

### Adding a Building Device
1. Go to **Settings > Devices & Services > ha_revpi > Configure**
2. Select **Add building device**
3. Choose a template from the list
4. Remap the IO names to match your PiCtory configuration (the template provides defaults, but your actual IO names will differ)
5. Submit -- the device and its entities are created immediately, no restart needed

Each building device appears as its own device in Home Assistant with entities for each mapped IO (sensors, switches, numbers, climate, fan, or cover depending on the device type).

### PID Control
Templates can include a PID control section. When enabled, a built-in PID controller loop runs in the background, reading a measured value (e.g. supply temperature) and writing to an output (e.g. heating valve). PID parameters (Kp, Ti, Td, setpoint) are exposed as number entities so you can tune them live from the dashboard.

## MQTT Publishing
ha_revpi includes an optional MQTT publisher that sends IO values to an MQTT broker. This is useful for integrating with external systems, logging, or bridging to other automation platforms. It uses its own standalone MQTT client (paho-mqtt), independent of the HA MQTT integration.

### Configuration
1. Go to **Settings > Devices & Services > ha_revpi > Configure**
2. Select **Configure MQTT publishing**
3. Fill in the broker settings:
   - **Enabled** -- toggle MQTT on/off
   - **Broker** -- hostname or IP of your MQTT broker
   - **Port** -- default 1883
   - **Username / Password** -- optional, for authenticated brokers
   - **Main topic** -- prefix for all published topics (default: `revpi`)
   - **Publish interval** -- minimum seconds between publishes of the same topic (1-60, default: 5)
   - **Publish core** -- enable publishing of CPU diagnostics (temperature, frequency, IO cycle time)
   - **Publish devices** -- select which building devices to publish

The connection is tested when you submit. If the broker is unreachable you will see an error before the configuration is saved.

### Topic Structure
Values are published as simple scalar payloads (numbers or `true`/`false`):
```
{main_topic}/revpi/core/cpu_temperature          → 52.3
{main_topic}/revpi/core/cpu_frequency             → 1500
{main_topic}/revpi/core/io_cycle                  → 8

{main_topic}/revpi/devices/{device_name}/temperature     → 21.5
{main_topic}/revpi/devices/{device_name}/heating_valve    → 45
{main_topic}/revpi/devices/{device_name}/fan_status       → true
{main_topic}/revpi/devices/{device_name}/alarms/filter_alarm → false
```

Only changed values are published, and each topic is rate-limited to the configured publish interval.


## Discussion 
See [here](https://github.com/partach/ha_revpi/discussions)

## Changelog
See [CHANGELOG.md](https://github.com/partach/ha_revpi/blob/main/CHANGELOG.md)

## Issues
Report at GitHub [Issues](https://github.com/partach/ha_revpi/issues)

## Support development
Are you working at RevPI? I could always use modules to test and integrate! Please reach out!
If you like this work, and find it usefull, or want to support this and future developments, it would be greatly appreciated :)

[![Donate](https://img.shields.io/badge/Donate-PayPal-green.svg?style=flat-square)](https://paypal.me/therealbean)
