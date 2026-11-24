"""ANDROIDCN-33599: Verify Internet/Wi-Fi settings page is available for DHCPv6/IPv6 checks."""

import unittest

from common.common_method import GeneralSettingsTestCase, screenshot
from case.General_Settings._settings_case_utils import open_action


class TestL2Dhcpv6Ipv6SlaacAndroidcn33599(GeneralSettingsTestCase):
    def test_l2_dhcpv6_ipv6_slaac(self):
        open_action(self, "android.settings.WIFI_SETTINGS", ("Internet", "Wi-Fi", "网络和互联网", "无线网络"))
        screenshot(self.device, __file__, "internet_wifi_settings")


if __name__ == "__main__":
    unittest.main(verbosity=2)
