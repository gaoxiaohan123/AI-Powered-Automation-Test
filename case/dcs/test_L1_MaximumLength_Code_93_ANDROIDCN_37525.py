# -*- coding:utf-8 -*-
"""Test Case: ANDROIDCN-37525 - Verify Maximum length property for Code 93."""

import os
import sys
import time
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
CODE93_IMAGE_LOCAL = os.path.join(PROJECT_ROOT, "files", "images", "dcs_imgs", "Code 93.jpg")
CODE93_IMAGE_REMOTE = "/sdcard/Pictures/Code_93.jpg"
# Fixture text "4422457N".
CODE93_EXPECTED_VALUE = "4422457N"

_SCANNING_LABELS = ["Scanning"]
_INTERNAL_SCANNER_LABELS = ["Internal Scanner", "Internal scanner"]
_DEFAULT_PROFILE_LABELS = ["Default profile", "Default Profile"]
_DATA_PROCESSING_LABELS = ["Data Processing Settings", "Data Processing"]
_SYMBOLOGY_LABELS = ["Symbology Settings", "Symbology"]
_CODE93_LABELS = ["Code 93", "Code93"]
_EDIT_RESOURCE_ID = "android:id/edit"
_OK_RESOURCE_ID = "android:id/button1"


def _load_device_serials_from_environment():
    dev0 = (os.environ.get("AUTONEXUS_DEV0_SN") or "").strip()
    dev1 = (os.environ.get("AUTONEXUS_DEV1_SN") or "").strip()
    if not dev0 or not dev1:
        raise RuntimeError("AUTONEXUS_DEV0_SN and AUTONEXUS_DEV1_SN must be provided by the web task")
    return dev0, dev1


DEV0_SERIAL, DEV1_SERIAL = _load_device_serials_from_environment()


class Test_MaximumLength_Code_93(unittest.TestCase):
    @classmethod
    def _ensure_device_sessions(cls):
        if hasattr(cls, "d0") and hasattr(cls, "d1"):
            return
        if not dcs_test_wait_device_online(DEV0_SERIAL, 25) or not dcs_test_wait_device_online(DEV1_SERIAL, 25):
            raise RuntimeError("Configured Code 93 test devices are offline")
        cls.d0 = dcs_test_connect_u2(DEV0_SERIAL)
        cls.d1 = dcs_test_connect_u2(DEV1_SERIAL)

    @classmethod
    def setUpClass(cls):
        print("\n" + "=" * 70)
        print("ANDROIDCN-37525: Verify Maximum length property for Code 93")
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

    def _goto_code93_setting(self):
        dcs_test_goto_symbology_setting(
            DEV0_SERIAL, self.d0, _SCANNING_LABELS, _INTERNAL_SCANNER_LABELS,
            _DEFAULT_PROFILE_LABELS, _SYMBOLOGY_LABELS, _CODE93_LABELS,
        )

    def _set_length(self, setting_name, value):
        self.assertTrue(self.d0(text=setting_name).exists, f"Cannot find {setting_name}")
        self.d0(text=setting_name).click()
        edit = self.d0(resourceId=_EDIT_RESOURCE_ID)
        self.assertTrue(edit.exists, f"{setting_name} dialog did not open")
        edit.set_text(str(value))
        self.d0(resourceId=_OK_RESOURCE_ID).click()

    def _scan_code93(self, state_name, expect_decode, rounds=1):
        values = []
        for round_number in range(1, rounds + 1):
            dcs_test_prepare_image_on_display_device(DEV1_SERIAL, self.d1, CODE93_IMAGE_LOCAL, CODE93_IMAGE_REMOTE)
            self.assertTrue(scan_open_input_field(self.d0, DEV0_SERIAL), "Failed to focus input field")
            scan_clear_input_field(self.d0)
            self.assertTrue(dcs_test_trigger_honeywell_scan(DEV0_SERIAL), f"Scan trigger failed for {state_name} round {round_number}")
            detected = scan_verify_decode_result(self.d0, max_wait_seconds=5)
            value = scan_get_input_field_text(self.d0) if detected else ""
            print(f"  {state_name} round {round_number}: detected={detected}, value='{value}'")
            self.assertEqual(detected, expect_decode, f"Unexpected Code 93 decode state for {state_name} round {round_number}, value='{value}'")
            save_step_screenshot(self.d0, f"{state_name}_round{round_number}", SCRIPT_IMG_DIR)
            values.append(value)
        return values

    def test_maximum_length_code93(self):
        """Test steps:
        1. Open Data Processing Settings and enable Wedge.
        2. Enable Code 93 and identify the valid Code 93 sample length.
        3. Set Maximum length below the sample length and verify the sample is rejected.
        4. Set Maximum length equal to the sample length and verify the sample decodes.
        """
        print("\n[Step 1] Open Data Processing Settings and enable Wedge")
        dcs_test_goto_data_processing_settings(DEV0_SERIAL, self.d0, _SCANNING_LABELS, _INTERNAL_SCANNER_LABELS, _DEFAULT_PROFILE_LABELS, _DATA_PROCESSING_LABELS)
        self.assertTrue(dcs_test_set_option_checked(self.d0, "Wedge", True), "Failed to enable Wedge")

        print("[Step 2] Enable Code 93 and scan the valid fixture")
        self._goto_code93_setting()
        self.assertTrue(dcs_test_set_option_checked(self.d0, "Code 93", True), "Failed to enable Code 93")
        time.sleep(3)
        self._set_length("Minimum length", "1")
        sample_value = self._scan_code93("step02_valid_code93_fixture", True)[0]
        self.assertTrue(sample_value, "Code 93 fixture decoded to an empty value")
        self.assertEqual(sample_value, CODE93_EXPECTED_VALUE, "Code 93 fixture decoded to an unexpected value")
        sample_length = len(sample_value)

        print("[Step 3] Set Maximum length below the Code 93 fixture length")
        self._goto_code93_setting()
        self._set_length("Maximum length", sample_length - 1)
        self._scan_code93("step03_above_maximum_length", False, rounds=3)

        print("[Step 4] Set Maximum length equal to the Code 93 fixture length")
        self._goto_code93_setting()
        self._set_length("Maximum length", sample_length)
        decoded_values = self._scan_code93("step04_at_maximum_length", True, rounds=3)
        self.assertEqual(decoded_values, [sample_value] * 3, "Code 93 decoded value changed at the maximum-length boundary")


if __name__ == "__main__":
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(Test_MaximumLength_Code_93)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)