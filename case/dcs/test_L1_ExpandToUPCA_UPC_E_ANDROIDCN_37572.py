# -*- coding:utf-8 -*-
"""Test Case: ANDROIDCN-37572 - Verify Expand to UPC-A property for UPC-E."""

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
UPC_E_IMAGE_LOCAL = os.path.join(PROJECT_ROOT, "files", "images", "dcs_imgs", "UPC-E.jpg")
UPC_E_IMAGE_REMOTE = "/sdcard/Pictures/UPC-E.jpg"
UPC_E_EXPANDED_TO_UPC_A = "01234500006"
UPC_E_NOT_EXPANDED = "0123456"

SCRIPT_BASENAME = os.path.splitext(os.path.basename(__file__))[0]
SCRIPT_IMG_DIR = os.path.join(PROJECT_ROOT, "img", SCRIPT_BASENAME)
os.makedirs(SCRIPT_IMG_DIR, exist_ok=True)

_SCANNING_LABELS = ["Scanning"]
_INTERNAL_SCANNER_LABELS = ["Internal Scanner", "Internal scanner"]
_DEFAULT_PROFILE_LABELS = ["Default profile", "Default Profile"]
_DATA_PROCESSING_LABELS = ["Data Processing Settings", "Data Processing"]
_SYMBOLOGY_LABELS = ["Symbology Settings", "Symbology"]
_UPC_E_LABELS = ["UPC-E", "UPC E"]


def _load_device_serials_from_environment():
    dev0 = (os.environ.get("AUTONEXUS_DEV0_SN") or "").strip()
    dev1 = (os.environ.get("AUTONEXUS_DEV1_SN") or "").strip()
    if not dev0 or not dev1:
        raise RuntimeError("AUTONEXUS_DEV0_SN and AUTONEXUS_DEV1_SN must be provided by the web task")
    return dev0, dev1


DEV0_SERIAL, DEV1_SERIAL = _load_device_serials_from_environment()


class Test_ExpandToUPCA_UPC_E(unittest.TestCase):

    @classmethod
    def _ensure_device_sessions(cls):
        if hasattr(cls, "d0") and hasattr(cls, "d1"):
            return
        if not dcs_test_wait_device_online(DEV0_SERIAL, 25) or not dcs_test_wait_device_online(DEV1_SERIAL, 25):
            raise RuntimeError("Configured UPC-E test devices are offline")
        cls.d0 = dcs_test_connect_u2(DEV0_SERIAL)
        cls.d1 = dcs_test_connect_u2(DEV1_SERIAL)

    @classmethod
    def setUpClass(cls):
        print("\n" + "=" * 70)
        print("ANDROIDCN-37572: Verify Expand to UPC-A property for UPC-E")
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

    def _goto_upc_e_setting(self):
        dcs_test_goto_symbology_setting(
            DEV0_SERIAL, self.d0, _SCANNING_LABELS, _INTERNAL_SCANNER_LABELS,
            _DEFAULT_PROFILE_LABELS, _SYMBOLOGY_LABELS, _UPC_E_LABELS,
        )

    def _scan_expected_value(self, expected_value, state_name, screenshot_prefix):
        failures = []
        for round_number in range(1, 4):
            scan_clear_input_field(self.d0)
            self.assertTrue(
                dcs_test_trigger_honeywell_scan(DEV0_SERIAL),
                f"Scan trigger failed with Expand to UPC-A {state_name}, round {round_number}",
            )
            detected = scan_verify_decode_result(self.d0, max_wait_seconds=6)
            value = scan_get_input_field_text(self.d0) if detected else ""
            print(f"  Expand to UPC-A {state_name}, round {round_number}: detected={detected}, value='{value}'")
            if not detected or value != expected_value:
                failures.append(f"Round {round_number}: detected={detected}, value='{value}'")
            save_step_screenshot(self.d0, f"{screenshot_prefix}_round{round_number}", SCRIPT_IMG_DIR)
        return failures

    def test_expand_to_upc_a_upc_e(self):
        """Test steps:
        1. Enable Wedge in Data Processing Settings.
        2. Enable UPC-E and Expand to UPC-A; keep Send check digit and Add-on required disabled.
        3. Display the UPC-E reference barcode and scan it three times; verify the decoded value is expanded to UPC-A.
        4. Disable Expand to UPC-A.
        5. Scan the same barcode three times; verify the decoded value remains in UPC-E format.
        """
        print("\n[Step 1] Open Data Processing Settings and enable Wedge")
        dcs_test_goto_data_processing_settings(
            DEV0_SERIAL, self.d0, _SCANNING_LABELS, _INTERNAL_SCANNER_LABELS,
            _DEFAULT_PROFILE_LABELS, _DATA_PROCESSING_LABELS,
        )
        self.assertTrue(dcs_test_set_option_checked(self.d0, "Wedge", True), "Failed to enable Wedge")
        save_step_screenshot(self.d0, "step01_enable_wedge", SCRIPT_IMG_DIR)

        print("[Step 2] Enable UPC-E and Expand to UPC-A")
        self._goto_upc_e_setting()
        for label, enabled in (("UPC-E", True), ("Send number system", True), ("Send check digit", False),
                       ("Add-on required", False), ("Expand to UPC-A", True)):
            self.assertTrue(dcs_test_set_option_checked(self.d0, label, enabled), f"Failed to set {label}={enabled}")
        save_step_screenshot(self.d0, "step02_expand_enabled", SCRIPT_IMG_DIR)

        print("[Step 3] Prepare UPC-E image and verify it expands to UPC-A")
        dcs_test_prepare_image_on_display_device(DEV1_SERIAL, self.d1, UPC_E_IMAGE_LOCAL, UPC_E_IMAGE_REMOTE)
        self.assertTrue(scan_open_input_field(self.d0, DEV0_SERIAL), "Failed to open an input field")
        expanded_failures = self._scan_expected_value(
            UPC_E_EXPANDED_TO_UPC_A, "enabled", "step03_expand_enabled"
        )

        print("[Step 4] Disable Expand to UPC-A")
        self._goto_upc_e_setting()
        self.assertTrue(
            dcs_test_set_option_checked(self.d0, "Expand to UPC-A", False),
            "Failed to disable Expand to UPC-A",
        )
        save_step_screenshot(self.d0, "step04_expand_disabled", SCRIPT_IMG_DIR)

        print("[Step 5] Verify UPC-E output is not expanded")
        self.assertTrue(scan_open_input_field(self.d0, DEV0_SERIAL), "Failed to reopen an input field")
        unexpanded_failures = self._scan_expected_value(
            UPC_E_NOT_EXPANDED, "disabled", "step05_expand_disabled"
        )

        self.assertFalse(
            expanded_failures or unexpanded_failures,
            f"Expand to UPC-A behavior mismatch. Expanded failures: {expanded_failures}; "
            f"Not expanded failures: {unexpanded_failures}",
        )


if __name__ == "__main__":
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(Test_ExpandToUPCA_UPC_E)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)