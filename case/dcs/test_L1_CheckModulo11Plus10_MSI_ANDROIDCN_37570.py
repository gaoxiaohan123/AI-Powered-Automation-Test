# -*- coding:utf-8 -*-
"""Test Case: ANDROIDCN-37570 - Check Modulo 11 plus 10 for MSI."""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from common.adb_common import (
	save_step_screenshot,
	dcs_test_cleanup_devices,
	dcs_test_press_home,
	dcs_test_prepare_image_on_display_device,
	dcs_test_trigger_honeywell_scan,
	dcs_test_wait_device_online,
	dcs_test_wake_and_unlock,
)
from common.common_method import (
	scan_clear_input_field,
	scan_get_input_field_text,
	scan_open_input_field,
	scan_verify_decode_result,
	dcs_test_connect_u2,
	dcs_test_goto_data_processing_settings,
	dcs_test_goto_symbology_setting,
	dcs_test_set_option_checked,
)

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.realpath(__file__))))
SCRIPT_BASENAME = os.path.splitext(os.path.basename(__file__))[0]
SCRIPT_IMG_DIR = os.path.join(PROJECT_ROOT, "img", SCRIPT_BASENAME)
os.makedirs(SCRIPT_IMG_DIR, exist_ok=True)
NO_CHECK_IMAGE_LOCAL = os.path.join(PROJECT_ROOT, "files", "images", "dcs_imgs", "MSI_No_Check_123456.png")
NO_CHECK_IMAGE_REMOTE = "/sdcard/Pictures/MSI_No_Check_123456.png"
MODULO_11_PLUS_10_IMAGE_LOCAL = os.path.join(PROJECT_ROOT, "files", "images", "dcs_imgs", "MSI_Modulo_11_plus_10.JPG")
MODULO_11_PLUS_10_IMAGE_REMOTE = "/sdcard/Pictures/MSI_Modulo_11_plus_10.JPG"
NO_CHECK_VALUE = "123456"
MODULO_11_PLUS_10_VALUE = "123456311"

_SCANNING_LABELS = ["Scanning"]
_INTERNAL_SCANNER_LABELS = ["Internal Scanner", "Internal scanner"]
_DEFAULT_PROFILE_LABELS = ["Default profile", "Default Profile"]
_DATA_PROCESSING_LABELS = ["Data Processing Settings", "Data Processing"]
_SYMBOLOGY_LABELS = ["Symbology Settings", "Symbology"]
_MSI_LABELS = ["MSI"]


def _load_device_serials_from_environment():
	dev0 = (os.environ.get("AUTONEXUS_DEV0_SN") or "").strip()
	dev1 = (os.environ.get("AUTONEXUS_DEV1_SN") or "").strip()
	if not dev0 or not dev1:
		raise RuntimeError("AUTONEXUS_DEV0_SN and AUTONEXUS_DEV1_SN must be provided by the web task")
	return dev0, dev1


DEV0_SERIAL, DEV1_SERIAL = _load_device_serials_from_environment()


class Test_CheckModulo11Plus10_MSI(unittest.TestCase):
	@classmethod
	def _ensure_device_sessions(cls):
		if hasattr(cls, "d0") and hasattr(cls, "d1"):
			return
		if not dcs_test_wait_device_online(DEV0_SERIAL, 25) or not dcs_test_wait_device_online(DEV1_SERIAL, 25):
			raise RuntimeError("Configured MSI test devices are offline")
		cls.d0 = dcs_test_connect_u2(DEV0_SERIAL)
		cls.d1 = dcs_test_connect_u2(DEV1_SERIAL)

	@classmethod
	def setUpClass(cls):
		cls._ensure_device_sessions()

	def setUp(self):
		self.__class__._ensure_device_sessions()
		dcs_test_wake_and_unlock(DEV0_SERIAL, self.d0)
		dcs_test_wake_and_unlock(DEV1_SERIAL, self.d1)
		dcs_test_press_home(DEV0_SERIAL)
		dcs_test_press_home(DEV1_SERIAL)

	def tearDown(self):
		dcs_test_cleanup_devices(DEV0_SERIAL, DEV1_SERIAL)
		dcs_test_press_home(DEV0_SERIAL)
		dcs_test_press_home(DEV1_SERIAL)

	def _set_check_digit_mode(self, labels, screenshot_name):
		dcs_test_goto_symbology_setting(
			DEV0_SERIAL, self.d0, _SCANNING_LABELS, _INTERNAL_SCANNER_LABELS,
			_DEFAULT_PROFILE_LABELS, _SYMBOLOGY_LABELS, _MSI_LABELS,
		)
		self.assertTrue(dcs_test_set_option_checked(self.d0, "MSI", True), "Failed to enable MSI")
		self.assertTrue(self.d0(text="Check digit mode").exists, "Cannot find Check digit mode")
		self.d0(text="Check digit mode").click()
		for label in labels:
			if self.d0(text=label).exists:
				self.d0(text=label).click()
				self.d0.press("back")
				dcs_test_goto_symbology_setting(
					DEV0_SERIAL, self.d0, _SCANNING_LABELS, _INTERNAL_SCANNER_LABELS,
					_DEFAULT_PROFILE_LABELS, _SYMBOLOGY_LABELS, _MSI_LABELS,
				)
				save_step_screenshot(self.d0, screenshot_name, SCRIPT_IMG_DIR)
				return
		self.fail(f"Cannot select MSI check digit mode from: {labels}")

	def _scan_sample(self, image_local, image_remote, expected_value, state_name):
		values = []
		for round_number in range(1, 4):
			dcs_test_prepare_image_on_display_device(DEV1_SERIAL, self.d1, image_local, image_remote)
			self.assertTrue(scan_open_input_field(self.d0, DEV0_SERIAL), "Failed to focus input field")
			scan_clear_input_field(self.d0)
			self.assertTrue(dcs_test_trigger_honeywell_scan(DEV0_SERIAL), "Scan trigger failed")
			detected = scan_verify_decode_result(self.d0, max_wait_seconds=5)
			value = scan_get_input_field_text(self.d0) if detected else ""
			print(f"  {state_name} round {round_number}: detected={detected}, value='{value}'")
			self.assertTrue(detected, f"{state_name} round {round_number}: MSI barcode was not decoded")
			self.assertEqual(value, expected_value, f"{state_name} round {round_number}: unexpected decoded value")
			save_step_screenshot(self.d0, f"{state_name}_round{round_number}", SCRIPT_IMG_DIR)
			values.append(value)
		return values

	def test_check_modulo_11_plus_10_msi(self):
		"""Test steps:
		1. Enable Wedge for keyboard output.
		2. Select No check and scan the no-check MSI fixture three times.
		3. Select Check modulo 11 plus 10 and scan its matching fixture three times.
		4. Verify both modes return their exact expected values.
		"""
		print("\n[Step 1] Open Data Processing Settings and enable Wedge")
		dcs_test_goto_data_processing_settings(
			DEV0_SERIAL, self.d0, _SCANNING_LABELS, _INTERNAL_SCANNER_LABELS,
			_DEFAULT_PROFILE_LABELS, _DATA_PROCESSING_LABELS,
		)
		self.assertTrue(dcs_test_set_option_checked(self.d0, "Wedge", True), "Failed to enable Wedge")

		print("[Step 2] Select No check and scan the no-check MSI fixture")
		self._set_check_digit_mode(["No check", "No check digit"], "step02_no_check")
		no_check_values = self._scan_sample(
			NO_CHECK_IMAGE_LOCAL, NO_CHECK_IMAGE_REMOTE, NO_CHECK_VALUE, "step02_no_check",
		)

		print("[Step 3] Select Check modulo 11 plus 10 and scan its MSI fixture")
		self._set_check_digit_mode(
			["Check modulo 11 plus 10", "Check Modulo 11 plus 10"], "step03_check_modulo_11_plus_10",
		)
		checked_values = self._scan_sample(
			MODULO_11_PLUS_10_IMAGE_LOCAL, MODULO_11_PLUS_10_IMAGE_REMOTE,
			MODULO_11_PLUS_10_VALUE, "step03_modulo_11_plus_10",
		)
		self.assertEqual(no_check_values, [NO_CHECK_VALUE] * 3)
		self.assertEqual(checked_values, [MODULO_11_PLUS_10_VALUE] * 3)


if __name__ == "__main__":
	suite = unittest.defaultTestLoader.loadTestsFromTestCase(Test_CheckModulo11Plus10_MSI)
	result = unittest.TextTestRunner(verbosity=2).run(suite)
	sys.exit(0 if result.wasSuccessful() else 1)
