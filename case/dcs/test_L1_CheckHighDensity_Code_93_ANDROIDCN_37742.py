# -*- coding:utf-8 -*-
"""Test Case: ANDROIDCN-37742 - Verify Check High density property for Code 93 (4 mil sample)."""

import os
import sys
import time
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
# Crop of the lower barcode in code93_4mil.PNG; its printed text is 16015521400128.
CODE93_4MIL_IMAGE_LOCAL = os.path.join(PROJECT_ROOT, "files", "images", "dcs_imgs", "code93_4mil_crop.png")
CODE93_4MIL_IMAGE_REMOTE = "/sdcard/Pictures/code93_4mil_crop.png"
CODE93_4MIL_EXPECTED_VALUE = "16015521400128"

_SCANNING_LABELS = ["Scanning"]
_INTERNAL_SCANNER_LABELS = ["Internal Scanner", "Internal scanner"]
_DEFAULT_PROFILE_LABELS = ["Default profile", "Default Profile"]
_DATA_PROCESSING_LABELS = ["Data Processing Settings", "Data Processing"]
_DECODE_SETTINGS_LABELS = ["Decode Settings"]
_SYMBOLOGY_LABELS = ["Symbology Settings", "Symbology"]
_CODE93_LABELS = ["Code 93", "Code93"]
_POOR_QUALITY_1D_LABEL = "Poor Quality 1D Reading"


def _load_device_serials_from_environment():
    dev0 = (os.environ.get("AUTONEXUS_DEV0_SN") or "").strip()
    dev1 = (os.environ.get("AUTONEXUS_DEV1_SN") or "").strip()
    if not dev0 or not dev1:
        raise RuntimeError("AUTONEXUS_DEV0_SN and AUTONEXUS_DEV1_SN must be provided by the web task")
    return dev0, dev1


DEV0_SERIAL, DEV1_SERIAL = _load_device_serials_from_environment()


class Test_CheckHighDensity_Code_93(unittest.TestCase):
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
        print("ANDROIDCN-37742: Verify Check High density property for Code 93")
        print("=" * 70)
        cls._ensure_device_sessions()

    def setUp(self):
        self.__class__._ensure_device_sessions()
        dcs_test_wake_and_unlock(DEV0_SERIAL, self.d0)
        dcs_test_wake_and_unlock(DEV1_SERIAL, self.d1)
        dcs_test_press_home(DEV0_SERIAL)
        dcs_test_press_home(DEV1_SERIAL)

    def tearDown(self):
        self._set_poor_quality_1d_reading(False)
        dcs_test_cleanup_devices(DEV0_SERIAL, DEV1_SERIAL)
        dcs_test_press_home(DEV0_SERIAL)
        dcs_test_press_home(DEV1_SERIAL)

    def _goto_code93_setting(self):
        dcs_test_goto_symbology_setting(
            DEV0_SERIAL, self.d0, _SCANNING_LABELS, _INTERNAL_SCANNER_LABELS,
            _DEFAULT_PROFILE_LABELS, _SYMBOLOGY_LABELS, _CODE93_LABELS,
        )

    def _set_poor_quality_1d_reading(self, enable):
        if not dcs_test_open_honeywell_settings(DEV0_SERIAL):
            return False
        for labels in (_SCANNING_LABELS, _INTERNAL_SCANNER_LABELS, _DEFAULT_PROFILE_LABELS, _DECODE_SETTINGS_LABELS):
            if not dcs_test_scroll_find_and_click(self.d0, labels):
                return False
        return dcs_test_set_option_checked(self.d0, _POOR_QUALITY_1D_LABEL, enable)

    def _scan_code93_4mil(self, state_name):
        values = []
        for round_number in range(1, 4):
            dcs_test_prepare_image_on_display_device(DEV1_SERIAL, self.d1, CODE93_4MIL_IMAGE_LOCAL, CODE93_4MIL_IMAGE_REMOTE)
            self.assertTrue(scan_open_input_field(self.d0, DEV0_SERIAL), "Failed to focus input field")
            scan_clear_input_field(self.d0)
            self.assertTrue(dcs_test_trigger_honeywell_scan(DEV0_SERIAL), f"Scan trigger failed for {state_name} round {round_number}")
            detected = scan_verify_decode_result(self.d0, max_wait_seconds=5)
            value = scan_get_input_field_text(self.d0) if detected else ""
            print(f"  {state_name} round {round_number}: detected={detected}, value='{value}'")
            save_step_screenshot(self.d0, f"{state_name}_round{round_number}", SCRIPT_IMG_DIR)
            self.assertTrue(detected, f"Code 93 4 mil barcode was not decoded for {state_name} round {round_number}")
            values.append(value)
        return values

    def test_check_high_density_code93(self):
        """Test steps:
        1. Open Data Processing Settings and enable Wedge.
        2. Enable Code 93 and High density.
        3. Enable Poor Quality 1D Reading in Decode Settings.
        4. Scan the Code 93 4 mil barcode more than once and verify the exact decoded value.
        """
        print("\n[Step 1] Open Data Processing Settings and enable Wedge")
        dcs_test_goto_data_processing_settings(DEV0_SERIAL, self.d0, _SCANNING_LABELS, _INTERNAL_SCANNER_LABELS, _DEFAULT_PROFILE_LABELS, _DATA_PROCESSING_LABELS)
        self.assertTrue(dcs_test_set_option_checked(self.d0, "Wedge", True), "Failed to enable Wedge")

        print("[Step 2] Enable Code 93 and High density")
        self._goto_code93_setting()
        self.assertTrue(dcs_test_set_option_checked(self.d0, "Code 93", True), "Failed to enable Code 93")
        self.assertTrue(dcs_test_set_option_checked(self.d0, "High density", True), "Failed to enable High density")
        save_step_screenshot(self.d0, "step02_code93_high_density_enabled", SCRIPT_IMG_DIR)

        print("[Step 3] Enable Poor Quality 1D Reading")
        self.assertTrue(self._set_poor_quality_1d_reading(True), "Failed to enable Poor Quality 1D Reading")
        save_step_screenshot(self.d0, "step03_poor_quality_1d_enabled", SCRIPT_IMG_DIR)
        time.sleep(3)

        print("[Step 4] Scan the Code 93 4 mil barcode")
        values = self._scan_code93_4mil("step04_code93_4mil")
        self.assertEqual(values, [CODE93_4MIL_EXPECTED_VALUE] * 3, f"Code 93 4 mil decoded value mismatch: {values}")


if __name__ == "__main__":
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(Test_CheckHighDensity_Code_93)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)
