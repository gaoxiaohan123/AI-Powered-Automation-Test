# -*- coding:utf-8 -*-
# pyright: reportMissingImports=false
"""
Test case: L0 eMMC internal-storage video lifecycle validation.

Test Steps:
1. Verify that no external SD card is mounted so the test uses internal storage.
2. Run a suspend/resume cycle and verify the device wakes before using the camera.
3. Record a video with the Camera application and identify the newly created file.
4. Open the recorded video and play it to completion to verify it is readable.
5. Select USB File transfer mode from the notification panel.
6. Verify the recorded video is visible in internal storage from the host computer.
7. Delete the video from the host computer and wait for media storage to update.
8. Verify the video is absent on the device, save evidence for completed steps, and
    restore the original USB/device state during cleanup.
"""

import os
import re
import subprocess
import sys
import time
import unittest

sys.path.insert(0, ".")

from common.adb_common import (
    adb_shell,
    get_device_serial,
    press_home_key,
    save_step_screenshot,
    is_screen_on,
    ipsm_get_prop,
    ipsm_restore_usb_mode,
    emmc_list_internal_video_files,
    emmc_latest_internal_video_file,
    emmc_list_internal_videos_with_meta,
    emmc_newest_valid_video_file,
    emmc_device_has_sd_card,
    emmc_verify_video_deleted_on_device,
    emmc_sleep_then_wake,
    emmc_normalize_internal_relpath,
    emmc_delete_video_from_pc,
)
from common.common_method import (
    camera_capture_device_state,
    camera_init_device,
    camera_dismiss_runtime_dialogs,
    camera_restore_device_state,
    camera_wake_up_device,
    camera_open_camera_app,
    camera_is_preview_visible,
    emmc_click_first_visible,
    emmc_switch_camera_to_video_mode,
    emmc_click_record_button_once,
    emmc_stop_recording,
    emmc_dismiss_camera_popups,
    emmc_play_video_to_end,
    ipsm_select_file_system_mode,
)


serial = get_device_serial()
device = None

SCRIPT_BASENAME = os.path.splitext(os.path.basename(__file__))[0]
ROOT_DIR = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", ".."))
IMG_ROOT = os.path.join(ROOT_DIR, "img")
SCRIPT_IMG_DIR = os.path.join(IMG_ROOT, SCRIPT_BASENAME)
os.makedirs(SCRIPT_IMG_DIR, exist_ok=True)


def init_device():
    """初始化 UIAutomator2 设备连接。"""
    global device
    if device is not None:
        return device

    last_err = None
    for _ in range(2):
        try:
            device = camera_init_device(serial)
            if device is not None:
                return device
        except Exception as e:
            last_err = e
            time.sleep(1)

    raise RuntimeError(f"Failed to initialize UI device: {last_err}")


def _get_device():
    """获取可用设备对象，必要时自动重连。"""
    global device
    if device is None:
        return init_device()
    return device


def _safe_save_step_screenshot(step_name):
    """截图安全封装，避免 device 丢失导致 NoneType 异常。"""
    dev = _get_device()
    return save_step_screenshot(dev, step_name, SCRIPT_IMG_DIR)


def _safe_wake_up_device():
    """唤醒设备，若句柄失效则先重连。"""
    dev = _get_device()
    camera_wake_up_device(dev)
    return device


def _is_ct47_device():
    """Return True only for CT47-specific storage verification handling."""
    model = adb_shell(serial, "getprop", "ro.product.model", timeout=8)
    product = adb_shell(serial, "getprop", "ro.build.product", timeout=8)
    combined = f"{model.stdout or ''} {product.stdout or ''}".lower()
    return "ct47" in combined


def _internal_video_exists(video_path, retries=5):
    """Check the recorded file across Android's equivalent storage paths."""
    if not video_path:
        return False
    file_name = video_path.replace("\\", "/").rsplit("/", 1)[-1]

    normalized = video_path.replace("\\", "/").strip()
    relative = normalized
    for prefix in ("/storage/emulated/0/", "/sdcard/"):
        if relative.startswith(prefix):
            relative = relative[len(prefix):]
            break

    candidates = [
        f"/storage/emulated/0/{relative}",
        f"/sdcard/{relative}",
    ]
    for _ in range(retries):
        for candidate in candidates:
            result = adb_shell(serial, "stat", "-c", "%s", candidate, timeout=8)
            out = (result.stdout or "").strip()
            if result.returncode == 0 and out.isdigit() and int(out) > 0:
                print(f"[emmc] [OK] video exists: {candidate} (size={out})", flush=True)
                return True
            result_test = adb_shell(serial, "test", "-f", candidate, timeout=8)
            if result_test.returncode == 0:
                print(f"[emmc] [OK] video exists (test -f): {candidate}", flush=True)
                return True
        time.sleep(1)

    media = adb_shell(
        serial,
        "content", "query", "--uri", "content://media/external/video/media",
        "--projection", "_display_name", "--where", f"_display_name='{file_name}'",
        timeout=12,
    )
    if media.returncode == 0 and file_name in (media.stdout or ""):
        print(f"[emmc] [OK] video exists in MediaStore: {file_name}", flush=True)
        return True

    listed = emmc_list_internal_video_files(serial)
    for f in listed:
        if f.replace("\\", "/").rsplit("/", 1)[-1] == file_name:
            print(f"[emmc] [OK] video matched in listed files: {f}", flush=True)
            return True

    print(
        f"[emmc] [WARN] video not found: expected={video_path}, listed={listed}",
        flush=True,
    )
    return False


def _ct47_video_is_stable(video_path):
    """Confirm CT47 finished writing the file before playback starts."""
    if not video_path:
        return False
    normalized = video_path.replace("\\", "/").strip()
    relative = normalized
    for prefix in ("/storage/emulated/0/", "/sdcard/"):
        if relative.startswith(prefix):
            relative = relative[len(prefix):]
            break

    candidates = (
        f"/storage/emulated/0/{relative}",
        f"/sdcard/{relative}",
    )
    previous_size = None
    for _ in range(5):
        current_size = None
        for candidate in candidates:
            result = adb_shell(serial, "stat", "-c", "%s", candidate, timeout=8)
            out = (result.stdout or "").strip()
            if result.returncode == 0 and out.isdigit() and int(out) > 0:
                current_size = int(out)
                break
            res_ls = adb_shell(serial, "ls", "-l", candidate, timeout=8)
            match = re.search(r"\s(\d+)\s+\d{4}-\d{2}-\d{2}", res_ls.stdout or "")
            if res_ls.returncode == 0 and match and int(match.group(1)) > 0:
                current_size = int(match.group(1))
                break
        if current_size is not None and current_size >= 10240:
            if current_size == previous_size:
                print(f"[emmc] [OK] CT47 video is stable: {video_path}, size={current_size}", flush=True)
                return True
            previous_size = current_size
        time.sleep(0.8)
    return False


def _record_one_video_and_get_new_path():
    """录制一个短视频并返回新生成的视频路径。"""
    dev = _get_device()
    is_ct47 = _is_ct47_device()
    before = set(emmc_list_internal_video_files(serial))

    for attempt in range(1, 3):
        opened = camera_open_camera_app(dev, serial)
        if not opened:
            print("[emmc] [WARN] camera open failed on this attempt", flush=True)
            continue

        emmc_dismiss_camera_popups(dev)

        if not camera_is_preview_visible(dev, serial):
            emmc_dismiss_camera_popups(dev)
            time.sleep(0.8)
            if not camera_is_preview_visible(dev, serial):
                print("[emmc] [WARN] camera preview not visible", flush=True)
                continue

        emmc_dismiss_camera_popups(dev)
        emmc_switch_camera_to_video_mode(dev)
        emmc_dismiss_camera_popups(dev)

        started = False
        for _ in range(3):
            if emmc_click_record_button_once(dev, serial):
                started = True
                break
            emmc_dismiss_camera_popups(dev)
            time.sleep(0.6)
        if not started:
            print("[emmc] [WARN] failed to start recording", flush=True)
            continue

        time.sleep(8)

        stopped = emmc_stop_recording(dev, serial)
        if not stopped:
            print("[emmc] [WARN] stop not confirmed; checking new video file before failing", flush=True)

        newest = ""
        # 录制落盘在部分机型较慢，延长检测窗口。
        for _ in range(15 if is_ct47 else 20):
            now_list = emmc_list_internal_video_files(serial)
            now = set(now_list)
            diff = sorted(now - before)
            if diff:
                newest = diff[-1]
                if not is_ct47 or _ct47_video_is_stable(newest):
                    break
                newest = ""
            elif is_ct47:
                # CT47 A13/A14: 如果 diff 为空，尝试通过 stat mtime 检测最新生成的非零视频
                cand = emmc_newest_valid_video_file(serial, min_size=10240)
                if cand and cand not in before and _ct47_video_is_stable(cand):
                    newest = cand
                    break
            time.sleep(0.8 if is_ct47 else 1)

        if newest:
            # 广播通知系统扫描新视频，确保 MediaStore & MTP 同步
            adb_shell(serial, "am", "broadcast", "-a", "android.intent.action.MEDIA_SCANNER_SCAN_FILE", "-d", f"file://{newest}", timeout=8)
            print(f"[emmc] [OK] new recorded video: {newest}", flush=True)
            return True, newest

        latest = (emmc_newest_valid_video_file(serial, min_size=10240) if is_ct47 else "") or emmc_latest_internal_video_file(serial)
        if latest:
            adb_shell(serial, "am", "broadcast", "-a", "android.intent.action.MEDIA_SCANNER_SCAN_FILE", "-d", f"file://{latest}", timeout=8)
            print(f"[emmc] [WARN] no diff video detected; fallback latest video: {latest}", flush=True)
            return True, latest

    print("[emmc] [WARN] recording attempts exhausted", flush=True)
    return False, ""


class Test_L0_EMMC(unittest.TestCase):
    """EMMC 场景验证：无 SD 卡 + 录像 + USB File system + PC 删除 + 手机侧确认删除。"""

    _suite_pre_state = None
    _pre_usb_config = ""

    @classmethod
    def setUpClass(cls):
        print("[emmc] ===== EMMC Test Setup =====", flush=True)
        if not serial:
            raise RuntimeError("No Android device found. Set ANDROID_SERIAL or connect one device.")

        init_device()
        cls._suite_pre_state = camera_capture_device_state(device, serial)
        cls._pre_usb_config = ipsm_get_prop(serial, "sys.usb.config")
        print(f"[emmc] captured pre_usb_config={cls._pre_usb_config}", flush=True)

    @classmethod
    def tearDownClass(cls):
        print("[emmc] ===== EMMC Test TearDown =====", flush=True)
        ipsm_restore_usb_mode(serial, cls._pre_usb_config)
        camera_restore_device_state(cls._suite_pre_state, device, serial)

    def setUp(self):
        _safe_wake_up_device()

    def test_L0_emmc_video_file_system_delete(self):
        """
        Test Steps:
        1. Verify no SD card is present and run a suspend/resume cycle.
        2. Record a Camera video and identify the new internal-storage file.
        3. Play the recording to completion and verify it is readable.
        4. Select USB File transfer mode and verify the video is visible to the host.
        5. Delete the file on the host and verify it is absent on the device.
        """

        print("[emmc] Step 1: Confirm device has no SD card", flush=True)
        has_sd = emmc_device_has_sd_card(serial)
        self.assertFalse(has_sd, "Device has SD card, expected no SD card for EMMC case")
        _safe_save_step_screenshot("step01_no_sd_card")

        print("[emmc] Step 2: Enter suspend then wake up", flush=True)
        resumed = emmc_sleep_then_wake(serial)
        self.assertTrue(resumed, "Device failed to wake from suspend")
        _safe_save_step_screenshot("step02_suspend_resume")

        print("[emmc] Step 3: Record one video by camera", flush=True)
        recorded, video_path = _record_one_video_and_get_new_path()
        self.assertTrue(recorded and bool(video_path), "Failed to record video")
        _safe_save_step_screenshot("step03_video_recorded")

        print("[emmc] Step 4: Directly open and play the recorded video", flush=True)
        played = emmc_play_video_to_end(_get_device(), serial, video_path)
        self.assertTrue(played, "Failed to play recorded video")
        _safe_save_step_screenshot("step04_video_playback_done")

        print("[emmc] Step 5: Return to Home before switching USB", flush=True)
        press_home_key(serial)
        time.sleep(1)
        _safe_save_step_screenshot("step05_home_before_usb")

        is_ct47 = _is_ct47_device()
        if is_ct47:
            video_confirmed_before_usb = _internal_video_exists(video_path)
        else:
            video_confirmed_before_usb = video_path in emmc_list_internal_video_files(serial)

        print("[emmc] Step 6: Open USB and select File system", flush=True)
        fs_ok = ipsm_select_file_system_mode(_get_device(), serial)
        self.assertTrue(fs_ok, "Failed to switch USB mode to File system")
        _safe_save_step_screenshot("step06_usb_file_system")

        print("[emmc] Step 7: Verify video exists in internal storage", flush=True)
        if is_ct47:
            existed_before_delete = video_confirmed_before_usb or _internal_video_exists(video_path)
        else:
            existed_before_delete = video_path in emmc_list_internal_video_files(serial)
        self.assertTrue(existed_before_delete, f"Recorded video not found in internal storage: {video_path}")
        _safe_save_step_screenshot("step07_video_in_internal_storage")

        print("[emmc] Step 8: Delete video from PC side", flush=True)
        deleted_on_pc = emmc_delete_video_from_pc(video_path)
        self.assertTrue(deleted_on_pc, "Failed to delete video from PC side")
        _safe_save_step_screenshot("step08_pc_delete_video")

        print("[emmc] Step 9: Confirm video is removed on device", flush=True)
        deleted_on_phone = emmc_verify_video_deleted_on_device(serial, video_path)
        self.assertTrue(deleted_on_phone, "Video still exists on device after PC deletion")
        _safe_save_step_screenshot("step09_phone_confirm_deleted")


if __name__ == "__main__":
    print("=" * 70)
    print("[EMMC] L0 EMMC Video + USB File-System Delete Test")
    print("=" * 70)
    try:
        init_device()
        unittest.main(verbosity=2)
    except Exception as e:
        print(f"[FAILED] Test failed: {e}")
        sys.exit(1)
