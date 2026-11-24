# -*- coding: utf-8 -*-
# __author__ = 'sophy_H400818'

"""
Test case: L2 Key Remap - APP_SWITCH -> TEXT ("TEST") (ANDROIDCN-35035)
Test key remap functionality via Settings --> Honeywell Settings --> Keyremap

Steps:
1. Open Settings --> Honeywell Settings --> Keyremap --> tap '+' -->
   select App Switch (virtual icon in the key-capture dialog) --> click OK -->
   find and tap "TEXT" in the target list --> tap the string editor
   (resourceId com.honeywell.keyremap2:id/et_string) --> type "T,E,S,T" --> click OK.
2. Return to the Home (launcher) screen, tap the Google search box, then press
   the App Switch key on the device (remapped key).
3. Confirm the search input receives "TEST".
4. Remap the same key to "CTRL_LEFT,A" and verify the typed text gets selected.
5. Remap the same key to "A,VOLUME_UP" and verify each press types 'a' and raises the volume.

Author: auto_test
Date: 2026-09-01
"""

import time
import unittest
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from common.adb_common import (
    get_device_serial,
    keyremap_click_virtual_appswitch,
    keyremap_force_stop_honeywell_settings,
    keyremap_get_stream_volume_index,
    keyremap_is_on_home_screen,
    keyremap_set_stream_volume_index,
    keyremap_tap_navbar_appswitch,
    press_home_key,
    run_adb_cmd,
    save_step_screenshot,

)
from common.common_method import (
    close_settings_app,
    get_case_config,
    get_package_name,
    keyremap_clear_all,
    keyremap_dialog_is_open,
    keyremap_find_text_center,
    keyremap_input_text_value,
    keyremap_is_text_selection_active,
    keyremap_open_page,
    keyremap_read_edit_text,
    keyremap_tap_add_button,
    keyremap_tap_ok_button,
    keyremap_tap_text,
    scan_clear_input_field,
    scan_get_input_field_text,
    scan_open_input_field,
)
import uiautomator2 as u2

# ── Device connection ─────────────────────────────────────────────────────────
serial = get_device_serial()
if not serial:
    print("Error: No Android device found. Connect a device or set ANDROID_SERIAL.")
    sys.exit(1)

d = u2.connect(serial)

SCRIPT_BASENAME = os.path.splitext(os.path.basename(__file__))[0]
IMG_ROOT = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.realpath(__file__)))),
    "img"
)
SCRIPT_IMG_DIR = os.path.join(IMG_ROOT, SCRIPT_BASENAME)
os.makedirs(SCRIPT_IMG_DIR, exist_ok=True)

SETTINGS_PKG = get_package_name("settings")
KEYREMAP_PKG = get_package_name("keyremap")

CASE_CONFIG_SECTION = "keyremap_text_case"
REMAP_TEXT_INPUT = get_case_config(CASE_CONFIG_SECTION, "remap_text_input")
EXPECTED_TEXT = get_case_config(CASE_CONFIG_SECTION, "expected_text")
SELECT_ALL_INPUT = get_case_config(CASE_CONFIG_SECTION, "select_all_input")
PROBE_TEXT = get_case_config(CASE_CONFIG_SECTION, "probe_text")
TEXT_AND_VOLUME_INPUT = get_case_config(CASE_CONFIG_SECTION, "text_and_volume_input")
STEP5_PRESS_COUNT = int(get_case_config(CASE_CONFIG_SECTION, "step5_press_count"))
VOLUME_STREAMS = tuple(get_case_config(CASE_CONFIG_SECTION, "volume_streams").split(","))
VOLUME_STREAM_NAME = get_case_config(CASE_CONFIG_SECTION, "volume_stream_name")
DEFAULT_VOLUME_INDEX = int(get_case_config(CASE_CONFIG_SECTION, "default_volume_index"))


# ── Test class ────────────────────────────────────────────────────────────────

class TestKeyremapAppSwitchToText(unittest.TestCase):
    """L2 test for Honeywell Keyremap: APP_SWITCH remapped to the TEXT string "TEST"."""

    @classmethod
    def setUpClass(cls):
        cls.dev_id = serial
        print(f"\n[Setup] Device: {cls.dev_id}")

    def setUp(self):
        print(f"\n{'='*60}\nTest: {self.id()}\n{'='*60}")
        d.press("home")
        time.sleep(1)

    def tearDown(self):
        # leave the search input if it is still open
        d.press("back")
        time.sleep(1)

        # clear the remap so the device is clean for the next run
        if keyremap_open_page(d, serial, SETTINGS_PKG, KEYREMAP_PKG):
            keyremap_clear_all(d, serial)

            # return to the parent page after clearing
            run_adb_cmd(serial, "shell input keyevent KEYCODE_BACK", log_print=False)
            time.sleep(1)

        pid_raw = run_adb_cmd(serial, f"shell pidof {KEYREMAP_PKG}", log_print=False)
        pid_str = (pid_raw.decode("utf-8", errors="ignore") if isinstance(pid_raw, bytes) else str(pid_raw)).strip()
        if pid_str and pid_str.isdigit():
            run_adb_cmd(serial, f"shell kill {pid_str}", log_print=False)

        # force-stop honeywell settings app
        keyremap_force_stop_honeywell_settings(serial)

        # clear the settings app to ensure a clean state
        close_settings_app(serial)

        d.screen_on()
        d.press("home")
        time.sleep(1)
        print(f"[TearDown] Completed: {self.id()}")

    def test_keyremap_appswitch_to_text(self):
        """
        L2 Keyremap end-to-end test: APP_SWITCH -> TEXT ("TEST").

        Step 1: Open Keyremap page → tap '+' → dialog appears →
                click App Switch virtual icon → click OK → target list opens →
                scroll until "TEXT" is visible → tap it → type "T,E,S,T"
                into the et_string editor → click OK → verify entry saved.
        Step 2: Return to the Home screen, tap the Google search box, then
                press the App Switch key on the device (remapped key).
        Step 3: Verify the search input contains "TEST" → Pass.
        Step 4: Reopen Keyremap → open the "User Text" entry → "TEXT" → input
                "CTRL_LEFT,A" → OK → back on the Home search box, type any text and
                press the App Switch key → verify the typed text becomes fully selected.
        Step 5: Reopen Keyremap → "User Text" → "TEXT" → input "A,VOLUME_UP" → OK →
                in the search box press the App Switch key N times → verify N 'a' characters
                are typed and the volume keeps increasing.
        """
        print("\n[L2_Keyremap] Testing APP_SWITCH -> TEXT Remap\n" + "="*60)

        # ── Step 1 ────────────────────────────────────────────────────────────
        print(f"\n[Step 1/5] Keyremap: '+' → App Switch → OK → 'TEXT' → input '{REMAP_TEXT_INPUT}' → OK")
        print("-"*60)

        if not keyremap_open_page(d, serial, SETTINGS_PKG, KEYREMAP_PKG):
            save_step_screenshot(d, "step1_nav_failed", SCRIPT_IMG_DIR)
            self.fail("Step 1 Failed: Could not navigate to Keyremap page")

        save_step_screenshot(d, "step1_keyremap_page", SCRIPT_IMG_DIR)
        print("  ✓ Keyremap page opened")

        keyremap_tap_add_button(d, serial)
        if not keyremap_dialog_is_open(d):
            save_step_screenshot(d, "step1_dialog_not_opened", SCRIPT_IMG_DIR)
            self.fail("Step 1 Failed: '+' button did not open the key-capture dialog")

        save_step_screenshot(d, "step1_dialog_opened", SCRIPT_IMG_DIR)
        print("  ✓ 'Please press the key to be mapped' dialog opened")

        # Click App Switch virtual icon as surrogate for physical scan button
        keyremap_click_virtual_appswitch(serial)
        time.sleep(1)

        keyremap_tap_ok_button(d, serial)

        if not keyremap_tap_text(d, serial, "TEXT", contains=False, max_swipes=10):
            save_step_screenshot(d, "step1_text_not_found", SCRIPT_IMG_DIR)
            self.fail("Step 1 Failed: 'TEXT' not found in target list after scrolling")
        time.sleep(2)

        if not keyremap_input_text_value(d, KEYREMAP_PKG, REMAP_TEXT_INPUT):
            save_step_screenshot(d, "step1_editor_not_found", SCRIPT_IMG_DIR)
            self.fail("Step 1 Failed: Could not find the TEXT string editor (et_string)")

        save_step_screenshot(d, "step1_text_entered", SCRIPT_IMG_DIR)
        print(f"  ✓ '{REMAP_TEXT_INPUT}' entered into the string editor")

        if not keyremap_tap_ok_button(d, serial):
            save_step_screenshot(d, "step1_ok_not_found", SCRIPT_IMG_DIR)
            self.fail("Step 1 Failed: Could not tap OK after entering the text")

        save_step_screenshot(d, "step1_remap_saved", SCRIPT_IMG_DIR)
        print(f"  ✓ Remap entry saved: APP_SWITCH → TEXT '{REMAP_TEXT_INPUT}'")
        print("  ✓ Step 1 passed")

        # ── Step 2 ────────────────────────────────────────────────────────────
        print("\n[Step 2/5] Return to Home screen, open Google search, press the App Switch key")
        print("-"*60)

        press_home_key(serial)
        is_on_home, last_focus = keyremap_is_on_home_screen(serial)

        if not is_on_home:
            save_step_screenshot(d, "step2_not_on_home", SCRIPT_IMG_DIR)
            self.fail(f"Step 2 Failed: could not return to the Home screen (last focus={last_focus})")

        save_step_screenshot(d, "step2_on_home", SCRIPT_IMG_DIR)
        print("  ✓ Returned to the Home screen")

        if not scan_open_input_field(d, serial):
            save_step_screenshot(d, "step2_search_not_opened", SCRIPT_IMG_DIR)
            self.fail("Step 2 Failed: Could not open the Google search input field")

        save_step_screenshot(d, "step2_search_opened", SCRIPT_IMG_DIR)
        print("  ✓ Google search input field is focused")

        keyremap_tap_navbar_appswitch(serial)
        time.sleep(2)
        save_step_screenshot(d, "step2_appswitch_pressed", SCRIPT_IMG_DIR)
        print("  ✓ Step 2 passed")

        # ── Step 3 ────────────────────────────────────────────────────────────
        print(f"\n[Step 3/5] Verify the search input received '{EXPECTED_TEXT}'")
        print("-"*60)

        typed_text = keyremap_read_edit_text(d)
        print(f"  Input field content: '{typed_text}'")

        if EXPECTED_TEXT.lower() not in typed_text.lower():
            save_step_screenshot(d, "step3_text_not_typed", SCRIPT_IMG_DIR)
            self.fail(
                f"Step 3 Failed: expected '{EXPECTED_TEXT}' in the input field after the "
                f"remapped APP_SWITCH key, got '{typed_text}'"
            )

        save_step_screenshot(d, "step3_text_typed", SCRIPT_IMG_DIR)
        print(f"  ✓ '{EXPECTED_TEXT}' was typed by the remapped APP_SWITCH key")
        print("  ✓ Step 3 passed")

        # ── Step 4 ──────────────────────────────────────────────────────────────────
        print(f"\n[Step 4/5] Reopen Keyremap → 'User Text' → 'TEXT' → input '{SELECT_ALL_INPUT}' → OK")
        print("-"*60)

        if not keyremap_open_page(d, serial, SETTINGS_PKG, KEYREMAP_PKG):
            save_step_screenshot(d, "step4_nav_failed", SCRIPT_IMG_DIR)
            self.fail("Step 4 Failed: Could not navigate back to the Keyremap page")

        save_step_screenshot(d, "step4_keyremap_page", SCRIPT_IMG_DIR)

        if not keyremap_tap_text(d, serial, "User Text", contains=True, max_swipes=10):
            save_step_screenshot(d, "step4_user_text_not_found", SCRIPT_IMG_DIR)
            self.fail("Step 4 Failed: 'User Text' entry not found in the Keyremap list")
        time.sleep(2)

        if not keyremap_tap_text(d, serial, "TEXT", contains=False, max_swipes=10):
            save_step_screenshot(d, "step4_text_not_found", SCRIPT_IMG_DIR)
            self.fail("Step 4 Failed: 'TEXT' not found after opening 'User Text'")
        time.sleep(2)

        if not keyremap_input_text_value(d, KEYREMAP_PKG, SELECT_ALL_INPUT):
            save_step_screenshot(d, "step4_editor_not_found", SCRIPT_IMG_DIR)
            self.fail("Step 4 Failed: Could not find the TEXT string editor (et_string)")

        if not keyremap_tap_ok_button(d, serial):
            save_step_screenshot(d, "step4_ok_not_found", SCRIPT_IMG_DIR)
            self.fail("Step 4 Failed: Could not tap OK after entering the shortcut")

        save_step_screenshot(d, "step4_remap_saved", SCRIPT_IMG_DIR)
        print(f"  ✓ Remap entry updated: APP_SWITCH → TEXT '{SELECT_ALL_INPUT}'")

        press_home_key(serial)
        is_on_home, last_focus = keyremap_is_on_home_screen(serial)
        if not is_on_home:
            save_step_screenshot(d, "step4_not_on_home", SCRIPT_IMG_DIR)
            self.fail(f"Step 4 Failed: could not return to the Home screen (last focus={last_focus})")

        if not scan_open_input_field(d, serial):
            save_step_screenshot(d, "step4_search_not_opened", SCRIPT_IMG_DIR)
            self.fail("Step 4 Failed: Could not open the Google search input field")

        run_adb_cmd(serial, f"shell input text {PROBE_TEXT}", log_print=False)
        time.sleep(2)
        save_step_screenshot(d, "step4_probe_text_typed", SCRIPT_IMG_DIR)
        print(f"  ✓ '{PROBE_TEXT}' typed into the search field")

        keyremap_tap_navbar_appswitch(serial)
        time.sleep(2)
        save_step_screenshot(d, "step4_appswitch_pressed", SCRIPT_IMG_DIR)

        selected, content_after = keyremap_is_text_selection_active(d, serial, PROBE_TEXT)
        print(f"  Field content after typing one character: '{content_after}'")

        if not selected:
            save_step_screenshot(d, "step4_text_not_selected", SCRIPT_IMG_DIR)
            self.fail(
                "Step 4 Failed: the search field content was not selected after the remapped "
                f"APP_SWITCH key sent '{SELECT_ALL_INPUT}' (content='{content_after}', expected a single character)"
            )

        save_step_screenshot(d, "step4_text_selected", SCRIPT_IMG_DIR)
        print("  ✓ Search field content is fully selected")
        print("  ✓ Step 4 passed")

        # ── Step 5 ──────────────────────────────────────────────────────────────────
        print(f"\n[Step 5/5] Reopen Keyremap → 'User Text' → 'TEXT' → input '{TEXT_AND_VOLUME_INPUT}' → OK")
        print("-"*60)

        if not keyremap_open_page(d, serial, SETTINGS_PKG, KEYREMAP_PKG):
            save_step_screenshot(d, "step5_nav_failed", SCRIPT_IMG_DIR)
            self.fail("Step 5 Failed: Could not navigate back to the Keyremap page")

        if not keyremap_tap_text(d, serial, "User Text", contains=True, max_swipes=10):
            save_step_screenshot(d, "step5_user_text_not_found", SCRIPT_IMG_DIR)
            self.fail("Step 5 Failed: 'User Text' entry not found in the Keyremap list")
        time.sleep(2)

        if not keyremap_tap_text(d, serial, "TEXT", contains=False, max_swipes=10):
            save_step_screenshot(d, "step5_text_not_found", SCRIPT_IMG_DIR)
            self.fail("Step 5 Failed: 'TEXT' not found after opening 'User Text'")
        time.sleep(2)

        if not keyremap_input_text_value(d, KEYREMAP_PKG, TEXT_AND_VOLUME_INPUT):
            save_step_screenshot(d, "step5_editor_not_found", SCRIPT_IMG_DIR)
            self.fail("Step 5 Failed: Could not find the TEXT string editor (et_string)")

        if not keyremap_tap_ok_button(d, serial):
            save_step_screenshot(d, "step5_ok_not_found", SCRIPT_IMG_DIR)
            self.fail("Step 5 Failed: Could not tap OK after entering the combined sequence")

        save_step_screenshot(d, "step5_remap_saved", SCRIPT_IMG_DIR)
        print(f"  ✓ Remap entry updated: APP_SWITCH → TEXT '{TEXT_AND_VOLUME_INPUT}'")

        press_home_key(serial)
        is_on_home, last_focus = keyremap_is_on_home_screen(serial)
        if not is_on_home:
            save_step_screenshot(d, "step5_not_on_home", SCRIPT_IMG_DIR)
            self.fail(f"Step 5 Failed: could not return to the Home screen (last focus={last_focus})")

        if not scan_open_input_field(d, serial):
            save_step_screenshot(d, "step5_search_not_opened", SCRIPT_IMG_DIR)
            self.fail("Step 5 Failed: Could not open the Google search input field")

        scan_clear_input_field(d)
        time.sleep(1)

        keyremap_set_stream_volume_index(serial, DEFAULT_VOLUME_INDEX, stream_name=VOLUME_STREAM_NAME)
        print(f"  Volume reset to index {DEFAULT_VOLUME_INDEX} on stream {VOLUME_STREAM_NAME}")

        volumes_before = {name: keyremap_get_stream_volume_index(serial, name) for name in VOLUME_STREAMS}
        print(f"  Volume before: {volumes_before}")

        # The volume only steps up when the presses come in quick succession, so avoid per-press UI reads.
        for press_index in range(1, STEP5_PRESS_COUNT + 1):
            keyremap_tap_navbar_appswitch(serial, wait=0.2)

        time.sleep(2)
        typed = keyremap_read_edit_text(d)
        save_step_screenshot(d, "step5_after_presses", SCRIPT_IMG_DIR)
        print(f"  Field content after {STEP5_PRESS_COUNT} presses: '{typed}'")

        if typed.lower().count("a") != STEP5_PRESS_COUNT:
            save_step_screenshot(d, "step5_text_mismatch", SCRIPT_IMG_DIR)
            self.fail(
                f"Step 5 Failed: after {STEP5_PRESS_COUNT} press(es) the field should contain "
                f"{STEP5_PRESS_COUNT} 'a' character(s), got '{typed}'"
            )

        volumes_after = {name: keyremap_get_stream_volume_index(serial, name) for name in VOLUME_STREAMS}
        raised = [
            name
            for name in VOLUME_STREAMS
            if volumes_before.get(name) is not None
            and volumes_after.get(name) is not None
            and volumes_after[name] > volumes_before[name]
        ]
        print(f"  Volume after: {volumes_after}, raised streams: {raised or 'none'}")

        if not raised:
            save_step_screenshot(d, "step5_volume_not_raised", SCRIPT_IMG_DIR)
            self.fail(
                "Step 5 Failed: no audio stream volume increased after the remapped APP_SWITCH key sent "
                f"'{TEXT_AND_VOLUME_INPUT}' (before={volumes_before}, after={volumes_after})"
            )

        save_step_screenshot(d, "step5_text_and_volume_verified", SCRIPT_IMG_DIR)
        print(f"  ✓ {STEP5_PRESS_COUNT} presses typed {STEP5_PRESS_COUNT} 'a' and raised the volume")
        print("  ✓ Step 5 passed")

        print("\n[L2_Keyremap] All steps passed ✓")


if __name__ == "__main__":
    unittest.main()
