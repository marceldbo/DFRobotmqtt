#!/usr/bin/env python3

"""
UPS watchdog action script.

This script is called by dfrobot_ups_mqtt.py when the UPS
watchdog times out.

Sequence:

1. Read the watchdog information passed by the UPS monitor.
2. Send the configured Pushover watchdog notification.
3. Exit.

The watchdog script does NOT shut down the Raspberry Pi.

Arguments:
    argv[1] = reason
    argv[2] = JSON encoded watchdog data
"""

import sys
import json
import logging
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


# ============================================================
# Logging
# ============================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)

logger = logging.getLogger("ups-watchdog")


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
# Send Pushover notification
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
    # Watchdog notification configuration
    # --------------------------------------------------------

    notification = pushover.get(
        "watchdog",
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


    # --------------------------------------------------------
    # Send notification
    # --------------------------------------------------------

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
            "Watchdog Pushover notification sent"
        )

        return True


    except Exception as e:

        logger.error(
            "Unable to send Pushover notification: %s",
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
                "Unable to decode watchdog data"
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
    # Log watchdog information
    # --------------------------------------------------------

    logger.error(
        "UPS WATCHDOG TIMEOUT: "
        "no successful UPS reading for %s seconds",

        data.get(
            "last_successful_read_seconds_ago",
            "unknown"
        )
    )


    # --------------------------------------------------------
    # Send Pushover notification
    # --------------------------------------------------------

    if not send_pushover(
        config
    ):

        logger.error(
            "Failed to send watchdog "
            "Pushover notification"
        )


    # --------------------------------------------------------
    # Exit
    # --------------------------------------------------------

    return 0


# ============================================================
# Entry point
# ============================================================

if __name__ == "__main__":

    raise SystemExit(
        main()
    )
