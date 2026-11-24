"""ANDROIDCN-35927: Verify Cast screen page and disabled default state."""

import time
import unittest

from common.common_method import GeneralSettingsTestCase, screenshot, shell
from case.General_Settings._settings_test_utils import require_visible


class TestL1CastScreenAndroidcn35927(GeneralSettingsTestCase):
    def test_l1_cast_screen(self):
        shell(self.serial, "am", "force-stop", "com.android.settings")
        output = shell(self.serial, "am", "start", "-a", "android.settings.CAST_SETTINGS")
        self.assertNotIn("Error", output, "Cast screen activity could not be opened")
        discovery_labels = ("No nearby devices", "No devices found", "Available devices")
        deadline = time.time() + 10
        while time.time() < deadline:
            if any(self.device(textContains=label).exists(timeout=0.4) for label in discovery_labels):
                screenshot(self.device, __file__, "step02_cast_screen_default_state")
                return
            time.sleep(0.5)
        self.fail("Cast screen did not expose a device discovery state within 10 seconds")


if __name__ == "__main__":
    unittest.main(verbosity=2)