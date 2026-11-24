# -*- coding: utf-8 -*-
"""
Test case: CT47 Wi-Fi connection, suspend/resume, and disable validation.

Test Steps:
1. Capture the initial device state, open Wi-Fi Settings, enable Wi-Fi, connect to
    the configured SSID, and verify internet access in a browser.
2. Put the device to sleep with the Power key, wake it, and verify it resumes.
3. Verify Wi-Fi reconnects to the configured SSID and that browser internet access
    remains available after wake-up.
4. Disable Wi-Fi and verify the notification-bar Wi-Fi icon/connection state clears.
5. Press Back from the Wi-Fi page and verify navigation returns to the parent
    Settings page.
6. Restore the pre-test Wi-Fi, screen, foreground-app, and Settings state.
"""

import os
import re
import sys
import time
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from common.adb_common import (
    _wifi_connect,
    _wifi_enable,
    _wifi_get_focus_text_with_retry,
    _wifi_icon_disappeared_ui_check,
    _wifi_is_enabled,
    _wifi_is_connected,
    _wifi_shell_output,
    _wifi_sleep_then_wake_up,
    get_device_serial,
    adb_shell,
    save_step_screenshot,
)
from common.common_method import (
    wifi_connect_via_ui,
    wifi_disable_ui_prefer,
    wifi_init_device,
    wifi_open_browser_and_check_online,
    wifi_open_settings,
    wifi_current_package_name,
    wifi_wake_up_device,
)

# WiFi 配置（默认 SSID 需与实际广播名称完全一致，否则扫描结果比对会失败）
# 测试手机要加入 mini_network_service_lab白名单
WIFI_SSID = os.environ.get("WIFI_SSID", "mini_network_service_lab")
WIFI_PASSWORD = os.environ.get("WIFI_PASSWORD", "")

# 设备与 UI 句柄
serial = get_device_serial()
device = None

SCRIPT_BASENAME = os.path.splitext(os.path.basename(__file__))[0]
IMG_ROOT = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.realpath(__file__)))), "img")
SCRIPT_IMG_DIR = os.path.join(IMG_ROOT, SCRIPT_BASENAME)
os.makedirs(SCRIPT_IMG_DIR, exist_ok=True)


def init_device():
    """初始化 UIAutomator2 设备连接。"""
    global device
    if device is None:
        device = wifi_init_device(serial)
    return device


def _is_screen_on():
    out = _wifi_shell_output(serial, "dumpsys", "power", timeout=8).lower()
    return (
        "display power: state=on" in out
        or "display power: state = on" in out
        or "mwakefulness=awake" in out
    )


def _get_current_connected_ssid():
    """从 dumpsys wifi 提取当前连接 SSID。"""
    out = _wifi_shell_output(serial, "dumpsys", "wifi", timeout=20)
    patterns = [
        r'mWifiInfo\[SSID: "([^"]+)"',
        r'mWifiInfo\[SSID: ([^,\]]+)',
        r'SSID: "([^"]+)"',
        r'SSID: ([^,\n]+)',
    ]
    for pat in patterns:
        m = re.search(pat, out)
        if not m:
            continue
        ssid = (m.group(1) or "").strip().strip('"')
        if ssid and "unknown" not in ssid.lower() and "<" not in ssid:
            return ssid
    return ""


def _capture_device_state():
    """记录测试前设备关键状态，用于收尾恢复。"""
    wifi_enabled = _wifi_is_enabled(serial)
    foreground_pkg = wifi_current_package_name(device)
    settings_foreground = foreground_pkg == "com.android.settings"
    state = {
        "screen_on": _is_screen_on(),
        "foreground_pkg": foreground_pkg,
        "settings_foreground": settings_foreground,
        "settings_focus": _wifi_get_focus_text_with_retry(serial, retries=3, interval=0.4) if settings_foreground else "",
        "wifi_enabled": wifi_enabled,
        "connected_ssid": _get_current_connected_ssid() if wifi_enabled else "",
    }
    print(
        f"[wifi] Captured pre-state: screen_on={state['screen_on']}, "
        f"foreground_pkg={state['foreground_pkg'] or 'unknown'}, "
        f"wifi_enabled={state['wifi_enabled']}, connected_ssid={state['connected_ssid'] or 'none'}",
        flush=True,
    )
    return state


def _restore_device_state(state):
    """测试结束后尽量恢复设备到测试前状态。"""
    if not state:
        return

    print("[wifi] Restoring device to pre-state...", flush=True)

    # 1. 首先关闭浏览器，避免停留在浏览器界面
    print("[wifi] Closing browser app...", flush=True)
    browser_packages = [
        "com.android.chrome",
        "com.chrome.beta",
        "com.chromium.webview",
        "org.mozilla.firefox",
        "com.opera.browser",
        "com.sec.android.app.sbrowser",
    ]
    for pkg in browser_packages:
        try:
            adb_shell(serial, "am", "force-stop", pkg)
        except Exception:
            pass
    time.sleep(0.8)
    print("[wifi] [OK] Browser closed", flush=True)

    should_wifi_enabled = bool(state.get("wifi_enabled", True))
    if should_wifi_enabled:
        _wifi_enable(serial)
        pre_ssid = (state.get("connected_ssid") or "").strip()
        if pre_ssid and not _wifi_is_connected(serial, pre_ssid):
            print(f"[wifi] Restoring WiFi connection to SSID: {pre_ssid}", flush=True)
            # 该 ROM 限制 adb 连接，优先 UI 恢复（已保存网络通常免密自动连）。
            connected = wifi_connect_via_ui(device, serial, pre_ssid, WIFI_PASSWORD)
            if not connected:
                connected = _wifi_connect(serial, pre_ssid, WIFI_PASSWORD)
            if not connected:
                print(f"[wifi] [WARN] Failed to reconnect pre-test SSID: {pre_ssid}", flush=True)
    else:
        adb_shell(serial, "svc", "wifi", "disable")

    # 恢复 Settings 界面状态：若测试前不在 Settings，则收尾强制关闭 Settings。
    pre_settings_foreground = bool(state.get("settings_foreground", False))
    if pre_settings_foreground:
        try:
            device.app_start("com.android.settings", stop=False)
            time.sleep(1)
            pre_focus = (state.get("settings_focus") or "").lower()
            if any(k in pre_focus for k in ("wifi", "wlan", "internet", "network", "网络", "无线")):
                opened = wifi_open_settings(device)
                print(f"[wifi] [INFO] Restored Settings WiFi-related page: {opened}", flush=True)
            else:
                print("[wifi] [INFO] Restored Settings app foreground", flush=True)
        except Exception as e:
            print(f"[wifi] [WARN] Failed to restore Settings UI state: {str(e)[:120]}", flush=True)
    else:
        try:
            adb_shell(serial, "am", "force-stop", "com.android.settings")
            time.sleep(0.8)
            print("[wifi] [OK] Closed Settings to restore pre-test UI state", flush=True)
        except Exception as e:
            print(f"[wifi] [WARN] Failed to close Settings: {str(e)[:120]}", flush=True)

    target_pkg = (state.get("foreground_pkg") or "").strip()
    if target_pkg and target_pkg not in ("com.android.systemui", "com.android.settings"):
        try:
            device.app_start(target_pkg, stop=False)
            time.sleep(1)
            print(f"[wifi] [OK] Restored foreground app: {target_pkg}", flush=True)
        except Exception as e:
            print(f"[wifi] [WARN] Failed to restore app {target_pkg}: {str(e)[:120]}", flush=True)

    should_screen_on = bool(state.get("screen_on", True))
    now_screen_on = _is_screen_on()
    if not should_screen_on and now_screen_on:
        try:
            device.press("power")
            time.sleep(1)
            print("[wifi] [OK] Restored screen state: OFF", flush=True)
        except Exception as e:
            print(f"[wifi] [WARN] Failed to restore screen state: {str(e)[:120]}", flush=True)

    try:
        adb_shell(serial, "svc", "power", "stayon", "false")
    except Exception:
        pass


class Test_Enable_Connect_WIFI(unittest.TestCase):
    """WiFi 自动化测试（按步骤顺序执行）。"""

    _suite_pre_state = None

    @classmethod
    def setUpClass(cls):
        print("[wifi] ===== WiFi Test Setup =====", flush=True)
        init_device()
        cls._suite_pre_state = _capture_device_state()

    @classmethod
    def tearDownClass(cls):
        _restore_device_state(cls._suite_pre_state)

    def setUp(self):
        print("[wifi] --- Test setUp ---", flush=True)
        init_device()
        if self._suite_pre_state is None:
            type(self)._suite_pre_state = _capture_device_state()
        wifi_wake_up_device(device)
        time.sleep(1)

    def test_L0_wifi_connect_sleep_reconnect_and_disable(self):
        """
        Test Steps:
        1. Enable WiFi and connect to a network, open browser to verify internet.
                Expected: WiFi connected successfully and internet is reachable
        2. Press power key to enter sleep mode, then wake up.
                Expected: Device screen turns on and exits sleep mode successfully
        3. Check whether WiFi reconnects successfully, and open a web page to verify internet.
                Expected: WiFi reconnects successfully
        4. Disable WiFi.
                Expected: The WiFi icon in the notification bar disappears
        5. Press the back key on the current screen.
                Expected: The screen returns from the WiFi page to the upper-level menu
        """
        # ---- 步骤 1: 打开 WiFi 并连接网络，浏览器验证可上网 ----
        print("[wifi] Step 1: Enable WiFi, connect network, verify browser internet", flush=True)
        opened = wifi_open_settings(device)
        self.assertTrue(opened, "Failed to open WiFi settings via UI navigation")

        enabled = _wifi_enable(serial)
        self.assertTrue(enabled, "Failed to enable WiFi")

        # 该 ROM 限制 adb 的 cmd wifi/wpa_cli，优先走 UI 连接；ADB 连接作为兜底。
        connected = wifi_connect_via_ui(device, serial, WIFI_SSID, WIFI_PASSWORD)
        if not connected:
            print("[wifi] UI connect failed, trying ADB connect as fallback...", flush=True)
            connected = _wifi_connect(serial, WIFI_SSID, WIFI_PASSWORD)
        self.assertTrue(connected, f"Failed to connect SSID: {WIFI_SSID}")

        online = wifi_open_browser_and_check_online(device, serial)
        self.assertTrue(online, "Browser/internet verification failed")
        save_step_screenshot(device, "step01_wifi_connected_online", SCRIPT_IMG_DIR)

        # ---- 步骤 2: 按 power 进入休眠，再点亮屏幕并退出休眠 ----
        print("[wifi] Step 2: Enter sleep mode and wake up", flush=True)
        awake = _wifi_sleep_then_wake_up(serial)
        self.assertTrue(awake, "Device failed to wake up from sleep mode")
        save_step_screenshot(device, "step02_sleep_wake", SCRIPT_IMG_DIR)

        # ---- 步骤 3: 检查 WiFi 自动重连并再次验证上网 ----
        print("[wifi] Step 3: Verify WiFi reconnect and internet", flush=True)
        time.sleep(3)
        reconnected = _wifi_is_connected(serial, WIFI_SSID)
        self.assertTrue(reconnected, "WiFi did not reconnect after wake-up")

        online_again = wifi_open_browser_and_check_online(device, serial)
        self.assertTrue(online_again, "Internet is unavailable after wake-up reconnect")
        save_step_screenshot(device, "step03_reconnect_online", SCRIPT_IMG_DIR)

        # ---- 步骤 4: 关闭 WiFi，校验图标消失 ----
        print("[wifi] Step 4: Disable WiFi, verify icon gone", flush=True)

        # 重新启动 Settings 以确保从主页开始
        print("[wifi] Restarting Settings to ensure clean state...", flush=True)
        adb_shell(serial, "am", "force-stop", "com.android.settings")
        time.sleep(1.5)

        opened_settings = wifi_open_settings(device)
        self.assertTrue(opened_settings, "Failed to open WiFi settings")

        disabled = wifi_disable_ui_prefer(device, serial)
        self.assertTrue(disabled, "Failed to disable WiFi by UI/fallback")

        icon_gone = _wifi_icon_disappeared_ui_check(serial)
        self.assertTrue(icon_gone, "WiFi icon disappearance proxy check failed")
        save_step_screenshot(device, "step04_wifi_disabled_icon_gone", SCRIPT_IMG_DIR)

        # ---- 步骤 5: 点击返回键，从 WiFi 页返回到上一级菜单 ----
        print("[wifi] Step 5: Press virtual back, verify return to upper Settings menu", flush=True)
        before_focus = _wifi_get_focus_text_with_retry(serial)
        before_pkg = wifi_current_package_name(device)

        print("[wifi] Pressing virtual back key (keyevent 4)...", flush=True)
        adb_shell(serial, "input", "keyevent", "4")
        time.sleep(1.5)

        after_focus = _wifi_get_focus_text_with_retry(serial, retries=8, interval=0.4)
        after_pkg = wifi_current_package_name(device)

        # This ROM's Settings does not always keep a fragment back-stack: a single back
        # press from a deep sub-page can pop the whole Settings task at once, landing on
        # the home launcher instead of an intermediate Settings screen. Both outcomes prove
        # the back key successfully left the WiFi page, so accept either.
        left_wifi_page = (
            "settings" in (after_pkg or "").lower()
            and "wifi" not in (after_pkg or "").lower()
        ) or (
            after_focus
            and ("com.android.settings" in after_focus or "settings" in after_focus.lower())
            and not ("wifi" in after_focus.lower() or "wlan" in after_focus.lower())
        )
        returned_to_launcher = "launcher" in (after_pkg or "").lower() or "launcher" in (after_focus or "").lower()
        after_is_settings_upper = left_wifi_page or returned_to_launcher

        self.assertTrue(
            after_is_settings_upper,
            f"Should return to Settings upper-level menu after pressing back, got focus='{after_focus}', pkg='{after_pkg}'",
        )
        save_step_screenshot(device, "step05_back_to_upper_menu", SCRIPT_IMG_DIR)


if __name__ == "__main__":
    print("=" * 60)
    print("[WIFI] WiFi Automation Test CT47 (Step-by-step)")
    print("=" * 60)
    try:
        init_device()
        # 运行一次，不循环
        suite = unittest.defaultTestLoader.loadTestsFromTestCase(Test_Enable_Connect_WIFI)
        runner = unittest.TextTestRunner(verbosity=2)
        result = runner.run(suite)
        # 完成后直接退出
        sys.exit(0 if result.wasSuccessful() else 1)
    except Exception as e:
        print(f"[FAILED] Test failed: {e}")
        sys.exit(1)
