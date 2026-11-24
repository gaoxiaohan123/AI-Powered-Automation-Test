# -*- coding:utf-8 -*-
"""
Test Case: ANDROIDCN-37824
Case Name: Enable/Disable UPC-E1 and verify scan behavior via a focused input field

Device mapping:
- dev0 (scanner DUT)
- dev1 (barcode image display)

Image source:
- files/images/dcs_imgs/UPC-E1.jpg

Expected behavior:
1) UPC-E1 enabled: repeated scans succeed.
2) UPC-E1 disabled: repeated scans do not decode UPC-E1.
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
    scan_open_input_field,
    scan_clear_input_field,
    scan_get_input_field_text,
    scan_verify_decode_result,
    dcs_test_connect_u2,
    dcs_test_goto_data_processing_settings,
    dcs_test_goto_symbology_setting,
    dcs_test_set_option_checked,
)

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.realpath(__file__))))
def _load_device_serials_from_environment():
    dev0 = (os.environ.get("AUTONEXUS_DEV0_SN") or "").strip()
    dev1 = (os.environ.get("AUTONEXUS_DEV1_SN") or "").strip()
    if not dev0 or not dev1:
        raise RuntimeError("AUTONEXUS_DEV0_SN and AUTONEXUS_DEV1_SN must be provided by the web task")
    return dev0, dev1


DEV0_SERIAL, DEV1_SERIAL = _load_device_serials_from_environment()

SCRIPT_BASENAME = os.path.splitext(os.path.basename(__file__))[0]
IMG_ROOT = os.path.join(PROJECT_ROOT, "img")
SCRIPT_IMG_DIR = os.path.join(IMG_ROOT, SCRIPT_BASENAME)
os.makedirs(SCRIPT_IMG_DIR, exist_ok=True)

UPC_E1_IMAGE_LOCAL = os.path.join(PROJECT_ROOT, "files", "images", "dcs_imgs", "UPC-E1.jpg")
UPC_E1_IMAGE_REMOTE = "/sdcard/Pictures/UPC-E1.jpg"

_SCANNING_LABELS = ["Scanning"]
_INTERNAL_SCANNER_LABELS = ["Internal Scanner", "Internal scanner"]
_DEFAULT_PROFILE_LABELS = ["Default profile", "Default Profile"]
_DATA_PROCESSING_LABELS = ["Data Processing Settings", "Data Processing"]
_SYMBOLOGY_LABELS = ["Symbology Settings", "Symbology"]
_UPC_E_LABELS = ["UPC-E", "UPC E", "UPC-E1"]


class Test_EnableDisable_UPC_E1(unittest.TestCase):

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
        print("ANDROIDCN-37824: Enable/Disable UPC-E1")
        print("=" * 70)
        print(f"dev0(scanner): {DEV0_SERIAL}")
        print(f"dev1(image):   {DEV1_SERIAL}")

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

    def test_enable_disable_dcs_test(self):
        """Test steps:
        1. Open Data Processing Settings and enable Wedge output.
        2. Navigate to Symbology Settings and enable UPC-E1.
        3. Display the UPC-E1 reference barcode on the reference device and focus the scanner input field.
        4. Scan the barcode three times and verify the expected UPC-E1 value is returned each time.
        5. Disable UPC-E1, scan the same barcode three times, and verify the input field remains empty.
        """
        fail_count_enable = 0
        fail_count_disable = 0
        unexpected_results_enable = []
        unexpected_results_disable = []
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

        print("[Step 3] Open Symbology Settings -> UPC-E1")
        dcs_test_goto_symbology_setting(
            DEV0_SERIAL,
            self.d0,
            _SCANNING_LABELS,
            _INTERNAL_SCANNER_LABELS,
            _DEFAULT_PROFILE_LABELS,
            _SYMBOLOGY_LABELS,
            _UPC_E_LABELS,
        )
        save_step_screenshot(self.d0, "step03_dcs_test_setting", SCRIPT_IMG_DIR)

        print("[Step 4] Enable UPC-E1")
        self.assertTrue(dcs_test_set_option_checked(self.d0, "UPC-E1", True), "Failed to enable UPC-E1")
        save_step_screenshot(self.d0, "step04_enable_dcs_test", SCRIPT_IMG_DIR)

        print("[Step 5] Prepare reference image on dev1 and focus an input field on dev0")
        dcs_test_prepare_image_on_display_device(
            DEV1_SERIAL,
            self.d1,
            UPC_E1_IMAGE_LOCAL,
            UPC_E1_IMAGE_REMOTE,
        )
        self.assertTrue(scan_open_input_field(self.d0, DEV0_SERIAL), "Failed to open an input field")
        save_step_screenshot(self.d0, "step05_open_input_field", SCRIPT_IMG_DIR)

        print("[Step 6] Scan UPC-E1 multiple times (expect success each time)")
        success_results = []
        for i in range(1, 4):
            scan_clear_input_field(self.d0)
            trig_ok = dcs_test_trigger_honeywell_scan(DEV0_SERIAL)
            self.assertTrue(trig_ok, f"Scan trigger failed at enabled round {i}")
            detected = scan_verify_decode_result(self.d0, max_wait_seconds=6)
            value = scan_get_input_field_text(self.d0) if detected else ""
            print(f"  Enabled round {i}: {value}")
            if value == '1123456':
                success_results.append(value)
            else:
                unexpected_results_enable.append(value)
                fail_count_enable += 1
            #self.assertTrue(detected and value, f"No decode result when UPC-E1 enabled (round {i})")           
            save_step_screenshot(self.d0, f"step06_enabled_round{i}", SCRIPT_IMG_DIR)

        print("[Step 7] Disable UPC-E1")
        dcs_test_goto_symbology_setting(
            DEV0_SERIAL,
            self.d0,
            _SCANNING_LABELS,
            _INTERNAL_SCANNER_LABELS,
            _DEFAULT_PROFILE_LABELS,
            _SYMBOLOGY_LABELS,
            _UPC_E_LABELS,
        )
        self.assertTrue(dcs_test_set_option_checked(self.d0, "UPC-E1", False), "Failed to disable UPC-E1")
        save_step_screenshot(self.d0, "step07_disable_dcs_test", SCRIPT_IMG_DIR)

        print("[Step 8] Focus the input field on dev0 again")
        self.assertTrue(scan_open_input_field(self.d0, DEV0_SERIAL), "Failed to reopen an input field")
        save_step_screenshot(self.d0, "step08_reopen_input_field", SCRIPT_IMG_DIR)

        print("[Step 9] Scan UPC-E1 multiple times (expect decode fail)")
        for i in range(1, 4):
            scan_clear_input_field(self.d0)
            trig_ok = dcs_test_trigger_honeywell_scan(DEV0_SERIAL)
            self.assertTrue(trig_ok, f"Scan trigger failed at disabled round {i}")
            detected = scan_verify_decode_result(self.d0, max_wait_seconds=4)
            value = scan_get_input_field_text(self.d0) if detected else ""
            print(f"  Disabled round {i}: {value}")
            if detected and value.strip() not in {"", "Search...", "Search…"}:
                unexpected_results_disable.append(value)
                fail_count_disable += 1
            save_step_screenshot(self.d0, f"step09_disabled_round{i}", SCRIPT_IMG_DIR)

        self.assertEqual(
            fail_count_enable,
            0,
            "UPC-E1 cannot be decoded after enabling. Unexpected results: " + str(unexpected_results_enable),
        )

        self.assertEqual(
            fail_count_disable,
            0,
            "UPC-E1 still decoded after disabling. Unexpected results: " + str(unexpected_results_disable),
        )


if __name__ == "__main__":
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(Test_EnableDisable_UPC_E1)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)