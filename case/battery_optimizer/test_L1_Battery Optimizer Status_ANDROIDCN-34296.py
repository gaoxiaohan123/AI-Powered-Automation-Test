# -*- coding:utf-8 -*-
"""
ANDROIDCN-34296: verify the Battery Optimizer Status page is available.

Case steps:
1. Open Settings -> Honeywell Settings -> Battery Optimizer.
2. Open the Status entry.
3. Verify the Status page displays normally.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.realpath(__file__)))))

import uiautomator2 as u2

from common.adb_common import get_device_serial
from common.common_method import battery_optimizer_open, battery_optimizer_open_entry, battery_optimizer_reset_apps, battery_optimizer_restore_none, screenshot as save_screenshot

SERIAL = get_device_serial()
DEVICE = u2.connect(SERIAL)


class TestL1BatteryOptimizerStatus(unittest.TestCase):
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

    def test_L1_battery_optimizer_status(self):
        self.assertTrue(battery_optimizer_open(DEVICE, SERIAL), 'Step 1 FAIL: unable to enter Battery Optimizer')
        self.assertTrue(battery_optimizer_open_entry(DEVICE, ('Status', 'STATUS', 'status')), 'Step 2 FAIL: unable to open Status')
        save_screenshot(DEVICE, __file__, 'step2_status')
        self.assertTrue(DEVICE.dump_hierarchy(), 'Step 2 FAIL: Status page hierarchy is empty')


if __name__ == '__main__':
    unittest.main(verbosity=2)