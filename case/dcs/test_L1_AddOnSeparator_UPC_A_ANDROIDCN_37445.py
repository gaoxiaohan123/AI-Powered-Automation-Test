# -*- coding:utf-8 -*-
"""Test Case: ANDROIDCN-37445 - Verify UPC-A Add-on separator with Add-on required disabled."""

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

UPC_A_IMAGES = {
    "add_on_5": ("UPC-A-with-5-addendas.jpg", "345634567896 25678", "34563456789625678"),
    "add_on_2": ("UPC-A-with-2-addendas.jpg", "012345678912 23", "01234567891223"),
    "no_add_on": ("UPC-A.jpg", "012345678905", "012345678905"),
}
_SCANNING_LABELS = ["Scanning"]
_INTERNAL_SCANNER_LABELS = ["Internal Scanner", "Internal scanner"]
_DEFAULT_PROFILE_LABELS = ["Default profile", "Default Profile"]
_DATA_PROCESSING_LABELS = ["Data Processing Settings", "Data Processing"]
_SYMBOLOGY_LABELS = ["Symbology Settings", "Symbology"]
_UPC_A_LABELS = ["UPC-A", "UPC A"]


def _load_device_serials_from_environment():
    dev0 = (os.environ.get("AUTONEXUS_DEV0_SN") or "").strip()
    dev1 = (os.environ.get("AUTONEXUS_DEV1_SN") or "").strip()
    if not dev0 or not dev1:
        raise RuntimeError("AUTONEXUS_DEV0_SN and AUTONEXUS_DEV1_SN must be provided by the web task")
    return dev0, dev1


DEV0_SERIAL, DEV1_SERIAL = _load_device_serials_from_environment()


class Test_AddOnSeparator_UPC_A(unittest.TestCase):
    @classmethod
    def _ensure_device_sessions(cls):
        if hasattr(cls, "d0") and hasattr(cls, "d1"):
            return
        if not dcs_test_wait_device_online(DEV0_SERIAL, 25) or not dcs_test_wait_device_online(DEV1_SERIAL, 25):
            raise RuntimeError("Configured UPC-A test devices are offline")
        cls.d0 = dcs_test_connect_u2(DEV0_SERIAL)
        cls.d1 = dcs_test_connect_u2(DEV1_SERIAL)

    @classmethod
    def setUpClass(cls):
        print("\n" + "=" * 70)
        print("ANDROIDCN-37445: Verify UPC-A Add-on separator")
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

    def _goto_upc_a_setting(self):
        dcs_test_goto_symbology_setting(
            DEV0_SERIAL, self.d0, _SCANNING_LABELS, _INTERNAL_SCANNER_LABELS,
            _DEFAULT_PROFILE_LABELS, _SYMBOLOGY_LABELS, _UPC_A_LABELS,
        )

    def _prepare_and_verify(self, image_key, expected_value, state_name):
        filename, _, _ = UPC_A_IMAGES[image_key]
        local_path = os.path.join(PROJECT_ROOT, "files", "images", "dcs_imgs", filename)
        remote_path = f"/sdcard/Pictures/{filename}"
        dcs_test_prepare_image_on_display_device(DEV1_SERIAL, self.d1, local_path, remote_path)
        self.assertTrue(scan_open_input_field(self.d0, DEV0_SERIAL), "Failed to focus input field")

        failures = []
        for round_number in range(1, 4):
            last_result = ""
            for attempt_number in range(1, 6):
                if attempt_number > 1:
                    dcs_test_prepare_image_on_display_device(DEV1_SERIAL, self.d1, local_path, remote_path)
                    self.assertTrue(scan_open_input_field(self.d0, DEV0_SERIAL), "Failed to refocus input field")
                scan_clear_input_field(self.d0)
                self.assertTrue(dcs_test_trigger_honeywell_scan(DEV0_SERIAL), "Scan trigger failed")
                detected = scan_verify_decode_result(self.d0, max_wait_seconds=3)
                value = scan_get_input_field_text(self.d0) if detected else ""
                print(
                    f"  {state_name} {image_key}, round {round_number}, attempt {attempt_number}: "
                    f"detected={detected}, value='{value}'"
                )
                save_step_screenshot(
                    self.d0,
                    f"{state_name}_{image_key}_round{round_number}_attempt{attempt_number}",
                    SCRIPT_IMG_DIR,
                )
                if detected and value == expected_value:
                    break
                last_result = f"detected={detected}, value='{value}'"
            else:
                failures.append(f"{image_key} round {round_number}: {last_result}")
        return failures

    def test_add_on_separator_upc_a(self):
        """Test steps:
        1. Open Data Processing Settings and enable Wedge.
        2. Enable UPC-A, Add-on 2/5, and Add-on separator.
        3. Verify Add-on values include a space separator.
        4. Disable Add-on separator.
        5. Verify Add-on values contain no separator.
        """
        print("\n[Step 1] Open Data Processing Settings and enable Wedge")
        dcs_test_goto_data_processing_settings(
            DEV0_SERIAL, self.d0, _SCANNING_LABELS, _INTERNAL_SCANNER_LABELS,
            _DEFAULT_PROFILE_LABELS, _DATA_PROCESSING_LABELS,
        )
        self.assertTrue(dcs_test_set_option_checked(self.d0, "Wedge", True), "Failed to enable Wedge")
        save_step_screenshot(self.d0, "step01_enable_wedge", SCRIPT_IMG_DIR)

        print("[Step 2] Enable UPC-A, Add-on 2/5, and Add-on separator")
        self._goto_upc_a_setting()
        for label, enabled in (("Enable UPC-A", True), ("Send number system", True), ("Send check digit", True),
                               ("Add-on 2", True), ("Add-on 5", True), ("Add-on required", False),
                               ("Add-on separator", True)):
            self.assertTrue(dcs_test_set_option_checked(self.d0, label, enabled), f"Failed to set {label}={enabled}")
        save_step_screenshot(self.d0, "step02_separator_enabled", SCRIPT_IMG_DIR)

        print("[Step 3] Verify Add-on values contain a space separator")
        with_separator_failures = []
        for image_key in ("add_on_5", "add_on_2", "no_add_on"):
            with_separator_failures.extend(self._prepare_and_verify(image_key, UPC_A_IMAGES[image_key][1], "enabled"))

        print("[Step 4] Disable Add-on separator")
        self._goto_upc_a_setting()
        self.assertTrue(dcs_test_set_option_checked(self.d0, "Add-on separator", False), "Failed to disable Add-on separator")
        save_step_screenshot(self.d0, "step04_separator_disabled", SCRIPT_IMG_DIR)

        print("[Step 5] Verify Add-on values contain no separator")
        without_separator_failures = []
        for image_key in ("add_on_5", "add_on_2", "no_add_on"):
            without_separator_failures.extend(self._prepare_and_verify(image_key, UPC_A_IMAGES[image_key][2], "disabled"))

        self.assertFalse(
            with_separator_failures or without_separator_failures,
            f"Add-on separator behavior mismatch. With separator: {with_separator_failures}; "
            f"Without separator: {without_separator_failures}",
        )


if __name__ == "__main__":
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(Test_AddOnSeparator_UPC_A)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)