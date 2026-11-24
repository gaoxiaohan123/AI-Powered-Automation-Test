# -*- coding:utf-8 -*-
"""Test Case: ANDROIDCN-37696 - Verify Maximum length property for MSI."""

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
MSI_AT_MAXIMUM_IMAGE = os.path.join(PROJECT_ROOT, "files", "images", "dcs_imgs", "MSI_No_Check_123456.png")
MSI_ABOVE_MAXIMUM_IMAGE = os.path.join(PROJECT_ROOT, "files", "images", "dcs_imgs", "MSI_No_Check_1234567.png")
MSI_AT_MAXIMUM_VALUE = "123456"
MAXIMUM_LENGTH = 6

_SCANNING_LABELS = ["Scanning"]
_INTERNAL_SCANNER_LABELS = ["Internal Scanner", "Internal scanner"]
_DEFAULT_PROFILE_LABELS = ["Default profile", "Default Profile"]
_DATA_PROCESSING_LABELS = ["Data Processing Settings", "Data Processing"]
_SYMBOLOGY_LABELS = ["Symbology Settings", "Symbology"]
_MSI_LABELS = ["MSI"]
_EDIT_RESOURCE_ID = "android:id/edit"
_OK_RESOURCE_ID = "android:id/button1"


def _load_device_serials_from_environment():
    dev0 = (os.environ.get("AUTONEXUS_DEV0_SN") or "").strip()
    dev1 = (os.environ.get("AUTONEXUS_DEV1_SN") or "").strip()
    if not dev0 or not dev1:
        raise RuntimeError("AUTONEXUS_DEV0_SN and AUTONEXUS_DEV1_SN must be provided by the web task")
    return dev0, dev1


DEV0_SERIAL, DEV1_SERIAL = _load_device_serials_from_environment()


class Test_MaximumLength_MSI(unittest.TestCase):
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

    def _goto_msi_setting(self):
        dcs_test_goto_symbology_setting(
            DEV0_SERIAL, self.d0, _SCANNING_LABELS, _INTERNAL_SCANNER_LABELS,
            _DEFAULT_PROFILE_LABELS, _SYMBOLOGY_LABELS, _MSI_LABELS,
        )

    def _set_length(self, setting_name, value):
        self._goto_msi_setting()
        self.assertTrue(self.d0(text=setting_name).exists, f"Cannot find {setting_name}")
        self.d0(text=setting_name).click()
        edit = self.d0(resourceId=_EDIT_RESOURCE_ID)
        self.assertTrue(edit.exists, f"{setting_name} dialog did not open")
        edit.set_text(str(value))
        self.d0(resourceId=_OK_RESOURCE_ID).click()
        self.assertFalse(edit.exists, f"{setting_name} dialog did not close after saving")

    def _configure_lengths(self):
        self._goto_msi_setting()
        self.assertTrue(dcs_test_set_option_checked(self.d0, "MSI", True), "Failed to enable MSI")
        self.d0(text="Check digit mode").click()
        self.assertTrue(self.d0(text="No check").exists, "Cannot find No check mode")
        self.d0(text="No check").click()
        self.d0.press("back")
        self._set_length("Minimum length", 4)
        self._set_length("Maximum length", MAXIMUM_LENGTH)
        save_step_screenshot(self.d0, "step02_maximum_length_6", SCRIPT_IMG_DIR)

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

    def test_maximum_length_msi(self):
        """Test steps:
        1. Enable Wedge for keyboard output.
        2. Enable MSI and configure the tested Minimum and Maximum length values.
        3. Verify an above-maximum barcode is rejected three times.
        4. Verify an at-maximum barcode decodes to its exact value three times.
        """
        print("\n[Step 1] Open Data Processing Settings and enable Wedge")
        dcs_test_goto_data_processing_settings(DEV0_SERIAL, self.d0, _SCANNING_LABELS, _INTERNAL_SCANNER_LABELS,
                                               _DEFAULT_PROFILE_LABELS, _DATA_PROCESSING_LABELS)
        self.assertTrue(dcs_test_set_option_checked(self.d0, "Wedge", True), "Failed to enable Wedge")

        print("[Step 2] Enable MSI and configure the Minimum and Maximum length values")
        self._configure_lengths()

        print("[Step 3] Verify the above-maximum MSI barcode is rejected")
        self._scan(MSI_ABOVE_MAXIMUM_IMAGE, "step03_above_maximum", "")

        print("[Step 4] Verify the at-maximum MSI barcode decodes exactly")
        accepted = self._scan(MSI_AT_MAXIMUM_IMAGE, "step04_at_maximum", MSI_AT_MAXIMUM_VALUE)
        self.assertEqual(accepted, [MSI_AT_MAXIMUM_VALUE] * 3)


if __name__ == "__main__":
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(Test_MaximumLength_MSI)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)