# __author__ = 'sophy'

# -*- coding:utf-8 -*-
import os
import unittest
import time
import subprocess
import sys
import uiautomator2 as u2
"""
Test case: ANDROIDCN-35598 - Airplane mode disables wireless radios.

Test Steps:
1. Wake the device and ensure Airplane mode is disabled before the test starts.
2. Enable Wi-Fi and confirm the system reports its enabled state.
3. Enable Bluetooth, accept any runtime permission dialog, and confirm it is enabled.
4. Open Settings > Network & internet > Airplane mode and enable Airplane mode.
5. Capture evidence and verify the reported Wi-Fi and Bluetooth states match the
    expected disabled values for the target device.
6. During cleanup, disable Airplane mode, close Settings, and return to Home.
"""

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from common.adb_common import save_step_screenshot, get_device_serial, run_adb_cmd

serial = get_device_serial()
if not serial:
    print("Error: No Android device found. Connect a device or set ANDROID_SERIAL.")
    sys.exit(1)

d = u2.connect(serial)

SCRIPT_BASENAME = os.path.splitext(os.path.basename(__file__))[0]
SCRIPT_IMG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.realpath(__file__)))), 'img', SCRIPT_BASENAME)
os.makedirs(SCRIPT_IMG_DIR, exist_ok=True)


def _run_adb_shell(command):
    output = run_adb_cmd(serial, f"shell {command}", log_print=False)
    if isinstance(output, bytes):
        return output.decode("utf-8", errors="ignore").strip()
    text = str(output).strip()
    if text.startswith("b'") and text.endswith("'"):
        text = text[2:-1]
    elif text.startswith('b"') and text.endswith('"'):
        text = text[2:-1]
    return text.strip()


def _dismiss_bt_permission_dialog(timeout_sec=3):
    for _ in range(timeout_sec):
        for label in ("ALLOW", "Allow", "OK", "Yes", "Turn on", "Turn off", "允许", "确定"):
            btn = d(text=label)
            if btn.exists:
                btn.click()
                time.sleep(1)
                return
        time.sleep(1)


def _click_setting_item(candidates):
    for text in candidates:
        if d(text=text).exists(timeout=2):
            d(text=text).click()
            return True

    for text in candidates:
        try:
            d(scrollable=True).scroll.to(text=text)
            time.sleep(1)
        except Exception:
            continue
        if d(text=text).exists(timeout=1):
            d(text=text).click()
            return True
    return False


def _get_labeled_switch(candidates):
    for text in candidates:
        sw = d(text=text).right(className="android.widget.Switch")
        if sw.exists:
            return sw
    return None

def _open_wifi_settings():
    print("enable wifi..")
    subprocess.run(["adb", "-s", serial, "shell", "svc", "wifi", "enable"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(2)
    wifi_state = _run_adb_shell("settings get global wifi_on")
    print(f"wifi state after enable request: {wifi_state}")

def _open_bt_settings():
    print("enable BT..")
    """Enable Bluetooth using system intent and verify by ADB state."""
    time.sleep(2)
    subprocess.run(
        ["adb", "-s", serial, "shell", "am", "start", "-a", "android.bluetooth.adapter.action.REQUEST_ENABLE"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )
    time.sleep(2)
    _dismiss_bt_permission_dialog()

    bt_state = ""
    for _ in range(8):
        bt_state = _run_adb_shell("settings get global bluetooth_on")
        if bt_state == "1":
            break
        time.sleep(1)
    assert bt_state == "1", f"Bluetooth should be enabled, but state is {bt_state}"

def _open_airplane_mode_settings():
    print("enable airplane mode..")
    """Open Airplane mode settings and ensure it is ON."""
    print("perform open airplane mode settings..")
    # subprocess.run(["adb", "-s", serial, "shell", "am", "start", "-n", "com.android.settings/.Settings"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
     # Force restart Settings app with -S flag (stop and start)
    subprocess.run(
        ["adb", "-s", serial, "shell", "am", "start", "-S",
         "-n", "com.android.settings/.Settings"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )
    time.sleep(2)

    _click_setting_item(("Network & internet", "网络和互联网", "无线和网络", "网络和连接"))
    time.sleep(1)

    if not _click_setting_item(("Airplane mode", "飞行模式")):
        raise AssertionError("Airplane mode entry not found in Settings")
    time.sleep(1)

    # Toggle Airplane mode if off
    ap_switch = _get_labeled_switch(("Airplane mode", "飞行模式"))
    if ap_switch.exists():
        checked = ap_switch.info.get("checked", False)
        if str(checked).lower() == "false":
            ap_switch.click()

    time.sleep(2)

def _close_airplane_mode():
    print("disable airplane mode..")
    """Turn off Airplane mode after test."""
    subprocess.run(["adb", "-s", serial, "shell", "am", "start", "-n", "com.android.settings/.Settings"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(2)

    _click_setting_item(("Network & internet", "网络和互联网", "无线和网络", "网络和连接"))
    time.sleep(1)

    if not _click_setting_item(("Airplane mode", "飞行模式")):
        d.press('home')
        return
    time.sleep(1)

    # Toggle Airplane mode if on
    ap_switch = _get_labeled_switch(("Airplane mode", "飞行模式"))
    if ap_switch.exists():
        checked = ap_switch.info.get("checked", False)
        if str(checked).lower() == "true":
            ap_switch.click()
            print("Airplane mode turned OFF")

    time.sleep(2)
    d.press('home')


def check_airplane():        
        # Check airplane mode status and turn it off if it's on
        airplane_result = subprocess.run(
            f'adb -s {serial} shell settings get global airplane_mode_on',
            shell=True,
            capture_output=True,
            text=True
        )
        airplane_state = airplane_result.stdout.strip()
        
        if airplane_state == '1':
            print("Airplane mode is ON, turning it off...")
            _close_airplane_mode()
        else:
            print("Airplane mode is already OFF")
            d.press('home')

class Test_L0_Airplane(unittest.TestCase):
    def setUp(self):
        d.screen_on()
        d.press('home')
        time.sleep(1)
        check_airplane()

    def tearDown(self):
        # close Settings.
        subprocess.run(f'adb -s {serial} shell am force-stop com.android.settings', shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
   
        # Turn off airplane mode after test passes
        _close_airplane_mode()
        time.sleep(2)
        print("Test completed. Airplane mode has been turned off.")
        d.press('home')

    def test_L0_airplan_mode(self):
        """
        Test Steps:
        1. Start from Home with the screen on and ensure Airplane mode is disabled.
        2. Enable Wi-Fi and record the reported `wifi_on` state.
        3. Enable Bluetooth, accepting a system confirmation dialog when present,
           and verify the reported `bluetooth_on` state is enabled.
        4. Open Settings > Network & internet > Airplane mode and turn Airplane
           mode on.
        5. Wait for the radio-state transition, capture a screenshot, and verify
           `wifi_on` is `3` and `bluetooth_on` is `2`.
        6. During teardown, disable Airplane mode, close Settings, and return to
           Home so subsequent tests begin from a connected baseline.
        """
        _open_wifi_settings()
        _open_bt_settings()
        _open_airplane_mode_settings()

        # Wait for airplane mode to take effect
        time.sleep(3)
        
        # Verify WiFi is disabled
        wifi_result = subprocess.run(
            f'adb -s {serial} shell settings get global wifi_on',
            shell=True,
            capture_output=True,
            text=True
        )
        wifi_state = wifi_result.stdout.strip()
        print(f"WiFi state after airplane mode: {wifi_state}")
        
        # Verify Bluetooth is disabled
        bt_result = subprocess.run(
            f'adb -s {serial} shell settings get global bluetooth_on',
            shell=True,
            capture_output=True,
            text=True
        )
        bt_state = bt_result.stdout.strip()
        print(f"Bluetooth state after airplane mode: {bt_state}")
        
        # Take screenshot for verification
        save_step_screenshot(d, 'airplane_mode_enabled', SCRIPT_IMG_DIR)
        
        # Assert both WiFi and Bluetooth are disabled (state = 0)
        self.assertEqual(wifi_state, '3', f"WiFi should be disabled in airplane mode, but state is {wifi_state}")
        self.assertEqual(bt_state, '2', f"Bluetooth should be disabled in airplane mode, but state is {bt_state}")
        
        print("✅ PASS: WiFi and Bluetooth are both disabled in airplane mode")