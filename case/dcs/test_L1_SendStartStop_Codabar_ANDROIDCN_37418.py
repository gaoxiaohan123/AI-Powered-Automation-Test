# -*- coding:utf-8 -*-
"""Test Case: ANDROIDCN-37418 - Verify Send start/stop property for Codabar."""

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
CODABAR_IMAGE_LOCAL = os.path.join(PROJECT_ROOT, "files", "images", "dcs_imgs", "Codabar_with_check_digit.jpg")
CODABAR_IMAGE_REMOTE = "/sdcard/Pictures/Codabar_with_check_digit.jpg"

_SCANNING_LABELS = ["Scanning"]
_INTERNAL_SCANNER_LABELS = ["Internal Scanner", "Internal scanner"]
_DEFAULT_PROFILE_LABELS = ["Default profile", "Default Profile"]
_DATA_PROCESSING_LABELS = ["Data Processing Settings", "Data Processing"]
_SYMBOLOGY_LABELS = ["Symbology Settings", "Symbology"]
_CODABAR_LABELS = ["Codabar", "CodaBar", "CODABAR"]
_START_STOP_CHARACTERS = {"A", "B", "C", "D", "T", "N", "*", "E"}


def _load_device_serials_from_environment():
    dev0 = (os.environ.get("AUTONEXUS_DEV0_SN") or "").strip()
    dev1 = (os.environ.get("AUTONEXUS_DEV1_SN") or "").strip()
    if not dev0 or not dev1:
        raise RuntimeError("AUTONEXUS_DEV0_SN and AUTONEXUS_DEV1_SN must be provided by the web task")
    return dev0, dev1


DEV0_SERIAL, DEV1_SERIAL = _load_device_serials_from_environment()


class Test_SendStartStop_Codabar(unittest.TestCase):
    @classmethod
    def _ensure_device_sessions(cls):
        if hasattr(cls, "d0") and hasattr(cls, "d1"):
            return
        if not dcs_test_wait_device_online(DEV0_SERIAL, 25) or not dcs_test_wait_device_online(DEV1_SERIAL, 25):
            raise RuntimeError("Configured Codabar test devices are offline")
        cls.d0 = dcs_test_connect_u2(DEV0_SERIAL)
        cls.d1 = dcs_test_connect_u2(DEV1_SERIAL)

    @classmethod
    def setUpClass(cls):
        print("\n" + "=" * 70)
        print("ANDROIDCN-37418: Verify Send start/stop property for Codabar")
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

    def _goto_codabar_setting(self):
        dcs_test_goto_symbology_setting(
            DEV0_SERIAL, self.d0, _SCANNING_LABELS, _INTERNAL_SCANNER_LABELS,
            _DEFAULT_PROFILE_LABELS, _SYMBOLOGY_LABELS, _CODABAR_LABELS,
        )

    def _verify_start_stop_output(self, state_name, expect_start_stop):
        failures = []
        for round_number in range(1, 4):
            dcs_test_prepare_image_on_display_device(DEV1_SERIAL, self.d1, CODABAR_IMAGE_LOCAL, CODABAR_IMAGE_REMOTE)
            self.assertTrue(scan_open_input_field(self.d0, DEV0_SERIAL), "Failed to focus input field")
            scan_clear_input_field(self.d0)
            self.assertTrue(dcs_test_trigger_honeywell_scan(DEV0_SERIAL), "Scan trigger failed")
            detected = scan_verify_decode_result(self.d0, max_wait_seconds=5)
            value = scan_get_input_field_text(self.d0) if detected else ""
            has_start_stop = len(value) >= 2 and value[0] in _START_STOP_CHARACTERS and value[-1] in _START_STOP_CHARACTERS
            print(f"  {state_name} round {round_number}: detected={detected}, value='{value}', has_start_stop={has_start_stop}")
            if not detected or has_start_stop != expect_start_stop:
                failures.append(f"round {round_number}: detected={detected}, value='{value}', has_start_stop={has_start_stop}")
            save_step_screenshot(self.d0, f"{state_name}_round{round_number}", SCRIPT_IMG_DIR)
        return failures

    def test_send_start_stop_codabar(self):
        """Test steps:
        1. Open Data Processing Settings and enable Wedge.
        2. Enable Codabar and Send start/stop.
        3. Verify start and stop characters are sent.
        4. Disable Send start/stop.
        5. Verify start and stop characters are omitted.
        """
        print("\n[Step 1] Open Data Processing Settings and enable Wedge")
        dcs_test_goto_data_processing_settings(DEV0_SERIAL, self.d0, _SCANNING_LABELS, _INTERNAL_SCANNER_LABELS, _DEFAULT_PROFILE_LABELS, _DATA_PROCESSING_LABELS)
        self.assertTrue(dcs_test_set_option_checked(self.d0, "Wedge", True), "Failed to enable Wedge")
        save_step_screenshot(self.d0, "step01_enable_wedge", SCRIPT_IMG_DIR)

        print("[Step 2] Enable Codabar and Send start/stop")
        self._goto_codabar_setting()
        for label, enabled in (("Codabar", True), ("Send start/stop", True)):
            self.assertTrue(dcs_test_set_option_checked(self.d0, label, enabled), f"Failed to set {label}={enabled}")
        save_step_screenshot(self.d0, "step02_start_stop_enabled", SCRIPT_IMG_DIR)

        print("[Step 3] Verify start and stop characters are sent")
        enabled_failures = self._verify_start_stop_output("start_stop_enabled", True)

        print("[Step 4] Disable Send start/stop")
        self._goto_codabar_setting()
        self.assertTrue(dcs_test_set_option_checked(self.d0, "Send start/stop", False), "Failed to disable Send start/stop")
        save_step_screenshot(self.d0, "step04_start_stop_disabled", SCRIPT_IMG_DIR)

        print("[Step 5] Verify start and stop characters are omitted")
        disabled_failures = self._verify_start_stop_output("start_stop_disabled", False)

        self.assertFalse(enabled_failures or disabled_failures, f"Codabar Send start/stop behavior mismatch. Enabled failures: {enabled_failures}; Disabled failures: {disabled_failures}")


if __name__ == "__main__":
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(Test_SendStartStop_Codabar)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)