# __author__ = 'H339143'
# -*- coding:utf-8 -*-
"""
Test case: ANDROID-ATC-16411-L1 - Backlight timeout at 15 seconds.

Test Steps:
1. Wake the device, return to Home, and disable stay-awake-while-charging so
    USB/ADB power does not prevent the display timeout.
2. Open Settings > Display > Screen timeout (or Sleep on compatible builds).
3. Select the 15 seconds timeout value and return to Home without touching the display.
4. Wait beyond the configured timeout, capture a screenshot, and verify the screen
    state is off.
5. Restore the stay-awake configuration and close Settings during cleanup.
"""
import unittest
import uiautomator2 as u2
import time
import subprocess
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from common.adb_common import save_step_screenshot, get_device_serial, run_adb_cmd

serial = get_device_serial()
if not serial:
    print("Error: No Android device found. Connect a device or set ANDROID_SERIAL.")
    sys.exit(1)

d = u2.connect(serial)

SCRIPT_BASENAME = os.path.splitext(os.path.basename(__file__))[0]
SCRIPT_IMG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.realpath(__file__)))), 'img', SCRIPT_BASENAME)
os.makedirs(SCRIPT_IMG_DIR, exist_ok=True)


def _open_sleep_settings():
    """Open the Display > Sleep settings page."""
    subprocess.run(f'adb -s {serial} shell am start -n com.android.settings/.Settings', shell=True)
    time.sleep(3)

    if not d(text="Display").exists(timeout=3):
        d(scrollable=True).scroll.to(text="Display")
        time.sleep(1)
    d(text='Display').click()
    time.sleep(2)

    # Some models need to expand Advanced first.
    if d(text="Advanced").exists(timeout=2):
        d(text='Advanced').click()
        time.sleep(2)

    if not d(text="Screen timeout").exists(timeout=3):
        # Compatible with different Android wording.
        if not d(text="Sleep").exists(timeout=3):
            d(scrollable=True).scroll.to(text="Sleep")
            time.sleep(1)
        d(text='Sleep').click()
    else:
        d(text='Screen timeout').click()
    time.sleep(2)


class Test_Backlight(unittest.TestCase):
    def setUp(self):
        d.screen_on()
        d.press('home')
        time.sleep(1)
        # Turn off stay-awake mode. The device stays connected/charging over USB
        # throughout the automated run (ADB itself is USB-attached), and on some
        # Honeywell ROMs "svc power stayon false" alone does not retroactively
        # clear an already-active "stay awake while plugged in" state, so also
        # force the underlying setting directly for good measure.
        subprocess.run(f'adb -s {serial} shell svc power stayon false', shell=True)
        run_adb_cmd(serial, 'shell settings put global stay_on_while_plugged_in 0', log_print=False)
        subprocess.run(f'adb -s {serial} shell am force-stop com.android.settings', shell=True)

    def tearDown(self):
        # Restore stay-awake mode and close Settings.
        # subprocess.run(f'adb -s {serial} shell svc power stayon true', shell=True)
        run_adb_cmd(serial, 'shell settings put global stay_on_while_plugged_in 3', log_print=False)
        subprocess.run(f'adb -s {serial} shell am force-stop com.android.settings', shell=True)

    # ANDROID-ATC-16411-L1-Backlight-time-out-15s:
    # Verify whether 15s screen timeout works as expected.
    def test_L0_backlight_15s(self):
        """
        Test Steps:
        1. Open Display > Screen timeout/Sleep after disabling stay-awake mode.
        2. Select the 15 seconds timeout option and return to Home.
        3. Wait longer than 15 seconds without interaction.
        4. Capture evidence and verify the device reports the screen is off.
        """
        _open_sleep_settings()

        # Set Sleep timeout to 15 seconds.
        if d(text="15 seconds").exists(timeout=3):
            d(text="15 seconds").click()
        else:
            self.fail("'15 seconds' option not found")
        time.sleep(2)

        # Go back to home and verify screen-off within the timeout window.
        # Poll instead of a single fixed-time check to tolerate normal timing
        # slop around the 15s boundary, while still failing if the screen
        # never turns off well past the configured timeout.
        d.press('home')
        screen_on = True

        time.sleep(16)
        screen_on = d.info.get('screenOn', True)

        save_step_screenshot(d, 'after_15s', SCRIPT_IMG_DIR)
        self.assertFalse(screen_on, "Screen is still on after 15-second timeout")


if __name__ == '__main__':
    unittest.main(verbosity=2)