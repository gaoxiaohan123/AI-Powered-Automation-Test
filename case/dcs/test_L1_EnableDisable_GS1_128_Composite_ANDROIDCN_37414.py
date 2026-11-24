# -*- coding:utf-8 -*-
"""Test Case: ANDROIDCN-37414 - Enable/Disable GS1-128 Composite and verify scan behavior."""

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
COMPOSITE_IMAGE_LOCAL = os.path.join(PROJECT_ROOT, "files", "images", "dcs_imgs", "GS1_128_Composite_gen.png")
COMPOSITE_IMAGE_REMOTE = "/sdcard/Pictures/GS1_128_Composite_gen.png"
EXPECTED_ENABLED = "0199012345678909170712042119AN47954769"
EXPECTED_DISABLED = "0199012345678909"

_SCANNING_LABELS = ["Scanning"]
_INTERNAL_SCANNER_LABELS = ["Internal Scanner", "Internal scanner"]
_DEFAULT_PROFILE_LABELS = ["Default profile", "Default Profile"]
_DATA_PROCESSING_LABELS = ["Data Processing Settings", "Data Processing"]
_SYMBOLOGY_LABELS = ["Symbology Settings", "Symbology"]
_GS1_128_LABELS = ["GS1-128", "GS1 128"]
_COMPOSITE_LABELS = ["Composite"]
_COMPOSITE_OPTIONS = ("Composite with UPC enabled", "Combine composites")


def _load_device_serials_from_environment():
    dev0 = (os.environ.get("AUTONEXUS_DEV0_SN") or "").strip()
    dev1 = (os.environ.get("AUTONEXUS_DEV1_SN") or "").strip()
    if not dev0 or not dev1:
        raise RuntimeError("AUTONEXUS_DEV0_SN and AUTONEXUS_DEV1_SN must be provided by the web task")
    return dev0, dev1


DEV0_SERIAL, DEV1_SERIAL = _load_device_serials_from_environment()


class Test_EnableDisable_GS1_128_Composite(unittest.TestCase):
    @classmethod
    def _ensure_device_sessions(cls):
        if hasattr(cls, "d0") and hasattr(cls, "d1"):
            return
        if not dcs_test_wait_device_online(DEV0_SERIAL, 25) or not dcs_test_wait_device_online(DEV1_SERIAL, 25):
            raise RuntimeError("Configured GS1-128 Composite test devices are offline")
        cls.d0 = dcs_test_connect_u2(DEV0_SERIAL)
        cls.d1 = dcs_test_connect_u2(DEV1_SERIAL)

    @classmethod
    def setUpClass(cls):
        print("\n" + "=" * 70)
        print("ANDROIDCN-37414: Enable/Disable GS1-128 Composite")
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

    def _goto_symbology(self, symbology_labels):
        dcs_test_goto_symbology_setting(
            DEV0_SERIAL, self.d0, _SCANNING_LABELS, _INTERNAL_SCANNER_LABELS,
            _DEFAULT_PROFILE_LABELS, _SYMBOLOGY_LABELS, symbology_labels,
        )

    def _set_composite_options(self, enabled):
        self._goto_symbology(_COMPOSITE_LABELS)
        for label in _COMPOSITE_OPTIONS:
            self.assertTrue(dcs_test_set_option_checked(self.d0, label, enabled), f"Failed to set {label}={enabled}")

    def _scan_composite(self, state_name):
        values = []
        for round_number in range(1, 4):
            dcs_test_prepare_image_on_display_device(DEV1_SERIAL, self.d1, COMPOSITE_IMAGE_LOCAL, COMPOSITE_IMAGE_REMOTE)
            self.assertTrue(scan_open_input_field(self.d0, DEV0_SERIAL), "Failed to focus input field")
            scan_clear_input_field(self.d0)
            for _attempt in range(2):
                self.assertTrue(dcs_test_trigger_honeywell_scan(DEV0_SERIAL), f"Scan trigger failed at {state_name} round {round_number}")
                detected = scan_verify_decode_result(self.d0, max_wait_seconds=5)
                if detected:
                    break
            value = scan_get_input_field_text(self.d0) if detected else ""
            print(f"  {state_name} round {round_number}: detected={detected}, value='{value}'")
            save_step_screenshot(self.d0, f"{state_name}_round{round_number}", SCRIPT_IMG_DIR)
            values.append(value if detected else "")
        return values

    def test_enable_disable_gs1_128_composite(self):
        """Test steps:
        1. Open Data Processing Settings and enable Wedge.
        2. Enable GS1-128.
        3. Enable Composite, "Composite with UPC enabled" and "Combine composites".
        4. Scan a GS1-128 Composite barcode three times and verify it decodes consistently.
        5. Disable "Composite with UPC enabled" and "Combine composites".
        6. Scan the barcode three times and verify only the GS1-128 linear result is output.
        """
        print("\n[Step 1] Open Data Processing Settings and enable Wedge")
        dcs_test_goto_data_processing_settings(DEV0_SERIAL, self.d0, _SCANNING_LABELS, _INTERNAL_SCANNER_LABELS, _DEFAULT_PROFILE_LABELS, _DATA_PROCESSING_LABELS)
        self.assertTrue(dcs_test_set_option_checked(self.d0, "Wedge", True), "Failed to enable Wedge")
        save_step_screenshot(self.d0, "step01_enable_wedge", SCRIPT_IMG_DIR)

        print("[Step 2] Enable GS1-128")
        self._goto_symbology(_GS1_128_LABELS)
        self.assertTrue(dcs_test_set_option_checked(self.d0, "GS1-128", True), "Failed to enable GS1-128")
        save_step_screenshot(self.d0, "step02_enable_gs1_128", SCRIPT_IMG_DIR)

        print("[Step 3] Enable Composite options")
        self._goto_symbology(_COMPOSITE_LABELS)
        self.assertTrue(dcs_test_set_option_checked(self.d0, "Composite", True), "Failed to enable Composite")
        self._set_composite_options(True)
        save_step_screenshot(self.d0, "step03_enable_composite", SCRIPT_IMG_DIR)

        print("[Step 4] Verify the combined composite result when enabled")
        enabled_values = self._scan_composite("enabled")

        print("[Step 5] Disable Composite options")
        self._set_composite_options(False)
        save_step_screenshot(self.d0, "step05_disable_composite", SCRIPT_IMG_DIR)

        print("[Step 6] Verify only the GS1-128 linear result when disabled")
        disabled_values = self._scan_composite("disabled")

        failures = []
        for round_number, (enabled, disabled) in enumerate(zip(enabled_values, disabled_values), 1):
            if enabled != EXPECTED_ENABLED:
                failures.append(f"round {round_number}: enabled value '{enabled}' != expected '{EXPECTED_ENABLED}'")
            if disabled != EXPECTED_DISABLED:
                failures.append(f"round {round_number}: disabled value '{disabled}' != expected '{EXPECTED_DISABLED}'")
        self.assertFalse(failures, f"GS1-128 Composite behavior mismatch: {failures}")


if __name__ == "__main__":
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(Test_EnableDisable_GS1_128_Composite)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)
