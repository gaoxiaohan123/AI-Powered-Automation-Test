"""ANDROIDCN-37852: L1_Language & keyboard (Auto-capitalization).

Description:
Check language&input (Auto-capitalization).
"""

import time
import unittest
import xml.etree.ElementTree as ET

from common.common_method import GeneralSettingsTestCase, screenshot, tap_language_input_entry, tap_path


class TestL1AutoCapitalizationAndroidcn37852(GeneralSettingsTestCase):
    def _is_auto_capitalization_enabled(self):
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
                if row["text"] in ("Auto-capitalization", "Auto capitalization"):
                    for candidate in rows[index + 1:index + 8]:
                        if candidate["class"] == "android.widget.Switch":
                            return candidate["checked"]
                    self.fail("Auto-capitalization switch widget is missing")

            if self.device(scrollable=True).exists(timeout=0.4):
                self.device(scrollable=True).scroll.vert.forward(steps=30)
            time.sleep(0.6)

        self.fail("Gboard Auto-capitalization option is missing")

    def test_l1_auto_capitalization_setting(self):
        """Open Gboard Text correction and verify Auto-capitalization is enabled by default."""
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
        self.assertTrue(self._is_auto_capitalization_enabled(), "Auto-capitalization should be enabled by default")
        screenshot(self.device, __file__, "step01_auto_capitalization_option")


if __name__ == "__main__":
    unittest.main(verbosity=2)