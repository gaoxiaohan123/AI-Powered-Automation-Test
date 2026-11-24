# -*- coding:utf-8 -*-
"""Test Case: ANDROIDCN-37631 - Double check Modulo 10 for MSI."""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from common.adb_common import (save_step_screenshot, dcs_test_cleanup_devices, dcs_test_press_home,
                               dcs_test_prepare_image_on_display_device, dcs_test_trigger_honeywell_scan,
                               dcs_test_wait_device_online, dcs_test_wake_and_unlock)
from common.common_method import (scan_clear_input_field, scan_get_input_field_text, scan_open_input_field,
                                  scan_verify_decode_result, dcs_test_connect_u2,
                                  dcs_test_goto_data_processing_settings, dcs_test_goto_symbology_setting,
                                  dcs_test_set_option_checked)

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.realpath(__file__))))
SCRIPT_BASENAME = os.path.splitext(os.path.basename(__file__))[0]
SCRIPT_IMG_DIR = os.path.join(PROJECT_ROOT, "img", SCRIPT_BASENAME)
os.makedirs(SCRIPT_IMG_DIR, exist_ok=True)
DOUBLE_MODULO_10_IMAGE = os.path.join(PROJECT_ROOT, "files", "images", "dcs_imgs", "MSI with Check digit 2mod10.jpg")
SINGLE_MODULO_10_IMAGE = os.path.join(PROJECT_ROOT, "files", "images", "dcs_imgs", "MSI with Check digit 1mod10_3x.png")
DOUBLE_MODULO_10_VALUE = "12345666"

_SCANNING_LABELS = ["Scanning"]
_INTERNAL_SCANNER_LABELS = ["Internal Scanner", "Internal scanner"]
_DEFAULT_PROFILE_LABELS = ["Default profile", "Default Profile"]
_DATA_PROCESSING_LABELS = ["Data Processing Settings", "Data Processing"]
_SYMBOLOGY_LABELS = ["Symbology Settings", "Symbology"]
_MSI_LABELS = ["MSI"]


def _load_device_serials_from_environment():
    dev0 = (os.environ.get("AUTONEXUS_DEV0_SN") or "").strip()
    dev1 = (os.environ.get("AUTONEXUS_DEV1_SN") or "").strip()
    if not dev0 or not dev1:
        raise RuntimeError("AUTONEXUS_DEV0_SN and AUTONEXUS_DEV1_SN must be provided by the web task")
    return dev0, dev1


DEV0_SERIAL, DEV1_SERIAL = _load_device_serials_from_environment()


class Test_DoubleCheckModulo10_MSI(unittest.TestCase):
    @classmethod
    def _ensure_device_sessions(cls):
        if hasattr(cls, "d0"):
            return
        if not dcs_test_wait_device_online(DEV0_SERIAL, 25) or not dcs_test_wait_device_online(DEV1_SERIAL, 25):
            raise RuntimeError("Configured MSI test devices are offline")
        cls.d0 = dcs_test_connect_u2(DEV0_SERIAL)
        cls.d1 = dcs_test_connect_u2(DEV1_SERIAL)

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

    def _set_double_modulo_10(self):
        dcs_test_goto_symbology_setting(DEV0_SERIAL, self.d0, _SCANNING_LABELS, _INTERNAL_SCANNER_LABELS,
                                        _DEFAULT_PROFILE_LABELS, _SYMBOLOGY_LABELS, _MSI_LABELS)
        self.assertTrue(dcs_test_set_option_checked(self.d0, "MSI", True), "Failed to enable MSI")
        self.d0(text="Check digit mode").click()
        labels = ["Double check modulo 10", "Double check Modulo 10"]
        for label in labels:
            if self.d0(text=label).exists:
                self.d0(text=label).click()
                self.d0.press("back")
                save_step_screenshot(self.d0, "step02_double_check_modulo_10", SCRIPT_IMG_DIR)
                return
        self.fail("Cannot select Double check modulo 10")

    def _scan(self, image_path, state_name, expected_value):
        values = []
        for round_number in range(1, 4):
            dcs_test_prepare_image_on_display_device(DEV1_SERIAL, self.d1, image_path, "/sdcard/Pictures/" + os.path.basename(image_path))
            self.assertTrue(scan_open_input_field(self.d0, DEV0_SERIAL), "Failed to focus input field")
            scan_clear_input_field(self.d0)
            self.assertTrue(dcs_test_trigger_honeywell_scan(DEV0_SERIAL), "Scan trigger failed")
            detected = scan_verify_decode_result(self.d0, max_wait_seconds=5)
            value = scan_get_input_field_text(self.d0) if detected else ""
            print(f"  {state_name} round {round_number}: detected={detected}, value='{value}'")
            self.assertEqual(detected, expected_value != "", f"{state_name} round {round_number}: unexpected decode state")
            self.assertEqual(value, expected_value, f"{state_name} round {round_number}: unexpected decoded value")
            save_step_screenshot(self.d0, f"{state_name}_round{round_number}", SCRIPT_IMG_DIR)
            values.append(value)
        return values

    def test_double_check_modulo_10_msi(self):
        """Test steps:
        1. Enable Wedge for keyboard output.
        2. Enable MSI and select Double check modulo 10.
        3. Verify a double-Modulo-10 barcode decodes to its exact value three times.
        4. Verify a single-Modulo-10 barcode is rejected three times.
        """
        print("\n[Step 1] Open Data Processing Settings and enable Wedge")
        dcs_test_goto_data_processing_settings(DEV0_SERIAL, self.d0, _SCANNING_LABELS, _INTERNAL_SCANNER_LABELS,
                                               _DEFAULT_PROFILE_LABELS, _DATA_PROCESSING_LABELS)
        self.assertTrue(dcs_test_set_option_checked(self.d0, "Wedge", True), "Failed to enable Wedge")

        print("[Step 2] Enable MSI and select Double check modulo 10")
        self._set_double_modulo_10()

        print("[Step 3] Verify the double-Modulo-10 MSI barcode decodes exactly")
        accepted = self._scan(DOUBLE_MODULO_10_IMAGE, "step03_double_modulo_10", DOUBLE_MODULO_10_VALUE)
        self.assertEqual(accepted, [DOUBLE_MODULO_10_VALUE] * 3)

        print("[Step 4] Verify the single-Modulo-10 MSI barcode is rejected")
        self._scan(SINGLE_MODULO_10_IMAGE, "step04_non_double_modulo_10", "")


if __name__ == "__main__":
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(Test_DoubleCheckModulo10_MSI)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)