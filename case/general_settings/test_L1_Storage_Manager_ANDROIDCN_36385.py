"""ANDROIDCN-36385: Verify Storage manager and photo/video retention choices."""

import time
import unittest

from common.common_method import GeneralSettingsTestCase, open_settings_action, screenshot, shell
from case.General_Settings._settings_test_utils import click_visible, require_visible


class TestL1StorageManagerAndroidcn36385(GeneralSettingsTestCase):
    ENTRY_LABELS = ("Storage manager", "存储管理器")
    SWITCH_LABELS = ("Use Storage manager", "使用存储管理器")
    RETENTION_LABELS = ("Over 30 days old", "Over 60 days old", "Over 90 days old")

    def _prepare_settings_entry(self):
        if "mWakefulness=Awake" not in shell(self.serial, "dumpsys", "power"):
            shell(self.serial, "input", "keyevent", "224")
            time.sleep(0.8)
        shell(self.serial, "input", "swipe", "540", "1700", "540", "500", "300")
        shell(self.serial, "cmd", "statusbar", "collapse")
        time.sleep(0.5)

    def _open_storage_manager_page(self):
        for _ in range(2):
            self._prepare_settings_entry()
            shell(self.serial, "am", "force-stop", "com.android.settings")
            open_settings_action(self, self.device, "android.settings.INTERNAL_STORAGE_SETTINGS", wait_seconds=1)
            deadline = time.time() + 10
            while time.time() < deadline:
                current = self.device.app_current()
                overview = self.device(textContains="THIS DEVICE")
                if (
                    current.get("activity", "").endswith("StorageDashboardActivity")
                    and (overview.exists(timeout=0.3) or self.device(textContains="This device").exists(timeout=0.3))
                ):
                    click_visible(self, self.device, self.ENTRY_LABELS, "Storage manager")
                    require_visible(self, self.device, self.SWITCH_LABELS, "Storage manager page")
                    return
                time.sleep(0.5)
        self.fail("Storage Settings page did not become ready within two launch attempts")

    def _storage_manager_switch(self):
        switch = self.device(resourceId="android:id/switch_widget")
        if not switch.exists(timeout=2):
            self._open_storage_manager_page()
            switch = self.device(resourceId="android:id/switch_widget")
        self.assertTrue(switch.exists(timeout=5), "Storage manager switch was not found")
        return switch

    def _set_storage_manager(self, enabled):
        switch = self._storage_manager_switch()
        if bool(switch.info.get("checked", False)) != enabled:
            switch.click()
        deadline = time.time() + 10
        while time.time() < deadline:
            switch = self.device(resourceId="android:id/switch_widget")
            if switch.exists(timeout=0.5) and bool(switch.info.get("checked", False)) == enabled:
                return
            time.sleep(0.5)
        self.assertEqual(
            bool(self._storage_manager_switch().info.get("checked", False)),
            enabled,
            "Failed to set Use Storage manager to {}".format(enabled),
        )

    def _select_retention_period(self, option_label):
        for _ in range(2):
            self._storage_manager_switch()
            click_visible(self, self.device, ("Remove photos & videos", "移除照片和视频"), "Remove photos & videos")
            option = self.device(text=option_label)
            if option.exists(timeout=2):
                option.click()
                time.sleep(0.8)
                return
            self._open_storage_manager_page()
        self.fail("Photo and video retention period was not found: {}".format(option_label))

    def test_l1_storage_manager(self):
        self._open_storage_manager_page()
        original_state = bool(self._storage_manager_switch().info.get("checked", False))
        try:
            self._set_storage_manager(True)
            screenshot(self.device, __file__, "step02_storage_manager_enabled")

            for option_label in self.RETENTION_LABELS:
                self._select_retention_period(option_label)
            screenshot(self.device, __file__, "step03_photo_video_retention_selected")
        finally:
            self._set_storage_manager(original_state)
            screenshot(self.device, __file__, "step04_storage_manager_restored")


if __name__ == "__main__":
    unittest.main(verbosity=2)
