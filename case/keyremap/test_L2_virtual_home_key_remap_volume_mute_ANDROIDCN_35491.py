# -*- coding: utf-8 -*-
# __author__ = 'sophy_H400818'

"""
Test case: L2 Key Remap - HOME -> VOLUME_MUTE
Test key remap functionality via Settings --> Honeywell Settings --> Keyremap

Steps:
1. Open Settings --> Honeywell Settings --> Keyremap --> tap '+' -->
   select Home (virtual icon in the key-capture dialog) --> click OK -->
   scroll the target list until "VOLUME_MUTE" is visible --> click it.
2. Press the Home key on the device (remapped key).
3. Run `adb shell cmd media_session volume --stream 3 --get` and confirm the
   reported volume is 0 (device muted). If so, the test passes.

Author: auto_test
Date: 2026-08-28
"""

import subprocess
import time
import unittest
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from common.adb_common import (
    get_device_serial,
    keyremap_click_virtual_home,
    keyremap_force_stop_honeywell_settings,
    keyremap_is_media_volume_zero_by_media_session,
    keyremap_tap_navbar_home,
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
    keyremap_tap_add_button,
    keyremap_tap_ok_button,
    keyremap_tap_text,
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

class TestKeyremapHomeToVolumeMute(unittest.TestCase):
    """L2 test for Honeywell Keyremap: HOME remapped to VOLUME_MUTE."""

    @classmethod
    def setUpClass(cls):
        cls.dev_id = serial
        print(f"\n[Setup] Device: {cls.dev_id}")

    def setUp(self):
        print(f"\n{'='*60}\nTest: {self.id()}\n{'='*60}")
        d.press("home")
        time.sleep(1)

    def tearDown(self):
        # restore volume and clear the remap so the device is clean for the next run
        run_adb_cmd(serial, "shell input keyevent KEYCODE_VOLUME_MUTE", log_print=False)
        if keyremap_open_page(d, serial, SETTINGS_PKG, KEYREMAP_PKG):
            keyremap_clear_all(d, serial)

            # return to the parent page after clearing
            run_adb_cmd(serial, "shell input keyevent KEYCODE_BACK", log_print=False)
            time.sleep(1)

        # fore-stop honeywell settings app
        keyremap_force_stop_honeywell_settings(serial)

        # clear the settings app to ensure a clean state
        close_settings_app(serial)

        pid_raw = run_adb_cmd(serial, f"shell pidof {KEYREMAP_PKG}", log_print=False)
        pid_str = (pid_raw.decode("utf-8", errors="ignore") if isinstance(pid_raw, bytes) else str(pid_raw)).strip()
        if pid_str and pid_str.isdigit():
            run_adb_cmd(serial, f"shell kill {pid_str}", log_print=False)
        d.screen_on()
        d.press("home")
        time.sleep(1)
        print(f"[TearDown] Completed: {self.id()}")

    def test_keyremap_home_to_volume_mute(self):
        """
        L2 Keyremap end-to-end test: HOME -> VOLUME_MUTE.

        Step 1: Open Keyremap page → tap '+' → dialog appears →
                click Home virtual icon → key captured →
                click OK → target list opens → scroll until "VOLUME_MUTE"
                is visible → tap it → verify entry saved.
        Step 2: Press the Home key on the device (remapped key).
        Step 3: Run `adb shell cmd media_session volume --stream 3 --get` and
                verify the reported volume is 0 (device muted) → Pass.
        """
        print("\n[L2_Keyremap] Testing HOME -> VOLUME_MUTE Remap\n" + "="*60)

        # ── Step 1 ────────────────────────────────────────────────────────────
        print("\n[Step 1/3] Keyremap: '+' → Home → OK → scroll to find & tap 'VOLUME_MUTE'")
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

        # Click Home virtual icon as surrogate for physical scan button
        keyremap_click_virtual_home(serial)
        time.sleep(1)

        keyremap_tap_ok_button(d, serial)
        # NONE/KEYS are always on the first screen; VOLUME_MUTE can require scrolling to reach on
        # small screens, so don't gate this check on it being visible without scrolling first.
        if keyremap_find_text_center(d, "NONE", contains=False) is None:
            save_step_screenshot(d, "step1_target_list_not_found", SCRIPT_IMG_DIR)
            self.fail("Step 1 Failed: Remap target list did not open after clicking OK")

        if not keyremap_tap_text(d, serial, "VOLUME_MUTE", contains=True, max_swipes=10):
            save_step_screenshot(d, "step1_mute_not_found", SCRIPT_IMG_DIR)
            self.fail("Step 1 Failed: 'VOLUME_MUTE' not found in target list after scrolling")
        time.sleep(2)

        if keyremap_find_text_center(d, "MUTE", contains=True) is None:
            save_step_screenshot(d, "step1_entry_not_confirmed", SCRIPT_IMG_DIR)
            self.fail("Step 1 Failed: 'MUTE' not shown in Keyremap list after saving")

        save_step_screenshot(d, "step1_remap_saved", SCRIPT_IMG_DIR)
        print("  ✓ Remap entry saved: HOME → VOLUME_MUTE")
        print("  ✓ Step 1 passed")

        # ── Step 2 ────────────────────────────────────────────────────────────
        print("\n[Step 2/3] Press the Home key on the device")
        print("-"*60)

        keyremap_tap_navbar_home(serial)
        time.sleep(1)
        save_step_screenshot(d, "step2_home_pressed", SCRIPT_IMG_DIR)
        print("  ✓ Step 2 passed")

        # ── Step 3 ────────────────────────────────────────────────────────────
        print("\n[Step 3/3] Verify media volume is 0 via media_session command")
        print("-"*60)

        volume_is_zero = keyremap_is_media_volume_zero_by_media_session(serial)
        print(f"  media_session 'volume --stream 3 --get' is 0: {volume_is_zero}")

        if not volume_is_zero:
            save_step_screenshot(d, "step3_not_muted", SCRIPT_IMG_DIR)
            self.fail(
                "Step 3 Failed: device was not muted by HOME "
                "(media_session volume is not 0)"
            )

        save_step_screenshot(d, "step3_muted", SCRIPT_IMG_DIR)
        print("  ✓ media_session volume is 0 – device muted")
        print("  ✓ Step 3 passed")
        print("\n[L2_Keyremap] All steps passed ✓")

if __name__ == "__main__":
    unittest.main()
