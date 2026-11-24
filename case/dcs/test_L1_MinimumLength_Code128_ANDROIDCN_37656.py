# -*- coding:utf-8 -*-
"""Test Case: ANDROIDCN-37656 - Verify Minimum length property for Code 128."""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from common.adb_common import dcs_test_cleanup_devices, dcs_test_prepare_image_on_display_device, dcs_test_press_home, dcs_test_trigger_honeywell_scan, dcs_test_wait_device_online, dcs_test_wake_and_unlock, save_step_screenshot
from common.common_method import dcs_test_connect_u2, dcs_test_goto_data_processing_settings, dcs_test_goto_symbology_setting, dcs_test_set_option_checked, scan_clear_input_field, scan_get_input_field_text, scan_open_input_field, scan_verify_decode_result

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.realpath(__file__))))
SCRIPT_IMG_DIR = os.path.join(PROJECT_ROOT, "img", os.path.splitext(os.path.basename(__file__))[0])
os.makedirs(SCRIPT_IMG_DIR, exist_ok=True)
IMAGE_LOCAL = os.path.join(PROJECT_ROOT, "files", "images", "dcs_imgs", "Code 128.jpg")
IMAGE_REMOTE = "/sdcard/Pictures/Code 128.jpg"
_SCANNING_LABELS = ["Scanning"]
_INTERNAL_SCANNER_LABELS = ["Internal Scanner", "Internal scanner"]
_DEFAULT_PROFILE_LABELS = ["Default profile", "Default Profile"]
_DATA_PROCESSING_LABELS = ["Data Processing Settings", "Data Processing"]
_SYMBOLOGY_LABELS = ["Symbology Settings", "Symbology"]
_CODE128_LABELS = ["Code 128", "Code128", "CODE 128"]
_EDIT_RESOURCE_ID = "android:id/edit"
_OK_RESOURCE_ID = "android:id/button1"


def _load_device_serials():
    dev0, dev1 = (os.environ.get("AUTONEXUS_DEV0_SN") or "").strip(), (os.environ.get("AUTONEXUS_DEV1_SN") or "").strip()
    if not dev0 or not dev1:
        raise RuntimeError("AUTONEXUS_DEV0_SN and AUTONEXUS_DEV1_SN must be provided by the web task")
    return dev0, dev1


DEV0_SERIAL, DEV1_SERIAL = _load_device_serials()


class Test_MinimumLength_Code128(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not dcs_test_wait_device_online(DEV0_SERIAL, 25) or not dcs_test_wait_device_online(DEV1_SERIAL, 25):
            raise RuntimeError("Configured Code 128 test devices are offline")
        cls.d0, cls.d1 = dcs_test_connect_u2(DEV0_SERIAL), dcs_test_connect_u2(DEV1_SERIAL)

    def setUp(self):
        if not hasattr(self.__class__, "d0"):
            self.__class__.setUpClass()
        dcs_test_wake_and_unlock(DEV0_SERIAL, self.d0); dcs_test_wake_and_unlock(DEV1_SERIAL, self.d1)
        dcs_test_press_home(DEV0_SERIAL); dcs_test_press_home(DEV1_SERIAL)

    def tearDown(self):
        dcs_test_cleanup_devices(DEV0_SERIAL, DEV1_SERIAL)
        dcs_test_press_home(DEV0_SERIAL); dcs_test_press_home(DEV1_SERIAL)

    def _goto_code128(self):
        dcs_test_goto_symbology_setting(DEV0_SERIAL, self.d0, _SCANNING_LABELS, _INTERNAL_SCANNER_LABELS, _DEFAULT_PROFILE_LABELS, _SYMBOLOGY_LABELS, _CODE128_LABELS)

    def _set_minimum(self, value):
        self._goto_code128(); self.d0(text="Minimum length").click()
        self.d0(resourceId=_EDIT_RESOURCE_ID).set_text(str(value)); self.d0(resourceId=_OK_RESOURCE_ID).click()

    def _scan_three_times(self, label, expect_decode):
        for round_number in range(1, 4):
            dcs_test_prepare_image_on_display_device(DEV1_SERIAL, self.d1, IMAGE_LOCAL, IMAGE_REMOTE)
            self.assertTrue(scan_open_input_field(self.d0, DEV0_SERIAL), "Failed to focus input field")
            scan_clear_input_field(self.d0); self.assertTrue(dcs_test_trigger_honeywell_scan(DEV0_SERIAL), "Scan trigger failed")
            detected = scan_verify_decode_result(self.d0, max_wait_seconds=5)
            value = scan_get_input_field_text(self.d0) if detected else ""
            print(f"  {label} round {round_number}: detected={detected}, value='{value}'")
            self.assertEqual(detected, expect_decode, f"{label} round {round_number}: unexpected decode state")
            if expect_decode: self.assertEqual(len(value), 20, f"{label} round {round_number}: expected 20 characters")
            save_step_screenshot(self.d0, f"{label}_round{round_number}", SCRIPT_IMG_DIR)

    def test_minimum_length_code128(self):
        """Test steps:
        1. Open Data Processing Settings and enable Wedge output.
        2. Navigate to Code 128 settings and enable Code 128.
        3. Set Minimum length to 21 and scan the 20-character reference barcode three times; verify rejection.
        4. Set Minimum length to 20 and scan the same barcode three times; verify successful decoding at the boundary.
        """
        dcs_test_goto_data_processing_settings(DEV0_SERIAL, self.d0, _SCANNING_LABELS, _INTERNAL_SCANNER_LABELS, _DEFAULT_PROFILE_LABELS, _DATA_PROCESSING_LABELS)
        self.assertTrue(dcs_test_set_option_checked(self.d0, "Wedge", True), "Failed to enable Wedge")
        self._goto_code128(); self.assertTrue(dcs_test_set_option_checked(self.d0, "Code 128", True), "Failed to enable Code 128")
        self._set_minimum(21); save_step_screenshot(self.d0, "step03_minimum_length_21", SCRIPT_IMG_DIR)
        self._scan_three_times("step05_below_minimum", False)
        self._set_minimum(20); save_step_screenshot(self.d0, "step06_minimum_length_20", SCRIPT_IMG_DIR)
        self._scan_three_times("step06_at_minimum", True)


if __name__ == "__main__":
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(Test_MinimumLength_Code128)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)