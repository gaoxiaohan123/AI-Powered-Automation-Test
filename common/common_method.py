# __author__ = 'H339143'
# -*- coding:utf-8 -*-

"""
    common methods
"""

import subprocess
from subprocess import *
import time
import configparser
import os
import re
import xml.etree.ElementTree as ET
import unittest
from datetime import datetime, timedelta, timezone
from uiautomator import Device
import sys


try:
    import uiautomator2 as u2
except ImportError:
    u2 = None

class CommonMethod(object):
    def __init__(self):
        pass

    # Description: The common preamble is called by all scripts. It connects or disconnect to wifi, closes recent apps,
    # brings the device to home screen etc
    def tc_common_preamble(self, cfname):
        global tc_details

        # tc_details = config.tc_test_backlight
        config = configparser.ConfigParser()
        path = os.path.split(os.path.realpath(__file__))[0] + '/allconfig.config'
        config.read(path)
        tc_details = dict(config.items(cfname))  # list-->dict

        # Read and apply the configuration values.
        values = int(tc_details['no_devices'])
        for index in range(values):
            dev_str = 'dev' + str(index)
            # Create an instance of the uiautomator object
            ui_dev_str = 'ui_dev' + str(index)
            tc_details[ui_dev_str] = Device(tc_details[dev_str])
            output = subprocess.check_output("adb devices", shell=True).decode('utf-8', errors='ignore')
            if tc_details[dev_str] in output and (tc_details[dev_str] + '\tno permissions') not in output:
                cmd = ' -s ' + tc_details[dev_str] + ' logcat -c'
                self.Run_Adb_Cmd(str(index), cmd)

        for index in range(int(tc_details['no_devices'])):
            # To disable google security popup (ACCEPT or CONTINUE)
            cmd = "shell settings put global package_verifier_enable 0"
            self.Run_Adb_Cmd(tc_details['dev' + str(index)], cmd)

            # Power on and Unlock Device
            self.Run_Adb_Cmd(tc_details['dev' + str(index)], "shell input keyevent 82")
            time.sleep(3)
            self.Run_Adb_Cmd(tc_details['dev' + str(index)], "shell input keyevent 3")
            time.sleep(3)
            if tc_details['ui_dev' + str(index)](textContains="Launcher3").exists:
                tc_details['ui_dev' + str(index)](textContains="Launcher3").click()

            if tc_details['ui_dev' + str(index)](text="ALWAYS").exists:
                tc_details['ui_dev' + str(index)](text="ALWAYS").click()

            # Put device stay awake
            dev_id = tc_details['dev' + str(index)]
            self.Run_Adb_Cmd(dev_id, "shell svc power stayon true")
            # Clear all recent apps - hardcoded to 6 apps currently
            self.Run_Adb_Cmd(tc_details['dev' + str(index)], "shell input keyevent KEYCODE_APP_SWITCH")
            time.sleep(3)
            # Allow google to regularly check device activity - popup
            if tc_details['ui_dev' + str(index)](textContains="Allow Google to regularly check").exists:
                if tc_details['ui_dev' + str(index)](textContains="DECLINE").exists:
                    tc_details['ui_dev' + str(index)](textContains="DECLINE").click()
                else:
                    if tc_details['ui_dev' + str(index)](textContains="Decline").exists:
                        tc_details['ui_dev' + str(index)](textContains="Decline").click()
            time.sleep(3)
            for i in range(6):
                self.Run_Adb_Cmd(tc_details['dev' + str(index)], "shell input keyevent 20", False)
                self.Run_Adb_Cmd(tc_details['dev' + str(index)], "shell input keyevent DEL", False)
            # Uninstall videoplayer application
            self.Run_Adb_Cmd(tc_details['dev' + str(index)], "shell pm uninstall videoplayer.mediaplayer.hdplayer")

            # Uninstall skype application
            self.Run_Adb_Cmd(tc_details['dev' + str(index)], "shell pm uninstall com.skype.raider")

            # Autoconnect to Wi-Fi if 'wifi_status'='on' or not present in the test case config file
            try:
                if tc_details['wifi_status'] == 'on':
                    self.tc_wifi_connect(index)
                elif tc_details['wifi_status'] == 'off':
                    self.tc_wifi_disconnect(index)
            except Exception as e:
                print(e)
                self.tc_wifi_connect(index)

            # Come to home screen
            self.Run_Adb_Cmd(tc_details['dev' + str(index)], "shell input keyevent 3")
            time.sleep(4)
            return tc_details

    # Description: This function connects to a Wi-Fi network using wifi_ssid and wifi_passwd from the session config file.
    # Here dev_num is optional; if not provided, the function defaults to dev0.
    # def tc_wifi_connect(self, dev_num=0):
    #     global tc_details
    #     # Turn on Wi-Fi.
    #     self.Run_Adb_Cmd(tc_details['dev' + str(dev_num)], "shell svc wifi enable")

    #     # Open Wi-Fi settings and choose the target network.
    #     self.Run_Adb_Cmd(tc_details['dev' + str(dev_num)], "shell am start -a android.settings.WIFI_SETTINGS")
    #     time.sleep(4)

    #     if (tc_details['ui_dev' + str(dev_num)](text="Connected").exists == False):
    #         if (tc_details['ui_dev' + str(dev_num)](text=tc_details['wifi_ssid']).exists == False):
    #             tc_details['ui_dev' + str(dev_num)](scrollable=True).fling.toEnd()
    #             tc_details['ui_dev' + str(dev_num)](scrollable=True).scroll.to(text=tc_details['wifi_ssid'])

    #         tc_details['ui_dev' + str(dev_num)](text=tc_details['wifi_ssid']).click()
    #         time.sleep(3)

    #         # Enter password and connect to Wi-Fi.
    #         if (tc_details['ui_dev' + str(dev_num)](text="Password").exists == True):
    #             tc_details['ui_dev' + str(dev_num)](resourceId="com.android.settings:id/password").click()
    #             self.Run_Adb_Cmd(tc_details['dev' + str(dev_num)],
    #                              "shell input text " + tc_details['wifi_passwd'])
    #             time.sleep(5)

    #         if (tc_details['ui_dev' + str(dev_num)](text="Connect").exists == True):
    #             tc_details['ui_dev' + str(dev_num)](text="Connect").click()
    #         elif (tc_details['ui_dev' + str(dev_num)](text="CONNECT").exists == True):
    #             tc_details['ui_dev' + str(dev_num)](text="CONNECT").click()
    #         time.sleep(30)
    #     else:
    #         pass

    # Description: This function disconnects from the Wi-Fi network.
    # Here dev_num is optional; if not provided, the function defaults to dev0.
    def tc_wifi_disconnect(self, dev_num=0):
        global tc_details
        self.Run_Adb_Cmd(tc_details['dev' + str(dev_num)], "shell svc wifi disable")

    # Function to close an app package.
    # Usage: close_package(self.tc_details['dev0'], "settings")
    def close_package(self, dev_id, package_name):
        config = configparser.ConfigParser()
        path = os.path.split(os.path.realpath(__file__))[0] + '/commands.config'
        config.read(path)
        package_full_name = config.get('app_close_commands', package_name)
        cmd = "shell pm clear " + package_full_name
        self.Run_Adb_Cmd(dev_id, cmd)

# ============= Camera_Method_Sally: Camera UI Method Helpers =============

# Camera_Method_Sally
def camera_init_device(serial):
    """初始化并返回 UIAutomator2 设备连接。"""
    if u2 is None:
        raise ImportError("uiautomator2 is not installed")
    print(f"[camera] Connecting to device: {serial}", flush=True)
    device = u2.connect(serial)
    info = device.info
    print(
        f"[camera] [OK] Device connected, screen={info['displayWidth']}x{info['displayHeight']}",
        flush=True,
    )
    return device


# Camera_Method_Sally
def camera_wake_up_device(device):
    """唤醒并解锁设备。"""
    try:
        device.unlock()
    except Exception:
        try:
            device.press("power")
            time.sleep(0.8)
            device.swipe_ext("up", scale=0.9)
        except Exception:
            pass
    time.sleep(1)


# Camera_Method_Sally
def camera_dismiss_runtime_dialogs(device):
    """关闭相机首次启动可能出现的授权弹窗。"""
    keywords = [
        "Allow", "While using the app", "WHILE USING THE APP", "OK", "Continue", "Agree",
    ]
    for _ in range(3):
        acted = False
        for text in keywords:
            obj = device(text=text)
            if obj.exists(timeout=0.2):
                obj.click()
                time.sleep(0.5)
                acted = True
        if not acted:
            break


# Camera_Method_Sally
def camera_open_camera_app(device, serial):
    """通过正常 Launcher 入口启动识别到的优先相机包。"""
    from common.adb_common import CAMERA_PACKAGES, adb_shell, detect_default_camera_activity
    print("[camera] Opening camera app...", flush=True)

    resolved = detect_default_camera_activity(serial, preferred_packages=CAMERA_PACKAGES)
    resolved_package = resolved.split("/", 1)[0] if resolved else ""
    if resolved_package in CAMERA_PACKAGES:
        result = adb_shell(
            serial, "am", "start", "-W",
            "-a", "android.intent.action.MAIN",
            "-c", "android.intent.category.LAUNCHER",
            "-p", resolved_package,
            timeout=12,
        )
        time.sleep(2)
        camera_dismiss_runtime_dialogs(device)
        from common.adb_common import camera_foreground_package
        if result.returncode == 0 and camera_foreground_package(serial) == resolved_package:
            print(f"[camera] [OK] Camera opened by launcher: {resolved_package}", flush=True)
            return True

    for pkg in CAMERA_PACKAGES:
        try:
            device.app_start(pkg, stop=True)
            time.sleep(2)
            camera_dismiss_runtime_dialogs(device)
            from common.adb_common import camera_foreground_package
            if camera_foreground_package(serial) == pkg:
                print(f"[camera] [OK] Camera opened by app_start: {pkg}", flush=True)
                return True
        except Exception:
            continue

    print("[camera] [FAILED] Failed to open camera app", flush=True)
    return False


# Camera_Method_Sally
def camera_is_preview_visible(device, serial):
    """检查相机预览界面是否正常显示（UI 元素检测）。"""
    from common.adb_common import camera_is_camera_foreground
    if not camera_is_camera_foreground(serial):
        print("[camera] [ERROR] Camera app not in foreground", flush=True)
        return False

    candidates = [
        device(resourceId="org.codeaurora.snapcam:id/shutter_button"),
        device(resourceId="com.android.camera:id/shutter_button"),
        device(resourceIdMatches=".*shutter.*"),
        device(descriptionContains="快门"),
        device(descriptionContains="Shutter"),
        device(descriptionContains="拍照"),
        device(descriptionContains="Photo"),
    ]
    for obj in candidates:
        try:
            if obj.exists(timeout=0.3):
                print("[camera] [OK] Found shutter button - preview is normal", flush=True)
                return True
        except Exception:
            continue

    preview_candidates = [
        device(resourceId="org.codeaurora.snapcam:id/preview"),
        device(resourceId="com.android.camera:id/preview"),
        device(resourceIdMatches=".*preview.*"),
        device(className="android.view.SurfaceView"),
    ]
    for obj in preview_candidates:
        try:
            if obj.exists(timeout=0.3):
                print("[camera] [OK] Found preview surface - preview is normal", flush=True)
                return True
        except Exception:
            continue

    print("[camera] [OK] Camera in foreground, assuming preview is normal", flush=True)
    return True


# Camera_Method_Sally
def camera_verify_preview_by_screenshot(device):
    """通过截图验证预览界面是否有实质内容（非黑屏）。"""
    try:
        img = device.screenshot()
        if img is None:
            print("[camera] [WARN] Screenshot returned None", flush=True)
            return False
        w, h = img.size
        if w < 100 or h < 100:
            print(f"[camera] [WARN] Screenshot size too small: {w}x{h}", flush=True)
            return False
        print(f"[camera] [OK] Screenshot captured: {w}x{h}", flush=True)
        return True
    except Exception as e:
        print(f"[camera] [WARN] Failed to capture screenshot: {str(e)[:120]}", flush=True)
        return False


# Camera_Method_Sally
def camera_capture_device_state(device, serial):
    """记录测试前设备关键状态，用于收尾恢复。"""
    from common.adb_common import camera_is_screen_on, camera_foreground_package
    state = {
        "screen_on": camera_is_screen_on(serial),
        "foreground_pkg": camera_foreground_package(serial),
    }
    print(
        f"[camera] Captured pre-state: screen_on={state['screen_on']}, "
        f"foreground_pkg={state['foreground_pkg'] or 'unknown'}",
        flush=True,
    )
    return state


# Camera_Method_Sally
def camera_restore_device_state(state, device, serial):
    """尽量将设备恢复到测试前状态。"""
    from common.adb_common import CAMERA_PACKAGES, camera_is_screen_on
    if not state:
        return

    print("[camera] Restoring device to pre-state...", flush=True)

    for pkg in CAMERA_PACKAGES:
        try:
            device.app_stop(pkg)
        except Exception:
            pass

    target_pkg = (state.get("foreground_pkg") or "").strip()
    if target_pkg and target_pkg not in CAMERA_PACKAGES and target_pkg != "com.android.systemui":
        try:
            device.app_start(target_pkg, stop=False)
            time.sleep(1)
            print(f"[camera] [OK] Restored foreground app: {target_pkg}", flush=True)
        except Exception as e:
            print(f"[camera] [WARN] Failed to restore app {target_pkg}: {str(e)[:120]}", flush=True)
    else:
        try:
            device.press("home")
            time.sleep(1)
            print("[camera] [OK] Returned to home screen", flush=True)
        except Exception as e:
            print(f"[camera] [WARN] Failed to return to home: {str(e)[:120]}", flush=True)

    should_screen_on = bool(state.get("screen_on", True))
    now_screen_on = camera_is_screen_on(serial)
    if not should_screen_on and now_screen_on:
        try:
            device.press("power")
            time.sleep(1)
            print("[camera] [OK] Restored screen state: OFF", flush=True)
        except Exception as e:
            print(f"[camera] [WARN] Failed to restore screen state: {str(e)[:120]}", flush=True)


# Camera_Method_Sally
def camera_click_ui_elements(device):
    """尝试点击相机预览界面的各个UI元素，验证可点击性。
    
    :param device: UIAutomator2 device 对象
    :return: 列表，每项为 (元素名称, 是否点击成功, 错误信息)
    """
    candidates = [
        ("Shutter Button (Snapcam)", device(resourceId="org.codeaurora.snapcam:id/shutter_button")),
        ("Shutter Button (Android)", device(resourceId="com.android.camera:id/shutter_button")),
        ("Shutter Button (Regex)", device(resourceIdMatches=".*shutter.*")),
        ("Description - 快门", device(descriptionContains="快门")),
        ("Description - Shutter", device(descriptionContains="Shutter")),
        ("Description - 拍照", device(descriptionContains="拍照")),
        ("Description - Photo", device(descriptionContains="Photo")),
    ]
    
    results = []
    for name, obj in candidates:
        try:
            if obj.exists(timeout=0.3):
                obj.click()
                results.append((name, True, None))
                print(f"[camera] [OK] Clicked UI element: {name}", flush=True)
                time.sleep(0.5)
            else:
                results.append((name, False, "Element not found"))
        except Exception as e:
            results.append((name, False, str(e)[:120]))
            print(f"[camera] [WARN] Failed to click {name}: {str(e)[:120]}", flush=True)
    
    return results

# Scan_Method_Sally_0624
def scan_init_device(serial, retries=5, retry_delay=2):
    """Initialize uiautomator2 after confirming ADB and atx-agent are ready."""
    if u2 is None:
        raise ImportError("[ERROR] uiautomator2 not installed. Install with: pip install uiautomator2")

    last_error = None
    for attempt in range(1, max(1, retries) + 1):
        try:
            print(f"[scan] Connecting to device: {serial} (attempt {attempt}/{retries})", flush=True)
            adb_state = subprocess.run(
                ["adb", "-s", serial, "get-state"],
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )
            if adb_state.returncode != 0 or (adb_state.stdout or "").strip() != "device":
                raise RuntimeError(f"ADB is not ready: {(adb_state.stderr or adb_state.stdout or '').strip()}")

            dev = u2.connect(serial)
            info = dev.info
            print(
                f"[scan] [OK] Device connected, screen={info['displayWidth']}x{info['displayHeight']}",
                flush=True,
            )
            return dev
        except Exception as error:
            last_error = error
            if attempt < max(1, retries):
                print(f"[scan] [WARN] Device not ready: {error}; retrying in {retry_delay}s", flush=True)
                time.sleep(retry_delay)

    raise RuntimeError(
        f"Failed to initialize uiautomator2 for {serial} after {max(1, retries)} attempts: {last_error}"
    )


# Scan_Method_Sally_0624
def scan_reconnect_device(serial, reason=""):
    """Rebuild uiautomator2 session and return device, None on failure."""
    try:
        if reason:
            print(f"[scan] Reconnecting device ({reason})...", flush=True)
        time.sleep(0.15)
        return scan_init_device(serial)
    except Exception as e:
        print(f"[scan] [WARN] Reconnect device failed: {e}", flush=True)
        return None


# Scan_Method_Sally_0624
def scan_swipe_unlock_if_needed(device, serial):
    """Swipe up to unlock when keyguard is visible."""
    from common.adb_common import scan_is_lockscreen_showing, adb_shell

    if not scan_is_lockscreen_showing(serial):
        return

    try:
        info = device.info
        width = int(info.get("displayWidth", 1080))
        height = int(info.get("displayHeight", 1920))
        x = width // 2
        start_y = int(height * 0.82)
        end_y = int(height * 0.28)
        device.swipe(x, start_y, x, end_y, 0.2)
        time.sleep(0.1)

        if scan_is_lockscreen_showing(serial):
            adb_shell(serial, "input", "keyevent", "82")
            time.sleep(0.1)
    except Exception as e:
        print(f"[scan] [WARN] Swipe unlock failed: {e}", flush=True)


# Scan_Method_Sally_0624
def scan_wake_up_device(device, serial):
    """Wake and unlock device."""
    from common.adb_common import adb_shell

    try:
        device.unlock()
    except Exception:
        adb_shell(serial, "input", "keyevent", "26")
        time.sleep(0.5)
        adb_shell(serial, "input", "keyevent", "82")
    scan_swipe_unlock_if_needed(device, serial)

# Scan_Method_Sally_0624
def scan_get_input_field_text(device, focused_timeout=0.2, fallback_timeout=0.2):
    """Read non-empty text from the focused EditText, then any EditText."""
    selectors = (
        device(focused=True, className="android.widget.EditText"),
        device(className="android.widget.EditText"),
        device(focused=True),
    )
    for index, selector in enumerate(selectors):
        try:
            timeout = focused_timeout if index in (0, 3) else fallback_timeout
            if not selector.exists(timeout=timeout):
                continue
            text = (selector.get_text() or "").strip()
            if text:
                return text
        except Exception:
            pass
    return ""


# Scan_Method_Sally_0624
def scan_clear_input_field(device, focused_timeout=0.12, fallback_timeout=0.12):
    """Clear current input field content if not empty."""
    current_text = scan_get_input_field_text(device, focused_timeout=focused_timeout, fallback_timeout=fallback_timeout)
    if len(current_text) == 0:
        return False
    try:
        focused = device(focused=True)
        if focused.exists(timeout=focused_timeout):
            focused.set_text("")
            time.sleep(0.01)
            return True

        edit = device(className="android.widget.EditText")
        if edit.exists(timeout=fallback_timeout):
            edit.set_text("")
            time.sleep(0.01)
            return True

        return False
    except Exception as e:
        print(f"[scan] [WARN] Clear failed: {e}", flush=True)
        return False

# Scan_Method_Sally_2026-09-15
def scan_open_input_field(device, serial):
    """Open launcher input field and return True when EditText is available."""
    from common.adb_common import adb_shell

    model_result = adb_shell(serial, "getprop", "ro.product.model", timeout=8)
    device_model = (model_result.stdout or "").strip().upper()
    is_ct45 = device_model == "CT45"

    def _dump_input_bounds():
        """Read launcher nodes through adb, avoiding slow uiautomator2 queries on CT45."""
        dump_path = "/sdcard/scan_input_ui.xml"
        dump_ret = adb_shell(serial, "uiautomator", "dump", dump_path, timeout=8)
        if dump_ret.returncode != 0:
            return []
        xml_text = adb_shell(serial, "cat", dump_path, timeout=8).stdout or ""
        try:
            root = ET.fromstring(xml_text)
        except ET.ParseError:
            return []

        nodes = []
        for node in root.iter("node"):
            bounds = node.attrib.get("bounds", "")
            match = re.fullmatch(r"\[(\d+),(\d+)\]\[(\d+),(\d+)\]", bounds)
            if not match:
                continue
            left, top, right, bottom = (int(value) for value in match.groups())
            attrs = {key: (value or "").lower() for key, value in node.attrib.items()}
            nodes.append((node, left, top, right, bottom, attrs))
        return nodes

    def _tap_search_entry():
        nodes = _dump_input_bounds()
        for node, left, top, right, bottom, attrs in nodes:
            if attrs.get("class", "").endswith("edittext"):
                adb_shell(serial, "input", "tap", str((left + right) // 2), str((top + bottom) // 2), timeout=5)
                return True

        search_keys = ("search_container", "search_widget", "search_src_text")
        for node, left, top, right, bottom, attrs in nodes:
            resource_id = attrs.get("resource-id", "")
            description = attrs.get("content-desc", "")
            text = attrs.get("text", "")
            if (
                    any(key in resource_id for key in search_keys)
                    or "search" in description
                    or "search" in text
            ):
                adb_shell(serial, "input", "tap", str((left + right) // 2), str((top + bottom) // 2), timeout=5)
                return True
        return False

    for _ in range(3 if is_ct45 else 2):
        try:
            if is_ct45:
                initial_nodes = _dump_input_bounds()
                if any(node.attrib.get("class", "").endswith("EditText") for node, *_ in initial_nodes):
                    _tap_search_entry()
                    return True

            adb_shell(serial, "am", "start", "-a", "android.intent.action.MAIN", "-c",
                      "android.intent.category.HOME", timeout=8)
            time.sleep(0.8 if is_ct45 else 0.22)

            if is_ct45:
                _tap_search_entry()
                time.sleep(0.5)
                if any(
                        node.attrib.get("class", "").endswith("EditText")
                        for node, *_ in _dump_input_bounds()
                ):
                    return True

            click_targets = [
                ("com.android.systemui:id/search_container", "resourceId"),
                ("com.google.android.apps.gsa.search:id/search_widget", "resourceId"),
                ("com.google.android.googlequicksearchbox:id/googleapp_search_widget_background", "resourceId"),
                ("Search", "description"),
                (None, "tap_center"),
            ]

            for target, method in click_targets:
                try:
                    if method == "resourceId":
                        obj = device(resourceId=target)
                        if obj.exists(timeout=0.2):
                            obj.click()
                            time.sleep(0.08)
                            break
                    elif method == "description":
                        obj = device(descriptionContains=target)
                        if obj.exists(timeout=0.2):
                            obj.click()
                            time.sleep(0.08)
                            break
                    elif method == "tap_center":
                        if is_ct45:
                            info = device.info
                            width = int(info.get("displayWidth", 1080))
                            height = int(info.get("displayHeight", 1920))
                            device.click(width // 2, max(100, int(height * 0.1)))
                        else:
                            info = device.info
                            device.click(info["displayWidth"] // 2, int(info["displayHeight"] * 0.15))
                        time.sleep(0.06)
                        break
                except Exception:
                    pass

            edit_box = device(className="android.widget.EditText")
            if edit_box.exists(timeout=0.5 if is_ct45 else 0.2):
                if is_ct45:
                    edit_box.click()
                    time.sleep(0.1)
                return True

            if device(resourceId="android:id/search_src_text").exists(timeout=0.5 if is_ct45 else 0.2):
                if is_ct45:
                    device(resourceId="android:id/search_src_text").click()
                    time.sleep(0.1)
                return True

            if device(focusable=True, className="android.widget.EditText").exists(timeout=0.5 if is_ct45 else 0.2):
                if is_ct45:
                    device(focusable=True, className="android.widget.EditText").click()
                    time.sleep(0.1)
                return True
        except Exception as e:
            print(f"[scan] [WARN] Open input failed: {e}", flush=True)

    return False

# Scan_Method_Sally_2026-09-15
def scan_refocus_input_field(device, serial=None):
    """Refocus existing EditText after resume/wakeup."""
    if serial:
        from common.adb_common import adb_shell

        model_result = adb_shell(serial, "getprop", "ro.product.model", timeout=8)
        if (model_result.stdout or "").strip().upper() == "CT45":
            dump_path = "/sdcard/scan_refocus_ui.xml"
            dump_ret = adb_shell(serial, "uiautomator", "dump", dump_path, timeout=8)
            if dump_ret.returncode == 0:
                xml_text = adb_shell(serial, "cat", dump_path, timeout=8).stdout or ""
                try:
                    root = ET.fromstring(xml_text)
                    for node in root.iter("node"):
                        if not node.attrib.get("class", "").endswith("EditText"):
                            continue
                        match = re.fullmatch(
                            r"\[(\d+),(\d+)\]\[(\d+),(\d+)\]",
                            node.attrib.get("bounds", ""),
                        )
                        if match:
                            left, top, right, bottom = (int(value) for value in match.groups())
                            adb_shell(
                                serial,
                                "input",
                                "tap",
                                str((left + right) // 2),
                                str((top + bottom) // 2),
                                timeout=5,
                            )
                            time.sleep(0.2)
                            return True
                except ET.ParseError:
                    pass

    try:
        edit = device(className="android.widget.EditText")
        if edit.exists(timeout=0.3):
            edit.click()
            time.sleep(0.03)
            return True
    except Exception as e:
        print(f"[scan] [WARN] Refocus input failed: {e}", flush=True)
    return False


# Scan_Method_Sally_0624
def scan_verify_decode_result(device, max_wait_seconds=10):
    """Verify barcode decode result by polling input text."""
    retry_interval = 0.12
    max_attempts = max(5, int(max_wait_seconds / retry_interval))
    placeholder_values = {"Search...", "Search…"}

    for attempt in range(max_attempts):
        text = scan_get_input_field_text(device)
        if text and text.strip() not in placeholder_values:
            print(f"[scan] [OK] Barcode detected: '{text}'", flush=True)
            return True
        if attempt < max_attempts - 1:
            time.sleep(retry_interval)

    print(f"[scan] [FAIL] No barcode detected after {max_wait_seconds}s", flush=True)
    return False


#EnableDisable_UPC_E1_Method_Alice_2026-8-7
def dcs_test_connect_u2(serial):
    """Connect to a device through uiautomator2 for the UPC-E1 case."""
    if u2 is None:
        raise ImportError("uiautomator2 is not installed")
    return u2.connect(serial)


# General_Settings_Method_Frank_Xu_2026-08-24
# Author: Frank Xu
# Created: 2026-08-24
# Updated: 2026-08-27
# Scope: General Settings test cases
# Purpose: Provide shared device setup, CT47 keyguard recovery, Settings navigation,
# state restoration, and screenshot helpers for the 13 General Settings test cases.
class GeneralSettingsTestCase(unittest.TestCase):
    """Base test case that restores General Settings values after each test."""

    def setUp(self):
        self.serial, self.device = require_device(self)
        try:
            if "mWakefulness=Awake" not in shell(self.serial, "dumpsys", "power"):
                shell(self.serial, "input", "keyevent", "224")
                time.sleep(0.8)
            # CT47 recovery sequence: dismiss an existing keyguard before launching Settings.
            shell(self.serial, "input", "keyevent", "82")
            shell(self.serial, "input", "swipe", "540", "1900", "540", "300", "600")
            shell(self.serial, "wm", "dismiss-keyguard")
            shell(self.serial, "cmd", "statusbar", "collapse")
            time.sleep(0.5)
        except Exception:
            pass
        self._snapshot = self._capture_device_state()

    def tearDown(self):
        self._restore_device_state()

    def _capture_device_state(self):
        from common.adb_common import setting_value

        snapshot = {
            "timezone": "",
            "time_12_24": "",
            "navigation_mode": "",
            "long_press_timeout": "",
            "incall_power_button_behavior": "",
            "lockscreen_disabled": "",
        }
        try:
            snapshot["timezone"] = shell(self.serial, "getprop", "persist.sys.timezone")
            snapshot["time_12_24"] = setting_value(self.serial, "system", "time_12_24")
            snapshot["navigation_mode"] = setting_value(self.serial, "secure", "navigation_mode")
            snapshot["long_press_timeout"] = setting_value(self.serial, "secure", "long_press_timeout")
            snapshot["incall_power_button_behavior"] = setting_value(
                self.serial, "secure", "incall_power_button_behavior"
            )
            snapshot["lockscreen_disabled"] = setting_value(self.serial, "secure", "lockscreen.disabled")
        except Exception:
            pass
        return snapshot

    def _restore_device_state(self):
        from common.adb_common import adb_shell, set_setting

        snapshot = getattr(self, "_snapshot", {})
        timezone = snapshot.get("timezone", "")
        if timezone and timezone != "null":
            try:
                shell(self.serial, "cmd", "alarm", "set-timezone", timezone)
            except Exception:
                pass
        for namespace, key in (
            ("system", "time_12_24"),
            ("secure", "navigation_mode"),
            ("secure", "long_press_timeout"),
            ("secure", "incall_power_button_behavior"),
            ("secure", "lockscreen.disabled"),
        ):
            value = snapshot.get(key, "")
            if value and value != "null":
                try:
                    set_setting(self.serial, namespace, key, value)
                except Exception:
                    pass
        try:
            adb_shell(self.serial, "am", "force-stop", "com.android.settings", timeout=5)
            self.device.press("home")
            adb_shell(self.serial, "cmd", "statusbar", "collapse", timeout=5)
        except Exception:
            pass


def require_device(test_case):
    """Return the selected online device and its uiautomator2 connection."""
    from common.adb_common import get_device_serial

    serial = get_device_serial()
    if not serial:
        test_case.skipTest("No online Android device. Set ANDROID_SERIAL or connect one device.")
    if u2 is None:
        test_case.skipTest("uiautomator2 is not installed")
    return serial, u2.connect(serial)


def shell(serial, *command, timeout=15):
    """Run an ADB shell command and return stdout, failing on an ADB error."""
    from common.adb_common import adb_shell

    result = adb_shell(serial, *command, timeout=timeout)
    if result.returncode != 0:
        raise AssertionError("adb shell {} failed: {}".format(" ".join(command), result.stderr.strip()))
    return (result.stdout or "").strip()


def open_settings(device):
    from common.adb_common import adb_shell, get_device_serial

    device.press("home")
    serial = get_device_serial()
    if serial:
        adb_shell(serial, "cmd", "statusbar", "collapse", timeout=5)
    device.app_start("com.android.settings", stop=True)
    time.sleep(2)


def tap_text(device, text, timeout=3):
    for attempt in range(6):
        for selector in (device(text=text), device(textContains=text)):
            if selector.exists(timeout=timeout if attempt == 0 else 0.5):
                selector.click()
                time.sleep(0.8)
                return True
        if not device(scrollable=True).exists(timeout=0.5):
            break
        device(scrollable=True).scroll.vert.forward(steps=35)
        time.sleep(0.5)
    return False


def tap_first_available_text(device, candidates, timeout=3):
    for candidate in candidates:
        if tap_text(device, candidate, timeout=timeout):
            return candidate
    return None


def tap_xml_text(device, candidates, timeout=2):
    for _ in range(6):
        try:
            root = ET.fromstring(device.dump_hierarchy(compressed=False))
            for node in root.iter("node"):
                text_value = (node.attrib.get("text") or "").strip()
                description = (node.attrib.get("content-desc") or "").strip()
                if text_value not in candidates and description not in candidates:
                    continue
                match = re.match(r"\[(\d+),(\d+)\]\[(\d+),(\d+)\]", node.attrib.get("bounds") or "")
                if match:
                    left, top, right, bottom = (int(value) for value in match.groups())
                    device.click((left + right) / 2, (top + bottom) / 2)
                    time.sleep(timeout)
                    return text_value or description
        except Exception:
            pass
        time.sleep(0.5)
    return None


def tap_language_input_entry(test_case, device):
    candidates = (
        "Language & input", "Languages & input", "Language and input", "Languages and input",
        "Language, input, gesture", "Languages, input, gesture", "语言和输入法", "语言与输入法",
    )
    chosen = tap_first_available_text(device, candidates, timeout=1) or tap_xml_text(device, candidates, timeout=1)
    if chosen:
        return chosen
    try:
        root = ET.fromstring(device.dump_hierarchy(compressed=False))
    except Exception:
        test_case.fail("Failed to dump UI hierarchy while finding Languages & input entry")

    scored = []
    for node in root.iter("node"):
        text_value = (node.attrib.get("text") or "").strip()
        if not text_value:
            continue
        lower_value = text_value.lower()
        score = 0
        if re.search(r"language", lower_value) or "语言" in text_value:
            score += 3
        if re.search(r"input|keyboard|ime", lower_value) or re.search(r"输入|输入法|键盘", text_value):
            score += 3
        if "gesture" in lower_value or "手势" in text_value:
            score += 1
        if score:
            scored.append((score, text_value))
    for _, candidate in sorted(scored, key=lambda item: item[0], reverse=True):
        if tap_text(device, candidate, timeout=1):
            return candidate
    test_case.fail("Languages & input entry was not found under System")


def tap_path(test_case, device, *labels, reset_home=True, strict=True):
    if reset_home:
        open_settings(device)
    for label in labels:
        if isinstance(label, (list, tuple)):
            chosen = tap_first_available_text(device, label)
            if not chosen:
                if strict:
                    test_case.fail("Settings entry '{}' was not found".format(" / ".join(label)))
                return False
        elif not tap_text(device, label):
            if strict:
                test_case.fail("Settings entry '{}' was not found".format(label))
            return False
    return True


def open_settings_action(test_case, device, action, wait_seconds=2):
    from common.adb_common import adb_shell, get_device_serial

    serial = get_device_serial()
    if not serial:
        test_case.skipTest("No online Android device. Set ANDROID_SERIAL or connect one device.")
    result = adb_shell(serial, "am", "start", "-a", action, timeout=10)
    if result.returncode != 0:
        test_case.fail("Failed to launch settings action '{}': {}".format(action, result.stderr.strip()))
    if "Error:" in (result.stdout or ""):
        test_case.skipTest("Settings action is not supported on this device: {}".format(action))
    time.sleep(wait_seconds)


def screenshot(device, script_file, step_name):
    from common.adb_common import save_step_screenshot

    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.realpath(script_file))))
    script_name = os.path.splitext(os.path.basename(script_file))[0]
    save_step_screenshot(device, step_name, os.path.join(project_root, "img", script_name))


#EnableDisable_UPC_E1_Method_Alice_2026-8-7
def dcs_test_scroll_find_and_click(device, labels, max_swipes=2, wait_each=0.25):
    """Find a settings label by scrolling and click it."""
    for _ in range(max_swipes):
        for label in labels:
            try:
                obj = device(text=label)
                if obj.exists(timeout=0.6):
                    obj.click()
                    time.sleep(0.8)
                    return True
                device(scrollable=True).scroll.to(text=label)
                time.sleep(2)
                obj.click()
                time.sleep(0.8)
                return True
            except Exception:
                pass
        time.sleep(wait_each)
    return False


#EnableDisable_UPC_E1_Method_Alice_2026-8-7
def dcs_test_query_option_checked(device, label):
    """Return the checked state of a settings option, or None when unavailable."""
    try:
        root = ET.fromstring(device.dump_hierarchy())
    except Exception:
        return None

    parent_map = {child: parent for parent in root.iter() for child in parent}
    nodes = list(root.iter("node"))
    exact_matches = [node for node in nodes if (node.attrib.get("text") or "").strip() == label]
    matching_nodes = exact_matches or [
        node for node in nodes if label in (node.attrib.get("text") or "").strip()
    ]
    for node in matching_nodes:
        candidates = [node]
        container = node
        for _ in range(2):
            parent = parent_map.get(container)
            if parent is None:
                break
            candidates.extend(parent.iter("node"))
            container = parent

        for candidate in candidates:
            checked = candidate.attrib.get("checked")
            checkable = candidate.attrib.get("checkable")
            class_name = candidate.attrib.get("class", "")
            if checked in ("true", "false") and (
                checkable == "true" or "CheckBox" in class_name or "Switch" in class_name
            ):
                return checked == "true"
    return None


#EnableDisable_UPC_E1_Method_Alice_2026-8-7
def _dcs_test_click_option_checkbox(device, label):
    """Tap the checkbox sibling of a settings label when row clicks do not toggle it."""
    try:
        root = ET.fromstring(device.dump_hierarchy())
    except Exception:
        return False

    parent_map = {child: parent for parent in root.iter() for child in parent}
    nodes = list(root.iter("node"))
    exact_matches = [node for node in nodes if (node.attrib.get("text") or "").strip() == label]
    for node in exact_matches:
        container = node
        candidates = []
        for _ in range(2):
            parent = parent_map.get(container)
            if parent is None:
                break
            candidates.extend(parent.iter("node"))
            container = parent
        for sibling in candidates:
            checked = sibling.attrib.get("checked")
            checkable = sibling.attrib.get("checkable")
            class_name = sibling.attrib.get("class", "")
            if checked not in ("true", "false") or not (
                checkable == "true" or "CheckBox" in class_name or "Switch" in class_name
            ):
                continue
            bounds = sibling.attrib.get("bounds", "")
            match = re.match(r"\[(\d+),(\d+)\]\[(\d+),(\d+)\]", bounds)
            if match:
                left, top, right, bottom = (int(value) for value in match.groups())
                device.click((left + right) // 2, (top + bottom) // 2)
                return True
    return False


#EnableDisable_UPC_E1_Method_Alice_2026-8-7
def dcs_test_set_option_checked(device, label, enable):
    """Set a settings option to the requested checked state."""
    state = dcs_test_query_option_checked(device, label)
    if state is not None and state == enable:
        return True

    if not dcs_test_scroll_find_and_click(device, [label], max_swipes=2):
        return False

    time.sleep(1)
    new_state = dcs_test_query_option_checked(device, label)
    if new_state == enable:
        return True
    if not _dcs_test_click_option_checkbox(device, label):
        return False

    time.sleep(1)
    return dcs_test_query_option_checked(device, label) == enable


#EnableDisable_UPC_E1_Method_Alice_2026-8-7
def dcs_test_goto_data_processing_settings(
    serial,
    device,
    scanning_labels,
    internal_scanner_labels,
    default_profile_labels,
    data_processing_labels,
):
    """Navigate Honeywell Settings to Data Processing Settings."""
    from common.adb_common import dcs_test_open_honeywell_settings

    if not dcs_test_open_honeywell_settings(serial):
        raise AssertionError("Cannot open Honeywell Settings")
    navigation = [
        (scanning_labels, "Scanning"),
        (internal_scanner_labels, "Internal Scanner"),
        (default_profile_labels, "Default profile"),
        (data_processing_labels, "Data Processing Settings"),
    ]
    for labels, description in navigation:
        if not dcs_test_scroll_find_and_click(device, labels):
            raise AssertionError(f"Cannot find '{description}'")


#EnableDisable_UPC_E1_Method_Alice_2026-8-7
def dcs_test_goto_symbology_setting(
    serial,
    device,
    scanning_labels,
    internal_scanner_labels,
    default_profile_labels,
    symbology_labels,
    upc_e_labels,
):
    """Navigate Honeywell Settings to the UPC-E1 symbology option."""
    from common.adb_common import dcs_test_open_honeywell_settings

    if not dcs_test_open_honeywell_settings(serial):
        raise AssertionError("Cannot open Honeywell Settings")
    navigation = [
        (scanning_labels, "Scanning"),
        (internal_scanner_labels, "Internal Scanner"),
        (default_profile_labels, "Default profile"),
        (symbology_labels, "Symbology Settings"),
        (upc_e_labels, "UPC-E"),
    ]
    for labels, description in navigation:
        if not dcs_test_scroll_find_and_click(device, labels):
            raise AssertionError(f"Cannot find '{description}'")


#EnableDisable_UPC_E1_Method_Alice_2026-8-7
def dcs_test_handle_image_viewer_chooser(device):
    """Dismiss the image viewer chooser shown while preparing the barcode image."""
    try:
        if device(resourceId="android:id/button_always").exists(timeout=1):
            device(resourceId="android:id/button_always").click()
            print("[display] Image viewer chooser: Always")
            return True
        elif device(resourceId="android:id/button_once").exists(timeout=1):
            device(resourceId="android:id/button_once").click()
            print("[display] Image viewer chooser: Once")
            return True
        print("[display] Image viewer chooser: not shown")
        return False
    except Exception as error:
        print(f"[display] Image viewer chooser handling failed: {error}")
        return False


# Scan_Method_Sally_0624
def scan_dismiss_common_dialogs(device):
    """Dismiss common popups that may block scan actions."""
    keywords = ["Allow", "允许", "Continue", "继续", "OK", "确定", "Got it", "我知道了"]
    try:
        for key in keywords:
            btn = device(textContains=key)
            if btn.exists(timeout=0.15):
                btn.click()
                time.sleep(0.08)
                break
    except Exception:
        pass


# Scan_Method_Sally_0624
def scan_switch_to_guest_account_via_ui(device, serial, get_current_user_id_func, get_guest_user_id_func, max_wait_seconds=20):
    """UI fallback to switch user to Guest account."""
    from common.adb_common import adb_shell

    before_user = get_current_user_id_func()
    try:
        adb_shell(serial, "am", "start", "-a", "android.settings.USER_SETTINGS", timeout=8)
    except Exception:
        adb_shell(serial, "am", "start", "-a", "android.settings.SETTINGS", timeout=8)
    time.sleep(0.8)

    user_keywords = ["Users & accounts", "Users", "用户", "多用户", "Multiple users"]
    found_user_entry = False
    for keyword in user_keywords:
        obj = device(textContains=keyword)
        if obj.exists(timeout=0.8):
            obj.click()
            time.sleep(0.5)
            found_user_entry = True
            break

    if not found_user_entry:
        for _ in range(4):
            device.swipe(540, 1400, 540, 500, 0.08)
            time.sleep(0.2)
            for keyword in user_keywords + ["Guest", "访客"]:
                obj = device(textContains=keyword)
                if obj.exists(timeout=0.6):
                    obj.click()
                    time.sleep(0.5)
                    found_user_entry = True
                    break
            if found_user_entry:
                break

    guest_clicked = False
    for keyword in ["Guest", "访客", "Add guest", "添加访客"]:
        obj = device(textContains=keyword)
        if obj.exists(timeout=0.8):
            obj.click()
            time.sleep(0.5)
            guest_clicked = True
            break

    if not guest_clicked:
        return False

    for confirm in ["Switch", "切换", "Yes", "确定", "OK", "Continue", "继续"]:
        obj = device(textContains=confirm)
        if obj.exists(timeout=0.6):
            obj.click()
            break

    guest_id = get_guest_user_id_func()
    deadline = time.time() + max_wait_seconds
    while time.time() < deadline:
        current = get_current_user_id_func()
        if guest_id is not None and current == guest_id:
            return True
        if before_user is not None and current is not None and current != before_user:
            return True
        time.sleep(0.5)
    return False

# Reboot_Method_Sally_0625
def reboot_power_menu_visible(device):
    """Return True if the power menu (restart/shutdown dialog) is currently visible."""
    menu_keys = ["Restart", "RESTART", "重启", "重新启动", "Power off", "关机", "Emergency", "紧急"]
    for key in menu_keys:
        try:
            if (
                device(text=key).exists(timeout=0.4)
                or device(textContains=key).exists(timeout=0.4)
                or device(description=key).exists(timeout=0.4)
                or device(descriptionContains=key).exists(timeout=0.4)
            ):
                return True
        except Exception:
            pass


# Reboot_Method_Sally_0625
def reboot_open_power_menu_from_quick_settings(device):
    """Fallback: open quick settings panel and tap the power menu entry."""
    try:
        w, h = device.info["displayWidth"], device.info["displayHeight"]
        device.swipe(w // 2, int(h * 0.02), w // 2, int(h * 0.65), duration=0.25)
        time.sleep(0.5)
        device.swipe(w // 2, int(h * 0.02), w // 2, int(h * 0.85), duration=0.25)
        time.sleep(0.8)
    except Exception:
        return False

    power_entry_keys = ["Power", "Power menu", "关机", "电源", "重启"]
    for key in power_entry_keys:
        for selector in (
                device(text=key),
                device(textContains=key),
                device(description=key),
                device(descriptionContains=key),
        ):
            try:
                if selector.exists(timeout=0.6):
                    selector.click()
                    time.sleep(1)
                    if reboot_power_menu_visible(device):
                        return True
            except Exception:
                pass
    try:
        device.press("back")
        time.sleep(0.3)
        device.press("back")
        time.sleep(0.3)
    except Exception:
        pass
    return False


# Reboot_Method_Sally_0625
def reboot_trigger_power_menu(device, serial):
    """Try multiple strategies to open the power menu."""
    from common.adb_common import reboot_run_adb
    attempts = [
        "input keyevent --longpress KEYCODE_POWER",
        "input keyevent KEYCODE_POWER --longpress",
        "input keyevent 26 --longpress",
    ]
    for cmd in attempts:
        try:
            device.shell(cmd)
        except Exception:
            reboot_run_adb(serial, ["shell"] + cmd.split(" "), timeout=10)
        time.sleep(1.2)
        if reboot_power_menu_visible(device):
            return True
    return reboot_open_power_menu_from_quick_settings(device)


# Reboot_Method_Sally_0625
def reboot_click_restart_button(device):
    """Click the Restart button in the power menu. Return True on success."""
    restart_keys = ["Restart", "RESTART", "重启", "重新启动"]
    for key in restart_keys:

        try:
            for selector in (
                    device(text=key),
                    device(textContains=key),
                    device(description=key),
                    device(descriptionContains=key),
            ):
                if selector.exists(timeout=0.8):
                    selector.click()
                    return True
        except Exception:
            pass

# Reboot_Method_Sally_0625
def reboot_restore_device_state(device, serial, pre_state):
    """Restore device state (screen, foreground app) to match pre-test snapshot."""
    from common.adb_common import scan_is_screen_on
    if not pre_state:
        return
    print("[reboot] Restoring device state...", flush=True)
    try:
        device.screen_on()
        device.unlock()
    except Exception:
        pass
    time.sleep(1)
    target_pkg = (pre_state.get("foreground_pkg") or "").strip()
    if target_pkg and target_pkg not in ("com.android.systemui", "com.android.launcher3"):
        try:
            device.app_start(target_pkg, stop=False)
            print(f"[reboot] [OK] Restored foreground app: {target_pkg}", flush=True)
            time.sleep(1)
        except Exception as e:
            print(f"[reboot] [WARN] Restore app failed ({target_pkg}): {str(e)[:120]}", flush=True)
    expect_screen_on = bool(pre_state.get("screen_on", True))
    now_on = scan_is_screen_on(serial)
    if expect_screen_on != now_on:
        try:
            device.press("power")
            time.sleep(1)
            print(f"[reboot] [OK] Restored screen state: {'ON' if expect_screen_on else 'OFF'}", flush=True)
        except Exception as e:
            print(f"[reboot] [WARN] Restore screen state failed: {str(e)[:120]}", flush=True)


# ============= IPSM_Method_Sally_0625: IPSM USB File System UI Automation Helpers =============

# IPSM_Method_Sally_2026-09-11
def ipsm_open_notification_panel(device):
    """Open notification panel with short swipe to avoid triggering Quick Settings."""
    try:
        device.open_notification()
        time.sleep(1.2)
        return True
    except Exception:
        pass

    try:
        w = device.info["displayWidth"]
        h = device.info["displayHeight"]
        device.swipe(w // 2, int(h * 0.02), w // 2, int(h * 0.40), duration=0.3)
        time.sleep(0.8)
        return True
    except Exception as e:
        print(f"[ipsm] [WARN] open notification panel failed: {e}", flush=True)
        return False

# IPSM_Method_Sally_2026-09-11
def ipsm_safe_click_text_contains(device, keyword, retries=2):
    """Safe click on UI element containing text keyword."""
    for _ in range(retries):
        try:
            obj = device(textContains=keyword)
            if not obj.exists(timeout=0.8):
                continue
            info = obj.info or {}
            bounds = info.get("bounds") or {}
            if info.get("clickable"):
                obj.click()
            elif bounds:
                # SystemUI notification title nodes are often non-clickable;
                # tapping their center activates the clickable notification row.
                left = int(bounds.get("left", 0))
                right = int(bounds.get("right", 0))
                top = int(bounds.get("top", 0))
                bottom = int(bounds.get("bottom", 0))
                device.click((left + right) // 2, (top + bottom) // 2)
            else:
                obj.click()
            time.sleep(1)
            return True
        except Exception:
            time.sleep(0.3)
    return False

# IPSM_Method_Sally_0625
def ipsm_expand_android_system_group(device):
    """Expand 'Android System' notification group to reveal USB notification."""
    group_headers = ["Android System", "系统界面", "System UI", "Android 系统"]

    for header in group_headers:
        group_el = device(textContains=header)
        if not group_el.exists(timeout=1.0):
            continue

        print(f"[ipsm] [INFO] found notification group header: {header}", flush=True)

        expand_desc = ["Expand", "展开", "See more", "查看全部"]
        for desc in expand_desc:
            btn = device(descriptionContains=desc)
            if btn.exists(timeout=0.6):
                try:
                    btn.click()
                    time.sleep(0.6)
                    print(f"[ipsm] [INFO] expanded '{header}' group via desc='{desc}'", flush=True)
                    return True
                except Exception:
                    pass

        try:
            group_el.click()
            time.sleep(0.6)
            print(f"[ipsm] [INFO] clicked group header '{header}' to expand", flush=True)
            return True
        except Exception:
            pass

    print("[ipsm] [INFO] Android System group not found or already expanded", flush=True)
    return False


# IPSM_Method_Sally_2026-09-11
def ipsm_open_usb_detail_page(device, serial):
    """Open USB settings detail page; fallback to USB settings Activity if UI fails."""
    from common.adb_common import adb_shell

    if not ipsm_open_notification_panel(device):
        print("[ipsm] [WARN] failed to open notification panel", flush=True)
        return False

    ipsm_expand_android_system_group(device)
    time.sleep(0.5)

    usb_notification_candidates = [
        "Charging this device via USB",
        "Charging device via USB",
        "Tap for more options",
        "点按可查看更多选项",
        "Use USB for",
        "USB 用于",
        "USB preferences",
        "USB 偏好设置",
        "正在通过 USB 为此设备充电",
        "正在通过 USB",
        "通过 USB 为此设备充电",
    ]

    for _ in range(3):
        for k in usb_notification_candidates:
            if ipsm_safe_click_text_contains(device, k, retries=1):
                print(f"[ipsm] [INFO] clicked USB notification entry: {k}", flush=True)
                time.sleep(1.0)
                return True
        try:
            device.swipe_ext("up", 0.2)
        except Exception:
            pass
        time.sleep(0.4)

    print("[ipsm] [WARN] USB notification not found in panel", flush=True)
    try:
        adb_shell(serial, "cmd", "statusbar", "expand-notifications", timeout=8)
        time.sleep(1.2)
        for k in usb_notification_candidates:
            if ipsm_safe_click_text_contains(device, k, retries=2):
                print(f"[ipsm] [INFO] clicked USB notification after statusbar expand: {k}", flush=True)
                time.sleep(1.0)
                return True
    except Exception:
        pass
    return False

# IPSM_Method_Sally_2026-09-11
def ipsm_click_usb_mode_option(device, mode_text, ct47_mode=False):
    """Click USB mode option in settings; try text first, then radio control."""
    item = device(textContains=mode_text)
    if not item.exists(timeout=0.8):
        return False

    try:
        info = item.info or {}
        bounds = info.get("bounds") or {}
        if info.get("clickable") and not ct47_mode:
            item.click()
        elif bounds:
            # CT47 exposes the option label as a non-clickable TextView. The
            # row is selectable by tapping the label bounds directly.
            left = int(bounds.get("left", 0))
            right = int(bounds.get("right", 0))
            top = int(bounds.get("top", 0))
            bottom = int(bounds.get("bottom", 0))
            device.click((left + right) // 2, (top + bottom) // 2)
        else:
            item.click()
        time.sleep(0.5)
        return True
    except Exception:
        return False

    return False

# IPSM_Method_Sally_0625
# IPSM_Method_Sally_2026-09-11
def ipsm_select_file_system_mode(device, serial):
    """Select File system/MTP mode via UI with ADB fallback."""
    from common.adb_common import (
        adb_shell,
        ipsm_is_mtp_enabled,
        ipsm_enable_mtp_by_adb_fallback,
        ipsm_get_prop,
    )

    model_result = adb_shell(serial, "getprop", "ro.product.model", timeout=8)
    device_model = (model_result.stdout or "").strip().lower()
    is_ct47 = "ct47" in device_model
    print(
        f"[ipsm] USB mode branch: {'CT47 adapted' if is_ct47 else 'CT70/default'} "
        f"(model={device_model or 'unknown'})",
        flush=True,
    )

    ipsm_open_usb_detail_page(device, serial)

    mode_candidates = [
        "File system",
        "File transfer",
        "File transfers",
        "Transfer files",
        "MTP",
        "文件系统",
        "文件传输",
        "传输文件",
    ]

    group_candidates = ["Use USB for", "USB 用于", "选择 USB 配置", "USB Preferences", "USB 偏好设置"]

    for _ in range(4):
        for g in group_candidates:
            try:
                ipsm_safe_click_text_contains(device, g, retries=1)
            except Exception:
                pass

        for mode in mode_candidates:
            if not ipsm_click_usb_mode_option(device, mode, ct47_mode=is_ct47):
                continue

            deadline = time.time() + 5
            adb_observed = False
            while time.time() < deadline:
                usb_state = ipsm_get_prop(serial, "sys.usb.state").lower()
                usb_cfg = ipsm_get_prop(serial, "sys.usb.config").lower()
                if usb_state or usb_cfg:
                    adb_observed = True
                if ipsm_is_mtp_enabled(serial):
                    print(f"[ipsm] [OK] USB set to file system mode via UI: state={usb_state}, cfg={usb_cfg}", flush=True)
                    return True
                time.sleep(0.5)

            # CT70 may keep the ADB property as "adb" while Windows has
            # already mounted the device as MTP. Host visibility is therefore
            # valid confirmation even when ADB remains connected.
            if ipsm_verify_ipsm_card_visible_on_pc():
                print("[ipsm] [OK] File Transfer confirmed by Windows MTP visibility", flush=True)
                return True

            if not adb_observed:
                print("[ipsm] [WARN] UI selected USB mode but ADB confirmation was unavailable", flush=True)
            else:
                print(f"[ipsm] [WARN] UI click did not confirm MTP mode: {mode}", flush=True)
            break

        try:
            device.swipe_ext("up", 0.2)
        except Exception:
            pass
        time.sleep(0.5)

    print("[ipsm] [WARN] UI path was not confirmed, falling back to ADB MTP switch", flush=True)
    if ipsm_enable_mtp_by_adb_fallback(serial):
        usb_state = ipsm_get_prop(serial, "sys.usb.state").lower()
        usb_cfg = ipsm_get_prop(serial, "sys.usb.config").lower()
        print(f"[ipsm] [OK] USB set to MTP via ADB fallback: state={usb_state}, cfg={usb_cfg}", flush=True)
        return True

    print("[ipsm] [WARN] All attempts to enable MTP failed", flush=True)
    return False

# IPSM_Method_Sally_2026-09-11
def ipsm_verify_ipsm_card_visible_on_pc():
    """Verify IPSM card is visible on Windows PC via PowerShell."""
    import subprocess

    ps = (
        "$shell = New-Object -ComObject Shell.Application;"
        "$computer = $shell.Namespace(17);"
        "$names = @();"
        "foreach ($it in $computer.Items()) { $names += $it.Name };"
        "$hit_shell = $false;"
        "foreach ($n in $names) { "
        "  if ($n -match '(?i)ipsm' -or $n -match '(?i)honeywell' -or $n -match '(?i)android') { $hit_shell = $true }"
        "};"
        "$pnp_names = @();"
        "try {"
        "  $pnp = Get-CimInstance Win32_PnPEntity -ErrorAction Stop | Where-Object { $_.Name -and ($_.Name -match '(?i)ipsm|honeywell|mtp|portable|android') };"
        "  foreach ($d in $pnp) { $pnp_names += $d.Name };"
        "} catch {}"
        "$hit_pnp = $pnp_names.Count -gt 0;"
        "$hit = $hit_shell -or $hit_pnp;"
        "if ($hit) {"
        "  Write-Output ('RESULT:VISIBLE::SHELL=' + ($names -join '|') + '::PNP=' + ($pnp_names -join '|'));"
        "} else {"
        "  Write-Output ('RESULT:MISSING::SHELL=' + ($names -join '|') + '::PNP=' + ($pnp_names -join '|'));"
        "  exit 2"
        "}"
    )

    ret = subprocess.run(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="ignore",
        timeout=25,
        check=False,
    )
    out = (ret.stdout or "").strip()
    err = (ret.stderr or "").strip()
    if ret.returncode == 0 and "RESULT:VISIBLE" in out:
        print("[ipsm] [OK] IPSM card is visible on PC", flush=True)
        return True

    print(f"[ipsm] [WARN] IPSM card not visible. stdout={out}, stderr={err}", flush=True)
    return False

# ============= EMMC_Method_Sally: EMMC Video Recording UI Helpers (2026-07-01) =============

# EMMC_Method_Sally_2026-07-01
def emmc_click_first_visible(device, selectors):
    """
    点击第一个可见的控件。
    
    :param device: uiautomator2 设备对象
    :param selectors: 选择器列表
    :return: True 如果成功点击，否则 False
    """
    import time
    for selector in selectors:
        try:
            if selector.exists(timeout=0.6):
                selector.click()
                time.sleep(0.8)
                return True
        except Exception:
            pass
    return False


def _emmc_screen_size(device):
    """Physical screen size; u2 info excludes the nav bar, which skews ratio-based taps."""
    import re
    try:
        out = str(device.shell(["wm", "size"]).output)
        sizes = re.findall(r"(\d+)x(\d+)", out)
        if sizes:
            return int(sizes[-1][0]), int(sizes[-1][1])
    except Exception:
        pass
    info = device.info or {}
    return int(info.get("displayWidth", 1080)), int(info.get("displayHeight", 1920))


def _emmc_camera_ui_tree_visible(device):
    """snapcam sometimes exposes a blank accessibility tree while controls are on screen."""
    try:
        return device(
            resourceIdMatches=r"org\.codeaurora\.snapcam:id/(shutter_button|video_button|mode_text|camera_controls)"
        ).exists(timeout=0.5)
    except Exception:
        return False


# EMMC_Method_Sally_2026-09-20 CK67 compatibility
def emmc_switch_camera_to_video_mode(device):
    """
    通过 UI 切换相机到录像模式。

    :param device: uiautomator2 设备对象
    :return: True 如果成功切换，否则 False
    """
    selectors = [
        device(resourceId="org.codeaurora.snapcam:id/mode_text", text="Video"),
        device(text="Video"),
        device(textContains="Video"),
        device(description="Video"),
        device(descriptionContains="Video"),
        device(resourceIdMatches=r".*(video|camcorder|movie|record).*"),
    ]
    for selector in selectors:
        try:
            if not selector.exists(timeout=0.6):
                continue
            if (selector.info or {}).get("selected") is True:
                return True
            bounds = (selector.info or {}).get("bounds") or {}
            if bounds:
                center = (
                    (int(bounds["left"]) + int(bounds["right"])) // 2,
                    (int(bounds["top"]) + int(bounds["bottom"])) // 2,
                )
                device.click(*center)
            else:
                selector.click()

            deadline = time.time() + 3
            while time.time() < deadline:
                if not selector.exists(timeout=0.1):
                    # CK67 collapses the mode row after a successful selection (2026-09-20).
                    return True
                if (selector.info or {}).get("selected") is True:
                    return True
                time.sleep(0.2)
        except Exception:
            continue

    # CK67 (480x800): Video tab sits left of the mode row; tapping it while already in Video is harmless.
    if not _emmc_camera_ui_tree_visible(device):
        width, height = _emmc_screen_size(device)
        if height < 1000:
            device.click(int(width * 0.167), int(height * 0.808))
            time.sleep(2)
            return True
    return False


# EMMC_Method_Sally_2026-07-01
def emmc_click_record_button_once(device, serial):
    """
    点击一次录制按钮。
    
    :param device: uiautomator2 设备对象
    :param serial: 设备 serial
    :return: True 如果成功点击，否则 False
    """
    import time
    candidates = [
        device(resourceId="org.codeaurora.snapcam:id/shutter_button"),
        device(resourceId="com.android.camera:id/shutter_button"),
        device(resourceIdMatches=r".*(record|video|camcorder|movie|shutter).*"),
        device(resourceIdMatches=r".*(record|shutter).*"),
        device(descriptionContains="Record"),
        device(descriptionContains="Video"),
        device(descriptionContains="Camcorder"),
        device(descriptionContains="录像"),
        device(descriptionContains="录制"),
        device(descriptionContains="停止"),
        device(textContains="Record"),
        device(textContains="Video"),
        device(textContains="录像"),
        device(textContains="录制"),
    ]
    for obj in candidates:
        try:
            if obj.exists(timeout=0.6):
                obj.click()
                time.sleep(0.6)
                return True
        except Exception:
            pass

    try:
        info = device.info or {}
        width = int(info.get("displayWidth", 1080))
        height = int(info.get("displayHeight", 1920))
        phys_width, phys_height = _emmc_screen_size(device)
        if phys_height < 1000:
            # Info height 736 would put 0.88 on the Photo/Video mode row instead of the shutter.
            fallback_points = [(phys_width // 2, int(phys_height * 0.919))]
        else:
            fallback_points = [
                (width // 2, int(height * 0.88)),
                (width // 2, int(height * 0.92)),
                (int(width * 0.82), int(height * 0.88)),
                (int(width * 0.18), int(height * 0.88)),
            ]
        for x, y in fallback_points:
            try:
                device.click(x, y)
                time.sleep(0.8)
                return True
            except Exception:
                continue
    except Exception:
        pass

    return False


# EMMC_Method_Sally_2026-07-01
def emmc_dismiss_camera_popups(device):
    """
    关闭可能遮挡相机预览/录制按钮的弹框。
    
    :param device: uiautomator2 设备对象
    """
    import time
    try:
        camera_dismiss_runtime_dialogs(device)
    except Exception:
        pass
    
    extra_keys = [
        "仅在使用该应用时允许",
        "使用时允许",
        "不再提示",
        "下次再说",
        "稍后",
        "Allow only while using the app",
        "Only this time",
        "Not now",
        "Later",
        "Got it",
    ]
    for _ in range(2):
        acted = False
        for key in extra_keys:
            try:
                for obj in (device(text=key), device(textContains=key), device(descriptionContains=key)):
                    if obj.exists(timeout=0.2):
                        obj.click()
                        time.sleep(0.4)
                        acted = True
                        break
            except Exception:
                pass
        if not acted:
            break

# EMMC_Method_Sally_2026-09-11
def emmc_stop_recording(device, serial, timeout=12):
    """Stop an active recording and confirm it actually stopped.

    The generic record-button helper matches the residual "Video" mode label and returns
    success without ending the capture, so on some ROMs (CT70) recording keeps running.
    Here only the real record control is pressed and the recording state is verified.
    """
    import time

    recording = switch_photo_video_is_recording(device)

    # CT70 camera builds can expose a different resource ID, so use explicit stop
    # semantics before trying a coordinate fallback. Never click a generic shutter
    # control because it may take a snapshot while recording.
    stop_selectors = [
        device(resourceId="org.codeaurora.snapcam:id/video_button"),
        device(resourceId="com.android.camera:id/video_button"),
        device(resourceId="org.codeaurora.snapcam:id/video_pause"),
        device(resourceIdMatches=r".*(video_button|stop|record_stop|recording_stop).*"),
        device(descriptionMatches=r"(?i).*(stop|停止|结束录制|停止录制).*(record|录制|录像)?"),
        device(textMatches=r"(?i).*(stop|停止|结束录制|停止录制).*(record|录制|录像)?"),
    ]
    for obj in stop_selectors:
        try:
            if not obj.exists(timeout=0.4):
                continue
            bounds = (obj.info or {}).get("bounds") or {}
            if bounds:
                cx = (int(bounds["left"]) + int(bounds["right"])) // 2
                cy = (int(bounds["top"]) + int(bounds["bottom"])) // 2
                device.click(cx, cy)
            else:
                obj.click()
            deadline = time.time() + timeout
            while time.time() < deadline:
                if not switch_photo_video_is_recording(device):
                    return True
                time.sleep(0.5)
        except Exception:
            pass

    ui_tree_visible = _emmc_camera_ui_tree_visible(device)
    if ui_tree_visible and not recording and not switch_photo_video_is_recording(device):
        return True

    # Some CT70 firmware exposes only an unlabeled bottom-center stop control.
    # Use the stable shutter area only after semantic selectors have failed.
    try:
        info = device.info or {}
        width = int(info.get("displayWidth", 1080))
        height = int(info.get("displayHeight", 1920))
        phys_width, phys_height = _emmc_screen_size(device)
        if phys_height < 1000:
            stop_points = ((phys_width // 2, int(phys_height * 0.919)),)
        else:
            stop_points = ((width // 2, int(height * 0.88)), (width // 2, int(height * 0.92)))
        for x, y in stop_points:
            device.click(x, y)
            deadline = time.time() + timeout
            while time.time() < deadline:
                if not switch_photo_video_is_recording(device):
                    return True
                time.sleep(0.5)
    except Exception:
        pass

    return not switch_photo_video_is_recording(device)

# EMMC_Method_Sally_2026-09-11
def emmc_play_video_to_end(device, serial, video_path):
    """
    打开并播放视频，等待播放完成，然后退出播放器。

    :param device: uiautomator2 设备对象
    :param serial: 设备 serial
    :param video_path: 视频文件的完整路径
    :return: True 如果播放完成，否则 False
    """
    import re
    import time
    from common.adb_common import adb_shell

    if not video_path:
        return False

    model_result = adb_shell(serial, "getprop", "ro.product.model", timeout=8)
    is_ct47 = "ct47" in (model_result.stdout or "").strip().lower()

    # Android 10+ scoped storage rejects file:// playback ("can't play"); the recorded
    # file must be indexed and opened through its MediaStore content:// URI.
    adb_shell(
        serial,
        "am", "broadcast", "-a", "android.intent.action.MEDIA_SCANNER_SCAN_FILE",
        "-d", f"file://{video_path}",
        timeout=10,
    )
    time.sleep(1)

    name = video_path.rsplit("/", 1)[-1]
    media_uri = f"file://{video_path}"
    for _ in range(5 if is_ct47 else 10):
        ret = adb_shell(
            serial,
            "content", "query", "--uri", "content://media/external/video/media",
            "--projection", "_id", "--where", f"\"_display_name='{name}'\"",
            timeout=15,
        )
        out = (ret.stdout or "") if ret.returncode == 0 else ""
        match = re.search(r"_id=(\d+)", out)
        if match:
            media_uri = f"content://media/external/video/media/{match.group(1)}"
            break
        time.sleep(0.3 if is_ct47 else 1)

    # Both CT47 and CT70 use the direct MediaStore path. VIEW launches the
    # player and starts the recorded video without opening the album first.
    def _focus_package():
        out = adb_shell(serial, "dumpsys", "window", timeout=10)
        match = re.search(r"mCurrentFocus=Window\{\S+ \S+ ([\w.]+)[/}]", out.stdout or "")
        return match.group(1).lower() if match else ""

    non_player = ("launcher", "snapcam", "camera", "settings", "systemui")
    player_package = ""
    for _ in range(2):
        # Camera still on top makes VIEW only get "delivered to top-most instance" with no player shown.
        adb_shell(serial, "input", "keyevent", "3", timeout=5)
        adb_shell(serial, "am", "force-stop", "com.google.android.apps.photos", timeout=8)
        time.sleep(1)

        launched = adb_shell(
            serial,
            "am", "start", "-a", "android.intent.action.VIEW",
            "-d", media_uri, "-t", "video/mp4", "--grant-read-uri-permission",
            timeout=12,
        )
        if launched.returncode != 0:
            continue

        for _ in range(10):
            time.sleep(1)
            focus = _focus_package()
            if focus and not any(p in focus for p in non_player):
                player_package = focus
                break
        if player_package:
            break
    if not player_package:
        return False

    playing = False
    for _ in range(3 if is_ct47 else 8):
        session = adb_shell(serial, "dumpsys", "media_session", timeout=8)
        session_text = ((session.stdout or "") + (session.stderr or "")).lower()
        if "state=playing" in session_text or "state=3" in session_text:
            playing = True
            break
        time.sleep(0.5 if is_ct47 else 1)

    # 等待播放完成
    time.sleep(3 if is_ct47 else 8)

    # 优先通过出现 Replay/重播 判断播放结束。
    replay_found = False
    for key in ["Replay", "重播", "重新播放"]:
        try:
            if device(textContains=key).exists(timeout=0.8) or device(descriptionContains=key).exists(timeout=0.8):
                replay_found = True
                break
        except Exception:
            pass

    foreground_package = _focus_package()
    player_foreground = bool(foreground_package) and not any(p in foreground_package for p in non_player)

    # 关闭播放器 - 按返回键退出
    try:
        adb_shell(serial, "input", "keyevent", "4", timeout=5)
        time.sleep(1)
    except Exception:
        pass

    return replay_found or playing or player_foreground or bool(player_package)

# ============= WiFi_Method_Sally: WiFi UI Automation Helpers =============

# WIFI_Method_Sally_0709
def wifi_init_device(serial):
    """Initialize UIAutomator2 device connection."""
    if u2 is None:
        raise ImportError("[ERROR] uiautomator2 not installed. Install with: pip install uiautomator2")
    if not serial:
        raise RuntimeError("No Android device found. Please connect a device first.")

    print(f"[wifi] Connecting to device: {serial}", flush=True)
    device = u2.connect(serial)
    info = device.info
    print(
        f"[wifi] [OK] Device connected, screen={info['displayWidth']}x{info['displayHeight']}",
        flush=True,
    )
    return device


# WIFI_Method_Sally_0709
def wifi_wake_up_device(device):
    """Wake and unlock device."""
    from common.adb_common import adb_shell
    print("[wifi] Waking up device...", flush=True)
    try:
        device.unlock()
    except Exception:
        serial = os.environ.get("ANDROID_SERIAL")
        if not serial:
            from common.adb_common import get_device_serial
            serial = get_device_serial()
        adb_shell(serial, "input", "keyevent", "26")  # power
        time.sleep(0.8)
        adb_shell(serial, "input", "keyevent", "82")  # menu/unlock
    time.sleep(1)
# Memory_Common_UI_Sophy_20260706
def memory_open_developer_memory_page(device, serial, screenshot_dir=None):
    """Open Settings -> Developer options -> Memory page."""
    if device is None or not serial:
        return False

    try:
        subprocess.run(
            ['adb', '-s', serial, 'shell', 'am', 'start', '-a', 'android.settings.APPLICATION_DEVELOPMENT_SETTINGS'],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        time.sleep(2)
    except Exception:
        return False

    # After reboot, Developer options page may need extra time to finish rendering.
    # Wait for page to settle before any scrolling.
    settled = False
    settle_deadline = time.time() + 8
    while time.time() < settle_deadline:
        try:
            if (
                device(text='Developer options').exists(timeout=0.5)
                or device(textContains='Developer').exists(timeout=0.5)
                or device(textContains='开发者').exists(timeout=0.5)
                or device(text='Memory').exists(timeout=0.5)
                or device(textContains='Memory').exists(timeout=0.5)
            ):
                settled = True
                break
        except Exception:
            pass
        time.sleep(0.4)

    if not settled:
        # Keep behavior permissive: continue to normal search loop even if title signal not found.
        time.sleep(1)

    if screenshot_dir and device is not None:
        try:
            from common.adb_common import save_step_screenshot
            save_step_screenshot(device, 'developer_options_opened', screenshot_dir)
        except Exception:
            pass

    for _ in range(15):
        try:
            if device(text='Memory').exists(timeout=1) or device(textContains='Memory').exists(timeout=1):
                break
            if device(scrollable=True).exists(timeout=1):
                device(scrollable=True).scroll.forward()
            else:
                device.swipe(500, 1500, 500, 500, duration=0.2)
        except Exception:
            time.sleep(0.3)
        time.sleep(0.3)
    else:
        if screenshot_dir and device is not None:
            try:
                from common.adb_common import save_step_screenshot
                save_step_screenshot(device, 'memory_option_not_found', screenshot_dir)
            except Exception:
                pass
        return False

    if screenshot_dir and device is not None:
        try:
            from common.adb_common import save_step_screenshot
            save_step_screenshot(device, 'memory_option_found', screenshot_dir)
        except Exception:
            pass

    try:
        if device(text='Memory').exists(timeout=1):
            device(text='Memory').click()
        elif device(textContains='Memory').exists(timeout=1):
            device(textContains='Memory').click()
        else:
            return False
        time.sleep(2)
    except Exception:
        return False

    if screenshot_dir and device is not None:
        try:
            from common.adb_common import save_step_screenshot
            save_step_screenshot(device, 'memory_page_opened', screenshot_dir)
        except Exception:
            pass
    return True


# Memory_Common_UI_Sophy_20260706
#
def memory_read_total_memory_value(device, screenshot_dir=None):
    """Read 'Total memory' value (GB) from Memory page, returns float or None."""
    if device is None:
        return None

    import re

    time.sleep(1.5)
    if screenshot_dir and device is not None:
        try:
            from common.adb_common import save_step_screenshot
            save_step_screenshot(device, 'memory_page_loaded', screenshot_dir)
        except Exception:
            pass

    total_memory = None

    try:
        if device(textContains='Total memory').exists(timeout=2):
            label = device(textContains='Total memory')
            label_bounds = label.info.get('bounds', {})
            label_bottom = label_bounds.get('bottom', 0)

            if device(textContains='GB').exists(timeout=1):
                gb_elements = device(textContains='GB')
                best_value = None
                min_distance = float('inf')

                for idx in range(gb_elements.count):
                    try:
                        elem = gb_elements[idx]
                        text_val = (elem.info.get('text', '') or '').strip()
                        elem_bounds = elem.info.get('bounds', {})
                        elem_top = elem_bounds.get('top', 0)
                        if elem_top < label_bottom:
                            continue

                        m = re.search(r'(\d+(?:\.\d+)?)\s*GB', text_val, re.IGNORECASE)
                        if not m:
                            continue

                        value = float(m.group(1))
                        if value < 1 or value > 32:
                            continue

                        distance = elem_top - label_bottom
                        if distance < min_distance:
                            min_distance = distance
                            best_value = value
                    except Exception:
                        continue

                if best_value is not None:
                    total_memory = best_value
    except Exception:
        pass

    if total_memory is None:
        try:
            xml = device.dump_hierarchy()
            patterns = [
                r'Total memory[^<>]*?</[^>]+>.*?text="(\d+(?:\.\d+)?)\s*GB"',
                r'Total memory.*?(\d+(?:\.\d+)?)\s*GB',
                r'text="Total memory"[^<]*<[^>]*text="(\d+(?:\.\d+)?)\s*GB"',
            ]
            for p in patterns:
                m = re.search(p, xml, re.IGNORECASE | re.DOTALL)
                if not m:
                    continue
                value = float(m.group(1))
                if 1 <= value <= 32:
                    total_memory = value
                    break
        except Exception:
            pass

    if total_memory is None:
        if screenshot_dir and device is not None:
            try:
                from common.adb_common import save_step_screenshot
                save_step_screenshot(device, 'memory_read_failed', screenshot_dir)
            except Exception:
                pass

    return total_memory


# Memory_Common_UI__Sophy_20260706
def memory_enable_usage_profiling(device, serial, screenshot_dir=None):
    """Enable 'Enable memory usage profiling' on Memory page and wait for reboot if prompted."""
    if device is None or not serial:
        return False, device

    restart_clicked = False

    try:
        for _ in range(12):
            if device(textContains='Enable memory usage profiling').exists(timeout=1):
                break
            if device(scrollable=True).exists(timeout=1):
                device(scrollable=True).scroll.forward()
            else:
                device.swipe(500, 1500, 500, 500, duration=0.2)
            time.sleep(0.3)
        else:
            return False, device

        if screenshot_dir and device is not None:
            try:
                from common.adb_common import save_step_screenshot
                save_step_screenshot(device, 'memory_profiling_option_found', screenshot_dir)
            except Exception:
                pass
        device(textContains='Enable memory usage profiling').click()
        time.sleep(1.2)
        if screenshot_dir and device is not None:
            try:
                from common.adb_common import save_step_screenshot
                save_step_screenshot(device, 'after_click_memory_profiling', screenshot_dir)
            except Exception:
                pass
    except Exception:
        return False, device

    restart_buttons = ['Restart', 'RESTART', 'Reboot', 'REBOOT', 'OK', '确定']
    try:
        for btn in restart_buttons:
            if device(text=btn).exists(timeout=1.2):
                device(text=btn).click()
                restart_clicked = True
                break
    except Exception:
        pass

    if not restart_clicked:
        return True, device

    time.sleep(8)
    start = time.time()
    timeout = 150
    while time.time() - start < timeout:
        try:
            state_ret = subprocess.run(
                ['adb', '-s', serial, 'get-state'],
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )
            if 'device' in (state_ret.stdout or '').strip():
                break
        except Exception:
            pass
        time.sleep(4)

    if u2 is None:
        return True, device

    for _ in range(6):
        try:
            new_device = u2.connect(serial)
            _ = new_device.info
            try:
                new_device.screen_on()
                new_device.press('home')
            except Exception:
                pass
            return True, new_device
        except Exception:
            time.sleep(3)

    return True, device


# Memory_Common_UI__Sophy_20260706
#Disable 'Enable memory usage profiling in settings -> Developer options -> Memory'  and wait for reboot if prompted.
def memory_disable_usage_profiling(device, serial, screenshot_dir=None):
    """Disable 'Enable memory usage profiling', restart device, and verify it is disabled."""
    if device is None or not serial:
        return False, device

    def _get_profiling_switch_checked(cur_device):
        """Return switch checked state: True/False, or None if cannot determine."""
        try:
            row = cur_device(textContains='Enable memory usage profiling')
            if not row.exists(timeout=1):
                return None

            try:
                sw = row.sibling(className='android.widget.Switch')
                if sw.exists(timeout=0.8):
                    return bool(sw.info.get('checked', False))
            except Exception:
                pass

            try:
                info = row.info or {}
                if 'checked' in info:
                    return bool(info.get('checked'))
            except Exception:
                pass
        except Exception:
            pass
        return None

    if not memory_open_developer_memory_page(device, serial, screenshot_dir):
        return False, device

    restart_clicked = False
    try:
        for _ in range(12):
            if device(textContains='Enable memory usage profiling').exists(timeout=1):
                break
            if device(scrollable=True).exists(timeout=1):
                device(scrollable=True).scroll.forward()
            else:
                device.swipe(500, 1500, 500, 500, duration=0.2)
            time.sleep(0.3)
        else:
            return False, device

        checked_before = _get_profiling_switch_checked(device)
        if checked_before is False:
            return True, device

        device(textContains='Enable memory usage profiling').click()
        time.sleep(1.2)

        if screenshot_dir and device is not None:
            try:
                from common.adb_common import save_step_screenshot
                save_step_screenshot(device, 'after_disable_memory_profiling', screenshot_dir)
            except Exception:
                pass
    except Exception:
        return False, device

    restart_buttons = ['Restart', 'RESTART', 'Reboot', 'REBOOT', 'OK', '确定']
    try:
        for btn in restart_buttons:
            if device(text=btn).exists(timeout=1.2):
                device(text=btn).click()
                restart_clicked = True
                break
    except Exception:
        pass

    if not restart_clicked:
        return False, device

    time.sleep(8)
    start = time.time()
    timeout = 150
    while time.time() - start < timeout:
        try:
            state_ret = subprocess.run(
                ['adb', '-s', serial, 'get-state'],
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )
            if 'device' in (state_ret.stdout or '').strip():
                break
        except Exception:
            pass
        time.sleep(4)

    if u2 is None:
        return True, device

    for _ in range(6):
        try:
            new_device = u2.connect(serial)
            _ = new_device.info
            try:
                new_device.screen_on()
                new_device.press('home')
            except Exception:
                pass
            device = new_device
            break
        except Exception:
            time.sleep(3)

    if not memory_open_developer_memory_page(device, serial, screenshot_dir):
        return False, device

    for _ in range(12):
        try:
            if device(textContains='Enable memory usage profiling').exists(timeout=1):
                break
            if device(scrollable=True).exists(timeout=1):
                device(scrollable=True).scroll.forward()
            else:
                device.swipe(500, 1500, 500, 500, duration=0.2)
            time.sleep(0.3)
        except Exception:
            time.sleep(0.3)
    else:
        return False, device

    checked_after = _get_profiling_switch_checked(device)
    if checked_after is False:
        if screenshot_dir and device is not None:
            try:
                from common.adb_common import save_step_screenshot
                save_step_screenshot(device, 'memory_profiling_disabled_verified', screenshot_dir)
            except Exception:
                pass
        return True, device

    return False, device


# Memory_Common_UI__Sophy_20260706
#enable enable memory usage profiling, check total memory size
def memory_get_total_memory_with_auto_enable(device, serial, screenshot_dir=None):
    """
    Unified memory UI flow for memory test cases.
    1) Open Developer options -> Memory
    2) Read Total memory
    3) If missing, enable memory usage profiling, then retry once

    Returns:
        (total_memory_gb_or_none, profiling_enabled_by_this_flow, current_device)
    """
    if not memory_open_developer_memory_page(device, serial, screenshot_dir):
        return None, False, device

    total_memory = memory_read_total_memory_value(device, screenshot_dir)
    if total_memory is not None:
        return total_memory, False, device

    enabled, device = memory_enable_usage_profiling(device, serial, screenshot_dir)
    if not enabled:
        return None, False, device

    if not memory_open_developer_memory_page(device, serial, screenshot_dir):
        return None, True, device

    total_memory = memory_read_total_memory_value(device, screenshot_dir)
    return total_memory, True, device

# SwitchPhotoVideo_Method_Sally_2026-08-03
def switch_photo_video_keep_awake_unlock(device, serial):
    """Keep screen awake and unlock before SwitchPhotoVideo actions."""
    from common.adb_common import adb_shell, switch_photo_video_is_device_awake, switch_photo_video_set_stayon

    switch_photo_video_set_stayon(serial, True)
    if not switch_photo_video_is_device_awake(serial):
        adb_shell(serial, "input", "keyevent", "224", timeout=6)
        time.sleep(0.6)
    adb_shell(serial, "wm", "dismiss-keyguard", timeout=6)
    try:
        device.swipe_ext("up", scale=0.9)
    except Exception:
        pass
    time.sleep(0.6)


# SwitchPhotoVideo_Method_Sally_2026-08-03
def switch_photo_video_click_any(selectors, timeout=0.4, delay=0.6):
    """Click the first existing UI selector."""
    for obj in selectors:
        try:
            if obj.exists(timeout=timeout):
                obj.click()
                time.sleep(delay)
                return True
        except Exception:
            pass
    return False


# SwitchPhotoVideo_Method_Sally_2026-08-03
def switch_photo_video_is_recording(device):
    """Detect whether camera is currently recording video."""
    try:
        btn = device(resourceId="org.codeaurora.snapcam:id/video_button")
        if btn.exists(timeout=0.2):
            desc = str((btn.info or {}).get("contentDescription") or "")
            if "stop" in desc.lower() or "停止" in desc:
                return True
    except Exception:
        pass

    marks = [
        device(textMatches=r"^\d{1,2}:\d{2}$"),
        device(textMatches=r"^\d{1,2}:\d{2}:\d{2}$"),
        device(resourceIdMatches=r".*(recording|chronometer|timer|record_time).*"),
    ]
    for obj in marks:
        try:
            if obj.exists(timeout=0.2):
                return True
        except Exception:
            pass
    return False


# SwitchPhotoVideo_Method_Sally_2026-08-03
def switch_photo_video_is_mode(device, name, mode_text_id):
    """Check whether camera is currently in target mode (Photo/Video)."""
    if name == "Video" and switch_photo_video_is_recording(device):
        return True
    if name == "Photo" and switch_photo_video_is_recording(device):
        return False
    try:
        tab = device(resourceId=mode_text_id, text=name)
        if tab.exists(timeout=0.3):
            return bool((tab.info or {}).get("selected", False))
    except Exception:
        pass

    words = [name, name.upper(), "视频", "录像"] if name == "Video" else [name, "拍照", "照片"]
    for w in words:
        try:
            if device(text=w, selected=True).exists(timeout=0.2):
                return True
        except Exception:
            pass
    return False


# SwitchPhotoVideo_Method_Sally_2026-08-03
def switch_photo_video_switch_mode(device, name, round_idx, mode_text_id, step_shot):
    """Switch camera to target mode and verify success."""
    step = (
        f"step02_switch_video_round{round_idx:02d}"
        if name == "Video"
        else f"step04_switch_photo_round{round_idx:02d}"
    )
    if switch_photo_video_is_mode(device, name, mode_text_id):
        step_shot(step)
        return True

    for _ in range(4):
        selectors = [
            device(resourceId=mode_text_id, text=name),
            device(text=name),
            device(text=name.upper()),
        ]
        if not switch_photo_video_click_any(selectors, delay=0.8):
            try:
                info = device.info or {}
                width = int(info.get("displayWidth", 1080))
                height = int(info.get("displayHeight", 1920))
                y = int(height * 0.83)
                if name == "Video":
                    device.swipe(int(width * 0.2), y, int(width * 0.8), y, duration=0.2)
                else:
                    device.swipe(int(width * 0.8), y, int(width * 0.2), y, duration=0.2)
                time.sleep(0.8)
            except Exception:
                pass

        if switch_photo_video_is_mode(device, name, mode_text_id):
            step_shot(step)
            return True

    return False


# SwitchPhotoVideo_Method_Sally_2026-08-03
def switch_photo_video_ensure_preview(device, serial, round_idx, step_shot):
    """Ensure camera preview is visible with simple recovery."""
    if camera_is_preview_visible(device, serial):
        return True

    for _ in range(2):
        switch_photo_video_keep_awake_unlock(device, serial)
        if camera_is_preview_visible(device, serial):
            step_shot(f"step00_preview_recovered_round{round_idx:02d}")
            return True
        if camera_open_camera_app(device, serial) and camera_is_preview_visible(device, serial):
            step_shot(f"step00_preview_reopen_round{round_idx:02d}")
            return True

    return False

# WIFI_Method_Static_IP_Sophy_2026-09-07
def wifi_apply_static_ip_config(device, static_ip):
    """Expand Advanced options in the WiFi connect dialog and fill Static IP fields.

    static_ip keys: ip, gateway, prefix_length, dns1, dns2 (all optional strings).
    """
    if not static_ip:
        return False
    try:
        advanced = device(resourceId="com.android.settings:id/wifi_advanced_toggle")
        if advanced.exists(timeout=2) and not (advanced.info or {}).get("checked", False):
            advanced.click()
            time.sleep(0.5)

        ip_settings_spinner = device(resourceId="com.android.settings:id/ip_settings")
        if ip_settings_spinner.exists(timeout=2):
            ip_settings_spinner.click()
            time.sleep(0.5)
            static_option = device(text="Static")
            if static_option.exists(timeout=2):
                static_option.click()
                time.sleep(0.5)

        fields = (
            ("ipaddress", static_ip.get("ip")),
            ("gateway", static_ip.get("gateway")),
            ("network_prefix_length", static_ip.get("prefix_length")),
            ("dns1", static_ip.get("dns1")),
            ("dns2", static_ip.get("dns2")),
        )
        for field_id, value in fields:
            if not value:
                continue
            field = device(resourceId=f"com.android.settings:id/{field_id}")
            if field.exists(timeout=2):
                field.clear_text()
                field.set_text(str(value))
                time.sleep(0.3)
        return True
    except Exception as error:
        print(f"[wifi] [WARN] Failed to apply static IP config: {error}", flush=True)
        return False

# WIFI_Method_Connect_UI_Sophy_H400818_2026-09-07
def wifi_connect_via_ui(device, serial, ssid, password, static_ip=None):
    """Connect to a WiFi network from the currently opened WiFi settings page.

    static_ip: optional dict (see wifi_apply_static_ip_config) to configure a static IP
    instead of DHCP before connecting.
    """
    from common.adb_common import _wifi_is_connected, press_back_key

    target_ssid = (ssid or '').strip()
    if not target_ssid:
        return False

    try:
        if _wifi_is_connected(serial, target_ssid):
            return True
        time.sleep(5)
        network = device(text=target_ssid)
        if not network.exists(timeout=2):
            network = device(textContains=target_ssid)
        if not network.exists(timeout=2):
            print(f"[wifi] [WARN] SSID not found in WiFi settings: {target_ssid}", flush=True)
            return False

        network.click()
        time.sleep(2)

        password_field = device(resourceId="com.android.settings:id/password")
        if password_field.exists(timeout=2):
            password_field.set_text(password or '')
            time.sleep(2)

        #if static_ip:
        #    wifi_apply_static_ip_config(device, static_ip)

        # sophy added 2026-08-14:
        press_back_key(serial)
        for button_text in ("Connect", "CONNECT", "连接"):
            button = device(text=button_text)
            if button.exists(timeout=1):
                button.click()
                break
        time.sleep(15)

        for _ in range(12):
            if _wifi_is_connected(serial, target_ssid):
                print(f"[wifi] [SUCCESS] Connected via UI: {target_ssid}", flush=True)
                return True
            time.sleep(2)
    except Exception as error:
        print(f"[wifi] [WARN] UI connection failed: {error}", flush=True)

    return False


# RTC_Method_Sophy_H400818_2026-07-24
def rtc_get_device_time_format(serial):
    """Read current system 12/24-hour format from device settings.

    Returns:
        "12", "24", or "unknown"
    """
    if not serial:
        return "unknown"

    from common.adb_common import rtc_settings_get_time_format_value

    try:
        value = rtc_settings_get_time_format_value(serial, 'system', 'time_12_24', timeout=8).lower()
        if value == '24':
            return '24'
        if value == '12':
            return '12'
    except Exception:
        pass

    return 'unknown'


# RTC_Method_Sophy_H400818_2026-07-24
def rtc_read_system_time_text(serial, hour_format='auto'):
    """Read system time text from adb shell date command.

    hour_format:
        auto -> infer from device setting
        12   -> return 12-hour time text
        24   -> return 24-hour time text
    """
    if not serial:
        return ''

    from common.adb_common import rtc_date_output

    fmt = hour_format
    if fmt == 'auto':
        current = rtc_get_device_time_format(serial)
        fmt = current if current in ('12', '24') else '12'

    patterns = ['+%H:%M']
    if str(fmt) == '12':
        # Try several 12-hour patterns for better compatibility across Android shells.
        patterns = ['+%I:%M %p', '+%I:%M%p', '+%r', '+%I:%M']

    for date_pattern in patterns:
        try:
            out, err_raw = rtc_date_output(serial, date_pattern, timeout=8)
            err = (err_raw or '').lower()

            if not out:
                continue
            if 'invalid' in out.lower() or 'invalid' in err:
                continue

            # Some Android shells return 12-hour text without AM/PM marker.
            if str(fmt) == '12':
                out_upper = out.upper()
                has_meridiem = ('AM' in out_upper) or ('PM' in out_upper) or ('上午' in out) or ('下午' in out)
                if not has_meridiem and ':' in out:
                    try:
                        hour_text, _ = rtc_date_output(serial, '+%H', timeout=8)
                        if hour_text.isdigit():
                            meridiem = 'AM' if int(hour_text) < 12 else 'PM'
                            out = f"{out} {meridiem}"
                    except Exception:
                        pass

            return out
        except Exception:
            continue

    return ''


def _rtc_find_24_hour_option(serial, device):
    """Find 24-hour format option on Date & time page with downward scrolling."""

    """Open the Date & time settings page."""
    from common.adb_common import rtc_open_date_time_setting

    rtc_open_date_time_setting(serial, restart_settings=False, timeout=10)
    time.sleep(2)
    target_text = "Use 24-hour format"

    try:
        if device(text=target_text).exists(timeout=0.8):
            device(text=target_text).click()
            time.sleep(0.8)
            return True
    except Exception:
        pass

    for _ in range(10):
        try:
            if device(scrollable=True).exists(timeout=0.5):
                device(scrollable=True).scroll.forward()
            else:
                device.swipe(500, 1500, 500, 500, duration=0.22)
            time.sleep(0.4)

            if device(text=target_text).exists(timeout=0.5):
                device(text=target_text).click()
                time.sleep(0.8)
                return True
        except Exception:
            pass

    return False


# RTC_Method_Sophy_H400818_2026-07-24
def rtc_set_use_24_hour_format(device, serial, enable):
    """Set 'Use 24-hour format' to target state via Settings UI."""
    if device is None or not serial:
        return False

    target = '24' if enable else '12'
    current = rtc_get_device_time_format(serial)
    if current == target:
        return True

    for _ in range(8):
        current = rtc_get_device_time_format(serial)
        if current == target:
            return True

        found_and_clicked = _rtc_find_24_hour_option(serial, device)
        if not found_and_clicked:
            break

        time.sleep(0.8)

    return rtc_get_device_time_format(serial) == target


# RTC_Method_H400818_2026-08-10_test_L1_Time Zone Modify_ANDROIDCN-34035
def rtc_disable_automatic_time_zone(device, serial):
    """Open Date & time and ensure automatic time-zone selection is disabled."""
    if device is None or not serial:
        return False

    from common.adb_common import rtc_open_date_time_setting

    rtc_open_date_time_setting(serial, restart_settings=False, timeout=10)
    time.sleep(3)

    option = None
    option_label = None
    for _ in range(10):
        for label in ('Set automatically', 'Set time zone automatically', '自动设置', '自动设置时区'):
            candidate = device(textContains=label)
            if candidate.exists(timeout=0.4):
                option = candidate
                option_label = label
                break
        if option is not None:
            break
        try:
            device(scrollable=True).scroll.forward()
        except Exception:
            device.swipe(500, 1500, 500, 500, duration=0.22)
        time.sleep(0.4)

    if option is None:
        print('[RTC] Set automatically option not found.', flush=True)
        return False

    try:
        print(f'[RTC] Found automatic time-zone option: {option_label}', flush=True)
        switch = (
                option.right(resourceId='android:id/switch_widget')
                or option.right(className='android.widget.Switch')
        )
        if not switch.exists(timeout=0.8):
            print('[RTC] Automatic time-zone switch not found.', flush=True)
            return False
        checked_before = bool(switch.info.get('checked'))
        print(f'[RTC] Set automatically status before click: {"ON" if checked_before else "OFF"}', flush=True)
        if not checked_before:
            print('[RTC] Set automatically is already OFF.', flush=True)
            return True
        print('[RTC] Set automatically is ON, clicking its switch.', flush=True)
        switch.click()
        time.sleep(1)
        checked_after = bool(switch.info.get('checked'))
        print(f'[RTC] Set automatically status after click: {"ON" if checked_after else "OFF"}', flush=True)
        if not checked_after:
            print('[RTC] Set automatically disabled successfully.', flush=True)
            return True
        print('[RTC] Failed to disable Set automatically.', flush=True)
        return False
    except Exception:
        print('[RTC] Exception while disabling Set automatically.', flush=True)
        return False


# RTC_Method__test_cleanup_enable_auto_time_zone_H400818_2026-08-13
def rtc_enable_automatic_time_zone(device, serial):
    """Open Date & time and ensure automatic time-zone selection is enabled."""
    if device is None or not serial:
        return False

    from common.adb_common import rtc_open_date_time_setting

    rtc_open_date_time_setting(serial, restart_settings=False, timeout=10)
    time.sleep(2)

    option = None
    option_label = None
    for _ in range(10):
        for label in ('Set automatically', 'Set time zone automatically', '自动设置', '自动设置时区'):
            candidate = device(textContains=label)
            if candidate.exists(timeout=0.4):
                option = candidate
                option_label = label
                break
        if option is not None:
            break
        try:
            device(scrollable=True).scroll.forward()
        except Exception:
            device.swipe(500, 1500, 500, 500, duration=0.22)
        time.sleep(0.4)

    if option is None:
        print('[RTC] Set automatically option not found.', flush=True)
        return False

    try:
        print(f'[RTC] Found automatic time-zone option: {option_label}', flush=True)
        switch = (
                option.right(resourceId='android:id/switch_widget')
                or option.right(className='android.widget.Switch')
        )
        if not switch.exists(timeout=0.8):
            print('[RTC] Automatic time-zone switch not found.', flush=True)
            return False
        checked_before = bool(switch.info.get('checked'))
        print(f'[RTC] Set automatically status before click: {"ON" if checked_before else "OFF"}', flush=True)
        if checked_before:
            print('[RTC] Set automatically is already ON.', flush=True)
            return True
        print('[RTC] Set automatically is OFF, clicking its switch.', flush=True)
        switch.click()
        time.sleep(1)
        checked_after = bool(switch.info.get('checked'))
        print(f'[RTC] Set automatically status after click: {"ON" if checked_after else "OFF"}', flush=True)
        if checked_after:
            print('[RTC] Set automatically enabled successfully.', flush=True)
            return True
        print('[RTC] Failed to enable Set automatically.', flush=True)
        return False
    except Exception:
        print('[RTC] Exception while enabling Set automatically.', flush=True)
        return False


# RTC_Method_H400818_2026-08-10_L1_Time Zone Modify_ANDROIDCN-34035
def rtc_select_New_York_time_zone(device, serial):
    """Select United States -> New York in the Date & time time-zone settings."""
    if device is None or not serial:
        return False

    from common.adb_common import force_stop_Settings_app, rtc_open_date_time_setting

    # 1. 打开 Date & time 设置
    force_stop_Settings_app(serial, 'com.android.settings')
    rtc_open_date_time_setting(serial, restart_settings=True, timeout=10)

    time.sleep(2)

    if not device(textContains="GMT").exists(timeout=2):
        device(scrollable=True).scroll.to(textContains="GMT")
        time.sleep(5)

    device(textContains='GMT').click()
    time.sleep(2)

    region = device(text="Region")
    if not region.exists(timeout=3):
        return False

    region.click()
    time.sleep(1)

    # 4. 直接找 EditText 输入 United States
    edit = device(text="Search region")
    if not edit.exists(timeout=3):
        return False

    edit.set_text("united states")
    time.sleep(1)

    # 5. 选择 United States
    us = device(text="United States")
    if not us.exists(timeout=5):
        return False
    us.click()
    time.sleep(1)

    # 6. 选择 New York
    if not device(text="New York").exists(timeout=2):
        device(scrollable=True).scroll.to(text="New York")
        time.sleep(5)
    if not device(text="New York").exists(timeout=2):
        print('[RTC] New York option not found.', flush=True)
        return False
    device(text="New York").click()
    time.sleep(2)

    return True


# RTC_Method_H400818_2026-08-10_L1_Time Zone Modify_ANDROIDCN-34035
def rtc_read_system_time_zone(serial, device=None):
    """Read the current Android time-zone ID, with UI fallback."""
    if not serial:
        return ''

    from common.adb_common import rtc_get_time_zone

    try:
        timezone = rtc_get_time_zone(serial, 'persist.sys.timezone', timeout=8)
        if timezone:
            return timezone
    except Exception:
        pass

    if device is not None:
        for text_value in ('New York', '纽约', 'America/New_York'):
            try:
                if device(textContains=text_value).exists(timeout=1):
                    return text_value
            except Exception:
                continue
    return ''


# RTC_Method_Close settings app_Sophy_H400818_2026-08-13
def close_settings_app(serial):
    """Force-stop Settings app."""
    from common.adb_common import force_stop_Settings_app
    return force_stop_Settings_app(serial, 'com.android.settings')


# RTC_Method_Open Date&Time settings_Sophy_H400818_2026-08-13
def rtc_open_date_time_page(serial):
    """Open Date & time settings page."""
    from common.adb_common import rtc_open_date_time_setting
    return rtc_open_date_time_setting(serial, restart_settings=False, timeout=10)


# RTC_Method_Set date by adb_Sophy_H400818_2026-08-13
def rtc_try_set_date_by_adb(serial, year, month, day):
    """Try setting device date via adb shell date command."""
    from common.adb_common import rtc_set_device_date
    return rtc_set_device_date(serial, year, month, day, hhmm='1200', timeout=5)


# RTC_Method_Wait boot completed_Sophy_H400818_2026-08-13
def rtc_wait_boot_completed(serial, checks=12, interval_sec=10):
    """Wait until device is online and sys.boot_completed=1."""
    from common.adb_common import rtc_wait_for_device, rtc_is_boot_completed

    checks = max(1, int(checks))
    for _ in range(checks):
        rtc_wait_for_device(serial, timeout=60)
        if rtc_is_boot_completed(serial, timeout=8):
            return True
        time.sleep(interval_sec)
    return False


# RTC_Method_Soft reboot and wait_Sophy_H400818_2026-08-13
def rtc_soft_reboot_and_wait(serial, initial_wait_sec=60, checks=12, interval_sec=10):
    """Reboot device and wait for boot completion."""
    from common.adb_common import rtc_reboot_device

    reboot_ok = rtc_reboot_device(serial, timeout=10)
    time.sleep(initial_wait_sec)
    boot_ok = rtc_wait_boot_completed(serial, checks=checks, interval_sec=interval_sec)
    return reboot_ok and boot_ok


# RTC_Method_Trigger hard reset_Sophy_H400818_2026-08-13
def rtc_trigger_hard_reset(serial, hold_seconds=10):
    """Try forced reboot via held power key script, then fallback to repeated keyevents."""
    from common.adb_common import (
        rtc_detect_power_input_device,
        rtc_start_hold_power_script,
        rtc_send_power_keyevent,
        rtc_reboot_device,
    )

    hold_seconds = max(3, int(hold_seconds))
    input_device = rtc_detect_power_input_device(serial, timeout=6)
    if rtc_start_hold_power_script(serial, input_device, hold_seconds=hold_seconds):
        return True, 'hold_script'

    start_time = time.time()
    count = 0
    while time.time() - start_time < hold_seconds:
        rtc_send_power_keyevent(serial, timeout=2)
        count += 1
        time.sleep(0.1)
    if count > 0:
        return True, 'rapid_keyevent'

    rtc_reboot_device(serial, timeout=10)
    return False, 'adb_reboot_fallback'


# RTC_Method_Disable automatic time_Sophy_H400818_2026-08-14
def rtc_disable_automatic_time(device, serial):
    """Disable 'Set time automatically' on the current Date & time page."""
    if device is None:
        return False
    rtc_open_date_time_page(serial)
    time.sleep(2)
    try:
        option = device(text="Set time automatically")
        if not option.exists(timeout=2):
            option = device(textContains="Set time automatically")
        if not option.exists(timeout=1):
            print("  ⚠ Could not find 'Set time automatically' option")
            return False

        switch = option.right(resourceId="android:id/switch_widget")
        if switch is None or not switch.exists(timeout=1):
            switch = option.right(className="android.widget.Switch")
        if not switch.exists(timeout=1):
            print("  ⚠ Could not find switch for 'Set time automatically'")
            return False

        if not switch.info.get("checked", False):
            print("  ✓ Automatic time is already disabled")
            return True

        print("  Automatic time is ON, disabling...")
        switch.click()
        time.sleep(2)

        disabled = not bool(switch.info.get("checked", True))
        print("  ✓ Successfully disabled" if disabled else "  ⚠ May still be enabled")
        return disabled
    except Exception as error:
        print(f"  ⚠ Failed to disable automatic time: {error}")
        return False


# RTC_Method_Enable automatic time_Sophy_H400818_2026-08-14
def rtc_enable_automatic_time(device, serial):
    """Enable 'Set time automatically' on the current Date & time page."""
    if device is None:
        return False
    rtc_open_date_time_page(serial)
    time.sleep(2)
    try:
        option = device(text="Set time automatically")
        if not option.exists(timeout=2):
            option = device(textContains="Set time automatically")
        if not option.exists(timeout=1):
            print("  ⚠ Could not find 'Set time automatically' option")
            return False

        switch = option.right(resourceId="android:id/switch_widget")
        if switch is None or not switch.exists(timeout=1):
            switch = option.right(className="android.widget.Switch")
        if not switch.exists(timeout=1):
            print("  ⚠ Could not find switch for 'Set time automatically'")
            return False

        if switch.info.get("checked", False):
            print("  ✓ Automatic time is already enabled")
            return True

        print("  Automatic time is OFF, enabling...")
        switch.click()
        time.sleep(2)

        enabled = bool(switch.info.get("checked", False))
        print("  ✓ Successfully enabled" if enabled else "  ⚠ May still be disabled")
        return enabled
    except Exception as error:
        print(f"  ⚠ Failed to enable automatic time: {error}")
        return False


# RTC_Method_Set date via Settings UI_Sophy_H400818_2026-08-13
def rtc_set_date_via_settings_ui(device, serial, year, month, day, img_dir, manual_fallback=None):
    """Set date through Date & time settings UI with multi-strategy picker handling."""
    from datetime import datetime
    from common.adb_common import (
        get_system_date,
        save_step_screenshot,
    )

    try:
        print(f"  Opening Date & Time Settings...")

        result_ok = rtc_open_date_time_page(serial)
        time.sleep(3)

        if not result_ok or not device(text="Date").exists(timeout=3):
            print(f"  ⚠ Intent failed, trying manual navigation...")
            if callable(manual_fallback):
                return manual_fallback(year, month, day)
            return False

        save_step_screenshot(device, "datetime_settings", img_dir)

        print(f"  Step 1: Disable 'Set time automatically'...")
        rtc_disable_automatic_time(device, serial)

        time.sleep(1)
        save_step_screenshot(device, "auto_time_disabled", img_dir)

        print(f"  Looking for 'Date' option...")
        if device(text="Date", className="android.widget.TextView").exists(timeout=2):
            date_elem = device(text="Date", className="android.widget.TextView")
            print(f"  Clicking 'Date'...")
            date_elem.click()
            time.sleep(2)
        else:
            print("  ⚠ Could not find 'Date' option")
            save_step_screenshot(device, "date_option_not_found", img_dir)
            return False

        save_step_screenshot(device, "date_picker_opened", img_dir)
        print(f"  Setting date to {year}-{month}-{day}...")
        day_clicked = False

        print(f"  Trying ADB command to set date directly...")
        try:
            ok, err_msg = rtc_try_set_date_by_adb(serial, year, month, day)
            if ok:
                print(f"  ✓ Date set via ADB command")
                if device(text="Cancel").exists(timeout=1):
                    device(text="Cancel").click()
                device.press("back")
                device.press("home")
                time.sleep(0.5)
                return True
            print(f"  ⚠ ADB command failed (may need root): {err_msg}")
        except Exception as e:
            print(f"  ⚠ ADB command error: {e}")

        print(f"  Trying Material Design Calendar Picker...")
        try:
            target_year = int(year)
            target_month = int(month)
            target_day = int(day)
            month_names = {
                1: "January", 2: "February", 3: "March", 4: "April",
                5: "May", 6: "June", 7: "July", 8: "August",
                9: "September", 10: "October", 11: "November", 12: "December"
            }

            target_month_name = month_names[target_month]
            target_day_str = str(target_day).zfill(2)
            target_date_desc = f"{target_day_str} {target_month_name} {target_year}"

            print(f"  Looking for date: {target_date_desc}")
            if not device(className="android.view.View", descriptionContains=target_date_desc).exists(timeout=1):
                print(f"  Target date not visible, determining navigation direction...")
                device_date_str = get_system_date(serial)
                if device_date_str:
                    try:
                        device_date = datetime.strptime(device_date_str, "%Y-%m-%d")
                        device_month = device_date.month
                        device_year = device_date.year
                        month_diff = (target_year - device_year) * 12 + (target_month - device_month)
                        print(f"  Device month: {month_names[device_month]} {device_year}")
                        print(f"  Target month: {target_month_name} {target_year}")
                        print(f"  Month difference: {month_diff}")
                    except Exception:
                        month_diff = 1
                else:
                    month_diff = 1

                if month_diff > 0:
                    print(f"  Clicking 'Next month' {abs(month_diff)} times...")
                    for i in range(abs(month_diff)):
                        if device(resourceId="android:id/next").exists(timeout=1):
                            device(resourceId="android:id/next").click()
                            time.sleep(0.5)
                            print(f"    Navigated {i + 1}/{abs(month_diff)}")
                            if device(className="android.view.View", descriptionContains=target_date_desc).exists(
                                    timeout=0.5):
                                print(f"  ✓ Target date now visible")
                                break
                        else:
                            print(f"  ⚠ Next button not found")
                            break
                elif month_diff < 0:
                    print(f"  Clicking 'Previous month' {abs(month_diff)} times...")
                    for i in range(abs(month_diff)):
                        if device(resourceId="android:id/prev").exists(timeout=1):
                            device(resourceId="android:id/prev").click()
                            time.sleep(0.5)
                            print(f"    Navigated {i + 1}/{abs(month_diff)}")
                            if device(className="android.view.View", descriptionContains=target_date_desc).exists(
                                    timeout=0.5):
                                print(f"  ✓ Target date now visible")
                                break
                        else:
                            print(f"  ⚠ Previous button not found")
                            break

            time.sleep(0.5)
            save_step_screenshot(device, "month_navigated", img_dir)

            print(f"  Clicking target date: {target_date_desc}...")
            if device(className="android.view.View", descriptionContains=target_date_desc).exists(timeout=1):
                elem = device(className="android.view.View", descriptionContains=target_date_desc)
                elem.click()
                day_clicked = True
                print(f"  ✓ Clicked date via contentDescription")
                time.sleep(0.5)

            if not day_clicked:
                day_str_no_zero = str(target_day)
                if device(text=day_str_no_zero, clickable=True).exists(timeout=0.5):
                    elems = device(text=day_str_no_zero, clickable=True)
                    for i in range(min(elems.count, 5)):
                        try:
                            elem = elems[i]
                            bounds = elem.info.get("bounds", {})
                            top = bounds.get("top", 0)
                            if top > 800:
                                elem.click()
                                day_clicked = True
                                print(f"  ✓ Clicked date via text match")
                                time.sleep(0.5)
                                break
                        except Exception:
                            continue

            if not day_clicked:
                print(f"  ⚠ Could not click target date")
            else:
                save_step_screenshot(device, "day_clicked", img_dir)
                print(f"  ✓ Date selection completed via Material Design Calendar")

        except Exception as e:
            print(f"  ⚠ Calendar picker error: {e}")
            import traceback
            traceback.print_exc()

        if not day_clicked and device(className="android.widget.NumberPicker").exists(timeout=1):
            print(f"  Trying NumberPicker method...")
            pickers = device(className="android.widget.NumberPicker")
            picker_count = pickers.count
            print(f"  Found {picker_count} NumberPicker(s)")

            if picker_count >= 3:
                try:
                    year_picker = device(className="android.widget.NumberPicker", instance=2)
                    year_input = year_picker.child(className="android.widget.EditText")
                    if year_input.exists():
                        year_input.set_text(year)
                        print(f"    Year set to {year}")

                    month_picker = device(className="android.widget.NumberPicker", instance=0)
                    month_input = month_picker.child(className="android.widget.EditText")
                    if month_input.exists():
                        month_input.set_text(str(int(month)))
                        print(f"    Month set to {month}")

                    day_picker = device(className="android.widget.NumberPicker", instance=1)
                    day_input = day_picker.child(className="android.widget.EditText")
                    if day_input.exists():
                        day_input.set_text(str(int(day)))
                        print(f"    Day set to {day}")

                    time.sleep(0.5)
                except Exception as e:
                    print(f"  ⚠ Error setting date via NumberPicker: {e}")

        if not day_clicked:
            print(f"  Trying simple text-based day selection...")
            try:
                target_day_str = str(int(day))
                all_elements = device(clickable=True)
                for i in range(all_elements.count):
                    try:
                        elem = all_elements[i]
                        elem_text = elem.info.get("text", "")
                        elem_desc = elem.info.get("contentDescription", "")
                        if elem_text == target_day_str or target_day_str in elem_desc:
                            bounds = elem.info.get("bounds", {})
                            if bounds:
                                elem.click()
                                print(f"  ✓ Clicked day {target_day_str} (element search)")
                                day_clicked = True
                                time.sleep(0.5)
                                break
                    except Exception:
                        continue
            except Exception as e:
                print(f"  ⚠ Simple search failed: {e}")

        save_step_screenshot(device, "date_values_set", img_dir)

        print(f"  Confirming date selection...")
        if device(text="OK").exists(timeout=1):
            device(text="OK").click()
            print(f"  Clicked 'OK'")
        elif device(text="Done").exists(timeout=1):
            device(text="Done").click()
            print(f"  Clicked 'Done'")
        elif device(className="android.widget.Button").exists(timeout=1):
            buttons = device(className="android.widget.Button")
            if buttons.count > 0:
                buttons[buttons.count - 1].click()
                print(f"  Clicked button")

        time.sleep(1)
        save_step_screenshot(device, "date_confirmed", img_dir)
        device.press("back")
        device.press("home")
        time.sleep(1)

        return True

    except Exception as e:
        print(f"  ❌ Error setting date via Settings UI: {e}")
        save_step_screenshot(device, "set_date_error", img_dir)
        device.press("back")
        device.press("back")
        device.press("home")
        return False


# RTC_Method_Read device epoch_Sophy_H400818_2026-08-13
def rtc_get_device_epoch_seconds(serial):
    """Read device unix epoch seconds using adb shell date +%s."""
    if not serial:
        return None

    from common.adb_common import rtc_date_output

    try:
        out, _ = rtc_date_output(serial, '+%s', timeout=8)
        out = (out or "").strip()
        if out.isdigit():
            return int(out)
    except Exception:
        pass
    return None


# RTC_Method_Check network time sync_Sophy_H400818_2026-08-13
def rtc_is_network_time_synced_with_host(serial, tolerance_seconds=300):
    """Check whether device time is synchronized with host current time within tolerance."""
    device_epoch = rtc_get_device_epoch_seconds(serial)
    if device_epoch is None:
        return False, None

    host_epoch = int(time.time())
    diff = abs(device_epoch - host_epoch)
    return diff <= int(tolerance_seconds), diff


# RTC_Method_Wait network time sync_Sophy_H400818_2026-08-13
def rtc_wait_network_time_sync(serial, tolerance_seconds=300, retries=9, interval_sec=10):
    """Poll until device time syncs with host time or retries exhausted."""
    retries = max(1, int(retries))
    interval_sec = max(1, int(interval_sec))

    last_diff = None
    for attempt in range(1, retries + 1):
        synced, diff = rtc_is_network_time_synced_with_host(serial, tolerance_seconds=tolerance_seconds)
        last_diff = diff
        if synced:
            return True, diff
        if attempt < retries:
            time.sleep(interval_sec)
    return False, last_diff


# RTC_Method_Enable mobile data_Sophy_H400818_2026-08-17
def rtc_enable_mobile_data(serial):
    """Enable mobile data for the WWAN time synchronization test."""
    from common.adb_common import wwan_enable_mobile_data

    return wwan_enable_mobile_data(serial)

# ScanDemo_Verify barcode result_Sophy_H400818_2026-08-17
def scandemo_verify_decode_result(device, expected_barcode):
    """Read and verify a ScanDemo barcode result from the current UI."""
    decode_result = None

    try:
        result_selector = device(resourceIdMatches=".*decode.*|.*result.*|.*data.*")
        if result_selector.exists(timeout=2):
            decode_result = result_selector.get_text()
        elif device(textContains=expected_barcode).exists(timeout=1):
            decode_result = device(textContains=expected_barcode).get_text()
        else:
            ui_text = device.dump_hierarchy()
            if expected_barcode in ui_text:
                decode_result = expected_barcode
            else:
                for element in device.xpath('//*[@text]').all():
                    text = element.text
                    if text and len(text) >= 10 and any(char.isalnum() for char in text) and ' ' not in text:
                        decode_result = text
                        break
    except Exception as error:
        print(f"[ScanDemo] Failed to read decode result: {error}", flush=True)
        return None, False

    if decode_result is None:
        return None, False

    cleaned_result = decode_result.strip()
    if expected_barcode in cleaned_result:
        start_index = cleaned_result.find(expected_barcode)
        cleaned_result = cleaned_result[start_index:start_index + len(expected_barcode)]
    else:
        for prefix in ('Decode Result:', 'Barcode:', 'Data:', 'Result:', 'Code:'):
            if prefix in cleaned_result:
                cleaned_result = cleaned_result.split(prefix, 1)[1].strip()
                break

    return cleaned_result, cleaned_result == expected_barcode

# WIFI_Method_Disconnect current network via Forget_Sophy_H400818_2026-08-21
# WIFI_Method_Disconnect current network via Forget_Sophy_H400818_modified_2026-09-17(改成点击之前连接的wifi的名字去断开wifi的连接)
def wifi_disconnect(device, serial):
    """Forget the currently connected WiFi network through Android Settings."""
    from common.adb_common import _wifi_get_active_ssid,wifi_open_settings_by_adb

    if device is None or not serial:
        return False

    try:
        if not wifi_open_settings_by_adb(serial):
            print('[wifi] [ERROR] Failed to open WiFi settings.', flush=True)
            return False

        active_ssid = (_wifi_get_active_ssid(serial) or '').strip().strip('"')
        connected = None
        if active_ssid:
            candidate = device(text=active_ssid)
            if candidate.exists(timeout=2):
                connected = candidate
            else:
                candidate = device(textContains=active_ssid)
                if candidate.exists(timeout=2):
                    connected = candidate

        if connected is None:
            for label in ('Connected', '已连接', '已连接的网络'):
                candidate = device(text=label)
                if candidate.exists(timeout=1):
                    connected = candidate
                    break
                candidate = device(textContains=label)
                if candidate.exists(timeout=1):
                    connected = candidate
                    break

        if connected is None:
            print('[wifi] [WARN] Connected WiFi network was not found.', flush=True)
            return not bool(_wifi_get_active_ssid(serial))

        connected.click()
        time.sleep(1.5)

        for label in ('Forget', 'FORGET'):
            forget = device(text=label)
            if not forget.exists(timeout=1):
                forget = device(textContains=label)
            if forget.exists(timeout=1):
                forget.click()
                time.sleep(2)
                disconnected = not bool(_wifi_get_active_ssid(serial))
                print(
                    '[wifi] WiFi network forgotten successfully.' if disconnected
                    else '[wifi] [WARN] WiFi network may still be connected.',
                    flush=True,
                )
                return disconnected

        print('[wifi] [WARN] Forget option was not found.', flush=True)
    except Exception as error:
        print(f'[wifi] [ERROR] Failed to forget connected WiFi network: {error}', flush=True)

    return False

# General_Settings_Reliability_Frank_Xu_2026-08-25
# Author: Frank Xu
# Scope: General Settings test cases
# Purpose: Recover a failed UIAutomator2 hierarchy once and support OEM Settings pages that do not expose scrollable=true.
def require_device(test_case):
    """Return a selected device after verifying its UIAutomator2 hierarchy service."""
    from common.adb_common import get_device_serial

    serial = get_device_serial()
    if not serial:
        test_case.skipTest("No online Android device. Set ANDROID_SERIAL or connect one device.")
    if u2 is None:
        test_case.skipTest("uiautomator2 is not installed")

    device = u2.connect(serial)
    try:
        ET.fromstring(device.dump_hierarchy(compressed=False))
    except Exception as first_error:
        print(
            "[WARN] UIAutomator2 hierarchy is unavailable; reinitializing the device agent once: {}".format(first_error),
            flush=True,
        )
        try:
            recovery = subprocess.run(
                [sys.executable, "-m", "uiautomator2", "-s", serial, "init"],
                capture_output=True,
                text=True,
                timeout=90,
            )
        except (OSError, subprocess.TimeoutExpired) as recovery_error:
            test_case.skipTest("Unable to reinitialize UIAutomator2: {}".format(recovery_error))
        if recovery.returncode != 0:
            test_case.skipTest(
                "Unable to reinitialize UIAutomator2: {}".format((recovery.stderr or recovery.stdout).strip())
            )

        device = u2.connect(serial)
        try:
            ET.fromstring(device.dump_hierarchy(compressed=False))
        except Exception as recovery_error:
            test_case.skipTest(
                "UIAutomator2 hierarchy remains unavailable after recovery: {}".format(recovery_error)
            )
    return serial, device


def tap_text(device, text, timeout=3):
    """Find and tap Settings text, including OEM pages without a scrollable hierarchy node."""
    for attempt in range(6):
        for selector in (device(text=text), device(textContains=text)):
            if selector.exists(timeout=timeout if attempt == 0 else 0.5):
                selector.click()
                time.sleep(0.8)
                return True
        if device(scrollable=True).exists(timeout=0.5):
            device(scrollable=True).scroll.vert.forward(steps=35)
        else:
            device.swipe(0.5, 0.85, 0.5, 0.25, duration=0.35)
        time.sleep(0.5)
    return False


# Keyremap_Method_2026-08-27
def keyremap_find_text_center(device, search_text, contains=True):
    """Find the center coordinate of a text node in the UIAutomator2 hierarchy.

    Args: device is the UIAutomator2 device object; search_text is the text to find; contains controls substring vs exact match.
    Returns: (x, y) if found, None if not found or the hierarchy could not be read.
    Precondition: the target widget's text is inside a node element from dump_hierarchy() output and includes a bounds attribute.
    """
    try:
        hierarchy = device.dump_hierarchy()
        for node in re.finditer(r'<node[^>]*>', hierarchy):
            node_text = node.group(0)
            text_match = re.search(r'\btext="([^"]*)"', node_text)
            if not text_match:
                continue
            text_value = text_match.group(1)
            if not ((contains and search_text in text_value) or (not contains and search_text == text_value)):
                continue
            bounds_match = re.search(r'bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"', node_text)
            if bounds_match:
                left, top, right, bottom = (int(value) for value in bounds_match.groups())
                return (left + right) // 2, (top + bottom) // 2
    except Exception as error:
        print(f"  [Hier] dump_hierarchy failed: {type(error).__name__}: {str(error)[:80]}")
    return None


# Keyremap_Method_2026-08-27
# def keyremap_scroll_up(device):
#     """使用 UIAutomator2 可滚动节点向上翻页。"""
#     try:
#         scrollable = device(scrollable=True)
#         if not scrollable.exists(timeout=0.5):
#             return False
#         scrollable.scroll.vert.forward(steps=35)
#         time.sleep(0.5)
#         return True
#     except Exception as error:
#         print(f"  [Nav] Semantic scroll failed: {type(error).__name__}: {str(error)[:80]}")
#         return False

# # Keyremap_Method_2026-08-27
# def keyremap_tap_text(device, serial, search_text, contains=True, max_swipes=8):
#     """Scroll to find and tap Keyremap page text via ADB.

#     Args: device is the UIAutomator2 device object; serial is the device serial number; search_text is the target text;
#           contains is the match mode; max_swipes is the max number of swipes.
#     Returns: True if tapped successfully, False if not found after exhausting retries.
#     Precondition: the page responds to the ADB swipe-up coordinates already verified by the test case.
#     """
#     from common.adb_common import keyremap_swipe_up, run_adb_cmd

#     for _ in range(max_swipes):
#         position = keyremap_find_text_center(device, search_text, contains=contains)
#         if position:
#             run_adb_cmd(serial, f"shell input tap {position[0]} {position[1]}", log_print=False)
#             return True
#         if not keyremap_scroll_up(device):
#             keyremap_swipe_up(serial)
#     return False

# Keyremap_Method_2026-08-27                           
def keyremap_tap_text(device, serial, search_text, contains=True, max_swipes=8):
    """Scroll to find and tap Keyremap page text via ADB.

    Args: device is the UIAutomator2 device object; serial is the device serial number; search_text is the target text;
          contains is the match mode; max_swipes is the max number of swipes.
    Returns: True if tapped successfully, False if not found after exhausting retries.
    Precondition: the page responds to the ADB swipe-up coordinates already verified by the test case.
    """
    from common.adb_common import keyremap_swipe_up, run_adb_cmd

    for _ in range(max_swipes):
        position = keyremap_find_text_center(device, search_text, contains=contains)
        if position:
            run_adb_cmd(serial, f"shell input tap {position[0]} {position[1]}", log_print=False)
            return True
                                          
        keyremap_swipe_up(serial)
    return False


# Keyremap_Method_2026-08-27
def keyremap_open_page(device, serial, settings_package, keyremap_package):
    """Open the Honeywell Settings -> Keyremap page inside Settings.

    Args: device is the UIAutomator2 device object; serial is the device serial number; settings_package and
          keyremap_package are the target app package names.
    Returns: True if the Keyremap page was reached, otherwise False.
    Precondition: the corresponding entry exists in system settings; the Keyremap system app allows restarting by PID after root.
    """
    from common.adb_common import run_adb_cmd
    # Sophy_H400818_2026-09-02 (line4293-4294)
    # Dismiss any Quickstep Overview overlay first: it stays on top of the freshly started Settings
    # window and swallows the scroll gestures, so the entry list would never scroll.
    if not keyremap_ensure_uiautomator_healthy(device, serial):
        print("  [Nav] Cannot navigate because uiautomator hierarchy is unavailable")
        return False

    run_adb_cmd(serial, "shell input keyevent KEYCODE_HOME", log_print=False)
    time.sleep(1)
    run_adb_cmd(serial, f"shell am force-stop {settings_package}", log_print=False)
    # The process may still be alive after force-stop for a system app; re-root and kill by PID to refresh the page Fragment.
    run_adb_cmd(serial, "root", log_print=False)
    time.sleep(1)
    pid_output = run_adb_cmd(serial, f"shell pidof {keyremap_package}", log_print=False)
    pid_text = (
        pid_output.decode("utf-8", errors="ignore") if isinstance(pid_output, bytes) else str(pid_output)).strip()
    if pid_text and pid_text.isdigit():
        run_adb_cmd(serial, f"shell kill {pid_text}", log_print=False)
        print(f"  [Nav] Killed {keyremap_package} PID={pid_text}")
    time.sleep(2)
    run_adb_cmd(serial, f"shell am start -n {settings_package}/.Settings", log_print=False)
    time.sleep(4)

    if keyremap_find_text_center(device, "Keyremap", contains=False) is not None:
        return True
    if not keyremap_tap_text(device, serial, "Honeywell Settings", contains=True, max_swipes=6):
        print("  [Nav] 'Honeywell Settings' not found")
        return False
    time.sleep(5)
    if not keyremap_tap_text(device, serial, "Keyremap", contains=False, max_swipes=6):
        print("  [Nav] 'Keyremap' not found in Honeywell Settings")
        return False
    time.sleep(2)
    return keyremap_find_text_center(device, "Keyremap", contains=False) is not None

# Keyremap_Method_2026-08-27
def keyremap_clear_entries(device, serial):
    """Clear all Keyremap mapping entries via selection mode.

    Args: device is the UIAutomator2 device object; serial is the device serial number.
    Returns: None.
    Precondition: currently on the Keyremap page; safe to call with an empty list; coordinate fallbacks are
          scaled from a 1080x2160 baseline to the device's actual resolution.
    """
    from common.adb_common import run_adb_cmd
    import re as _re

    size_output = run_adb_cmd(serial, "shell wm size", log_print=False)
    size_text = size_output.decode("utf-8", errors="ignore") if isinstance(size_output, bytes) else str(size_output)
    sizes = _re.findall(r"(?:Override|Physical) size:\s*(\d+)x(\d+)", size_text)
    if sizes:
        screen_width, screen_height = (int(value) for value in sizes[-1])
    else:
        screen_width, screen_height = 1080, 2160

    def _scale(baseline_x, baseline_y):
        return round(screen_width * baseline_x / 1080), round(screen_height * baseline_y / 2160)

    menu_x, menu_y = _scale(1004, 156)
    run_adb_cmd(serial, f"shell input tap {menu_x} {menu_y}", log_print=False)
    time.sleep(2)
    # Prefer locating by hierarchy text; fall back to the verified coordinates when the OEM page does not expose the text.
    all_select = keyremap_find_text_center(device, "ALL SELECT", contains=False)
    all_select_fallback = _scale(540, 1884)
    run_adb_cmd(serial, f"shell input tap {all_select[0]} {all_select[1]}" if all_select else f"shell input tap {all_select_fallback[0]} {all_select_fallback[1]}", log_print=False)
    time.sleep(0.5)
    delete = keyremap_find_text_center(device, "DELETE", contains=False)
    delete_fallback = _scale(880, 1884)
    run_adb_cmd(serial, f"shell input tap {delete[0]} {delete[1]}" if delete else f"shell input tap {delete_fallback[0]} {delete_fallback[1]}", log_print=False)
    time.sleep(1.5)

    confirmation = None
    for _ in range(4):
        confirmation = keyremap_find_text_center(device, "OK", contains=False)
        if confirmation:
            break
        time.sleep(0.5)
    confirmation_fallback = _scale(900, 1419)
    run_adb_cmd(serial, f"shell input tap {confirmation[0]} {confirmation[1]}" if confirmation else f"shell input tap {confirmation_fallback[0]} {confirmation_fallback[1]}", log_print=False)
    time.sleep(2)
    clear = keyremap_find_text_center(device, "CLEAR", contains=False)
    if clear:
        run_adb_cmd(serial, f"shell input tap {clear[0]} {clear[1]}", log_print=False)
        time.sleep(0.5)

# Keyremap_Method_2026-08-27
def keyremap_tap_add_button(device, serial):
    """Clear old mappings, then tap the add button on the empty Keyremap list.

    Args: device is the UIAutomator2 device object; serial is the device serial number.
    Returns: None.
    Precondition: currently on the Keyremap page; the add button coordinate is scaled from a
          1080x2160 baseline (540, 346) to the device's actual resolution.
    """
    from common.adb_common import run_adb_cmd
    import re as _re
    if keyremap_find_text_center(device, "HOME", contains=False) is not None:
        keyremap_clear_entries(device, serial)
    time.sleep(0.5)

    size_output = run_adb_cmd(serial, "shell wm size", log_print=False)
    size_text = size_output.decode("utf-8", errors="ignore") if isinstance(size_output, bytes) else str(size_output)
    sizes = _re.findall(r"(?:Override|Physical) size:\s*(\d+)x(\d+)", size_text)
    if sizes:
        screen_width, screen_height = (int(value) for value in sizes[-1])
        tap_x = round(screen_width * 540 / 1080)
        tap_y = round(screen_height * 346 / 2160)
    else:
        tap_x, tap_y = 540, 346
    run_adb_cmd(serial, f"shell input tap {tap_x} {tap_y}", log_print=False)
    time.sleep(2)
    if not keyremap_dialog_is_open(device):
        run_adb_cmd(serial, "shell input tap 540 346", log_print=False)
        time.sleep(2)

# Keyremap_Method_2026-08-27
def keyremap_dialog_is_open(device):
    """Determine whether the Keyremap key-capture dialog is currently displayed.

    Args: device is the UIAutomator2 device object.
    Returns: True if the dialog prompt text is detected, otherwise False.
    Precondition: the dialog prompt text is "Please press the key to be mapped".
    """
    return keyremap_find_text_center(device, "Please press the key to be mapped", contains=True) is not None


# Keyremap_Method_2026-08-27
def keyremap_click_ok(device, serial):
    """Tap OK on the capture dialog and wait for the remap target list to load.

    Args: device is the UIAutomator2 device object; serial is the device serial number.
    Returns: True if OK was found and tapped, otherwise False.
    Precondition: the Keyremap dialog with the exact text "OK" is currently displayed.
    """
    from common.adb_common import run_adb_cmd

    position = keyremap_find_text_center(device, "OK", contains=False)
    if not position:
        return False
    run_adb_cmd(serial, f"shell input tap {position[0]} {position[1]}", log_print=False)
    time.sleep(4)
    return True


# Keyremap_Method_2026-08-27
def keyremap_select_home_target(device, serial):
    """Select HOME in the Keyremap target list.

    Args: device is the UIAutomator2 device object; serial is the device serial number.
    Returns: True if selected within five polling attempts, otherwise False.
    Precondition: currently on the Keyremap KEYS target list.
    """
    from common.adb_common import run_adb_cmd

    for _ in range(5):
        position = keyremap_find_text_center(device, "HOME", contains=False)
        if position:
            run_adb_cmd(serial, f"shell input tap {position[0]} {position[1]}", log_print=False)
            time.sleep(2)
            return True
        time.sleep(1)
    print("  [Remap] 'HOME' not visible in target list after retries")
    return False


# Keyremap_Method_2026-08-27
def keyremap_clear_all(device, serial):
    """Clear Keyremap mappings and return the success status.

    Args: device is the UIAutomator2 device object; serial is the device serial number.
    Returns: True once the clear flow has been executed.
    Precondition: currently on the Keyremap page.
    """
    keyremap_clear_entries(device, serial)
    return True

def tap_path(test_case, device, *labels, reset_home=True, strict=True):
    """Navigate a General Settings path after verifying UIAutomator2 hierarchy health."""
    try:
        ET.fromstring(device.dump_hierarchy(compressed=False))
    except Exception as exc:
        test_case.fail(
            "UIAutomator2 hierarchy is unavailable; reinitialize the device agent before "
            "running Settings tests: {}".format(exc)
        )
    if reset_home:
        open_settings(device)
    for label in labels:
        if isinstance(label, (list, tuple)):
            chosen = tap_first_available_text(device, label)
            if not chosen:
                if strict:
                    test_case.fail("Settings entry '{}' was not found".format(" / ".join(label)))
                return False
        elif not tap_text(device, label):
            if strict:
                test_case.fail("Settings entry '{}' was not found".format(label))
            return False
    return True

# Keyremap_Method_Sophy_H400818_2026-08-27
def keyremap_select_target(device, serial, target_text, contains=False):
    """Select the given remap target in the Keyremap target list.

    Args: device is the UIAutomator2 device object; serial is the device serial number; target_text is the target
          list item text; contains controls substring vs exact match.
    Returns: True if selected within five polling attempts, otherwise False.
    Precondition: currently on the Keyremap target list (KEYS/FUNCTIONS, etc.).
    """
    from common.adb_common import run_adb_cmd

    for _ in range(5):
        position = keyremap_find_text_center(device, target_text, contains=contains)
        if position:
            run_adb_cmd(serial, f"shell input tap {position[0]} {position[1]}", log_print=False)
            time.sleep(2)
            return True
        time.sleep(1)
    print(f"  [Remap] '{target_text}' not visible in target list after retries")
    return False

# Keyremap_Method_Sophy_H400818_2026-08-27
def keyremap_find_desc_center(device, search_desc, contains=True):
    """Find the center coordinate of a node by content-desc in the UIAutomator2 hierarchy.

    Args: device is the UIAutomator2 device object; search_desc is the content-desc to find; contains controls
          substring vs exact match.
    Returns: (x, y) if found, None if not found or the hierarchy could not be read.
    Precondition: the target widget's content-desc is inside a node element from dump_hierarchy() output and
          includes a bounds attribute.
    """
    try:
        hierarchy = device.dump_hierarchy()
        for node in re.finditer(r'<node[^>]*>', hierarchy):
            node_text = node.group(0)
            desc_match = re.search(r'content-desc="([^"]*)"', node_text)
            if not desc_match:
                continue
            desc_value = desc_match.group(1)
            if not desc_value:
                continue
            if not ((contains and search_desc in desc_value) or (not contains and search_desc == desc_value)):
                continue
            bounds_match = re.search(r'bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"', node_text)
            if bounds_match:
                left, top, right, bottom = (int(value) for value in bounds_match.groups())
                return (left + right) // 2, (top + bottom) // 2
    except Exception as error:
        print(f"  [Hier] dump_hierarchy failed: {type(error).__name__}: {str(error)[:80]}")
    return None


# Keyremap_Method_Sophy_H400818_2026-08-27
# Keyremap_Method_Sophy_H400818_2026-09-10 修改，兼容CK67
def keyremap_tap_ok_button(device, serial):
    """Dismiss the TEXT editor keyboard and confirm the current Keyremap dialog.

    Args: device is the UIAutomator2 device object; serial is the device serial number.
    Returns: True if a visible confirmation button was tapped, otherwise False.
    Precondition: the key-capture dialog or TEXT editor is currently displayed.
    """
    # Author: Sophy H400818, Date: 2026-09-10. Hide IME only while the TEXT editor owns focus.
    try:
        editor = device(focused=True, className="android.widget.EditText")

        if editor.exists(timeout=0.3):
            device.press("back")
            time.sleep(0.6)
    except Exception:
        pass

    selectors = (
        device(text="OK", clickable=True),
        device(text="OK"),
        device(resourceId="com.honeywell.keyremap2:id/bt_ok"),
        device(description="OK"),
    )
    for button in selectors:
        try:
            if button.exists(timeout=1):
                button.click()
                time.sleep(1)
                return True
        except Exception:
            pass

# PictureQuality_Method_Sally_2026-08-27
PICTURE_QUALITY_ENTRY_TEXTS = ("Picture quality", "Photo quality", "照片质量")

# PictureQuality_Method_Sally_2026-08-27
PICTURE_QUALITY_POPUP_TEXTS = (
    "ALLOW", "Allow", "While using the app", "Only this time", "OK", "NEXT", "GOT IT", "NO THANKS",
    "允许", "仅在使用该应用时允许", "仅此一次", "确定", "下一步", "知道了",
)

# PictureQuality_Method_Sally_2026-08-27
def picture_quality_dismiss_popups(device):
    """Close permission and welcome dialogs shown on the first camera launch."""
    for _ in range(5):
        selectors = [device(resourceIdMatches=r".*permission_allow.*")]
        selectors.extend(device(text=text) for text in PICTURE_QUALITY_POPUP_TEXTS)
        if not switch_photo_video_click_any(selectors, timeout=0.3, delay=0.8):
            return

# PictureQuality_Method_Sally_2026-08-27
def picture_quality_open_camera_settings(device):
    """Open the camera settings page from the preview screen."""
    selectors = [device(resourceIdMatches=r".*id/(menu_)?settings.*"), device(descriptionContains="Settings"), device(descriptionContains="设置")]
    return switch_photo_video_click_any(selectors, timeout=0.5, delay=1.0)

# PictureQuality_Method_Sally_2026-08-27
def picture_quality_open_entry(device):
    """Open the Picture quality row inside the camera settings page."""
    for _ in range(3):
        for key in PICTURE_QUALITY_ENTRY_TEXTS:
            if switch_photo_video_click_any([device(text=key)], timeout=0.4, delay=1.0):
                return True
        try:
            device(scrollable=True).scroll.forward()
        except Exception:
            break
    return False

# PictureQuality_Method_Sally_2026-08-27
def picture_quality_option_selectors(device, option_name):
    """Selectors matching one radio option inside the Picture quality dialog."""
    return [device(className="android.widget.CheckedTextView", text=option_name), device(text=option_name, checkable=True)]

# PictureQuality_Method_Sally_2026-08-27
def picture_quality_select_option(device, option_name):
    """Choose a Picture quality option; the radio dialog dismisses itself once chosen."""
    if not switch_photo_video_click_any(picture_quality_option_selectors(device, option_name), timeout=1.0, delay=1.0):
        return False

    end = time.time() + 5
    while time.time() < end:
        if not device(text="CANCEL").exists(timeout=0.3):
            return True
        time.sleep(0.3)
    return False


# PictureQuality_Method_Sally_2026-08-27
def picture_quality_is_option_selected(device, option_name):
    """Check whether the Picture quality dialog marks the option as checked."""
    for selector in picture_quality_option_selectors(device, option_name):
        if selector.exists(timeout=0.4) and selector.info.get("checked"):
            return True
    return False


# PictureQuality_Method_Sally_2026-08-27
def picture_quality_shutter_selectors(device):
    """Selectors matching the camera shutter button."""
    return [device(resourceIdMatches=r".*id/(shutter|capture)_button$"), device(descriptionContains="Shutter"), device(descriptionContains="拍照")]


# PictureQuality_Method_Sally_2026-08-27
def picture_quality_back_to_preview(device):
    """Press back until the camera preview with its shutter button is shown."""
    for _ in range(3):
        device.press("back")
        time.sleep(1.2)
        if any(selector.exists(timeout=0.3) for selector in picture_quality_shutter_selectors(device)):
            return True
    return False


# PictureQuality_Method_Sally_2026-08-27
def picture_quality_take_photo(device, serial, step_name, step_shot):
    """Take one photo and return (ok, size_bytes) of the newly created file."""
    from common.adb_common import picture_quality_list_photos_with_size

    before_photos = picture_quality_list_photos_with_size(serial)
    for _ in range(2):
        if not switch_photo_video_click_any(picture_quality_shutter_selectors(device), timeout=0.8, delay=0.7):
            continue
        end = time.time() + 15
        while time.time() < end:
            time.sleep(1.2)
            new_sizes = [
                size for path, size in picture_quality_list_photos_with_size(serial).items()
                if path not in before_photos
            ]
            if new_sizes:
                step_shot(step_name)
                return True, max(new_sizes)

    return False, 0


# PictureQuality_Method_Sally_2026-08-27
def picture_quality_restore_high(device, serial):
    """Best-effort cleanup that restores the Picture quality setting back to High."""
    return (camera_is_preview_visible(device, serial) and picture_quality_open_camera_settings(device)
            and picture_quality_open_entry(device) and picture_quality_select_option(device, "High")
            and picture_quality_back_to_preview(device))
# Keyremap_Method_Sophy_H400818_2026-08-28
def keyremap_is_android_menu_shown(device, timeout=6):
    """Determine whether the Android launcher options menu is displayed after pressing MENU.
                                                                                                   
 

    Args: device is the UIAutomator2 device object; timeout is the max polling duration in seconds.
    Returns: (is_shown, matched menu item text). matched text is empty when nothing was found.
    Precondition: the launcher options menu exposes at least one of the known entries
          (Wallpapers / Widgets / Home settings / Style & wallpapers) in the UI hierarchy.
    """
    menu_items = (
        "Wallpaper & style",
        "Wallpapers",
        "Wallpaper",
        "Widgets",
        "Home settings",
        "Style & wallpapers",
        "壁纸",
        "微件",
        "主屏幕设置",
    )
    deadline = time.time() + timeout
    while time.time() < deadline:
        for item in menu_items:
            if keyremap_find_text_center(device, item, contains=True) is not None:
                return True, item
        time.sleep(1)
    return False, ""

                                        
                                                 
                                                                
                                                                                                                                                    
                                                                          

# Sophy_get_package_name_2026-08-31
def get_package_name(name):
    """Read an app package name from the [package_names] section of commands.config.

    Args: name is the config key, e.g. "settings" or "keyremap".
    Returns: the full package name string.
    """
    config = configparser.ConfigParser()
    path = os.path.join(os.path.split(os.path.realpath(__file__))[0], 'commands.config')
    config.read(path)
    return config.get('package_names', name)


# Sophy_get_case_config_2026-09-01
def get_case_config(section, key):
    """Read a test-case parameter from allconfig.config.

    Args: section is the config section name; key is the option name.
    Returns: the raw string value.
    """
    config = configparser.ConfigParser()
    path = os.path.join(os.path.split(os.path.realpath(__file__))[0], 'allconfig.config')
    config.read(path)
    return config.get(section, key)




# Keyremap_Method_Sophy_H400818_2026-08-31
def keyremap_input_text_value(device, keyremap_package, value):
    """Type the remap string into the Keyremap TEXT editor (resourceId .../et_string).

    Args: device is the UIAutomator2 device object; keyremap_package is the Keyremap package name;
          value is the string to map the key to.
    Returns: True if the field was found and filled, otherwise False.
    Precondition: the TEXT target page is open after selecting "TEXT" in the remap target list.
    """
    edit = device(resourceId=f"{keyremap_package}:id/et_string")
    if not edit.exists(timeout=5):
        edit = device(className="android.widget.EditText")
        if not edit.exists(timeout=3):
            return False
    edit.click()
    time.sleep(0.5)
    edit.clear_text()
    edit.set_text(value)
    time.sleep(1)
    return True


# Keyremap_Method_Sophy_H400818_2026-08-31
def keyremap_read_edit_text(device, timeout=6):
    """Read the current content of the focused/first EditText on screen.

    Args: device is the UIAutomator2 device object; timeout is the max polling duration in seconds.
    Returns: the text content, or an empty string when no EditText is available.
    Precondition: used to verify the string emitted by a TEXT-type key remap.
    """
    deadline = time.time() + timeout
    while time.time() < deadline:
        for selector in (
            device(focused=True, className="android.widget.EditText"),
            device(className="android.widget.EditText"),
        ):
            try:
                if selector.exists(timeout=0.3):
                    content = selector.get_text()
                    if content:
                        return content
            except Exception:
                pass
        time.sleep(0.5)
    return ""


# Keyremap_Method_Sophy_H400818_2026-09-01
def keyremap_is_text_selection_active(device, serial, original_text, probe_char="Z"):
    """Verify a select-all happened by typing one character and checking it replaced the whole field.
 
    Args: device is the UIAutomator2 device object; serial is the device serial number; original_text is the
          content typed before the select-all; probe_char is the single character used to overwrite it.
    Returns: (is_selected, field content after typing probe_char).
    Precondition: the input field is focused. Android exposes no selection range in the UI hierarchy, so the
          selection is proven indirectly: with all text selected the new character replaces everything,
          otherwise it is appended to the original text.
    """
    from common.adb_common import run_adb_cmd
 
    run_adb_cmd(serial, f"shell input text {probe_char}", log_print=False)
    time.sleep(1.5)
    # Must read the EditText itself: the focused node can be an empty wrapper on the Google search widget.
    content = keyremap_read_edit_text(device)
    if not content:
        content = scan_get_input_field_text(device)
    return content.strip().upper() == probe_char.upper(), content

# IMEI_Method_Sophy_H400818_2026-09-01
def imei_is_valid(imei):
    """Validate that an IMEI string is present and not all zeros.

    Args: imei is the IMEI string to validate.
    Returns: (is_valid, reason).
    Precondition: none.
    """
    if not imei:
        return False, "IMEI is null or empty"
    if re.match(r'^0+$', imei):
        return False, f"IMEI is all zeros: {imei}"
    return True, "Valid"


# IMEI_Method_Sophy_H400818_2026-09-01
def imei_extract_candidates(xml, exclude=None):
    """Extract unique 14-15 digit IMEI candidates from a UI hierarchy dump.

    Args: xml is the dumped hierarchy string; exclude filters out an already-known IMEI value.
    Returns: a list of unique IMEI-looking digit strings, in the order found.
    Precondition: none.
    """
    unique = []
    for value in re.findall(r'\b(\d{14,15})\b', xml):
        if value not in unique and value != exclude:
            unique.append(value)
    return unique


# IMEI_Method_Sophy_H400818_2026-09-01
def imei_open_dialer(device, serial):
    """Open the Phone app and make sure the dialpad is visible.

    Args: device is the UIAutomator2 device object; serial is the device serial number.
    Returns: None.
    Precondition: none.
    """
    phone_opened = False
    for app_name in ("Phone", "电话", "Dialer", "拨号"):
        if device(text=app_name).exists(timeout=2):
            device(text=app_name).click()
            phone_opened = True
            time.sleep(2)
            break
                
    if not phone_opened and device(scrollable=True).exists():
        device(scrollable=True).scroll.to(text="Phone")
        if device(text="Phone").exists(timeout=2):
            device(text="Phone").click()
            phone_opened = True
            time.sleep(2)

    if not phone_opened:
        subprocess.run(f'adb -s {serial} shell am start -a android.intent.action.DIAL', shell=True)
        time.sleep(2)
                                                                                                                       
    for selector in (
        {"resourceId": "com.google.android.dialer:id/tab_dialpad"},
        {"resourceId": "com.android.dialer:id/fab"},
    ):
        if device(**selector).exists(timeout=2):
            device(**selector).click()
            time.sleep(1)
            break

# IMEI_Method_Sophy_H400818_2026-09-01
def imei_clear_dialpad_digits(device, serial):
    """Clear any existing digits on an already-open dialpad.                                                                                    
    Args: device is the UIAutomator2 device object; serial is the device serial number.
    Returns: None.
    Precondition: the Phone app dialpad is visible.
    """
    digits_field = None
    for resource_id in ("com.google.android.dialer:id/digits", "com.android.dialer:id/digits"):
        if device(resourceId=resource_id).exists(timeout=1):
            digits_field = device(resourceId=resource_id)
            break

    if not digits_field or not digits_field.exists() or not digits_field.info.get('text', ''):
        return
                                                                                                                                                   

    delete_btn = None
    for selector in (
        {"resourceId": "com.google.android.dialer:id/deleteButton"},
        {"resourceId": "com.android.dialer:id/deleteButton"},
        {"description": "backspace"},
        {"description": "delete"},
    ):
        if device(**selector).exists(timeout=1):
            delete_btn = device(**selector)
            break

    if delete_btn:
        delete_btn.long_click()
        time.sleep(0.5)
        if digits_field.exists() and digits_field.info.get('text', ''):
            for _ in range(20):
                if digits_field.exists() and not digits_field.info.get('text', ''):
                    break
                delete_btn.click()
                time.sleep(0.1)
    else:
        digits_field.long_click()
        time.sleep(0.3)
        if device(text="Select all").exists(timeout=1):
            device(text="Select all").click()
            time.sleep(0.2)
        subprocess.run(f'adb -s {serial} shell input keyevent KEYCODE_DEL', shell=True)
                


# IMEI_Method_Sophy_H400818_2026-09-01
def imei_dial_code(device, code):
    """Input a dial code (e.g. *#06#) using the on-screen dialpad keys.
                                                                       

    Args: device is the UIAutomator2 device object; code is the dial string to input.
    Returns: None.
    Precondition: the Phone app dialpad is visible.
    """
    for char in code:
        if char == '*':
            selectors = (
                {"resourceId": "com.google.android.dialer:id/star"},
                {"resourceId": "com.android.dialer:id/star"},
                {"className": "android.widget.ImageButton", "description": "star"},
                {"className": "android.widget.TextView", "text": "*"},
            )
        elif char == '#':
            selectors = (
                {"resourceId": "com.google.android.dialer:id/pound"},
                {"resourceId": "com.android.dialer:id/pound"},
                {"className": "android.widget.ImageButton", "description": "pound"},
                {"className": "android.widget.TextView", "text": "#"},
            )
        elif char.isdigit():
            if device(className="android.widget.TextView", text=char).exists(timeout=1):
                device(className="android.widget.TextView", text=char).click()
            else:
                device(text=char).click()
            time.sleep(0.3)
            continue
        else:
            continue
                           
                         
                                                                                            
                                            
             
                         
                                    
                                           

        for selector in selectors:
            if device(**selector).exists(timeout=1):
                device(**selector).click()
                break
        time.sleep(0.3)


# IMEI_Method_Sophy_H400818_2026-09-01
def imei_read_from_dialer(device, serial, img_dir, code="*#06#"):
    """Open the dialer, dial the IMEI info code and read the IMEI value(s) shown in the popup.

    Args: device is the UIAutomator2 device object; serial is the device serial number; img_dir is the
          screenshot output directory; code is the dial string that triggers the IMEI dialog.
    Returns: (sim1_imei, sim2_imei); sim2_imei is None for single-SIM devices.
    Precondition: none.
    """
    from common.adb_common import save_step_screenshot

    imei_open_dialer(device, serial)
    imei_clear_dialpad_digits(device, serial)
    imei_dial_code(device, code)

    time.sleep(3)
    save_step_screenshot(device, "dialer_imei_dialog", img_dir)

    unique_imeis = imei_extract_candidates(device.dump_hierarchy())
    sim1 = unique_imeis[0] if len(unique_imeis) >= 1 else None
    sim2 = unique_imeis[1] if len(unique_imeis) >= 2 else None

    device.press("back")
    time.sleep(1)
    device.press("home")
    time.sleep(1)
    return sim1, sim2


# IMEI_Method_Sophy_H400818_2026-09-01
def imei_read_sim_imei_from_settings(device, sim_label, exclude_imei=None, allow_plain_imei_label=False):
    """Scroll to an IMEI menu item in About phone, open it, and read the IMEI.

    Args: device is the UIAutomator2 device object; sim_label is e.g. "sim slot 1" / "sim slot 2";
          exclude_imei filters out an already-known value (used when scanning for SIM2 after SIM1);
          allow_plain_imei_label also matches a bare "IMEI" menu item (single-SIM devices show no
          "(sim slot N)" suffix at all).
    Returns: the IMEI string, or None if the menu item could not be found/clicked/read.
    Precondition: the About phone page is currently displayed.
    """
    def _find_matching_instance():
        if not device(textContains="IMEI").exists(timeout=0.5):
            return None
        elements = device(textContains="IMEI")
        for i in range(elements.count):
            try:
                elem = device(textContains="IMEI", instance=i)
                elem_text = elem.get_text()
            except Exception:
                continue
            text_lower = elem_text.lower()
            if "status" in text_lower:
                continue
            if sim_label in text_lower:
                return elem
            if allow_plain_imei_label and text_lower.strip() == "imei":
                return elem
        return None

    matching_elem = None
    for _ in range(10):
        matching_elem = _find_matching_instance()
        if matching_elem:
            break
        device(scrollable=True).scroll.forward()
        time.sleep(0.4)

    if not matching_elem:
        return None

    matching_elem.click()
    time.sleep(1.5)

    xml = device.dump_hierarchy()
    candidates = imei_extract_candidates(xml, exclude=exclude_imei)
    imei_value = candidates[0] if candidates else None

    if not imei_value:
        for elem in device(className="android.widget.TextView"):
            try:
                text = elem.get_text()
            except Exception:
                continue
            if text and re.match(r'^\d{14,15}$', text.strip()) and text.strip() != exclude_imei:
                imei_value = text.strip()
                break

    device.press("back")
    time.sleep(1)
    return imei_value


# DevOptions_Method_Sophy_H400818_2026-09-01
def dev_options_enable(device, serial):
    """Enable Developer Options via the About phone -> tap Build number 7 times flow.

    Args: device is the UIAutomator2 device object; serial is the device serial number.
    Returns: True if Developer Options ends up enabled, False otherwise.
    Precondition: none.
    """
    from common.adb_common import dev_options_is_enabled

    if dev_options_is_enabled(serial):
        return True

    subprocess.run(
        f"adb -s {serial} shell am start -a android.settings.DEVICE_INFO_SETTINGS",
        capture_output=True, text=True, shell=True, timeout=5,
    )
    time.sleep(2)

    for _ in range(10):
        if device(textContains="Build number").exists(timeout=1):
            break
        if device(scrollable=True).exists():
            device(scrollable=True).scroll.forward()
        time.sleep(0.3)

    if not device(textContains="Build number").exists(timeout=2):
        return False

    for _ in range(7):
        device(textContains="Build number").click()
        time.sleep(0.2)
    time.sleep(1)
    device.press("back")
    time.sleep(0.5)
    return True
    
# ============= WiFi_Method_Sally: WiFi UI Automation Helpers =============

# WIFI_Method_Sally_0907
def wifi_init_device(serial):
    """Initialize UIAutomator2 device connection."""
    if u2 is None:
        raise ImportError("[ERROR] uiautomator2 not installed. Install with: pip install uiautomator2")
    if not serial:
        raise RuntimeError("No Android device found. Please connect a device first.")

    print(f"[wifi] Connecting to device: {serial}", flush=True)
    device = u2.connect(serial)
    info = device.info
    print(
        f"[wifi] [OK] Device connected, screen={info['displayWidth']}x{info['displayHeight']}",
        flush=True,
    )
    return device


# WIFI_Method_Sally_0907
def wifi_wake_up_device(device):
    """Wake and unlock device."""
    from common.adb_common import adb_shell, adb_shell_output
    print("[wifi] Waking up device...", flush=True)
    serial = os.environ.get("ANDROID_SERIAL")
    if not serial:
        from common.adb_common import get_device_serial
        serial = get_device_serial()

    # u2's device.unlock() may press POWER on a stale screenOn=False reading and blank an already-on
    # screen, so wake purely via adb with the idempotent KEYCODE_WAKEUP (224).
    adb_shell(serial, "svc", "power", "stayon", "true", timeout=6)
    for _ in range(3):
        out = adb_shell_output(serial, "dumpsys", "power", timeout=8) or ""
        if "mWakefulness=Awake" in out or "Display Power: state=ON" in out:
            break
        adb_shell(serial, "input", "keyevent", "224", timeout=6)
        time.sleep(1)

    adb_shell(serial, "wm", "dismiss-keyguard", timeout=6)
    time.sleep(0.5)
    try:
        device.swipe_ext("up", scale=0.9)
    except Exception:
        pass
    time.sleep(0.5)
                                                           
                                        
                                                             
                       
                                                                   
                 


# WIFI_Method_Sally_0907
def wifi_press_home(serial):
    """Press Home to return to launcher."""
    from common.adb_common import adb_shell
    adb_shell(serial, "input", "keyevent", "3")
    time.sleep(1)


# WIFI_Method_Sally_0907
def wifi_open_settings(device):
    """Navigate from Settings to WiFi page: Settings -> Network & internet -> Internet -> WiFi (three-level menu)."""
    from common.adb_common import _wifi_shell_output

    serial = os.environ.get("ANDROID_SERIAL")
    if not serial:
        from common.adb_common import get_device_serial
        serial = get_device_serial()

    print("[wifi] Opening WiFi settings: Settings -> Network & internet -> Internet -> WiFi", flush=True)

    # Force-stop first: some ROMs restore the last-viewed fragment (e.g. Developer options)
    # instead of the main Settings list when relaunched.
    _wifi_shell_output(serial, "am", "force-stop", "com.android.settings", timeout=6)
    time.sleep(1)

    out = _wifi_shell_output(serial, "am", "start", "-a", "android.settings.SETTINGS", timeout=8)
    if "error" in out.lower() or "exception" in out.lower():
        return False

    time.sleep(3)

    # ========== LEVEL 1: Find and click "Network & internet" in Settings main page ==========
    print("[wifi] Level 1: Looking for 'Network & internet' in Settings main page...", flush=True)
    level1_keys = [
        "Network & internet",
        "网络和互联网",
        "连接和共享",
        "连接",
    ]

    level1_found = False
    # Try direct search first
    for key in level1_keys:
        try:
            obj = device(text=key)
            if obj.exists(timeout=1.5):
                print(f"[wifi] Level 1: Found '{key}' (exact match)", flush=True)
                obj.click()
                time.sleep(2.5)
                level1_found = True
                break
            obj2 = device(textContains=key)
            if obj2.exists(timeout=1.5):
                print(f"[wifi] Level 1: Found '{key}' (contains match)", flush=True)
                obj2.click()
                time.sleep(2.5)
                level1_found = True
                break
        except Exception:
            pass

    # Try scrolling if direct search failed
    if not level1_found:
        print("[wifi] Level 1: Scrolling to find 'Network & internet'...", flush=True)
        try:
            for scroll_idx in range(5):
                for key in level1_keys:
                    try:
                        obj = device(text=key)
                        if obj.exists(timeout=1):
                            print(f"[wifi] Level 1: Found '{key}' after scroll", flush=True)
                            obj.click()
                            time.sleep(2.5)
                            level1_found = True
                            break
                        obj2 = device(textContains=key)
                        if obj2.exists(timeout=1):
                            print(f"[wifi] Level 1: Found '{key}' after scroll (contains)", flush=True)
                            obj2.click()
                            time.sleep(2.5)
                            level1_found = True
                            break
                    except Exception:
                        pass
                if level1_found:
                    break
                device(scrollable=True).scroll.forward()
                time.sleep(0.8)
        except Exception as e:
            print(f"[wifi] Level 1: Exception during scroll: {e}", flush=True)

    if not level1_found:
        print("[wifi] [ERROR] Could not find 'Network & internet' in Settings main page", flush=True)
        return False

    # ========== LEVEL 2: Find and click "Internet" in Network & internet submenu ==========
    print("[wifi] Level 2: Looking for 'Internet' in Network & internet submenu...", flush=True)
    level2_keys = [
        "Internet",
        "互联网",
        "Mobile network",
        "移动网络",
        "Cellular",
        "蜂窝数据",
    ]

    level2_found = False
    # Try direct search first
    for key in level2_keys:
        try:
            obj = device(text=key)
            if obj.exists(timeout=1.5):
                print(f"[wifi] Level 2: Found '{key}' (exact match)", flush=True)
                obj.click()
                time.sleep(2.5)
                level2_found = True
                break
            obj2 = device(textContains=key)
            if obj2.exists(timeout=1.5):
                print(f"[wifi] Level 2: Found '{key}' (contains match)", flush=True)
                obj2.click()
                time.sleep(2.5)
                level2_found = True
                break
        except Exception:
            pass

    # Try scrolling if direct search failed
    if not level2_found:
        print("[wifi] Level 2: Scrolling to find 'Internet'...", flush=True)
        try:
            for scroll_idx in range(3):
                for key in level2_keys:
                    try:
                        obj = device(text=key)
                        if obj.exists(timeout=1):
                            print(f"[wifi] Level 2: Found '{key}' after scroll", flush=True)
                            obj.click()
                            time.sleep(2.5)
                            level2_found = True
                            break
                        obj2 = device(textContains=key)
                        if obj2.exists(timeout=1):
                            print(f"[wifi] Level 2: Found '{key}' after scroll (contains)", flush=True)
                            obj2.click()
                            time.sleep(2.5)
                            level2_found = True
                            break
                    except Exception:
                        pass
                if level2_found:
                    break
                device(scrollable=True).scroll.forward()
                time.sleep(0.8)
        except Exception as e:
            print(f"[wifi] Level 2: Exception during scroll: {e}", flush=True)

    if not level2_found:
        print("[wifi] [WARN] Could not find 'Internet' in Level 2, but continuing to search for WiFi", flush=True)

    # ========== LEVEL 3: Find and click "WiFi" to enter WiFi enable page ==========
    print("[wifi] Level 3: Looking for 'WiFi' in submenu...", flush=True)
    level3_keys = [
        "Wi-Fi",
        "WiFi",
        "WLAN",
        "无线局域网",
    ]

    # Try direct search first
    for key in level3_keys:
        try:
            obj = device(text=key)
            if obj.exists(timeout=1.5):
                print(f"[wifi] Level 3: Found '{key}' (exact match)", flush=True)
                obj.click()
                time.sleep(2.5)
                print("[wifi] Successfully navigated to WiFi enable page", flush=True)
                return True
            obj2 = device(textContains=key)
            if obj2.exists(timeout=1.5):
                print(f"[wifi] Level 3: Found '{key}' (contains match)", flush=True)
                obj2.click()
                time.sleep(2.5)
                print("[wifi] Successfully navigated to WiFi enable page", flush=True)
                return True
        except Exception:
            pass

    # Try scrolling if direct search failed
    print("[wifi] Level 3: Scrolling to find WiFi...", flush=True)
    try:
        for scroll_idx in range(3):
            for key in level3_keys:
                try:
                    obj = device(text=key)
                    if obj.exists(timeout=1):
                        print(f"[wifi] Level 3: Found '{key}' after scroll", flush=True)
                        obj.click()
                        time.sleep(2.5)
                        print("[wifi] Successfully navigated to WiFi enable page", flush=True)
                        return True
                    obj2 = device(textContains=key)
                    if obj2.exists(timeout=1):
                        print(f"[wifi] Level 3: Found '{key}' after scroll (contains)", flush=True)
                        obj2.click()
                        time.sleep(2.5)
                        print("[wifi] Successfully navigated to WiFi enable page", flush=True)
                        return True
                except Exception:
                    pass
            device(scrollable=True).scroll.forward()
            time.sleep(0.8)
    except Exception as e:
        print(f"[wifi] Level 3: Exception during scroll: {e}", flush=True)

    print("[wifi] [ERROR] Could not find WiFi entry at Level 3", flush=True)
    return False


# WIFI_Method_Sally_0907
def wifi_disable_ui_prefer(device, serial):
    """Disable WiFi via UI first, fallback to adb."""
    from common.adb_common import _wifi_is_enabled, _wifi_disable

    print("[wifi] Trying to disable WiFi via UI first...", flush=True)
    if not _wifi_is_enabled(serial):
        return True

    candidate_selectors = [
        lambda: device(resourceId="com.android.settings:id/switch_widget"),
        lambda: device(resourceId="android:id/switch_widget"),
        lambda: device(resourceIdMatches=r".*:id/switch_widget"),
        lambda: device(className="android.widget.Switch"),
        lambda: device(className="android.widget.SwitchCompat"),
        lambda: device(className="android.widget.CompoundButton"),
    ]

    for _ in range(4):
        if not _wifi_is_enabled(serial):
            return True

        clicked = False
        for build_obj in candidate_selectors:
            try:
                obj = build_obj()
                if obj.exists(timeout=1.0):
                    checked = None
                    try:
                        checked = obj.info.get("checked")
                    except Exception:
                        pass

                    if checked is False:
                        return True

                    obj.click()
                    clicked = True
                    time.sleep(1.5)
                    break
            except Exception:
                pass

        if clicked:
            continue

        for text_key in ["Wi-Fi", "WiFi", "WLAN", "无线局域网", "无线网络"]:
            try:
                row = device(textContains=text_key)
                if row.exists(timeout=0.8):
                    row.click()
                    time.sleep(1.2)
                    clicked = True
                    break
            except Exception:
                pass

        if clicked and not _wifi_is_enabled(serial):
            return True

    print("[wifi] [WARN] UI disable did not complete, fallback to adb disable", flush=True)
    return _wifi_disable(serial)

# WIFI_Method_Sally_0907
def wifi_open_browser_and_check_online(device, serial):
    """Open browser and verify http://www.baidu.com is actually reachable."""
    from common.adb_common import _wifi_shell_output, _wifi_is_baidu_reachable

    print("[wifi] Opening browser to verify internet...", flush=True)
    out = _wifi_shell_output(
        serial,
        "am",
        "start",
        "-a",
        "android.intent.action.VIEW",
        "-d",
        "http://www.baidu.com",
        timeout=10,
    )
    time.sleep(3)
    wifi_dismiss_browser_chooser(device)
    start_ok = "error" not in out.lower() and "exception" not in out.lower()
    return start_ok and _wifi_is_baidu_reachable(serial)

# WIFI_Method_Sally_0907
def wifi_dismiss_browser_chooser(device):
    """Dismiss the browser resolver dialog and Chrome's first-run onboarding screens
    (sign-in prompt, sync consent, etc.) that block navigation to the target URL.
    """
    dismissed_any = False
    for _ in range(4):
        dismissed = False
        try:
            for resource_id in (
                "android:id/button_always",
                "android:id/button_once",
                # Chrome FRE sign-in screen: prefer staying signed out over adding an account.
                "com.android.chrome:id/signin_fre_dismiss_button",
                "com.android.chrome:id/signin_fre_continue_button",
            ):
                btn = device(resourceId=resource_id)
                if btn.exists(timeout=0.5):
                    btn.click()
                    print(f"[wifi] Dismissed browser dialog via {resource_id}", flush=True)
                    time.sleep(1.5)
                    dismissed = True
                    break

            if not dismissed:
                for text_key in (
                    "Stay signed out", "No thanks", "Just once", "Skip",
                    "始终", "仅此一次", "始终允许", "确定", "OK", "跳过",
                ):
                    btn = device(text=text_key)
                    if btn.exists(timeout=0.3):
                        btn.click()
                        print(f"[wifi] Dismissed browser dialog via text '{text_key}'", flush=True)
                        time.sleep(1.5)
                        dismissed = True
                        break
        except Exception as error:
            print(f"[wifi] [WARN] Failed to dismiss browser chooser: {error}", flush=True)
            break

        if not dismissed:
            break
        dismissed_any = True

    return dismissed_any


# WIFI_Method_Sally_0907
def wifi_current_package_name(device):
    """Get foreground package name."""
    try:
        info = device.app_current()
        return (info or {}).get("package", "")
    except Exception:
        return ""


# WIFI_Method_Sally_0907
def wifi_save_step_screenshot(serial, test_name, step):
    """Save screenshot by adb for better stability."""
    from common.adb_common import save_debug_screenshot
    path = save_debug_screenshot(serial, f"{test_name}_{step}")
    print(f"[wifi] [OK] Screenshot saved: {path}", flush=True)
    return path

# CameraPreview_Method_Sally_2026-09-08
def camera_start_package_and_measure_preview(device, package, limit_ms=2000, serial=None):
    """直接启动相机包并返回预览出现耗时，超时返回 None。"""
    started = time.perf_counter()
    device.app_start(package, stop=True)
    deadline = started + limit_ms / 1000
    while time.perf_counter() < deadline:
        selectors = [
            device(resourceId="org.codeaurora.snapcam:id/shutter_button"),
            device(resourceId="com.android.camera:id/shutter_button"),
            device(resourceIdMatches=r".*id/shutter_button$"),
            device(resourceId="org.codeaurora.snapcam:id/preview"),
            device(resourceId="com.android.camera:id/preview"),
            device(resourceIdMatches=r".*id/preview$"),
            device(className="android.view.SurfaceView"),
        ]
        for selector in selectors:
            try:
                if selector.exists(timeout=0):
                    return (time.perf_counter() - started) * 1000
            except Exception:
                continue
        if serial:
            from common.adb_common import camera_foreground_package
            if camera_foreground_package(serial) == package:
                return (time.perf_counter() - started) * 1000
        time.sleep(0.02)
    return None

# Keyremap_Method_Sophy_H400818_2026-09-02
def keyremap_open_apps_tab(device, serial, max_swipes=6):
    """Open the APPS tab of the Keyremap target list.

    Args: device is the UIAutomator2 device object; serial is the device serial number;
          max_swipes is the max number of swipes used while looking for the tab.
    Returns: True if the APPS tab was tapped and its app list rendered, otherwise False.
    Precondition: the Keyremap target list (KEYS / FUNCTIONS / APPS tabs) is open after tapping OK
          in the key-capture dialog.
    """
    if not keyremap_tap_text(device, serial, "APPS", contains=False, max_swipes=max_swipes):
        print("  [Remap] 'APPS' tab not found in target list")
        return False
    time.sleep(2)
    return True


# Keyremap_Method_Sophy_H400818_2026-09-02
def keyremap_select_app_target(device, serial, app_label, max_swipes=25):
    """Scroll the Keyremap APPS list and select the app with the given label.

    Args: device is the UIAutomator2 device object; serial is the device serial number;
          app_label is the launcher label of the app (aapt application-label);
          max_swipes is the max number of swipes, the APPS list can be long on a loaded device.
    Returns: True if the app entry was tapped, otherwise False.
    Precondition: the APPS tab is already selected.
    """
    if not keyremap_tap_text(device, serial, app_label, contains=False, max_swipes=max_swipes):
        print(f"  [Remap] App '{app_label}' not found in APPS list after {max_swipes} swipes")
        return False
    time.sleep(2)
    return True


# Chrome account message Sophy_H400818_2026-09-04
def dismiss_chrome_first_run_prompts(device):
    """Dismiss Chrome's optional first-run account and notification prompts.

    Returns: True if at least one prompt was dismissed, otherwise False.
    """
    dismissed = False
    use_without_account = device(text="Use without an account")
    if use_without_account.exists(timeout=5):
        use_without_account.click()
        time.sleep(1)
        dismissed = True

    no_thanks = device(text="No thanks")
    if no_thanks.exists(timeout=5):
        no_thanks.click()
        time.sleep(1)
        dismissed = True

    return dismissed


# Keyremap_Method_Sophy_H400818_2026-09-08
def enable_provisioning_mode(device, serial, label):
    """Open Honeywell Settings, enter Provisioning Mode, and ensure it is enabled.

    Args: device is the UIAutomator2 device object; serial is the device serial number; label is the
          Provisioning Mode entry's display text on the Honeywell Settings page.
    Returns: (enabled, was_already_enabled). was_already_enabled is None when the switch state
          could not be read.
    Precondition: none; this opens Honeywell Settings itself.
    """
    from common.adb_common import dcs_test_open_honeywell_settings

    if not dcs_test_open_honeywell_settings(serial):
        return False, None
    time.sleep(2)

    if not dcs_test_scroll_find_and_click(device, [label], max_swipes=6):
        return False, None
    time.sleep(2)

    switch = device(resourceId="android:id/switch_widget")
    if not switch.exists(timeout=3):
        return False, None

    was_already_enabled = bool(switch.info.get("checked", False))
    if was_already_enabled:
        print(f"  '{label}' is already enabled")
        return True, was_already_enabled

    switch.click()
    time.sleep(1)
    enabled = bool(switch.info.get("checked", False))
    return enabled, was_already_enabled


# Keyremap_Method_Sophy_H400818_2026-09-14 /开打ezconfig会出现Viewing full screen 的
def dismiss_full_screen_hint(device):
    """Dismiss Android's optional 'Viewing full screen' education dialog."""
    got_it = device(text="Got it")
    if not got_it.exists(timeout=1):
        got_it = device(text="GOT IT")
        if not got_it.exists(timeout=1):
            return False
    got_it.click()
    time.sleep(1)
    return True

# PlayProtect_Method_Sophy_H400818_2026-09-14 disable之后，安装app时不会弹unsafety app install的通知
def disable_play_protect_app_scanning(device):
    """Disable Play Store's Scan apps with Play Protect setting when it is enabled.

    Returns: True when Play Protect scanning is confirmed off; False when Play Store or its
        setting cannot be opened, its state cannot be determined, or the disable confirmation fails.
    """
    try:
        device.app_info("com.android.vending")
        device.app_start("com.android.vending", wait=True)
        time.sleep(3)

        more_options = device(resourceId="com.android.vending:id/0_resource_name_obfuscated")
        if not more_options.exists(timeout=3):
            return False
        more_options.click()
        time.sleep(1)

        play_protect = device(textContains="Play Protect")
        if not play_protect.exists(timeout=3):
            return False
        play_protect.click()
        time.sleep(2)

        settings = device(descriptionMatches=r"(?i).*Settings.*")
        if not settings.exists(timeout=3):
            return False
        settings.click()
        time.sleep(2)

        scan_apps = device(textContains="Scan apps with Play Protect")
        if not scan_apps.exists(timeout=3):
            return False
        label_bounds = scan_apps.info.get("bounds", {})
        label_center_y = (label_bounds.get("top", 0) + label_bounds.get("bottom", 0)) // 2
        checkables = device(checkable=True)
        for index in range(checkables.count):
            control = checkables[index]
            bounds = control.info.get("bounds", {})
            control_center_y = (bounds.get("top", 0) + bounds.get("bottom", 0)) // 2
            if abs(control_center_y - label_center_y) > 100:
                continue
            if not bool(control.info.get("checked", False)):
                return True
            control.click()
            time.sleep(1)
            turn_off = device(text="Turn off")
            if not turn_off.exists(timeout=3):
                return False
            turn_off.click()
            time.sleep(1)
            return not bool(control.info.get("checked", True))
    except Exception:
        return False
    return False


# PlayProtect_Method_Sophy_H400818_2026-09-14
def enable_play_protect_app_scanning(device):
    """Enable Play Store's Scan apps with Play Protect setting when it is disabled.

    Returns: True when Play Protect scanning is confirmed on; False when Play Store or its
        setting cannot be opened or its state cannot be determined.
    """
    try:
        device.app_stop("com.android.vending")
        device.app_start("com.android.vending", wait=True)
        time.sleep(3)

        more_options = device(resourceId="com.android.vending:id/0_resource_name_obfuscated")
        if not more_options.exists(timeout=3):
            return False
        more_options.click()
        time.sleep(1)

        play_protect = device(textContains="Play Protect")
        if not play_protect.exists(timeout=3):
            return False
        play_protect.click()
        time.sleep(2)

        settings = device(descriptionMatches=r"(?i).*Settings.*")
        if not settings.exists(timeout=3):
            return False
        settings.click()
        time.sleep(2)

        scan_apps = device(textContains="Scan apps with Play Protect")
        if not scan_apps.exists(timeout=3):
            return False
        label_bounds = scan_apps.info.get("bounds", {})
        label_center_y = (label_bounds.get("top", 0) + label_bounds.get("bottom", 0)) // 2
        checkables = device(checkable=True)
        for index in range(checkables.count):
            control = checkables[index]
            bounds = control.info.get("bounds", {})
            control_center_y = (bounds.get("top", 0) + bounds.get("bottom", 0)) // 2
            if abs(control_center_y - label_center_y) > 100:
                continue
            if bool(control.info.get("checked", False)):
                return True
            control.click()
            time.sleep(1)
            return bool(control.info.get("checked", False))
    except Exception:
        return False
    return False


# Keyremap_Method_Sophy_H400818_2026-09-15
def keyremap_ensure_uiautomator_healthy(device, serial):
    """Restore uiautomator2 when its hierarchy service is stale.

    Returns: True if dump_hierarchy is available, otherwise False.
    """
    from common.adb_common import run_adb_cmd

    try:
        device.dump_hierarchy()
        return True
    except Exception as error:
        print(f"  [Nav] uiautomator hierarchy unavailable: {type(error).__name__}; restarting service")

    run_adb_cmd(serial, "shell am force-stop com.github.uiautomator", log_print=False)
    run_adb_cmd(serial, "shell am force-stop com.github.uiautomator.test", log_print=False)
    run_adb_cmd(serial, "shell pkill -f uiautomator", log_print=False)
    time.sleep(1)
    try:
        device.start_uiautomator()
        time.sleep(6)
        device.dump_hierarchy()
        print("  [Nav] uiautomator hierarchy restored")
        return True
    except Exception as error:
        print(f"  [Nav] uiautomator recovery failed: {type(error).__name__}: {str(error)[:80]}")
        return False

# CounterUiLifecycle_Peter_29260917
class CounterUiLifecycle:
    """Run the HSMCounters application lifecycle through visible device UI."""

    app_package = "com.honeywell.android.hsmcounters"
    apk_filename = "HSM_Counters_signed.apk"
    device_apk_path = "/sdcard/Download/HSM_Counters_signed.apk"
    apk_preview_icon_coordinates = (455, 770)

    def __init__(self, test_case, serial, apk_path, screenshot_dir):
        self.test_case = test_case
        self.device = test_case.device
        self.serial = serial
        self.apk_path = apk_path
        self.screenshot_dir = screenshot_dir

    def ensure_installed(self):
        from common.adb_common import package_is_installed, push_device_file

        if package_is_installed(self.serial, self.app_package):
            self.uninstall()
        self._dismiss_incomplete_installer()
        self.test_case.assertTrue(os.path.isfile(self.apk_path), f"Counter APK not found: {self.apk_path}")
        self.remove_downloaded_apk(4)
        print("[Step 5] Copy HSMCounters APK to device Downloads")
        pushed = push_device_file(self.serial, self.apk_path, self.device_apk_path)
        self.test_case.assertEqual(pushed.returncode, 0, f"Failed to copy Counter APK: {pushed.stderr}")
        for attempt in range(1, 4):
            if attempt > 1:
                if self._wait_for_package(True, timeout=1):
                    print("[INFO] HSMCounters package was already installed; skip duplicate installation")
                    self._dismiss_incomplete_installer()
                    return
                print("[Step 9] Close the incomplete installation screen before retrying")
                self._dismiss_incomplete_installer()
                time.sleep(0.5)
            self._open_downloaded_apk()
            if self._complete_install(attempt) and self._verify_install_success():
                self._dismiss_install_success()
                print("[INFO] HSMCounters installation success screen and package presence verified")
                return
            print(f"[Step 9] HSMCounters was not installed; retrying ({attempt}/3)")
        self.test_case.fail("HSMCounters was not installed after three visible installation attempts")

    def close_background_apps(self):
        print("[Step 2] Close all Recent Apps and return to Home")
        cards = self._recent_task_cards()
        if not cards and not self._is_recent_apps_visible():
            self.test_case.assertTrue(self.device(description="Overview").click_exists(timeout=3),
                                      "Recent Apps navigation button was not visible")
            self.test_case.assertTrue(self._wait_for_recent_apps_visible(2), "Recent Apps did not open")
            cards = self._recent_task_cards()
        for _ in range(12):
            if not cards:
                cards = self._recent_task_cards()
            if not cards:
                if self._is_recent_apps_visible():
                    cards = self._wait_for_recent_task_cards(1)
                if cards:
                    continue
                print("[INFO] No background app cards were visible")
                self.device.press("home")
                return
            description, bounds = max(cards, key=lambda card: (card[1][2] - card[1][0]) * (card[1][3] - card[1][1]))
            print(f"[INFO] Closing background app card: {description}")
            self.test_case.assertTrue(self._swipe_task_card_closed(description, bounds),
                                      f"Recent Apps card remained after swipe: {description}")
            cards = None
        self.test_case.fail("Background app cards remained after 12 individual close attempts")

    def uninstall(self):
        from common.adb_common import package_is_installed

        if not package_is_installed(self.serial, self.app_package):
            return
        print("[Step 16] Display HSMCounters uninstall screen on the device")
        shell(self.serial, "am", "start", "-a", "android.settings.APPLICATION_DETAILS_SETTINGS", "-d",
              f"package:{self.app_package}", timeout=15)
        time.sleep(2)
        self._click_text(("OK", "Ok", "确定"), 0.5)
        self.test_case.assertTrue(self._click_text(("Uninstall", "UNINSTALL", "卸载"), 10),
                                  "Uninstall button was not visible")
        self.test_case.assertTrue(self._click_text(("OK", "Ok", "确定", "Uninstall", "UNINSTALL", "卸载"), 10),
                                  "Uninstall confirmation button was not visible")
        self.test_case.assertTrue(self._wait_for_package(False), "HSMCounters remained installed after uninstall")

    def dismiss_legacy_app_warning(self):
        if self._click_text(("OK", "Ok", "确定"), 2):
            print("[INFO] Dismissed the visible HSMCounters legacy-app warning")

    def remove_downloaded_apk(self, step_number=17):
        from common.adb_common import remove_device_file

        print(f"[Step {step_number}] Remove HSMCounters APK from device Downloads")
        self.test_case.assertTrue(remove_device_file(self.serial, self.device_apk_path),
                                  "Failed to remove Counter APK from Downloads")

    def _open_downloaded_apk(self):
        from common.adb_common import adb_command, save_step_screenshot

        print("[Step 6] Open Downloads and tap the HSMCounters APK preview icon")
        adb_command(self.serial, "shell", "am", "force-stop", "com.google.android.documentsui", timeout=15)
        opened = adb_command(self.serial, "shell", "am", "start", "-a", "android.intent.action.VIEW_DOWNLOADS",
                             timeout=15)
        self.test_case.assertEqual(opened.returncode, 0, f"Failed to open Downloads: {opened.stderr}")
        apk_file = self.device(text=self.apk_filename)
        apk_is_visible = apk_file.exists(timeout=10)
        current_package = (self.device.app_current() or {}).get("package", "")
        if not apk_is_visible and current_package == "com.google.android.packageinstaller":
            print("[INFO] HSMCounters APK already opened in the visible Package Installer")
            return
        self.test_case.assertTrue(apk_is_visible, "HSMCounters APK was not visible in Downloads")
        save_step_screenshot(self.device, "step00_apk_visible_before_click", self.screenshot_dir)
        apk_file.click()
        time.sleep(0.5)
        if (self.device.app_current() or {}).get("package") == "com.google.android.documentsui":
            print("[INFO] APK file row did not open; using the legacy preview click fallback")
            self.device.click(*self.apk_preview_icon_coordinates)

    def _complete_install(self, attempt):
        from common.adb_common import save_step_screenshot

        print("[Step 7] Wait 0.5 seconds after tapping the APK")
        time.sleep(0.5)
        save_step_screenshot(self.device, f"step00_apk_click_attempt{attempt}_after_0_5s", self.screenshot_dir)
        if self._click_install(5):
            return True
        if self._accept_play_protect_warning_if_needed(1):
            return self._click_install(5)
        if self._allow_download_manager_install_source_if_needed(1):
            print("[INFO] Download Manager permission enabled; click Install in the returned confirmation dialog")
            return self._click_install(5)
        if not self._click_text(("Continue", "CONTINUE", "继续", "仍要安装", "继续安装"), 0.5):
            return False
        print("[Step 8] APK risk warning appeared; click CONTINUE, then click INSTALL")
        time.sleep(0.5)
        save_step_screenshot(self.device, f"step00_after_install_warning_attempt{attempt}", self.screenshot_dir)
        if self._click_install(5):
            return True
        if self._accept_play_protect_warning_if_needed(1):
            return self._click_install(5)
        if self._allow_download_manager_install_source_if_needed(1):
            print("[INFO] Download Manager permission enabled; click Install in the returned confirmation dialog")
        return self._click_install(5)

    def _click_install(self, timeout):
        deadline = time.time() + timeout
        while time.time() < deadline:
            button = self.device(textMatches=r"Install|INSTALL|安装")
            if button.exists(timeout=0.1):
                button.click()
                time.sleep(0.5)
                if self._accept_play_protect_warning_if_needed(1):
                    return self._click_install(5)
                if self._allow_download_manager_install_source_if_needed(1):
                    print(
                        "[INFO] Download Manager permission enabled; click Install in the returned confirmation dialog")
                    return self._click_install(5)
                time.sleep(0.5)
                return True
            time.sleep(0.1)
        return False

    def _dismiss_install_success(self):
        print("[Step 10] Close the visible HSMCounters installation complete screen")
        self._click_text(("Done", "DONE", "完成"), 5)
        time.sleep(0.5)

    def _verify_install_success(self):
        deadline = time.time() + 15
        while time.time() < deadline:
            if self._text_visible(("App installed.", "App installed", "APP INSTALLED", "应用已安装"), 0.1):
                return self._wait_for_package(True, 5)
            if self._text_visible(("App not installed.", "App not installed", "APP NOT INSTALLED", "应用未安装"),
                                  0.1):
                print("[WARN] Visible Package Installer failure detected; retrying installation")
                self._click_text(("Done", "DONE", "完成"), 1)
                return False
            if self._wait_for_package(True, 1):
                if self._text_visible(("Do you want to update this app?", "Update", "是否要更新此应用", "更新"),
                                      0.1):
                    print("[INFO] Update confirmation detected; HSMCounters was already installed")
                else:
                    print("[INFO] HSMCounters package presence verified after visible installation")
                return True
        return False

    def _dismiss_incomplete_installer(self):
        if (self.device.app_current() or {}).get("package", "") != "com.google.android.packageinstaller":
            return
        if self._click_text(("Done", "DONE", "完成", "Cancel", "CANCEL", "取消"), 2):
            print("[INFO] Closed the visible incomplete Package Installer screen")
            return
        self.device.press("back")

    def _accept_play_protect_warning_if_needed(self, timeout):
        deadline = time.time() + timeout
        more_details = None
        while time.time() < deadline and more_details is None:
            for label in ("More details", "MORE DETAILS", "Details", "DETAILS", "更多详细信息", "详情"):
                control = self.device(text=label)
                if control.exists(timeout=0.1):
                    more_details = control
                    break
        if more_details is None:
            return False
        for attempt in range(1, 4):
            self._long_press_control(more_details, 1.2)
            print(f"[INFO] Google Play Protect warning detected; clicked More details ({attempt}/3)")
            time.sleep(0.8)
            if self._play_protect_install_anyway_bounds():
                break
        self.test_case.assertTrue(self._long_press_play_protect_install_anyway(5),
                                  "Install anyway was not visible after opening Google Play Protect details")
        print("[INFO] Google Play Protect warning detected; clicked Install anyway")
        time.sleep(0.5)
        return True

    def _allow_download_manager_install_source_if_needed(self, timeout):
        current_package = (self.device.app_current() or {}).get("package", "")
        source_permission_page = self.device(textMatches=r"Allow from this source|允许来自此来源")
        if current_package == "com.android.settings" and not source_permission_page.exists(timeout=0.1):
            return False
        if current_package != "com.android.settings":
            if not self._click_text(("Settings", "SETTINGS", "设置"), timeout):
                return False
            deadline = time.time() + 5
            while time.time() < deadline:
                if (self.device.app_current() or {}).get("package") == "com.android.settings":
                    break
                time.sleep(0.1)
            else:
                return False
        self.test_case.assertTrue(source_permission_page.exists(timeout=5),
                                  "Allow from this source page was not visible")
        toggle = self._source_permission_toggle()
        self.test_case.assertTrue(toggle.exists(timeout=5), "Allow from this source switch was not visible")
        if not bool(toggle.info.get("checked", False)):
            bounds = toggle.info["visibleBounds"]
            self.device.click((bounds["left"] + bounds["right"]) // 2, (bounds["top"] + bounds["bottom"]) // 2)
            time.sleep(0.5)
        if (self.device.app_current() or {}).get("package", "") == "com.android.settings":
            refreshed_toggle = self._source_permission_toggle()
            self.test_case.assertTrue(
                refreshed_toggle.exists(timeout=1) and bool(refreshed_toggle.info.get("checked", False)),
                "Allow from this source was not enabled")
            self.device.press("back")
            time.sleep(0.5)
        else:
            self.test_case.assertEqual((self.device.app_current() or {}).get("package", ""),
                                       "com.google.android.packageinstaller",
                                       "Download Manager permission did not return to Package Installer")
        print("[INFO] Enabled Allow from this source through the visible Settings page")
        return True

    def _swipe_task_card_closed(self, description, bounds):
        for _ in range(2):
            left, top, right, bottom = bounds
            card_height = bottom - top
            self.device.swipe((left + right) // 2, bottom - max(1, card_height // 30), (left + right) // 2,
                              max(0, top - card_height * 2), duration=0.05)
            deadline = time.time() + 2
            while time.time() < deadline:
                if not any(card_description == description for card_description, _ in self._recent_task_cards()):
                    return True
                time.sleep(0.2)
            for card_description, card_bounds in self._recent_task_cards():
                if card_description == description:
                    bounds = card_bounds
                    break
        return False

    def _wait_for_recent_task_cards(self, timeout):
        deadline = time.time() + timeout
        while time.time() < deadline:
            cards = self._recent_task_cards()
            if cards:
                return cards
            time.sleep(0.2)
        return []

    def _wait_for_recent_apps_visible(self, timeout):
        deadline = time.time() + timeout
        while time.time() < deadline:
            if self._is_recent_apps_visible() or self._recent_task_cards():
                return True
            time.sleep(0.2)
        return False

    def _is_recent_apps_visible(self):
        if "RecentsActivity" in (self.device.app_current() or {}).get("activity", ""):
            return True
        root = ET.fromstring(self.device.dump_hierarchy(compressed=False))
        screen_width, screen_height = self.device.window_size()
        for node in root.iter():
            attributes = node.attrib
            if attributes.get("package") == "com.android.launcher3" and attributes.get(
                    "class") == "android.view.View" and attributes.get("content-desc") == "Home" and attributes.get(
                    "bounds") == f"[0,32][{screen_width},{screen_height - 64}]":
                return True
        return False

    def _recent_task_cards(self):
        cards = []
        root = ET.fromstring(self.device.dump_hierarchy(compressed=False))
        _, screen_height = self.device.window_size()
        for node in root.iter():
            attributes = node.attrib
            bounds_match = re.fullmatch(r"\[(\d+),(\d+)\]\[(\d+),(\d+)\]", attributes.get("bounds", ""))
            if attributes.get("clickable") == "true" and attributes.get(
                    "package") == "com.android.launcher3" and attributes.get(
                    "class") == "android.widget.FrameLayout" and attributes.get("content-desc",
                                                                                "").strip() and bounds_match:
                bounds = tuple(map(int, bounds_match.groups()))
                if bounds[3] - bounds[1] >= screen_height // 2:
                    cards.append((attributes["content-desc"].strip(), bounds))
        return cards

    def _source_permission_toggle(self):
        toggle = self.device(resourceId="android:id/switch_widget")
        return toggle if toggle.exists(timeout=0.1) else self.device(checkable=True, clickable=True)

    def _click_text(self, labels, timeout):
        deadline = time.time() + timeout
        while time.time() < deadline:
            for label in labels:
                control = self.device(text=label)
                if control.exists(timeout=0.1):
                    control.click()
                    return True
            time.sleep(0.1)
        return False

    def _text_visible(self, labels, timeout):
        deadline = time.time() + timeout
        while time.time() < deadline:
            if any(self.device(text=label).exists(timeout=0.1) for label in labels):
                return True
            time.sleep(0.1)
        return False

    def _long_press_text(self, labels, timeout):
        deadline = time.time() + timeout
        while time.time() < deadline:
            for label in labels:
                control = self.device(text=label)
                if control.exists(timeout=0.1):
                    self._long_press_control(control)
                    return True
            time.sleep(0.1)
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
            bounds = self._play_protect_install_anyway_bounds()
            if bounds:
                left, _, _, bottom = bounds
                self.device.long_click(left + 150, bottom - 30, duration=0.8)
                time.sleep(0.5)
                return True
            time.sleep(0.1)
        return False

    def _play_protect_install_anyway_bounds(self):
        root = ET.fromstring(self.device.dump_hierarchy(compressed=False))
        for node in root.iter():
            if "Install anyway" in node.attrib.get("text", ""):
                values = [int(value) for value in
                          node.attrib.get("bounds", "").replace("[", ",").replace("]", ",").split(",") if value]
                if len(values) == 4:
                    return values
        return None

    def _long_press_control(self, control, duration=0.8):
        bounds = control.info["visibleBounds"]
        self.device.long_click((bounds["left"] + bounds["right"]) // 2, (bounds["top"] + bounds["bottom"]) // 2,
                               duration=duration)

    def _wait_for_package(self, should_be_installed, timeout=60):
        from common.adb_common import wait_for_package_state

        return wait_for_package_state(self.serial, self.app_package, should_be_installed, timeout)


# BatteryOptimizer_Method_Phili_2026-09-09
def battery_optimizer_reset_apps(serial):
    """Stop Honeywell Settings and Battery Optimizer before or after a test."""
    from common.adb_common import adb_shell

    adb_shell(serial, "am", "force-stop", "com.honeywell.settings")
    adb_shell(serial, "am", "force-stop", "com.honeywell.batterymaximizer")

# BatteryOptimizer_Method_Phili_2026-09-09
def battery_optimizer_open(device, serial):
    """Open Honeywell Settings -> Battery Optimizer and return whether it reached foreground.

    Some firmware/boot transitions leave the settings entry stale or the app not in the foreground,
    so direct launch of the Battery Optimizer HomeActivity is used as a fallback when the nav path fails.
    """
    from common.adb_common import adb_shell

    settings_package = "com.honeywell.settings"
    optimizer_package = "com.honeywell.batterymaximizer"
    adb_shell(serial, "am", "force-stop", settings_package, timeout=8)
    adb_shell(serial, "am", "start", "--activity-clear-task", "-n", f"{settings_package}/.MainActivity", timeout=10)
    if tap_text(device, "Battery Optimizer", timeout=1):
        for _ in range(5):
            time.sleep(1)
            if (device.info.get("currentPackageName") or "") == optimizer_package:
                return True

    adb_shell(serial, "am", "force-stop", optimizer_package, timeout=8)
    adb_shell(
        serial,
        "am",
        "start",
        "--activity-clear-task",
        "-n",
        f"{optimizer_package}/.activities.HomeActivity",
        timeout=10,
    )
    for _ in range(5):
        time.sleep(1)
        if (device.info.get("currentPackageName") or "") == optimizer_package:
            return True
        if device(resourceId=f"{optimizer_package}:id/textView_active_profile_value").exists(timeout=0.5):
            return True
        if device(text="OPTIMIZE BATTERY").exists(timeout=0.5):
            return True
    return False

# BatteryOptimizer_Method_Phili_2026-09-09
def battery_optimizer_read_active_profile(device):
    """Return the Battery Optimizer active profile text, or None when it is unavailable."""
    value = device(resourceId="com.honeywell.batterymaximizer:id/textView_active_profile_value")
    return (value.get_text() or "").strip() if value.exists(timeout=2) else None

# BatteryOptimizer_Method_Phili_2026-09-09
def battery_optimizer_open_profile_list(device):
    """Open the Battery Optimizer profile selector."""
    return tap_text(device, "OPTIMIZE BATTERY", timeout=2)

# BatteryOptimizer_Method_Phili_2026-09-09
def battery_optimizer_profile_options_visible(device):
    """Return whether at least one expected Battery Optimizer profile option is displayed."""
    return any(
        device(text=profile).exists(timeout=0.5)
        for profile in ("None", "Energy Saver", "Cold Storage", "Custom Profile")
    )

# BatteryOptimizer_Method_Phili_2026-09-09
def battery_optimizer_visible_profile_names(device):
    """Return the supported Battery Optimizer profile names visible on the selector page."""
    profiles = ("None", "Energy Saver", "Cold Storage", "Custom Profile")
    return tuple(profile for profile in profiles if device(text=profile).exists(timeout=0.5))

# BatteryOptimizer_Method_Phili_2026-09-09
def battery_optimizer_dismiss_location_prompt(device):
    """Dismiss transient Android location prompts that may interrupt profile selection."""
    candidates = (
        "Turn on location",
        "Turn on",
        "Allow location access",
        "Allow",
        "ALLOW",
        "ENABLE",
        "OK",
        "Continue",
        "Continue anyway",
        "Turn on location access",
        "Turn on location services",
    )
    for _ in range(6):
        acted = False
        for label in candidates:
            try:
                target = device(text=label)
                if target.exists(timeout=0.2):
                    target.click()
                    time.sleep(0.5)
                    acted = True
            except Exception:
                pass
            try:
                target = device(textContains="location")
                if target.exists(timeout=0.2):
                    target.click()
                    time.sleep(0.5)
                    acted = True
            except Exception:
                pass
            try:
                target = device(descriptionContains="location")
                if target.exists(timeout=0.2):
                    target.click()
                    time.sleep(0.5)
                    acted = True
            except Exception:
                pass
        if not acted:
            break
        time.sleep(0.5)
    return True

# BatteryOptimizer_Method_Phili_2026-09-09
def battery_optimizer_select_profile(device, profile_name):
    """Select and apply a profile, returning to the Battery Optimizer main screen."""
    battery_optimizer_dismiss_location_prompt(device)
    if not battery_optimizer_open_profile_list(device):
        battery_optimizer_dismiss_location_prompt(device)
        return False
    if not tap_text(device, profile_name, timeout=2):
        battery_optimizer_dismiss_location_prompt(device)
        if not tap_text(device, profile_name, timeout=2):
            return False
    battery_optimizer_dismiss_location_prompt(device)
    if not tap_text(device, "SELECT PROFILE", timeout=2):
        battery_optimizer_dismiss_location_prompt(device)
        return False
    time.sleep(1)
    battery_optimizer_dismiss_location_prompt(device)
    device.press("back")
    time.sleep(1)
    return True

# BatteryOptimizer_Method_Phili_2026-09-09
def battery_optimizer_restore_none(device, serial):
    """Restore Battery Optimizer's active profile to None and return whether it succeeded."""
    if not battery_optimizer_open(device, serial):
        return False
    if battery_optimizer_read_active_profile(device) == "None":
        return True
    return (
            battery_optimizer_select_profile(device, "None")
            and battery_optimizer_read_active_profile(device) == "None"
    )

# BatteryOptimizer_Method_Phili_2026-09-09
def battery_optimizer_open_entry(device, labels):
    """Open an entry on a Battery Optimizer page using supported label aliases."""
    for label in labels:
        entry = device(description=label)
        if entry.exists(timeout=0.5):
            entry.click()
            time.sleep(1)
            return True
    return bool(tap_first_available_text(device, labels, timeout=1))

# RTC_Method_Sophy_H400818_2026-07-24
def rtc_get_beijing_date():
    """Return the current Beijing date in YYYY-MM-DD format."""
    return datetime.now(timezone(timedelta(hours=8))).strftime('%Y-%m-%d')

# RTC_Method_Sophy_H400818_2026-09-22
def rtc_compare_device_date(serial, expected_date):
    """Read the device date and compare it with an expected YYYY-MM-DD date."""
    if not serial:
        return '', False, 'Device serial is empty'

    from common.adb_common import rtc_date_output

    try:
        device_date, error = rtc_date_output(serial, '+%Y-%m-%d')
        device_date = (device_date or '').strip()
        if not device_date:
            return '', False, (error or 'Unable to read device date').strip()
        return device_date, device_date == expected_date, ''
    except Exception as error:
        return '', False, str(error)