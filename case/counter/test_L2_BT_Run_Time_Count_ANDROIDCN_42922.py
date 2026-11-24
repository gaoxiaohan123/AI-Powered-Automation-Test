# -*- coding:utf-8 -*-
"""Verify HSMCounters records Bluetooth enabled runtime."""

import os
import re
import sys
import time
import unittest
import xml.etree.ElementTree as element_tree

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import uiautomator2 as u2

from common.adb_common import adb_command, dcs_test_wait_device_online, get_device_serial, save_step_screenshot
from common.common_method import CounterUiLifecycle, shell

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.realpath(__file__))))
SCRIPT_BASENAME = os.path.splitext(os.path.basename(__file__))[0]
SCRIPT_IMG_DIR = os.path.join(PROJECT_ROOT, "img", SCRIPT_BASENAME)
os.makedirs(SCRIPT_IMG_DIR, exist_ok=True)

SERIAL = get_device_serial()
APP_PACKAGE = "com.honeywell.android.hsmcounters"
APP_COMPONENT = f"{APP_PACKAGE}/.MainActivity"
APK_PATH = os.path.join(PROJECT_ROOT, "files", "apps", "HSM_Counters_signed.apk")
DOWNLOAD_DIR = "/sdcard/Download"
DEVICE_APK_PATH = f"{DOWNLOAD_DIR}/HSM_Counters_signed.apk"
APK_PREVIEW_ICON_COORDINATES = (455, 770)
COUNTER_RESOURCE_ID = f"{APP_PACKAGE}:id/counter"
VALUE_RESOURCE_ID = f"{APP_PACKAGE}:id/value"
BLUETOOTH_RUNTIME_COUNTER = "BLUETOOTH_RUNTIME"
RUNTIME_SECONDS = 65
RUNTIME_BUFFER_SECONDS = 2


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


class Test_BT_Run_Time_Count_ANDROIDCN_42922(unittest.TestCase):
    """ANDROIDCN-42922: HSM_COUNTER_BT_RUNTIME increments while Bluetooth is enabled."""

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
        self._set_bluetooth_enabled(False)

    def tearDown(self):
        try:
            self._set_bluetooth_enabled(False)
            print("[INFO] Bluetooth left disabled in the visible system Settings page")
        finally:
            self.counter_lifecycle.uninstall()

    def _ensure_counter_app_installed(self):
        self.counter_lifecycle.ensure_installed()

    def _open_downloaded_counter_apk(self):
        print("[Step 6] Open Downloads and tap the HSMCounters APK preview icon")
        for attempt in range(2):
            adb_command(SERIAL, "shell", "am", "force-stop", "com.google.android.documentsui", timeout=15)
            opened = adb_command(
                SERIAL,
                "shell",
                "am",
                "start",
                "-a",
                "android.intent.action.VIEW_DOWNLOADS",
                timeout=15,
            )
            self.assertEqual(opened.returncode, 0, f"Failed to open Downloads: {opened.stderr}")
            self.assertNotIn("Error", opened.stdout or "", f"Failed to open Downloads: {opened.stdout}")
            apk_file = self.device(text="HSM_Counters_signed.apk")
            if apk_file.exists(timeout=10):
                break
            print(f"[WARN] HSMCounters APK was not visible in Downloads; retrying ({attempt + 1}/2)")
        else:
            self.fail("HSMCounters APK was not visible in Downloads")
        save_step_screenshot(self.device, "step00_apk_visible_before_click", SCRIPT_IMG_DIR)
        self.device.click(*APK_PREVIEW_ICON_COORDINATES)

    def _complete_visible_apk_install(self, attempt):
        """Install directly or accept the visible risk warning before installing."""
        print("[Step 7] Wait 0.5 seconds after tapping the APK")
        time.sleep(0.5)
        save_step_screenshot(self.device, f"step00_apk_click_attempt{attempt}_after_0_5s", SCRIPT_IMG_DIR)
        if self._accept_play_protect_warning_if_needed(timeout=5):
            return self._click_install_button(timeout=5)
        if self._allow_download_manager_install_source_if_needed(timeout=5):
            print("[INFO] Download Manager permission enabled; click Install in the returned confirmation dialog")
            return self._click_install_button(timeout=5)
        if self._click_install_button(timeout=0.5):
            print("[Step 8] Package Installer appeared directly; click INSTALL")
            return True

        if not self._accept_install_risk_if_needed():
            return False

        print("[Step 8] APK risk warning appeared; click CONTINUE, then click INSTALL")
        save_step_screenshot(self.device, f"step00_apk_install_warning_attempt{attempt}", SCRIPT_IMG_DIR)
        time.sleep(0.5)
        save_step_screenshot(self.device, f"step00_after_install_warning_attempt{attempt}", SCRIPT_IMG_DIR)
        if self._accept_play_protect_warning_if_needed(timeout=5):
            return self._click_install_button(timeout=5)
        if self._allow_download_manager_install_source_if_needed(timeout=5):
            print("[INFO] Download Manager permission enabled; click Install in the returned confirmation dialog")
        return self._click_install_button(timeout=5)

    def _click_install_button(self, timeout):
        deadline = time.time() + timeout
        while time.time() < deadline:
            install_button = self.device(textMatches=r"Install|INSTALL|安装")
            if install_button.exists(timeout=0.1):
                install_button.click()
                time.sleep(0.5)
                if self._accept_play_protect_warning_if_needed(timeout=3):
                    return self._click_install_button(timeout=5)
                if self._allow_download_manager_install_source_if_needed(timeout=3):
                    print("[INFO] Download Manager permission enabled; click Install in the returned confirmation dialog")
                    return self._click_install_button(timeout=5)
                time.sleep(0.5)
                return True
            time.sleep(0.1)
        return False

    def _accept_install_risk_if_needed(self):
        """Accept the visible Android warning shown before the install screen."""
        accepted = self._click_visible_text(
            ("Continue", "CONTINUE", "继续", "仍要安装", "继续安装", "OK", "Ok", "确定"),
            timeout=0.5,
            post_click_delay=0,
        )
        if accepted:
            print("[INFO] Accepted the visible APK installation risk reminder")
        return accepted

    def _accept_play_protect_warning_if_needed(self, timeout):
        more_details = None
        for label in ("More details", "MORE DETAILS", "Details", "DETAILS", "更多详细信息", "详情"):
            control = self.device(text=label)
            if control.exists(timeout=timeout):
                more_details = control
                break
        if more_details is None:
            return False
        for press_attempt in range(1, 4):
            self._long_press_control(more_details, duration=1.2)
            print(f"[INFO] Google Play Protect warning detected; clicked More details ({press_attempt}/3)")
            time.sleep(0.8)
            if self._play_protect_install_anyway_bounds():
                break
        self.assertTrue(
            self._long_press_play_protect_install_anyway(timeout=5),
            "Install anyway was not visible after opening Google Play Protect details",
        )
        print("[INFO] Google Play Protect warning detected; clicked Install anyway")
        return True

    def _allow_download_manager_install_source_if_needed(self, timeout):
        current_package = (self.device.app_current() or {}).get("package", "")
        source_permission_page = self.device(textMatches=r"Allow from this source|允许来自此来源")
        if current_package == "com.android.settings" and not source_permission_page.exists(timeout=0.1):
            return False
        if current_package != "com.android.settings":
            if not self._click_visible_text(("Settings", "SETTINGS", "设置"), timeout=timeout, post_click_delay=0):
                return False
            deadline = time.time() + 5
            while time.time() < deadline:
                if (self.device.app_current() or {}).get("package") == "com.android.settings":
                    break
                time.sleep(0.1)
            else:
                return False
        self.assertTrue(
            source_permission_page.exists(timeout=5),
            "Allow from this source page was not visible",
        )
        toggle = self._source_permission_toggle()
        self.assertTrue(toggle.exists(timeout=5), "Allow from this source switch was not visible")
        if not bool(toggle.info.get("checked", False)):
            bounds = toggle.info["visibleBounds"]
            self.device.click(
                (bounds["left"] + bounds["right"]) // 2,
                (bounds["top"] + bounds["bottom"]) // 2,
            )
            time.sleep(0.5)
        self.assertTrue(
            bool(self._source_permission_toggle().info.get("checked", False)),
            "Allow from this source was not enabled",
        )
        print("[INFO] Enabled Allow from this source through the visible Settings page")
        self.device.press("back")
        time.sleep(0.5)
        return True

    def _source_permission_toggle(self):
        toggle = self.device(resourceId="android:id/switch_widget")
        if toggle.exists(timeout=0.1):
            return toggle
        return self.device(checkable=True, clickable=True)

    def _uninstall_counter_app(self):
        print("[Step 16] Display HSMCounters uninstall screen on the device")
        shell(
            SERIAL,
            "am",
            "start",
            "-a",
            "android.settings.APPLICATION_DETAILS_SETTINGS",
            "-d",
            f"package:{APP_PACKAGE}",
            timeout=15,
        )
        time.sleep(2)
        self.assertTrue(
            self._click_visible_text(("Uninstall", "UNINSTALL", "卸载"), timeout=10),
            "Uninstall button was not visible in app details",
        )
        self.assertTrue(
            self._click_visible_text(("OK", "Ok", "确定", "Uninstall", "UNINSTALL", "卸载"), timeout=10),
            "Uninstall confirmation button was not visible",
        )
        self.assertTrue(self._wait_for_counter_package(False), "HSMCounters remained installed after uninstall")
        print("[INFO] HSMCounters uninstall screen completed and package absence verified")

    def _remove_downloaded_counter_apk(self, step_number):
        print(f"[Step {step_number}] Remove HSMCounters APK from device Downloads")
        removed = adb_command(SERIAL, "shell", "rm", "-f", DEVICE_APK_PATH, timeout=30)
        self.assertEqual(removed.returncode, 0, f"Failed to remove Counter APK: {removed.stderr}")
        absent = adb_command(SERIAL, "shell", "test", "!", "-e", DEVICE_APK_PATH, timeout=15)
        self.assertEqual(absent.returncode, 0, "Counter APK remained in Downloads after cleanup")
        print("[INFO] HSMCounters APK is absent from Downloads")

    def _dismiss_incomplete_installer(self):
        current_package = (self.device.app_current() or {}).get("package", "")
        if current_package != "com.google.android.packageinstaller":
            return
        if self._click_visible_text(("Done", "DONE", "完成", "Cancel", "CANCEL", "取消"), timeout=2):
            print("[INFO] Closed the visible incomplete Package Installer screen")
            return
        self.device.press("back")

    def _dismiss_install_success(self):
        if self._click_visible_text(("Done", "DONE", "完成"), timeout=5):
            print("[INFO] Closed the visible installation complete screen")
        time.sleep(0.5)

    def _verify_install_success(self):
        self.assertTrue(
            self._visible_text_exists(("App installed.", "App installed", "APP INSTALLED", "应用已安装"), timeout=15),
            "HSMCounters installation success screen was not visible",
        )
        return self._wait_for_counter_package(True)

    def _click_visible_text(self, labels, timeout, post_click_delay=1):
        deadline = time.time() + timeout
        while time.time() < deadline:
            for label in labels:
                selector = self.device(text=label)
                if selector.exists(timeout=0.3):
                    selector.click()
                    if post_click_delay:
                        time.sleep(post_click_delay)
                    return True
            time.sleep(0.3)
        return False

    def _visible_text_exists(self, labels, timeout):
        deadline = time.time() + timeout
        while time.time() < deadline:
            if any(self.device(text=label).exists(timeout=0.3) for label in labels):
                return True
            time.sleep(0.3)
        return False

    def _long_press_visible_text(self, labels, timeout, post_click_delay=0.5):
        deadline = time.time() + timeout
        while time.time() < deadline:
            for label in labels:
                selector = self.device(text=label)
                if selector.exists(timeout=0.3):
                    self._long_press_control(selector)
                    if post_click_delay:
                        time.sleep(post_click_delay)
                    return True
            time.sleep(0.3)
        return False

    def _long_press_play_protect_install_anyway(self, timeout):
        deadline = time.time() + timeout
        while time.time() < deadline:
            for label in ("Install anyway", "INSTALL ANYWAY", "仍要安装", "仍要安装此应用"):
                control = self.device(text=label)
                if control.exists(timeout=0.1):
                    self._long_press_control(control)
                    time.sleep(0.5)
                    return True
            link_bounds = self._play_protect_install_anyway_bounds()
            if link_bounds:
                left, _, _, bottom = link_bounds
                self.device.long_click(left + 150, bottom - 30, duration=0.8)
                time.sleep(0.5)
                return True
            time.sleep(0.1)
        return False

    def _play_protect_install_anyway_bounds(self):
        root = element_tree.fromstring(self.device.dump_hierarchy(compressed=False))
        for node in root.iter():
            if "Install anyway" not in node.attrib.get("text", ""):
                continue
            bounds = node.attrib.get("bounds", "")
            values = [int(value) for value in bounds.replace("[", ",").replace("]", ",").split(",") if value]
            if len(values) == 4:
                return values
        return None

    def _long_press_control(self, control, duration=0.8):
        bounds = control.info["visibleBounds"]
        self.device.long_click(
            (bounds["left"] + bounds["right"]) // 2,
            (bounds["top"] + bounds["bottom"]) // 2,
            duration=duration,
        )

    def _wait_for_counter_package(self, should_be_installed):
        deadline = time.time() + 60
        while time.time() < deadline:
            installed = adb_command(SERIAL, "shell", "pm", "path", APP_PACKAGE, timeout=15)
            is_installed = installed.returncode == 0 and bool((installed.stdout or "").strip())
            if is_installed == should_be_installed:
                return True
            time.sleep(1)
        return False

    def _close_background_apps(self):
        try:
            opened = self.device(description="Overview").click_exists(timeout=3)
        except Exception as exc:
            self.fail(f"Failed to open Recent Apps: {exc}")
        if not opened:
            self.device.press("recent")
            time.sleep(1)
            opened = bool(self._recent_task_cards()) or self.device(description="Overview").exists(timeout=1)
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

    def _open_bluetooth_settings(self):
        toggle = self.device(resourceId="android:id/switch_widget")
        for launch_attempt in range(1, 3):
            started = adb_command(
                SERIAL,
                "shell",
                "am",
                "start",
                "-a",
                "android.settings.BLUETOOTH_SETTINGS",
                timeout=15,
            )
            self.assertEqual(started.returncode, 0, f"Failed to open Bluetooth Settings: {started.stderr}")
            if toggle.exists(timeout=5):
                return toggle
            print(f"[WARN] Bluetooth Settings was not ready; reopening ({launch_attempt}/2)")
        if not toggle.exists(timeout=1):
            self.assertTrue(
                self._click_visible_text(("Connection preferences",), timeout=5),
                "Connection preferences was not visible in Connected devices",
            )
            self.assertTrue(
                self._click_visible_text(("Bluetooth",), timeout=5),
                "Bluetooth was not visible in Connection preferences",
            )
        self.assertTrue(toggle.exists(timeout=10), "Bluetooth toggle was not visible in Settings")
        return toggle

    def _set_bluetooth_enabled(self, enabled):
        toggle = self._open_bluetooth_settings()
        if bool(toggle.info.get("checked", False)) == enabled:
            return
        bounds = toggle.info["visibleBounds"]
        self.device.click(
            (bounds["left"] + bounds["right"]) // 2,
            (bounds["top"] + bounds["bottom"]) // 2,
        )
        time.sleep(0.5)
        if bool(self.device(resourceId="android:id/switch_widget").info.get("checked", False)) != enabled:
            self.device.click(540, (bounds["top"] + bounds["bottom"]) // 2)
        deadline = time.time() + 15
        while time.time() < deadline:
            if bool(self.device(resourceId="android:id/switch_widget").info.get("checked", False)) == enabled:
                return
            time.sleep(1)
        self.fail(f"Bluetooth did not become {'enabled' if enabled else 'disabled'}")

    def _open_counter_app(self):
        result = adb_command(SERIAL, "shell", "am", "start", "-n", APP_COMPONENT, timeout=20)
        self.assertEqual(result.returncode, 0, f"Failed to launch HSMCounters: {result.stderr}")
        if self._click_visible_text(("OK", "Ok", "确定"), timeout=2, post_click_delay=0):
            print("[INFO] Dismissed the visible HSMCounters legacy-app warning")
        self.assertTrue(
            self.device(resourceId=COUNTER_RESOURCE_ID).exists(timeout=10),
            "HSMCounters counter list was not visible after launch",
        )

    def test_l2_bt_run_time_count(self):
        print("[Step 11] Open HSMCounters and record BLUETOOTH_RUNTIME")
        self._open_counter_app()
        count_before = _read_counter_value(self.device, BLUETOOTH_RUNTIME_COUNTER)
        save_step_screenshot(self.device, "step01_bluetooth_runtime_before", SCRIPT_IMG_DIR)
        print(f"[INFO] BLUETOOTH_RUNTIME before: {count_before}")

        print(f"[Step 12] Enable Bluetooth for {RUNTIME_SECONDS + RUNTIME_BUFFER_SECONDS} seconds")
        self._set_bluetooth_enabled(True)
        time.sleep(RUNTIME_SECONDS + RUNTIME_BUFFER_SECONDS)
        self._set_bluetooth_enabled(False)

        print("[Step 14] Reopen HSMCounters and verify the runtime increased")
        self._open_counter_app()
        count_after = _read_counter_value(self.device, BLUETOOTH_RUNTIME_COUNTER)
        save_step_screenshot(self.device, "step02_bluetooth_runtime_after", SCRIPT_IMG_DIR)
        print(f"[INFO] BLUETOOTH_RUNTIME after: {count_after}")
        self.assertGreaterEqual(
            count_after,
            count_before + RUNTIME_SECONDS,
            f"Expected BLUETOOTH_RUNTIME to increase by at least {RUNTIME_SECONDS} seconds; "
            f"before={count_before}, after={count_after}",
        )


if __name__ == "__main__":
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(Test_BT_Run_Time_Count_ANDROIDCN_42922)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)