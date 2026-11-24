# -*- coding:utf-8 -*-
"""Test Case: ANDROIDCN-37717 - Verify enabling and disabling Han Xin."""

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


def _load_device_serials_from_environment():
    dev0 = (os.environ.get("AUTONEXUS_DEV0_SN") or "").strip()
    dev1 = (os.environ.get("AUTONEXUS_DEV1_SN") or "").strip()
    if not dev0 or not dev1:
        raise RuntimeError("AUTONEXUS_DEV0_SN and AUTONEXUS_DEV1_SN must be provided by the web task")
    return dev0, dev1


DEV0_SERIAL, DEV1_SERIAL = _load_device_serials_from_environment()


class Test_EnableDisable_Han_Xin(unittest.TestCase):
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
        print("ANDROIDCN-37717: Verify enabling and disabling Han Xin")
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

    def _set_han_xin_enabled(self, enabled, step_name):
        dcs_test_goto_symbology_setting(
            DEV0_SERIAL, self.d0, _SCANNING_LABELS, _INTERNAL_SCANNER_LABELS,
            _DEFAULT_PROFILE_LABELS, _SYMBOLOGY_LABELS, _HAN_XIN_LABELS,
        )
        self.assertTrue(dcs_test_set_option_checked(self.d0, "Han Xin", enabled), f"Failed to set Han Xin enabled={enabled}")
        save_step_screenshot(self.d0, step_name, SCRIPT_IMG_DIR)

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

    def test_enable_disable_han_xin(self):
        """Test steps:
        1. Open Data Processing Settings and enable Wedge.
        2. Enable Han Xin.
        3. Scan the Han Xin sample three times and verify the exact decoded value each time.
        4. Disable Han Xin.
        5. Scan the Han Xin sample three times and verify it is rejected each time.
        """
        print("\n[Step 1] Open Data Processing Settings and enable Wedge")
        dcs_test_goto_data_processing_settings(DEV0_SERIAL, self.d0, _SCANNING_LABELS, _INTERNAL_SCANNER_LABELS, _DEFAULT_PROFILE_LABELS, _DATA_PROCESSING_LABELS)
        self.assertTrue(dcs_test_set_option_checked(self.d0, "Wedge", True), "Failed to enable Wedge")

        print("[Step 2] Enable Han Xin")
        self._set_han_xin_enabled(True, "step02_han_xin_enabled")

        print("[Step 3] Verify the Han Xin sample decodes exactly when enabled")
        enabled_values = self._scan_han_xin("step03_han_xin_enabled", True)
        self.assertEqual(enabled_values, [HAN_XIN_VALUE] * 3, "Enabled Han Xin decoded values are inconsistent")

        print("[Step 4] Disable Han Xin")
        self._set_han_xin_enabled(False, "step04_han_xin_disabled")

        print("[Step 5] Verify the Han Xin sample is rejected when disabled")
        self._scan_han_xin("step05_han_xin_disabled", False)


if __name__ == "__main__":
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(Test_EnableDisable_Han_Xin)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)
