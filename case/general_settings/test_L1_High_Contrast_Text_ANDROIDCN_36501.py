"""ANDROIDCN-36501: Verify High contrast text can be enabled and disabled."""

import unittest

from common.common_method import GeneralSettingsTestCase, screenshot, shell, tap_path
from case.General_Settings._settings_test_utils import set_switch, switch_state


class TestL1HighContrastTextAndroidcn36501(GeneralSettingsTestCase):
    OPTION_LABELS = ("High contrast text", "高对比度文字")

    def _open_high_contrast_text_option(self):
        paths = (
            (
                ("Display", "显示"),
                ("Display size and text", "显示大小和文字"),
            ),
            (
                ("Accessibility", "辅助功能"),
                ("Text and display", "文本和显示"),
            ),
        )
        for path in paths:
            shell(self.serial, "am", "start", "-a", "android.settings.SETTINGS")
            if not tap_path(self, self.device, *path, strict=False):
                continue
            for _ in range(8):
                if any(self.device(text=label).exists(timeout=0.4) for label in self.OPTION_LABELS):
                    return True
                if self.device(scrollable=True).exists(timeout=0.3):
                    self.device(scrollable=True).scroll.vert.forward(steps=35)
                else:
                    self.device.swipe(0.5, 0.84, 0.5, 0.25, duration=0.3)
        return False

    def test_l1_high_contrast_text(self):
        if not self._open_high_contrast_text_option():
            self.skipTest("High contrast text is not exposed by either supported Settings path")
        original_state = switch_state(self.device, self.OPTION_LABELS)
        try:
            set_switch(self, self.device, self.OPTION_LABELS, True)
            screenshot(self.device, __file__, "step02_high_contrast_text_enabled")
            set_switch(self, self.device, self.OPTION_LABELS, False)
            screenshot(self.device, __file__, "step02_high_contrast_text_disabled")
        finally:
            set_switch(self, self.device, self.OPTION_LABELS, original_state)


if __name__ == "__main__":
    unittest.main(verbosity=2)
