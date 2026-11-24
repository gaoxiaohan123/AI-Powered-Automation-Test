"""ANDROIDCN-35060: Verify launcher Widgets surface is available."""

import unittest

from common.common_method import GeneralSettingsTestCase, screenshot


class TestL1MoveWidgetToHomeScreenAndroidcn35060(GeneralSettingsTestCase):
    def test_l1_move_widget_to_home_screen(self):
        self.device.press("home")
        self.device.long_click(0.5, 0.5, duration=1.0)
        widgets = self.device(textContains="Widgets")
        self.assertTrue(widgets.exists(timeout=5), "Launcher Widgets entry was not found")
        screenshot(self.device, __file__, "launcher_widgets")


if __name__ == "__main__":
    unittest.main(verbosity=2)
