"""ANDROIDCN-33426: Verify Display Screen timeout values and power-off behavior."""

import time
import unittest

from common.adb_common import set_setting, setting_value
from common.common_method import GeneralSettingsTestCase, open_settings_action, screenshot, shell
from case.General_Settings._settings_test_utils import prepare_settings_entry, require_visible, screen_is_on


class TestL1ScreenTimeoutAndroidcn33426(GeneralSettingsTestCase):
    def test_l1_screen_timeout(self):
        original = setting_value(self.serial, "system", "screen_off_timeout")
        original_lock_delay = setting_value(self.serial, "secure", "lock_screen_lock_after_timeout")
        try:
            set_setting(self.serial, "secure", "lock_screen_lock_after_timeout", 86400000)
            open_settings_action(self, self.device, "android.settings.DISPLAY_SETTINGS")
            require_visible(self, self.device, ("Screen timeout", "屏幕超时"), "Screen timeout entry")
            screenshot(self.device, __file__, "step02_screen_timeout_options")

            for timeout_ms, wait_seconds in ((15000, 17), (30000, 32)):
                set_setting(self.serial, "system", "screen_off_timeout", timeout_ms)
                self.assertEqual(setting_value(self.serial, "system", "screen_off_timeout"), str(timeout_ms))
                if not screen_is_on(self.serial):
                    shell(self.serial, "input", "keyevent", "224")
                time.sleep(wait_seconds)
                self.assertFalse(screen_is_on(self.serial), "Screen stayed on after {} seconds".format(timeout_ms // 1000))
                shell(self.serial, "input", "keyevent", "224")
        finally:
            if original and original != "null":
                set_setting(self.serial, "system", "screen_off_timeout", original)
            prepare_settings_entry(self.serial)
            if original_lock_delay and original_lock_delay != "null":
                set_setting(self.serial, "secure", "lock_screen_lock_after_timeout", original_lock_delay)
            else:
                shell(self.serial, "settings", "delete", "secure", "lock_screen_lock_after_timeout")


if __name__ == "__main__":
    unittest.main(verbosity=2)
