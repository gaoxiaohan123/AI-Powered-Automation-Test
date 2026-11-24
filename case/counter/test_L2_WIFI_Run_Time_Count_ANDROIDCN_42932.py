# -*- coding:utf-8 -*-
"""Verify HSMCounters records Wi-Fi enabled runtime."""

import os
import re
import sys
import time
import unittest
import xml.etree.ElementTree as element_tree

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import uiautomator2 as u2

from common.adb_common import adb_command, dcs_test_wait_device_online, get_device_serial, save_step_screenshot
from common.common_method import CounterUiLifecycle

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.realpath(__file__))))
SCRIPT_BASENAME = os.path.splitext(os.path.basename(__file__))[0]
SCRIPT_IMG_DIR = os.path.join(PROJECT_ROOT, "img", SCRIPT_BASENAME)
os.makedirs(SCRIPT_IMG_DIR, exist_ok=True)

SERIAL = get_device_serial()
APP_PACKAGE = "com.honeywell.android.hsmcounters"
APP_COMPONENT = f"{APP_PACKAGE}/.MainActivity"
APK_PATH = os.path.join(PROJECT_ROOT, "files", "apps", "HSM_Counters_signed.apk")
COUNTER_RESOURCE_ID = f"{APP_PACKAGE}:id/counter"
VALUE_RESOURCE_ID = f"{APP_PACKAGE}:id/value"
WIFI_RUNTIME_COUNTER = "WIFI_RUNTIME"
RUNTIME_SECONDS = 65
WIFI_RUNTIME_WINDOW_SECONDS = 120


def _read_counter_value(device, counter_name):
    """Return the integer displayed in the row for the requested counter."""
    for _ in range(12):
        root = element_tree.fromstring(device.dump_hierarchy(compressed=False))
        for parent in root.iter():
            children = list(parent)
            if not any(
                child.attrib.get("resource-id") == COUNTER_RESOURCE_ID
                and child.attrib.get("text") == counter_name
                for child in children
            ):
                continue
            for child in children:
                if child.attrib.get("resource-id") != VALUE_RESOURCE_ID:
                    continue
                value_text = child.attrib.get("text", "").strip()
                if re.fullmatch(r"\d+", value_text):
                    return int(value_text)
                raise AssertionError(f"Invalid {counter_name} value: '{value_text}'")
        device.swipe(540, 1750, 540, 450, duration=0.2)
        time.sleep(0.5)
    raise AssertionError(f"{counter_name} counter was not found in HSMCounters")


class Test_WIFI_Run_Time_Count_ANDROIDCN_42932(unittest.TestCase):
    """ANDROIDCN-42932: HSM_COUNTER_WIFI_RUNTIME increments while Wi-Fi is enabled."""

    @classmethod
    def setUpClass(cls):
        if not SERIAL or not dcs_test_wait_device_online(SERIAL, 30):
            raise RuntimeError("No Android device found. Connect one device or set ANDROID_SERIAL.")
        cls.device = u2.connect(SERIAL)

    def setUp(self):
        self.counter_lifecycle = CounterUiLifecycle(self, SERIAL, APK_PATH, SCRIPT_IMG_DIR)
        self.addCleanup(self.counter_lifecycle.remove_downloaded_apk)
        self.counter_lifecycle.close_background_apps()
        self.device.press("home")
        time.sleep(0.5)
        self._ensure_counter_app_installed()
        self._set_wifi_enabled(False)

    def tearDown(self):
        try:
            self._set_wifi_enabled(False)
            print("[INFO] Wi-Fi left disabled in the visible system Settings page")
        finally:
            self.counter_lifecycle.uninstall()

    def _ensure_counter_app_installed(self):
        self.counter_lifecycle.ensure_installed()

    def _close_background_apps(self):
        try:
            opened = self.device(description="Overview").click_exists(timeout=3)
        except Exception as exc:
            self.fail(f"Failed to open Recent Apps: {exc}")
        self.assertTrue(opened, "Recent Apps navigation button was not visible")
        time.sleep(1)

        for _ in range(12):
            cards = self._recent_task_cards()
            if not cards:
                print("[INFO] No background app cards were visible")
                return

            description, bounds = max(
                cards,
                key=lambda card: (card[1][2] - card[1][0]) * (card[1][3] - card[1][1]),
            )
            left, top, right, bottom = bounds
            card = self.device(description=description)
            if not card.exists(timeout=1):
                continue

            print(f"[INFO] Closing background app card: {description}")
            card_height = bottom - top
            self.device.swipe(
                (left + right) // 2,
                bottom - max(1, card_height // 30),
                (left + right) // 2,
                max(0, top - card_height * 2),
                duration=0.05,
            )

            deadline = time.time() + 3
            while time.time() < deadline:
                if not any(
                    card_description == description
                    for card_description, _ in self._recent_task_cards()
                ):
                    break
                time.sleep(0.2)
            else:
                print(f"[WARN] Recent Apps card remained after swipe; retrying: {description}")

        self.fail("Background app cards remained after 12 individual close attempts")

    def _recent_task_cards(self):
        cards = []
        try:
            root = element_tree.fromstring(self.device.dump_hierarchy(compressed=False))
        except Exception as exc:
            print(f"[WARN] Could not read Recent Apps cards: {exc}")
            return cards

        for node in root.iter():
            attributes = node.attrib
            if (
                attributes.get("package") == "com.android.launcher3"
                and attributes.get("class") == "android.widget.FrameLayout"
                and attributes.get("clickable") == "true"
            ):
                description = attributes.get("content-desc", "").strip()
                bounds_match = re.fullmatch(
                    r"\[(\d+),(\d+)\]\[(\d+),(\d+)\]",
                    attributes.get("bounds", ""),
                )
                if description and bounds_match:
                    cards.append((description, tuple(map(int, bounds_match.groups()))))
        return cards

    def _open_wifi_settings(self):
        for launch_attempt in range(1, 3):
            started = adb_command(
                SERIAL,
                "shell",
                "am",
                "start",
                "-a",
                "android.settings.WIFI_SETTINGS",
                timeout=15,
            )
            self.assertEqual(started.returncode, 0, f"Failed to open Wi-Fi Settings: {started.stderr}")
            toggle = self._wifi_toggle()
            if toggle.exists(timeout=5):
                return toggle
            print(f"[WARN] Wi-Fi Settings was not ready; reopening ({launch_attempt}/2)")
        self.fail("Wi-Fi toggle was not visible in Settings")

    def _set_wifi_enabled(self, enabled):
        toggle = self._open_wifi_settings()
        if bool(toggle.info.get("checked", False)) == enabled:
            if enabled:
                time.sleep(2)
                print("[INFO] Wi-Fi is visibly enabled and stabilized")
            return
        bounds = toggle.info["visibleBounds"]
        self.device.click(
            (bounds["left"] + bounds["right"]) // 2,
            (bounds["top"] + bounds["bottom"]) // 2,
        )
        time.sleep(0.5)
        if bool(self._wifi_toggle().info.get("checked", False)) != enabled:
            self.device.click(540, (bounds["top"] + bounds["bottom"]) // 2)
        deadline = time.time() + 15
        while time.time() < deadline:
            if bool(self._wifi_toggle().info.get("checked", False)) == enabled:
                if enabled:
                    time.sleep(2)
                    print("[INFO] Wi-Fi is visibly enabled and stabilized")
                else:
                    self._wait_for_wifi_disconnected()
                    print("[INFO] Wi-Fi is visibly disconnected")
                return
            time.sleep(1)
        self.fail(f"Wi-Fi did not become {'enabled' if enabled else 'disabled'}")

    def _wifi_toggle(self):
        toggle = self.device(resourceId="android:id/switch_widget")
        if toggle.exists(timeout=0.1):
            return toggle
        return self.device(resourceId="com.android.settings:id/switchWidget")

    def _wait_for_wifi_disconnected(self):
        deadline = time.time() + 20
        while time.time() < deadline:
            if not self.device(text="Connected").exists(timeout=0.1):
                return
            time.sleep(0.5)
        self.fail("Wi-Fi remained visibly connected after being disabled")

    def _open_counter_app(self, refresh=False):
        if refresh:
            stopped = adb_command(SERIAL, "shell", "am", "force-stop", APP_PACKAGE, timeout=15)
            self.assertEqual(stopped.returncode, 0, f"Failed to refresh HSMCounters: {stopped.stderr}")
            time.sleep(1)
        result = adb_command(SERIAL, "shell", "am", "start", "-n", APP_COMPONENT, timeout=20)
        self.assertEqual(result.returncode, 0, f"Failed to launch HSMCounters: {result.stderr}")
        self.counter_lifecycle.dismiss_legacy_app_warning()
        self.assertTrue(
            self.device(resourceId=COUNTER_RESOURCE_ID).exists(timeout=10),
            "HSMCounters counter list was not visible after launch",
        )

    def test_l2_wifi_run_time_count(self):
        print("[Step 1] Open HSMCounters and record WIFI_RUNTIME")
        self._open_counter_app()
        count_before = _read_counter_value(self.device, WIFI_RUNTIME_COUNTER)
        save_step_screenshot(self.device, "step01_wifi_runtime_before", SCRIPT_IMG_DIR)
        print(f"[INFO] WIFI_RUNTIME before: {count_before}")

        print(f"[Step 2] Enable Wi-Fi for {WIFI_RUNTIME_WINDOW_SECONDS} seconds")
        self._set_wifi_enabled(True)
        time.sleep(WIFI_RUNTIME_WINDOW_SECONDS)
        self._set_wifi_enabled(False)

        print("[Step 3] Reopen HSMCounters and verify the runtime increased")
        self._open_counter_app(refresh=True)
        count_after = _read_counter_value(self.device, WIFI_RUNTIME_COUNTER)
        save_step_screenshot(self.device, "step03_wifi_runtime_after", SCRIPT_IMG_DIR)
        print(f"[INFO] WIFI_RUNTIME after: {count_after}")
        self.assertGreaterEqual(
            count_after,
            count_before + RUNTIME_SECONDS,
            f"Expected WIFI_RUNTIME to increase by at least {RUNTIME_SECONDS} seconds; "
            f"before={count_before}, after={count_after}",
        )


if __name__ == "__main__":
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(Test_WIFI_Run_Time_Count_ANDROIDCN_42932)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)