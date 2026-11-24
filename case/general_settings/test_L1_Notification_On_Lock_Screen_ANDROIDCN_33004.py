"""ANDROIDCN-33004: Verify lock-screen notification settings page is available."""

import unittest

from common.common_method import GeneralSettingsTestCase, screenshot
from case.General_Settings._settings_case_utils import find_text, open_action


class TestL1NotificationOnLockScreenAndroidcn33004(GeneralSettingsTestCase):
    def test_l1_notification_on_lock_screen(self):
        open_action(self, "android.settings.NOTIFICATION_SETTINGS", ("Notifications", "通知"))
        find_text(self, ("Notifications on lock screen", "Lock screen", "锁定屏幕", "锁屏通知"))
        screenshot(self.device, __file__, "notification_on_lock_screen")


if __name__ == "__main__":
    unittest.main(verbosity=2)
