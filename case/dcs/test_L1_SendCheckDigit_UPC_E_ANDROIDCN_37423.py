# -*- coding:utf-8 -*-
"""
Test Case: ANDROIDCN-37423
Case Name: Verify Send check digit property for UPC-E
"""

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
UPC_E_WITH_CHECK_DIGIT = "01234565"
UPC_E_WITHOUT_CHECK_DIGIT = "0123456"

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


class Test_SendCheckDigit_UPC_E(unittest.TestCase):

    @classmethod
    def _ensure_device_sessions(cls):
        if hasattr(cls, "d0") and hasattr(cls, "d1"):
            return
        if not dcs_test_wait_device_online(DEV0_SERIAL, timeout_seconds=25):
            raise RuntimeError(f"dev0 offline: {DEV0_SERIAL}")
        if not dcs_test_wait_device_online(DEV1_SERIAL, timeout_seconds=25):
            raise RuntimeError(f"dev1 offline: {DEV1_SERIAL}")
        cls.d0 = dcs_test_connect_u2(DEV0_SERIAL)
        cls.d1 = dcs_test_connect_u2(DEV1_SERIAL)

    @classmethod
    def setUpClass(cls):
        print("\n" + "=" * 70)
        print("ANDROIDCN-37423: Verify Send check digit property for UPC-E")
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
            DEV0_SERIAL,
            self.d0,
            _SCANNING_LABELS,
            _INTERNAL_SCANNER_LABELS,
            _DEFAULT_PROFILE_LABELS,
            _SYMBOLOGY_LABELS,
            _UPC_E_LABELS,
        )

    def _scan_expected_value(self, expected_value, state_name, screenshot_prefix):
        failures = []
        for round_number in range(1, 4):
            scan_clear_input_field(self.d0)
            self.assertTrue(
                dcs_test_trigger_honeywell_scan(DEV0_SERIAL),
                f"Scan trigger failed with Send check digit {state_name}, round {round_number}",
            )
            detected = scan_verify_decode_result(self.d0, max_wait_seconds=6)
            value = scan_get_input_field_text(self.d0) if detected else ""
            print(
                f"  Send check digit {state_name}, round {round_number}: "
                f"detected={detected}, value='{value}'"
            )
            if not detected or value != expected_value:
                failures.append(f"Round {round_number}: detected={detected}, value='{value}'")
            save_step_screenshot(self.d0, f"{screenshot_prefix}_round{round_number}", SCRIPT_IMG_DIR)
        return failures

    def test_send_check_digit_upc_e(self):
        """Test steps:
        1. Enable Wedge in Data Processing Settings.
        2. Enable UPC-E, Send number system, and Send check digit.
        3. Scan the UPC-E reference barcode and verify the output includes the check digit.
        4. Disable Send check digit.
        5. Scan the same barcode and verify the output excludes the check digit.
        """
        print("\n[Step 1] Open Data Processing Settings")
        dcs_test_goto_data_processing_settings(
            DEV0_SERIAL,
            self.d0,
            _SCANNING_LABELS,
            _INTERNAL_SCANNER_LABELS,
            _DEFAULT_PROFILE_LABELS,
            _DATA_PROCESSING_LABELS,
        )
        save_step_screenshot(self.d0, "step01_data_processing_settings", SCRIPT_IMG_DIR)

        print("[Step 2] Enable Wedge")
        self.assertTrue(dcs_test_set_option_checked(self.d0, "Wedge", True), "Failed to enable Wedge")
        save_step_screenshot(self.d0, "step02_enable_wedge", SCRIPT_IMG_DIR)

        print("[Step 3] Open Symbology Settings -> UPC-E")
        self._goto_upc_e_setting()
        save_step_screenshot(self.d0, "step03_upc_e_setting", SCRIPT_IMG_DIR)

        print("[Step 4] Enable UPC-E, Send number system, and Send check digit")
        self.assertTrue(dcs_test_set_option_checked(self.d0, "UPC-E", True), "Failed to enable UPC-E")
        self.assertTrue(
            dcs_test_set_option_checked(self.d0, "Send number system", True),
            "Failed to enable Send number system",
        )
        self.assertTrue(
            dcs_test_set_option_checked(self.d0, "Send check digit", True),
            "Failed to enable Send check digit",
        )
        save_step_screenshot(self.d0, "step04_enable_send_check_digit", SCRIPT_IMG_DIR)

        print("[Step 5] Prepare UPC-E image on dev1 and focus an input field on dev0")
        dcs_test_prepare_image_on_display_device(
            DEV1_SERIAL,
            self.d1,
            UPC_E_IMAGE_LOCAL,
            UPC_E_IMAGE_REMOTE,
        )
        self.assertTrue(scan_open_input_field(self.d0, DEV0_SERIAL), "Failed to open an input field")
        save_step_screenshot(self.d0, "step05_open_input_field", SCRIPT_IMG_DIR)

        print("[Step 6] Scan UPC-E with Send check digit enabled")
        enabled_failures = self._scan_expected_value(
            UPC_E_WITH_CHECK_DIGIT,
            "enabled",
            "step06_send_check_digit_enabled",
        )

        print("[Step 7] Disable Send check digit")
        self._goto_upc_e_setting()
        self.assertTrue(
            dcs_test_set_option_checked(self.d0, "Send check digit", False),
            "Failed to disable Send check digit",
        )
        save_step_screenshot(self.d0, "step07_disable_send_check_digit", SCRIPT_IMG_DIR)

        print("[Step 8] Focus the input field on dev0 again")
        self.assertTrue(scan_open_input_field(self.d0, DEV0_SERIAL), "Failed to reopen an input field")
        save_step_screenshot(self.d0, "step08_reopen_input_field", SCRIPT_IMG_DIR)

        print("[Step 9] Scan UPC-E with Send check digit disabled")
        disabled_failures = self._scan_expected_value(
            UPC_E_WITHOUT_CHECK_DIGIT,
            "disabled",
            "step09_send_check_digit_disabled",
        )

        self.assertFalse(
            enabled_failures or disabled_failures,
            f"Send check digit behavior mismatch. Enabled failures: {enabled_failures}; "
            f"Disabled failures: {disabled_failures}",
        )


if __name__ == "__main__":
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(Test_SendCheckDigit_UPC_E)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)