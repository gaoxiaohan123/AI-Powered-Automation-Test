# -*- coding:utf-8 -*-
"""Test Case: ANDROIDCN-37545 - Verify UPC-A Add-on separator with Add-on required enabled."""

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
    "no_add_on": ("UPC-A.jpg", None, None),
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


class Test_AddOnSeparatorRequired_UPC_A(unittest.TestCase):
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
        print("ANDROIDCN-37545: Verify UPC-A Add-on separator with Add-on required")
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

    def _prepare_image_and_focus_input(self, image_key):
        filename, _, _ = UPC_A_IMAGES[image_key]
        local_path = os.path.join(PROJECT_ROOT, "files", "images", "dcs_imgs", filename)
        remote_path = f"/sdcard/Pictures/{filename}"
        dcs_test_prepare_image_on_display_device(DEV1_SERIAL, self.d1, local_path, remote_path)
        self.assertTrue(scan_open_input_field(self.d0, DEV0_SERIAL), "Failed to focus input field")

    def _verify_expected_output(self, image_key, expected_value, state_name):
        failures = []
        for round_number in range(1, 4):
            self._prepare_image_and_focus_input(image_key)
            scan_clear_input_field(self.d0)
            self.assertTrue(dcs_test_trigger_honeywell_scan(DEV0_SERIAL), "Scan trigger failed")
            detected = scan_verify_decode_result(self.d0, max_wait_seconds=5)
            value = scan_get_input_field_text(self.d0) if detected else ""
            print(f"  {state_name} {image_key}, round {round_number}: detected={detected}, value='{value}'")
            if not detected or value != expected_value:
                failures.append(f"{image_key} round {round_number}: detected={detected}, value='{value}'")
            save_step_screenshot(self.d0, f"{state_name}_{image_key}_round{round_number}", SCRIPT_IMG_DIR)
        return failures

    def _verify_no_output(self, state_name):
        failures = []
        for round_number in range(1, 4):
            self._prepare_image_and_focus_input("no_add_on")
            scan_clear_input_field(self.d0)
            self.assertTrue(dcs_test_trigger_honeywell_scan(DEV0_SERIAL), "Scan trigger failed")
            detected = scan_verify_decode_result(self.d0, max_wait_seconds=5)
            value = scan_get_input_field_text(self.d0) if detected else ""
            print(f"  {state_name} no_add_on, round {round_number}: detected={detected}, value='{value}'")
            if detected or value:
                failures.append(f"no_add_on round {round_number}: detected={detected}, value='{value}'")
            save_step_screenshot(self.d0, f"{state_name}_no_add_on_round{round_number}", SCRIPT_IMG_DIR)
        return failures

    def test_add_on_separator_required_upc_a(self):
        """Test steps:
        1. Open Data Processing Settings and enable Wedge.
        2. Enable UPC-A, Add-on 2/5, Add-on required, and Add-on separator.
        3. Verify required Add-on values include a space and base UPC-A is rejected.
        4. Disable Add-on separator.
        5. Verify required Add-on values contain no space and base UPC-A remains rejected.
        """
        print("\n[Step 1] Open Data Processing Settings and enable Wedge")
        dcs_test_goto_data_processing_settings(
            DEV0_SERIAL, self.d0, _SCANNING_LABELS, _INTERNAL_SCANNER_LABELS,
            _DEFAULT_PROFILE_LABELS, _DATA_PROCESSING_LABELS,
        )
        self.assertTrue(dcs_test_set_option_checked(self.d0, "Wedge", True), "Failed to enable Wedge")
        save_step_screenshot(self.d0, "step01_enable_wedge", SCRIPT_IMG_DIR)

        print("[Step 2] Enable UPC-A, Add-on 2/5, Add-on required, and Add-on separator")
        self._goto_upc_a_setting()
        for label, enabled in (("Enable UPC-A", True), ("Send number system", True), ("Send check digit", True),
                               ("Add-on 2", True), ("Add-on 5", True), ("Add-on required", True),
                               ("Add-on separator", True)):
            self.assertTrue(dcs_test_set_option_checked(self.d0, label, enabled), f"Failed to set {label}={enabled}")
        save_step_screenshot(self.d0, "step02_separator_enabled", SCRIPT_IMG_DIR)

        print("[Step 3] Verify required Add-on values contain a space and base UPC-A is rejected")
        with_separator_failures = []
        for image_key in ("add_on_5", "add_on_2"):
            with_separator_failures.extend(self._verify_expected_output(image_key, UPC_A_IMAGES[image_key][1], "enabled"))
        with_separator_failures.extend(self._verify_no_output("enabled"))

        print("[Step 4] Disable Add-on separator")
        self._goto_upc_a_setting()
        self.assertTrue(dcs_test_set_option_checked(self.d0, "Add-on separator", False), "Failed to disable Add-on separator")
        save_step_screenshot(self.d0, "step04_separator_disabled", SCRIPT_IMG_DIR)

        print("[Step 5] Verify required Add-on values contain no space and base UPC-A remains rejected")
        without_separator_failures = []
        for image_key in ("add_on_5", "add_on_2"):
            without_separator_failures.extend(self._verify_expected_output(image_key, UPC_A_IMAGES[image_key][2], "disabled"))
        without_separator_failures.extend(self._verify_no_output("disabled"))

        self.assertFalse(
            with_separator_failures or without_separator_failures,
            f"Add-on required separator behavior mismatch. With separator: {with_separator_failures}; "
            f"Without separator: {without_separator_failures}",
        )


if __name__ == "__main__":
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(Test_AddOnSeparatorRequired_UPC_A)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)