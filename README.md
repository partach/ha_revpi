[![Home Assistant](https://img.shields.io/badge/Home_Assistant-00A1DF?style=flat-square&logo=home-assistant&logoColor=white)](https://www.home-assistant.io)
[![HACS](https://img.shields.io/badge/HACS-Default-41BDF5?style=flat-square)](https://hacs.xyz)
[![HACS Action](https://img.shields.io/github/actions/workflow/status/partach/ha_revpi/validate-hacs.yml?label=HACS%20Action&style=flat-square)](https://github.com/partach/ha_revpi/actions)
[![License](https://img.shields.io/github/license/partach/ha_revpi?color=ffca28&style=flat-square)](https://github.com/partach/ha_revpi/blob/main/LICENSE)
[![HACS validated](https://img.shields.io/badge/HACS-validated-41BDF5?style=flat-square)](https://github.com/hacs/integration)
# Home Assistant on RevPI: ha_revpi
RevPI CPU and RevPI module support for Home Assistant<BR>

The below tutorial is focussed on the main steps and skips details on standard RevPI knowledge or linux knowledge for that matter.<BR>
It is beyond the goal of this tutorial to explain those. For RevPI basics look at https://revolutionpi.com/ for more help


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

## Using the integration.
When following above steps with adding the integration, you are presented with the setup dialog of the integration:<BR>
<p align="center">
  <img src="https://github.com/partach/ha_revpi/blob/main/pictures/revpi-install.png" width="300"/>
  <br><em>Installation screen of the integration</em>
</p>
Choose local (default) if you are running Home Assistant directly on the RevPI (installation steps below). <BR>
(For remote connection see chapter below)
The `config rsc` file name and location should be filled in (how you saved the file in PiCtory, see below).<BR>
`Submit` If all was done correctly the integration will automaticall detect the CPU and modules.<BR>
<BR>
<p align="center">
  <img src="https://github.com/partach/ha_revpi/blob/main/pictures/revpi-integration1.png" width="500"/>
  <br><em>Each found module is a device in Home Assistant</em>
</p>
All entities can be used as normal in Home Assistant in any way you like.

## Using the Home Assistant Lovelace card.
The card is automatically installed and can be used on your dashboard.<BR>
When adding the card select the installed device in the visual setup of adding the card.<BR>
You can chose all found devices and the card will show that information. The card is specific to a module.
<p align="center">
  <img src="https://github.com/partach/ha_revpi/blob/main/pictures/revpi-card.png" width="500"/>
  <br><em>Dashboard example</em>
</p>
The card is interactive so you can also change values here (depending on how you setup the module in PiCtory)<BR>

## Setting up RevPI CPU
1. unbox your goodies. Pay special attention to right side of CPU. It states the **URL and password** to connect to your CPU!<BR>
2. Write it down **URL and password** as you need it later.<BR>
3. Best to use a DIN rail; Connect 24V power supply to CPU and module(s), see picture<BR>
<p align="center">
  <img src="https://github.com/partach/ha_revpi/blob/main/pictures/revpi-power.png" width="200"/>
  <br><em>Connect power supply 24V DC</em>
</p>
3. Connect network (wired out of the box, wireless is option). We assume now wired in this example<BR>
4. Use browser on same network. Use the data gathered in step 1. Example: https://revpi123456.local:41443 <BR>
     (see right side of CPU housing for actual serial number)<BR>
5. If all ok you get a login screen. User: pi , Password: as written down during unboxing in step 1.<BR>
6. You are now logged in! If not, repeat previous steps to see if you missed anything<BR>
7. On the right side of the menu, go to 'Software update' (if you are linux savvy you can use apt in the terminal...) <BR>
<BR>
<p align="center">
  <img src="https://github.com/partach/ha_revpi/blob/main/pictures/revpi-main-web.png" width="600"/>
  <br><em>Connect power supply 24V DC</em>
</p>

## Use PiCtory for enabling your setup for use with HA
Before you can use the integration in Home Assistant you need to make sure your RevPI setup is configured.
This goes via included PiCtory tool accessible via the URL of your RevPI CPU, see pictures above.
This tutorial is not meant for detailed RevPI knowledge, please use RevPI provided material for that.<BR>
Make sure of the following: <BR>
1. Chose `Open` button on top left to open Pictory in the Web default page (see picture above).<BR>
2. In PiCtory: Drag and drop your devices (CPU and Modules) in the exact order in the setup<BR>
3. Setup the module. For example MIO: make sure you mark `export` pre register you want to see in HA!
3. Save your configuration (File, Save / Save as default config). The name of the rsc file you need for the integration setup!

## Installation of Home Assistant on RevPI CPU
Setting up Home Assistant on your RevPI goes via the terminal, accessible via the default web home page after login (menu on the left).<BR>
See above how to login.
First install Docker.<BR>

```
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
```

create the file to run the Docker container (can be helpfull for later)<BR>

```
sudo nano run-home-assistant.sh
```

Copy past this text in the nano editor:<BR>

```
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
Some items are passed on to the container to ensure we can execute...
For example if you want to use a USB device in HA make sure you pass that via --device=/dev/ttyTheRightPort

To close nano: ctrl-x chose y(es) to write file.
Make sure the file is executable: <BR>

```
sudo chown 777 run-home-assistant.sh
```
now run the container to start HA (this is reboot safe due to options given when constructing the container).
Meaning when all goes well you don't have to ever run this start up script again (unless you want to change parameters).

```
./run-home-assistant.sh
```

## Installation of HACS for Home Assistant on RevPI CPU
Setting up HACS on your RevPI goes via the terminal, accessible via the default web home page after login (menu on the left).<BR>
See above how to login.
First make sure you have installed HA and the container is running (step above).
```
sudo docker exec -it homeassistant bash -c "wget -O - https://get.hacs.xyz | bash -"
sudo docker restart homeassistant
```
The rest is default HACS install (in HA go to settings --> devices and services --> button 'Add Integration' --> chose HACS --> follow rest of steps


## Run integration on other HA installation in the network
With default settings of the RevPI this is not possible.<BR>
You need to adapt (via terminal) some settings.

[PLCSERVER] is disabled — plcserver = 0. This is the service RevPiNetIO connects to.<BR>
[XMLRPC] is bound to localhost — bindip = 127.0.0.1, so it only accepts local connections.

To fix both:
```
sudo nano /etc/revpipyload/revpipyload.conf
```

Change:

[PLCSERVER] section: plcserver = 0 → plcserver = 1<BR>
[XMLRPC] section: bindip = 127.0.0.1 → bindip = *<BR>
<BR>
Now add your HA host to the allowed list:
```
sudo nano /etc/revpipyload/aclplcserver.conf
```
Add the IP and ACL level of your local HA instance there like 192.168.x.x,2
ACL level 2 is read/write (1 is read only)

Then restart:
```
sudo systemctl restart revpipyload
```

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
