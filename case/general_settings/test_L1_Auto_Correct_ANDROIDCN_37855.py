"""ANDROIDCN-37855: L1_Language & keyboard (Auto-correct).

Description:
Check language&input (Auto-correct).
"""

import re
import unittest
import time
import xml.etree.ElementTree as ET

from common.common_method import GeneralSettingsTestCase, screenshot, tap_language_input_entry, tap_path


class TestL1AutoCorrectAndroidcn37855(GeneralSettingsTestCase):

    @staticmethod
    def _parse_bounds(bounds_text):
        match = re.match(r"\[(\d+),(\d+)\]\[(\d+),(\d+)\]", bounds_text or "")
        if not match:
            return None
        return tuple(int(v) for v in match.groups())

    def _is_auto_correction_enabled(self):
        for _ in range(10):
            xml_text = self.device.dump_hierarchy(compressed=False)
            root = ET.fromstring(xml_text)

            rows = []
            for node in root.iter("node"):
                rows.append({
                    "text": (node.attrib.get("text") or "").strip(),
                    "desc": (node.attrib.get("content-desc") or "").strip(),
                    "class": node.attrib.get("class", ""),
                    "checked": node.attrib.get("checked", "false").lower() == "true",
                    "bounds": node.attrib.get("bounds", ""),
                })

            for index, row in enumerate(rows):
                if row["text"] == "Auto-correction":
                    for candidate in rows[index + 1:index + 6]:
                        if candidate["class"] == "android.widget.Switch":
                            return candidate["checked"]
                    break

            time.sleep(0.8)

        self.fail("Auto-correction option is missing")

    def _open_corrections_page(self):
        for _ in range(8):
            xml_text = self.device.dump_hierarchy(compressed=False)
            root = ET.fromstring(xml_text)
            has_auto = False
            has_group = False
            for node in root.iter("node"):
                text_value = (node.attrib.get("text") or "").strip()
                if text_value == "Auto-correction":
                    has_auto = True
                if text_value == "Corrections":
                    has_group = True

            if has_auto and has_group:
                return

            if self.device(scrollable=True).exists(timeout=0.4):
                self.device(scrollable=True).scroll.vert.forward(steps=35)
            time.sleep(0.6)

        self.fail("Corrections section with Auto-correction was not found")

    def test_l1_auto_correct_setting(self):
        """Open Gboard Text correction and verify Auto-correction is enabled by default."""
        tap_path(
            self,
            self.device,
            ("System", "系统"),
            reset_home=True,
            strict=True,
        )
        detected_label = tap_language_input_entry(self, self.device)
        print("[INFO] Detected Languages & input entry: {}".format(detected_label), flush=True)
        tap_path(
            self,
            self.device,
            ("On-screen keyboard", "Virtual keyboard", "屏幕键盘", "虚拟键盘", "Keyboard", "Keyboards"),
            ("Gboard", "Gboard - Multilingual typing", "谷歌拼音输入法"),
            ("Text correction", "Corrections", "文字更正", "文本更正"),
            reset_home=False,
            strict=True,
        )
        self._open_corrections_page()
        self.assertTrue(
            self._is_auto_correction_enabled(),
            "Auto-correction should be enabled by default",
        )
        screenshot(self.device, __file__, "step01_auto_correction_option")


if __name__ == "__main__":
    unittest.main(verbosity=2)