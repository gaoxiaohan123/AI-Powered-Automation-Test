# -*- coding: utf-8 -*-
"""
Scan Wedge automation test - executed step by step in order

Steps:
1. Open an input field, scan into the input field, and verify decode success
2. Press the power key to enter sleep mode, wake up, scan into the input field, and verify decode success
3. Rapidly press the scan key 20 times and verify each scan decodes successfully
4. Enter Settings and switch to the Guest account
5. Open the input field in the Guest account, scan, and verify decode success
6. Rapidly press the scan key 20 times in the Guest account and verify each scan decodes successfully
"""

import os
import sys
import time
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from common.adb_common import (
    adb_shell,
    dcs_test_prepare_image_on_display_device,
    dcs_test_press_home,
    dcs_test_trigger_honeywell_scan,
    dcs_test_wait_device_online,
    dcs_test_wake_and_unlock,
    save_step_screenshot,
    scan_create_guest_user_id,
    scan_enable_u2_for_user,
    scan_get_current_user_id,
    scan_get_guest_user_id,
    scan_get_owner_user_id,
    scan_handle_guest_reset_prompt,
    scan_is_screen_on,
    scan_move_cursor_to_end,
    scan_switch_user_by_id,
    scan_wait_power_state,
)
from common.common_method import (
    dcs_test_connect_u2,
    scan_clear_input_field,
    scan_dismiss_common_dialogs,
    scan_get_input_field_text,
    scan_init_device,
    scan_open_input_field,
    scan_reconnect_device,
    scan_refocus_input_field,
    scan_swipe_unlock_if_needed,
    scan_switch_to_guest_account_via_ui,
    scan_wake_up_device,
)

DEV0_SERIAL = (os.environ.get("AUTONEXUS_DEV0_SN") or os.environ.get("ANDROID_SERIAL") or "").strip()
DEV1_SERIAL = (os.environ.get("AUTONEXUS_DEV1_SN") or "").strip()
if not DEV0_SERIAL or not DEV1_SERIAL:
    raise RuntimeError("AUTONEXUS_DEV0_SN and AUTONEXUS_DEV1_SN are required")

EXPECTED_BARCODE = "12345ABCDEF"
PLACEHOLDER_TEXTS = {"Search...", "Search…"}

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.realpath(__file__))))
SCRIPT_IMG_DIR = os.path.join(PROJECT_ROOT, "img", os.path.splitext(os.path.basename(__file__))[0])
os.makedirs(SCRIPT_IMG_DIR, exist_ok=True)
REFERENCE_IMAGE = os.path.join(PROJECT_ROOT, "files", "images", "scandemo_img", "12345ABCDEF.jpg")
REFERENCE_REMOTE_PATH = "/sdcard/Pictures/12345ABCDEF.jpg"

if not dcs_test_wait_device_online(DEV0_SERIAL, timeout_seconds=25):
    raise RuntimeError(f"Scanner device is offline: {DEV0_SERIAL}")
if not dcs_test_wait_device_online(DEV1_SERIAL, timeout_seconds=25):
    raise RuntimeError(f"Display device is offline: {DEV1_SERIAL}")


class Test_ScanWedge(unittest.TestCase):
    """Scan Wedge automation test (executed step by step in order)."""

    d0 = None
    d1 = None

    # ---------- device / session helpers ----------

    def _init_devices(self):
        if self.d0 is None:
            self.d0 = scan_init_device(DEV0_SERIAL)
        if self.d1 is None:
            self.d1 = dcs_test_connect_u2(DEV1_SERIAL)

    def _reconnect(self, reason):
        """Rebuild the uiautomator2 session (it can become invalid after a user switch)."""
        user_id = scan_get_current_user_id(DEV0_SERIAL)
        if user_id is not None and user_id != self._owner_user_id:
            scan_enable_u2_for_user(DEV0_SERIAL, user_id)
        self.d0 = scan_reconnect_device(DEV0_SERIAL, reason=reason)
        return self.d0 is not None

    def _show_reference_barcode(self):
        """Display the reference barcode on the second device."""
        if not os.path.exists(REFERENCE_IMAGE):
            raise AssertionError(f"Reference image not found: {REFERENCE_IMAGE}")
        dcs_test_wake_and_unlock(DEV1_SERIAL, self.d1)
        dcs_test_prepare_image_on_display_device(
            DEV1_SERIAL, self.d1, REFERENCE_IMAGE, REFERENCE_REMOTE_PATH
        )
        save_step_screenshot(self.d1, "reference_barcode_display", SCRIPT_IMG_DIR)

    def _screenshot(self, step):
        save_step_screenshot(self.d0, step, img_dir=SCRIPT_IMG_DIR)

    # ---------- input field / scan helpers ----------

    def _open_input(self):
        if scan_open_input_field(self.d0, DEV0_SERIAL):
            return True
        return self._reconnect("open input retry") and scan_open_input_field(self.d0, DEV0_SERIAL)

    def _focus_input(self):
        """Click the EditText (if not focused) and move the cursor to the end."""
        try:
            if not self.d0(focused=True, className="android.widget.EditText").exists(timeout=0.2):
                scan_refocus_input_field(self.d0)
            scan_move_cursor_to_end(DEV0_SERIAL)
        except Exception:
            pass

    def _scan(self, ensure_focus=False):
        """Clear the input field, then trigger one scan (press, 0.8s, release)."""
        scan_clear_input_field(self.d0)
        if ensure_focus:
            self._focus_input()
        ok = dcs_test_trigger_honeywell_scan(DEV0_SERIAL)
        scan_move_cursor_to_end(DEV0_SERIAL)
        return ok

    def _verify_barcode(self, max_wait_seconds=10):
        """Poll the input field until it contains the expected barcode."""
        deadline = time.time() + max_wait_seconds
        attempts = 0
        while True:
            text = scan_get_input_field_text(self.d0)
            attempts += 1
            if text and text.strip() not in PLACEHOLDER_TEXTS and EXPECTED_BARCODE in text:
                print(f"[scan] [OK] Barcode matched expected value: '{EXPECTED_BARCODE}'", flush=True)
                return True
            # A u2 call that triggers atx-agent recovery can eat the whole window, so always allow a few reads.
            if time.time() >= deadline and attempts >= 3:
                break
            time.sleep(0.12)
        print(f"[scan] [FAIL] Expected barcode not detected after {max_wait_seconds}s: {EXPECTED_BARCODE}", flush=True)
        return False

    def _rapid_scan(self, focus_every, verify_wait, guest=False):
        """Open the input field, scan 20 times back to back, and verify the final result."""
        self.assertTrue(self._open_input(), "Failed to open input field")
        self._scan(ensure_focus=True)
        for i in range(1, 20):
            dcs_test_trigger_honeywell_scan(DEV0_SERIAL)
            if focus_every and i % focus_every == 0:
                self._focus_input()
            time.sleep(0.04)
        if guest:
            # atx-agent drops in Guest during the burst; rebuild u2 before reading the field.
            self._reconnect("guest rapid scan")
        return self._verify_barcode(max_wait_seconds=verify_wait)

    def _guest_scan_with_retries(self, attempts=3, verify_wait=8):
        """Guest scan: dismiss popups, refocus, scan, and retry on failure."""
        for idx in range(attempts):
            self._dismiss_guest_reset()
            scan_dismiss_common_dialogs(self.d0)
            if not scan_refocus_input_field(self.d0):
                self._open_input()
                scan_refocus_input_field(self.d0)
            if not self._scan(ensure_focus=True):
                self._reconnect("scan trigger retry")
            if self._verify_barcode(max_wait_seconds=verify_wait):
                return True
            print(f"[scan] [WARN] Scan verify failed, retry {idx + 1}/{attempts}", flush=True)
        return False

    # ---------- power / user helpers ----------

    def _dismiss_guest_reset(self):
        scan_handle_guest_reset_prompt(DEV0_SERIAL, retries=2, interval=0.15, device=self.d0)

    def _toggle_power(self, expect_on):
        """Press power until the screen reaches the expected state (one retry)."""
        adb_shell(DEV0_SERIAL, "input", "keyevent", "26")
        if scan_wait_power_state(DEV0_SERIAL, expect_on, timeout=2.2):
            return True
        adb_shell(DEV0_SERIAL, "input", "keyevent", "26")
        return scan_wait_power_state(DEV0_SERIAL, expect_on, timeout=1.8)

    def _sleep_then_wake(self):
        if not scan_is_screen_on(DEV0_SERIAL):
            self._toggle_power(expect_on=True)
        if not self._toggle_power(expect_on=False):
            print("[scan] [WARN] Failed to enter sleep state before wake", flush=True)
        time.sleep(3)
        if not self._toggle_power(expect_on=True):
            print("[scan] [WARN] Failed to wake screen by power key", flush=True)
        adb_shell(DEV0_SERIAL, "input", "keyevent", "82")
        scan_swipe_unlock_if_needed(self.d0, DEV0_SERIAL)
        return scan_is_screen_on(DEV0_SERIAL)

    def _ensure_guest_user(self):
        """Switch to Guest via ADB (creating it if needed), falling back to the Settings UI."""
        guest_id = scan_get_guest_user_id(DEV0_SERIAL)
        if guest_id is None:
            scan_create_guest_user_id(DEV0_SERIAL)
            guest_id = scan_get_guest_user_id(DEV0_SERIAL)
        if guest_id is not None:
            if scan_get_current_user_id(DEV0_SERIAL) == guest_id:
                return True
            if scan_switch_user_by_id(DEV0_SERIAL, guest_id, max_wait_seconds=15):
                # u2 has no accessibility service in the Guest user until it is enabled there.
                return self._reconnect("guest u2 service")
        print("[scan] [WARN] ADB guest switch failed, trying UI fallback", flush=True)
        return scan_switch_to_guest_account_via_ui(
            self.d0,
            DEV0_SERIAL,
            get_current_user_id_func=lambda: scan_get_current_user_id(DEV0_SERIAL),
            get_guest_user_id_func=lambda: scan_get_guest_user_id(DEV0_SERIAL),
            max_wait_seconds=20,
        )

    # ---------- fixtures ----------

    def setUp(self):
        self._init_devices()
        scan_wake_up_device(self.d0, DEV0_SERIAL)
        self._show_reference_barcode()
        self._initial_user_id = scan_get_current_user_id(DEV0_SERIAL)
        self._owner_user_id = scan_get_owner_user_id(DEV0_SERIAL)

    def tearDown(self):
        try:
            target = self._initial_user_id if self._initial_user_id is not None else self._owner_user_id
            if scan_get_current_user_id(DEV0_SERIAL) != target:
                restored = scan_switch_user_by_id(DEV0_SERIAL, target)
                if not restored:
                    self._reconnect("restore user retry")
                    restored = scan_switch_user_by_id(DEV0_SERIAL, target, max_wait_seconds=18)
                print(f"[scan] Restore user to {target}: {'OK' if restored else 'FAILED'}", flush=True)
        except Exception as e:
            print(f"[scan] [WARN] TearDown restore failed: {e}", flush=True)

        try:
            scan_clear_input_field(self.d0)
            dcs_test_press_home(DEV0_SERIAL)
        except Exception as e:
            print(f"[scan] [WARN] TearDown cleanup failed: {e}", flush=True)

    # ---------- test ----------

    def test_L0_scan_wedge(self):
        """Wedge scan automation test: the complete flow of all steps."""

        print("[scan] === STEP 1: Open input field and scan ===", flush=True)
        self.assertTrue(self._open_input(), "Failed to open input field")
        self._scan()
        self.assertTrue(self._verify_barcode(), "Scan decode failed (step 1)")
        self._screenshot("step01_open_input_and_scan")

        print("[scan] === STEP 2: Sleep, wake up, and scan ===", flush=True)
        self.assertTrue(self._sleep_then_wake(), "Device failed to wake up")
        self.assertTrue(scan_refocus_input_field(self.d0), "Failed to refocus input field after wake-up")
        self._scan()
        self.assertTrue(self._verify_barcode(), "Scan decode failed after sleep/wake (step 2)")
        self._screenshot("step02_sleep_wake_then_scan")

        print("[scan] === STEP 3: Rapid scan 20 times ===", flush=True)
        self.assertTrue(self._rapid_scan(focus_every=5, verify_wait=15), "Rapid scan failed (step 3)")
        self._screenshot("step03_rapid_scan_20_times")

        print("[scan] === STEP 4: Switch to Guest account ===", flush=True)
        self.assertTrue(self._ensure_guest_user(), "Failed to switch to Guest account")
        self._dismiss_guest_reset()
        self._screenshot("step04_switch_to_guest_account")

        print("[scan] === STEP 5: Scan in Guest account ===", flush=True)
        self.assertTrue(self._ensure_guest_user(), "Failed to switch to Guest account before Step 5")
        self._dismiss_guest_reset()
        self.assertTrue(self._open_input(), "Failed to open input field")
        self.assertTrue(self._guest_scan_with_retries(), "Scan decode failed (step 5)")
        self._screenshot("step05_scan_in_guest_account")

        print("[scan] === STEP 6: Rapid scan 20 times in Guest ===", flush=True)
        self.assertTrue(self._rapid_scan(focus_every=0, verify_wait=20, guest=True), "Rapid scan in Guest failed (step 6)")
        self._screenshot("step06_rapid_scan_20_times_in_guest")


if __name__ == "__main__":
    unittest.main(verbosity=2)
