# -*- coding:utf-8 -*-
"""Test Case: ANDROIDCN-37593 - Verify accepted Code 128 length values."""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from common.adb_common import dcs_test_cleanup_devices, dcs_test_press_home, dcs_test_wait_device_online, dcs_test_wake_and_unlock, save_step_screenshot
from common.common_method import dcs_test_connect_u2, dcs_test_goto_symbology_setting

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.realpath(__file__))))
SCRIPT_IMG_DIR = os.path.join(PROJECT_ROOT, "img", os.path.splitext(os.path.basename(__file__))[0])
os.makedirs(SCRIPT_IMG_DIR, exist_ok=True)
_SCANNING_LABELS = ["Scanning"]
_INTERNAL_SCANNER_LABELS = ["Internal Scanner", "Internal scanner"]
_DEFAULT_PROFILE_LABELS = ["Default profile", "Default Profile"]
_SYMBOLOGY_LABELS = ["Symbology Settings", "Symbology"]
_CODE128_LABELS = ["Code 128", "Code128", "CODE 128"]
_EDIT_RESOURCE_ID = "android:id/edit"
_OK_RESOURCE_ID = "android:id/button1"
_CANCEL_RESOURCE_ID = "android:id/button2"


def _load_device_serial():
    serial = (os.environ.get("AUTONEXUS_DEV0_SN") or "").strip()
    if not serial:
        raise RuntimeError("AUTONEXUS_DEV0_SN must be provided by the web task")
    return serial


DEV0_SERIAL = _load_device_serial()


class Test_MinimumMaximumLength_Code128(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not dcs_test_wait_device_online(DEV0_SERIAL, 25):
            raise RuntimeError("Configured Code 128 scanner device is offline")
        cls.d0 = dcs_test_connect_u2(DEV0_SERIAL)

    def setUp(self):
        if not hasattr(self.__class__, "d0"):
            self.__class__.setUpClass()
        dcs_test_wake_and_unlock(DEV0_SERIAL, self.d0)
        dcs_test_press_home(DEV0_SERIAL)

    def tearDown(self):
        if self.d0(resourceId=_CANCEL_RESOURCE_ID).exists:
            self.d0(resourceId=_CANCEL_RESOURCE_ID).click()
        dcs_test_cleanup_devices(DEV0_SERIAL, DEV0_SERIAL)
        dcs_test_press_home(DEV0_SERIAL)

    def _goto_code128_setting(self):
        dcs_test_goto_symbology_setting(DEV0_SERIAL, self.d0, _SCANNING_LABELS, _INTERNAL_SCANNER_LABELS, _DEFAULT_PROFILE_LABELS, _SYMBOLOGY_LABELS, _CODE128_LABELS)

    def _read_value(self, setting_name):
        self._goto_code128_setting()
        self.d0(text=setting_name).click()
        value = self.d0(resourceId=_EDIT_RESOURCE_ID).get_text()
        self.d0(resourceId=_CANCEL_RESOURCE_ID).click()
        return value

    def _assert_rejected(self, setting_name, candidate, screenshot_name):
        original = self._read_value(setting_name)
        self._goto_code128_setting()
        self.d0(text=setting_name).click()
        self.d0(resourceId=_EDIT_RESOURCE_ID).set_text(str(candidate))
        self.d0(resourceId=_OK_RESOURCE_ID).click()
        if self.d0(resourceId=_EDIT_RESOURCE_ID).exists:
            save_step_screenshot(self.d0, screenshot_name, SCRIPT_IMG_DIR)
            self.d0(resourceId=_CANCEL_RESOURCE_ID).click()
            return
        self.assertEqual(self._read_value(setting_name), original, f"{setting_name} accepted invalid value '{candidate}'")
        save_step_screenshot(self.d0, screenshot_name, SCRIPT_IMG_DIR)

    def test_minimum_maximum_length_code128(self):
        """Test steps:
        1. Read the current Code 128 Minimum length and Maximum length values.
        2. Enter non-numeric input for Minimum length and verify it is not accepted.
        3. Set Minimum length above Maximum length and verify the invalid value is rejected.
        4. Set Maximum length below Minimum length and verify the invalid value is rejected.
        5. Set Maximum length above the accepted limit and verify the invalid value is rejected.
        """
        maximum = int(self._read_value("Maximum length"))
        minimum = int(self._read_value("Minimum length"))

        self._goto_code128_setting()
        self.d0(text="Minimum length").click()
        edit = self.d0(resourceId=_EDIT_RESOURCE_ID)
        edit.set_text("")
        self.d0.shell("input text abc")
        self.assertNotEqual(edit.get_text(), "abc", "Minimum length accepted non-numeric input")
        save_step_screenshot(self.d0, "step02_non_numeric_input", SCRIPT_IMG_DIR)
        self.d0(resourceId=_CANCEL_RESOURCE_ID).click()

        self._assert_rejected("Minimum length", maximum + 1, "step03_minimum_above_maximum")
        self._assert_rejected("Maximum length", minimum - 1, "step04_maximum_below_minimum")
        self._assert_rejected("Maximum length", maximum + 1, "step05_maximum_above_accepted_limit")


if __name__ == "__main__":
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(Test_MinimumMaximumLength_Code128)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)