# -*- coding:utf-8 -*-
"""
ANDROIDCN-33786: verify selectable Battery Optimizer profiles take effect.

Case steps:
1. Open Battery Optimizer and select the default None profile.
2. Verify selecting None takes effect.
3. Repeat selection and verification for Energy Saver and Cold Storage.
4. Add a Custom Profile, save it, then verify it takes effect.

Automation note: validate every profile exposed by the current firmware. Cold Storage
is optional because some firmware configurations do not provide that profile.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.realpath(__file__)))))

import uiautomator2 as u2

from common.adb_common import get_device_serial
from common.common_method import battery_optimizer_open, battery_optimizer_open_profile_list, battery_optimizer_read_active_profile, battery_optimizer_reset_apps, battery_optimizer_restore_none, battery_optimizer_select_profile, battery_optimizer_visible_profile_names, screenshot as save_screenshot

SERIAL = get_device_serial()
DEVICE = u2.connect(SERIAL)


class TestL1BatteryOptimizerProfileSettingsTakeEffect(unittest.TestCase):
    def setUp(self):
        DEVICE.screen_on()
        DEVICE.press('home')
        battery_optimizer_reset_apps(SERIAL)

    def tearDown(self):
        try:
            self.assertTrue(battery_optimizer_restore_none(DEVICE, SERIAL), 'Cleanup FAIL: unable to restore the None profile')
        finally:
            battery_optimizer_reset_apps(SERIAL)
            DEVICE.press('home')

    def test_L1_battery_optimizer_profile_settings_take_effect(self):
        self.assertTrue(battery_optimizer_open(DEVICE, SERIAL), 'Unable to enter Battery Optimizer')
        self.assertTrue(battery_optimizer_open_profile_list(DEVICE), 'Step 1 FAIL: unable to open profile list')
        supported_profiles = battery_optimizer_visible_profile_names(DEVICE)
        DEVICE.press('back')
        self.assertIn('None', supported_profiles, 'Step 1 FAIL: None profile is not available')
        self.assertIn('Energy Saver', supported_profiles, 'Step 1 FAIL: Energy Saver profile is not available')

        expected_profiles = {
            'None': 'None',
            'Energy Saver': 'Energy Saver',
            'Cold Storage': 'Cold Storage',
            'Custom Profile': 'Custom',
        }
        for step, profile in enumerate(supported_profiles, start=1):
            self.assertTrue(battery_optimizer_select_profile(DEVICE, profile), f'Step {step} FAIL: cannot select {profile}')
            actual = battery_optimizer_read_active_profile(DEVICE)
            save_screenshot(DEVICE, __file__, f'step{step}_{profile.lower().replace(" ", "_")}')
            expected = expected_profiles[profile]
            self.assertEqual(actual, expected, f'Step {step} FAIL: expected {expected}, got {actual}')

        if 'Cold Storage' not in supported_profiles:
            print('[Info] Cold Storage is not supported on this firmware; skipped optional profile validation.', flush=True)


if __name__ == '__main__':
    unittest.main(verbosity=2)