# -*- coding:utf-8 -*-
"""Test Case: ANDROIDCN-37777 - Verify Code 128 Short Quiet Zone behavior."""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from common.adb_common import dcs_test_cleanup_devices, dcs_test_open_honeywell_settings, dcs_test_prepare_image_on_display_device, dcs_test_press_home, dcs_test_trigger_honeywell_scan, dcs_test_wait_device_online, dcs_test_wake_and_unlock, save_step_screenshot
from common.common_method import dcs_test_connect_u2, dcs_test_goto_data_processing_settings, dcs_test_goto_symbology_setting, dcs_test_scroll_find_and_click, dcs_test_set_option_checked, scan_clear_input_field, scan_get_input_field_text, scan_open_input_field, scan_verify_decode_result

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.realpath(__file__))))
SCRIPT_IMG_DIR = os.path.join(PROJECT_ROOT, "img", os.path.splitext(os.path.basename(__file__))[0])
os.makedirs(SCRIPT_IMG_DIR, exist_ok=True)
IMAGE_LOCAL = os.path.join(PROJECT_ROOT, "files", "images", "dcs_imgs", "Code128_short_quiet_zone.jpg")
IMAGE_REMOTE = "/sdcard/Pictures/Code128_short_quiet_zone.jpg"
_SCANNING_LABELS = ["Scanning"]
_INTERNAL_SCANNER_LABELS = ["Internal Scanner", "Internal scanner"]
_DEFAULT_PROFILE_LABELS = ["Default profile", "Default Profile"]
_DATA_PROCESSING_LABELS = ["Data Processing Settings", "Data Processing"]
_DECODE_SETTINGS_LABELS = ["Decode Settings", "Decode settings"]
_SYMBOLOGY_LABELS = ["Symbology Settings", "Symbology"]
_CODE128_LABELS = ["Code 128", "Code128", "CODE 128"]


def _load_device_serials():
    dev0 = (os.environ.get("AUTONEXUS_DEV0_SN") or "").strip()
    dev1 = (os.environ.get("AUTONEXUS_DEV1_SN") or "").strip()
    if not dev0 or not dev1:
        raise RuntimeError("AUTONEXUS_DEV0_SN and AUTONEXUS_DEV1_SN must be provided by the web task")
    return dev0, dev1


DEV0_SERIAL, DEV1_SERIAL = _load_device_serials()


class Test_ShortQuietZone_Code128(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not dcs_test_wait_device_online(DEV0_SERIAL, 25) or not dcs_test_wait_device_online(DEV1_SERIAL, 25):
            raise RuntimeError("Configured Code 128 test devices are offline")
        cls.d0 = dcs_test_connect_u2(DEV0_SERIAL)
        cls.d1 = dcs_test_connect_u2(DEV1_SERIAL)

    def setUp(self):
        if not hasattr(self.__class__, "d0"):
            self.__class__.setUpClass()
        dcs_test_wake_and_unlock(DEV0_SERIAL, self.d0)
        dcs_test_wake_and_unlock(DEV1_SERIAL, self.d1)
        dcs_test_press_home(DEV0_SERIAL)
        dcs_test_press_home(DEV1_SERIAL)

    def tearDown(self):
        dcs_test_cleanup_devices(DEV0_SERIAL, DEV1_SERIAL)
        dcs_test_press_home(DEV0_SERIAL)
        dcs_test_press_home(DEV1_SERIAL)

    def _goto_decode_settings(self):
        self.assertTrue(dcs_test_open_honeywell_settings(DEV0_SERIAL), "Cannot open Honeywell Settings")
        for labels, description in (
            (_SCANNING_LABELS, "Scanning"),
            (_INTERNAL_SCANNER_LABELS, "Internal Scanner"),
            (_DEFAULT_PROFILE_LABELS, "Default profile"),
            (_DECODE_SETTINGS_LABELS, "Decode Settings"),
        ):
            self.assertTrue(dcs_test_scroll_find_and_click(self.d0, labels, max_swipes=3), f"Cannot find {description}")

    def _goto_code128(self):
        dcs_test_goto_symbology_setting(DEV0_SERIAL, self.d0, _SCANNING_LABELS, _INTERNAL_SCANNER_LABELS, _DEFAULT_PROFILE_LABELS, _SYMBOLOGY_LABELS, _CODE128_LABELS)

    def _set_short_quiet_zone(self, value):
        self._goto_code128()
        self.assertTrue(dcs_test_scroll_find_and_click(self.d0, ["Short Quiet Zone"], max_swipes=3), "Cannot open Short Quiet Zone")
        option = self.d0(resourceId="android:id/text1", text=value)
        self.assertTrue(option.exists, f"Short Quiet Zone option '{value}' is unavailable")
        option.click()
        self.assertFalse(option.exists(timeout=1), f"Short Quiet Zone option '{value}' was not selected")

    def _scan_three_times(self, label):
        decoded_count = 0
        for round_number in range(1, 4):
            dcs_test_prepare_image_on_display_device(DEV1_SERIAL, self.d1, IMAGE_LOCAL, IMAGE_REMOTE)
            self.assertTrue(scan_open_input_field(self.d0, DEV0_SERIAL), "Failed to focus input field")
            scan_clear_input_field(self.d0)
            self.assertTrue(dcs_test_trigger_honeywell_scan(DEV0_SERIAL), "Scan trigger failed")
            detected = scan_verify_decode_result(self.d0, max_wait_seconds=5)
            value = scan_get_input_field_text(self.d0) if detected else ""
            print(f"  {label} round {round_number}: detected={detected}, value='{value}'")
            if detected:
                self.assertEqual(value, "5C728G22802860I1GXTB", f"{label} round {round_number}: unexpected Code 128 data")
                decoded_count += 1
            save_step_screenshot(self.d0, f"{label}_round{round_number}", SCRIPT_IMG_DIR)
        return decoded_count

    def test_short_quiet_zone_code128(self):
        """Test steps:
        1. Open Data Processing Settings, enable Wedge output, and disable Fast Linear Decode.
        2. Navigate to Code 128 settings and enable Code 128.
        3. Set Short Quiet Zone to Enable both ends and scan the short-quiet-zone barcode three times; verify every scan succeeds.
        4. Set Short Quiet Zone to Disable and scan the same barcode three times; verify fewer than three scans decode.
        """
        dcs_test_goto_data_processing_settings(DEV0_SERIAL, self.d0, _SCANNING_LABELS, _INTERNAL_SCANNER_LABELS, _DEFAULT_PROFILE_LABELS, _DATA_PROCESSING_LABELS)
        self.assertTrue(dcs_test_set_option_checked(self.d0, "Wedge", True), "Failed to enable Wedge")
        self._goto_decode_settings()
        self.assertTrue(dcs_test_set_option_checked(self.d0, "Fast Linear Decode", False), "Failed to disable Fast Linear Decode")
        save_step_screenshot(self.d0, "precondition_fast_linear_decode_disabled", SCRIPT_IMG_DIR)
        self._goto_code128()
        self.assertTrue(dcs_test_set_option_checked(self.d0, "Code 128", True), "Failed to enable Code 128")

        self._set_short_quiet_zone("Enable both ends")
        save_step_screenshot(self.d0, "step03_short_quiet_zone_both_ends", SCRIPT_IMG_DIR)
        self.assertEqual(self._scan_three_times("step05_both_ends"), 3, "Short Quiet Zone 'Enable both ends' did not decode every attempt")

        self._set_short_quiet_zone("Disable")
        save_step_screenshot(self.d0, "step06_short_quiet_zone_disabled", SCRIPT_IMG_DIR)
        self.assertLess(self._scan_three_times("step08_short_quiet_zone_disabled"), 3, "Short Quiet Zone 'Disable' decoded every attempt instead of degrading short-quiet-zone scanning")


if __name__ == "__main__":
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(Test_ShortQuietZone_Code128)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)