# -*- coding:utf-8 -*-
"""Test Case: ANDROIDCN-37468 - Verify Coupon Code property for UPC-A."""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from common.adb_common import (
    save_step_screenshot,
    dcs_test_cleanup_devices,
    dcs_test_open_honeywell_settings,
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
    dcs_test_scroll_find_and_click,
    dcs_test_set_option_checked,
)

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.realpath(__file__))))
SCRIPT_BASENAME = os.path.splitext(os.path.basename(__file__))[0]
SCRIPT_IMG_DIR = os.path.join(PROJECT_ROOT, "img", SCRIPT_BASENAME)
os.makedirs(SCRIPT_IMG_DIR, exist_ok=True)

COUPON_IMAGE_FILENAME = "UPC-A_Coupon_Code.jpg"
COUPON_IMAGE_LOCAL = os.path.join(PROJECT_ROOT, "files", "images", "dcs_imgs", COUPON_IMAGE_FILENAME)
COUPON_IMAGE_REMOTE = f"/sdcard/Pictures/{COUPON_IMAGE_FILENAME}"
UPC_A_VALUE = "501234567890"
COUPON_CODE_VALUE = "8100049097"
_SCANNING_LABELS = ["Scanning"]
_INTERNAL_SCANNER_LABELS = ["Internal Scanner", "Internal scanner"]
_DEFAULT_PROFILE_LABELS = ["Default profile", "Default Profile"]
_DATA_PROCESSING_LABELS = ["Data Processing Settings", "Data Processing"]
_SYMBOLOGY_LABELS = ["Symbology Settings", "Symbology"]
_UPC_A_LABELS = ["UPC-A", "UPC A"]
_UPC_EAN_LABELS = ["UPC/EAN settings", "UPC EAN settings"]
_GS1_128_LABELS = ["GS1-128", "GS1 128"]


def _load_device_serials_from_environment():
    dev0 = (os.environ.get("AUTONEXUS_DEV0_SN") or "").strip()
    dev1 = (os.environ.get("AUTONEXUS_DEV1_SN") or "").strip()
    if not dev0 or not dev1:
        raise RuntimeError("AUTONEXUS_DEV0_SN and AUTONEXUS_DEV1_SN must be provided by the web task")
    return dev0, dev1


DEV0_SERIAL, DEV1_SERIAL = _load_device_serials_from_environment()


class Test_CouponCode_UPC_A(unittest.TestCase):
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
        print("\n" + "=" * 70)
        print("ANDROIDCN-37468: Verify Coupon Code property for UPC-A")
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

    def _goto_symbology_option(self, option_labels):
        dcs_test_open_honeywell_settings(DEV0_SERIAL)
        for labels, description in (
            (_SCANNING_LABELS, "Scanning"),
            (_INTERNAL_SCANNER_LABELS, "Internal Scanner"),
            (_DEFAULT_PROFILE_LABELS, "Default profile"),
            (_SYMBOLOGY_LABELS, "Symbology Settings"),
            (option_labels, option_labels[0]),
        ):
            if not dcs_test_scroll_find_and_click(self.d0, labels):
                raise AssertionError(f"Cannot find '{description}'")

    def _goto_upc_a_setting(self):
        dcs_test_goto_symbology_setting(
            DEV0_SERIAL, self.d0, _SCANNING_LABELS, _INTERNAL_SCANNER_LABELS,
            _DEFAULT_PROFILE_LABELS, _SYMBOLOGY_LABELS, _UPC_A_LABELS,
        )

    def _verify_coupon_output(self, coupon_enabled, expected_value):
        failures = []
        for round_number in range(1, 4):
            dcs_test_prepare_image_on_display_device(
                DEV1_SERIAL, self.d1, COUPON_IMAGE_LOCAL, COUPON_IMAGE_REMOTE
            )
            self.assertTrue(scan_open_input_field(self.d0, DEV0_SERIAL), "Failed to focus input field")
            scan_clear_input_field(self.d0)
            self.assertTrue(dcs_test_trigger_honeywell_scan(DEV0_SERIAL), "Scan trigger failed")
            detected = scan_verify_decode_result(self.d0, max_wait_seconds=5)
            value = scan_get_input_field_text(self.d0) if detected else ""
            print(
                f"  Coupon Code={coupon_enabled}, round {round_number}: "
                f"detected={detected}, value='{value}'"
            )
            if not detected or value != expected_value:
                failures.append(f"round {round_number}: detected={detected}, value='{value}'")
            save_step_screenshot(self.d0, f"coupon_{coupon_enabled}_round{round_number}", SCRIPT_IMG_DIR)
        return failures

    def _verify_independent_coupon_outputs(self):
        failures = []
        allowed_values = {UPC_A_VALUE, COUPON_CODE_VALUE}
        for round_number in range(1, 4):
            dcs_test_prepare_image_on_display_device(
                DEV1_SERIAL, self.d1, COUPON_IMAGE_LOCAL, COUPON_IMAGE_REMOTE
            )
            self.assertTrue(scan_open_input_field(self.d0, DEV0_SERIAL), "Failed to focus input field")
            scan_clear_input_field(self.d0)
            self.assertTrue(dcs_test_trigger_honeywell_scan(DEV0_SERIAL), "Scan trigger failed")
            detected = scan_verify_decode_result(self.d0, max_wait_seconds=5)
            value = scan_get_input_field_text(self.d0) if detected else ""
            print(f"  Coupon Code=False, round {round_number}: detected={detected}, value='{value}'")
            if not detected or value not in allowed_values:
                failures.append(f"round {round_number}: detected={detected}, value='{value}'")
            save_step_screenshot(self.d0, f"coupon_False_round{round_number}", SCRIPT_IMG_DIR)
        return failures

    def test_coupon_code_upc_a(self):
        """Test steps:
        1. Open Data Processing Settings and enable Wedge.
        2. Enable UPC-A and GS1-128.
        3. Enable Coupon Code and verify the UPC-A result.
        4. Disable Coupon Code.
        5. Verify the UPC-A and coupon values are output independently.
        """
        print("\n[Step 1] Open Data Processing Settings and enable Wedge")
        dcs_test_goto_data_processing_settings(
            DEV0_SERIAL, self.d0, _SCANNING_LABELS, _INTERNAL_SCANNER_LABELS,
            _DEFAULT_PROFILE_LABELS, _DATA_PROCESSING_LABELS,
        )
        self.assertTrue(dcs_test_set_option_checked(self.d0, "Wedge", True), "Failed to enable Wedge")
        save_step_screenshot(self.d0, "step01_enable_wedge", SCRIPT_IMG_DIR)

        print("[Step 2] Enable UPC-A and GS1-128")
        self._goto_upc_a_setting()
        for label, enabled in (("Enable UPC-A", True), ("Send number system", True), ("Send check digit", True)):
            self.assertTrue(dcs_test_set_option_checked(self.d0, label, enabled), f"Failed to set {label}={enabled}")
        self._goto_symbology_option(_GS1_128_LABELS)
        self.assertTrue(dcs_test_set_option_checked(self.d0, "GS1-128", True), "Failed to enable GS1-128")
        save_step_screenshot(self.d0, "step02_enable_upc_a_gs1_128", SCRIPT_IMG_DIR)

        print("[Step 3] Enable Coupon Code and verify the UPC-A result")
        self._goto_upc_a_setting()
        self.assertTrue(dcs_test_set_option_checked(self.d0, "Combine Coupon Codes", False), "Failed to disable Combine Coupon Codes")
        self._goto_symbology_option(_UPC_EAN_LABELS)
        self.assertTrue(dcs_test_set_option_checked(self.d0, "Coupon Code", True), "Failed to enable Coupon Code")
        save_step_screenshot(self.d0, "step03_coupon_enabled", SCRIPT_IMG_DIR)
        enabled_failures = self._verify_coupon_output(True, UPC_A_VALUE)

        print("[Step 4] Disable Coupon Code and verify both independent results")
        self._goto_symbology_option(_UPC_EAN_LABELS)
        self.assertTrue(dcs_test_set_option_checked(self.d0, "Coupon Code", False), "Failed to disable Coupon Code")
        save_step_screenshot(self.d0, "step04_coupon_disabled", SCRIPT_IMG_DIR)
        disabled_failures = self._verify_independent_coupon_outputs()

        self.assertFalse(
            enabled_failures or disabled_failures,
            f"Coupon Code behavior mismatch. Enabled failures: {enabled_failures}; "
            f"Disabled failures: {disabled_failures}",
        )


if __name__ == "__main__":
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(Test_CouponCode_UPC_A)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)