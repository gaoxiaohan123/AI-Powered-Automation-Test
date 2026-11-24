# -*- coding: utf-8 -*-
# __author__ = 'sophy_H400818'

"""
Test case: L2 Keyremap - HOME -> TEXT key sequence (ANDROIDCN-33117)

Verifies that HOME can be remapped to text values "a" and "b", then to
CTRL_LEFT,C and CTRL_LEFT,V to copy and paste Search text.

Author: Sophy H400818
Date: 2026-09-08
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
	keyremap_tap_navbar_home,
	press_home_key,
	run_adb_cmd,
	save_step_screenshot,
)
from common.common_method import (
	close_settings_app,
	get_package_name,
	keyremap_clear_all,
	keyremap_dialog_is_open,
	keyremap_input_text_value,
	keyremap_open_page,
	keyremap_tap_add_button,
	keyremap_tap_ok_button,
	keyremap_tap_text,
	scan_clear_input_field,
	scan_get_input_field_text,
	scan_open_input_field,
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
COPY_PROBE_TEXT = "COPYTEST"


class TestKeyremapHomeToTextSequence(unittest.TestCase):
	"""L2 test for HOME remapped to text and a copy shortcut."""

	@classmethod
	def setUpClass(cls):
		cls.dev_id = serial
		print(f"\n[Setup] Device: {cls.dev_id}")

	def setUp(self):
		d.press("home")
		time.sleep(1)

	def tearDown(self):
		d.press("back")
		if keyremap_open_page(d, serial, SETTINGS_PKG, KEYREMAP_PKG):
			keyremap_clear_all(d, serial)

		run_adb_cmd(serial, "shell input keyevent KEYCODE_BACK", log_print=False)

		keyremap_force_stop_honeywell_settings(serial)
		close_settings_app(serial)
		d.screen_on()
		d.press("home")
		print(f"[TearDown] Completed: {self.id()}")

	def _save_home_text_mapping(self, text_value, is_new_mapping=False):
		"""Create or update the HOME TEXT mapping and return True on success."""
		if not keyremap_open_page(d, serial, SETTINGS_PKG, KEYREMAP_PKG):
			return False

		if is_new_mapping:
			keyremap_tap_add_button(d, serial)
			if not keyremap_dialog_is_open(d):
				return False
			keyremap_click_virtual_home(serial)
			if not keyremap_tap_ok_button(d, serial):
				return False
		else:
			if not keyremap_tap_text(d, serial, "User Text", contains=True, max_swipes=10):
				return False

		if not keyremap_tap_text(d, serial, "TEXT", contains=False, max_swipes=10):
			return False
		if not keyremap_input_text_value(d, KEYREMAP_PKG, text_value):
			return False
		return keyremap_tap_ok_button(d, serial)

	def _open_empty_search(self):
		"""Return to launcher, focus Search, and clear its text."""
		press_home_key(serial)
		if not scan_open_input_field(d, serial):
			return False
		scan_clear_input_field(d)
		return True

	def _select_all_search_text(self):
		"""Select all text using the native Android text-selection menu."""
		edit = d(focused=True, className="android.widget.EditText")
		if not edit.exists(timeout=1):
			edit = d(className="android.widget.EditText")
		if not edit.exists(timeout=1):
			return False
		edit.long_click()
		time.sleep(1)
		for label in ("Select all", "全选"):
			option = d(text=label)
			if option.exists(timeout=0.5):
				option.click()
				time.sleep(0.5)
				return True
		return False

	def test_home_key_remaps_text_and_copy_shortcut(self):
		"""
		L2 Keyremap end-to-end test: HOME -> TEXT and clipboard shortcuts.
		Step 1: Map HOME to TEXT 'a', open an empty launcher Search field, press
				the mapped key, and verify that 'a' is entered.
		Step 2: Update the mapping to TEXT 'b' and verify that 'b' is entered.
		Step 3: Map HOME to CTRL_LEFT,C, select probe text in Search, press the
				mapped key, then paste into a cleared Search field and verify the text.
		Step 4: Map HOME to CTRL_LEFT,V, press the mapped key in an empty Search
				field, and verify that the copied probe text is pasted.
		"""
		print("\n[L2_Keyremap] Testing HOME -> TEXT a, b, CTRL_LEFT,C, CTRL_LEFT,V\n" + "=" * 60)

		if not self._save_home_text_mapping("a", is_new_mapping=True):
			save_step_screenshot(d, "step1_mapping_a_failed", SCRIPT_IMG_DIR)
			self.fail("Could not create HOME -> TEXT 'a' mapping")
		if not self._open_empty_search():
			save_step_screenshot(d, "step1_search_not_opened", SCRIPT_IMG_DIR)
			self.fail("Could not open the launcher Search input")
		keyremap_tap_navbar_home(serial)
		typed_text = scan_get_input_field_text(d)
		if typed_text.lower() != "a":
			save_step_screenshot(d, "step1_a_not_typed", SCRIPT_IMG_DIR)
			self.fail(f"Expected Search to contain 'a', got '{typed_text}'")
		save_step_screenshot(d, "step1_a_typed", SCRIPT_IMG_DIR)

		if not self._save_home_text_mapping("b"):
			save_step_screenshot(d, "step2_mapping_b_failed", SCRIPT_IMG_DIR)
			self.fail("Could not update HOME -> TEXT 'b' mapping")
		if not self._open_empty_search():
			save_step_screenshot(d, "step2_search_not_opened", SCRIPT_IMG_DIR)
			self.fail("Could not open the launcher Search input")
		keyremap_tap_navbar_home(serial)
		typed_text = scan_get_input_field_text(d)
		if typed_text.lower() != "b":
			save_step_screenshot(d, "step2_b_not_typed", SCRIPT_IMG_DIR)
			self.fail(f"Expected Search to contain 'b', got '{typed_text}'")
		save_step_screenshot(d, "step2_b_typed", SCRIPT_IMG_DIR)

		if not self._save_home_text_mapping("CTRL_LEFT,C"):
			save_step_screenshot(d, "step3_mapping_copy_failed", SCRIPT_IMG_DIR)
			self.fail("Could not update HOME -> TEXT 'CTRL_LEFT,C' mapping")
		if not self._open_empty_search():
			save_step_screenshot(d, "step3_search_not_opened", SCRIPT_IMG_DIR)
			self.fail("Could not open the launcher Search input")
		run_adb_cmd(serial, f"shell input text {COPY_PROBE_TEXT}", log_print=False)
		time.sleep(1)
		if not self._select_all_search_text():
			save_step_screenshot(d, "step3_select_all_failed", SCRIPT_IMG_DIR)
			self.fail("Could not select all Search text before testing copy")

		keyremap_tap_navbar_home(serial)
		time.sleep(1)
		if not self._open_empty_search():
			save_step_screenshot(d, "step3_search_not_reopened", SCRIPT_IMG_DIR)
			self.fail("Could not reopen and clear Search after the HOME copy shortcut")
		run_adb_cmd(serial, "shell input keyevent KEYCODE_PASTE", log_print=False)
		time.sleep(1)
		pasted_text = scan_get_input_field_text(d)
		if pasted_text.upper() != COPY_PROBE_TEXT:
			save_step_screenshot(d, "step3_copy_not_verified", SCRIPT_IMG_DIR)
			self.fail(
				f"Expected pasted clipboard text '{COPY_PROBE_TEXT}', got '{pasted_text}'"
			)

		save_step_screenshot(d, "step3_copy_verified", SCRIPT_IMG_DIR)

		if not self._save_home_text_mapping("CTRL_LEFT,V"):
			save_step_screenshot(d, "step4_mapping_paste_failed", SCRIPT_IMG_DIR)
			self.fail("Could not update HOME -> TEXT 'CTRL_LEFT,V' mapping")
		if not self._open_empty_search():
			save_step_screenshot(d, "step4_search_not_opened", SCRIPT_IMG_DIR)
			self.fail("Could not open the launcher Search input")

		keyremap_tap_navbar_home(serial)
		time.sleep(1)
		pasted_text = scan_get_input_field_text(d)
		if pasted_text.upper() != COPY_PROBE_TEXT:
			save_step_screenshot(d, "step4_paste_not_verified", SCRIPT_IMG_DIR)
			self.fail(
				f"Expected HOME to paste '{COPY_PROBE_TEXT}', got '{pasted_text}'"
			)

		save_step_screenshot(d, "step4_paste_verified", SCRIPT_IMG_DIR)
		print("  HOME emitted 'a', then 'b', then copied and pasted the Search text")


if __name__ == "__main__":
	unittest.main()
