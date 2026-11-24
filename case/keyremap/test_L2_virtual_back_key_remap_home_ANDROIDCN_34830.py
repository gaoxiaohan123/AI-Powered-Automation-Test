# -*- coding: utf-8 -*-
# __author__ = 'sophy_H400818'

"""
Test case: L2 Key Remap - BACK -> HOME (ANDROIDCN-34830)
Test key remap functionality via Settings --> Honeywell Settings --> Keyremap

Steps:
1. Open Settings --> Honeywell Settings --> Keyremap --> tap '+' -->
   select Back (virtual icon in the key-capture dialog) --> click OK -->
   select "HOME" in the target list --> click it.
2. Press the Back key on the device (remapped key).
3. Confirm the device navigates to the Home (launcher) screen. If so, the
   test passes.

Author: auto_test
Date: 2026-08-28
"""

import time
import unittest
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from common.adb_common import (
    get_device_serial,
    keyremap_click_virtual_back,
    keyremap_force_stop_honeywell_settings,
    keyremap_is_on_home_screen,
    keyremap_tap_navbar_back,
    run_adb_cmd,
    save_step_screenshot,

)
from common.common_method import (
    close_settings_app,
    get_package_name,
    keyremap_clear_all,
    keyremap_dialog_is_open,
    keyremap_find_text_center,
    keyremap_open_page,
    keyremap_select_home_target,
    keyremap_tap_add_button,
    keyremap_tap_ok_button,
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


# ── Test class ────────────────────────────────────────────────────────────────

class TestKeyremapBackToHome(unittest.TestCase):
    """L2 test for Honeywell Keyremap: BACK remapped to HOME."""

    @classmethod
    def setUpClass(cls):
        cls.dev_id = serial
        print(f"\n[Setup] Device: {cls.dev_id}")

    def setUp(self):
        print(f"\n{'='*60}\nTest: {self.id()}\n{'='*60}")
        d.press("home")
        time.sleep(1)

    def tearDown(self):
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

    def test_keyremap_back_to_home(self):
        """
        L2 Keyremap end-to-end test: BACK -> HOME.

        Step 1: Open Keyremap page → tap '+' → dialog appears →
                click Back virtual icon → key captured →
                click OK → target list opens → select "HOME" → verify
                entry saved.
        Step 2: Press the Back key on the device (remapped key).
        Step 3: Verify the device navigates to the Home (launcher)
                screen → Pass.
        """
        print("\n[L2_Keyremap] Testing BACK -> HOME Remap\n" + "="*60)

        # ── Step 1 ────────────────────────────────────────────────────────────
        print("\n[Step 1/3] Keyremap: '+' → Back → OK → select 'HOME'")
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

        # Click Back virtual icon as surrogate for physical scan button
        keyremap_click_virtual_back(serial)
        time.sleep(1)

        keyremap_tap_ok_button(d, serial)
        if keyremap_find_text_center(d, "HOME", contains=False) is None:
            save_step_screenshot(d, "step1_target_list_not_found", SCRIPT_IMG_DIR)
            self.fail("Step 1 Failed: Remap target list did not open after clicking OK")

        if not keyremap_select_home_target(d, serial):
            save_step_screenshot(d, "step1_home_not_found", SCRIPT_IMG_DIR)
            self.fail("Step 1 Failed: 'HOME' not found in target list")

        if keyremap_find_text_center(d, "HOME", contains=False) is None:
            save_step_screenshot(d, "step1_entry_not_confirmed", SCRIPT_IMG_DIR)
            self.fail("Step 1 Failed: 'HOME' not shown in Keyremap list after saving")

        save_step_screenshot(d, "step1_remap_saved", SCRIPT_IMG_DIR)
        print("  ✓ Remap entry saved: BACK → HOME")
        print("  ✓ Step 1 passed")

        # ── Step 2 ────────────────────────────────────────────────────────────
        print("\n[Step 2/3] Press the Back key on the device")
        print("-"*60)

        keyremap_tap_navbar_back(serial)
        time.sleep(1)
        save_step_screenshot(d, "step2_back_pressed", SCRIPT_IMG_DIR)
        print("  ✓ Step 2 passed")

        # ── Step 3 ────────────────────────────────────────────────────────────
        print("\n[Step 3/3] Verify the device navigated to the Home screen")
        print("-"*60)

        is_on_home, last_focus = keyremap_is_on_home_screen(serial)
        print(f"  On home screen: {is_on_home}, last focus: {last_focus}")

        if not is_on_home:
            save_step_screenshot(d, "step3_not_home", SCRIPT_IMG_DIR)
            self.fail(
                "Step 3 Failed: device did not navigate to the Home screen "
                f"after remapped BACK (last focus={last_focus})"
            )

        save_step_screenshot(d, "step3_on_home", SCRIPT_IMG_DIR)
        print("  ✓ Device is on the Home screen")
        print("  ✓ Step 3 passed")
        print("\n[L2_Keyremap] All steps passed ✓")

if __name__ == "__main__":
    unittest.main()
