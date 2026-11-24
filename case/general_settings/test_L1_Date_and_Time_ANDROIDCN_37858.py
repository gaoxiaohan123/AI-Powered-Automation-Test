"""ANDROIDCN-37858: L1_Date and Time.

Description:
Verify Date&time and time zone can be set and displayed successfully.
"""

import unittest

from common.adb_common import set_setting, setting_value
from common.common_method import GeneralSettingsTestCase, open_settings_action, screenshot, shell


class TestL1DateAndTimeAndroidcn37858(GeneralSettingsTestCase):

    def test_l1_date_and_time(self):
        """Validate timezone switching and 12/24-hour format writes in Settings."""
        open_settings_action(self, self.device, "android.settings.DATE_SETTINGS")
        screenshot(self.device, __file__, "step01_date_time_page")

        for timezone in ("Asia/Tokyo", "Asia/Bangkok", "Pacific/Pago_Pago"):
            shell(self.serial, "cmd", "alarm", "set-timezone", timezone)
            self.assertEqual(shell(self.serial, "getprop", "persist.sys.timezone"), timezone)

        for format_value in ("24", "12"):
            set_setting(self.serial, "system", "time_12_24", format_value)
            self.assertEqual(setting_value(self.serial, "system", "time_12_24"), format_value)
        screenshot(self.device, __file__, "step08_time_formats_verified")


if __name__ == "__main__":
    unittest.main(verbosity=2)