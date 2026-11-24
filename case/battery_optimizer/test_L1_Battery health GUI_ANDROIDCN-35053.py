# -*- coding:utf-8 -*-
"""
ANDROIDCN-35053: verify the Battery Health UI and value are displayed.

Case steps:
1. Open Settings -> Honeywell Settings -> Battery Optimizer.
2. Open Overall Health.
3. Verify the battery health percentage displays normally.
"""

import os
import re
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.realpath(__file__)))))

import uiautomator2 as u2

from common.adb_common import get_device_serial
from common.common_method import battery_optimizer_open, battery_optimizer_open_entry, battery_optimizer_reset_apps, battery_optimizer_restore_none, screenshot as save_screenshot

SERIAL = get_device_serial()
DEVICE = u2.connect(SERIAL)


class TestL1BatteryHealthGui(unittest.TestCase):
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

    def test_L1_battery_health_gui(self):
        self.assertTrue(battery_optimizer_open(DEVICE, SERIAL), 'Step 1 FAIL: unable to enter Battery Optimizer')
        self.assertTrue(battery_optimizer_open_entry(DEVICE, ('Overall Health', 'Overall health')), 'Step 2 FAIL: unable to open Overall Health')
        hierarchy = DEVICE.dump_hierarchy()
        save_screenshot(DEVICE, __file__, 'step2_overall_health')
        self.assertRegex(hierarchy, re.compile(r'\d+\s*%'), 'Step 2 FAIL: battery health percentage not displayed')


if __name__ == '__main__':
    unittest.main(verbosity=2)