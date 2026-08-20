#!/usr/bin/env python3

"""
DFRobot Raspberry Pi UPS HAT -> MQTT

Configuration is loaded from config.yaml.

Supports:
    - DFR0494 UPS HAT
    - MQTT publishing
    - Low battery detection
    - Watchdog timeout
    - External Python action scripts
"""

import json
import time
import logging
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml
import paho.mqtt.client as mqtt

try:
    from smbus2 import SMBus
except ImportError:
    from smbus import SMBus


# ============================================================
# Configuration file
# ============================================================

CONFIG_FILE = (
    Path(__file__).resolve().parent / "config.yaml"
)


# ============================================================
# Logging
# ============================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)

logger = logging.getLogger("dfrobot-ups")


# ============================================================
# Configuration loader
# ============================================================

def load_config():

    if not CONFIG_FILE.exists():

        raise FileNotFoundError(
            f"Configuration file not found: {CONFIG_FILE}"
        )

    with open(
        CONFIG_FILE,
        "r",
        encoding="utf-8"
    ) as file:

        config = yaml.safe_load(file)

    if not config:
        raise ValueError(
            "Configuration file is empty"
        )

    return config


# ============================================================
# DFRobot UPS registers
# ============================================================

REG_FIRMWARE_VERSION = 0x02

REG_VOLTAGE_HIGH = 0x03
REG_VOLTAGE_LOW = 0x04

REG_SOC_HIGH = 0x05
REG_SOC_LOW = 0x06


# ============================================================
# UPS HAT
# ============================================================

class DFRobotUPS:

    def __init__(
        self,
        bus_number,
        address
    ):

        self.address = address

        self.bus = SMBus(
            bus_number
        )


    def read_firmware_version(self):

        value = self.bus.read_byte_data(
            self.address,
            REG_FIRMWARE_VERSION
        )

        major = (value >> 4) & 0x0F
        minor = value & 0x0F

        return f"{major}.{minor}"


    def read_voltage(self):

        high = self.bus.read_byte_data(
            self.address,
            REG_VOLTAGE_HIGH
        )

        low = self.bus.read_byte_data(
            self.address,
            REG_VOLTAGE_LOW
        )

        raw = (
            ((high & 0x0F) << 8)
            | low
        )

        voltage_mv = raw * 1.25

        return voltage_mv


    def read_soc(self):

        high = self.bus.read_byte_data(
            self.address,
            REG_SOC_HIGH
        )

        low = self.bus.read_byte_data(
            self.address,
            REG_SOC_LOW
        )

        raw = (
            (high << 8)
            | low
        )

        soc = raw * 0.003906

        return max(
            0.0,
            min(100.0, soc)
        )


    def read(self):

        voltage_mv = self.read_voltage()

        soc = self.read_soc()

        firmware_version = self.read_firmware_version()

        return {
	    "firmware_version":
		firmware_version,

	    "voltage":
                round(
                    voltage_mv / 1000.0,
                    3
                ),

            "voltage_mv":
                round(
                    voltage_mv,
                    1 
                ),

            "battery":
                round(soc)
        }


    def close(self):

        self.bus.close()


# ============================================================
# External Python script
# ============================================================

def execute_script(
    script,
    reason,
    data
):

    if not script:

        logger.warning(
            "No script configured for %s",
            reason
        )

        return


    payload = json.dumps(
        data,
        separators=(",", ":")
    )


    try:

        logger.warning(
            "Executing %s: %s",
            reason,
            script
        )


        result = subprocess.run(
            [
                sys.executable,
                script,
                reason,
                payload
            ],

            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,

            text=True,

            timeout=30
        )


        if result.returncode == 0:

            logger.info(
                "Script completed successfully: %s",
                script
            )

            if result.stdout:

                logger.info(
                    "Script output: %s",
                    result.stdout.strip()
                )

        else:

            logger.error(
                "Script failed: %s "
                "return code=%s",
                script,
                result.returncode
            )

            if result.stderr:

                logger.error(
                    "Script error: %s",
                    result.stderr.strip()
                )


    except FileNotFoundError:

        logger.error(
            "Script not found: %s",
            script
        )


    except subprocess.TimeoutExpired:

        logger.error(
            "Script timed out: %s",
            script
        )


    except Exception as e:

        logger.error(
            "Unable to execute script %s: %s",
            script,
            e
        )


# ============================================================
# MQTT
# ============================================================

def create_mqtt_client(config):

    mqtt_config = config["mqtt"]


    client = mqtt.Client(
        mqtt.CallbackAPIVersion.VERSION2,

        client_id=
            mqtt_config["client_id"]
    )


    username = mqtt_config.get(
        "username",
        ""
    )

    password = mqtt_config.get(
        "password",
        ""
    )


    if username:

        client.username_pw_set(
            username,
            password
        )


    client.will_set(
        mqtt_config["status_topic"],

        payload="offline",

        qos=1,

        retain=True
    )


    return client


def mqtt_connect(
    client,
    config
):

    mqtt_config = config["mqtt"]


    while True:

        try:

            broker = mqtt_config["broker"]

            port = mqtt_config["port"]


            logger.info(
                "Connecting to MQTT broker "
                "%s:%s",
                broker,
                port
            )


            client.connect(
                broker,
                port,
                60
            )


            client.loop_start()


            client.publish(
                mqtt_config["status_topic"],

                "online",

                qos=1,

                retain=True
            )


            logger.info(
                "Connected to MQTT broker"
            )


            return True


        except Exception as e:

            logger.error(
                "MQTT connection failed: %s",
                e
            )


            time.sleep(
                mqtt_config.get(
                    "reconnect_delay",
                    10
                )
            )


# ============================================================
# Main
# ============================================================

def main():

    logger.info(
        "Starting DFRobot UPS MQTT monitor"
    )


    # --------------------------------------------------------
    # Load configuration
    # --------------------------------------------------------

    try:

        config = load_config()

    except Exception as e:

        logger.error(
            "Unable to load configuration: %s",
            e
        )

        return 1


    # --------------------------------------------------------
    # Configuration
    # --------------------------------------------------------

    i2c_config = config["i2c"]

    mqtt_config = config["mqtt"]

    monitor_config = config["monitor"]

    battery_config = config["low_battery"]

    watchdog_config = config["watchdog"]


    logger.info(
        "Configuration loaded from %s",
        CONFIG_FILE
    )


    logger.info(
        "I2C bus=%s address=0x%02X",
        i2c_config["bus"],
        i2c_config["address"]
    )


    logger.info(
        "Low battery threshold=%.1f%%",
        battery_config["threshold"]
    )


    logger.info(
        "Low battery reset threshold=%.1f%%",
        battery_config["reset_threshold"]
    )


    logger.info(
        "Watchdog timeout=%s seconds",
        watchdog_config["timeout"]
    )


    # --------------------------------------------------------
    # Open UPS
    # --------------------------------------------------------

    try:

        ups = DFRobotUPS(
            bus_number=i2c_config["bus"],
            address=i2c_config["address"]
        )


        logger.info(
            "Connected to UPS HAT"
        )


    except Exception as e:

        logger.error(
            "Unable to open UPS HAT: %s",
            e
        )

        return 1


    # --------------------------------------------------------
    # MQTT
    # --------------------------------------------------------

    mqtt_client = create_mqtt_client(
        config
    )

    mqtt_connect(
        mqtt_client,
        config
    )


    # --------------------------------------------------------
    # State
    # --------------------------------------------------------

    low_battery_alarm = False

    watchdog_alarm = False

    last_successful_read = (
        time.monotonic()
    )


    # --------------------------------------------------------
    # Main loop
    # --------------------------------------------------------

    try:

        while True:

            try:

                # ==================================================
                # Read UPS
                # ==================================================

                data = ups.read()


                last_successful_read = (
                    time.monotonic()
                )


                # ==================================================
                # Watchdog recovery
                # ==================================================

                if watchdog_alarm:

                    logger.info(
                        "UPS communication restored"
                    )


                    watchdog_alarm = False


                    mqtt_client.publish(
                        mqtt_config["status_topic"],

                        "online",

                        qos=1,

                        retain=True
                    )


                # ==================================================
                # Low battery
                # ==================================================

                battery = data["battery"]


                if (
                    battery
                    < battery_config["threshold"]

                    and not low_battery_alarm
                ):

                    low_battery_alarm = True


                    logger.warning(
                        "LOW BATTERY: %.2f%%",
                        battery
                    )


                    alarm_data = dict(data)


                    alarm_data.update({

                        "reason":
                            "low_battery",

                        "threshold":
                            battery_config[
                                "threshold"
                            ],

                        "timestamp":
                            datetime.now(
                                timezone.utc
                            ).astimezone()
                            .isoformat()
                    })


                    execute_script(
                        battery_config["script"],

                        "low_battery",

                        alarm_data
                    )


                elif (
                    battery
                    >= battery_config[
                        "reset_threshold"
                    ]

                    and low_battery_alarm
                ):

                    low_battery_alarm = False


                    logger.info(
                        "Battery recovered: %.2f%%",
                        battery
                    )


                # ==================================================
                # Status
                # ==================================================

                if low_battery_alarm:

                    status = "low_battery"

                else:

                    status = "online"


                # ==================================================
                # MQTT payload
                # ==================================================

                data["status"] = status

                data["low_battery_alarm"] = (
                    low_battery_alarm
                )

                data["watchdog_alarm"] = (
                    watchdog_alarm
                )

                data["timestamp"] = (
                    datetime.now(
                        timezone.utc
                    ).astimezone()
                    .isoformat()
                )


                payload = json.dumps(
                    data,
                    separators=(",", ":")
                )


                # ==================================================
                # Publish
                # ==================================================

                result = mqtt_client.publish(

                    mqtt_config["topic"],

                    payload,

                    qos=1,

                    retain=True
                )


                if result.rc != mqtt.MQTT_ERR_SUCCESS:

                    logger.error(
                        "MQTT publish failed: %s",
                        result.rc
                    )

                else:

                    logger.info(
                        "UPS: %.3f V, %.2f%%, status=%s",

                        data["voltage"],

                        data["battery"],

                        status
                    )


            except Exception as e:

                logger.error(
                    "Error reading UPS: %s",
                    e
                )


            # ==================================================
            # Watchdog
            # ==================================================

            elapsed = (
                time.monotonic()
                - last_successful_read
            )


            if (
                elapsed
                >= watchdog_config["timeout"]

                and not watchdog_alarm
            ):

                watchdog_alarm = True


                logger.error(
                    "WATCHDOG TIMEOUT: "
                    "no successful UPS reading "
                    "for %.1f seconds",
                    elapsed
                )


                watchdog_data = {

                    "reason":
                        "watchdog",

                    "watchdog_alarm":
                        True,

                    "low_battery_alarm":
                        low_battery_alarm,

                    "timeout":
                        watchdog_config["timeout"],

                    "last_successful_read_seconds_ago":
                        round(elapsed, 1),

                    "timestamp":
                        datetime.now(
                            timezone.utc
                        ).astimezone()
                        .isoformat()
                }


                # Publish watchdog state

                try:

                    mqtt_client.publish(

                        mqtt_config["topic"],

                        json.dumps(
                            watchdog_data,
                            separators=(",", ":")
                        ),

                        qos=1,

                        retain=True
                    )


                    mqtt_client.publish(

                        mqtt_config["status_topic"],

                        "watchdog",

                        qos=1,

                        retain=True
                    )


                except Exception as e:

                    logger.error(
                        "Unable to publish "
                        "watchdog state: %s",
                        e
                    )


                # Execute Python watchdog script

                execute_script(

                    watchdog_config["script"],

                    "watchdog",

                    watchdog_data
                )


            # ==================================================
            # Wait
            # ==================================================

            time.sleep(
                monitor_config[
                    "update_interval"
                ]
            )


    except KeyboardInterrupt:

        logger.info(
            "Stopping UPS monitor"
        )


    finally:

        try:

            mqtt_client.publish(

                mqtt_config["status_topic"],

                "offline",

                qos=1,

                retain=True
            )

        except Exception:

            pass


        try:

            mqtt_client.loop_stop()

            mqtt_client.disconnect()

        except Exception:

            pass


        try:

            ups.close()

        except Exception:

            pass


    return 0


# ============================================================
# Entry point
# ============================================================

if __name__ == "__main__":

    raise SystemExit(
        main()
    )
