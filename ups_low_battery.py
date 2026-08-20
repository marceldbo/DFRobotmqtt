#!/usr/bin/env python3

"""
UPS low-battery action script.

Sequence:

1. Read the UPS information passed by the UPS monitor.
2. Send the configured Pushover notification.
3. Check for and stop Domoticz gracefully if it is running.
4. Wait the configured shutdown delay.
5. Shut down the Raspberry Pi.

If Domoticz is not installed, cannot be found, or is not running,
the Raspberry Pi will still continue to shut down.

Arguments:
argv[1] = reason
argv[2] = JSON encoded UPS data
"""

import sys
import json
import time
import logging
import subprocess
from pathlib import Path
from urllib import request
from urllib.parse import urlencode

import yaml


# ============================================================
# Configuration
# ============================================================

CONFIG_FILE = (
    Path(__file__).resolve().parent / "config.yaml"
)

DOMOTICZ_SERVICE = "domoticz"

SYSTEMCTL_TIMEOUT = 10
DOMOTICZ_STOP_TIMEOUT = 30


# ============================================================
# Logging
# ============================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)

logger = logging.getLogger("ups-low-battery")


# ============================================================
# Load configuration
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
# Pushover
# ============================================================

def send_pushover(config):

    pushover = config.get(
        "pushover",
        {}
    )

    # --------------------------------------------------------
    # Check whether Pushover is enabled
    # --------------------------------------------------------

    if not pushover.get(
        "enabled",
        False
    ):

        logger.info(
            "Pushover notifications disabled"
        )

        return True

    # --------------------------------------------------------
    # Pushover credentials
    # --------------------------------------------------------

    token = pushover.get(
        "token",
        ""
    )

    user = pushover.get(
        "user",
        ""
    )

    # --------------------------------------------------------
    # Low-battery notification configuration
    # --------------------------------------------------------

    notification = pushover.get(
        "low_battery",
        {}
    )

    title = notification.get(
        "title",
        ""
    )

    message = notification.get(
        "message",
        ""
    )

    priority = notification.get(
        "priority",
        0
    )

    # --------------------------------------------------------
    # Validate configuration
    # --------------------------------------------------------

    if not token or not user:

        logger.error(
            "Pushover token or user is missing"
        )

        return False

    if not title or not message:

        logger.error(
            "Pushover title or message is missing"
        )

        return False

    # --------------------------------------------------------
    # Create request
    # --------------------------------------------------------

    payload = urlencode({

        "token": token,

        "user": user,

        "title": title,

        "message": message,

        "priority": priority

    }).encode("utf-8")

    try:

        req = request.Request(

            "https://api.pushover.net/1/messages.json",

            data=payload,

            method="POST"
        )

        with request.urlopen(
            req,
            timeout=15
        ) as response:

            response.read()

        logger.info(
            "Low-battery Pushover notification sent"
        )

        return True

    except Exception as e:

        logger.error(
            "Unable to send Pushover notification: %s",
            e
        )

        return False


# ============================================================
# Check Domoticz service
# ============================================================

def domoticz_exists():

    """
    Check whether the Domoticz systemd service exists.

    Returns:
        True  = service exists
        False = service does not exist or systemctl failed
    """

    try:

        result = subprocess.run(

            [
                "systemctl",
                "cat",
                DOMOTICZ_SERVICE
            ],

            check=False,

            stdout=subprocess.PIPE,

            stderr=subprocess.PIPE,

            text=True,

            timeout=SYSTEMCTL_TIMEOUT
        )

        if result.returncode == 0:

            logger.info(
                "Domoticz service found"
            )

            return True

        logger.warning(
            "Domoticz service not found"
        )

        if result.stderr:

            logger.warning(
                "systemctl: %s",
                result.stderr.strip()
            )

        return False

    except subprocess.TimeoutExpired:

        logger.warning(
            "Timeout while checking for Domoticz service"
        )

        return False

    except Exception as e:

        logger.warning(
            "Unable to check for Domoticz service: %s",
            e
        )

        return False


# ============================================================
# Check whether Domoticz is running
# ============================================================

def domoticz_running():

    """
    Check whether the Domoticz service is currently active.

    Returns:
        True  = Domoticz is running
        False = Domoticz is not running
    """

    try:

        result = subprocess.run(

            [
                "systemctl",
                "is-active",
                "--quiet",
                DOMOTICZ_SERVICE
            ],

            check=False,

            timeout=SYSTEMCTL_TIMEOUT
        )

        if result.returncode == 0:

            logger.info(
                "Domoticz is running"
            )

            return True

        logger.info(
            "Domoticz is not running"
        )

        return False

    except subprocess.TimeoutExpired:

        logger.warning(
            "Timeout while checking Domoticz status"
        )

        return False

    except Exception as e:

        logger.warning(
            "Unable to determine Domoticz status: %s",
            e
        )

        return False


# ============================================================
# Stop Domoticz
# ============================================================

def stop_domoticz():

    """
    Stop Domoticz if it exists and is running.

    Failure to find or stop Domoticz does NOT prevent
    the Raspberry Pi from shutting down.
    """

    logger.warning(
        "Checking Domoticz service"
    )

    # --------------------------------------------------------
    # Does the service exist?
    # --------------------------------------------------------

    if not domoticz_exists():

        logger.warning(
            "Domoticz service is not installed/found"
        )

        logger.warning(
            "Continuing with Raspberry Pi shutdown"
        )

        return True

    # --------------------------------------------------------
    # Is Domoticz running?
    # --------------------------------------------------------

    if not domoticz_running():

        logger.info(
            "Domoticz is not running"
        )

        logger.info(
            "No Domoticz shutdown required"
        )

        return True

    # --------------------------------------------------------
    # Stop Domoticz
    # --------------------------------------------------------

    logger.warning(
        "Stopping Domoticz service: %s",
        DOMOTICZ_SERVICE
    )

    try:

        result = subprocess.run(

            [
                "systemctl",
                "stop",
                DOMOTICZ_SERVICE
            ],

            check=False,

            stdout=subprocess.PIPE,

            stderr=subprocess.PIPE,

            text=True,

            timeout=SYSTEMCTL_TIMEOUT
        )

        if result.returncode != 0:

            logger.error(
                "Unable to stop Domoticz "
                "(return code %s)",
                result.returncode
            )

            if result.stderr:

                logger.error(
                    "systemctl error: %s",
                    result.stderr.strip()
                )

            logger.warning(
                "Continuing with Raspberry Pi shutdown"
            )

            return True

    except subprocess.TimeoutExpired:

        logger.error(
            "Timeout while stopping Domoticz"
        )

        logger.warning(
            "Continuing with Raspberry Pi shutdown"
        )

        return True

    except Exception as e:

        logger.error(
            "Error stopping Domoticz: %s",
            e
        )

        logger.warning(
            "Continuing with Raspberry Pi shutdown"
        )

        return True

    # --------------------------------------------------------
    # Wait until Domoticz has actually stopped
    # --------------------------------------------------------

    logger.info(
        "Waiting for Domoticz to stop"
    )

    for _ in range(DOMOTICZ_STOP_TIMEOUT):

        try:

            result = subprocess.run(

                [
                    "systemctl",
                    "is-active",
                    "--quiet",
                    DOMOTICZ_SERVICE
                ],

                check=False,

                timeout=SYSTEMCTL_TIMEOUT
            )

            if result.returncode != 0:

                logger.info(
                    "Domoticz has stopped"
                )

                return True

        except subprocess.TimeoutExpired:

            logger.warning(
                "Timeout checking Domoticz status"
            )

            break

        except Exception as e:

            logger.warning(
                "Error checking Domoticz status: %s",
                e
            )

            break

        time.sleep(1)

    # --------------------------------------------------------
    # Do not block shutdown if Domoticz refuses to stop
    # --------------------------------------------------------

    logger.warning(
        "Domoticz did not stop within %d seconds",
        DOMOTICZ_STOP_TIMEOUT
    )

    logger.warning(
        "Continuing with Raspberry Pi shutdown"
    )

    return True


# ============================================================
# Shutdown
# ============================================================

def shutdown_system():

    logger.warning(
        "Shutting down Raspberry Pi"
    )

    try:

        result = subprocess.run(

            [
                "sudo",
                "shutdown",
                "-h",
                "now"
            ],

            check=False,

            stdout=subprocess.PIPE,

            stderr=subprocess.PIPE,

            text=True,

            timeout=10
        )

        if result.returncode != 0:

            logger.error(
                "Shutdown command returned %s",
                result.returncode
            )

            if result.stderr:

                logger.error(
                    "shutdown error: %s",
                    result.stderr.strip()
                )

            return False

        return True

    except subprocess.TimeoutExpired:

        # The shutdown command may actually have succeeded
        # and the process can disappear as the system shuts down.

        logger.warning(
            "Shutdown command timed out; "
            "the system may already be shutting down"
        )

        return True

    except Exception as e:

        logger.error(
            "Unable to shut down Raspberry Pi: %s",
            e
        )

        return False


# ============================================================
# Main
# ============================================================

def main():

    # --------------------------------------------------------
    # Read arguments
    # --------------------------------------------------------

    reason = (
        sys.argv[1]
        if len(sys.argv) > 1
        else "unknown"
    )

    data = {}

    if len(sys.argv) > 2:

        try:

            data = json.loads(
                sys.argv[2]
            )

        except json.JSONDecodeError:

            logger.error(
                "Unable to decode UPS data"
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

        # Configuration is unavailable, but this is a
        # low-battery emergency. Do not leave the Pi running.

        logger.warning(
            "Configuration unavailable - "
            "continuing with Raspberry Pi shutdown"
        )

        shutdown_system()

        return 1

    # --------------------------------------------------------
    # Get shutdown delay
    # --------------------------------------------------------

    shutdown_delay = config.get(
        "low_battery",
        {}
    ).get(
        "shutdown_delay",
        180
    )

    # --------------------------------------------------------
    # Log UPS information
    # --------------------------------------------------------

    logger.warning(
        "UPS LOW BATTERY: "
        "reason=%s, "
        "battery=%s%%, "
        "voltage=%s V, "
        "threshold=%s%%",

        reason,

        data.get(
            "battery",
            "unknown"
        ),

        data.get(
            "voltage",
            "unknown"
        ),

        data.get(
            "threshold",
            "unknown"
        )
    )

    # --------------------------------------------------------
    # Send Pushover notification
    # --------------------------------------------------------

    send_pushover(
        config
    )

    # --------------------------------------------------------
    # Stop Domoticz
    # --------------------------------------------------------

    stop_domoticz()

    # --------------------------------------------------------
    # Wait
    # --------------------------------------------------------

    logger.warning(
        "Waiting %d seconds before "
        "shutting down Raspberry Pi",

        shutdown_delay
    )

    time.sleep(
        shutdown_delay
    )

    # --------------------------------------------------------
    # Shutdown Raspberry Pi
    # --------------------------------------------------------

    shutdown_system()

    return 0


# ============================================================
# Entry point
# ============================================================

if __name__ == "__main__":

    raise SystemExit(
        main()
    )
