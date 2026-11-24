# -*- coding:utf-8 -*-
"""Test Case: ANDROIDCN-37634 - Verify Full ASCII conversion property for Code 39."""

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
CODE39_IMAGE_LOCAL = os.path.join(PROJECT_ROOT, "files", "images", "dcs_imgs", "Code39_gen_FullASCII_abc.png")
CODE39_IMAGE_REMOTE = "/sdcard/Pictures/Code39_gen_FullASCII_abc.png"

_SCANNING_LABELS = ["Scanning"]
_INTERNAL_SCANNER_LABELS = ["Internal Scanner", "Internal scanner"]
_DEFAULT_PROFILE_LABELS = ["Default profile", "Default Profile"]
_DATA_PROCESSING_LABELS = ["Data Processing Settings", "Data Processing"]
_SYMBOLOGY_LABELS = ["Symbology Settings", "Symbology"]
_CODE_39_LABELS = ["Code 39", "Code39"]
_RAW_ENCODED_VALUE = "+A+B+C"
_FULL_ASCII_DECODED_VALUE = "abc"


def _load_device_serials_from_environment():
    dev0 = (os.environ.get("AUTONEXUS_DEV0_SN") or "").strip()
    dev1 = (os.environ.get("AUTONEXUS_DEV1_SN") or "").strip()
    if not dev0 or not dev1:
        raise RuntimeError("AUTONEXUS_DEV0_SN and AUTONEXUS_DEV1_SN must be provided by the web task")
    return dev0, dev1


DEV0_SERIAL, DEV1_SERIAL = _load_device_serials_from_environment()


class Test_FullASCII_Code39(unittest.TestCase):
    @classmethod
    def _ensure_device_sessions(cls):
        if hasattr(cls, "d0") and hasattr(cls, "d1"):
            return
        if not dcs_test_wait_device_online(DEV0_SERIAL, 25) or not dcs_test_wait_device_online(DEV1_SERIAL, 25):
            raise RuntimeError("Configured Code 39 test devices are offline")
        cls.d0 = dcs_test_connect_u2(DEV0_SERIAL)
        cls.d1 = dcs_test_connect_u2(DEV1_SERIAL)

    @classmethod
    def setUpClass(cls):
        print("\n" + "=" * 70)
        print("ANDROIDCN-37634: Verify Full ASCII conversion property for Code 39")
        print("=" * 70)
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

    def _goto_code39_setting(self):
        dcs_test_goto_symbology_setting(
            DEV0_SERIAL, self.d0, _SCANNING_LABELS, _INTERNAL_SCANNER_LABELS,
            _DEFAULT_PROFILE_LABELS, _SYMBOLOGY_LABELS, _CODE_39_LABELS,
        )

    def _set_full_ascii(self, enabled):
        self._goto_code39_setting()
        self.assertTrue(dcs_test_set_option_checked(self.d0, "Code 39", True), "Failed to enable Code 39")
        self.assertTrue(dcs_test_set_option_checked(self.d0, "Full ASCII conversion", enabled), f"Failed to set Full ASCII conversion={enabled}")

    def _scan_three_times(self, label, expected_value):
        for round_number in range(1, 4):
            dcs_test_prepare_image_on_display_device(DEV1_SERIAL, self.d1, CODE39_IMAGE_LOCAL, CODE39_IMAGE_REMOTE)
            self.assertTrue(scan_open_input_field(self.d0, DEV0_SERIAL), "Failed to focus input field")
            scan_clear_input_field(self.d0)
            self.assertTrue(dcs_test_trigger_honeywell_scan(DEV0_SERIAL), "Scan trigger failed")
            detected = scan_verify_decode_result(self.d0, max_wait_seconds=5)
            value = scan_get_input_field_text(self.d0) if detected else ""
            print(f"  {label} round {round_number}: detected={detected}, value='{value}'")
            self.assertTrue(detected, f"{label} round {round_number}: barcode was not detected")
            self.assertEqual(value, expected_value, f"{label} round {round_number}: unexpected decoded value '{value}'")
            save_step_screenshot(self.d0, f"{label}_round{round_number}", SCRIPT_IMG_DIR)

    def test_full_ascii_code39(self):
        """Test steps:
        1. Open Data Processing Settings and enable Wedge.
        2. Enable Code 39 and Full ASCII conversion; scan a Full-ASCII-shifted fixture ("+A+B+C").
        3. Verify the decoded value is converted to the original lowercase text ("abc").
        4. Disable Full ASCII conversion and scan the same fixture again.
        5. Verify the decoded value is the raw shifted characters ("+A+B+C").
        """
        print("\n[Step 1] Open Data Processing Settings and enable Wedge")
        dcs_test_goto_data_processing_settings(DEV0_SERIAL, self.d0, _SCANNING_LABELS, _INTERNAL_SCANNER_LABELS, _DEFAULT_PROFILE_LABELS, _DATA_PROCESSING_LABELS)
        self.assertTrue(dcs_test_set_option_checked(self.d0, "Wedge", True), "Failed to enable Wedge")

        print("[Step 2] Enable Full ASCII conversion and scan the fixture")
        self._set_full_ascii(True)
        save_step_screenshot(self.d0, "step02_full_ascii_enabled", SCRIPT_IMG_DIR)

        print("[Step 3] Verify the decoded value is converted to lowercase text")
        self._scan_three_times("full_ascii_enabled", _FULL_ASCII_DECODED_VALUE)

        print("[Step 4] Disable Full ASCII conversion and scan the fixture again")
        self._set_full_ascii(False)
        save_step_screenshot(self.d0, "step04_full_ascii_disabled", SCRIPT_IMG_DIR)

        print("[Step 5] Verify the decoded value is the raw shifted characters")
        self._scan_three_times("full_ascii_disabled", _RAW_ENCODED_VALUE)


if __name__ == "__main__":
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(Test_FullASCII_Code39)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)
