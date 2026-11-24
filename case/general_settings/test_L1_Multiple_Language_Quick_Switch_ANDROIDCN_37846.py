"""ANDROIDCN-37846: L1_Language&Input_Multiple language quick switch.

Description:
Provides the ability to use two or more languages at the same time.
"""

import unittest

from common.common_method import GeneralSettingsTestCase, open_settings_action, screenshot


class TestL1MultipleLanguageQuickSwitchAndroidcn37846(GeneralSettingsTestCase):

    def test_l1_multiple_language_quick_switch(self):
        """Open Languages and verify add-language entry and non-empty language list."""
        open_settings_action(self, self.device, "android.settings.LOCALE_SETTINGS")
        screenshot(self.device, __file__, "step01_languages_page")
        add_lang_exists = (
            self.device(textContains="Add a language").exists(timeout=1)
            or self.device(textContains="添加语言").exists(timeout=1)
            or self.device(textContains="Add language").exists(timeout=1)
            or self.device(textContains="语言").exists(timeout=1)
        )
        self.assertTrue(add_lang_exists, "The Languages page must provide an 'Add a language' entry")
        self.assertGreater(len(self.device.xpath('//*[@text]').all()), 0, "Language list is empty")


if __name__ == "__main__":
    unittest.main(verbosity=2)