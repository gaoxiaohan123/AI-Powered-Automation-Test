# -*- coding:utf-8 -*-
"""Test Case: ANDROIDCN-37601 - Verify Check digit mode property for Code 39."""

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
CODE39_WITHOUT_CHECK_DIGIT_LOCAL = os.path.join(PROJECT_ROOT, "files", "images", "dcs_imgs", "Code39_gen_12345_nocheck.png")
CODE39_WITH_CHECK_DIGIT_LOCAL = os.path.join(PROJECT_ROOT, "files", "images", "dcs_imgs", "Code39_gen_12345_check.png")
CODE39_WITHOUT_CHECK_DIGIT_REMOTE = "/sdcard/Pictures/Code39_gen_12345_nocheck.png"
CODE39_WITH_CHECK_DIGIT_REMOTE = "/sdcard/Pictures/Code39_gen_12345_check.png"

_SCANNING_LABELS = ["Scanning"]
_INTERNAL_SCANNER_LABELS = ["Internal Scanner", "Internal scanner"]
_DEFAULT_PROFILE_LABELS = ["Default profile", "Default Profile"]
_DATA_PROCESSING_LABELS = ["Data Processing Settings", "Data Processing"]
_SYMBOLOGY_LABELS = ["Symbology Settings", "Symbology"]
_CODE_39_LABELS = ["Code 39", "Code39"]
_CHECK_DIGIT_MODE_LABELS = {
    "No check": ["No check", "No check digit"],
    "Check digit": ["Check digit"],
    "Check and strip digit": ["Check and strip digit", "Check and strip check digit"],
}

def _load_device_serials_from_environment():
    dev0 = (os.environ.get("AUTONEXUS_DEV0_SN") or "").strip()
    dev1 = (os.environ.get("AUTONEXUS_DEV1_SN") or "").strip()
    if not dev0 or not dev1:
        raise RuntimeError("AUTONEXUS_DEV0_SN and AUTONEXUS_DEV1_SN must be provided by the web task")
    return dev0, dev1


DEV0_SERIAL, DEV1_SERIAL = _load_device_serials_from_environment()


class Test_CheckDigitMode_Code39(unittest.TestCase):
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
        print("ANDROIDCN-37601: Verify Check digit mode property for Code 39")
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

    def _set_check_digit_mode(self, mode_name):
        self._goto_code39_setting()
        self.assertTrue(dcs_test_set_option_checked(self.d0, "Code 39", True), "Failed to enable Code 39")
        self.assertTrue(self.d0(text="Check digit mode").exists, "Cannot find Check digit mode")
        self.d0(text="Check digit mode").click()
        for label in _CHECK_DIGIT_MODE_LABELS[mode_name]:
            if self.d0(text=label).exists:
                self.d0(text=label).click()
                save_step_screenshot(self.d0, f"set_{mode_name.lower().replace(' ', '_')}", SCRIPT_IMG_DIR)
                return
        self.fail(f"Cannot select Check digit mode '{mode_name}'")

    def _scan_sample(self, image_local, image_remote, state_name, expect_decode):
        values = []
        for round_number in range(1, 4):
            dcs_test_prepare_image_on_display_device(DEV1_SERIAL, self.d1, image_local, image_remote)
            self.assertTrue(scan_open_input_field(self.d0, DEV0_SERIAL), "Failed to focus input field")
            scan_clear_input_field(self.d0)
            self.assertTrue(dcs_test_trigger_honeywell_scan(DEV0_SERIAL), "Scan trigger failed")
            detected = scan_verify_decode_result(self.d0, max_wait_seconds=5)
            value = scan_get_input_field_text(self.d0) if detected else ""
            print(f"  {state_name} round {round_number}: detected={detected}, value='{value}'")
            self.assertEqual(detected, expect_decode, f"{state_name} round {round_number}: unexpected decode state, value='{value}'")
            if expect_decode:
                self.assertTrue(value, f"{state_name} round {round_number}: decoded value is empty")
                values.append(value)
            save_step_screenshot(self.d0, f"{state_name}_round{round_number}", SCRIPT_IMG_DIR)
        return values

    def test_check_digit_mode_code39(self):
        """Test steps:
        1. Open Data Processing Settings and enable Wedge.
        2. Set Code 39 Check digit mode to No check and verify both samples decode as-is.
        3. Set Check digit mode to Check digit and verify the no-digit sample is rejected.
        4. Set Check digit mode to Check and strip digit.
        5. Verify the check digit is removed from the decoded result.
        """
        print("\n[Step 1] Open Data Processing Settings and enable Wedge")
        dcs_test_goto_data_processing_settings(DEV0_SERIAL, self.d0, _SCANNING_LABELS, _INTERNAL_SCANNER_LABELS, _DEFAULT_PROFILE_LABELS, _DATA_PROCESSING_LABELS)
        self.assertTrue(dcs_test_set_option_checked(self.d0, "Wedge", True), "Failed to enable Wedge")

        print("[Step 2] Set Check digit mode to No check and scan both samples")
        self._set_check_digit_mode("No check")
        self._scan_sample(CODE39_WITHOUT_CHECK_DIGIT_LOCAL, CODE39_WITHOUT_CHECK_DIGIT_REMOTE, "no_check_without_digit", True)
        self._scan_sample(CODE39_WITH_CHECK_DIGIT_LOCAL, CODE39_WITH_CHECK_DIGIT_REMOTE, "no_check_with_digit", True)

        print("[Step 3] Set Check digit mode to Check digit")
        self._set_check_digit_mode("Check digit")
        self._scan_sample(CODE39_WITHOUT_CHECK_DIGIT_LOCAL, CODE39_WITHOUT_CHECK_DIGIT_REMOTE, "check_digit_without_digit", False)
        with_digit_values = self._scan_sample(CODE39_WITH_CHECK_DIGIT_LOCAL, CODE39_WITH_CHECK_DIGIT_REMOTE, "check_digit_with_digit", True)

        print("[Step 4] Set Check digit mode to Check and strip digit")
        self._set_check_digit_mode("Check and strip digit")
        self._scan_sample(CODE39_WITHOUT_CHECK_DIGIT_LOCAL, CODE39_WITHOUT_CHECK_DIGIT_REMOTE, "strip_digit_without_digit", False)
        stripped_values = self._scan_sample(CODE39_WITH_CHECK_DIGIT_LOCAL, CODE39_WITH_CHECK_DIGIT_REMOTE, "strip_digit_with_digit", True)

        self.assertTrue(
            all(with_digit_value[:-1] == stripped_value for with_digit_value, stripped_value in zip(with_digit_values, stripped_values)),
            f"Check and strip digit did not remove exactly one check digit. Check digit values: {with_digit_values}; stripped values: {stripped_values}",
        )


if __name__ == "__main__":
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(Test_CheckDigitMode_Code39)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)
