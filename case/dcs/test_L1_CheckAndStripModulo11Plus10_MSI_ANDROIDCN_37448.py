# -*- coding:utf-8 -*-
"""Test Case: ANDROIDCN-37448 - Check and strip Modulo 11 plus 10 for MSI."""

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
MSI_MODULO_11_PLUS_10_IMAGE_LOCAL = os.path.join(PROJECT_ROOT, "files", "images", "dcs_imgs", "MSI_Modulo_11_plus_10.JPG")
MSI_MODULO_11_PLUS_10_IMAGE_REMOTE = "/sdcard/Pictures/MSI_Modulo_11_plus_10.JPG"
MSI_NON_MODULO_11_PLUS_10_IMAGE_LOCAL = os.path.join(PROJECT_ROOT, "files", "images", "dcs_imgs", "MSI.jpg")
MSI_NON_MODULO_11_PLUS_10_IMAGE_REMOTE = "/sdcard/Pictures/MSI.jpg"
MSI_MODULO_11_PLUS_10_STRIPPED_VALUE = "1234563"

_SCANNING_LABELS = ["Scanning"]
_INTERNAL_SCANNER_LABELS = ["Internal Scanner", "Internal scanner"]
_DEFAULT_PROFILE_LABELS = ["Default profile", "Default Profile"]
_DATA_PROCESSING_LABELS = ["Data Processing Settings", "Data Processing"]
_SYMBOLOGY_LABELS = ["Symbology Settings", "Symbology"]
_MSI_LABELS = ["MSI"]
_CHECK_AND_STRIP_MODULO_11_PLUS_10_LABELS = ["Check and strip modulo 11 plus 10"]


def _load_device_serials_from_environment():
    dev0 = (os.environ.get("AUTONEXUS_DEV0_SN") or "").strip()
    dev1 = (os.environ.get("AUTONEXUS_DEV1_SN") or "").strip()
    if not dev0 or not dev1:
        raise RuntimeError("AUTONEXUS_DEV0_SN and AUTONEXUS_DEV1_SN must be provided by the web task")
    return dev0, dev1


DEV0_SERIAL, DEV1_SERIAL = _load_device_serials_from_environment()


class Test_CheckAndStripModulo11Plus10_MSI(unittest.TestCase):
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
        print("ANDROIDCN-37448: Check and strip Modulo 11 plus 10 for MSI")
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

    def _set_check_digit_mode(self):
        self._goto_msi_setting()
        self.assertTrue(dcs_test_set_option_checked(self.d0, "MSI", True), "Failed to enable MSI")
        self.assertTrue(self.d0(text="Check digit mode").exists, "Cannot find Check digit mode")
        self.d0(text="Check digit mode").click()
        for label in _CHECK_AND_STRIP_MODULO_11_PLUS_10_LABELS:
            if self.d0(text=label).exists:
                self.d0(text=label).click()
                save_step_screenshot(self.d0, "step02_check_and_strip_modulo_11_plus_10", SCRIPT_IMG_DIR)
                return
        self.fail("Cannot select Check and strip modulo 11 plus 10")

    def _scan_sample(self, image_local, image_remote, state_name, expect_decode, expected_value=None):
        for round_number in range(1, 4):
            dcs_test_prepare_image_on_display_device(DEV1_SERIAL, self.d1, image_local, image_remote)
            self.assertTrue(scan_open_input_field(self.d0, DEV0_SERIAL), "Failed to focus input field")
            scan_clear_input_field(self.d0)
            self.assertTrue(dcs_test_trigger_honeywell_scan(DEV0_SERIAL), "Scan trigger failed")
            detected = scan_verify_decode_result(self.d0, max_wait_seconds=5)
            value = scan_get_input_field_text(self.d0) if detected else ""
            print(f"  {state_name} round {round_number}: detected={detected}, value='{value}'")
            self.assertEqual(detected, expect_decode, f"{state_name} round {round_number}: unexpected decode state, value='{value}'")
            if expected_value is not None:
                self.assertEqual(value, expected_value, f"{state_name} round {round_number}: unexpected stripped value")
            save_step_screenshot(self.d0, f"{state_name}_round{round_number}", SCRIPT_IMG_DIR)

    def test_check_and_strip_modulo_11_plus_10_msi(self):
        """Test steps:
        1. Enable Wedge in Data Processing Settings.
        2. Enable MSI and select Check and strip modulo 11 plus 10.
        3. Verify a Modulo 11/10 MSI barcode decodes without its check characters.
        4. Verify an MSI barcode with a different check-digit scheme is rejected.
        """
        print("\n[Step 1] Open Data Processing Settings and enable Wedge")
        dcs_test_goto_data_processing_settings(
            DEV0_SERIAL, self.d0, _SCANNING_LABELS, _INTERNAL_SCANNER_LABELS,
            _DEFAULT_PROFILE_LABELS, _DATA_PROCESSING_LABELS,
        )
        self.assertTrue(dcs_test_set_option_checked(self.d0, "Wedge", True), "Failed to enable Wedge")

        print("[Step 2] Enable MSI and select Check and strip modulo 11 plus 10")
        self._set_check_digit_mode()

        print("[Step 3] Verify Modulo 11/10 MSI decoding strips both check characters")
        self._scan_sample(
            MSI_MODULO_11_PLUS_10_IMAGE_LOCAL, MSI_MODULO_11_PLUS_10_IMAGE_REMOTE,
            "step03_modulo_11_plus_10", True, MSI_MODULO_11_PLUS_10_STRIPPED_VALUE,
        )

        print("[Step 4] Verify an MSI barcode with another check-digit scheme is rejected")
        self._scan_sample(
            MSI_NON_MODULO_11_PLUS_10_IMAGE_LOCAL, MSI_NON_MODULO_11_PLUS_10_IMAGE_REMOTE,
            "step04_non_modulo_11_plus_10", False,
        )


if __name__ == "__main__":
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(Test_CheckAndStripModulo11Plus10_MSI)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)