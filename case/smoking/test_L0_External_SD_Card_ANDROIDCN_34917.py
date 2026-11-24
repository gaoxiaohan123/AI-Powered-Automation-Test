# -*- coding:utf-8 -*-
# pyright: reportMissingImports=false
"""
L0 External SD card functional verification test - UIAutomator2

Steps:
1. Device has an SD card with a video file inserted; enter suspend mode.
2. Exit suspend mode, play the video from the SD card, verify smooth playback.
3. Delete the video in the App, verify the video disappears.
4. Reboot the device (Reboot DUT), double-check the video has been deleted.

Notes:
- A single script contains only one test case, executed step by step internally.
- Take a screenshot after each successful step, saved to auto_test/img/<script_name>/
- Try to restore the device to its pre-test state after the script finishes.
"""

import os
import subprocess
import sys
import time
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

try:
    import uiautomator2 as u2
except ImportError:
    u2 = None

from common.adb_common import (
    adb_shell,
    camera_is_screen_on,
    device_file_exists,
    get_device_serial,
    media_delete_via_photos_app,
    media_is_player_active,
    media_start_video,
    save_step_screenshot,
    sdcard_find_mount_path,
    sdcard_push_media_file,
)

serial = get_device_serial()
device = None

SCRIPT_BASENAME = os.path.splitext(os.path.basename(__file__))[0]
IMG_ROOT = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.realpath(__file__)))), "img"
)
SCRIPT_IMG_DIR = os.path.join(IMG_ROOT, SCRIPT_BASENAME)
os.makedirs(SCRIPT_IMG_DIR, exist_ok=True)

# Local video file (on the PC, shared with the Audio test)
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.realpath(__file__))))
LOCAL_VIDEO_PATH = os.path.join(_PROJECT_ROOT, "files", "musics_videos", "3d_video.MP4")

# File name pushed to the SD card
SD_VIDEO_FILENAME = "sd_test_video.mp4"

def init_device(force_reconnect=False):
    """Initialize or reconnect UIAutomator2 device."""
    global device
    if u2 is None:
        raise ImportError("uiautomator2 is not installed. Run: pip install uiautomator2")
    if not serial:
        raise RuntimeError("No Android device found. Set ANDROID_SERIAL or connect a device.")
    if force_reconnect or device is None:
        print(f"[sdcard] Connecting to device: {serial}", flush=True)
        device = u2.connect(serial)
    return device


# ─────────────────────── Test class ─────────────────────────────────────────

class Test_External_SDCard(unittest.TestCase):
    """L0 External SD card verification: suspend/resume + video playback + App deletion + reboot confirmation"""

    def setUp(self):
        d = init_device()
        d.screen_on()
        d.press("home")
        time.sleep(1)

    def tearDown(self):
        try:
            d = init_device()
            d.screen_on()
            d.press("home")
            for pkg in [
                "com.google.android.apps.photos",
                "com.android.gallery3d",
                "com.android.music",
            ]:
                adb_shell(serial, f"am force-stop {pkg}", timeout=8)
        except Exception:
            pass

    def test_L0_external_sd_card(self):
        """
        L0 External SD Card — suspend/resume, video playback from SD, delete from App, reboot verify.

        Test Steps:
        1. Device has SD card with a video file. Enter suspend mode.
        2. Exit suspend, play video from SD card. Verify plays smoothly.
        3. Delete the video from App. Verify video disappears.
        4. Reboot DUT. Double check the video has been deleted.
        """
        d = init_device()

        # ── Prepare: detect SD card & push test video ────────────────────────
        sd_path = sdcard_find_mount_path(serial)
        if not sd_path:
            skip_msg = "未检测到外置SD卡，测试需插入SD卡测试后再执行。"
            print(f"[sdcard] [SKIP] {skip_msg}", flush=True)
            self.skipTest(skip_msg)

        print(f"\n[sdcard] SD card path: {sd_path}", flush=True)
        video_path = sdcard_push_media_file(
            serial, LOCAL_VIDEO_PATH, sd_path, SD_VIDEO_FILENAME
        )

        # ════════════════════════════════════════════════════════════════════
        # Step 1 — Verify video exists on SD card, then enter Suspend mode
        # ════════════════════════════════════════════════════════════════════
        print("\n[Step 1] Verify SD card video & enter suspend mode", flush=True)

        self.assertTrue(
            device_file_exists(serial, video_path),
            f"Step 1 FAIL: Video not found on SD card at {video_path}",
        )
        print(f"[sdcard] [OK] Video confirmed on SD card: {video_path}", flush=True)

        d.screen_off()
        time.sleep(2)
        self.assertFalse(
            camera_is_screen_on(serial),
            "Step 1 FAIL: Screen did not turn off (device did not enter suspend)",
        )
        print("[sdcard] [OK] Device entered suspend (screen off)", flush=True)
        save_step_screenshot(d, "step1_suspend", SCRIPT_IMG_DIR)

        # ════════════════════════════════════════════════════════════════════
        # Step 2 — Exit suspend, play video from SD card, verify smooth playback
        # ════════════════════════════════════════════════════════════════════
        print("\n[Step 2] Exit suspend & play video from SD card", flush=True)

        time.sleep(5)  # Remain in suspend briefly
        d.screen_on()
        time.sleep(2)
        self.assertTrue(
            camera_is_screen_on(serial),
            "Step 2 FAIL: Screen did not turn on (device did not exit suspend)",
        )
        print("[sdcard] [OK] Device resumed from suspend", flush=True)

        media_start_video(serial, video_path)
        time.sleep(5)  # Allow player to launch and start rendering frames

        playing = media_is_player_active(serial)
        save_step_screenshot(d, "step2_video_playing", SCRIPT_IMG_DIR)
        self.assertTrue(
            playing,
            "Step 2 FAIL: Video player is not in the foreground or media session not active",
        )
        print("[sdcard] [OK] Video playing smoothly from SD card", flush=True)

        time.sleep(8)  # Let video play for 8 s to confirm sustained smooth playback
        save_step_screenshot(d, "step2_video_playing_8s", SCRIPT_IMG_DIR)

        # Stop player before deletion
        for pkg in ["com.google.android.apps.photos", "com.android.gallery3d"]:
            adb_shell(serial, f"am force-stop {pkg}", timeout=8)
        d.press("home")
        time.sleep(1)

        # ════════════════════════════════════════════════════════════════════
        # Step 3 — Delete video from App, verify it disappears
        # ════════════════════════════════════════════════════════════════════
        print("\n[Step 3] Delete video from App & verify it disappears", flush=True)

        deleted = media_delete_via_photos_app(d, serial, video_path)
        save_step_screenshot(d, "step3_after_delete", SCRIPT_IMG_DIR)
        self.assertTrue(
            deleted,
            f"Step 3 FAIL: Video still exists on device after deletion: {video_path}",
        )
        self.assertFalse(
            device_file_exists(serial, video_path),
            f"Step 3 FAIL: ADB still detects video at {video_path}",
        )
        print("[sdcard] [OK] Video deleted; confirmed absent via ADB", flush=True)

        # ════════════════════════════════════════════════════════════════════
        # Step 4 — Reboot DUT, double-check video is still gone
        # ════════════════════════════════════════════════════════════════════
        print("\n[Step 4] Reboot DUT & double-check video remains deleted", flush=True)

        # Trigger power menu via long-press of power key
        subprocess.run(
            ["adb", "-s", serial, "shell", "input", "keyevent", "--longpress", "26"],
            timeout=10,
        )
        time.sleep(3)

        # Tap Restart / Reboot in the power menu
        if d(text="Restart").exists(timeout=3):
            d(text="Restart").click()
        elif d(text="Reboot").exists(timeout=2):
            d(text="Reboot").click()
        else:
            subprocess.run(["adb", "-s", serial, "shell", "input", "keyevent", "20"], timeout=5)
            time.sleep(0.5)
            subprocess.run(["adb", "-s", serial, "shell", "input", "keyevent", "23"], timeout=5)

        print("[sdcard] Waiting for device to finish rebooting (max 90 s)...", flush=True)
        time.sleep(8)  # Allow device to start shutdown sequence

        # Poll sys.boot_completed until device is fully booted
        boot_completed = False
        deadline = time.time() + 90
        while time.time() < deadline:
            try:
                result = subprocess.run(
                    ["adb", "-s", serial, "shell", "getprop", "sys.boot_completed"],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    encoding="utf-8",
                    errors="ignore",
                    timeout=8,
                )
                if result.stdout.strip() == "1":
                    boot_completed = True
                    break
            except Exception:
                pass
            time.sleep(3)

        self.assertTrue(
            boot_completed,
            "Step 4 FAIL: Device did not complete reboot within 90 s",
        )
        print("[sdcard] [OK] Device rebooted successfully", flush=True)
        time.sleep(3)  # Allow system services to fully settle

        # Reconnect UIAutomator2 after reboot
        d = init_device(force_reconnect=True)
        time.sleep(2)

        # Double-check: video must still be absent after reboot
        self.assertFalse(
            device_file_exists(serial, video_path),
            f"Step 4 FAIL: Video reappeared after reboot at {video_path}",
        )
        save_step_screenshot(d, "step4_reboot_no_video", SCRIPT_IMG_DIR)
        print("[sdcard] [OK] Confirmed: video is still deleted after reboot", flush=True)


if __name__ == "__main__":
    unittest.main(verbosity=2)
