"""ANDROIDCN-35443: Verify Clock app storage controls and reset behavior."""

import time
import unittest

from common.common_method import GeneralSettingsTestCase, screenshot, shell
from case.General_Settings._settings_test_utils import (
    click_visible,
    package_installed,
    prepare_settings_entry,
    require_visible,
)


class TestL1AppInfoStorageAndroidcn35443(GeneralSettingsTestCase):
    CLOCK_PACKAGES = ("com.google.android.deskclock", "com.android.deskclock")

    def _open_clock_storage_page(self, package_name):
        for _ in range(2):
            prepare_settings_entry(self.serial)
            shell(self.serial, "am", "force-stop", "com.android.settings")
            shell(
                self.serial,
                "am",
                "start",
                "-a",
                "android.settings.APPLICATION_DETAILS_SETTINGS",
                "-d",
                "package:" + package_name,
            )
            deadline = time.time() + 10
            while time.time() < deadline:
                current = self.device.app_current()
                storage_entry = self.device(text="Storage & cache")
                if current.get("activity", "").endswith("InstalledAppDetails") and storage_entry.exists(timeout=0.3):
                    storage_entry.click()
                    return
                time.sleep(0.5)
        self.fail("Clock App info Storage page did not become ready within two launch attempts")

    def _create_alarm_data(self, package_name):
        shell(self.serial, "monkey", "-p", package_name, "-c", "android.intent.category.LAUNCHER", "1")
        alarm_tab = self.device(description="Alarm")
        self.assertTrue(alarm_tab.exists(timeout=5), "Clock Alarm tab was not found")
        alarm_tab.click()
        add_alarm = self.device(description="Add alarm")
        self.assertTrue(add_alarm.exists(timeout=5), "Clock Add alarm button was not found")
        add_alarm.click()
        confirm_alarm = self.device(resourceId="com.google.android.deskclock:id/material_timepicker_ok_button")
        self.assertTrue(confirm_alarm.exists(timeout=5), "Clock alarm confirmation button was not found")
        confirm_alarm.click()
        time.sleep(1)
        self._open_clock_storage_page(package_name)

    def test_l1_app_info_storage(self):
        package_name = next((name for name in self.CLOCK_PACKAGES if package_installed(self.serial, name)), None)
        if not package_name:
            self.skipTest("Clock application is not installed")

        self._open_clock_storage_page(package_name)

        clear_storage = self.device(resourceId="com.android.settings:id/button1")
        if clear_storage.exists(timeout=2) and not clear_storage.info.get("enabled", False):
            self._create_alarm_data(package_name)
            clear_storage = self.device(resourceId="com.android.settings:id/button1")
        self.assertTrue(clear_storage.exists(timeout=2), "Clear storage button was not found")
        self.assertTrue(clear_storage.info.get("enabled", False), "Clear storage button remained disabled after creating an alarm")
        clear_storage.click()
        confirmation_title = self.device(resourceId="com.android.settings:id/alertTitle")
        self.assertTrue(confirmation_title.exists(timeout=2), "Clear storage confirmation was not shown")
        confirm_clear_storage = self.device(resourceId="android:id/button1")
        self.assertTrue(confirm_clear_storage.exists(timeout=2), "Clear storage confirmation button was not found")
        confirm_clear_storage.click()

        clear_cache = self.device(resourceId="com.android.settings:id/button2")
        if not clear_cache.exists(timeout=2):
            self._open_clock_storage_page(package_name)
            clear_cache = self.device(resourceId="com.android.settings:id/button2")
        self.assertTrue(clear_cache.exists(timeout=5), "Clear cache button was not found")
        clear_cache.click()
        screenshot(self.device, __file__, "step05_clock_cache_cleared")

        self.device.press("back")
        click_visible(self, self.device, ("Open by default", "默认打开"), "Open by default entry")
        require_visible(self, self.device, ("0 verified links", "0 个已验证链接", "No defaults", "无默认设置"), "Clock default links state")


if __name__ == "__main__":
    unittest.main(verbosity=2)