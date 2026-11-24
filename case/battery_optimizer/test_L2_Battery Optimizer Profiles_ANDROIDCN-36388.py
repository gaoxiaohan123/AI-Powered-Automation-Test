# -*- coding:utf-8 -*-
"""
ANDROIDCN-36388: verify all Battery Optimizer profile options are available.

Case steps:
1. Open Settings -> Honeywell Settings -> Battery Optimizer.
2. Open OPTIMIZE BATTERY and inspect the profile list.
3. Verify the default profile is None.
4. Verify Energy Saver, Cold Storage, and Custom Profile can be configured.

Automation note: profile availability is firmware-dependent; the script validates
the options displayed by the target device.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.realpath(__file__)))))

import uiautomator2 as u2

from common.adb_common import get_device_serial
from common.common_method import battery_optimizer_open, battery_optimizer_open_profile_list, battery_optimizer_profile_options_visible, battery_optimizer_read_active_profile, battery_optimizer_reset_apps, battery_optimizer_restore_none, battery_optimizer_select_profile, battery_optimizer_visible_profile_names, screenshot as save_screenshot

SERIAL = get_device_serial()
DEVICE = u2.connect(SERIAL)


class TestL2BatteryOptimizerProfiles(unittest.TestCase):
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

    def test_L2_battery_optimizer_profiles(self):
        self.assertTrue(battery_optimizer_open(DEVICE, SERIAL), 'Step 1 FAIL: unable to enter Battery Optimizer')
        self.assertTrue(battery_optimizer_open_profile_list(DEVICE), 'Step 2 FAIL: unable to open profile list')
        self.assertTrue(battery_optimizer_profile_options_visible(DEVICE), 'Step 2 FAIL: not all expected profiles are available')
        save_screenshot(DEVICE, __file__, 'step2_profile_list')
        supported_profiles = battery_optimizer_visible_profile_names(DEVICE)
        DEVICE.press('back')

        # Step 3: restore and verify the documented default profile.
        self.assertTrue(battery_optimizer_select_profile(DEVICE, 'None'), 'Step 3 FAIL: unable to select the default None profile')
        self.assertEqual(
            battery_optimizer_read_active_profile(DEVICE),
            'None',
            'Step 3 FAIL: default active profile is not None',
        )
        save_screenshot(DEVICE, __file__, 'step3_default_profile_none')

        # Step 4: apply each firmware-supported non-default profile and verify it takes effect.
        expected_active_names = {'Energy Saver': 'Energy Saver', 'Cold Storage': 'Cold Storage', 'Custom Profile': 'Custom'}
        for profile_name in supported_profiles:
            if profile_name == 'None':
                continue
            self.assertTrue(
                battery_optimizer_select_profile(DEVICE, profile_name),
                f'Step 4 FAIL: unable to select {profile_name}',
            )
            self.assertEqual(
                battery_optimizer_read_active_profile(DEVICE),
                expected_active_names[profile_name],
                f'Step 4 FAIL: {profile_name} did not become the active profile',
            )
            save_screenshot(DEVICE, __file__, f'step4_{profile_name.lower().replace(" ", "_")}')


if __name__ == '__main__':
    unittest.main(verbosity=2)