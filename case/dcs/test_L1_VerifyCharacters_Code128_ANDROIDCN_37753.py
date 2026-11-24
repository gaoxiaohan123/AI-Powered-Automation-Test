# -*- coding:utf-8 -*-
"""Test Case: ANDROIDCN-37753 - Verify Code 128 character compositions."""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from common.adb_common import (
    dcs_test_cleanup_devices,
    dcs_test_prepare_image_on_display_device,
    dcs_test_press_home,
    dcs_test_trigger_honeywell_scan,
    dcs_test_wait_device_online,
    dcs_test_wake_and_unlock,
    save_step_screenshot,
)
from common.common_method import (
    dcs_test_connect_u2,
    dcs_test_goto_data_processing_settings,
    dcs_test_goto_symbology_setting,
    dcs_test_set_option_checked,
    scan_clear_input_field,
    scan_get_input_field_text,
    scan_open_input_field,
    scan_verify_decode_result,
)

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.realpath(__file__))))
SCRIPT_IMG_DIR = os.path.join(PROJECT_ROOT, "img", os.path.splitext(os.path.basename(__file__))[0])
os.makedirs(SCRIPT_IMG_DIR, exist_ok=True)
FIXTURES = (
    ("numbers", "Code128_num.png", "1234567"),
    ("letters", "Code128_Pure_letters.png", "abCDEF"),
    ("alphanumeric", "Code 128.jpg", "5C728G22802860I1GXTB"),
)
_SCANNING_LABELS = ["Scanning"]
_INTERNAL_SCANNER_LABELS = ["Internal Scanner", "Internal scanner"]
_DEFAULT_PROFILE_LABELS = ["Default profile", "Default Profile"]
_DATA_PROCESSING_LABELS = ["Data Processing Settings", "Data Processing"]
_SYMBOLOGY_LABELS = ["Symbology Settings", "Symbology"]
_CODE128_LABELS = ["Code 128", "Code128", "CODE 128"]


def _load_device_serials():
    dev0 = (os.environ.get("AUTONEXUS_DEV0_SN") or "").strip()
    dev1 = (os.environ.get("AUTONEXUS_DEV1_SN") or "").strip()
    if not dev0 or not dev1:
        raise RuntimeError("AUTONEXUS_DEV0_SN and AUTONEXUS_DEV1_SN must be provided by the web task")
    return dev0, dev1


DEV0_SERIAL, DEV1_SERIAL = _load_device_serials()


class Test_VerifyCharacters_Code128(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not dcs_test_wait_device_online(DEV0_SERIAL, 25) or not dcs_test_wait_device_online(DEV1_SERIAL, 25):
            raise RuntimeError("Configured Code 128 test devices are offline")
        cls.d0 = dcs_test_connect_u2(DEV0_SERIAL)
        cls.d1 = dcs_test_connect_u2(DEV1_SERIAL)

    def setUp(self):
        if not hasattr(self.__class__, "d0"):
            self.__class__.setUpClass()
        dcs_test_wake_and_unlock(DEV0_SERIAL, self.d0)
        dcs_test_wake_and_unlock(DEV1_SERIAL, self.d1)
        dcs_test_press_home(DEV0_SERIAL)
        dcs_test_press_home(DEV1_SERIAL)

    def tearDown(self):
        dcs_test_cleanup_devices(DEV0_SERIAL, DEV1_SERIAL)
        dcs_test_press_home(DEV0_SERIAL)
        dcs_test_press_home(DEV1_SERIAL)

    def _goto_code128(self):
        dcs_test_goto_symbology_setting(DEV0_SERIAL, self.d0, _SCANNING_LABELS, _INTERNAL_SCANNER_LABELS, _DEFAULT_PROFILE_LABELS, _SYMBOLOGY_LABELS, _CODE128_LABELS)

    def _scan_fixture(self, fixture_name, filename, expected_value):
        local_path = os.path.join(PROJECT_ROOT, "files", "images", "dcs_imgs", filename)
        remote_path = f"/sdcard/Pictures/{filename}"
        for round_number in range(1, 4):
            dcs_test_prepare_image_on_display_device(DEV1_SERIAL, self.d1, local_path, remote_path)
            self.assertTrue(scan_open_input_field(self.d0, DEV0_SERIAL), "Failed to focus input field")
            scan_clear_input_field(self.d0)
            self.assertTrue(dcs_test_trigger_honeywell_scan(DEV0_SERIAL), "Scan trigger failed")
            self.assertTrue(scan_verify_decode_result(self.d0, max_wait_seconds=5), f"{fixture_name} round {round_number}: barcode did not decode")
            value = scan_get_input_field_text(self.d0)
            print(f"  {fixture_name} round {round_number}: value='{value}'")
            self.assertEqual(value, expected_value, f"{fixture_name} round {round_number}: unexpected Code 128 data")
            save_step_screenshot(self.d0, f"{fixture_name}_round{round_number}", SCRIPT_IMG_DIR)

    def test_code128_characters(self):
        """Test steps:
        1. Open Data Processing Settings and enable Wedge output.
        2. Navigate to Code 128 settings and enable Code 128.
        3. Scan the numeric Code 128 reference barcode three times and verify its expected data.
        4. Scan the alphabetic Code 128 reference barcode three times and verify its expected data.
        5. Scan the alphanumeric Code 128 reference barcode three times and verify its expected data.
        """
        dcs_test_goto_data_processing_settings(DEV0_SERIAL, self.d0, _SCANNING_LABELS, _INTERNAL_SCANNER_LABELS, _DEFAULT_PROFILE_LABELS, _DATA_PROCESSING_LABELS)
        self.assertTrue(dcs_test_set_option_checked(self.d0, "Wedge", True), "Failed to enable Wedge")
        self._goto_code128()
        self.assertTrue(dcs_test_set_option_checked(self.d0, "Code 128", True), "Failed to enable Code 128")
        save_step_screenshot(self.d0, "step03_code128_enabled", SCRIPT_IMG_DIR)
        for fixture in FIXTURES:
            self._scan_fixture(*fixture)


if __name__ == "__main__":
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(Test_VerifyCharacters_Code128)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)