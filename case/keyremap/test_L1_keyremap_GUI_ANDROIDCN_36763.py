# -*- coding: utf-8 -*-
# __author__ = 'sophy_H400818'
"""
Test case: L1 Keyremap GUI (ANDROIDCN-36763)

Verifies that selecting the virtual HOME key in Honeywell Settings -> Keyremap
opens a target list containing KEYS, APPS, ACTIONS, COMMAND, and TEXT.

Author: Sophy H400818
Date: 2026-09-07
"""

import os
import sys
import time
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import uiautomator2 as u2

from common.adb_common import (
	get_device_serial,
	keyremap_click_virtual_home,
	keyremap_force_stop_honeywell_settings,
	run_adb_cmd,
	save_step_screenshot,
)
from common.common_method import (
	close_settings_app,
	get_package_name,
	keyremap_dialog_is_open,
	keyremap_find_text_center,
	keyremap_open_page,
	keyremap_tap_add_button,
	keyremap_tap_ok_button,
)


serial = get_device_serial()
if not serial:
	print("Error: No Android device found. Connect a device or set ANDROID_SERIAL.")
	sys.exit(1)

d = u2.connect(serial)

SCRIPT_BASENAME = os.path.splitext(os.path.basename(__file__))[0]
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.realpath(__file__))))
SCRIPT_IMG_DIR = os.path.join(PROJECT_ROOT, "img", SCRIPT_BASENAME)
os.makedirs(SCRIPT_IMG_DIR, exist_ok=True)

SETTINGS_PKG = get_package_name("settings")
KEYREMAP_PKG = get_package_name("keyremap")
TARGET_OPTIONS = ("KEYS", "APPS", "ACTIONS", "COMMAND", "TEXT")


class TestKeyremapGui(unittest.TestCase):
	"""L1 GUI smoke test for the Keyremap target selection screen."""

	@classmethod
	def setUpClass(cls):
		cls.dev_id = serial
		print(f"\n[Setup] Device: {cls.dev_id}")

	def setUp(self):
		print(f"\n{'=' * 60}\nTest: {self.id()}\n{'=' * 60}")
		d.press("home")
		time.sleep(1)

	def tearDown(self):
		keyremap_force_stop_honeywell_settings(serial)
		close_settings_app(serial)
		d.screen_on()
		d.press("home")
		print(f"[TearDown] Completed: {self.id()}")

	def test_home_key_displays_all_target_options(self):
		"""
		L1 Keyremap GUI smoke test.
		Step 1: Open Keyremap, tap '+', capture the virtual HOME key, and confirm it.
		Step 2: Verify the target list contains KEYS, APPS, ACTIONS, COMMAND, and TEXT.
		Step 3: Return to Honeywell Settings and verify the parent page is displayed.
		"""
		print("\n[L1_Keyremap] Verify HOME target options\n" + "=" * 60)

		if not keyremap_open_page(d, serial, SETTINGS_PKG, KEYREMAP_PKG):
			save_step_screenshot(d, "navigation_failed", SCRIPT_IMG_DIR)
			self.fail("Could not navigate to Honeywell Settings -> Keyremap")

		keyremap_tap_add_button(d, serial)
		if not keyremap_dialog_is_open(d):
			save_step_screenshot(d, "capture_dialog_not_opened", SCRIPT_IMG_DIR)
			self.fail("'+' did not open the key-capture dialog")

		keyremap_click_virtual_home(serial)
		if not keyremap_tap_ok_button(d, serial):
			save_step_screenshot(d, "home_capture_not_confirmed", SCRIPT_IMG_DIR)
			self.fail("Could not confirm the virtual HOME key capture")

		missing_options = [
			option
			for option in TARGET_OPTIONS
			if keyremap_find_text_center(d, option, contains=False) is None
		]
		if missing_options:
			save_step_screenshot(d, "target_options_missing", SCRIPT_IMG_DIR)
			self.fail(f"Missing Keyremap target options: {', '.join(missing_options)}")

		save_step_screenshot(d, "all_target_options_displayed", SCRIPT_IMG_DIR)
		print(f"  Target options displayed: {', '.join(TARGET_OPTIONS)}")

		d.press("back")
		time.sleep(1)
		d.press("back")
		time.sleep(2)
		if keyremap_find_text_center(d, "Honeywell Settings", contains=True) is None:
			save_step_screenshot(d, "honeywell_settings_not_displayed", SCRIPT_IMG_DIR)
			self.fail("Could not return to the Honeywell Settings page")

		save_step_screenshot(d, "honeywell_settings_displayed", SCRIPT_IMG_DIR)
		print("  Returned to Honeywell Settings")


if __name__ == "__main__":
	unittest.main()
