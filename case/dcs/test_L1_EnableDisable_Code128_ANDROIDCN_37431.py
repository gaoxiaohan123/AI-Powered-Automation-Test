# -*- coding:utf-8 -*-
"""Test Case: ANDROIDCN-37431 - Enable/Disable Code 128 and verify scan behavior."""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from common.adb_common import (
    dcs_test_cleanup_devices,
    dcs_test_prepare_image_on_display_device,
    dcs_test_press_home,
    dcs_test_trigger_honeywell_scan,
    dcs_test_wait_device_online,
    dcs_test_wake_and_unlock,
    save_step_screenshot,
)
from common.common_method import (
    dcs_test_connect_u2,
    dcs_test_goto_data_processing_settings,
    dcs_test_goto_symbology_setting,
    dcs_test_set_option_checked,
    scan_clear_input_field,
    scan_get_input_field_text,
    scan_open_input_field,
    scan_verify_decode_result,
)

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.realpath(__file__))))
SCRIPT_BASENAME = os.path.splitext(os.path.basename(__file__))[0]
SCRIPT_IMG_DIR = os.path.join(PROJECT_ROOT, "img", SCRIPT_BASENAME)
os.makedirs(SCRIPT_IMG_DIR, exist_ok=True)
CODE128_IMAGE_LOCAL = os.path.join(PROJECT_ROOT, "files", "images", "dcs_imgs", "Code 128.jpg")
CODE128_IMAGE_REMOTE = "/sdcard/Pictures/Code 128.jpg"

_SCANNING_LABELS = ["Scanning"]
_INTERNAL_SCANNER_LABELS = ["Internal Scanner", "Internal scanner"]
_DEFAULT_PROFILE_LABELS = ["Default profile", "Default Profile"]
_DATA_PROCESSING_LABELS = ["Data Processing Settings", "Data Processing"]
_SYMBOLOGY_LABELS = ["Symbology Settings", "Symbology"]
_CODE128_LABELS = ["Code 128", "Code128", "CODE 128"]


def _load_device_serials_from_environment():
    dev0 = (os.environ.get("AUTONEXUS_DEV0_SN") or "").strip()
    dev1 = (os.environ.get("AUTONEXUS_DEV1_SN") or "").strip()
    if not dev0 or not dev1:
        raise RuntimeError("AUTONEXUS_DEV0_SN and AUTONEXUS_DEV1_SN must be provided by the web task")
    return dev0, dev1


DEV0_SERIAL, DEV1_SERIAL = _load_device_serials_from_environment()


class Test_EnableDisable_Code128(unittest.TestCase):
    @classmethod
    def _ensure_device_sessions(cls):
        if hasattr(cls, "d0") and hasattr(cls, "d1"):
            return
        if not dcs_test_wait_device_online(DEV0_SERIAL, 25) or not dcs_test_wait_device_online(DEV1_SERIAL, 25):
            raise RuntimeError("Configured Code 128 test devices are offline")
        cls.d0 = dcs_test_connect_u2(DEV0_SERIAL)
        cls.d1 = dcs_test_connect_u2(DEV1_SERIAL)

    @classmethod
    def setUpClass(cls):
        print("\n" + "=" * 70)
        print("ANDROIDCN-37431: Enable/Disable Code 128")
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

    def _goto_code128_setting(self):
        dcs_test_goto_symbology_setting(
            DEV0_SERIAL,
            self.d0,
            _SCANNING_LABELS,
            _INTERNAL_SCANNER_LABELS,
            _DEFAULT_PROFILE_LABELS,
            _SYMBOLOGY_LABELS,
            _CODE128_LABELS,
        )

    def _scan_code128(self, state_name, expect_decode):
        values = []
        for round_number in range(1, 4):
            dcs_test_prepare_image_on_display_device(
                DEV1_SERIAL,
                self.d1,
                CODE128_IMAGE_LOCAL,
                CODE128_IMAGE_REMOTE,
            )
            save_step_screenshot(self.d1, f"{state_name}_display_round{round_number}", SCRIPT_IMG_DIR)
            self.assertTrue(scan_open_input_field(self.d0, DEV0_SERIAL), "Failed to focus input field")
            scan_clear_input_field(self.d0)
            self.assertTrue(
                dcs_test_trigger_honeywell_scan(DEV0_SERIAL),
                f"Scan trigger failed for {state_name} round {round_number}",
            )
            detected = scan_verify_decode_result(self.d0, max_wait_seconds=5)
            value = scan_get_input_field_text(self.d0) if detected else ""
            print(f"  {state_name} round {round_number}: detected={detected}, value='{value}'")
            self.assertEqual(
                detected,
                expect_decode,
                f"Unexpected Code 128 decode state for {state_name} round {round_number}, value='{value}'",
            )
            save_step_screenshot(self.d0, f"{state_name}_round{round_number}", SCRIPT_IMG_DIR)
            values.append(value)
        return values

    def test_enable_disable_code128(self):
        """Verify Code 128 repeatedly decodes while enabled and is rejected while disabled."""
        print("\n[Step 1] Open Data Processing Settings and enable Wedge")
        dcs_test_goto_data_processing_settings(
            DEV0_SERIAL,
            self.d0,
            _SCANNING_LABELS,
            _INTERNAL_SCANNER_LABELS,
            _DEFAULT_PROFILE_LABELS,
            _DATA_PROCESSING_LABELS,
        )
        self.assertTrue(dcs_test_set_option_checked(self.d0, "Wedge", True), "Failed to enable Wedge")

        print("[Step 2] Enable Code 128 and verify repeated decoding")
        self._goto_code128_setting()
        self.assertTrue(dcs_test_set_option_checked(self.d0, "Code 128", True), "Failed to enable Code 128")
        save_step_screenshot(self.d0, "step02_code128_enabled", SCRIPT_IMG_DIR)
        decoded_values = self._scan_code128("step02_code128_enabled", True)
        self.assertTrue(all(decoded_values), "Code 128 decoded to an empty value")
        self.assertEqual(len(set(decoded_values)), 1, f"Code 128 decoded inconsistently: {decoded_values}")

        print("[Step 3] Disable Code 128 and verify repeated rejection")
        self._goto_code128_setting()
        self.assertTrue(dcs_test_set_option_checked(self.d0, "Code 128", False), "Failed to disable Code 128")
        save_step_screenshot(self.d0, "step03_code128_disabled", SCRIPT_IMG_DIR)
        self._scan_code128("step03_code128_disabled", False)


if __name__ == "__main__":
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(Test_EnableDisable_Code128)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)