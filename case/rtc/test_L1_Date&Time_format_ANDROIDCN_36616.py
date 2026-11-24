# __author__Sophy = 'H400818'_20260724
# -*- coding:utf-8 -*-

"""
Date & Time format validation.

Test Steps:
1. Go to Settings -> Date & time and enable 24-hour format.
2. Read current system time and verify it is in 24-hour format.
3. Go to Settings -> Date & time and disable 24-hour format.
4. Read current system time and verify it is in 12-hour format.

备注: Created by H400818 on 2026-07-24
"""

import os
import re
import sys
import time
import unittest
import uiautomator2 as u2

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from common.common_method import (
    rtc_get_device_time_format,
    rtc_read_system_time_text,
    rtc_set_use_24_hour_format,
)
from common.adb_common import force_stop_Settings_app, save_step_screenshot


def _get_serial_or_fail():
    serial = os.environ.get('ANDROID_SERIAL')
    if not serial:
        raise AssertionError('ANDROID_SERIAL is not set. Please export ANDROID_SERIAL first.')
    return serial


def _connect_u2_with_retry(serial, retries=3, wait_seconds=2):
    last_error = None
    for i in range(retries):
        try:
            return u2.connect(serial)
        except Exception as e:
            last_error = e
            print(f'[setup] u2 connect attempt {i + 1}/{retries} failed: {e}')
            time.sleep(wait_seconds)
    raise AssertionError(f'Failed to connect uiautomator2 after {retries} attempts: {last_error}')


SCRIPT_BASENAME = os.path.splitext(os.path.basename(__file__))[0]
IMG_ROOT = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.realpath(__file__)))), 'img')
SCRIPT_IMG_DIR = os.path.join(IMG_ROOT, SCRIPT_BASENAME)
os.makedirs(SCRIPT_IMG_DIR, exist_ok=True)


class TestDateTimeFormat(unittest.TestCase):
    """Validate current 12-hour display and switching to 24-hour format."""

    def setUp(self):
        self.serial = _get_serial_or_fail()
        self.device = _connect_u2_with_retry(self.serial)
        
    def tearDown(self):
        """Cleanup after each test"""
        print("="*60)
       # Close Settings app 
        force_stop_Settings_app(self.serial, 'com.android.settings')
        self.device.press('home')
        print("[tearDown] Cleanup completed")

    @staticmethod
    def _is_12_hour_text(value):
        if not value:
            return False
        # Accept both English and Chinese meridiem markers.
        if re.search(r'(?i)(AM|PM)', value):
            return True
        if '上午' in value or '下午' in value:
            return True
        # Some Android shells return 12-hour clock without AM/PM marker.
        if re.match(r'^(0?[1-9]|1[0-2]):[0-5]\d$', value):
            return True
        return False

    @staticmethod
    def _is_24_hour_text(value):
        if not value:
            return False
        if re.search(r'(?i)\b(AM|PM)\b', value):
            return False
        return re.match(r'^([01]\d|2[0-3]):[0-5]\d$', value) is not None

    @staticmethod
    def _display_with_am_pm(value):
        """Return a display-friendly time string with AM/PM suffix when missing."""
        if not value:
            return value
        if re.search(r'(?i)\b(AM|PM)\b', value) or '上午' in value or '下午' in value:
            return value
        m = re.match(r'^([01]\d|2[0-3]):([0-5]\d)$', value)
        if not m:
            return value
        hour = int(m.group(1))
        meridiem = 'AM' if hour < 12 else 'PM'
        return f'{value} {meridiem}'

    def test_L1_date_time_format_androidcn_36616(self):
        """
        Date & Time format validation.
        Test Steps:
        1. Go to Settings -> Date & time and enable 24-hour format.
        2. Read current system time and verify it is in 24-hour format.
        3. Go to Settings -> Date & time and disable 24-hour format.
        4. Read current system time and verify it is in 12-hour format.
        """
        print('\n========== Date & Time format test ==========' )
        print(f'Device: {self.serial}')

        # Step 1: Check current Date & time format status.
        current_format = rtc_get_device_time_format(self.serial)
        print(f'[Step1] Current format before actions: {current_format}')

        # If currently disabled (12-hour), enable it first.
        if current_format != '24':
            enabled = rtc_set_use_24_hour_format(self.device, self.serial, enable=True)
            self.assertTrue(enabled, 'Failed to enable 24-hour format in Date & time settings.')
            save_step_screenshot(self.device, 'step1_24_hour_format_enabled', SCRIPT_IMG_DIR)
            print('[Step1] 24-hour format enabled')
        else:
            print('[Step1] 24-hour format already enabled')

        # Step 2: Read current system time and verify 24-hour format.
        after_enable_format = rtc_get_device_time_format(self.serial)
        self.assertEqual(after_enable_format, '24', f'Expected 24-hour format after enabling, got: {after_enable_format}')

        time_24 = rtc_read_system_time_text(self.serial, hour_format='auto')
        print(f'[Step2] Current system time text after enable: {self._display_with_am_pm(time_24)}')
        self.assertTrue(self._is_24_hour_text(time_24), f'Current time is not 24-hour text after enabling: {time_24}')

        # Step 3: Go to settings and disable 24-hour format.
        disabled = rtc_set_use_24_hour_format(self.device, self.serial, enable=False)
        self.assertTrue(disabled, 'Failed to disable 24-hour format in Date & time settings.')
        save_step_screenshot(self.device, 'step3_24_hour_format_disabled', SCRIPT_IMG_DIR)
        print('[Step3] 24-hour format disabled')

        # Step 4: Read current system time and verify 12-hour format.
        after_disable_format = rtc_get_device_time_format(self.serial)
        self.assertEqual(after_disable_format, '12', f'Expected 12-hour format after disabling, got: {after_disable_format}')

        time_12 = rtc_read_system_time_text(self.serial, hour_format='auto')
        print(f'[Step4] Current system time text after disable: {time_12}')
        self.assertTrue(self._is_12_hour_text(time_12), f'Current time is not 12-hour text after disabling: {time_12}')


if __name__ == '__main__':
    unittest.main(verbosity=2)
