# -*- coding:utf-8 -*-
"""Test Case: ANDROIDCN-37722 - Verify Coupon Code and Combine Coupon Codes for UPC-A."""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from common.adb_common import save_step_screenshot, dcs_test_cleanup_devices, dcs_test_open_honeywell_settings, dcs_test_press_home, dcs_test_prepare_image_on_display_device, dcs_test_trigger_honeywell_scan, dcs_test_wait_device_online, dcs_test_wake_and_unlock
from common.common_method import scan_clear_input_field, scan_get_input_field_text, scan_open_input_field, scan_verify_decode_result, dcs_test_connect_u2, dcs_test_goto_data_processing_settings, dcs_test_scroll_find_and_click, dcs_test_set_option_checked

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.realpath(__file__))))
SCRIPT_BASENAME = os.path.splitext(os.path.basename(__file__))[0]
SCRIPT_IMG_DIR = os.path.join(PROJECT_ROOT, "img", SCRIPT_BASENAME)
os.makedirs(SCRIPT_IMG_DIR, exist_ok=True)
IMAGE_LOCAL = os.path.join(PROJECT_ROOT, "files", "images", "dcs_imgs", "UPC-A_Coupon_Code.jpg")
IMAGE_REMOTE = "/sdcard/Pictures/UPC-A_Coupon_Code.jpg"
_SCANNING = ["Scanning"]
_INTERNAL = ["Internal Scanner", "Internal scanner"]
_PROFILE = ["Default profile", "Default Profile"]
_SYMBOLOGY = ["Symbology Settings", "Symbology"]


def _serials():
    dev0, dev1 = (os.environ.get("AUTONEXUS_DEV0_SN") or "").strip(), (os.environ.get("AUTONEXUS_DEV1_SN") or "").strip()
    if not dev0 or not dev1:
        raise RuntimeError("AUTONEXUS_DEV0_SN and AUTONEXUS_DEV1_SN must be provided by the web task")
    return dev0, dev1


DEV0_SERIAL, DEV1_SERIAL = _serials()


class Test_CouponCodeCombine_UPC_A(unittest.TestCase):
    @classmethod
    def _ensure_device_sessions(cls):
        if hasattr(cls, "d0") and hasattr(cls, "d1"):
            return
        if not dcs_test_wait_device_online(DEV0_SERIAL, 25) or not dcs_test_wait_device_online(DEV1_SERIAL, 25):
            raise RuntimeError("Configured UPC-A test devices are offline")
        cls.d0 = dcs_test_connect_u2(DEV0_SERIAL)
        cls.d1 = dcs_test_connect_u2(DEV1_SERIAL)

    @classmethod
    def setUpClass(cls):
        cls._ensure_device_sessions()

    def setUp(self):
        self.__class__._ensure_device_sessions()
        dcs_test_wake_and_unlock(DEV0_SERIAL, self.d0); dcs_test_wake_and_unlock(DEV1_SERIAL, self.d1)
        dcs_test_press_home(DEV0_SERIAL); dcs_test_press_home(DEV1_SERIAL)

    def tearDown(self):
        dcs_test_cleanup_devices(DEV0_SERIAL, DEV1_SERIAL)
        dcs_test_press_home(DEV0_SERIAL); dcs_test_press_home(DEV1_SERIAL)

    def _goto(self, labels):
        dcs_test_open_honeywell_settings(DEV0_SERIAL)
        for current_labels, description in ((_SCANNING, "Scanning"), (_INTERNAL, "Internal Scanner"), (_PROFILE, "Default profile"), (_SYMBOLOGY, "Symbology Settings"), (labels, labels[0])):
            if not dcs_test_scroll_find_and_click(self.d0, current_labels):
                raise AssertionError(f"Cannot find '{description}'")

    def _set(self, page_labels, label, enabled):
        self._goto(page_labels)
        self.assertTrue(dcs_test_set_option_checked(self.d0, label, enabled), f"Failed to set {label}={enabled}")

    def _verify(self, state_name, expected_value):
        failures = []
        for round_number in range(1, 4):
            dcs_test_prepare_image_on_display_device(DEV1_SERIAL, self.d1, IMAGE_LOCAL, IMAGE_REMOTE)
            self.assertTrue(scan_open_input_field(self.d0, DEV0_SERIAL), "Failed to focus input field")
            scan_clear_input_field(self.d0); self.assertTrue(dcs_test_trigger_honeywell_scan(DEV0_SERIAL), "Scan trigger failed")
            detected = scan_verify_decode_result(self.d0, 5); value = scan_get_input_field_text(self.d0) if detected else ""
            print(f"  {state_name}, round {round_number}: detected={detected}, value='{value}'")
            if not detected or value != expected_value:
                failures.append(f"round {round_number}: detected={detected}, value='{value}'")
            save_step_screenshot(self.d0, f"{state_name}_round{round_number}", SCRIPT_IMG_DIR)
        return failures

    def _verify_independent_outputs(self):
        failures = []
        allowed_values = {"501234567890", "8100049097"}
        for round_number in range(1, 4):
            dcs_test_prepare_image_on_display_device(DEV1_SERIAL, self.d1, IMAGE_LOCAL, IMAGE_REMOTE)
            self.assertTrue(scan_open_input_field(self.d0, DEV0_SERIAL), "Failed to focus input field")
            scan_clear_input_field(self.d0); self.assertTrue(dcs_test_trigger_honeywell_scan(DEV0_SERIAL), "Scan trigger failed")
            detected = scan_verify_decode_result(self.d0, 5); value = scan_get_input_field_text(self.d0) if detected else ""
            print(f"  coupon_and_combine_disabled, round {round_number}: detected={detected}, value='{value}'")
            if not detected or value not in allowed_values:
                failures.append(f"round {round_number}: detected={detected}, value='{value}'")
            save_step_screenshot(self.d0, f"coupon_and_combine_disabled_round{round_number}", SCRIPT_IMG_DIR)
        return failures

    def test_coupon_code_combine_upc_a(self):
        """Test steps:
        1. Open Data Processing Settings and enable Wedge.
        2. Enable UPC-A, Send number system, Send check digit, GS1-128, and Combine Coupon Codes.
        3. Enable Coupon Code and verify the coupon output is combined into one result.
        4. Disable Coupon Code and Combine Coupon Codes.
        5. Verify UPC-A and coupon values are output independently.
        """
        dcs_test_goto_data_processing_settings(DEV0_SERIAL, self.d0, _SCANNING, _INTERNAL, _PROFILE, ["Data Processing Settings", "Data Processing"])
        self.assertTrue(dcs_test_set_option_checked(self.d0, "Wedge", True), "Failed to enable Wedge")
        self._set(["UPC-A", "UPC A"], "Enable UPC-A", True)
        self._set(["UPC-A", "UPC A"], "Send number system", True)
        self._set(["UPC-A", "UPC A"], "Send check digit", True)
        self._set(["GS1-128", "GS1 128"], "GS1-128", True)
        self._set(["UPC-A", "UPC A"], "Combine Coupon Codes", True)
        self._set(["UPC/EAN settings", "UPC EAN settings"], "Coupon Code", True)
        enabled_failures = self._verify("coupon_and_combine_enabled", "5012345678908100049097")
        self._set(["UPC/EAN settings", "UPC EAN settings"], "Coupon Code", False)
        self._set(["UPC-A", "UPC A"], "Combine Coupon Codes", False)
        disabled_failures = self._verify_independent_outputs()
        self.assertFalse(enabled_failures or disabled_failures, f"Coupon combination mismatch. Enabled: {enabled_failures}; Disabled: {disabled_failures}")


if __name__ == "__main__":
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Test_CouponCodeCombine_UPC_A))
    sys.exit(0 if result.wasSuccessful() else 1)