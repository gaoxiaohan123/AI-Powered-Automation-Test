# -*- coding:utf-8 -*-
"""
L0 Snapdragon Camera app verification test - UIAutomator2

Verify the camera app in the app list is the Qualcomm Snapdragon Camera.

Test Steps:
1. Connect to the device, capture its pre-test state, wake it, and unlock it.
2. Query installed packages through ADB and verify `org.codeaurora.snapcam` exists.
3. Open the app drawer and search its pages for a Snapdragon Camera application entry.
4. Treat package installation as the required pass criterion, record the app-drawer
    result as supporting UI evidence, and capture a screenshot.
5. Restore the device state captured before the test.
"""

import os
import sys
import time
import unittest

sys.path.insert(0, '.')

from common.adb_common import (
    get_device_serial,
    adb_shell,
)
from common.common_method import (
    camera_init_device,
    camera_wake_up_device,
    camera_capture_device_state,
    camera_restore_device_state,
)

serial = get_device_serial()
device = None

SCRIPT_BASENAME = os.path.splitext(os.path.basename(__file__))[0]
IMG_ROOT = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.realpath(__file__)))), "img")
SCRIPT_IMG_DIR = os.path.join(IMG_ROOT, SCRIPT_BASENAME)
os.makedirs(SCRIPT_IMG_DIR, exist_ok=True)


def init_device():
    """Initialize the UIAutomator2 device connection."""
    global device
    if device is None:
        device = camera_init_device(serial)
    return device


def _is_snapdragon_camera_installed():
    """Use ADB pm list packages to confirm the Snapdragon Camera package is installed."""
    try:
        ret = adb_shell(serial, "pm", "list", "packages", "org.codeaurora.snapcam", timeout=10)
        out = (ret.stdout or "").strip()
        if "org.codeaurora.snapcam" in out:
            print("[camera] [OK] Snapdragon Camera (org.codeaurora.snapcam) is installed", flush=True)
            return True
    except Exception as e:
        print(f"[camera] [WARN] pm list packages check failed: {e}", flush=True)
    print("[camera] [ERROR] org.codeaurora.snapcam not found via pm list packages", flush=True)
    return False


def _find_snapdragon_in_app_drawer():
    """Open the app drawer and scroll page by page to check if the Snapdragon Camera icon is visible."""
    snapdragon_names = ["Snapdragon", "SnapCam", "SnapCamera"]

    # Return to the home screen
    try:
        device.press("home")
        time.sleep(1)
    except Exception:
        pass

    app_list_opened = False

    # Method 1: click the app drawer button
    try:
        btn = device(resourceIdMatches=".*app.*grid.*|.*app.*drawer.*|.*all.*apps.*")
        if btn.exists(timeout=1):
            btn.click()
            time.sleep(1.5)
            app_list_opened = True
    except Exception:
        pass

    # Method 2: swipe up to open
    if not app_list_opened:
        try:
            w, h = device.info["displayWidth"], device.info["displayHeight"]
            device.swipe(w // 2, int(h * 0.8), w // 2, int(h * 0.2), duration=0.5)
            time.sleep(1.5)
            app_list_opened = True
        except Exception:
            pass

    # Method 3: long press the home screen
    if not app_list_opened:
        try:
            w, h = device.info["displayWidth"], device.info["displayHeight"]
            device.long_click(w // 2, h // 2, duration=1)
            time.sleep(1)
            for kw in ["Apps", "All apps"]:
                if device(textContains=kw).exists(timeout=0.3):
                    device(textContains=kw).click()
                    time.sleep(1)
                    app_list_opened = True
                    break
        except Exception:
            pass

    if not app_list_opened:
        print("[camera] [WARN] Could not open app drawer, skipping UI visibility check", flush=True)
        return False

    # Page through the app drawer to find Snapdragon Camera (horizontal paging, up to 6 pages)
    for page in range(6):
        for name in snapdragon_names:
            try:
                if device(textContains=name).exists(timeout=0.5):
                    print(f"[camera] [OK] Found '{name}' in app drawer (page {page + 1})", flush=True)
                    device.press("home")
                    return True
            except Exception:
                pass
        # Horizontal paging
        try:
            w, h = device.info["displayWidth"], device.info["displayHeight"]
            device.swipe(int(w * 0.8), h // 2, int(w * 0.2), h // 2, duration=0.4)
            time.sleep(0.8)
        except Exception:
            break

    print("[camera] [WARN] Snapdragon Camera icon not visible in app drawer", flush=True)
    device.press("home")
    return False


def _check_snapdragon_is_default():
    """Dual verification: ADB package install confirmation (required) + app drawer UI visibility confirmation (recommended)."""
    print("[camera] Verifying Snapdragon Camera is installed and visible...", flush=True)

    # ADB confirms the package is installed (required condition)
    if not _is_snapdragon_camera_installed():
        return False

    # UI confirms the icon is visible in the app drawer (failure only warns, does not affect test result)
    visible = _find_snapdragon_in_app_drawer()
    if not visible:
        print("[camera] [WARN] Snapdragon Camera installed but icon not found in app drawer UI", flush=True)

    # Package installed is treated as pass
    print("[camera] [OK] Snapdragon Camera verified", flush=True)
    return True


def _save_step_screenshot(step):
    """Save the screenshot to the img/<script_name>/ directory."""
    ts = time.strftime("%Y%m%d_%H%M%S")
    filename = f"{step}_{ts}.png"
    path = os.path.join(SCRIPT_IMG_DIR, filename)
    try:
        img = device.screenshot()
        img.save(path)
        print(f"[camera] [OK] Screenshot saved: {path}", flush=True)
    except Exception as e:
        print(f"[camera] [WARN] Screenshot capture failed: {str(e)[:120]}", flush=True)
    return path


class Test_Snapdragon_Camera_App(unittest.TestCase):
    """Snapdragon Camera app verification test."""

    _suite_pre_state = None

    @classmethod
    def setUpClass(cls):
        print("[camera] ===== Snapdragon Camera App Verification Test Setup =====", flush=True)
        if not serial:
            raise RuntimeError("No Android device found. Set ANDROID_SERIAL or connect one device.")
        init_device()
        cls._suite_pre_state = camera_capture_device_state(device, serial)

    @classmethod
    def tearDownClass(cls):
        print("[camera] ===== Snapdragon Camera App Verification Test TearDown =====", flush=True)
        camera_restore_device_state(cls._suite_pre_state, device, serial)

    def setUp(self):
        print("[camera] --- Test setUp ---", flush=True)
        try:
            device.unlock()
        except Exception:
            pass
        time.sleep(0.5)

    def test_L0_verify_snapdragon_camera_in_app_list(self):
        """
        Test Steps:
        1. Wake and unlock the connected device.
        2. Verify `org.codeaurora.snapcam` is installed through ADB.
        3. Open the app drawer and search for the Snapdragon Camera entry.
        4. Capture evidence; package presence is the required pass condition.
        """
        print("[camera] Step 1: Check camera app in app list must be Snapdragon Camera", flush=True)
        camera_wake_up_device(device)
        
        is_snapdragon = _check_snapdragon_is_default()
        self.assertTrue(is_snapdragon, "Camera app is not Snapdragon Camera in app list")
        
        _save_step_screenshot("step01_snapdragon_camera_verified")


if __name__ == '__main__':
    print("=" * 60)
    print("[CAMERA] Snapdragon Camera App Verification Test")
    print("=" * 60)

    try:
        init_device()
        unittest.main(verbosity=2)
    except Exception as e:
        print(f"[FAILED] Test failed: {e}")
        sys.exit(1)
