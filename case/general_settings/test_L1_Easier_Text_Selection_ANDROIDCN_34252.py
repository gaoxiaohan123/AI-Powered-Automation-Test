"""ANDROIDCN-34252: Verify text selection controls in Messaging."""

import time
import unittest

from common.common_method import GeneralSettingsTestCase, screenshot, shell
from case.General_Settings._settings_test_utils import package_installed


class TestL1EasierTextSelectionAndroidcn34252(GeneralSettingsTestCase):
    PACKAGES = ("com.google.android.apps.messaging", "com.android.messaging")

    def test_l1_easier_text_selection(self):
        package_name = next((name for name in self.PACKAGES if package_installed(self.serial, name)), None)
        if not package_name:
            self.skipTest("Messaging app is not installed")
        shell(self.serial, "monkey", "-p", package_name, "-c", "android.intent.category.LAUNCHER", "1")
        time.sleep(2)
        editors = self.device(className="android.widget.EditText")
        if not editors.exists(timeout=2):
            self.skipTest("Messaging has no compose editor without creating a recipient")
        editors.click()
        editors.clear_text()
        shell(self.serial, "input", "text", "qwerty")
        bounds = editors.info["bounds"]
        text_x = bounds["left"] + min(106, (bounds["right"] - bounds["left"]) // 2)
        text_y = (bounds["top"] + bounds["bottom"]) // 2
        self.device.click(bounds["right"] - 288, text_y)
        shell(
            self.serial,
            "input",
            "swipe",
            str(text_x),
            str(text_y),
            str(text_x),
            str(text_y),
            "1200",
        )
        self.assertTrue(
            self.device(textContains="Copy").exists(timeout=2) or self.device(descriptionContains="Copy").exists(timeout=2),
            "Text selection controls were not displayed",
        )
        screenshot(self.device, __file__, "step02_text_selection")


if __name__ == "__main__":
    unittest.main(verbosity=2)
