# -*- coding:utf-8 -*-
"""Test Case: ANDROIDCN-37823 - Verify accepted Minimum/Maximum length values for MSI."""

import os
import sys
import time
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from common.adb_common import (
    save_step_screenshot,
    dcs_test_cleanup_devices,
    dcs_test_press_home,
    dcs_test_wait_device_online,
    dcs_test_wake_and_unlock,
)
from common.common_method import (
    dcs_test_connect_u2,
    dcs_test_goto_data_processing_settings,
    dcs_test_goto_symbology_setting,
    dcs_test_set_option_checked,
)

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.realpath(__file__))))
SCRIPT_BASENAME = os.path.splitext(os.path.basename(__file__))[0]
SCRIPT_IMG_DIR = os.path.join(PROJECT_ROOT, "img", SCRIPT_BASENAME)
os.makedirs(SCRIPT_IMG_DIR, exist_ok=True)

_SCANNING_LABELS = ["Scanning"]
_INTERNAL_SCANNER_LABELS = ["Internal Scanner", "Internal scanner"]
_DEFAULT_PROFILE_LABELS = ["Default profile", "Default Profile"]
_DATA_PROCESSING_LABELS = ["Data Processing Settings", "Data Processing"]
_SYMBOLOGY_LABELS = ["Symbology Settings", "Symbology"]
_MSI_LABELS = ["MSI"]
_EDIT_RESOURCE_ID = "android:id/edit"
_OK_RESOURCE_ID = "android:id/button1"
_CANCEL_RESOURCE_ID = "android:id/button2"


def _load_device_serial():
    serial = (os.environ.get("AUTONEXUS_DEV0_SN") or "").strip()
    if not serial:
        raise RuntimeError("AUTONEXUS_DEV0_SN must be provided by the web task")
    return serial


DEV0_SERIAL = _load_device_serial()


class Test_MinimumMaximumLength_MSI(unittest.TestCase):
    @classmethod
    def _ensure_device_session(cls):
        if hasattr(cls, "d0"):
            return
        if not dcs_test_wait_device_online(DEV0_SERIAL, 25):
            raise RuntimeError("Configured MSI scanner device is offline")
        cls.d0 = dcs_test_connect_u2(DEV0_SERIAL)

    @classmethod
    def setUpClass(cls):
        print("\n" + "=" * 70)
        print("ANDROIDCN-37823: Verify accepted Minimum/Maximum length values for MSI")
        print("=" * 70)
        cls._ensure_device_session()

    def setUp(self):
        self.__class__._ensure_device_session()
        dcs_test_wake_and_unlock(DEV0_SERIAL, self.d0)
        dcs_test_press_home(DEV0_SERIAL)

    def tearDown(self):
        if self.d0(resourceId=_CANCEL_RESOURCE_ID).exists:
            self.d0(resourceId=_CANCEL_RESOURCE_ID).click()
        dcs_test_cleanup_devices(DEV0_SERIAL, DEV0_SERIAL)
        dcs_test_press_home(DEV0_SERIAL)

    def _goto_msi_setting(self):
        dcs_test_goto_symbology_setting(
            DEV0_SERIAL, self.d0, _SCANNING_LABELS, _INTERNAL_SCANNER_LABELS,
            _DEFAULT_PROFILE_LABELS, _SYMBOLOGY_LABELS, _MSI_LABELS,
        )

    def _open_length_dialog(self, setting_name):
        self._goto_msi_setting()
        self.assertTrue(self.d0(text=setting_name).exists, f"Cannot find {setting_name}")
        self.d0(text=setting_name).click()
        time.sleep(1)
        self.assertTrue(self.d0(resourceId=_EDIT_RESOURCE_ID).exists, f"{setting_name} dialog did not open")

    def _read_length_value(self, setting_name):
        self._open_length_dialog(setting_name)
        value = self.d0(resourceId=_EDIT_RESOURCE_ID).get_text()
        self.d0(resourceId=_CANCEL_RESOURCE_ID).click()
        return value

    def _assert_value_rejected(self, setting_name, candidate_value, step_name):
        original_value = self._read_length_value(setting_name)
        self._open_length_dialog(setting_name)
        self.d0(resourceId=_EDIT_RESOURCE_ID).set_text(candidate_value)
        self.d0(resourceId=_OK_RESOURCE_ID).click()
        if self.d0(resourceId=_EDIT_RESOURCE_ID).exists:
            current_input = self.d0(resourceId=_EDIT_RESOURCE_ID).get_text()
            print(f"  {setting_name}: original='{original_value}', candidate='{candidate_value}', input='{current_input}'")
            save_step_screenshot(self.d0, step_name, SCRIPT_IMG_DIR)
            self.d0(resourceId=_CANCEL_RESOURCE_ID).click()
            return
        current_value = self._read_length_value(setting_name)
        print(f"  {setting_name}: original='{original_value}', candidate='{candidate_value}', current='{current_value}'")
        save_step_screenshot(self.d0, step_name, SCRIPT_IMG_DIR)
        self.assertEqual(current_value, original_value, f"{setting_name} accepted invalid value '{candidate_value}'")

    def _assert_non_numeric_rejected(self):
        original_value = self._read_length_value("Minimum length")
        self._open_length_dialog("Minimum length")
        edit = self.d0(resourceId=_EDIT_RESOURCE_ID)
        edit.set_text("")
        self.d0.shell("input text abc")
        current_input = edit.get_text()
        print(f"  Minimum length non-numeric input: actual='{current_input}'")
        save_step_screenshot(self.d0, "step02_non_numeric_input", SCRIPT_IMG_DIR)
        self.assertNotEqual(current_input, "abc", "Minimum length accepted non-numeric input")
        self.d0(resourceId=_CANCEL_RESOURCE_ID).click()
        self.assertEqual(self._read_length_value("Minimum length"), original_value, "Non-numeric input changed Minimum length")

    def test_minimum_maximum_length_msi(self):
        """Test steps:
        1. Enable Wedge in Data Processing Settings.
        2. Verify invalid text cannot be entered into Minimum length.
        3. Verify Minimum length cannot exceed Maximum length.
        4. Verify Maximum length cannot be less than Minimum length or exceed its accepted maximum.
        """
        print("\n[Step 1] Open Data Processing Settings and enable Wedge")
        dcs_test_goto_data_processing_settings(
            DEV0_SERIAL, self.d0, _SCANNING_LABELS, _INTERNAL_SCANNER_LABELS,
            _DEFAULT_PROFILE_LABELS, _DATA_PROCESSING_LABELS,
        )
        self.assertTrue(dcs_test_set_option_checked(self.d0, "Wedge", True), "Failed to enable Wedge")

        print("[Step 2] Verify invalid text cannot be entered into Minimum length")
        self._assert_non_numeric_rejected()

        print("[Step 3] Verify Minimum length cannot exceed Maximum length")
        maximum_value = int(self._read_length_value("Maximum length"))
        self._assert_value_rejected("Minimum length", str(maximum_value + 1), "step03_minimum_above_maximum")

        print("[Step 4] Verify Maximum length cannot be less than Minimum length")
        minimum_value = int(self._read_length_value("Minimum length"))
        self._assert_value_rejected("Maximum length", str(minimum_value - 1), "step04_maximum_below_minimum")

        print("[Step 5] Verify Maximum length cannot exceed its accepted maximum")
        self._assert_value_rejected("Maximum length", str(maximum_value + 1), "step05_maximum_above_accepted_limit")


if __name__ == "__main__":
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(Test_MinimumMaximumLength_MSI)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)