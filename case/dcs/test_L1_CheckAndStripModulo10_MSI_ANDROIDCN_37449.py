# -*- coding:utf-8 -*-
"""Test Case: ANDROIDCN-37449 - Check and strip Modulo 10 for MSI."""

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
MSI_MODULO_10_IMAGE_LOCAL = os.path.join(PROJECT_ROOT, "files", "images", "dcs_imgs", "MSI_Modulo_10_1234566.png")
MSI_MODULO_10_IMAGE_REMOTE = "/sdcard/Pictures/MSI_Modulo_10_1234566.png"
MSI_MODULO_10_VALUE = "1234566"
MSI_MODULO_10_STRIPPED_VALUE = "123456"

_SCANNING_LABELS = ["Scanning"]
_INTERNAL_SCANNER_LABELS = ["Internal Scanner", "Internal scanner"]
_DEFAULT_PROFILE_LABELS = ["Default profile", "Default Profile"]
_DATA_PROCESSING_LABELS = ["Data Processing Settings", "Data Processing"]
_SYMBOLOGY_LABELS = ["Symbology Settings", "Symbology"]
_MSI_LABELS = ["MSI"]
_CHECK_AND_STRIP_MODULO_10_LABELS = ["Check and strip Modulo 10", "Check and strip modulo 10"]


def _load_device_serials_from_environment():
    dev0 = (os.environ.get("AUTONEXUS_DEV0_SN") or "").strip()
    dev1 = (os.environ.get("AUTONEXUS_DEV1_SN") or "").strip()
    if not dev0 or not dev1:
        raise RuntimeError("AUTONEXUS_DEV0_SN and AUTONEXUS_DEV1_SN must be provided by the web task")
    return dev0, dev1


DEV0_SERIAL, DEV1_SERIAL = _load_device_serials_from_environment()


class Test_CheckAndStripModulo10_MSI(unittest.TestCase):
    @classmethod
    def _ensure_device_sessions(cls):
        if hasattr(cls, "d0") and hasattr(cls, "d1"):
            return
        if not dcs_test_wait_device_online(DEV0_SERIAL, 25) or not dcs_test_wait_device_online(DEV1_SERIAL, 25):
            raise RuntimeError("Configured MSI test devices are offline")
        cls.d0 = dcs_test_connect_u2(DEV0_SERIAL)
        cls.d1 = dcs_test_connect_u2(DEV1_SERIAL)

    @classmethod
    def setUpClass(cls):
        print("\n" + "=" * 70)
        print("ANDROIDCN-37449: Check and strip Modulo 10 for MSI")
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

    def _goto_msi_setting(self):
        dcs_test_goto_symbology_setting(
            DEV0_SERIAL, self.d0, _SCANNING_LABELS, _INTERNAL_SCANNER_LABELS,
            _DEFAULT_PROFILE_LABELS, _SYMBOLOGY_LABELS, _MSI_LABELS,
        )

    def _set_check_digit_mode(self, mode_labels, screenshot_name):
        self._goto_msi_setting()
        self.assertTrue(dcs_test_set_option_checked(self.d0, "MSI", True), "Failed to enable MSI")
        self.assertTrue(self.d0(text="Check digit mode").exists, "Cannot find Check digit mode")
        self.d0(text="Check digit mode").click()
        for label in mode_labels:
            if self.d0(text=label).exists:
                self.d0(text=label).click()
                self.d0.press("back")
                self._goto_msi_setting()
                save_step_screenshot(self.d0, screenshot_name, SCRIPT_IMG_DIR)
                return
        self.fail(f"Cannot select Check digit mode from: {mode_labels}")

    def _scan_sample(self, state_name, expected_value):
        values = []
        for round_number in range(1, 4):
            dcs_test_prepare_image_on_display_device(
                DEV1_SERIAL, self.d1, MSI_MODULO_10_IMAGE_LOCAL, MSI_MODULO_10_IMAGE_REMOTE,
            )
            self.assertTrue(scan_open_input_field(self.d0, DEV0_SERIAL), "Failed to focus input field")
            scan_clear_input_field(self.d0)
            self.assertTrue(dcs_test_trigger_honeywell_scan(DEV0_SERIAL), "Scan trigger failed")
            detected = scan_verify_decode_result(self.d0, max_wait_seconds=5)
            value = scan_get_input_field_text(self.d0) if detected else ""
            print(f"  {state_name} round {round_number}: detected={detected}, value='{value}'")
            self.assertTrue(detected, f"{state_name} round {round_number}: MSI barcode was not decoded")
            self.assertEqual(value, expected_value, f"{state_name} round {round_number}: unexpected decoded value")
            values.append(value)
            save_step_screenshot(self.d0, f"{state_name}_round{round_number}", SCRIPT_IMG_DIR)
        return values

    def test_check_and_strip_modulo_10_msi(self):
        """Test steps:
        1. Enable Wedge for keyboard output.
        2. Select No check and capture the full Modulo 10 barcode value three times.
        3. Enable MSI Check and strip Modulo 10 mode.
        4. Scan the same barcode three times and verify exactly one check character is removed.
        """
        print("\n[Step 1] Open Data Processing Settings and enable Wedge")
        dcs_test_goto_data_processing_settings(
            DEV0_SERIAL, self.d0, _SCANNING_LABELS, _INTERNAL_SCANNER_LABELS,
            _DEFAULT_PROFILE_LABELS, _DATA_PROCESSING_LABELS,
        )
        self.assertTrue(dcs_test_set_option_checked(self.d0, "Wedge", True), "Failed to enable Wedge")

        print("[Step 2] Capture the exact MSI value with its Modulo 10 check character")
        self._set_check_digit_mode(["No check", "No check digit"], "step02_no_check")
        unstripped_values = self._scan_sample("step02_no_check", MSI_MODULO_10_VALUE)

        print("[Step 3] Set Check digit mode to Check and strip Modulo 10")
        self._set_check_digit_mode(_CHECK_AND_STRIP_MODULO_10_LABELS, "step03_check_and_strip_modulo_10")

        print("[Step 4] Verify every scan removes exactly the Modulo 10 check character")
        stripped_values = self._scan_sample("step04_check_and_strip_modulo_10", MSI_MODULO_10_STRIPPED_VALUE)
        self.assertEqual(unstripped_values, [MSI_MODULO_10_VALUE] * 3)
        self.assertEqual(stripped_values, [MSI_MODULO_10_STRIPPED_VALUE] * 3)


if __name__ == "__main__":
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(Test_CheckAndStripModulo10_MSI)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)