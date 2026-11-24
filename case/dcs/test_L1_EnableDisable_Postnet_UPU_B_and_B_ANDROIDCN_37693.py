# -*- coding:utf-8 -*-
"""Test Case: ANDROIDCN-37693 - Enable/Disable Postnet,UPU(B and B) and verify scan behavior."""

import os
import sys
import time
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
    dcs_test_scroll_find_and_click,
    dcs_test_set_option_checked,
)

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.realpath(__file__))))
SCRIPT_BASENAME = os.path.splitext(os.path.basename(__file__))[0]
SCRIPT_IMG_DIR = os.path.join(PROJECT_ROOT, "img", SCRIPT_BASENAME)
os.makedirs(SCRIPT_IMG_DIR, exist_ok=True)
_IMAGE_DIR = os.path.join(PROJECT_ROOT, "files", "images", "dcs_imgs")
# (name, local image, remote image, expected value); values come from the fixture text.
SAMPLES = [
    ("bnb", os.path.join(_IMAGE_DIR, "Postnet_BandB_gen.png"), "/sdcard/Pictures/Postnet_BandB_gen.png", "22182"),
    ("upu", os.path.join(_IMAGE_DIR, "UPU.jpg"), "/sdcard/Pictures/UPU.jpg", "J18CUSA8E6N062315014880T"),
]

_SCANNING_LABELS = ["Scanning"]
_INTERNAL_SCANNER_LABELS = ["Internal Scanner", "Internal scanner"]
_DEFAULT_PROFILE_LABELS = ["Default profile", "Default Profile"]
_DATA_PROCESSING_LABELS = ["Data Processing Settings", "Data Processing"]
_SYMBOLOGY_LABELS = ["Symbology Settings", "Symbology"]
_POSTAL_LABELS = ["2D Postal Settings", "2D Postal"]
_ENABLE_LABEL = "Enable"
_POSTAL_DISABLED_CHOICE = "None"
_POSTAL_ENABLE_CHOICE = "Postnet, UPU (B and B)"


def _load_device_serials_from_environment():
    dev0 = (os.environ.get("AUTONEXUS_DEV0_SN") or "").strip()
    dev1 = (os.environ.get("AUTONEXUS_DEV1_SN") or "").strip()
    if not dev0 or not dev1:
        raise RuntimeError("AUTONEXUS_DEV0_SN and AUTONEXUS_DEV1_SN must be provided by the web task")
    return dev0, dev1


DEV0_SERIAL, DEV1_SERIAL = _load_device_serials_from_environment()


class Test_EnableDisable_Postnet_UPU_B_and_B(unittest.TestCase):
    @classmethod
    def _ensure_device_sessions(cls):
        if hasattr(cls, "d0") and hasattr(cls, "d1"):
            return
        if not dcs_test_wait_device_online(DEV0_SERIAL, 25) or not dcs_test_wait_device_online(DEV1_SERIAL, 25):
            raise RuntimeError("Configured Postnet,UPU(B and B) test devices are offline")
        cls.d0 = dcs_test_connect_u2(DEV0_SERIAL)
        cls.d1 = dcs_test_connect_u2(DEV1_SERIAL)

    @classmethod
    def setUpClass(cls):
        print("\n" + "=" * 70)
        print("ANDROIDCN-37693: Enable/Disable Postnet,UPU(B and B)")
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

    def _set_postal_choice(self, choice, step_name):
        dcs_test_goto_symbology_setting(
            DEV0_SERIAL, self.d0, _SCANNING_LABELS, _INTERNAL_SCANNER_LABELS,
            _DEFAULT_PROFILE_LABELS, _SYMBOLOGY_LABELS, _POSTAL_LABELS,
        )
        self.assertTrue(dcs_test_scroll_find_and_click(self.d0, [_ENABLE_LABEL]), "Cannot open 2D Postal Enable dialog")
        self.assertTrue(dcs_test_scroll_find_and_click(self.d0, [choice]), f"Cannot select '{choice}'")
        save_step_screenshot(self.d0, step_name, SCRIPT_IMG_DIR)
        time.sleep(3)

    def _scan_samples(self, state_name, expect_decode):
        for sample_name, local_image, remote_image, expected_value in SAMPLES:
            values = []
            for round_number in range(1, 4):
                dcs_test_prepare_image_on_display_device(DEV1_SERIAL, self.d1, local_image, remote_image)
                self.assertTrue(scan_open_input_field(self.d0, DEV0_SERIAL), "Failed to focus input field")
                scan_clear_input_field(self.d0)
                self.assertTrue(dcs_test_trigger_honeywell_scan(DEV0_SERIAL), f"Scan trigger failed for {sample_name} {state_name} round {round_number}")
                detected = scan_verify_decode_result(self.d0, max_wait_seconds=5)
                value = scan_get_input_field_text(self.d0) if detected else ""
                print(f"  {state_name} {sample_name} round {round_number}: detected={detected}, value='{value}'")
                save_step_screenshot(self.d0, f"{state_name}_{sample_name}_round{round_number}", SCRIPT_IMG_DIR)
                self.assertEqual(detected, expect_decode, f"Unexpected {sample_name} decode state for {state_name} round {round_number}, value='{value}'")
                values.append(value)
            if expect_decode:
                self.assertEqual(values, [expected_value] * 3, f"{sample_name} decoded value mismatch: {values}")

    def test_enable_disable_postnet_upu_b_and_b(self):
        """Test steps:
        1. Open Data Processing Settings and enable Wedge.
        2. Enable Postnet,UPU(B and B) and verify all samples decode correctly more than once.
        3. Disable 2D Postal and verify no sample decodes more than once.
        """
        print("\n[Step 1] Open Data Processing Settings and enable Wedge")
        dcs_test_goto_data_processing_settings(DEV0_SERIAL, self.d0, _SCANNING_LABELS, _INTERNAL_SCANNER_LABELS, _DEFAULT_PROFILE_LABELS, _DATA_PROCESSING_LABELS)
        self.assertTrue(dcs_test_set_option_checked(self.d0, "Wedge", True), "Failed to enable Wedge")

        print("[Step 2] Enable Postnet,UPU(B and B) and verify repeated decoding")
        self._set_postal_choice(_POSTAL_ENABLE_CHOICE, "step02_postnet_upu_b_and_b_enabled")
        self._scan_samples("step02_enabled", True)

        print("[Step 3] Disable Postnet,UPU(B and B) and verify repeated rejection")
        self._set_postal_choice(_POSTAL_DISABLED_CHOICE, "step03_postnet_upu_b_and_b_disabled")
        self._scan_samples("step03_disabled", False)


if __name__ == "__main__":
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(Test_EnableDisable_Postnet_UPU_B_and_B)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)
