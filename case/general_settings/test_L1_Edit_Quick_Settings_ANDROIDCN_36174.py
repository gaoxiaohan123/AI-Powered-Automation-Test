"""ANDROIDCN-36174: Verify Quick Settings edit control is available."""

import unittest

from common.common_method import GeneralSettingsTestCase, screenshot


class TestL1EditQuickSettingsAndroidcn36174(GeneralSettingsTestCase):
    def test_l1_edit_quick_settings(self):
        self.device.open_quick_settings()
        edit = self.device(descriptionContains="Edit")
        self.assertTrue(edit.exists(timeout=5), "Quick Settings Edit control was not found")
        edit.click()
        self.assertTrue(
            self.device(textContains="Hold and drag").exists(timeout=5)
            or self.device(textContains="Drag").exists(timeout=5),
            "Quick Settings edit surface did not open",
        )
        screenshot(self.device, __file__, "quick_settings_edit")


if __name__ == "__main__":
    unittest.main(verbosity=2)
