# -*- coding:utf-8 -*-
"""Test Case: ANDROIDCN-37612 - Verify Minimum length property for Han Xin."""

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
HAN_XIN_IMAGE_LOCAL = os.path.join(PROJECT_ROOT, "files", "images", "dcs_imgs", "HanXin_HANXIN12345.png")
HAN_XIN_IMAGE_REMOTE = "/sdcard/Pictures/HanXin_HANXIN12345.png"
HAN_XIN_VALUE = "HANXIN12345"

_SCANNING_LABELS = ["Scanning"]
_INTERNAL_SCANNER_LABELS = ["Internal Scanner", "Internal scanner"]
_DEFAULT_PROFILE_LABELS = ["Default profile", "Default Profile"]
_DATA_PROCESSING_LABELS = ["Data Processing Settings", "Data Processing"]
_SYMBOLOGY_LABELS = ["Symbology Settings", "Symbology"]
_HAN_XIN_LABELS = ["Han Xin", "Han xin"]
_EDIT_RESOURCE_ID = "android:id/edit"
_OK_RESOURCE_ID = "android:id/button1"


def _load_device_serials_from_environment():
    dev0 = (os.environ.get("AUTONEXUS_DEV0_SN") or "").strip()
    dev1 = (os.environ.get("AUTONEXUS_DEV1_SN") or "").strip()
    if not dev0 or not dev1:
        raise RuntimeError("AUTONEXUS_DEV0_SN and AUTONEXUS_DEV1_SN must be provided by the web task")
    return dev0, dev1


DEV0_SERIAL, DEV1_SERIAL = _load_device_serials_from_environment()


class Test_MinimumLength_Han_Xin(unittest.TestCase):
    @classmethod
    def _ensure_device_sessions(cls):
        if hasattr(cls, "d0") and hasattr(cls, "d1"):
            return
        if not dcs_test_wait_device_online(DEV0_SERIAL, 25) or not dcs_test_wait_device_online(DEV1_SERIAL, 25):
            raise RuntimeError("Configured Han Xin test devices are offline")
        cls.d0 = dcs_test_connect_u2(DEV0_SERIAL)
        cls.d1 = dcs_test_connect_u2(DEV1_SERIAL)

    @classmethod
    def setUpClass(cls):
        print("\n" + "=" * 70)
        print("ANDROIDCN-37612: Verify Minimum length property for Han Xin")
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

    def _goto_han_xin_setting(self):
        dcs_test_goto_symbology_setting(
            DEV0_SERIAL, self.d0, _SCANNING_LABELS, _INTERNAL_SCANNER_LABELS,
            _DEFAULT_PROFILE_LABELS, _SYMBOLOGY_LABELS, _HAN_XIN_LABELS,
        )

    def _set_length(self, setting_name, value):
        self.assertTrue(self.d0(text=setting_name).exists, f"Cannot find {setting_name}")
        self.d0(text=setting_name).click()
        edit = self.d0(resourceId=_EDIT_RESOURCE_ID)
        self.assertTrue(edit.exists, f"{setting_name} dialog did not open")
        edit.set_text(str(value))
        self.d0(resourceId=_OK_RESOURCE_ID).click()

    def _scan_han_xin(self, state_name, expect_decode, rounds=3):
        values = []
        for round_number in range(1, rounds + 1):
            dcs_test_prepare_image_on_display_device(DEV1_SERIAL, self.d1, HAN_XIN_IMAGE_LOCAL, HAN_XIN_IMAGE_REMOTE)
            self.assertTrue(scan_open_input_field(self.d0, DEV0_SERIAL), "Failed to focus input field")
            scan_clear_input_field(self.d0)
            self.assertTrue(dcs_test_trigger_honeywell_scan(DEV0_SERIAL), f"Scan trigger failed for {state_name} round {round_number}")
            detected = scan_verify_decode_result(self.d0, max_wait_seconds=5)
            value = scan_get_input_field_text(self.d0) if detected else ""
            print(f"  {state_name} round {round_number}: detected={detected}, value='{value}'")
            self.assertEqual(detected, expect_decode, f"Unexpected Han Xin decode state for {state_name} round {round_number}, value='{value}'")
            self.assertEqual(value, HAN_XIN_VALUE if expect_decode else "", f"Unexpected Han Xin value for {state_name} round {round_number}")
            save_step_screenshot(self.d0, f"{state_name}_round{round_number}", SCRIPT_IMG_DIR)
            values.append(value)
        return values

    def test_minimum_length_han_xin(self):
        """Test steps:
        1. Open Data Processing Settings and enable Wedge.
        2. Enable Han Xin and set Minimum length above the Han Xin sample length.
        3. Verify the sample is rejected three times.
        4. Set Minimum length equal to the Han Xin sample length and verify the exact value decodes three times.
        """
        sample_length = len(HAN_XIN_VALUE)
        print("\n[Step 1] Open Data Processing Settings and enable Wedge")
        dcs_test_goto_data_processing_settings(DEV0_SERIAL, self.d0, _SCANNING_LABELS, _INTERNAL_SCANNER_LABELS, _DEFAULT_PROFILE_LABELS, _DATA_PROCESSING_LABELS)
        self.assertTrue(dcs_test_set_option_checked(self.d0, "Wedge", True), "Failed to enable Wedge")

        print("[Step 2] Enable Han Xin and set Minimum length above the sample length")
        self._goto_han_xin_setting()
        self.assertTrue(dcs_test_set_option_checked(self.d0, "Han Xin", True), "Failed to enable Han Xin")
        self._set_length("Minimum length", sample_length + 1)
        save_step_screenshot(self.d0, "step02_minimum_length_above_sample", SCRIPT_IMG_DIR)

        print("[Step 3] Verify the Han Xin sample shorter than Minimum length is rejected")
        self._scan_han_xin("step03_below_minimum_length", False)

        print("[Step 4] Set Minimum length equal to the sample length and verify exact decode")
        self._goto_han_xin_setting()
        self._set_length("Minimum length", sample_length)
        decoded_values = self._scan_han_xin("step04_at_minimum_length", True)
        self.assertEqual(decoded_values, [HAN_XIN_VALUE] * 3, "Han Xin decoded value changed at the minimum-length boundary")


if __name__ == "__main__":
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(Test_MinimumLength_Han_Xin)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)
