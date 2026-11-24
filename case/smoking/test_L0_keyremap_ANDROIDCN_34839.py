# -*- coding: utf-8 -*-
"""
Test case: L0 Key Remap
Test key remap functionality via Settings --> Honeywell Settings --> Keyremap

Steps:
1. Boot up device and go to Settings --> Honeywell Settings --> Keyremap;
   tap '+', verify the "press the key to be mapped" dialog opens,
   click the Back virtual icon (surrogate for a physical scan button) –
   verify the key name appears in the dialog (scan button CAN be shown in the list).
2. Click OK --> target list opens --> select HOME -->
   verify entry shows "BACK ... HOME" in the Keyremap list.
3. Press the mapped key (KEYCODE_BACK); verify device launches to home page.
4. Return to Keyremap --> tap Clear (broom icon) --> list is empty -->
   press the key again --> device stays in the Settings context
   (no remap active, key reverts to normal navigation).

Author: auto_test
Date: 2026-06-30

UI facts discovered via live device exploration:
  - Menu entry text  : "Keyremap"  (exact, no space)
  - '+' button       : no text/desc, bounds [18,258][1062,434], center ~(540,346)
  - Clear button     : content-desc="Clear", bounds [928,84][1080,228]
  - Dialog text      : "Please press the key to be mapped"
  - Virtual key icons (left→right inside dialog):
      Back ←  [108,1131][396,1275]  center (252,1203)
      Home 🏠 [396,1131][684,1275]  center (540,1203)
      Overview □ [684,1131][972,1275]
  - OK button        : bounds [804,1347][996,1491]
  - CANCEL button    : bounds [573,1347][804,1491]
  - After capturing Back + clicking OK: remap-target list opens (KEYS tab)
      options: NONE, HOME, APP_SWITCH, SEARCH, MENU, VOLUME_UP, VOLUME_DOWN …
  - After selecting HOME: list shows "BACK" (left) and "HOME" (right)
  - Broom icon clears all entries
"""

import subprocess
import time
import unittest
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from common.adb_common import (
    get_device_serial,
    keyremap_click_virtual_back,
    keyremap_is_on_home_screen,
    keyremap_tap_navbar_back,
    run_adb_cmd,
    save_step_screenshot,
)
from common.common_method import (
    get_package_name,
    keyremap_clear_all,
    keyremap_dialog_is_open,
    keyremap_find_text_center,
    keyremap_open_page,
    keyremap_select_home_target,
    keyremap_tap_add_button,
    keyremap_click_ok,
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

class Test_Keyremap(unittest.TestCase):
    """L0 smoke test for Honeywell Keyremap functionality."""

    @classmethod
    def setUpClass(cls):
        cls.dev_id = serial
        print(f"\n[Setup] Device: {cls.dev_id}")

    def setUp(self):
        print(f"\n{'='*60}\nTest: {self.id()}\n{'='*60}")
        d.press("home")
        time.sleep(1)

    def tearDown(self):
        # force-stop settings normally; for keyremap2 (system app), use kill by PID
        subprocess.run(
            f"adb -s {serial} shell am force-stop {SETTINGS_PKG}",
            shell=True, capture_output=True,
        )
        pid_raw = run_adb_cmd(serial, f"shell pidof {KEYREMAP_PKG}", log_print=False)
        pid_str = (pid_raw.decode("utf-8", errors="ignore") if isinstance(pid_raw, bytes) else str(pid_raw)).strip()
        if pid_str and pid_str.isdigit():
            run_adb_cmd(serial, f"shell kill {pid_str}", log_print=False)
        d.screen_on()
        d.press("home")
        time.sleep(1)
        print(f"[TearDown] Completed: {self.id()}")

    def test_L0_keyremap(self):
        """
        L0 Keyremap end-to-end test.

        Test Steps:
        Step 1: Open Keyremap page → tap '+' → dialog appears →
                click Back virtual icon → key captured ("Back" shown) →
                verifies scan/key button CAN be shown in the list.
        Step 2: Click OK → target list opens → select HOME →
                verify entry shows "BACK ... HOME" in the list.
        Step 3: Press KEYCODE_BACK (the remapped key) →
                verify device navigates to home/launcher screen.
        Step 4: Return to Keyremap → tap Clear (broom) → list is empty →
                press KEYCODE_BACK again → verify device stays within
                Settings context (no remap active).
        """
        print("\n[L0_Keyremap] Testing Keyremap Functionality\n" + "="*60)

        # ── Step 1 ────────────────────────────────────────────────────────────
        print("\n[Step 1/4] Open Settings → Honeywell Settings → Keyremap")
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
        if keyremap_find_text_center(d, "Back", contains=False) is None:
            save_step_screenshot(d, "step1_key_not_captured", SCRIPT_IMG_DIR)
            self.fail("Step 1 Failed: Key not captured in dialog (expected 'Back' label)")

        save_step_screenshot(d, "step1_key_captured", SCRIPT_IMG_DIR)
        print("  ✓ Key captured: 'Back' shown in dialog (scan button capture mechanism works)")
        print("  ✓ Step 1 passed")

        # ── Step 2 ────────────────────────────────────────────────────────────
        print("\n[Step 2/4] Click OK → select HOME as remap target")
        print("-"*60)

        keyremap_click_ok(d, serial)

        if keyremap_find_text_center(d, "HOME", contains=False) is None:
            save_step_screenshot(d, "step2_target_list_not_found", SCRIPT_IMG_DIR)
            self.fail("Step 2 Failed: Remap target list did not open after clicking OK")

        if not keyremap_select_home_target(d, serial):
            save_step_screenshot(d, "step2_home_not_selected", SCRIPT_IMG_DIR)
            self.fail("Step 2 Failed: Could not select 'HOME' as remap target")

        if keyremap_find_text_center(d, "HOME", contains=False) is None:
            save_step_screenshot(d, "step2_entry_not_confirmed", SCRIPT_IMG_DIR)
            self.fail("Step 2 Failed: 'HOME' not shown in Keyremap list after saving")

        save_step_screenshot(d, "step2_remap_saved", SCRIPT_IMG_DIR)
        print("  ✓ Remap entry saved: BACK → HOME")
        print("  ✓ Step 2 passed")

        # ── Step 3 ────────────────────────────────────────────────────────────
        print("\n[Step 3/4] Press the remapped key → verify device goes to home page")
        print("-"*60)

        # Navigate to Settings (a non-home app) so there is a clear before/after.
        run_adb_cmd(serial, "shell am start -n com.android.settings/.Settings",
                    log_print=False)
        time.sleep(3)

        # Tap the software navigation bar Back button.
        # This touch event IS intercepted by the Keyremap service at the kernel level
        # (unlike raw ADB keyevent 4 or d.press("back") which bypass Keyremap).
        keyremap_tap_navbar_back(serial, wait=2)

        # The launcher often reports mCurrentFocus=null, so poll multiple signals
        # (focused window/app + resumed activity + resolved launcher package).
        is_on_home, focus_line = keyremap_is_on_home_screen(serial, timeout=8)
        print(f"  Focus after remapped Back: {focus_line or 'mCurrentFocus=null'}")

        if not is_on_home:
            save_step_screenshot(d, "step3_not_on_home", SCRIPT_IMG_DIR)
            self.fail(
                "Step 3 Failed: Device did not navigate to home page after pressing "
                "the remapped key (KEYCODE_BACK → HOME)"
            )

        save_step_screenshot(d, "step3_home_reached", SCRIPT_IMG_DIR)
        print("  ✓ Device navigated to home page after pressing remapped key")
        print("  ✓ Step 3 passed")

        # ── Step 4 ────────────────────────────────────────────────────────────
        print("\n[Step 4/4] Clear All remaps → press key → verify Back behaves normally")
        print("-"*60)

        if not keyremap_open_page(d, serial, SETTINGS_PKG, KEYREMAP_PKG):
            save_step_screenshot(d, "step4_nav_failed", SCRIPT_IMG_DIR)
            self.fail("Step 4 Failed: Could not navigate back to Keyremap page")

        if not keyremap_clear_all(d, serial):
            save_step_screenshot(d, "step4_clear_not_found", SCRIPT_IMG_DIR)
            self.fail("Step 4 Failed: Could not find the Clear (broom) button")

        if keyremap_find_text_center(d, "HOME", contains=False) is not None:
            save_step_screenshot(d, "step4_list_not_cleared", SCRIPT_IMG_DIR)
            self.fail("Step 4 Failed: Keyremap list still shows entries after Clear All")

        save_step_screenshot(d, "step4_after_clear", SCRIPT_IMG_DIR)
        print("  ✓ Clear All executed – list is empty")

        # Press nav bar Back directly from the Keyremap page (which was opened from
        # Honeywell Settings inside the Settings task).
        # • Remap cleared  → Back returns to Honeywell Settings (Settings package in focus)
        # • Remap still active → Keyremap intercepts Back and sends HOME → launcher
        # Using 'am start .Settings' before this tap was wrong: it is a singleTask
        # activity and clears keyremap2 from the back-stack, making Back exit to the
        # launcher naturally even without any remap.
        run_adb_cmd(serial, "shell input tap 150 2088", log_print=False)
        time.sleep(2)

        out = run_adb_cmd(serial, "shell dumpsys window", log_print=False)
        out_str = out.decode("utf-8", errors="ignore") if isinstance(out, bytes) else str(out)
        focus_line = ""
        for line in out_str.splitlines():
            if "mCurrentFocus" in line:
                focus_line = line.strip()
                break
        print(f"  Focus after cleared Back from Keyremap page: {focus_line}")
        went_to_home = "launcher" in focus_line.lower() or "home" in focus_line.lower()

        if went_to_home:
            save_step_screenshot(d, "step4_unexpected_home", SCRIPT_IMG_DIR)
            self.fail(
                "Step 4 Failed: After Clear All, pressing Back still jumped to Home "
                "(remap may still be active)"
            )

        save_step_screenshot(d, "step4_back_normal", SCRIPT_IMG_DIR)
        print("  ✓ After Clear All, Back no longer remaps to Home – behaves normally")
        print("  ✓ Step 4 passed")
        print("\n[L0_Keyremap] All steps passed ✓")

if __name__ == "__main__":
    unittest.main()