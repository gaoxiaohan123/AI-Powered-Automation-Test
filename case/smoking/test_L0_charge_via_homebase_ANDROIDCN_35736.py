# __author__ = 'H339143'
# -*- coding:utf-8 -*-

"""
L0 charge via homebase verification test.

Goal:
Verify the phone is currently charging.

Steps:
1. Ensure device is awake and on home screen.
2. Read battery status from `adb shell dumpsys battery`.
3. Assert battery status is charging.
"""

import os
import sys
import time
import unittest

import uiautomator2 as u2

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from common.adb_common import get_device_serial, run_adb_cmd, save_step_screenshot

serial = get_device_serial()
if not serial:
    print("Error: No Android device found. Connect a device or set ANDROID_SERIAL.")
    sys.exit(1)

d = u2.connect(serial)

SCRIPT_BASENAME = os.path.splitext(os.path.basename(__file__))[0]
SCRIPT_IMG_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.realpath(__file__)))),
    "img",
    SCRIPT_BASENAME,
)
os.makedirs(SCRIPT_IMG_DIR, exist_ok=True)

_BATTERY_STATUS_MAP = {
    1: "Unknown",
    2: "Charging",
    3: "Discharging",
    4: "Not charging",
    5: "Full",
}


def _adb_shell(command):
    """Run adb shell command and return text output."""
    output = run_adb_cmd(serial, f"shell {command}", log_print=False)
    if isinstance(output, bytes):
        return output.decode("utf-8", errors="ignore")
    return str(output)


def _parse_battery_info(raw_text):
    """Parse key fields from dumpsys battery output."""
    info = {
        "status_code": None,
        "status_text": "Unknown",
        "ac_powered": False,
        "usb_powered": False,
        "wireless_powered": False,
        "dock_powered": False,
    }

    for line in raw_text.splitlines():
        text = line.strip()
        if text.startswith("status:"):
            try:
                code = int(text.split(":", 1)[1].strip())
                info["status_code"] = code
                info["status_text"] = _BATTERY_STATUS_MAP.get(code, f"Code({code})")
            except Exception:
                pass
        elif text.startswith("AC powered:"):
            info["ac_powered"] = text.endswith("true")
        elif text.startswith("USB powered:"):
            info["usb_powered"] = text.endswith("true")
        elif text.startswith("Wireless powered:"):
            info["wireless_powered"] = text.endswith("true")
        elif text.startswith("Dock powered:"):
            info["dock_powered"] = text.endswith("true")

    return info


def _is_charging(info):
    """Return True when battery status indicates charging behavior."""
    status_code = info.get("status_code")
    powered = any(
        [
            info.get("ac_powered", False),
            info.get("usb_powered", False),
            info.get("wireless_powered", False),
            info.get("dock_powered", False),
        ]
    )

    # status=2 means Charging. status=5 means Full, often with power still connected.
    return status_code == 2 or (status_code == 5 and powered)


class Test_L0_Charge_Via_Homebase(unittest.TestCase):
    """L0 charging check: verify phone is charging."""

    def setUp(self):
        d.screen_on()
        d.press("home")
        time.sleep(1)

    def tearDown(self):
        d.press("home")

    def test_L0_charge_via_homebase(self):
        """
        Test Steps:
        1. Wake the device after it is placed on the Homebase charger.
        2. Read `dumpsys battery` and capture the charging-state evidence.
        3. Verify the battery status reports that the device is charging.
        """
        print("\n[Step 1] Prepare device state", flush=True)
        save_step_screenshot(d, "step1_home", SCRIPT_IMG_DIR)

        print("\n[Step 2] Read battery status", flush=True)
        battery_dump = _adb_shell("dumpsys battery")
        self.assertTrue(battery_dump and battery_dump != "error", "Failed to read battery status from adb")

        info = _parse_battery_info(battery_dump)
        print(
            "[Battery] status={status_text}, AC={ac}, USB={usb}, Wireless={wireless}, Dock={dock}".format(
                status_text=info["status_text"],
                ac=info["ac_powered"],
                usb=info["usb_powered"],
                wireless=info["wireless_powered"],
                dock=info["dock_powered"],
            ),
            flush=True,
        )
        save_step_screenshot(d, "step2_battery_status", SCRIPT_IMG_DIR)

        print("\n[Step 3] Verify charging", flush=True)
        self.assertTrue(
            _is_charging(info),
            "Phone is not charging. Expected Charging/Full(with power), got {}.".format(info["status_text"]),
        )
        print("[PASS] Phone is charging.", flush=True)


if __name__ == "__main__":
    unittest.main(verbosity=2)
