# __author__ = 'sophy_H400818'
# -*- coding:utf-8 -*-

"""Verify the device date rollback and build-date recovery after reboot."""

import calendar
import os
import re
import sys
import unittest
from datetime import datetime

import uiautomator2 as u2

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from common.adb_common import get_os_build_date, get_system_date, save_step_screenshot
from common.common_method import (
	close_settings_app,
	rtc_disable_automatic_time,
	rtc_enable_automatic_time,
	rtc_set_date_via_settings_ui,
	rtc_soft_reboot_and_wait,
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


def _connect_u2_with_retry(serial, retries=3):
	last_error = None
	for _ in range(retries):
		try:
			return u2.connect(serial)
		except Exception as error:
			last_error = error
	raise AssertionError(f'Failed to connect uiautomator2: {last_error}')


def _parse_build_date(build_text):
	match = re.search(r'([A-Z][a-z]{2})\s+(\d{1,2})\s+.*?(\d{4})$', build_text or '')
	if not match:
		return None
	return datetime.strptime(
		f'{match.group(1)} {match.group(2)} {match.group(3)}',
		'%b %d %Y',
	)


def _one_month_before(value):
	year = value.year if value.month > 1 else value.year - 1
	month = value.month - 1 if value.month > 1 else 12
	day = min(value.day, calendar.monthrange(year, month)[1])
	return value.replace(year=year, month=month, day=day)


class TestLongBeforeCurrentTime(unittest.TestCase):
	def setUp(self):
		self.serial = _get_serial_or_fail()
		self.device = _connect_u2_with_retry(self.serial)

	def tearDown(self):
		try:
			rtc_enable_automatic_time(self.device, self.serial)
		except Exception as error:
			print(f'[tearDown] Failed to enable automatic time: {error}', flush=True)
		close_settings_app(self.serial)
		try:
			self.device.press('home')
		except Exception:
			pass

	def test_l2_long_before_current_time_check_androidcn_35682(self):
		"""
        long_before_current_time_check
        Test Steps:
        1. Read OS build date.
        2. Disable Set time automatically.
        3. Disable 'Set time automatically.'
        4. Set system date to one month before build date.
        5. Reboot device and wait for boot completion.
        6. System date back to build date after reboot.
        """
		print('\n========== Build date rollback and reboot recovery test ==========')
		print(f'Device: {self.serial}')

		print('[Step1] Read OS build date.', flush=True)
		build_text = get_os_build_date(self.serial)
		build_date = _parse_build_date(build_text)
		self.assertIsNotNone(build_date, f'Unable to parse OS build date: {build_text}')
		print(f'[Step1] OS build time: {build_text}', flush=True)
		print(f'[Step1] OS build date: {build_date:%Y-%m-%d}', flush=True)

		print('[Step2] Disable Set time automatically.', flush=True)
		self.assertTrue(
			rtc_disable_automatic_time(self.device, self.serial),
			'Failed to disable Set time automatically.',
		)
		save_step_screenshot(self.device, 'step2_automatic_time_disabled', SCRIPT_IMG_DIR)

		target_date = _one_month_before(build_date)
		print(f'[Step3] Set system date to one month before build date: {target_date:%Y-%m-%d}.', flush=True)
		self.assertTrue(
			rtc_set_date_via_settings_ui(
				device=self.device,
				serial=self.serial,
				year=f'{target_date.year:04d}',
				month=f'{target_date.month:02d}',
				day=f'{target_date.day:02d}',
				img_dir=SCRIPT_IMG_DIR,
			),
			'Failed to set the system date before the OS build date.',
		)
		current_date = get_system_date(self.serial)
		print(f'[Step3] Current system date: {current_date}', flush=True)
		self.assertEqual(current_date, target_date.strftime('%Y-%m-%d'))
		save_step_screenshot(self.device, 'step3_date_before_build_date', SCRIPT_IMG_DIR)

		print('[Step4] Reboot device and wait for boot completion.', flush=True)
		self.assertTrue(
			rtc_soft_reboot_and_wait(self.serial, initial_wait_sec=60, checks=12, interval_sec=10),
			'Soft reboot or boot completion failed.',
		)
		self.device = _connect_u2_with_retry(self.serial)
		self.device.press('home')
		save_step_screenshot(self.device, 'step4_after_reboot', SCRIPT_IMG_DIR)

		print('[Step5] Verify system date returns to OS build date.', flush=True)
		reboot_date = get_system_date(self.serial)
		print(f'[Step5] Expected build date: {build_date:%Y-%m-%d}', flush=True)
		print(f'[Step5] Current system date: {reboot_date}', flush=True)
		self.assertEqual(
			reboot_date,
			build_date.strftime('%Y-%m-%d'),
			'System date did not return to the OS build date after reboot.',
		)


if __name__ == '__main__':
	unittest.main(verbosity=2)
