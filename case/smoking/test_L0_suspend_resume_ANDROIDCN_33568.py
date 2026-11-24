# -*- coding:utf-8 -*-
"""
Test case: L0 suspend/resume screen-state validation.

Test Steps:
1. Wake the device before each test and keep it awake during cleanup.
2. For each of three rounds, turn the screen off, capture evidence, and verify the
    reported screen state is off.
3. Wait for the suspend interval, turn the screen on, capture evidence, and verify
    the reported screen state is on before starting the next round.
"""
import os
import unittest
import uiautomator2 as u2
import time
from common.adb_common import save_step_screenshot


# Connect device via ANDROID_SERIAL environment variable
d = u2.connect(os.environ.get('ANDROID_SERIAL'))

SCRIPT_BASENAME = os.path.splitext(os.path.basename(__file__))[0]
SCRIPT_IMG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.realpath(__file__)))), 'img', SCRIPT_BASENAME)
os.makedirs(SCRIPT_IMG_DIR, exist_ok=True)


# CT47: Check SR Function
class Test_SR_Function(unittest.TestCase):
    def setUp(self):
        d.screen_on()

    def tearDown(self):
        d.screen_on()

    def test_L0_suspend_resume(self):
        """
        Test Steps:
        1. Turn the screen off and verify the reported state is off.
        2. Capture the suspended state, wait for the configured interval, and wake it.
        3. Capture the resumed state and verify the reported state is on.
        4. Repeat the complete suspend/resume validation for three rounds.
        """
        for i in range(3):
            step_prefix = f'round{i+1}'
            # Turn screen off.
            d.screen_off()
            time.sleep(1)
            status = d.info.get('screenOn')
            save_step_screenshot(d, f'{step_prefix}_screen_off', SCRIPT_IMG_DIR)
            self.assertFalse(status, f'Round {i+1}: failed to turn screen off')

            # Turn screen on.
            time.sleep(10)
            d.screen_on()
            time.sleep(1)
            status = d.info.get('screenOn')
            save_step_screenshot(d, f'{step_prefix}_screen_on', SCRIPT_IMG_DIR)
            self.assertTrue(status, f'Round {i+1}: failed to turn screen on')