# -*- coding: utf-8 -*-
# __author__ = 'sophy_H400818'
"""
Test case: L2 Key Remap - HOME -> VOLUME_UP.

Verify that selecting VOLUME_UP for the virtual HOME key raises the media
volume when the Home button on the navigation bar is pressed.

Author: auto_test
Date: 2026-09-24
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
	keyremap_get_stream_volume_index,
	keyremap_is_on_home_screen,
	keyremap_set_stream_volume_index,
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
SCRIPT_IMG_DIR = os.path.join(
	os.path.dirname(os.path.dirname(os.path.dirname(os.path.realpath(__file__)))),
	"img",
	SCRIPT_BASENAME,
)
os.makedirs(SCRIPT_IMG_DIR, exist_ok=True)

SETTINGS_PKG = get_package_name("settings")
KEYREMAP_PKG = get_package_name("keyremap")
VOLUME_UP_TARGET = "VOLUME_UP"
VOLUME_STREAM = "STREAM_MUSIC"


class TestKeyremapHomeToVolumeUp(unittest.TestCase):
	"""L2 test for HOME remapped to the VOLUME_UP function."""

	@classmethod
	def setUpClass(cls):
		cls.dev_id = serial
		print(f"\n[Setup] Device: {cls.dev_id}")

	def setUp(self):
		print(f"\n{'=' * 60}\nTest: {self.id()}\n{'=' * 60}")
		d.press("home")
		time.sleep(1)

	def tearDown(self):
		if getattr(self, "original_volume", None) is not None:
			keyremap_set_stream_volume_index(
				serial,
				self.original_volume,
				stream_name=VOLUME_STREAM,
			)

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

		d.screen_on()
		d.press("home")
		time.sleep(1)
		print(f"[TearDown] Completed: {self.id()}")

	def test_keyremap_home_to_volume_up(self):
		"""
		L2 Keyremap end-to-end test: HOME -> VOLUME_UP.
		Step 1: Open Keyremap page → tap '+' → dialog appears →
				click Home virtual icon → key captured →
				click OK → target list opens → scroll until "VOLUME_UP"
				is visible → tap it → verify entry saved.
		Step 2: Read the original STREAM_MUSIC volume, lower the volume three
				times to establish a baseline, then tap the navigation-bar Home key.
		Step 3: Verify STREAM_MUSIC volume increased after the remapped key press.
				Restore the original volume during teardown.
		"""
		print("\n[L2_Keyremap] Testing HOME -> VOLUME_UP Remap\n" + "=" * 60)

		print("\n[Step 1/3] Keyremap: '+' -> Home -> OK -> select 'VOLUME_UP'")
		print("-" * 60)
		if not keyremap_open_page(d, serial, SETTINGS_PKG, KEYREMAP_PKG):
			save_step_screenshot(d, "step1_nav_failed", SCRIPT_IMG_DIR)
			self.fail("Step 1 Failed: Could not navigate to Keyremap page")

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

		if keyremap_find_text_center(d, "NONE", contains=False) is None:
			save_step_screenshot(d, "step1_target_list_not_found", SCRIPT_IMG_DIR)
			self.fail("Step 1 Failed: Remap target list did not open after clicking OK")

		if not keyremap_tap_text(d, serial, VOLUME_UP_TARGET, contains=True, max_swipes=10):
			save_step_screenshot(d, "step1_volume_up_not_found", SCRIPT_IMG_DIR)
			self.fail("Step 1 Failed: 'VOLUME_UP' not found in target list after scrolling")
		time.sleep(2)

		if keyremap_find_text_center(d, VOLUME_UP_TARGET, contains=True) is None:
			save_step_screenshot(d, "step1_mapping_not_saved", SCRIPT_IMG_DIR)
			self.fail("Step 1 Failed: 'VOLUME_UP' was not shown in the Keyremap list after saving")

		save_step_screenshot(d, "step1_remap_saved", SCRIPT_IMG_DIR)
		print("  Remap entry saved: HOME -> VOLUME_UP")
		print("  Step 1 passed")

		print("\n[Step 2/3] Press the remapped Home key")
		print("-" * 60)
		press_home_key(serial)
		is_on_home, last_focus = keyremap_is_on_home_screen(serial)
		if not is_on_home:
			save_step_screenshot(d, "step2_not_on_home", SCRIPT_IMG_DIR)
			self.fail(f"Step 2 Failed: Could not return to Home screen (focus={last_focus})")

		self.original_volume = keyremap_get_stream_volume_index(serial, VOLUME_STREAM)
		if self.original_volume is None:
			save_step_screenshot(d, "step2_volume_unavailable", SCRIPT_IMG_DIR)
			self.fail("Step 2 Failed: Could not read STREAM_MUSIC volume before pressing Home")

		for _ in range(3):
			run_adb_cmd(serial, "shell input keyevent KEYCODE_VOLUME_DOWN", log_print=False)
			time.sleep(0.2)

		volume_before = keyremap_get_stream_volume_index(serial, VOLUME_STREAM)
		keyremap_tap_navbar_home(serial)
		time.sleep(1)
		volume_after = keyremap_get_stream_volume_index(serial, VOLUME_STREAM)
		save_step_screenshot(d, "step2_home_pressed", SCRIPT_IMG_DIR)
		print(f"  STREAM_MUSIC volume: before={volume_before}, after={volume_after}")

		print("\n[Step 3/3] Verify that the media volume increased")
		print("-" * 60)
		if volume_before is None or volume_after is None or volume_after <= volume_before:
			save_step_screenshot(d, "step3_volume_not_increased", SCRIPT_IMG_DIR)
			self.fail(
				"Step 3 Failed: VOLUME_UP did not raise STREAM_MUSIC volume "
				f"(before={volume_before}, after={volume_after})"
			)

		save_step_screenshot(d, "step3_volume_increased", SCRIPT_IMG_DIR)
		print("  HOME -> VOLUME_UP raised STREAM_MUSIC volume")
		print("  Step 3 passed")
		print("\n[L2_Keyremap] All steps passed")


if __name__ == "__main__":
	unittest.main(verbosity=2)
