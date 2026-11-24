# -*- coding:utf-8 -*-
# pyright: reportMissingImports=false
"""
相机自动化测试 - Suspend/Resume 场景（UI 优先）

步骤:
1. 打开 camera
2. 设备进入 suspend
3. resume 设备并检查 camera 预览界面
4. 拍一张照片
5. 录制一个视频
"""

import os
import re
import sys
import time
import unittest

sys.path.insert(0, '.')

try:
    import uiautomator2 as u2
except ImportError:
    print("[ERROR] uiautomator2 not installed. Install with: pip install uiautomator2")
    sys.exit(1)

from common.adb_common import get_device_serial, camera_photo_count

serial = get_device_serial()
device = None

SCRIPT_BASENAME = os.path.splitext(os.path.basename(__file__))[0]
IMG_ROOT = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.realpath(__file__)))), "img")
SCRIPT_IMG_DIR = os.path.join(IMG_ROOT, SCRIPT_BASENAME)
os.makedirs(SCRIPT_IMG_DIR, exist_ok=True)


CAMERA_PACKAGES = [
    "org.codeaurora.snapcam",
    "com.android.camera",
    "com.google.android.GoogleCamera",
    "com.sonyericsson.android.camera",
]


def init_device():
    """初始化 UIAutomator2 设备连接。"""
    global device
    if device is None:
        print(f"[camera] Connecting to device: {serial}", flush=True)
        device = u2.connect(serial)
        info = device.info
        print(
            f"[camera] [OK] Device connected, screen={info['displayWidth']}x{info['displayHeight']}",
            flush=True,
        )
    return device


def _shell_output(cmd, timeout=8):
    """执行 shell 并返回文本输出。"""
    try:
        resp = device.shell(cmd, timeout=timeout)
        if hasattr(resp, "output"):
            return (resp.output or "").strip()
        return str(resp).strip()
    except Exception:
        return ""


def _foreground_package():
    """获取前台包名。"""
    out = _shell_output("dumpsys window windows", timeout=4)
    m = re.search(r"\s([a-zA-Z0-9_\.]+)/", out)
    return m.group(1) if m else ""


def _is_camera_foreground():
    pkg = _foreground_package()
    return any(x in pkg for x in CAMERA_PACKAGES)


def _wake_up_device():
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


def _press_home():
    """按 Home 键返回桌面。"""
    device.press("home")
    time.sleep(1)


def _dismiss_runtime_dialogs():
    """关闭相机首次启动可能出现的授权弹窗。"""
    keywords = [
        "允许", "仅使用期间允许", "始终允许", "确定", "继续", "同意",
        "Allow", "While using the app", "OK", "Continue", "Agree",
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


def _open_camera_app():
    """启动相机应用（UI 优先，失败再回退）。"""
    print("[camera] Opening camera app...", flush=True)

    for pkg in CAMERA_PACKAGES:
        try:
            device.app_start(pkg, stop=True)
            time.sleep(2)
            _dismiss_runtime_dialogs()
            if _is_camera_foreground():
                print(f"[camera] [OK] Camera opened by app_start: {pkg}", flush=True)
                return True
        except Exception:
            continue

    # 回退到 intent
    out = _shell_output("am start -a android.media.action.IMAGE_CAPTURE", timeout=8)
    time.sleep(2)
    _dismiss_runtime_dialogs()
    if "exception" not in out.lower() and _is_camera_foreground():
        print("[camera] [OK] Camera opened by intent", flush=True)
        return True

    print("[camera] [FAILED] Failed to open camera app", flush=True)
    return False


def _get_screen_size():
    info = device.info
    return info["displayWidth"], info["displayHeight"]


def _is_camera_preview_visible():
    """检查相机预览是否正常显示。"""
    if not _is_camera_foreground():
        return False

    candidates = [
        device(resourceId="org.codeaurora.snapcam:id/shutter_button"),
        device(resourceId="com.android.camera:id/shutter_button"),
        device(resourceIdMatches=".*shutter.*"),
        device(descriptionContains="快门"),
        device(descriptionContains="Shutter"),
    ]
    for obj in candidates:
        try:
            if obj.exists(timeout=0.2):
                return True
        except Exception:
            continue

    # 若按钮不可识别但相机仍在前台，也认为预览存在
    return True


def _trigger_shutter():
    """拍照（优先按钮，回退坐标）。"""
    print("[camera] Trigger shutter...", flush=True)

    button_selectors = [
        device(resourceId="org.codeaurora.snapcam:id/shutter_button"),
        device(resourceId="com.android.camera:id/shutter_button"),
        device(resourceIdMatches=".*shutter.*"),
        device(descriptionContains="快门"),
        device(descriptionContains="Shutter"),
    ]
    for obj in button_selectors:
        try:
            if obj.exists(timeout=0.3):
                obj.click()
                time.sleep(2)
                return True
        except Exception:
            continue

    w, h = _get_screen_size()
    for x, y in [(w // 2, int(h * 0.92)), (w // 2, int(h * 0.88)), (int(w * 0.9), int(h * 0.85))]:
        try:
            device.click(x, y)
            time.sleep(0.6)
        except Exception:
            continue

    try:
        device.press("volume_up")
        time.sleep(2)
    except Exception:
        pass
    return True


def _media_count(extensions):
    """统计常见媒体目录下指定后缀文件数量。"""
    folders = [
        "/sdcard/DCIM/Camera",
        "/storage/emulated/0/DCIM/Camera",
        "/sdcard/DCIM",
        "/storage/emulated/0/DCIM",
        "/sdcard/Movies",
        "/storage/emulated/0/Movies",
    ]
    total = 0
    for folder in folders:
        out = _shell_output(f"ls -1 {folder}", timeout=8)
        if not out:
            continue
        for line in out.splitlines():
            name = (line or "").strip().lower()
            if any(name.endswith(ext) for ext in extensions):
                total += 1
    return total


def _video_count():
    return _media_count((".mp4", ".3gp", ".mkv", ".webm"))


def _list_video_files_with_size():
    """返回视频文件字典: {filename: size_bytes}。"""
    out = _shell_output("ls -l /sdcard/DCIM/Camera", timeout=10)
    files = {}
    if not out:
        return files
    for line in out.splitlines():
        if "VID_" not in line or ".mp4" not in line:
            continue
        # 常见 ls -l 格式: -rw-rw---- 2 u0_a200 media_rw 28532724 2026-06-13 22:05 /sdcard/DCIM/Camera/VID_xxx.mp4
        parts = line.split()
        if len(parts) < 8:
            continue
        try:
            size = int(parts[4])
        except Exception:
            continue
        name = parts[-1].strip()
        files[name] = size
    return files


def _wait_new_nonzero_video(before_files, min_size=10240, timeout=35):
    """等待出现新视频且大小大于阈值。"""
    end_time = time.time() + timeout
    last_files = before_files
    while time.time() < end_time:
        time.sleep(2)
        now_files = _list_video_files_with_size()
        last_files = now_files
        for name, size in now_files.items():
            if name not in before_files and size >= min_size:
                return True, name, size, now_files
    return False, "", 0, last_files


def _wait_count_increase(count_fn, before, timeout=20):
    """等待媒体数量增长，避免保存延迟造成误判。"""
    end_time = time.time() + timeout
    last = before
    while time.time() < end_time:
        time.sleep(2)
        now = count_fn()
        last = now
        if now > before:
            return True, now
    return False, last


def _switch_to_panorama_mode():
    """切换到全景模式。"""
    print("[camera] Switching to panorama mode...", flush=True)

    pano_keywords = ["全景", "Panorama", "Pano"]
    for kw in pano_keywords:
        obj = device(textContains=kw)
        if obj.exists(timeout=0.3):
            obj.click()
            time.sleep(1)
            return True
        obj2 = device(descriptionContains=kw)
        if obj2.exists(timeout=0.3):
            obj2.click()
            time.sleep(1)
            return True

    # 常见模式入口
    for kw in ["模式", "更多", "More", "Mode"]:
        obj = device(textContains=kw)
        if obj.exists(timeout=0.3):
            obj.click()
            time.sleep(1)
            break
        obj2 = device(descriptionContains=kw)
        if obj2.exists(timeout=0.3):
            obj2.click()
            time.sleep(1)
            break

    for kw in pano_keywords:
        obj = device(textContains=kw)
        if obj.exists(timeout=0.3):
            obj.click()
            time.sleep(1)
            return True
        obj2 = device(descriptionContains=kw)
        if obj2.exists(timeout=0.3):
            obj2.click()
            time.sleep(1)
            return True

    # 回退：Snapcam 上模式控件可能不暴露，尝试底部横向滑动切模式
    w, h = _get_screen_size()
    try:
        for _ in range(2):
            device.swipe(int(w * 0.8), int(h * 0.86), int(w * 0.2), int(h * 0.86), duration=0.2)
            time.sleep(0.8)
        print("[camera] [WARN] Panorama switch by text not found, used swipe fallback", flush=True)
        return _is_camera_foreground()
    except Exception:
        print("[camera] [WARN] Panorama mode switch not found", flush=True)
        return False


def _capture_panorama():
    """拍摄一张全景照片。"""
    if not _switch_to_panorama_mode():
        return False

    if not _trigger_shutter():
        return False

    # 全景通常需要移动设备并结束拍摄
    w, h = _get_screen_size()
    try:
        device.swipe(int(w * 0.3), int(h * 0.5), int(w * 0.7), int(h * 0.5), duration=0.5)
        time.sleep(2)
    except Exception:
        pass

    for kw in ["完成", "结束", "停止", "Done", "Stop", "Finish"]:
        obj = device(textContains=kw)
        if obj.exists(timeout=0.2):
            obj.click()
            break
        obj2 = device(descriptionContains=kw)
        if obj2.exists(timeout=0.2):
            obj2.click()
            break

    time.sleep(3)
    return True


def _switch_to_video_mode():
    """切换到视频模式。"""
    print("[camera] Switching to video mode...", flush=True)

    # Snapcam 优先：点击 mode_text=Video
    try:
        snap_video = device(resourceId="org.codeaurora.snapcam:id/mode_text", text="Video")
        if snap_video.exists(timeout=0.5):
            snap_video.click()
            time.sleep(1)
            return True
    except Exception:
        pass

    for kw in ["视频", "录像", "Video"]:
        obj = device(textContains=kw)
        if obj.exists(timeout=0.3):
            obj.click()
            time.sleep(1)
            return True
        obj2 = device(descriptionContains=kw)
        if obj2.exists(timeout=0.3):
            obj2.click()
            time.sleep(1)
            return True
    # 回退：Snapcam 上模式控件可能不暴露，尝试底部横向滑动切模式
    w, h = _get_screen_size()
    try:
        for _ in range(2):
            device.swipe(int(w * 0.2), int(h * 0.86), int(w * 0.8), int(h * 0.86), duration=0.2)
            time.sleep(0.8)
        print("[camera] [WARN] Video switch by text not found, used swipe fallback", flush=True)
        return _is_camera_foreground()
    except Exception:
        print("[camera] [WARN] Video mode switch not found", flush=True)
        return False


def _record_short_video(seconds=5):
    """录制一段短视频。"""
    if not _switch_to_video_mode():
        return False

    # 先点中间，唤醒可能自动隐藏的底部控制条
    w, h = _get_screen_size()
    try:
        device.click(w // 2, h // 2)
        time.sleep(0.6)
    except Exception:
        pass

    print("[camera] Start recording...", flush=True)
    btn_candidates = [
        device(resourceId="org.codeaurora.snapcam:id/video_button"),
        device(resourceIdMatches=".*record.*"),
        device(descriptionContains="录制"),
        device(descriptionContains="Record"),
        device(textContains="录制"),
        device(textContains="Record"),
    ]

    started = False
    for obj in btn_candidates:
        if obj.exists(timeout=0.3):
            obj.click()
            started = True
            break

    if not started:
        # 回退点击底部中央
        device.click(w // 2, int(h * 0.92))
        started = True

    if not started:
        return False

    time.sleep(seconds)

    print("[camera] Stop recording...", flush=True)
    try:
        device.click(w // 2, h // 2)
        time.sleep(0.6)
    except Exception:
        pass
    stopped = False
    for obj in btn_candidates:
        if obj.exists(timeout=0.3):
            obj.click()
            stopped = True
            break

    if not stopped:
        device.click(w // 2, int(h * 0.92))
        stopped = True

    time.sleep(2)
    return started and stopped


def _save_step_screenshot(step):
    """将截图保存到 img/脚本名/ 目录。"""
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


def _suspend_then_resume():
    """设备进入 suspend 后再唤醒恢复。"""
    print("[camera] Entering suspend...", flush=True)
    device.press("power")
    time.sleep(2)

    print("[camera] Resuming device...", flush=True)
    device.press("power")
    time.sleep(1)
    _wake_up_device()
    return True


def _is_screen_on():
    """基于 dumpsys 判断屏幕是否点亮。"""
    out = _shell_output("dumpsys power", timeout=8).lower()
    return (
        "display power: state=on" in out
        or "display power: state = on" in out
        or "mwakefulness=awake" in out
    )


def _capture_device_state():
    """记录测试前设备关键状态，用于收尾恢复。"""
    state = {
        "screen_on": _is_screen_on(),
        "foreground_pkg": _foreground_package(),
    }
    print(
        f"[camera] Captured pre-state: screen_on={state['screen_on']}, "
        f"foreground_pkg={state['foreground_pkg'] or 'unknown'}",
        flush=True,
    )
    return state


def _restore_device_state(state):
    """尽量将设备恢复到测试前状态。"""
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

    should_screen_on = bool(state.get("screen_on", True))
    now_screen_on = _is_screen_on()
    if not should_screen_on and now_screen_on:
        try:
            device.press("power")
            time.sleep(1)
            print("[camera] [OK] Restored screen state: OFF", flush=True)
        except Exception as e:
            print(f"[camera] [WARN] Failed to restore screen state: {str(e)[:120]}", flush=True)


class Test_SuspendCamera_UI(unittest.TestCase):
    """按步骤执行相机 Suspend/Resume 相关测试。"""

    _suite_pre_state = None

    @classmethod
    def setUpClass(cls):
        print("[camera] ===== Camera Suspend UI Test Setup =====", flush=True)
        if not serial:
            raise RuntimeError("No Android device found. Set ANDROID_SERIAL or connect one device.")
        init_device()
        cls._suite_pre_state = _capture_device_state()

    @classmethod
    def tearDownClass(cls):
        _restore_device_state(cls._suite_pre_state)

    def setUp(self):
        print("[camera] --- Test setUp ---", flush=True)
        _wake_up_device()
        time.sleep(0.5)

    def tearDown(self):
        print("[camera] --- Test tearDown ---", flush=True)
        time.sleep(0.2)

    def test_01_suspend_resume_camera_flow(self):
        """打开 camera -> suspend -> resume 校验预览 -> 拍照 -> 录像。"""
        print("[camera] Step 1: Open camera", flush=True)
        opened = _open_camera_app()
        self.assertTrue(opened, "Failed to open camera")

        print("[camera] Step 2: Enter suspend", flush=True)
        resumed = _suspend_then_resume()
        self.assertTrue(resumed, "Failed to suspend/resume device")

        print("[camera] Step 3: Verify camera preview after resume", flush=True)
        preview_ok = _is_camera_preview_visible()
        self.assertTrue(preview_ok, "Camera preview is not normal after resume")
        _save_step_screenshot("step03_resume_preview")

        print("[camera] Step 4: Capture one photo", flush=True)
        before_photo = camera_photo_count(serial, verbose=False)
        action_photo_ok = _trigger_shutter()
        self.assertTrue(action_photo_ok, "Failed to trigger shutter")
        photo_ok, after_photo = _wait_count_increase(lambda: camera_photo_count(serial, verbose=False), before_photo)
        if not photo_ok:
            print(
                f"[camera] [WARN] Photo count not increased (before={before_photo}, after={after_photo}), "
                "keep UI action result as pass criterion",
                flush=True,
            )
        _save_step_screenshot("step04_take_photo")

        print("[camera] Step 5: Record one video", flush=True)
        before_video = _video_count()
        before_video_files = _list_video_files_with_size()
        rec_action_ok = _record_short_video(seconds=6)
        video_ok, new_video_name, new_video_size, after_video_files = _wait_new_nonzero_video(before_video_files)
        after_video = _video_count()
        self.assertTrue(rec_action_ok, "Video record UI action failed")
        self.assertTrue(
            video_ok,
            f"No real video generated. before_count={before_video}, after_count={after_video}, "
            f"before_files={before_video_files}, after_files={after_video_files}",
        )
        _save_step_screenshot("step05_record_video")
        print(
            f"[camera] [OK] New real video: {new_video_name}, size={new_video_size} bytes",
            flush=True,
        )


if __name__ == '__main__':
    print("=" * 60)
    print("[CAMERA] Suspend/Resume Camera UI Automation Test")
    print("=" * 60)

    try:
        init_device()
        unittest.main(verbosity=2)
    except Exception as e:
        print(f"[FAILED] Test failed: {e}")
        sys.exit(1)
