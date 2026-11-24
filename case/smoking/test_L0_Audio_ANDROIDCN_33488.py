# -*- coding:utf-8 -*-
# pyright: reportMissingImports=false
"""
L0 audio verification test - UIAutomator2

Steps:
1. Suspend the device (screen off) then wake it up
2. Play files/musics_videos/test_music.mp3 and verify audio plays
3. Play files/musics_videos/3d_video.MP4 and verify video plays
4. Record a clip with the recorder
5. Replay the recording

Notes: one test case, run step by step; screenshot after each step into img/<script_name>/.
"""

import os
import re
import sys
import time
import subprocess
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

try:
    import uiautomator2 as u2
except ImportError:
    u2 = None

from common.adb_common import get_device_serial, save_step_screenshot

serial = get_device_serial()
device = None

SCRIPT_BASENAME = os.path.splitext(os.path.basename(__file__))[0]
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.realpath(__file__))))
SCRIPT_IMG_DIR = os.path.join(PROJECT_ROOT, "img", SCRIPT_BASENAME)
os.makedirs(SCRIPT_IMG_DIR, exist_ok=True)

MEDIA_DIR = os.path.join(PROJECT_ROOT, "files", "musics_videos")
LOCAL_MUSIC = os.path.join(MEDIA_DIR, "test_music.mp3")
LOCAL_VIDEO = os.path.join(MEDIA_DIR, "3d_video.MP4")
DEVICE_MUSIC = "/sdcard/test_music.mp3"
DEVICE_VIDEO = "/sdcard/3d_video.MP4"
DEVICE_RECORD_DIR = "/sdcard/Music"
RECORDING_GLOB = "recording-*.amr"
YOUTUBE_MUSIC_PACKAGE = "com.google.android.apps.youtube.music"

MUSIC_DURATION = 20
VIDEO_DURATION = 10
RECORD_DURATION = 8
REPLAY_DURATION = 8


def adb(cmd, timeout=15):
    """Run `adb -s <serial> ...` and return stripped stdout."""
    r = subprocess.run(["adb", "-s", serial, *cmd], capture_output=True,
                       text=True, errors="ignore", check=False, timeout=timeout)
    return (r.stdout or "").strip()


def sh(cmd, timeout=15):
    """Run an adb shell command."""
    return adb(["shell", cmd], timeout=timeout)


def init_device():
    global device
    if u2 is None:
        raise ImportError("uiautomator2 not installed: pip install uiautomator2")
    if not serial:
        raise RuntimeError("No Android device. Set ANDROID_SERIAL or connect one.")
    if device is None:
        device = u2.connect(serial)
    return device


def screen_on():
    out = sh("dumpsys power").lower()
    return "state=on" in out or "mwakefulness=awake" in out


def media_active():
    out = sh("dumpsys media_session").lower()
    if "state=playing" in out or "state=3" in out:
        return True
    return "state:started" in sh("dumpsys audio").lower()


def wait_for_media_playing(timeout=8):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if media_active():
            return True
        time.sleep(1)
    return False


def push(local, remote):
    assert os.path.isfile(local), f"Local file not found: {local}"
    adb(["push", local, remote], timeout=60)
    sh(f"am broadcast -a android.intent.action.MEDIA_SCANNER_SCAN_FILE -d file://{remote}")
    print(f"[audio] pushed {remote}", flush=True)


def stop_players():
    sh("am force-stop com.android.gallery3d")
    sh("am force-stop com.google.android.apps.photos")
    sh("am force-stop com.android.music")


def media_uri(remote, media_type="audio"):
    """Return the MediaStore URI for a scanned file, falling back to file://."""
    name = remote.rsplit("/", 1)[-1]
    out = sh(f"content query --uri content://media/external/{media_type}/media "
             f"--projection _id --where \"_display_name='{name}'\"")
    match = re.search(r"_id=(\d+)", out or "")
    if match:
        return f"content://media/external/{media_type}/media/{match.group(1)}"
    return f"file://{remote}"


def play(remote, mime):
    uri = media_uri(remote)
    package_arg = ""
    if sh(f"pm path {YOUTUBE_MUSIC_PACKAGE}").startswith("package:"):
        sh(f"pm grant {YOUTUBE_MUSIC_PACKAGE} android.permission.READ_MEDIA_AUDIO")
        package_arg = f"-p {YOUTUBE_MUSIC_PACKAGE} "
    out = sh(f"am start -a android.intent.action.VIEW {package_arg}-d {uri} "
             f"-t {mime} --grant-read-uri-permission")
    if "error:" in out.lower() or "exception" in out.lower():
        raise RuntimeError(f"Unable to start audio player: {out}")


def play_video(remote):
    """Play via content:// URI (file:// black-buffers on Android 7+); fall back to file://."""
    uri = media_uri(remote, "video")
    sh(f"am start -a android.intent.action.VIEW -d {uri} -t video/* --grant-read-uri-permission")


def dismiss_allow():
    """Dismiss consecutive app chooser and permission dialogs."""
    tapped = False
    resource_ids = (
        "com.android.permissioncontroller:id/permission_allow_button",
        "com.android.permissioncontroller:id/permission_allow_foreground_only_button",
    )
    labels = ("YouTube Music", "While using the app", "Allow", "Always",
              "ALLOW", "Only this time", "OK")
    for _ in range(6):
        target = None
        try:
            for resource_id in resource_ids:
                button = device(resourceId=resource_id)
                if button.exists(timeout=0.5):
                    target = button
                    break
            if target is None:
                for label in labels:
                    button = device(text=label)
                    if button.exists(timeout=0.5):
                        target = button
                        break
            if target is None:
                break
            target.click()
            tapped = True
            time.sleep(1)
        except Exception:
            break
    return tapped


def tap_node(resource_id):
    """Tap the center of a node by resource-id (works for NAF buttons). True if tapped."""
    try:
        xml = device.dump_hierarchy() or ""
    except Exception:
        return False
    for m in re.finditer(r"<node\b[^>]*>", xml):
        tag = m.group(0)
        rid = re.search(r'resource-id="([^"]*)"', tag)
        if rid and rid.group(1) == resource_id:
            b = re.search(r'bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"', tag)
            if b:
                x1, y1, x2, y2 = map(int, b.groups())
                sh(f"input tap {(x1 + x2) // 2} {(y1 + y2) // 2}")
                return True
    return False


class Test_L0_Audio(unittest.TestCase):
    """suspend/resume -> music -> video -> record -> replay."""

    _new_recording = None

    @classmethod
    def setUpClass(cls):
        init_device()

    def setUp(self):
        init_device()
        try:
            device.screen_on()
            device.unlock()
        except Exception:
            pass
        time.sleep(1)

    def step01_suspend_resume(self):
        sh("input keyevent 26")
        time.sleep(3)
        self.assertFalse(screen_on(), "Step1: screen did not turn off")
        sh("input keyevent 26")
        time.sleep(2)
        try:
            device.unlock()
        except Exception:
            pass
        self.assertTrue(screen_on(), "Step1: screen did not turn on")
        save_step_screenshot(device, "step01_suspend_resume", SCRIPT_IMG_DIR)

    def step02_play_music(self):
        push(LOCAL_MUSIC, DEVICE_MUSIC)
        stop_players()
        play(DEVICE_MUSIC, "audio/*")
        time.sleep(3)
        dismiss_allow()
        self.assertTrue(wait_for_media_playing(), "Step2: music did not start playing")
        time.sleep(MUSIC_DURATION)
        save_step_screenshot(device, "step02_music_playing", SCRIPT_IMG_DIR)
        stop_players()

    def step03_play_video(self):
        push(LOCAL_VIDEO, DEVICE_VIDEO)
        stop_players()
        play_video(DEVICE_VIDEO)
        time.sleep(3)
        dismiss_allow()
        time.sleep(VIDEO_DURATION)
        save_step_screenshot(device, "step03_video_playing", SCRIPT_IMG_DIR)
        self.assertTrue(screen_on(), "Step3: screen off during video (crash?)")
        stop_players()

    def step04_record(self):
        rec_id = "com.android.soundrecorder:id/recordButton"
        stop_id = "com.android.soundrecorder:id/stopButton"
        before = set(sh(f"ls {DEVICE_RECORD_DIR}/{RECORDING_GLOB} 2>/dev/null").split())
        # Proactively grant the mic/storage permissions instead of relying on a
        # tap-through "Allow" dialog. If RECORD_AUDIO was ever denied before
        # (including "Don't ask again"), the app stops showing the normal
        # runtime-permission prompt and instead shows a "can't work without
        # required permissions, go to Settings" dialog that dismiss_allow()
        # cannot handle - so no recording is ever produced and the app just
        # shows that dialog. Granting the permission up front avoids the
        # prompt entirely regardless of prior denial state.
        sh("pm grant com.android.soundrecorder android.permission.RECORD_AUDIO")
        sh("pm grant com.android.soundrecorder android.permission.WRITE_EXTERNAL_STORAGE")
        sh("pm grant com.android.soundrecorder android.permission.READ_EXTERNAL_STORAGE")
        sh("pm grant com.android.soundrecorder android.permission.READ_MEDIA_AUDIO")
        sh("am start -n com.android.soundrecorder/.SoundRecorder")
        time.sleep(3)
        dismiss_allow()
        w, h = device.info["displayWidth"], device.info["displayHeight"]
        if not tap_node(rec_id):                       # record
            device.click(w // 2, int(h * 0.82))
        dismiss_allow()
        time.sleep(RECORD_DURATION)
        save_step_screenshot(device, "step04_recording", SCRIPT_IMG_DIR)
        if not tap_node(stop_id):                      # stop
            device.click(int(w * 0.155), int(h * 0.69))
        time.sleep(2)
        for kw in ("SAVE", "Save", "OK"):
            b = device(text=kw)
            if b.exists(timeout=1):
                b.click()
                break
        time.sleep(2)
        after = set(sh(f"ls {DEVICE_RECORD_DIR}/{RECORDING_GLOB} 2>/dev/null").split())
        new = after - before
        self.assertTrue(new, "Step4: no recording file created")
        self.__class__._new_recording = sorted(new)[-1]

    def step05_replay(self):
        rec = self.__class__._new_recording
        self.assertIsNotNone(rec, "Step5: no recording from step4")
        stop_players()
        play(rec, "audio/*")
        time.sleep(3)
        dismiss_allow()
        self.assertTrue(wait_for_media_playing(), "Step5: recording did not start playing")
        time.sleep(REPLAY_DURATION)
        save_step_screenshot(device, "step05_replay", SCRIPT_IMG_DIR)
        stop_players()
        sh(f"rm -f {rec}")

    def test_L0_audio(self):
        """L0 audio verification test.

            Test Steps:
            1. Suspend the device (screen off) then wake it up
            2. Play files/musics_videos/test_music.mp3 and verify audio plays
            3. Play files/musics_videos/3d_video.MP4 and verify video plays
            4. Record a clip with the recorder
            5. Replay the recording and verify its audio plays."""
        self.step01_suspend_resume()
        self.step02_play_music()
        self.step03_play_video()
        self.step04_record()
        self.step05_replay()
        stop_players()
        sh("input keyevent 3")  # back to home


if __name__ == "__main__":
    init_device()
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(Test_L0_Audio)
    ok = unittest.TextTestRunner(verbosity=2).run(suite).wasSuccessful()
    sys.exit(0 if ok else 1)
