"""ANDROIDCN-37847: Verify Google Drive backup can be enabled and disabled."""

import time
import unittest

from common.common_method import GeneralSettingsTestCase, screenshot, shell, tap_path
from case.General_Settings._settings_test_utils import require_visible


class TestL1BackupDisplayAndroidcn37847(GeneralSettingsTestCase):
    def _open_backup_page(self):
        shell(self.serial, "am", "force-stop", "com.android.settings")
        shell(self.serial, "am", "start", "-a", "android.settings.SETTINGS")
        if not tap_path(self, self.device, ("System", "系统"), ("Backup", "备份"), strict=False):
            self.skipTest("Backup Settings page is not exposed by this CT47 build")
        require_visible(
            self,
            self.device,
            ("Back up to Google Drive", "备份到 Google 云端硬盘"),
            "Google Drive backup option",
        )

    def _backup_switch(self):
        switch = self.device(resourceId="android:id/switch_widget")
        self.assertTrue(switch.exists(timeout=5), "Google Drive backup switch was not found")
        return switch

    def _set_backup_enabled(self, enabled):
        switch = self._backup_switch()
        if bool(switch.info.get("checked", False)) != enabled:
            switch.click()
            if not enabled:
                confirm_turn_off = self.device(text="TURN OFF & DELETE")
                if not confirm_turn_off.exists(timeout=3):
                    confirm_turn_off = self.device(resourceId="android:id/button1")
                self.assertTrue(
                    confirm_turn_off.exists(timeout=3),
                    "Turn off and delete backup confirmation was not shown",
                )
                confirm_turn_off.click()
        deadline = time.time() + 10
        while time.time() < deadline:
            switch = self.device(resourceId="android:id/switch_widget")
            try:
                if switch.exists(timeout=0.5) and bool(switch.info.get("checked", False)) == enabled:
                    return
            except Exception:
                self._open_backup_page()
            time.sleep(0.5)
        self.fail("Failed to set Back up to Google Drive to {}".format(enabled))

    def test_l1_backup_display(self):
        """Verify the Google Drive backup setting can be enabled, disabled, and exited."""
        self._open_backup_page()
        self.assertFalse(self._backup_switch().info.get("checked", False), "Back up to Google Drive is enabled by default")
        screenshot(self.device, __file__, "step01_google_drive_backup_disabled")
        try:
            self._set_backup_enabled(True)
            screenshot(self.device, __file__, "step02_google_drive_backup_enabled")
        finally:
            self._set_backup_enabled(False)
            screenshot(self.device, __file__, "step03_google_drive_backup_disabled")

        self.device.press("back")
        self.assertTrue(
            self.device(text="Languages\u00a0& input").exists(timeout=3)
                or self.device(textContains="Languages").exists(timeout=3)
            or self.device(text="Backup").exists(timeout=1),
            "Back navigation did not return to the System page",
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
