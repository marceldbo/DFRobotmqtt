# DFRobotmqtt
DFRobot Raspberry Pi UPS to MQTT script including notifications via a Pushover SMS service. The solution also triggers two separate scripts: one when a low power threshold has been reached and one when the Watchdog timer runs out.

## Implemented features summary

- Battery SOC and Voltage monitoring and publishing to MQTT
- Invoke external scripts when a configurable Low Power threshold has been reached
- Invoke external script when Watchdog time-out has been reached e.g. auto-reboot after X-seconds
- Send events to a Pushover SMS notification service
  
## Installation

To install:

- Go into /home/pi directory and run `git clone https://github.com/marceldbo/DFRobotmqtt.git`

To update:

- From the /home/pi/DFRobotmqtt directory, using a command line, do: `git pull` followed by a sudo systemctl daemon-reload

## Configuration

Open the /home/pi/DFRobotmqtt directory and copy the config.yaml.example file to config.yaml:

- cp config.yaml.example config.yaml
  
Open the **config.yaml** file and change the MQTT Broker IP and hostname and the broker username/password. If no username/password is required to use your broker then delete the username and password lines. Also configure the Pushover parameters e.g. user, token and desired messages. Save the file.

The next step is to create a python virtual environment (venv) in the DFRobotmqtt directory:

- python3 -m venv dfrobot-venv
  
and activate the virtual environment:

- source dfrobot-venv/bin/activate
  
The prompt will look like this:

- (dfrobot-venv) pi@hostname:~/DFRobotmqtt $

Now go into the virtual environment:

- (dfrobot-venv) pi@hostname:~/DFRobotmqtt $ cd dfrobot-venv
  
Do an **ls**, the contents should look like this:

  bin  include  lib  lib64  pyvenv.cfg
  
Copy the requirement.txt file from DFRobotmqtt into the venv:

- cp ../requirements.txt .
  
And do: 
                             
- pip install -r requirements.txt
                                            
Also edit the pyvenv.cfg file and set correct directory path:

  home = /usr/bin
  include-system-site-packages = false
  version = 3.11.2
  executable = /usr/bin/python3.11
  command = /usr/bin/python3 -m venv /home/pi/DFRobotmqtt/dfrobot-venv                                                                                                                                                                                                     
Now save the file and **deactivate** the venv:

  (dfrobot-venv) pi@hostname:~/DFRobotmqtt $ deactivate
  
We will return to the normal prompt and are ready to configure and run dfrobotmqtt.py as a background service: 

  sudo cp dfrobotmqtt.service /lib/systemd/system/dfrobotmqtt.service
  sudo nano /lib/systemd/system/dfrobotmqtt.service
  
and change the paths in WorkingDirectory and ExecStart to the location of pijuicemqtt.py. Because we are using a venv, we need to use the full path into the virtual environment:

  [Unit]
  Description=DFRobot UPS to MQTT
  After=multi-user.target
  StartLimitIntervalSec=610
  StartLimitBurst=10

  [Service]
  WorkingDirectory=/home/pi/DFRobotmqtt
  User=pi
  Type=idle
  ExecStart=/home/pi/DFRobotmqtt/dfrobot-venv/bin/python3 /home/pi/DFRobotmqtt/dfrobotmqtt.py
  Restart=always
  RestartSec=30

  [Install]
  WantedBy=multi-user.target

Now save and exit. Make sure that the **mosquitto mqtt broker** is running before starting the dfrobotmqtt.service as follows:

  sudo systemctl daemon-reload
  sudo systemctl enable dfrobotmqtt.service
  sudo systemctl start dfrobotmqtt.service
  sudo systemctl status dfrobotmqtt.service

You should see the background service active and running. Depending on the configuration the service will publish the status to MQTT every 30 seconds. The script will restart automatically if it crashes, and after Pi restart.

The script can be stopped by:

  sudo systemctl stop dfrobotmqtt.service

In addition, you can change the scripts to define what happens when the power drops below a certain point e.g. stopping certain applications and do a graceful shutdown. In case of a Watchdog time-out, the system will be restarted and a notification will be send via pushover.

## Ideas and TO DO's

- More generic external controls e.g. external control for a Heat Exchanger, etc.
- Support for separate language files as currently the devices are created in English.
- Adding a combined text device with system serial numbers, RTE, charge/discharge cycles etc.  
