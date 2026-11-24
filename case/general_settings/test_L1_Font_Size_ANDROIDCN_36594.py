"""ANDROIDCN-36594: Verify Font size settings are available."""

import unittest

from common.common_method import GeneralSettingsTestCase, screenshot
from case.General_Settings._settings_case_utils import click_text, find_text, open_action


class TestL1FontSizeAndroidcn36594(GeneralSettingsTestCase):
    def test_l1_font_size(self):
        open_action(self, "android.settings.DISPLAY_SETTINGS", ("Display", "显示"))
        click_text(self, ("Display size and text", "Display size", "显示大小和文字", "显示大小"))
        find_text(self, ("Font size", "字体大小"))
        screenshot(self.device, __file__, "font_size_entry")


if __name__ == "__main__":
    unittest.main(verbosity=2)
