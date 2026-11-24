"""ANDROIDCN-34632: Verify Power button ends call setting toggles."""

import os
import time
import unittest

from common.common_method import GeneralSettingsTestCase, open_settings_action, screenshot, shell
from case.General_Settings._settings_test_utils import (
    click_visible,
    prepare_settings_entry,
    set_switch,
    switch_state,
)


class TestL1PowerButtonEndsCallAndroidcn34632(GeneralSettingsTestCase):
    OPTION_LABELS = ("Power button ends call", "电源按钮挂断电话")

    def _is_wlan_only_device(self):
        override = (os.environ.get("FORCE_WLAN_ONLY_DEVICE") or "").strip().lower()
        if override in ("1", "true", "yes", "y", "on"):
            return True
        if override in ("0", "false", "no", "n", "off"):
            return False
        if shell(self.serial, "getprop", "ro.radio.noril").lower() in ("1", "true", "yes"):
            return True
        return "android.hardware.telephony" not in shell(self.serial, "pm", "list", "features")

    def _verify_call_can_be_ended_with_power_button(self):
        test_number = (os.environ.get("TEST_PHONE_NUMBER") or "").strip()
        if not test_number:
            print("[INFO] WWAN live-call verification was not run: TEST_PHONE_NUMBER is not configured", flush=True)
            return

        shell(self.serial, "am", "start", "-a", "android.intent.action.CALL", "-d", "tel:" + test_number)
        time.sleep(3)
        shell(self.serial, "input", "keyevent", "26")
        time.sleep(2)
        call_state = shell(self.serial, "dumpsys", "telephony.registry")
        self.assertIn("mCallState=0", call_state, "Power button did not end the active call")

    def _open_system_controls(self):
        for _ in range(2):
            prepare_settings_entry(self.serial)
            shell(self.serial, "am", "force-stop", "com.android.settings")
            open_settings_action(self, self.device, "android.settings.ACCESSIBILITY_SETTINGS", wait_seconds=1)
            deadline = time.time() + 10
            while time.time() < deadline:
                current = self.device.app_current()
                if current.get("activity", "").endswith("AccessibilitySettingsActivity"):
                    click_visible(self, self.device, ("System controls", "系统控制"), "System controls")
                    return
                time.sleep(0.5)
        self.fail("Accessibility System controls page did not become ready within two launch attempts")

    def test_l1_power_button_ends_call(self):
        self._open_system_controls()
        original_state = switch_state(self.device, self.OPTION_LABELS)
        set_switch(self, self.device, self.OPTION_LABELS, True)
        screenshot(self.device, __file__, "step02_power_button_ends_call_enabled")
        try:
            if not self._is_wlan_only_device():
                self._verify_call_can_be_ended_with_power_button()
        finally:
            set_switch(self, self.device, self.OPTION_LABELS, original_state)
            screenshot(self.device, __file__, "step04_power_button_ends_call_disabled")


if __name__ == "__main__":
    unittest.main(verbosity=2)
