# -*- coding: utf-8 -*-
# __author__ = 'sophy_H400818'
"""
Test case: L2 Keyremap - HOME -> MIDDLESCAN (ANDROIDCN-35006)

Verifies that mapping the virtual HOME key to MIDDLESCAN scans the barcode
shown on a reference device and wedges its value into the launcher Search box.

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
	dcs_test_prepare_image_on_display_device,
	dcs_test_wait_device_online,
	dcs_test_wake_and_unlock,
	keyremap_click_virtual_home,
	keyremap_force_stop_honeywell_settings,
	keyremap_tap_navbar_home,
	press_home_key,
	run_adb_cmd,
	save_step_screenshot,
)
from common.common_method import (
	close_settings_app,
	dcs_test_connect_u2,
	get_package_name,
	keyremap_clear_all,
	keyremap_dialog_is_open,
	keyremap_find_text_center,
	keyremap_open_page,
	keyremap_tap_add_button,
	keyremap_tap_ok_button,
	keyremap_tap_text,
	scan_clear_input_field,
	scan_get_input_field_text,
	scan_open_input_field,
)


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.realpath(__file__))))
SCANNER_SERIAL = (os.environ.get("AUTONEXUS_DEV0_SN") or os.environ.get("ANDROID_SERIAL") or "").strip()
REFERENCE_SERIAL = (os.environ.get("AUTONEXUS_DEV1_SN") or "").strip()
if not SCANNER_SERIAL or not REFERENCE_SERIAL:
	raise RuntimeError("AUTONEXUS_DEV0_SN and AUTONEXUS_DEV1_SN are required")
if not dcs_test_wait_device_online(SCANNER_SERIAL, timeout_seconds=25):
	raise RuntimeError(f"Scanner device is offline: {SCANNER_SERIAL}")
if not dcs_test_wait_device_online(REFERENCE_SERIAL, timeout_seconds=25):
	raise RuntimeError(f"Reference device is offline: {REFERENCE_SERIAL}")

d = dcs_test_connect_u2(SCANNER_SERIAL)
reference_device = dcs_test_connect_u2(REFERENCE_SERIAL)

SCRIPT_BASENAME = os.path.splitext(os.path.basename(__file__))[0]
SCRIPT_IMG_DIR = os.path.join(PROJECT_ROOT, "img", SCRIPT_BASENAME)
os.makedirs(SCRIPT_IMG_DIR, exist_ok=True)

SETTINGS_PKG = get_package_name("settings")
KEYREMAP_PKG = get_package_name("keyremap")
EXPECTED_BARCODE = "12345ABCDEF"
MIDDLE_SCAN_TARGET = "MIDDLESCAN"
REFERENCE_IMAGE = os.path.join(PROJECT_ROOT, "files", "images", "scandemo_img", f"{EXPECTED_BARCODE}.jpg")
REFERENCE_REMOTE_PATH = f"/sdcard/Pictures/{EXPECTED_BARCODE}.jpg"


class TestKeyremapHomeToMiddleScan(unittest.TestCase):
	"""L2 test for Honeywell Keyremap: HOME remapped to MIDDLESCAN."""

	@classmethod
	def setUpClass(cls):
		cls.dev_id = SCANNER_SERIAL
		print(f"\n[Setup] Scanner: {SCANNER_SERIAL}; reference: {REFERENCE_SERIAL}")

	def setUp(self):
		dcs_test_wake_and_unlock(SCANNER_SERIAL, d)
		dcs_test_wake_and_unlock(REFERENCE_SERIAL, reference_device)
		d.press("home")
		reference_device.press("home")
		time.sleep(1)

	def tearDown(self):
		if keyremap_open_page(d, SCANNER_SERIAL, SETTINGS_PKG, KEYREMAP_PKG):
			keyremap_clear_all(d, SCANNER_SERIAL)
			# return to the parent page after clearing
			run_adb_cmd(SCANNER_SERIAL, "shell input keyevent KEYCODE_BACK", log_print=False)
			time.sleep(1)

		pid_raw = run_adb_cmd(SCANNER_SERIAL, f"shell pidof {KEYREMAP_PKG}", log_print=False)
		pid_str = (pid_raw.decode("utf-8", errors="ignore") if isinstance(pid_raw, bytes) else str(pid_raw)).strip()
		if pid_str and pid_str.isdigit():
			run_adb_cmd(SCANNER_SERIAL, f"shell kill {pid_str}", log_print=False)
		else:
			print(f"No running process found for {KEYREMAP_PKG}")

		keyremap_force_stop_honeywell_settings(SCANNER_SERIAL)
		close_settings_app(SCANNER_SERIAL)
		d.screen_on()
		d.press("home")
		print(f"[TearDown] Completed: {self.id()}")

	def test_home_key_remapped_to_middle_scan_wedges_barcode(self):
		"""
		L2 Keyremap end-to-end test: HOME -> MIDDLESCAN.
		Step 1: Display the expected barcode on the reference device.
		Step 2: Map the scanner device's virtual HOME key to MIDDLESCAN and
				verify the mapping is saved.
		Step 3: Open and clear launcher Search on the scanner, tap the mapped
				Home key, and verify the reference barcode is entered.
		"""
		print("\n[L2_Keyremap] Testing HOME -> MIDDLESCAN\n" + "=" * 60)

		self.assertTrue(os.path.isfile(REFERENCE_IMAGE), f"Reference image not found: {REFERENCE_IMAGE}")
		dcs_test_prepare_image_on_display_device(
			REFERENCE_SERIAL,
			reference_device,
			REFERENCE_IMAGE,
			REFERENCE_REMOTE_PATH,
		)
		save_step_screenshot(reference_device, "reference_barcode_displayed", SCRIPT_IMG_DIR)

		if not keyremap_open_page(d, SCANNER_SERIAL, SETTINGS_PKG, KEYREMAP_PKG):
			save_step_screenshot(d, "keyremap_navigation_failed", SCRIPT_IMG_DIR)
			self.fail("Could not navigate to Honeywell Settings -> Keyremap")

		keyremap_tap_add_button(d, SCANNER_SERIAL)
		if not keyremap_dialog_is_open(d):
			save_step_screenshot(d, "capture_dialog_not_opened", SCRIPT_IMG_DIR)
			self.fail("'+' did not open the key-capture dialog")

		keyremap_click_virtual_home(SCANNER_SERIAL)
		if not keyremap_tap_ok_button(d, SCANNER_SERIAL):
			save_step_screenshot(d, "home_capture_not_confirmed", SCRIPT_IMG_DIR)
			self.fail("Could not confirm the virtual HOME key capture")
		time.sleep(1)

		if not keyremap_tap_text(d, SCANNER_SERIAL, MIDDLE_SCAN_TARGET, contains=False, max_swipes=10):
			save_step_screenshot(d, "middlescan_not_found", SCRIPT_IMG_DIR)
			self.fail(f"'{MIDDLE_SCAN_TARGET}' was not found in the Keyremap target list")
		time.sleep(1)
		
		if keyremap_find_text_center(d, "MIDDLESCAN", contains=False) is None:
			save_step_screenshot(d, "mapping_not_saved", SCRIPT_IMG_DIR)
			self.fail("MIDDLESCAN mapping was not shown after selecting MIDDLESCAN")
		save_step_screenshot(d, "home_middlescan_mapping_saved", SCRIPT_IMG_DIR)

		press_home_key(SCANNER_SERIAL)
		if not scan_open_input_field(d, SCANNER_SERIAL):
			save_step_screenshot(d, "search_not_opened", SCRIPT_IMG_DIR)
			self.fail("Could not open the launcher Search input field")
		scan_clear_input_field(d)
		save_step_screenshot(d, "search_ready_for_scan", SCRIPT_IMG_DIR)

		keyremap_tap_navbar_home(SCANNER_SERIAL, wait=1, hold_ms=400)
		deadline = time.time() + 10
		scanned_text = ""
		while time.time() < deadline:
			scanned_text = scan_get_input_field_text(d)
			if EXPECTED_BARCODE in scanned_text:
				break
			time.sleep(0.5)

		if EXPECTED_BARCODE not in scanned_text:
			save_step_screenshot(d, "barcode_not_wedged", SCRIPT_IMG_DIR)
			self.fail(
				f"Expected '{EXPECTED_BARCODE}' in Search after the remapped HOME key, "
				f"got '{scanned_text}'"
			)

		save_step_screenshot(d, "barcode_wedged", SCRIPT_IMG_DIR)
		print(f"  HOME -> MIDDLESCAN entered '{EXPECTED_BARCODE}' into Search")


if __name__ == "__main__":
	unittest.main()
