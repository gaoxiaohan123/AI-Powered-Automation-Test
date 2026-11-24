"""ANDROIDCN-37862: L1_Language & keyboard (Popup on keypress).

Description:
Check language&input (Popup on keypress).
"""

import time
import xml.etree.ElementTree as ET
import unittest
from PIL import ImageChops
import subprocess

from common.common_method import (
    GeneralSettingsTestCase,
    open_settings_action,
    screenshot,
    shell,
    tap_language_input_entry,
    tap_path,
)


class TestL1PopupOnKeypressAndroidcn37862(GeneralSettingsTestCase):

    AOSP_KEYBOARD_CANDIDATES = (
        "Android Keyboard (AOSP)",
        "Android Keyboard",
        "AOSP",
        "安卓键盘",
    )

    GBOARD_CANDIDATES = (
        "Gboard",
        "Gboard - Multilingual typing",
        "谷歌拼音输入法",
    )

    POPUP_ON_KEYPRESS_CANDIDATES = (
        "Popup on keypress",
        "按键时弹出",
        "按键弹出",
    )

    def _open_popup_on_keypress_option(self):
        output = shell(
            self.serial,
            "am",
            "start",
            "-n",
            "com.google.android.inputmethod.latin/"
            "com.google.android.apps.inputmethod.latin.preference.SettingsActivity",
        )
        if "Error:" not in output:
            if self.device(text="Keys").exists(timeout=2):
                return
            for label in self.POPUP_ON_KEYPRESS_CANDIDATES:
                if self.device(text=label).exists(timeout=0.3):
                    return
            if self.device(text="Preferences").exists(timeout=2):
                self.device(text="Preferences").click()
                time.sleep(1.2)
                return

        open_settings_action(self, self.device, "android.settings.INPUT_METHOD_SETTINGS")

        # CT47 uses Gboard, whose key-preview setting is in Preferences.
        if tap_path(
            self,
            self.device,
            ("On-screen keyboard", "Virtual keyboard", "屏幕键盘", "虚拟键盘", "Keyboard", "Keyboards"),
            self.GBOARD_CANDIDATES,
            ("Preferences", "Preference", "偏好设置", "首选项"),
            reset_home=False,
            strict=False,
        ):
            return

        # Some device builds expose Gboard directly from the input-method page.
        if tap_path(
            self,
            self.device,
            self.GBOARD_CANDIDATES,
            ("Preferences", "Preference", "偏好设置", "首选项"),
            reset_home=False,
            strict=False,
        ):
            return

        gboard_visible = False
        for candidate in self.GBOARD_CANDIDATES:
            if self.device(textContains=candidate).exists(timeout=0.3):
                gboard_visible = True
                break
        if not gboard_visible:
            self.skipTest("Gboard is not installed or enabled on this device")

        # Final fallback for device variants that only expose the System path.
        open_settings_action(self, self.device, "android.settings.SETTINGS")
        if tap_path(
            self,
            self.device,
            ("System", "系统"),
            reset_home=False,
            strict=False,
        ):
            detected_label = tap_language_input_entry(self, self.device)
            print("[INFO] Detected Languages & input entry: {}".format(detected_label), flush=True)
            tap_path(
                self,
                self.device,
                ("On-screen keyboard", "Virtual keyboard", "屏幕键盘", "虚拟键盘", "Keyboard", "Keyboards"),
                self.GBOARD_CANDIDATES,
                ("Preferences", "Preference", "偏好设置", "首选项"),
                reset_home=False,
                strict=False,
            )
            if self.device(text="Popup on keypress").exists(timeout=0.8) or self.device(textContains="keypress").exists(timeout=0.8):
                return

        self.skipTest("Cannot navigate to Gboard Preferences on this device build/language")

    def _popup_on_keypress_switch_state(self):
        if self.device(scrollable=True).exists(timeout=0.4):
            self.device(scrollable=True).scroll.vert.backward(steps=100)
            time.sleep(0.5)
        for _ in range(8):
            xml_text = self.device.dump_hierarchy(compressed=False)
            root = ET.fromstring(xml_text)
            rows = []
            for node in root.iter("node"):
                rows.append({
                    "text": (node.attrib.get("text") or "").strip(),
                    "class": node.attrib.get("class", ""),
                    "checked": node.attrib.get("checked", "false").lower() == "true",
                })

            for index, row in enumerate(rows):
                if row["text"] in self.POPUP_ON_KEYPRESS_CANDIDATES:
                    for candidate in rows[index + 1:index + 8]:
                        if candidate["class"] == "android.widget.Switch":
                            return candidate["checked"]

            if self.device(scrollable=True).exists(timeout=0.4):
                self.device(scrollable=True).scroll.vert.forward(steps=30)
            time.sleep(0.5)

        self.fail("Popup on keypress option is missing")

    def _find_popup_on_keypress_option(self):
        for _ in range(8):
            for label in self.POPUP_ON_KEYPRESS_CANDIDATES:
                option = self.device(text=label)
                if option.exists(timeout=0.3):
                    return option
            if not self.device(scrollable=True).exists(timeout=0.4):
                break
            self.device(scrollable=True).scroll.vert.forward(steps=30)
            time.sleep(0.5)
        self.fail("Popup on keypress option is missing")

    def _set_popup_on_keypress(self, enabled):
        option = self._find_popup_on_keypress_option()
        current = self._popup_on_keypress_switch_state()
        if current == enabled:
            return
        option.click()
        time.sleep(0.8)
        if self._popup_on_keypress_switch_state() == enabled:
            return
        self.fail("Failed to set Popup on keypress to {}".format(enabled))

    def _open_messages_input(self):
        packages = ("com.google.android.apps.messaging", "com.android.messaging")
        target = None
        for pkg in packages:
            try:
                if shell(self.serial, "pm", "path", pkg).startswith("package:"):
                    target = pkg
                    break
            except Exception:
                continue
        if not target:
            self.skipTest("No Messaging app package found for popup-on-keypress verification")

        shell(self.serial, "monkey", "-p", target, "-c", "android.intent.category.LAUNCHER", "1")
        time.sleep(2)

        for selector in (
            self.device(resourceId="com.google.android.apps.messaging:id/start_chat_fab"),
            self.device(resourceId="com.android.messaging:id/start_chat_fab"),
            self.device(textContains="Start chat"),
            self.device(textContains="开始聊天"),
        ):
            if selector.exists(timeout=0.6):
                selector.click()
                time.sleep(1)
                break

        for selector in (
            self.device(textContains="Text message"),
            self.device(textContains="短信"),
            self.device(className="android.widget.EditText"),
            self.device(className="android.widget.MultiAutoCompleteTextView"),
        ):
            if selector.exists(timeout=1):
                selector.click()
                time.sleep(1)
                return

        self.fail("Unable to focus message input box")

    def _tap_keyboard_key_and_verify_input(self):
        editor = self._focused_editor()
        before = editor.get_text() or ""

        for key in (
            self.device(description="a"),
            self.device(text="a"),
            self.device(description="A"),
            self.device(text="A"),
            self.device(description="q"),
            self.device(text="q"),
        ):
            if key.exists(timeout=0.3):
                key.click()
                time.sleep(0.4)
                if self._focused_editor().get_text() != before:
                    return
        else:
            self.device.click(120, 1870)
            time.sleep(0.4)

        editor = self._focused_editor()
        after = editor.get_text() or ""
        self.assertNotEqual(after, before, "Key press did not update message input")

    def _verify_key_preview(self, expected_visible):
        key = self.device(description="a")
        if not key.exists(timeout=0.8):
            key = self.device(text="a")
        if not key.exists(timeout=0.8):
            self.fail("Gboard letter key is not visible for key-preview verification")

        info = key.info
        left, top, right, bottom = info["bounds"]["left"], info["bounds"]["top"], info["bounds"]["right"], info["bounds"]["bottom"]
        center_x, center_y = (left + right) // 2, (top + bottom) // 2
        baseline = self.device.screenshot(format="pillow")

        command = [
            "adb", "-s", self.serial, "shell", "input", "swipe",
            str(center_x), str(center_y), str(center_x), str(center_y), "700",
        ]
        press = subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            time.sleep(0.2)
            pressed = self.device.screenshot(format="pillow")
        finally:
            press.wait(timeout=2)

        difference = ImageChops.difference(baseline, pressed)
        preview_bounds = (
            max(0, left - 80),
            max(0, top - 300),
            min(pressed.width, right + 80),
            max(0, top - 20),
        )
        changed_pixels = sum(
            1
            for pixel in difference.crop(preview_bounds).get_flattened_data()
            if pixel != (0, 0, 0)
        )
        if expected_visible:
            self.assertGreater(changed_pixels, 800, "Gboard key-preview popup was not visible while the key was pressed")
        else:
            self.assertLess(changed_pixels, 800, "Gboard key-preview popup remained visible after disabling the setting")
        return pressed

    def _focused_editor(self):
        for selector in (
            self.device(className="android.widget.EditText"),
            self.device(className="android.widget.MultiAutoCompleteTextView"),
        ):
            if selector.exists(timeout=0.8):
                return selector
        self.fail("Message input box is missing after key press")

    def _clear_message_draft(self):
        for selector in (
            self.device(className="android.widget.EditText"),
            self.device(className="android.widget.MultiAutoCompleteTextView"),
        ):
            if selector.exists(timeout=0.5):
                selector.set_text("")

    def test_l1_popup_on_keypress_setting(self):
        """Execute step1-step5 flow for Popup on keypress with toggle and typing verification."""
        self._open_popup_on_keypress_option()
        original_state = self._popup_on_keypress_switch_state()
        try:
            # Step1/2: Verify Gboard's default state and capture the enabled setting.
            self.assertTrue(original_state, "Popup on keypress should be enabled by default")
            screenshot(self.device, __file__, "step02_popup_on_keypress_enabled")

            # Step3: A held key press shows Gboard's visual preview and inserts text.
            self._open_messages_input()
            self._verify_key_preview(True)
            self._tap_keyboard_key_and_verify_input()
            screenshot(self.device, __file__, "step03_typing_with_popup_enabled")

            # Step4: Disable the visual preview.
            self._open_popup_on_keypress_option()
            self._set_popup_on_keypress(False)
            self.assertFalse(self._popup_on_keypress_switch_state(), "Popup on keypress should be disabled")
            screenshot(self.device, __file__, "step04_popup_on_keypress_disabled")

            # Step5: The visual preview is absent, while key input remains available.
            self._open_messages_input()
            self._verify_key_preview(False)
            self._tap_keyboard_key_and_verify_input()
            screenshot(self.device, __file__, "step05_typing_with_popup_disabled")
        finally:
            try:
                self._open_popup_on_keypress_option()
                self._set_popup_on_keypress(original_state)
            finally:
                self._open_messages_input()
                self._clear_message_draft()


if __name__ == "__main__":
    unittest.main(verbosity=2)