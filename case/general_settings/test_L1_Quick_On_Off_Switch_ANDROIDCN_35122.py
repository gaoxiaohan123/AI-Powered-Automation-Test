"""ANDROIDCN-35122: Verify Quick Settings controls are available."""

import unittest

from common.common_method import GeneralSettingsTestCase, screenshot


class TestL1QuickOnOffSwitchAndroidcn35122(GeneralSettingsTestCase):
    def test_l1_quick_on_off_switch(self):
        self.device.open_quick_settings()
        self.assertTrue(self.device(descriptionContains="Settings").exists(timeout=3) or self.device(textContains="Internet").exists(timeout=3), "Quick Settings did not open")
        screenshot(self.device, __file__, "quick_settings_controls")


if __name__ == "__main__":
    unittest.main(verbosity=2)
