"""ANDROIDCN-36061: Verify launcher supports long-press widget management."""

import unittest

from common.common_method import GeneralSettingsTestCase, screenshot


class TestL1RemoveWidgetFromHomeScreenAndroidcn36061(GeneralSettingsTestCase):
    def test_l1_remove_widget_from_home_screen(self):
        self.device.press("home")
        self.device.long_click(0.5, 0.5, duration=1.0)
        self.assertTrue(self.device(textContains="Widgets").exists(timeout=5), "Launcher widget management was not available")
        screenshot(self.device, __file__, "widget_management")


if __name__ == "__main__":
    unittest.main(verbosity=2)
