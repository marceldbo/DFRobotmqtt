# DFRobotmqtt

A Python script for monitoring a **DFRobot Raspberry Pi UPS HAT** and publishing UPS information to MQTT. The solution also supports **Pushover notifications** and can execute external scripts when a low-power threshold or watchdog timeout is reached.

## Features

* Monitor and publish **Battery State of Charge (SOC)** to MQTT
* Monitor and publish **Battery Voltage** to MQTT
* Invoke an external script when a configurable **low-power threshold** is reached
* Invoke an external script when the **watchdog timeout** is reached

  * For example, automatically reboot or shut down the Raspberry Pi
* Send events and alerts through **Pushover**
* Run continuously as a **systemd service**
* Automatically restart the service if it crashes
* Automatically start the service after a Raspberry Pi reboot

## Installation

### Clone the repository

Go to `/home/pi` and clone the repository:

```bash
cd /home/pi
git clone https://github.com/marceldbo/DFRobotmqtt.git
```

### Updating the installation

To update the software, go to the repository directory and pull the latest changes:

```bash
cd /home/pi/DFRobotmqtt
git pull
```

If the systemd service configuration has changed, reload systemd:

```bash
sudo systemctl daemon-reload
```

## Configuration

Copy the example configuration file to `config.yaml`:

```bash
cd /home/pi/DFRobotmqtt
cp config.yaml.example config.yaml
```

Open `config.yaml` and configure the following:

* MQTT broker IP address or hostname
* MQTT username and password
* Pushover user key
* Pushover API token
* Pushover notification messages
* Low-power threshold
* Watchdog settings
* Other available script parameters

If your MQTT broker does not require authentication, remove the MQTT username and password entries from `config.yaml`.

Save the configuration file when finished.

> **Important:** Do not commit your personal `config.yaml` to GitHub if it contains passwords, API tokens, or other sensitive information. Keep the example values in `config.yaml.example`.

## Python Virtual Environment

Create a Python virtual environment in the `DFRobotmqtt` directory:

```bash
cd /home/pi/DFRobotmqtt
python3 -m venv dfrobot-venv
```

Activate the virtual environment:

```bash
source dfrobot-venv/bin/activate
```

Your command prompt should now look similar to:

```text
(dfrobot-venv) pi@hostname:~/DFRobotmqtt $
```

### Install the required Python packages

Copy the requirements file into the virtual environment directory:

```bash
cp requirements.txt dfrobot-venv/
```

Change to the virtual environment directory:

```bash
cd dfrobot-venv
```

The directory should contain:

```text
bin
include
lib
lib64
pyvenv.cfg
requirements.txt
```

Install the required packages:

```bash
pip install -r requirements.txt
```

### Verify `pyvenv.cfg`

The `pyvenv.cfg` file should contain paths appropriate for your Python installation. For example:

```ini
home = /usr/bin
include-system-site-packages = false
version = 3.11.2
executable = /usr/bin/python3.11
command = /usr/bin/python3 -m venv /home/pi/DFRobotmqtt/dfrobot-venv
```

The exact Python version and paths may differ depending on your Raspberry Pi OS installation.

Save the file and deactivate the virtual environment:

```bash
deactivate
```

## Configure the systemd Service

The application can be run as a background service using `systemd`.

Copy the service definition:

```bash
sudo cp dfrobotmqtt.service /lib/systemd/system/dfrobotmqtt.service
```

Edit the service file if necessary:

```bash
sudo nano /lib/systemd/system/dfrobotmqtt.service
```

Make sure `WorkingDirectory` and `ExecStart` point to the correct installation directory and Python virtual environment.

Example:

```ini
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
```

> **Note:** If your installation is not located in `/home/pi/DFRobotmqtt`, update the paths accordingly.

## Start the Service

Make sure the **Mosquitto MQTT broker** is running before starting the DFRobotmqtt service.

Reload the systemd configuration:

```bash
sudo systemctl daemon-reload
```

Enable the service so that it starts automatically after a reboot:

```bash
sudo systemctl enable dfrobotmqtt.service
```

Start the service:

```bash
sudo systemctl start dfrobotmqtt.service
```

Check its status:

```bash
sudo systemctl status dfrobotmqtt.service
```

You should see the service listed as **active (running)**.

Depending on your configuration, the script will publish UPS status information to MQTT every **30 seconds**.

The service is configured to restart automatically if the Python script crashes and will automatically start again after a Raspberry Pi reboot.

## Stop the Service

To stop the service manually:

```bash
sudo systemctl stop dfrobotmqtt.service
```

To restart it:

```bash
sudo systemctl restart dfrobotmqtt.service
```

To prevent it from starting automatically after a reboot:

```bash
sudo systemctl disable dfrobotmqtt.service
```

## External Scripts

The solution can execute external scripts when specific conditions occur.

### Low-power threshold

When the battery level drops below the configured low-power threshold, the configured external script can be executed.

This can be used, for example, to:

* Stop applications
* Stop services
* Perform a graceful shutdown
* Send additional notifications

### Watchdog timeout

If the configured watchdog timer expires, the watchdog action can be triggered.

This can be used, for example, to:

* Reboot the Raspberry Pi
* Shut down the Raspberry Pi
* Stop specific services
* Send a Pushover notification

The exact actions depend on the external scripts configured for your installation.

## Pushover Notifications

The script supports notifications through **Pushover**.

Configure your Pushover credentials and desired notification messages in `config.yaml`.

Notifications can be used to report events such as:

* Low battery condition
* Watchdog timeout
* Automatic restart
* Other UPS-related events supported by the script

## Monitoring the Service

To view the service status:

```bash
sudo systemctl status dfrobotmqtt.service
```

To view the live service log:

```bash
sudo journalctl -u dfrobotmqtt.service -f
```

To view recent log entries:

```bash
sudo journalctl -u dfrobotmqtt.service
```

## MQTT

The script publishes UPS information to the configured MQTT broker.

The exact MQTT topics and payloads depend on the settings in `config.yaml`.

Typical information includes:

* Battery SOC
* Battery voltage
* UPS status
* Watchdog-related events
* Power-related events

## Troubleshooting

If the service does not start, first check its status:

```bash
sudo systemctl status dfrobotmqtt.service
```

Then check the systemd log:

```bash
sudo journalctl -u dfrobotmqtt.service -n 100 --no-pager
```

If the MQTT connection is not working, verify:

1. The Mosquitto broker is running.
2. The MQTT hostname/IP address in `config.yaml` is correct.
3. The MQTT username and password are correct, if authentication is enabled.
4. The Raspberry Pi can reach the MQTT broker over the network.

You can also run the script manually from the virtual environment to see Python errors directly:

```bash
cd /home/pi/DFRobotmqtt
source dfrobot-venv/bin/activate
python3 dfrobotmqtt.py
```

## License

See the repository for licensing information.

## Author

**Marcel de Bont**

GitHub: [@marceldbo](https://github.com/marceldbo)
