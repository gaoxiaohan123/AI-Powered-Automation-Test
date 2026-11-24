"""ANDROIDCN-37865: L1_Swip up on Home button.

Description:
Select and set Gesture navigation to enable, then check function.
"""

import unittest

from common.common_method import GeneralSettingsTestCase, open_settings_action, screenshot, tap_path


class TestL1SwipeUpOnHomeButtonAndroidcn37865(GeneralSettingsTestCase):

    def test_l1_gesture_navigation(self):
        """Open Settings -> System -> Gestures -> System navigation and verify gesture entry."""
        open_settings_action(self, self.device, "android.settings.SETTINGS")
        tap_path(
            self,
            self.device,
            ("System", "系统"),
            ("Gestures", "手势"),
            ("System navigation", "系统导航"),
        )
        screenshot(self.device, __file__, "step01_system_navigation")
        gesture = self.device(textContains="Gesture navigation")
        if not gesture.exists(timeout=1):
            gesture = self.device(textContains="手势导航")
        self.assertTrue(gesture.exists(timeout=2), "Gesture navigation selection did not remain available")


if __name__ == "__main__":
    unittest.main(verbosity=2)