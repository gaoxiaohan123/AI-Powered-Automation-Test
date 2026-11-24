# -*- coding: utf-8 -*-
# __author__ = 'sophy_H400818'

"""
Test case: L3 Keyremap provisioning via EZConfig (ANDROIDCN-33957)

Verifies that a HOME -> ENTER remap pushed through EZConfig's DeviceConfig ->
Honeywell Settings -> KeyRemap node is applied by the Keyremap app and that
the remapped HOME key behaves as ENTER.

Steps:
1. Open Honeywell Settings -> Provisioning Mode and enable it.
2. Open the Power Tools (EZMenu) app -> EZConfig -> navigation drawer ->
   Generator (or Local XML Generator) -> wait 6s -> DeviceConfig -> DeviceConfig
   -> Honeywell Settings -> KeyRemap -> KeyRemap -> set the Value field to
   HOME-ENTER -> Save / Update Configures (directly, or via the overflow menu).
3. Open Settings -> Honeywell Settings -> Keyremap and confirm the HOME row
   now shows ENTER.
4. Confirm the remapped HOME key behaves as ENTER in the Search input field.

Author: Sophy H400818
Date: 2026-09-08
"""

import configparser
import os
import sys
import time
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import uiautomator2 as u2

from common.adb_common import (
    dcs_test_open_honeywell_settings,
    get_device_serial,
    keyremap_tap_navbar_home,
    press_home_key,
    run_adb_cmd,
    save_step_screenshot,
)
from common.common_method import (
    close_settings_app,
    dcs_test_scroll_find_and_click,
    dismiss_full_screen_hint,
    get_case_config,
    get_package_name,
    keyremap_clear_all,
    enable_provisioning_mode,
    keyremap_find_desc_center,
    keyremap_find_text_center,
    keyremap_open_page,
    scan_clear_input_field,
    scan_get_input_field_text,
    scan_open_input_field,
    tap_text,
)


serial = get_device_serial()
if not serial:
    print("Error: No Android device found. Connect a device or set ANDROID_SERIAL.")
    sys.exit(1)

d = u2.connect(serial)

SCRIPT_BASENAME = os.path.splitext(os.path.basename(__file__))[0]
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.realpath(__file__))))
SCRIPT_IMG_DIR = os.path.join(PROJECT_ROOT, "img", SCRIPT_BASENAME)
os.makedirs(SCRIPT_IMG_DIR, exist_ok=True)

SETTINGS_PKG = get_package_name("settings")
KEYREMAP_PKG = get_package_name("keyremap")
EZMENU_PKG = get_case_config("keyremap_apps_case", "powertool_app_package")
EZMENU_LABEL = get_case_config("keyremap_apps_case", "powertool_app_label")

CASE_CONFIG_SECTION = "keyremap_provisioning_case"
PROVISIONING_MODE_LABEL = get_case_config(CASE_CONFIG_SECTION, "provisioning_mode_label")
EZCONFIG_ENTRY_LABEL = get_case_config(CASE_CONFIG_SECTION, "ezconfig_entry_label")
GENERATOR_LABELS = [item.strip() for item in get_case_config(CASE_CONFIG_SECTION, "generator_labels").split(",")]
DEVICE_CONFIG_LABEL = get_case_config(CASE_CONFIG_SECTION, "device_config_label")
HONEYWELL_SETTINGS_NODE_LABEL = get_case_config(CASE_CONFIG_SECTION, "honeywell_settings_node_label")
KEYREMAP_NODE_LABEL = get_case_config(CASE_CONFIG_SECTION, "keyremap_node_label")
IGNORE_KEYREMAP_TO_PTT_LABEL = get_case_config(CASE_CONFIG_SECTION, "ignore_keyremap_to_ptt_label")
REMAP_VALUE = get_case_config(CASE_CONFIG_SECTION, "remap_value")
SAVE_LABEL = get_case_config(CASE_CONFIG_SECTION, "save_label")
UPDATE_CONFIGURES_LABEL = get_case_config(CASE_CONFIG_SECTION, "update_configures_label")
PROBE_TEXT = get_case_config(CASE_CONFIG_SECTION, "probe_text")


def _read_app_close_package(name):
    """Read a bare app package name from the [app_close_commands] section of commands.config."""
    config = configparser.ConfigParser()
    path = os.path.join(os.path.dirname(os.path.realpath(__file__)), "..", "..", "common", "commands.config")
    config.read(path)
    return config.get("app_close_commands", name)


EZCONFIG_PKG = _read_app_close_package("ezconfig")


class TestKeyremapProvisioningViaEZConfig(unittest.TestCase):
    """L3 test: provision HOME -> ENTER through EZConfig and verify it in Keyremap."""

    @classmethod
    def setUpClass(cls):
        cls.dev_id = serial
        print(f"\n[Setup] Device: {cls.dev_id}")

    def setUp(self):
        print(f"\n{'=' * 60}\nTest: {self.id()}\n{'=' * 60}")
        self.provisioning_was_enabled = None
        d.press("home")
        time.sleep(1)

    def tearDown(self):
        if keyremap_open_page(d, serial, SETTINGS_PKG, KEYREMAP_PKG):
            keyremap_clear_all(d, serial)
        # return to the parent page after clearing
        run_adb_cmd(serial, "shell input keyevent KEYCODE_BACK", log_print=False)
        time.sleep(1)

        # Restore Provisioning Mode to whatever state it was in before the test, if it was captured.
        if self.provisioning_was_enabled is False and dcs_test_open_honeywell_settings(serial):
            time.sleep(2)
            if dcs_test_scroll_find_and_click(d, [PROVISIONING_MODE_LABEL], max_swipes=6):
                time.sleep(2)
                switch = d(resourceId="android:id/switch_widget")
                if switch.exists(timeout=3) and bool(switch.info.get("checked", False)):
                    switch.click()
                    time.sleep(1)

        run_adb_cmd(serial, f"shell am force-stop {EZCONFIG_PKG}", log_print=False)
        # The Value editor screen actually runs as com.honeywell.tools.xmleditor (confirmed by
        # its resourceId prefix), a different package from EZCONFIG_PKG, so it needs its own stop.
        run_adb_cmd(serial, "shell am force-stop com.honeywell.tools.xmleditor", log_print=False)
        run_adb_cmd(serial, f"shell am force-stop {EZMENU_PKG}", log_print=False)
        run_adb_cmd(serial, "shell am force-stop com.honeywell.settings", log_print=False)
        close_settings_app(serial)
        d.screen_on()
        d.press("home")
        print(f"[TearDown] Completed: {self.id()}")

    def _tap_more_options(self):
        """Open the current screen's overflow ('more options') menu."""
        more_options = d(descriptionMatches=r"(?i).*more options.*")
        if not more_options.exists(timeout=2):
            position = keyremap_find_desc_center(d, "More options", contains=True)
            if position:
                run_adb_cmd(serial, f"shell input tap {position[0]} {position[1]}", log_print=False)
                time.sleep(1)
                return True
            return False
        more_options.click()
        time.sleep(1)
        return True

    def _generator_labels_visible(self):
        """Return True once any Generator-related drawer entry is visible."""
        return any(d(text=label).exists(timeout=1) for label in GENERATOR_LABELS)

    def _click_leftmost_toolbar_icon(self):
        """Tap the leftmost clickable toolbar icon, which is the drawer toggle on firmwares
        that mislabel its content-desc (e.g. as 'Navigate up' instead of 'Open navigation drawer')."""
        best = None
        for class_name in ("android.widget.ImageButton", "android.widget.ImageView"):
            elements = d(className=class_name, clickable=True)
            for idx in range(elements.count):
                try:
                    bounds = elements[idx].info.get("bounds", {})
                except Exception:
                    continue
                top = bounds.get("top", 10 ** 9)
                left = bounds.get("left", 10 ** 9)
                if top > 200:
                    continue
                if best is None or left < best[0]:
                    best = (left, bounds)
        if best is None:
            return False
        _, bounds = best
        center_x = (bounds.get("left", 0) + bounds.get("right", 0)) // 2
        center_y = (bounds.get("top", 0) + bounds.get("bottom", 0)) // 2
        run_adb_cmd(serial, f"shell input tap {center_x} {center_y}", log_print=False)
        time.sleep(1)
        return True

    def _open_navigation_drawer(self):
        """Open EZConfig's left navigation drawer (hamburger icon), covering firmwares whose
        toolbar toggle content-desc is mislabeled as 'Navigate up' on the DrawerLayout root screen."""
        drawer_descriptions = ("Open navigation drawer", "navigation drawer", "Navigation drawer")
        for _ in range(2):
            for desc in drawer_descriptions:
                position = keyremap_find_desc_center(d, desc, contains=True)
                if position:
                    run_adb_cmd(serial, f"shell input tap {position[0]} {position[1]}", log_print=False)
                    time.sleep(1)
                    if self._generator_labels_visible():
                        return True

            # A DrawerLayout means the top-left toolbar icon is the drawer toggle even when its
            # content-desc reads "Navigate up" (observed on some firmware/screen resolutions).
            if d(classNameMatches=r".*DrawerLayout$").exists(timeout=1):
                if self._click_leftmost_toolbar_icon() and self._generator_labels_visible():
                    return True

            # No DrawerLayout: "Navigate up" is a genuine back arrow, so return to the root screen first.
            if d(descriptionMatches=r"(?i).*navigate up.*").exists(timeout=0.5):
                d.press("back")
                time.sleep(1)
                continue
            break

        # Final fallback: tap the toolbar's top-left corner directly.
        size_output = run_adb_cmd(serial, "shell wm size", log_print=False)
        size_text = size_output.decode("utf-8", errors="ignore") if isinstance(size_output, bytes) else str(size_output)
        import re

        match = re.search(r"Physical size:\s*(\d+)x(\d+)", size_text)
        if match:
            width, _ = (int(value) for value in match.groups())
            tap_x, tap_y = round(width * 0.08), 70
        else:
            tap_x, tap_y = 38, 70
        run_adb_cmd(serial, f"shell input tap {tap_x} {tap_y}", log_print=False)
        time.sleep(1)
        return self._generator_labels_visible()

    def _select_generator(self):
        """Tap 'Generator', falling back to 'Local XML Generator'."""
        for label in GENERATOR_LABELS:
            if tap_text(d, label):
                return True
        return False

    def _save_and_update_configures(self):
        """Apply the edited Value: tap Save/Update Configures directly, else via the overflow menu."""
        saved = False
        if d(text=SAVE_LABEL).exists(timeout=2):
            d(text=SAVE_LABEL).click()
            time.sleep(2)
            saved = True
        if d(text=UPDATE_CONFIGURES_LABEL).exists(timeout=2):
            d(text=UPDATE_CONFIGURES_LABEL).click()
            time.sleep(1)
            saved = True
        if saved:
            return True

        if not self._tap_more_options():
            return False
        if not tap_text(d, SAVE_LABEL):
            return False
        if not self._tap_more_options():
            return False
        return tap_text(d, UPDATE_CONFIGURES_LABEL)

    def test_keyremap_provisioning_home_to_enter(self):
        """
        L3 Keyremap provisioning test: configure HOME -> ENTER through EZConfig.
        Step 1: Enable Provisioning Mode in Honeywell Settings.
        Step 2: Open EZConfig, navigate to DeviceConfig -> Honeywell Settings
            -> KeyRemap, set its value to HOME -> ENTER, then save and
            update the configuration.
        Step 3: Open Keyremap and verify that HOME is mapped to ENTER.
        Step 4: Enter probe text in launcher Search, press the mapped Home key,
            and verify ENTER submits the search while preserving the query.
        """
        print("\n[L3_Keyremap] Testing EZConfig provisioning HOME -> ENTER\n" + "=" * 60)

        # ── Step 1: enable Provisioning Mode ──────────────────────────────────
        print(f"\n[Step 1/4] Honeywell Settings -> enable '{PROVISIONING_MODE_LABEL}'")
        print("-" * 60)

        enabled, self.provisioning_was_enabled = enable_provisioning_mode(
            d, serial, PROVISIONING_MODE_LABEL
        )
        if not enabled:
            save_step_screenshot(d, "step1_provisioning_mode_not_enabled", SCRIPT_IMG_DIR)
            self.fail(f"Step 1 Failed: could not enable '{PROVISIONING_MODE_LABEL}'")

        save_step_screenshot(d, "step1_provisioning_mode_enabled", SCRIPT_IMG_DIR)
        print(f"  ✓ '{PROVISIONING_MODE_LABEL}' enabled")

        # ── Step 2: navigate EZConfig to the KeyRemap Value field ─────────────
        print(f"\n[Step 2/4] Power Tools -> EZConfig -> Generator -> DeviceConfig -> KeyRemap")
        print("-" * 60)

        # com.honeywell.tools.ezmenu declares several LAUNCHER activities (Demos, Tools, NFC);
        # an ambiguous package-only app_start can resolve to the Scan Demo screen instead of
        # Power Tools, so launch the ToolsLaunchActivity component explicitly.
        run_adb_cmd(serial, f"shell am force-stop {EZMENU_PKG}", log_print=False)
        time.sleep(1)
        run_adb_cmd(serial, f"shell am start -n {EZMENU_PKG}/.ToolsLaunchActivity", log_print=False)
        time.sleep(3)
        if not tap_text(d, EZCONFIG_ENTRY_LABEL):
            save_step_screenshot(d, "step2_ezconfig_entry_not_found", SCRIPT_IMG_DIR)
            self.fail(f"Step 2 Failed: '{EZCONFIG_ENTRY_LABEL}' not found in {EZMENU_LABEL}")
        time.sleep(3)
        if dismiss_full_screen_hint(d):
            print("  Dismissed the optional 'Viewing full screen' dialog")
        save_step_screenshot(d, "step2_ezconfig_opened", SCRIPT_IMG_DIR)

        if not self._open_navigation_drawer():
            save_step_screenshot(d, "step2_nav_drawer_not_opened", SCRIPT_IMG_DIR)
            self.fail("Step 2 Failed: could not open the EZConfig navigation drawer")
        time.sleep(1)

        if not self._select_generator():
            save_step_screenshot(d, "step2_generator_not_found", SCRIPT_IMG_DIR)
            self.fail(f"Step 2 Failed: none of {GENERATOR_LABELS} found in the navigation drawer")
        save_step_screenshot(d, "step2_generator_selected", SCRIPT_IMG_DIR)

        time.sleep(6)

        if not dcs_test_scroll_find_and_click(d, [DEVICE_CONFIG_LABEL], max_swipes=8):
            save_step_screenshot(d, "step2_device_config_not_found", SCRIPT_IMG_DIR)
            self.fail(f"Step 2 Failed: '{DEVICE_CONFIG_LABEL}' not found")
        time.sleep(2)
        save_step_screenshot(d, "step2_device_config_opened", SCRIPT_IMG_DIR)

        if not dcs_test_scroll_find_and_click(d, [DEVICE_CONFIG_LABEL], max_swipes=8):
            save_step_screenshot(d, "step2_device_config_node_not_found", SCRIPT_IMG_DIR)
            self.fail(f"Step 2 Failed: '{DEVICE_CONFIG_LABEL}' node not found after opening the generator page")
        time.sleep(1)

        if not dcs_test_scroll_find_and_click(d, [HONEYWELL_SETTINGS_NODE_LABEL], max_swipes=8):
            save_step_screenshot(d, "step2_honeywell_settings_node_not_found", SCRIPT_IMG_DIR)
            self.fail(f"Step 2 Failed: '{HONEYWELL_SETTINGS_NODE_LABEL}' node not found")
        time.sleep(1)

        if not dcs_test_scroll_find_and_click(d, [KEYREMAP_NODE_LABEL], max_swipes=8):
            save_step_screenshot(d, "step2_keyremap_node_not_found", SCRIPT_IMG_DIR)
            self.fail(f"Step 2 Failed: '{KEYREMAP_NODE_LABEL}' node not found under {HONEYWELL_SETTINGS_NODE_LABEL}")
        time.sleep(1)

        # KeyRemap is only selectable after both sibling entries are visible.
        anchor = None
        for _ in range(8):
            ignore_keyremap_to_ptt = d(text=IGNORE_KEYREMAP_TO_PTT_LABEL)
            clear_keyremap = d(text="ClearAllKeyRemap")
            if ignore_keyremap_to_ptt.exists(timeout=0.5) and clear_keyremap.exists(timeout=0.5):
                anchor = ignore_keyremap_to_ptt
                break
            if d(scrollable=True).exists(timeout=0.5):
                d(scrollable=True).scroll.forward()
            else:
                d.swipe(0.5, 0.8, 0.5, 0.3, duration=0.2)
            time.sleep(0.5)

        if anchor is None:
            save_step_screenshot(d, "step2_keyremap_entries_not_found", SCRIPT_IMG_DIR)
            self.fail(
                f"Step 2 Failed: both '{IGNORE_KEYREMAP_TO_PTT_LABEL}' and "
                "'Clear KeyRemap' must be visible"
            )

        keyremap_subitem = anchor.down(text=KEYREMAP_NODE_LABEL)
        if not keyremap_subitem.exists(timeout=2):
            save_step_screenshot(d, "step2_keyremap_subitem_not_found", SCRIPT_IMG_DIR)
            self.fail(f"Step 2 Failed: '{KEYREMAP_NODE_LABEL}' below '{IGNORE_KEYREMAP_TO_PTT_LABEL}' not found")
        keyremap_subitem.click()
        time.sleep(1)
        save_step_screenshot(d, "step2_keyremap_node_opened", SCRIPT_IMG_DIR)

        edit = d(resourceId="com.honeywell.tools.xmleditor:id/valuevalue")
        time.sleep(1)
        if not edit.exists(timeout=5):
            save_step_screenshot(d, "step2_value_field_not_found", SCRIPT_IMG_DIR)
            self.fail("Step 2 Failed: Value edit field not found on the KeyRemap node")
        edit.click()
        time.sleep(0.5)
        edit.clear_text()
        edit.set_text(REMAP_VALUE)
        time.sleep(1)

        run_adb_cmd(serial, "shell input keyevent KEYCODE_BACK", log_print=False)
        time.sleep(1)
        save_step_screenshot(d, "step2_value_entered", SCRIPT_IMG_DIR)
        print(f"  ✓ Value set to '{REMAP_VALUE}'")

        if not self._save_and_update_configures():
            save_step_screenshot(d, "step2_save_update_failed", SCRIPT_IMG_DIR)
            self.fail("Step 2 Failed: could not Save / Update Configures the KeyRemap value")
        time.sleep(2)
        save_step_screenshot(d, "step2_saved_and_updated", SCRIPT_IMG_DIR)
        print("  ✓ Step 2 passed")

        # ── Step 3: verify Keyremap shows HOME -> ENTER ───────────────────────
        print("\n[Step 3/4] Settings -> Honeywell Settings -> Keyremap: verify HOME -> ENTER")
        print("-" * 60)

        if not keyremap_open_page(d, serial, SETTINGS_PKG, KEYREMAP_PKG):
            save_step_screenshot(d, "step3_keyremap_not_opened", SCRIPT_IMG_DIR)
            self.fail("Step 3 Failed: could not navigate to the Keyremap page")

        if keyremap_find_text_center(d, "HOME", contains=False) is None:
            save_step_screenshot(d, "step3_home_entry_missing", SCRIPT_IMG_DIR)
            self.fail("Step 3 Failed: HOME entry not shown in Keyremap after EZConfig provisioning")

        if keyremap_find_text_center(d, "ENTER", contains=True) is None:
            save_step_screenshot(d, "step3_enter_target_missing", SCRIPT_IMG_DIR)
            self.fail("Step 3 Failed: Keyremap does not show ENTER as the HOME target")

        save_step_screenshot(d, "step3_home_to_enter_confirmed", SCRIPT_IMG_DIR)
        print("  ✓ Keyremap shows HOME -> ENTER")
        print("  ✓ Step 3 passed")

        # ── Step 4: functional check ───────────────────────────────────────────
        print(f"\n[Step 4/4] Verify the remapped HOME key behaves as ENTER")
        print("-" * 60)

        press_home_key(serial)
        if not scan_open_input_field(d, serial):
            save_step_screenshot(d, "step4_search_not_opened", SCRIPT_IMG_DIR)
            self.fail("Step 4 Failed: could not open the launcher Search input field")
        scan_clear_input_field(d)
        run_adb_cmd(serial, f"shell input text {PROBE_TEXT}", log_print=False)
        time.sleep(1)
        # Capture the pre-press focus state: a real ENTER submission dismisses the keyboard and
        # unfocuses the field, whereas a no-op HOME (already on the home/search screen) would not.
        edit_focused_before = d(focused=True, className="android.widget.EditText").exists(timeout=1)

        keyremap_tap_navbar_home(serial)
        time.sleep(1)

        content_after = scan_get_input_field_text(d)
        # Pressing ENTER can submit the search and navigate to a results page where the query
        # is shown as a static text node rather than a focused/EditText widget, so fall back
        # to a screen-wide text search before declaring the probe text lost.
        if PROBE_TEXT.lower() not in content_after.lower() and not d(textContains=PROBE_TEXT).exists(timeout=2):
            save_step_screenshot(d, "step4_probe_text_lost", SCRIPT_IMG_DIR)
            self.fail(
                f"Step 4 Failed: expected '{PROBE_TEXT}' to remain in Search after the remapped "
                f"HOME (ENTER) key, got '{content_after}'"
            )

        keyboard_dismissed = not d(focused=True, className="android.widget.EditText").exists(timeout=2)
        save_step_screenshot(d, "step4_enter_behavior_checked", SCRIPT_IMG_DIR)
        print(f"  Search field content after HOME: '{content_after}' (keyboard dismissed: {keyboard_dismissed})")

        # If the field was focused before the key press, the remapped ENTER must dismiss the
        # keyboard/lose focus; otherwise HOME likely behaved as a plain, no-op HOME press.
        if edit_focused_before and not keyboard_dismissed:
            self.fail(
                "Step 4 Failed: the remapped HOME key did not submit the search - the Search "
                "field is still focused/keyboard still shown, suggesting HOME was not mapped to ENTER"
            )
        print("  ✓ Step 4 passed")

        print("\n[L3_Keyremap] All steps passed ✓")


if __name__ == "__main__":
    unittest.main()
