# __author__ = 'H339143'
# -*- coding:utf-8 -*-

"""
L1 Battery Optimizer Profile settings keep after reboot

Verify the Battery Optimizer active profile persists across device reboots.

Steps:
1. Settings -> Honeywell Settings -> Battery Optimizer. Default active profile should be None.
2. Select Energy Saver. Active profile should change to Energy Saver.
3. Reboot device, go to Battery Optimizer. Active profile should still be Energy Saver.
4. Select Custom Profile. Active profile should change to Custom Profile.
5. Reboot device. Active profile should still be Custom Profile.
"""

import os
import sys
import time
import unittest

# Ensure project root is importable when running this script directly
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.realpath(__file__)))))

import uiautomator2 as u2

from common.adb_common import (
    get_device_serial,
    adb_shell,
    reboot_run_adb,
    reboot_run_adb_shell,
    reboot_wait_device_success,
)
from common.common_method import (
    battery_optimizer_open,
    battery_optimizer_read_active_profile,
    battery_optimizer_reset_apps,
    battery_optimizer_restore_none,
    battery_optimizer_select_profile,
    screenshot as save_screenshot,
)

# Connect device via ANDROID_SERIAL environment variable
serial = get_device_serial()
d = u2.connect(serial)

_PKG_HW_SETTINGS = 'com.honeywell.settings'
_PKG_BATTERY_MAXIMIZER = 'com.honeywell.batterymaximizer'

_ACTIVE_PROFILE_VALUE_ID = f'{_PKG_BATTERY_MAXIMIZER}:id/textView_active_profile_value'

# The profile list shows the full name, but the main screen's "Active Profile" value
# abbreviates "Custom Profile" to "Custom".
_PROFILE_DISPLAY_NAME = {
    'None': 'None',
    'Energy Saver': 'Energy Saver',
    'Custom Profile': 'Custom',
}


def _force_stop_apps():
    """Force-stop Honeywell Settings and Battery Optimizer to reset to a clean state."""
    battery_optimizer_reset_apps(serial)


def _open_honeywell_settings():
    """Start Honeywell Settings with the same activity launch pattern used by the stable suite."""
    adb_shell(serial, 'am', 'force-stop', _PKG_HW_SETTINGS, timeout=8)
    time.sleep(0.5)
    adb_shell(serial, 'am', 'start', '--activity-clear-task', '-n', f'{_PKG_HW_SETTINGS}/.MainActivity', timeout=10)
    time.sleep(1.5)


def _open_battery_optimizer():
    """Open Honeywell Settings -> Battery Optimizer using the known-good navigation wrapper."""
    return battery_optimizer_open(d, serial)


def _read_active_profile():
    """Read the 'Active Profile' value text on the Battery Optimizer main screen."""
    for _ in range(10):
        value = battery_optimizer_read_active_profile(d)
        if value is not None and value != '':
            return value
        time.sleep(0.5)
    return None


def _select_profile(profile_name):
    """Open the profile list, pick profile_name and apply it, then return to the main screen."""
    return battery_optimizer_select_profile(d, profile_name)


def _restore_default_profile():
    """Restore the Battery Optimizer active profile to its default value."""
    return battery_optimizer_restore_none(d, serial)


def _reconnect_uiautomator(max_retries=3, delay_sec=2):
    """Reconnect uiautomator after a reboot with a few retries for flaky device recovery."""
    global d
    last_error = None
    for attempt in range(1, max_retries + 1):
        try:
            d = u2.connect(serial)
            d.screen_on()
            d.press('home')
            time.sleep(1)
            return True
        except Exception as exc:  # pragma: no cover - device recovery path
            last_error = exc
            print(f'[reboot] u2 reconnect attempt {attempt}/{max_retries} failed: {exc}', flush=True)
            if attempt < max_retries:
                time.sleep(delay_sec)
    print(f'[reboot] u2 reconnect failed after {max_retries} attempts: {last_error}', flush=True)
    return False


def _reboot_and_wait(retries=3):
    """Reboot the device and wait until it fully boots back up, with retry support for flaky recovery."""
    last_error = None
    for attempt in range(1, retries + 1):
        try:
            print(f'\n[reboot] attempt {attempt}/{retries}: reboot and wait for device recovery', flush=True)
            old_boot_id = reboot_run_adb_shell(serial, 'cat /proc/sys/kernel/random/boot_id', timeout=8)
            reboot_run_adb(serial, ['reboot'], timeout=15)
            boot_ok = reboot_wait_device_success(serial, old_boot_id, timeout_sec=240)
            if not boot_ok:
                print(f'[reboot] boot check failed on attempt {attempt}/{retries}', flush=True)
                time.sleep(2)
                continue
            if _reconnect_uiautomator(max_retries=3, delay_sec=2):
                return True
        except Exception as exc:  # pragma: no cover - device recovery path
            last_error = exc
            print(f'[reboot] reboot/reconnect exception on attempt {attempt}/{retries}: {exc}', flush=True)
            time.sleep(2)
    print(f'[reboot] final reboot recovery failed after {retries} attempts: {last_error}', flush=True)
    return False


class TestL1BatteryOptimizerProfilePersistAfterReboot(unittest.TestCase):
    """L1: Battery Optimizer profile setting should persist after device reboot."""

    def setUp(self):
        d.screen_on()
        d.press('home')
        _force_stop_apps()
        time.sleep(1)

    def tearDown(self):
        try:
            if not _restore_default_profile():
                print('[Cleanup] Unable to restore Battery Optimizer profile to None', flush=True)
        finally:
            _force_stop_apps()
            d.press('home')

    def test_L1_battery_optimizer_profile_keep_after_reboot(self):
        """Steps 1-5: switch profiles and verify persistence across reboots."""
        # Step 1: Settings -> Honeywell Settings -> Battery Optimizer, default profile should be None
        print('\n[Step 1] Open Battery Optimizer and check default profile', flush=True)
        opened = _open_battery_optimizer()
        self.assertTrue(opened, 'Step 1 FAIL: unable to enter Battery Optimizer')
        # Reset to None first so the default-state assertion is meaningful and repeatable.
        active = _read_active_profile()
        if active != 'None':
            self.assertTrue(_select_profile('None'), 'Step 1 FAIL: unable to reset profile to None')
            active = _read_active_profile()
        save_screenshot(d, __file__, 'step1_default_profile_none')
        self.assertEqual(active, 'None', f"Step 1 FAIL: default active profile = '{active}', expected 'None'")
        print('[Step 1] PASS - default active profile = None', flush=True)

        # Step 2: Select Energy Saver
        print('\n[Step 2] Select Energy Saver profile', flush=True)
        self.assertTrue(_select_profile('Energy Saver'), 'Step 2 FAIL: unable to select Energy Saver')
        active = _read_active_profile()
        save_screenshot(d, __file__, 'step2_active_profile_energy_saver')
        expected = _PROFILE_DISPLAY_NAME['Energy Saver']
        self.assertEqual(active, expected, f"Step 2 FAIL: active profile = '{active}', expected '{expected}'")
        print(f'[Step 2] PASS - active profile = {active}', flush=True)

        # Step 3: Reboot, then verify the profile is still Energy Saver
        print('\n[Step 3] Reboot device and verify profile is kept', flush=True)
        self.assertTrue(_reboot_and_wait(), 'Step 3 FAIL: device did not come back online after reboot')
        opened = _open_battery_optimizer()
        self.assertTrue(opened, 'Step 3 FAIL: unable to enter Battery Optimizer after reboot')
        active = _read_active_profile()
        save_screenshot(d, __file__, 'step3_active_profile_after_reboot')
        self.assertEqual(active, expected, f"Step 3 FAIL: active profile after reboot = '{active}', expected '{expected}'")
        print(f'[Step 3] PASS - active profile after reboot = {active}', flush=True)

        # Step 4: Select Custom Profile
        print('\n[Step 4] Select Custom Profile', flush=True)
        self.assertTrue(_select_profile('Custom Profile'), 'Step 4 FAIL: unable to select Custom Profile')
        active = _read_active_profile()
        save_screenshot(d, __file__, 'step4_active_profile_custom')
        expected = _PROFILE_DISPLAY_NAME['Custom Profile']
        self.assertEqual(active, expected, f"Step 4 FAIL: active profile = '{active}', expected '{expected}'")
        print(f'[Step 4] PASS - active profile = {active}', flush=True)

        # Step 5: Reboot, then verify the profile is still Custom Profile
        print('\n[Step 5] Reboot device and verify profile is kept', flush=True)
        self.assertTrue(_reboot_and_wait(), 'Step 5 FAIL: device did not come back online after reboot')
        opened = _open_battery_optimizer()
        self.assertTrue(opened, 'Step 5 FAIL: unable to enter Battery Optimizer after reboot')
        active = _read_active_profile()
        save_screenshot(d, __file__, 'step5_active_profile_after_reboot')
        self.assertEqual(active, expected, f"Step 5 FAIL: active profile after reboot = '{active}', expected '{expected}'")
        print(f'[Step 5] PASS - active profile after reboot = {active}', flush=True)


if __name__ == '__main__':
    unittest.main(verbosity=2)
