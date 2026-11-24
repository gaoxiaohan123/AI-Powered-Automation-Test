# -*- coding: utf-8 -*-
# __author__ = 'sophy_H400818'
"""
Test case: L2 Key Remap - HOME -> EXPLORER.

Verify that selecting EXPLORER for the virtual HOME key launches the browser
when the Home button on the navigation bar is pressed.
"""

import os
import sys
import time
import unittest

import uiautomator2 as u2

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from common.adb_common import (
	get_device_serial,
	keyremap_click_virtual_home,
	keyremap_force_stop_honeywell_settings,
	keyremap_is_on_home_screen,
	keyremap_tap_navbar_home,
	keyremap_wait_app_foreground,
	press_home_key,
	run_adb_cmd,
	save_step_screenshot,
)
from common.common_method import (
	close_settings_app,
	get_package_name,
	keyremap_clear_all,
	keyremap_dialog_is_open,
	keyremap_find_text_center,
	keyremap_open_page,
	keyremap_tap_text,
	keyremap_tap_add_button,
	keyremap_tap_ok_button,
)


serial = get_device_serial()
if not serial:
	print("Error: No Android device found. Connect a device or set ANDROID_SERIAL.")
	sys.exit(1)

d = u2.connect(serial)
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.realpath(__file__))))
SCRIPT_BASENAME = os.path.splitext(os.path.basename(__file__))[0]
SCRIPT_IMG_DIR = os.path.join(PROJECT_ROOT, "img", SCRIPT_BASENAME)
os.makedirs(SCRIPT_IMG_DIR, exist_ok=True)

SETTINGS_PKG = get_package_name("settings")
KEYREMAP_PKG = get_package_name("keyremap")
EXPLORER_TARGET = "EXPLORER"
BROWSER_PACKAGES = (
	"com.android.browser",
	"com.android.chrome",
	"com.google.android.apps.chrome",
)


class TestKeyremapHomeToExplorer(unittest.TestCase):
	"""L2 test for HOME remapped to the EXPLORER function."""

	@classmethod
	def setUpClass(cls):
		cls.dev_id = serial
		print(f"\n[Setup] Device: {cls.dev_id}")

	def setUp(self):
		print(f"\n{'=' * 60}\nTest: {self.id()}\n{'=' * 60}")
		for package in BROWSER_PACKAGES:
			run_adb_cmd(serial, f"shell am force-stop {package}", log_print=False)
		d.press("home")
		time.sleep(1)

	def tearDown(self):
		for package in BROWSER_PACKAGES:
			run_adb_cmd(serial, f"shell am force-stop {package}", log_print=False)

		if keyremap_open_page(d, serial, SETTINGS_PKG, KEYREMAP_PKG):
			keyremap_clear_all(d, serial)
			run_adb_cmd(serial, "shell input keyevent KEYCODE_BACK", log_print=False)
			time.sleep(1)
		else:
			print("[TearDown] [WARN] Keyremap page not reachable; mapping may remain")

		keyremap_force_stop_honeywell_settings(serial)
		close_settings_app(serial)
		pid_raw = run_adb_cmd(serial, f"shell pidof {KEYREMAP_PKG}", log_print=False)
		pid_str = (pid_raw.decode("utf-8", errors="ignore") if isinstance(pid_raw, bytes) else str(pid_raw)).strip()
		if pid_str and pid_str.isdigit():
			run_adb_cmd(serial, f"shell kill {pid_str}", log_print=False)
		d.screen_on()
		d.press("home")
		time.sleep(1)
		print(f"[TearDown] Completed: {self.id()}")

	def test_keyremap_home_to_explorer(self):
		"""
		L2 Keyremap end-to-end test: HOME -> EXPLORER.
		Step 1: Map the virtual HOME key to EXPLORER and verify the entry.
		Step 2: Return to the Home screen and tap the navigation-bar Home key.
		Step 3: Verify that a supported browser is launched.
		"""
		print("\n[L2_Keyremap] Testing HOME -> EXPLORER Remap\n" + "=" * 60)

		print("\n[Step 1/3] Keyremap: '+' -> Home -> OK -> select 'EXPLORER'")
		print("-" * 60)
		if not keyremap_open_page(d, serial, SETTINGS_PKG, KEYREMAP_PKG):
			save_step_screenshot(d, "step1_nav_failed", SCRIPT_IMG_DIR)
			self.fail("Step 1 Failed: Could not navigate to Keyremap page")
		time.sleep(2)

		save_step_screenshot(d, "step1_keyremap_page", SCRIPT_IMG_DIR)

		keyremap_tap_add_button(d, serial)
		if not keyremap_dialog_is_open(d):
			save_step_screenshot(d, "step1_dialog_not_opened", SCRIPT_IMG_DIR)
			self.fail("Step 1 Failed: '+' button did not open the key-capture dialog")

		save_step_screenshot(d, "step1_dialog_opened", SCRIPT_IMG_DIR)

		keyremap_click_virtual_home(serial)
		time.sleep(1)
		if not keyremap_tap_ok_button(d, serial):
			save_step_screenshot(d, "step1_ok_failed", SCRIPT_IMG_DIR)
			self.fail("Step 1 Failed: Could not confirm the captured HOME key")

		# NONE is visible on the first target-list page even when EXPLORER needs scrolling.
		if keyremap_find_text_center(d, "NONE", contains=False) is None:
			save_step_screenshot(d, "step1_target_list_not_found", SCRIPT_IMG_DIR)
			self.fail("Step 1 Failed: Remap target list did not open after clicking OK")

		if not keyremap_tap_text(d, serial, EXPLORER_TARGET, contains=True, max_swipes=10):
			save_step_screenshot(d, "step1_explorer_not_found", SCRIPT_IMG_DIR)
			self.fail("Step 1 Failed: 'EXPLORER' not found in target list after scrolling")
		time.sleep(2)

		if keyremap_find_text_center(d, EXPLORER_TARGET, contains=True) is None:
			save_step_screenshot(d, "step1_mapping_not_saved", SCRIPT_IMG_DIR)
			self.fail("Step 1 Failed: 'EXPLORER' was not shown in the Keyremap list after saving")

		save_step_screenshot(d, "step1_remap_saved", SCRIPT_IMG_DIR)
		print("  Remap entry saved: HOME -> EXPLORER")
		print("  Step 1 passed")

		print("\n[Step 2/3] Press the navigation-bar Home key")
		print("-" * 60)
		press_home_key(serial)
		is_on_home, last_focus = keyremap_is_on_home_screen(serial)
		if not is_on_home:
			save_step_screenshot(d, "step2_not_on_home", SCRIPT_IMG_DIR)
			self.fail(f"Step 2 Failed: Could not return to Home screen (focus={last_focus})")

		keyremap_tap_navbar_home(serial)
		time.sleep(1)
		save_step_screenshot(d, "step2_home_pressed", SCRIPT_IMG_DIR)
		print("  Step 2 passed")

		print("\n[Step 3/3] Verify that the browser was launched")
		print("-" * 60)
		browser_package = None
		focus_info = ""
		for package in BROWSER_PACKAGES:
			launched, focus_info = keyremap_wait_app_foreground(serial, package, timeout=6)
			if launched:
				browser_package = package
				break

		if browser_package is None:
			save_step_screenshot(d, "step3_browser_not_launched", SCRIPT_IMG_DIR)
			self.fail(f"Step 3 Failed: EXPLORER did not launch a browser (focus={focus_info or 'unknown'})")

		save_step_screenshot(d, "step3_browser_launched", SCRIPT_IMG_DIR)
		print(f"  Browser launched successfully: {browser_package}")
		print("  Step 3 passed")
		print("\n[L2_Keyremap] All steps passed")


if __name__ == "__main__":
	unittest.main(verbosity=2)
