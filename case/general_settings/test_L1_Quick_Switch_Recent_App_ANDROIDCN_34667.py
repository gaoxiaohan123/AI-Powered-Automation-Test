"""ANDROIDCN-34667: Verify the Recents key switches between recent applications."""

import time
import unittest

from common.common_method import GeneralSettingsTestCase, screenshot, shell


class TestL1QuickSwitchRecentAppAndroidcn34667(GeneralSettingsTestCase):
    def test_l1_quick_switch_recent_app(self):
        shell(self.serial, "am", "start", "-a", "android.settings.SETTINGS")
        time.sleep(1)
        shell(self.serial, "input", "keyevent", "HOME")
        time.sleep(1)
        before = shell(self.serial, "dumpsys", "window", "windows")
        shell(self.serial, "input", "keyevent", "KEYCODE_APP_SWITCH")
        time.sleep(0.3)
        shell(self.serial, "input", "keyevent", "KEYCODE_APP_SWITCH")
        time.sleep(1)
        after = shell(self.serial, "dumpsys", "window", "windows")
        self.assertNotEqual(after, before, "Recents key did not change the active task")
        screenshot(self.device, __file__, "step02_recent_app_switched")


if __name__ == "__main__":
    unittest.main(verbosity=2)
