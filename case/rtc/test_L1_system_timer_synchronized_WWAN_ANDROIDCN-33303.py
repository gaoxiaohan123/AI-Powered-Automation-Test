# __author__ = 'sophy_H400818'
# -*- coding:utf-8 -*-

"""Validate system time synchronization after enabling automatic time over WWAN."""

import os
import sys
import time
import unittest
from datetime import datetime, timedelta

import uiautomator2 as u2

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from common.adb_common import get_system_date, rtc_date_output, save_step_screenshot, sim_card_is_present,imei_get_baseband_type
from common.common_method import (
	close_settings_app,
	rtc_compare_device_date,
	rtc_disable_automatic_time,
	rtc_enable_automatic_time,
	rtc_enable_mobile_data,
	rtc_get_beijing_date,
	rtc_set_date_via_settings_ui,
	rtc_wait_network_time_sync,
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


class TestSystemTimerSynchronizedWWAN(unittest.TestCase):
	def setUp(self):
		self.serial = _get_serial_or_fail()
		self.device = _connect_u2_with_retry(self.serial)

	def _skip_if_no_sim(self):
		if not sim_card_is_present(self.serial):
			skip_msg = '未检测到SIM卡，测试需插入SIM卡测试后再执行'
			print(f'[setup] [SKIP] {skip_msg}', flush=True)
			self.skipTest(skip_msg)

	def tearDown(self):
		
		close_settings_app(self.serial)
		self.device.press('home')

	def test_L1_system_timer_synchronized_wwan_androidcn_33303(self):
		"""
		Test Steps:
		1. Open Date & time and disable Set time automatically if enabled.
		2. Set a manual date in Date & time.
		3. Enable mobile data so the device has a WWAN network.
		4. Open Date & time and enable Set time automatically.
		5. Read system time and verify it synchronizes to current network time.
		"""
		print('\n========== WWAN system timer synchronized test ==========')
		print(f'Device: {self.serial}')
		beijing_date_before = rtc_get_beijing_date()
		print(f'[Before WWAN] Actual Beijing date: {beijing_date_before}', flush=True)

		baseband = imei_get_baseband_type(self.serial)
		if baseband == "apq":
			skip_msg = "WLAN device - WWAN test requires a device with cellular capability"
			print(f"  [SKIP] {skip_msg}", flush=True)
			self.skipTest(skip_msg)
		
		self._skip_if_no_sim()

		print('[Step1] Disable Set time automatically.', flush=True)
		self.assertTrue(
			rtc_disable_automatic_time(self.device, self.serial),
			'Failed to disable Set time automatically.',
		)
		save_step_screenshot(self.device, 'step1_set_automatic_disabled', SCRIPT_IMG_DIR)

		print('[Step2] Set manual date.', flush=True)
		current_date_str = get_system_date(self.serial)
		base_date = datetime.strptime(current_date_str, '%Y-%m-%d') if current_date_str else datetime.now()
		target_date = base_date + timedelta(days=1)
		self.assertTrue(
			rtc_set_date_via_settings_ui(
				device=self.device,
				serial=self.serial,
				year=target_date.strftime('%Y'),
				month=target_date.strftime('%m'),
				day=target_date.strftime('%d'),
				img_dir=SCRIPT_IMG_DIR,
			),
			'Failed to set manual date in Date & time.',
		)
		save_step_screenshot(self.device, 'step2_manual_date_set', SCRIPT_IMG_DIR)

		print('[Step3] Enable mobile data for WWAN.', flush=True)
		self.assertTrue(rtc_enable_mobile_data(self.serial), 'Failed to enable mobile data.')

		print('[Step4] Enable Set time automatically.', flush=True)
		self.assertTrue(
			rtc_enable_automatic_time(self.device, self.serial),
			'Failed to enable Set time automatically.',
		)
		beijing_date_after = rtc_get_beijing_date()
		device_date, dates_match, device_date_error = rtc_compare_device_date(
			self.serial,
			beijing_date_after,
		)
		print(f'[After WWAN] Actual Beijing date: {beijing_date_after}', flush=True)
		print(f'[After WWAN] Device date after enabling automatic time: {device_date or "<unavailable>"}', flush=True)
		if device_date:
			print(
				f'[Date comparison] Beijing/device date: '
				f'{"CONSISTENT" if dates_match else "NOT CONSISTENT"}',
				flush=True,
			)
		else:
			print(f'[Date comparison] Unable to read device date: {device_date_error or "unknown error"}', flush=True)
		synced_datetime, _ = rtc_date_output(self.serial, '+%Y-%m-%d %H:%M:%S')
		print(f'[Step4] Device synchronized time: {synced_datetime}', flush=True)
		save_step_screenshot(self.device, 'step4_set_automatic_enabled', SCRIPT_IMG_DIR)

		print('[Step5] Verify system time synchronized to current network time.', flush=True)
		synced, diff = rtc_wait_network_time_sync(
			self.serial,
			tolerance_seconds=300,
			retries=9,
			interval_sec=10,
		)
		self.assertTrue(
			synced,
			f'System time did not synchronize to current network time. Last epoch diff: {diff} seconds.',
		)
		final_synced_datetime, _ = rtc_date_output(self.serial, '+%Y-%m-%d %H:%M:%S')
		print(f'[Step5] Synchronized. Epoch diff: {diff} seconds. Current device time: {final_synced_datetime}', flush=True)
		save_step_screenshot(self.device, 'step5_time_synced', SCRIPT_IMG_DIR)


if __name__ == '__main__':
	unittest.main(verbosity=2)
