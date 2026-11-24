# __author__ = 'sophy_H400818'
# -*- coding:utf-8 -*-

"""Validate changing the Android time zone to America/New_York."""
import os
import subprocess
import sys
import time
import unittest

import uiautomator2 as u2

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from common.adb_common import (
	reboot_run_adb_shell,
	reboot_wait_device_success,
	save_step_screenshot,
	force_stop_Settings_app,
)
from common.common_method import (
	rtc_disable_automatic_time_zone,
	rtc_enable_automatic_time_zone,
	rtc_read_system_time_zone,
	rtc_select_New_York_time_zone,
)


SCRIPT_BASENAME = os.path.splitext(os.path.basename(__file__))[0]
SCRIPT_IMG_DIR = os.path.join(
	os.path.dirname(os.path.dirname(os.path.dirname(os.path.realpath(__file__)))),
	'img',
	SCRIPT_BASENAME,
)
os.makedirs(SCRIPT_IMG_DIR, exist_ok=True)


def _get_serial_or_fail():
	serial = os.environ.get('ANDROID_SERIAL')
	if not serial:
		raise AssertionError('ANDROID_SERIAL is not set. Please export ANDROID_SERIAL first.')
	return serial


def _connect_u2_with_retry(serial, retries=3, wait_seconds=2):
	last_error = None
	for attempt in range(retries):
		try:
			return u2.connect(serial)
		except Exception as error:
			last_error = error
			print(f'[setup] u2 connect attempt {attempt + 1}/{retries} failed: {error}')
			time.sleep(wait_seconds)
	raise AssertionError(f'Failed to connect uiautomator2 after {retries} attempts: {last_error}')


class TestTimeZoneModify(unittest.TestCase):
	def setUp(self):
		self.serial = _get_serial_or_fail()
		self.device = _connect_u2_with_retry(self.serial)

	def tearDown(self):
		# Restore Date & time -> Set automatically to ON after test.
		try:
			rtc_enable_automatic_time_zone(self.device, self.serial)
		except Exception as error:
			print(f"[tearDown] Failed to enable automatic time zone: {error}")

		 # Close Settings app 
		force_stop_Settings_app(self.serial, 'com.android.settings')
		self.device.press('home')
		print("[tearDown] Cleanup completed")

	def test_L1_time_zone_modify_androidcn_34035(self):
		"""
		Time zone modify validation.
		Test Steps:
		1. Go to Settings -> Date & time and disable automatic time zone.
		2. Manually select United States -> New York.
		3. Read current system time zone and verify it is America/New_York.
		4. Reboot device and wait for boot completion.
		5. Read current system time zone again and verify it remains America/New_York.
		6. Read current system time zone again and verify it remains America/New_York after reboot
		7. Read current system time zone again and verify it remains America/New_York. aftre power off and power on.
		"""
		print('\n========== Time zone modify test ==========')
		print(f'Device: {self.serial}')


		
		expected_timezone = 'america/new_york'

		# self.assertTrue(rtc_open_date_time_settings(self.device, self.serial), 'Failed to open Date & time settings.')
		# save_step_screenshot(self.device, 'step1_date_time_opened', SCRIPT_IMG_DIR)

		print('[Step2] Disabling Set automatically for time zone.', flush=True)
		self.assertTrue(rtc_disable_automatic_time_zone(self.device, self.serial), 'Failed to disable Set automatically for time zone.')
		save_step_screenshot(self.device, 'step2_automatic_time_zone_disabled', SCRIPT_IMG_DIR)
		print('[Step2] Completed.', flush=True)

		print('[Step3] Selecting United States -> New York time zone.', flush=True)
		self.assertTrue(rtc_select_New_York_time_zone(self.device,self.serial), 'Failed to select United States -> New York time zone.')
		save_step_screenshot(self.device, 'step3_new_york_selected', SCRIPT_IMG_DIR)
		print('[Step3] Completed.', flush=True)

		timezone_before_reboot = rtc_read_system_time_zone(self.serial, self.device)
		print(f'[Step4] Time zone before reboot: {timezone_before_reboot}')
		normalized = timezone_before_reboot.lower().replace(' ', '')
		self.assertTrue(
			normalized == expected_timezone or 'newyork' in normalized,
			f'Expected America/New_York before reboot, got: {timezone_before_reboot}',
		)

		print('[Step5] Rebooting device and waiting for boot completion.', flush=True)
		old_boot_id = reboot_run_adb_shell(self.serial, 'cat /proc/sys/kernel/random/boot_id', timeout=8)
		subprocess.run(['adb', '-s', self.serial, 'reboot'], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
		self.assertTrue(
			reboot_wait_device_success(self.serial, old_boot_id, timeout_sec=300),
			'Failed to wait for device reboot completion.',
		)
		self.device = _connect_u2_with_retry(self.serial, retries=5, wait_seconds=3)
		time.sleep(2)
		save_step_screenshot(self.device, 'step5_reboot_completed', SCRIPT_IMG_DIR)
		print('[Step5] Completed.', flush=True)

		timezone_after_reboot = rtc_read_system_time_zone(self.serial, self.device)
		print(f'[Step6] Time zone after reboot: {timezone_after_reboot}')
		normalized_after_reboot = timezone_after_reboot.lower().replace(' ', '')
		self.assertTrue(
			normalized_after_reboot == expected_timezone or 'newyork' in normalized_after_reboot,
			f'Expected America/New_York after reboot, got: {timezone_after_reboot}',
		)


if __name__ == '__main__':
	unittest.main(verbosity=2)
