# -*- coding: utf-8 -*-
# __author__ = 'sophy_H400818'
"""
Test case: L2 Key Remap - HOME -> FUNCTION in GetKeyCode.

Install getkeycode-20250730.apk, remap the virtual HOME key to FUNCTION, and
verify the app displays KeyCode: 119 after the remapped Home key is pressed.

Author: Sophy H400818
Date: 2026-09-28
"""

import os
import re
import sys
import time
import unittest
import xml.etree.ElementTree as ET

import uiautomator2 as u2

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from common.adb_common import (
	get_device_serial,
	keyremap_click_virtual_home,
	keyremap_force_stop_honeywell_settings,
	keyremap_install_app,
	keyremap_tap_navbar_home,
	keyremap_uninstall_app,
	keyremap_wait_app_foreground,
	run_adb_cmd,
	save_step_screenshot,
)
from common.common_method import (
	close_settings_app,
	disable_play_protect_app_scanning,
	enable_play_protect_app_scanning,
	get_package_name,
	keyremap_clear_all,
	keyremap_dialog_is_open,
	keyremap_find_text_center,
	keyremap_open_page,
	keyremap_tap_add_button,
	keyremap_tap_ok_button,
	keyremap_tap_text,
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
APK_FILE_NAME = "getkeycode-20250730.apk"
APK_PATH = os.path.join(PROJECT_ROOT, "files", "apps", APK_FILE_NAME)
APP_PACKAGE = "com.example.getkeycode"
FUNCTION_TARGET = "FUNCTION"
FUNCTION_KEYCODE = 119


class TestKeyremapHomeToFunctionKeyEventDisplay(unittest.TestCase):
	"""Verify HOME -> FUNCTION reports keycode 119 in GetKeyCode."""

	@classmethod
	def setUpClass(cls):
		cls.dev_id = serial
		print(f"\n[Setup] Device: {cls.dev_id}")

	def setUp(self):
		print(f"\n{'=' * 60}\nTest: {self.id()}\n{'=' * 60}")
		d.screen_on()
		d.press("home")
		time.sleep(1)

	def tearDown(self):
		run_adb_cmd(serial, f"shell am force-stop {APP_PACKAGE}", log_print=False)
		if keyremap_open_page(d, serial, SETTINGS_PKG, KEYREMAP_PKG):
			keyremap_clear_all(d, serial)
			run_adb_cmd(serial, "shell input keyevent KEYCODE_BACK", log_print=False)
			time.sleep(1)
		else:
			print("[TearDown] [WARN] Keyremap page not reachable; mapping may remain")

		keyremap_force_stop_honeywell_settings(serial)
		close_settings_app(serial)
		pid_raw = run_adb_cmd(serial, f"shell pidof {KEYREMAP_PKG}", log_print=False)
		pid_str = (
			pid_raw.decode("utf-8", errors="ignore")
			if isinstance(pid_raw, bytes)
			else str(pid_raw)
		).strip()
		if pid_str and pid_str.isdigit():
			run_adb_cmd(serial, f"shell kill {pid_str}", log_print=False)

		keyremap_uninstall_app(serial, APP_PACKAGE)
		if enable_play_protect_app_scanning(d):
			print("  Play Protect app scanning is enabled")
		else:
			print("  Play Protect app scanning could not be restored")
		run_adb_cmd(serial, "shell am force-stop com.android.vending", log_print=False)
		d.screen_on()
		d.press("home")
		time.sleep(1)
		print(f"[TearDown] Completed: {self.id()}")

	def test_keyremap_home_to_function_keyeventdisplay(self):
		"""
		L2 Keyremap end-to-end test: HOME -> FUNCTION in GetKeyCode.
		Step 1: Install getkeycode-20250730.apk.
		Step 2: Map the virtual HOME key to FUNCTION and verify the entry.
		Step 3: Open GetKeyCode and verify it is in the foreground.
		Step 4: Tap the navigation-bar Home key and verify the app displays
				KeyCode: 119.
		"""
		print("\n[L2_Keyremap] Testing HOME -> FUNCTION in GetKeyCode\n" + "=" * 60)

		print(f"\n[Step 1/4] Install '{APK_FILE_NAME}'")
		if disable_play_protect_app_scanning(d):
			print("  Play Protect app scanning is disabled")
		installed, install_output = keyremap_install_app(serial, APK_PATH, APP_PACKAGE)
		if not installed:
			save_step_screenshot(d, "step1_install_failed", SCRIPT_IMG_DIR)
			self.fail(f"Step 1 Failed: could not install {APK_FILE_NAME} ({install_output})")
		save_step_screenshot(d, "step1_app_installed", SCRIPT_IMG_DIR)

		print("\n[Step 2/4] Configure HOME -> FUNCTION")
		if not keyremap_open_page(d, serial, SETTINGS_PKG, KEYREMAP_PKG):
			save_step_screenshot(d, "step2_nav_failed", SCRIPT_IMG_DIR)
			self.fail("Step 2 Failed: Could not navigate to Keyremap page")
		keyremap_tap_add_button(d, serial)
		if not keyremap_dialog_is_open(d):
			save_step_screenshot(d, "step2_dialog_not_opened", SCRIPT_IMG_DIR)
			self.fail("Step 2 Failed: '+' button did not open the key-capture dialog")
		keyremap_click_virtual_home(serial)
		time.sleep(1)
		if not keyremap_tap_ok_button(d, serial):
			save_step_screenshot(d, "step2_ok_failed", SCRIPT_IMG_DIR)
			self.fail("Step 2 Failed: Could not confirm the captured HOME key")
		if keyremap_find_text_center(d, "NONE", contains=False) is None:
			save_step_screenshot(d, "step2_target_list_not_found", SCRIPT_IMG_DIR)
			self.fail("Step 2 Failed: Remap target list did not open")
		if not keyremap_tap_text(d, serial, FUNCTION_TARGET, contains=False, max_swipes=10):
			save_step_screenshot(d, "step2_function_not_found", SCRIPT_IMG_DIR)
			self.fail("Step 2 Failed: 'FUNCTION' not found in target list")
		time.sleep(2)
		if keyremap_find_text_center(d, FUNCTION_TARGET, contains=False) is None:
			save_step_screenshot(d, "step2_mapping_not_saved", SCRIPT_IMG_DIR)
			self.fail("Step 2 Failed: 'FUNCTION' was not shown in the Keyremap list")
		save_step_screenshot(d, "step2_remap_saved", SCRIPT_IMG_DIR)

		print("\n[Step 3/4] Open GetKeyCode")
		d.app_start(APP_PACKAGE)
		app_shown, focus_info = keyremap_wait_app_foreground(serial, APP_PACKAGE, timeout=15)
		if not app_shown:
			save_step_screenshot(d, "step3_app_not_launched", SCRIPT_IMG_DIR)
			self.fail(f"Step 3 Failed: GetKeyCode did not open (focus={focus_info})")
		save_step_screenshot(d, "step3_app_ready", SCRIPT_IMG_DIR)

		print("\n[Step 4/4] Press Home and verify KeyCode 119")
		keyremap_tap_navbar_home(serial)
		deadline = time.time() + 10
		key_code_seen = False
		texts = []
		while time.time() < deadline:
			try:
				root = ET.fromstring(d.dump_hierarchy())
				texts = [node.attrib.get("text", "") for node in root.iter()]
			except ET.ParseError:
				texts = []
			key_code_seen = any(
				re.search(r"\bKeyCode:\s*119\b", text) is not None for text in texts
			)
			if key_code_seen:
				break
			time.sleep(1)

		save_step_screenshot(d, "step4_keycode", SCRIPT_IMG_DIR)
		if not key_code_seen:
			self.fail(
				f"Step 4 Failed: expected KeyCode {FUNCTION_KEYCODE}; "
				f"visible text={texts}"
			)
		print(f"  GetKeyCode displayed KeyCode: {FUNCTION_KEYCODE}")

if __name__ == "__main__":
	unittest.main(verbosity=2)