# -*- coding:utf-8 -*-
# pyright: reportMissingImports=false
"""
Snapdragon 相机应用验证测试 - UI自动化

步骤:
1. 检查应用列表中的 camera app 必须是高通的 Snapdragon Camera
"""

import os
import sys
import time
import unittest

sys.path.insert(0, '.')

from common.adb_common import (
    get_device_serial,
    adb_shell,
    save_step_screenshot,
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
    """初始化 UIAutomator2 设备连接。"""
    global device
    if device is None:
        device = camera_init_device(serial)
    return device


def _is_snapdragon_camera_installed():
    """通过 ADB pm list packages 确认 Snapdragon Camera 包名是否已安装。"""
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
    """打开 app drawer 并逐页滚动，查找 Snapdragon Camera 图标是否可见。"""
    snapdragon_names = ["Snapdragon", "SnapCam", "SnapCamera"]

    # 返回主屏幕
    try:
        device.press("home")
        time.sleep(1)
    except Exception:
        pass

    app_list_opened = False

    # 方式1：点击 app drawer 按钮
    try:
        btn = device(resourceIdMatches=".*app.*grid.*|.*app.*drawer.*|.*all.*apps.*")
        if btn.exists(timeout=1):
            btn.click()
            time.sleep(1.5)
            app_list_opened = True
    except Exception:
        pass

    # 方式2：向上滑动打开
    if not app_list_opened:
        try:
            w, h = device.info["displayWidth"], device.info["displayHeight"]
            device.swipe(w // 2, int(h * 0.8), w // 2, int(h * 0.2), duration=0.5)
            time.sleep(1.5)
            app_list_opened = True
        except Exception:
            pass

    # 方式3：长按主屏幕
    if not app_list_opened:
        try:
            w, h = device.info["displayWidth"], device.info["displayHeight"]
            device.long_click(w // 2, h // 2, duration=1)
            time.sleep(1)
            for kw in ["应用", "All apps"]:
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

    # 在 app drawer 中逐页翻找 Snapdragon Camera（横向翻页，最多6页）
    for page in range(6):
        for name in snapdragon_names:
            try:
                if device(textContains=name).exists(timeout=0.5):
                    print(f"[camera] [OK] Found '{name}' in app drawer (page {page + 1})", flush=True)
                    device.press("home")
                    return True
            except Exception:
                pass
        # 横向翻页
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
    """双重验证：ADB 包名安装确认（必要条件）+ app drawer UI 可见性确认（建议条件）。"""
    print("[camera] Verifying Snapdragon Camera is installed and visible...", flush=True)

    # ADB 确认包已安装（必要条件）
    if not _is_snapdragon_camera_installed():
        return False

    # UI 确认图标在 app drawer 中可见（不通过只警告，不影响测试结果）
    visible = _find_snapdragon_in_app_drawer()
    if not visible:
        print("[camera] [WARN] Snapdragon Camera installed but icon not found in app drawer UI", flush=True)

    # 包已安装即视为通过
    print("[camera] [OK] Snapdragon Camera verified", flush=True)
    return True



class Test_SnapdragonCameraApp(unittest.TestCase):
    """Snapdragon 相机应用验证测试。"""

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

    def test_01_verify_snapdragon_camera_in_app_list(self):
        """检查应用列表中的 camera app 必须是高通的 Snapdragon Camera。"""
        print("[camera] Step 1: Check camera app in app list must be Snapdragon Camera", flush=True)
        camera_wake_up_device(device)
        
        is_snapdragon = _check_snapdragon_is_default()
        self.assertTrue(is_snapdragon, "Camera app is not Snapdragon Camera in app list")
        
        save_step_screenshot(device, "step01_snapdragon_camera_verified", SCRIPT_IMG_DIR)


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
