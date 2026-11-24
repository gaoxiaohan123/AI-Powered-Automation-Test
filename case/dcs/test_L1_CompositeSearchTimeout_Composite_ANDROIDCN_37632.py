# -*- coding:utf-8 -*-
"""Test Case: ANDROIDCN-37632 - Verify the Composite search timeout property."""

import os
import sys
import time
import unittest

from uiautomator2.exceptions import UiObjectNotFoundError

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from common.adb_common import (
    save_step_screenshot,
    dcs_test_cleanup_devices,
    dcs_test_press_home,
    dcs_test_prepare_image_on_display_device,
    dcs_test_wait_device_online,
    dcs_test_wake_and_unlock,
    scan_send_scan_button_broadcast,
)
from common.common_method import (
    scan_clear_input_field,
    scan_get_input_field_text,
    scan_open_input_field,
    dcs_test_connect_u2,
    dcs_test_goto_data_processing_settings,
    dcs_test_goto_symbology_setting,
    dcs_test_set_option_checked,
)

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.realpath(__file__))))
SCRIPT_BASENAME = os.path.splitext(os.path.basename(__file__))[0]
SCRIPT_IMG_DIR = os.path.join(PROJECT_ROOT, "img", SCRIPT_BASENAME)
os.makedirs(SCRIPT_IMG_DIR, exist_ok=True)
EAN13_IMAGE_LOCAL = os.path.join(PROJECT_ROOT, "files", "images", "dcs_imgs", "EAN13_Normal_gen.png")
EAN13_IMAGE_REMOTE = "/sdcard/Pictures/EAN13_Normal_gen.png"
EXPECTED_EAN13 = "331234567890"

_SCANNING_LABELS = ["Scanning"]
_INTERNAL_SCANNER_LABELS = ["Internal Scanner", "Internal scanner"]
_DEFAULT_PROFILE_LABELS = ["Default profile", "Default Profile"]
_DATA_PROCESSING_LABELS = ["Data Processing Settings", "Data Processing"]
_SYMBOLOGY_LABELS = ["Symbology Settings", "Symbology"]
_EAN13_LABELS = ["EAN-13", "EAN13", "EAN 13"]
_COMPOSITE_LABELS = ["Composite"]
_COMPOSITE_OPTIONS = ("Composite", "Composite with UPC enabled", "Combine composites")
_TIMEOUT_SETTING = "Composite search timeout"
_EDIT_RESOURCE_ID = "android:id/edit"
_OK_RESOURCE_ID = "android:id/button1"
_CANCEL_RESOURCE_ID = "android:id/button2"
_SCAN_ROUNDS = 5
# The scan path adds ADB/UI polling noise, so only the relative difference is checked.
_MIN_DELAY_DIFF_SECONDS = 0.1


def _load_device_serials_from_environment():
    dev0 = (os.environ.get("AUTONEXUS_DEV0_SN") or "").strip()
    dev1 = (os.environ.get("AUTONEXUS_DEV1_SN") or "").strip()
    if not dev0 or not dev1:
        raise RuntimeError("AUTONEXUS_DEV0_SN and AUTONEXUS_DEV1_SN must be provided by the web task")
    return dev0, dev1


DEV0_SERIAL, DEV1_SERIAL = _load_device_serials_from_environment()


class Test_CompositeSearchTimeout_Composite(unittest.TestCase):
    @classmethod
    def _ensure_device_sessions(cls):
        if hasattr(cls, "d0") and hasattr(cls, "d1"):
            return
        if not dcs_test_wait_device_online(DEV0_SERIAL, 25) or not dcs_test_wait_device_online(DEV1_SERIAL, 25):
            raise RuntimeError("Configured Composite test devices are offline")
        cls.d0 = dcs_test_connect_u2(DEV0_SERIAL)
        cls.d1 = dcs_test_connect_u2(DEV1_SERIAL)

    @classmethod
    def setUpClass(cls):
        print("\n" + "=" * 70)
        print("ANDROIDCN-37632: Verify the Composite search timeout property")
        print("=" * 70)
        cls._ensure_device_sessions()

    def setUp(self):
        self.__class__._ensure_device_sessions()
        dcs_test_wake_and_unlock(DEV0_SERIAL, self.d0)
        dcs_test_wake_and_unlock(DEV1_SERIAL, self.d1)
        dcs_test_press_home(DEV0_SERIAL)
        dcs_test_press_home(DEV1_SERIAL)

    def tearDown(self):
        if self.d0(resourceId=_CANCEL_RESOURCE_ID).exists:
            self.d0(resourceId=_CANCEL_RESOURCE_ID).click()
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

    def _set_search_timeout(self, value):
        for attempt in range(1, 4):
            self._goto_symbology(_COMPOSITE_LABELS)
            self.d0(text=_TIMEOUT_SETTING).click()
            edit = self.d0(resourceId=_EDIT_RESOURCE_ID)
            if not edit.wait(timeout=5):
                continue
            time.sleep(1)
            try:
                edit.set_text(str(value))
            except UiObjectNotFoundError:
                print(f"  {_TIMEOUT_SETTING} dialog changed while typing, retry {attempt}")
                self.d0.press("back")
                continue
            self.d0(resourceId=_OK_RESOURCE_ID).click()
            return
        self.fail(f"Failed to set {_TIMEOUT_SETTING} to {value}")

    def _measure_scan_delay(self, state_name):
        delays = []
        for round_number in range(1, _SCAN_ROUNDS + 1):
            dcs_test_prepare_image_on_display_device(DEV1_SERIAL, self.d1, EAN13_IMAGE_LOCAL, EAN13_IMAGE_REMOTE)
            self.assertTrue(scan_open_input_field(self.d0, DEV0_SERIAL), "Failed to focus input field")
            scan_clear_input_field(self.d0)
            started = time.monotonic()
            self.assertTrue(scan_send_scan_button_broadcast(DEV0_SERIAL, 1), f"Scan trigger failed at {state_name} round {round_number}")
            value, elapsed = "", None
            while time.monotonic() - started < 6:
                text = (scan_get_input_field_text(self.d0) or "").strip()
                if text and text not in ("Search...", "Search…"):
                    value, elapsed = text, time.monotonic() - started
                    break
            scan_send_scan_button_broadcast(DEV0_SERIAL, 0)
            self.assertTrue(value, f"EAN-13 was not decoded at {state_name} round {round_number}")
            self.assertEqual(value, EXPECTED_EAN13, f"Decoded value mismatch at {state_name} round {round_number}")
            print(f"  {state_name} round {round_number}: value='{value}', delay={elapsed:.3f}s")
            save_step_screenshot(self.d0, f"{state_name}_round{round_number}", SCRIPT_IMG_DIR)
            delays.append(elapsed)
        best = min(delays)
        print(f"  {state_name} min delay: {best:.3f}s, all={[round(x, 3) for x in delays]}")
        return best

    def test_composite_search_timeout(self):
        """Test steps:
        1. Open Data Processing Settings and enable Wedge.
        2. Enable EAN-13.
        3. Enable Composite, "Composite with UPC enabled" and "Combine composites".
        4. Keep Composite search timeout at 300 and scan a normal EAN-13 barcode several times.
        5. Change Composite search timeout to 10 and scan again; the delay must be shorter.
        6. Disable the Composite options, restore the timeout to 300 and scan again; there must be no extra delay.
        """
        print("\n[Step 1] Open Data Processing Settings and enable Wedge")
        dcs_test_goto_data_processing_settings(DEV0_SERIAL, self.d0, _SCANNING_LABELS, _INTERNAL_SCANNER_LABELS, _DEFAULT_PROFILE_LABELS, _DATA_PROCESSING_LABELS)
        self.assertTrue(dcs_test_set_option_checked(self.d0, "Wedge", True), "Failed to enable Wedge")
        save_step_screenshot(self.d0, "step01_enable_wedge", SCRIPT_IMG_DIR)

        print("[Step 2] Enable EAN-13")
        self._goto_symbology(_EAN13_LABELS)
        self.assertTrue(dcs_test_set_option_checked(self.d0, "EAN-13", True), "Failed to enable EAN-13")
        save_step_screenshot(self.d0, "step02_enable_ean13", SCRIPT_IMG_DIR)

        print("[Step 3] Enable Composite options")
        self._set_composite_options(True)
        save_step_screenshot(self.d0, "step03_enable_composite", SCRIPT_IMG_DIR)

        print("[Step 4] Timeout 300: measure scan delay")
        self._set_search_timeout(300)
        delay_300 = self._measure_scan_delay("timeout300")

        print("[Step 5] Timeout 10: measure scan delay")
        self._set_search_timeout(10)
        delay_10 = self._measure_scan_delay("timeout10")

        print("[Step 6] Composite disabled, timeout 300: measure scan delay")
        self._set_composite_options(False)
        self._set_search_timeout(300)
        delay_disabled = self._measure_scan_delay("disabled")

        failures = []
        if delay_300 - delay_10 < _MIN_DELAY_DIFF_SECONDS:
            failures.append(f"timeout 300 delay {delay_300:.3f}s is not longer than timeout 10 delay {delay_10:.3f}s")
        if delay_300 - delay_disabled < _MIN_DELAY_DIFF_SECONDS:
            failures.append(f"timeout 300 delay {delay_300:.3f}s is not longer than composite-disabled delay {delay_disabled:.3f}s")
        self.assertFalse(failures, f"Composite search timeout behavior mismatch: {failures}")


if __name__ == "__main__":
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(Test_CompositeSearchTimeout_Composite)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)
