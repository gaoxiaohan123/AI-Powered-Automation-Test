# -*- coding:utf-8 -*-
"""
ANDROIDCN-35749: verify key Battery Optimizer UI entries are visible.

Case steps:
1. Open Settings -> Honeywell Settings -> Battery Optimizer.
2. Verify Status and App Usage pages open and display normally.
3. Open OPTIMIZE BATTERY and verify the default value and selectable profiles.
4. Verify information for each visible profile displays normally.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.realpath(__file__)))))

import uiautomator2 as u2

from common.adb_common import get_device_serial
from common.common_method import battery_optimizer_open, battery_optimizer_open_entry, battery_optimizer_open_profile_list, battery_optimizer_profile_options_visible, battery_optimizer_reset_apps, battery_optimizer_restore_none, screenshot as save_screenshot

SERIAL = get_device_serial()
DEVICE = u2.connect(SERIAL)


class TestL1UiCheck(unittest.TestCase):
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

    def test_L1_ui_check(self):
        self.assertTrue(battery_optimizer_open(DEVICE, SERIAL), 'Step 1 FAIL: unable to enter Battery Optimizer')
        save_screenshot(DEVICE, __file__, 'step1_battery_optimizer_main')

        self.assertTrue(battery_optimizer_open_entry(DEVICE, ('Status', 'STATUS', 'status')), 'Step 2 FAIL: unable to open Status')
        save_screenshot(DEVICE, __file__, 'step2_status')
        self.assertTrue(battery_optimizer_open(DEVICE, SERIAL), 'Step 2 FAIL: unable to return to Battery Optimizer')
        self.assertTrue(battery_optimizer_open_entry(DEVICE, ('App Usage', 'APP USAGE', 'App usage', 'app usage')), 'Step 2 FAIL: unable to open App Usage')
        save_screenshot(DEVICE, __file__, 'step2_app_usage')
        self.assertTrue(battery_optimizer_open(DEVICE, SERIAL), 'Step 2 FAIL: unable to return to Battery Optimizer')

        self.assertTrue(battery_optimizer_open_profile_list(DEVICE), 'Step 3 FAIL: OPTIMIZE BATTERY cannot be opened')
        self.assertTrue(battery_optimizer_profile_options_visible(DEVICE), 'Step 3 FAIL: expected profile options are not visible')
        save_screenshot(DEVICE, __file__, 'step3_profile_options')


if __name__ == '__main__':
    unittest.main(verbosity=2)