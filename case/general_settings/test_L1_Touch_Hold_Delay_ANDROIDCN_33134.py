"""ANDROIDCN-33134: Verify Touch and hold delay values are selectable."""

import unittest

from common.common_method import GeneralSettingsTestCase, open_settings_action, screenshot
from common.adb_common import setting_value
from case.General_Settings._settings_test_utils import click_visible


class TestL1TouchHoldDelayAndroidcn33134(GeneralSettingsTestCase):
    OPTIONS = (
        (("Short", "短"), "400"),
        (("Medium", "中"), "1000"),
        (("Long", "长"), "1500"),
    )

    def _open_delay_dialog(self):
        click_visible(
            self,
            self.device,
            ("Touch & hold delay", "Touch and hold delay", "触摸并按住延迟"),
            "Touch and hold delay",
        )

    def test_l1_touch_hold_delay(self):
        open_settings_action(self, self.device, "android.settings.ACCESSIBILITY_SETTINGS")
        click_visible(self, self.device, ("Timing controls", "时间控制"), "Timing controls")
        for option, expected_timeout in self.OPTIONS:
            self._open_delay_dialog()
            click_visible(self, self.device, option, "Touch and hold delay option")
            self.assertEqual(
                setting_value(self.serial, "secure", "long_press_timeout"),
                expected_timeout,
                "Touch and hold delay did not change to {}".format(option[0]),
            )
        screenshot(self.device, __file__, "step02_touch_hold_delay_options")


if __name__ == "__main__":
    unittest.main(verbosity=2)
