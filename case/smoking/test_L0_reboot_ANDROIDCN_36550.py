# -*- coding:utf-8 -*-
# pyright: reportMissingImports=false
"""
L0 reboot verification test - UIAutomator2

Steps:
1. Long press the power key for 1 second to bring up the power menu
2. Click Restart, device reboots successfully
3. Automatically enable USB debugging mode after reboot
Notes:
- A script contains only one test case, executed internally in step order.
- Take a screenshot after each successful step, saved to:
    C:/Users/H255821/Desktop/2026 Automation/auto_test_0605/img/<script_name>/
- Restore the device to its pre-test state as much as possible after the script ends.
"""

import os
import sys
import time
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from common.adb_common import (
    get_device_serial,
    save_step_screenshot,
    reboot_run_adb_shell,
    reboot_capture_pre_state,
    reboot_enable_usb_debugging,
    reboot_verify_usb_debugging_enabled,
    reboot_wait_device_success,
)
from common.common_method import (
    scan_init_device,
    reboot_trigger_power_menu,
    reboot_click_restart_button,
    reboot_restore_device_state,
)

serial = get_device_serial()
device = None

SCRIPT_BASENAME = os.path.splitext(os.path.basename(__file__))[0]
IMG_ROOT = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.realpath(__file__)))), "img")
SCRIPT_IMG_DIR = os.path.join(IMG_ROOT, SCRIPT_BASENAME)
os.makedirs(SCRIPT_IMG_DIR, exist_ok=True)


def init_device(force_reconnect=False):
    """Initialize or reconnect UIAutomator2 device via common helper."""
    global device
    if force_reconnect or device is None:
        device = scan_init_device(serial)
    return device


class Test_L0_Reboot(unittest.TestCase):
    """L0 reboot test: long press power -> click Restart -> verify reboot success."""

    _suite_pre_state = None

    @classmethod
    def setUpClass(cls):
        print("[reboot] ===== Reboot Test Setup =====", flush=True)
        init_device()
        cls._suite_pre_state = reboot_capture_pre_state(serial)

    @classmethod
    def tearDownClass(cls):
        print("[reboot] ===== Reboot Test TearDown =====", flush=True)
        reboot_restore_device_state(device, serial, cls._suite_pre_state)

    def setUp(self):
        print("[reboot] --- Test setUp ---", flush=True)
        init_device()
        try:
            device.screen_on()
            device.unlock()
        except Exception:
            pass
        time.sleep(1)

    def step01_long_press_power_show_menu(self):
        """Step01: Long press the power key for 1 second to bring up the power menu."""
        print("[reboot] Step 1: Long press power key (1s), expect power menu", flush=True)

        opened = reboot_trigger_power_menu(device, serial)
        if not opened:
            save_step_screenshot(device, "step01_power_menu_not_found", SCRIPT_IMG_DIR)
        self.assertTrue(opened, "Power menu did not appear after long pressing power key")
        save_step_screenshot(device, "step01_power_menu", SCRIPT_IMG_DIR)

    def step02_click_restart_and_verify_reboot(self):
        """Step02: Click Restart, device reboots successfully."""
        print("[reboot] Step 2: Click Restart and verify reboot success", flush=True)

        old_boot_id = reboot_run_adb_shell(serial, "cat /proc/sys/kernel/random/boot_id", timeout=8)
        self.assertTrue(old_boot_id, "Cannot read pre-reboot boot_id")

        clicked = reboot_click_restart_button(device)
        self.assertTrue(clicked, "Restart button not found/clickable in power menu")

        reboot_ok = reboot_wait_device_success(serial, old_boot_id, timeout_sec=300)
        self.assertTrue(reboot_ok, "Device reboot verification failed")

        # Reconnect UIAutomator2 after reboot to take screenshot.
        init_device(force_reconnect=True)
        try:
            device.screen_on()
            device.unlock()
        except Exception:
            pass
        time.sleep(1)
        save_step_screenshot(device, "step02_reboot_success", SCRIPT_IMG_DIR)

    def step03_enable_usb_debugging(self):
        """Step03: Automatically enable USB debugging mode after reboot."""
        print("[reboot] Step 3: Enable USB debugging after reboot", flush=True)

        enabled = reboot_enable_usb_debugging(serial)
        self.assertTrue(enabled, "Failed to enable USB debugging via adb settings")

        time.sleep(1)
        verified = reboot_verify_usb_debugging_enabled(serial)
        self.assertTrue(verified, "USB debugging verification failed")

        save_step_screenshot(device, "step03_usb_debugging_enabled", SCRIPT_IMG_DIR)

    def test_L0_reboot(self):
        """
        Test Steps:
        1. Long-press the Power key and verify the power menu is displayed.
        2. Select Restart and verify the device completes a normal reboot.
        3. Re-enable and verify USB debugging after the device returns online.
        """
        self.step01_long_press_power_show_menu()
        self.step02_click_restart_and_verify_reboot()
        self.step03_enable_usb_debugging()


if __name__ == "__main__":
    print("=" * 60)
    print("[REBOOT] L0 Reboot Test (Step-by-step)")
    print("=" * 60)
    try:
        init_device()
        suite = unittest.defaultTestLoader.loadTestsFromTestCase(Test_L0_Reboot_ANDROIDCN_36550)
        runner = unittest.TextTestRunner(verbosity=2)
        result = runner.run(suite)
        sys.exit(0 if result.wasSuccessful() else 1)
    except Exception as e:
        print(f"[FAILED] Test failed: {e}")
        sys.exit(1)
