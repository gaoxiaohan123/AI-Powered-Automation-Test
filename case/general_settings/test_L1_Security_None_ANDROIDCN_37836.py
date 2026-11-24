"""ANDROIDCN-37836: Verify the Screen lock page supports None for an unsecured SKU."""

import unittest

from common.common_method import GeneralSettingsTestCase, open_settings_action, screenshot
from case.General_Settings._settings_test_utils import click_visible, require_visible


class TestL1SecurityNoneAndroidcn37836(GeneralSettingsTestCase):
    def test_l1_security_none(self):
        open_settings_action(self, self.device, "android.settings.SECURITY_SETTINGS")
        click_visible(self, self.device, ("Screen lock", "屏幕锁定"), "Screen lock entry")
        require_visible(self, self.device, ("None", "无"), "None screen lock option")
        screenshot(self.device, __file__, "step01_screen_lock_options")

        current = self.device(text="Swipe")
        if not current.exists(timeout=0.5):
            current = self.device(text="滑动")
        if not current.exists(timeout=0.5):
            self.skipTest("Current screen lock is credential-protected; automation cannot safely clear it")

        try:
            click_visible(self, self.device, ("None", "无"), "None screen lock option")
            self.device.press("power")
            self.device.press("power")
            self.assertFalse(self.device(textContains="Swipe up").exists(timeout=1), "Lock screen remained after selecting None")
            screenshot(self.device, __file__, "step04_unlocked_without_lock_screen")
        finally:
            open_settings_action(self, self.device, "android.settings.SECURITY_SETTINGS")
            click_visible(self, self.device, ("Screen lock", "屏幕锁定"), "Screen lock entry")
            click_visible(self, self.device, ("Swipe", "滑动"), "Swipe screen lock option")


if __name__ == "__main__":
    unittest.main(verbosity=2)
