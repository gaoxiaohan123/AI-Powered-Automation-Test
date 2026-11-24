"""ANDROIDCN-37864: Verify Gboard Double-space period default state."""

import time
import unittest

from common.common_method import GeneralSettingsTestCase, screenshot, shell
from case.General_Settings._settings_test_utils import require_visible, set_switch, switch_state


class TestL1DoubleSpacePeriodAndroidcn37864(GeneralSettingsTestCase):
    OPTION_LABELS = ("Double-space period", "双击空格键输入句号")

    def _open_text_correction(self):
        shell(self.serial, "am", "force-stop", "com.google.android.inputmethod.latin")
        output = shell(
            self.serial,
            "am",
            "start",
            "-n",
            "com.google.android.inputmethod.latin/"
            "com.google.android.apps.inputmethod.latin.preference.SettingsActivity",
        )
        if "Error:" in output:
            self.skipTest("Gboard Settings activity is not available")
        text_correction = require_visible(
            self,
            self.device,
            ("Text correction", "文本更正"),
            "Gboard Text correction entry",
        )[0]
        text_correction.click()
        time.sleep(0.8)

    def test_l1_double_space_period(self):
        self._open_text_correction()
        require_visible(self, self.device, self.OPTION_LABELS, "Double-space period")
        original_state = switch_state(self.device, self.OPTION_LABELS)
        self.assertTrue(original_state, "Double-space period is not enabled by default")
        try:
            screenshot(self.device, __file__, "step02_double_space_enabled")
            set_switch(self, self.device, self.OPTION_LABELS, False)
            screenshot(self.device, __file__, "step04_double_space_disabled")
        finally:
            set_switch(self, self.device, self.OPTION_LABELS, original_state)


if __name__ == "__main__":
    unittest.main(verbosity=2)