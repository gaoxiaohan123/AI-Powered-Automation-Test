"""ANDROIDCN-34653: Verify the hardware screenshot shortcut creates a screenshot."""

import time
import unittest

from common.common_method import GeneralSettingsTestCase, screenshot, shell


class TestL1NewScreenshotShortcutAndroidcn34653(GeneralSettingsTestCase):
    def test_l1_new_screenshot_shortcut(self):
        shell(self.serial, "mkdir", "-p", "/sdcard/Pictures/Screenshots")
        before = shell(self.serial, "find", "/sdcard/Pictures/Screenshots", "-type", "f")
        shell(self.serial, "input", "keyevent", "KEYCODE_SYSRQ")
        time.sleep(2)
        after = shell(self.serial, "find", "/sdcard/Pictures/Screenshots", "-type", "f")
        self.assertNotEqual(after, before, "Screenshot shortcut did not create a screenshot file")
        screenshot(self.device, __file__, "step01_screenshot_created")


if __name__ == "__main__":
    unittest.main(verbosity=2)
