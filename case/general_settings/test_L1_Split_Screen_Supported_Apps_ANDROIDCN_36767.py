"""ANDROIDCN-36767: Verify Recents exposes a supported-app split-screen entry."""

import unittest

from common.common_method import GeneralSettingsTestCase, screenshot


class TestL1SplitScreenSupportedAppsAndroidcn36767(GeneralSettingsTestCase):
    def test_l1_split_screen_supported_apps(self):
        self.device.app_start("com.google.android.deskclock", stop=True)
        self.device.press("recent")
        self.assertTrue(self.device.app_current().get("package"), "Recents did not open")
        screenshot(self.device, __file__, "recents_split_screen_supported")


if __name__ == "__main__":
    unittest.main(verbosity=2)
