# __author__ = 'sophy_H400818'
# -*- coding:utf-8 -*-

"""Validate system time synchronization after enabling automatic time with network connected."""

import os
import sys
import unittest
from datetime import datetime, timedelta

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from common.adb_common import _wifi_connect, _wifi_enable, get_system_date, save_step_screenshot
from common.common_method import (
	close_settings_app,
	rtc_disable_automatic_time,
	rtc_enable_automatic_time,
	rtc_compare_device_date,
	rtc_get_beijing_date,
	rtc_set_date_via_settings_ui,
	rtc_wait_network_time_sync,
	wifi_connect_via_ui,
	wifi_disconnect,
	wifi_init_device,
	wifi_open_settings,
)
SCRIPT_BASENAME = os.path.splitext(os.path.basename(__file__))[0]
SCRIPT_IMG_DIR = os.path.join(
	os.path.dirname(os.path.dirname(os.path.dirname(os.path.realpath(__file__)))),
	'img',
	SCRIPT_BASENAME,
)
os.makedirs(SCRIPT_IMG_DIR, exist_ok=True)


# Sophy_H400818_2026-08-14 Shared WiFi credentials. Environment variables override these defaults.
WIFI_SSID = os.environ.get('WIFI_SSID', 'CH3U_SUCN2_5G')
WIFI_PASSWORD = os.environ.get('WIFI_PASSWORD', os.environ.get('WIFI_PASS', 'mobility'))

def _get_serial_or_fail():
	serial = os.environ.get('ANDROID_SERIAL')
	if not serial:
		raise AssertionError('ANDROID_SERIAL is not set. Please export ANDROID_SERIAL first.')
	return serial


class TestSystemTimerSynchronized(unittest.TestCase):
	def setUp(self):
		self.serial = _get_serial_or_fail()
		self.device = wifi_init_device(self.serial)

	def tearDown(self):
		print('\nDisconnect wifi')
		try:
			wifi_disconnect(self.device, self.serial)
		except Exception as error:
			print(f'[tearDown] Failed to disconnect WiFi: {error}')

		print('\nclose settings.')
		close_settings_app(self.serial)
		self.device.press('home')
		print('[tearDown] Cleanup completed')

	def test_L1_system_timer_synchronized_androidcn_33303(self):
		"""
		System timer synchronization validation.
		Test Steps:
		1. Open Date & time and disable Set time automatically if it is enabled.
		2. Open Date & time and set a manual date/time.
		3. Open WiFi and connect to one WiFi network.
		4. Open Date & time and enable Set time automatically.
		5. Read system time and verify it synchronizes to current network time.
		"""
		print('\n========== System timer synchronized test ==========')
		print(f'Device: {self.serial}')
		beijing_date_before = rtc_get_beijing_date()
		print(f'[Before WiFi] Actual Beijing date: {beijing_date_before}', flush=True)

		# Step 1: Disable automatic time so manual date can be set.
		print('[Step1] Disable Set time automatically.', flush=True)
		self.assertTrue(
			rtc_disable_automatic_time(self.device, self.serial),
			'Failed to disable Set time automatically.',
		)
		save_step_screenshot(self.device, 'step1_set_automatic_disabled', SCRIPT_IMG_DIR)

		# Step 2: Set manual date to tomorrow in Date & time page.
		print('[Step2] Set manual date/time.', flush=True)
		current_date_str = get_system_date(self.serial)
		if current_date_str:
			base_date = datetime.strptime(current_date_str, '%Y-%m-%d')
		else:
			base_date = datetime.now()
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
			'Failed to set manual date/time in Date & time.',
		)
		save_step_screenshot(self.device, 'step2_manual_date_set', SCRIPT_IMG_DIR)

		# Step 3: Connect target WiFi network.
		print(f'[Step3] Connect WiFi: {WIFI_SSID}', flush=True)
		self.assertTrue(
			wifi_open_settings(self.device),
			'Failed to open WiFi settings via UI navigation.',
		)
		self.assertTrue(
			_wifi_enable(self.serial),
			'Failed to enable WiFi.',
		)
		connected = wifi_connect_via_ui(
			self.device,
			self.serial,
			WIFI_SSID,
			WIFI_PASSWORD,
		)
		

		if not connected:
			print('[RTC] Static IP UI connect failed, trying ADB connect as fallback...', flush=True)
			connected = _wifi_connect(self.serial, WIFI_SSID, WIFI_PASSWORD)
		self.assertTrue(
			connected,
			f'Failed to connect WiFi SSID: {WIFI_SSID}',
		)
		save_step_screenshot(self.device, 'step3_wifi_connected', SCRIPT_IMG_DIR)

		# Step 4: Re-enable automatic time.
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
		print(f'[After WiFi] Actual Beijing date: {beijing_date_after}', flush=True)
		print(f'[After WiFi] Device date after enabling automatic time: {device_date or "<unavailable>"}', flush=True)
		if device_date:
			print(
				f'[Date comparison] Beijing/device date: '
				f'{"CONSISTENT" if dates_match else "NOT CONSISTENT"}',
				flush=True,
			)
		else:
			print(f'[Date comparison] Unable to read device date: {device_date_error or "unknown error"}', flush=True)
		save_step_screenshot(self.device, 'step4_set_automatic_enabled', SCRIPT_IMG_DIR)

		# Step 5: Verify network time sync to current time.
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
		print(f'[Step5] Synchronized. Epoch diff: {diff} seconds', flush=True)
		save_step_screenshot(self.device, 'step5_time_synced', SCRIPT_IMG_DIR)


if __name__ == '__main__':
	unittest.main(verbosity=2)
