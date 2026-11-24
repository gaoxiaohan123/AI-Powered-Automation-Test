# -*- coding:utf-8 -*-
# pyright: reportMissingImports=false
"""
相机自动化测试 - 异常切换拍照与录像（UIAutomator2 优先）

步骤:
1. 打开 camera 并拍一张照片，检查拍照成功
2. 切换到录制视频界面，检查切换成功
3. 录制一个视频，检查录制成功
4. 重复步骤 1~3 共 20 次，每次照片和视频都能成功生成
"""
import os
import sys
import time
import unittest
sys.path.insert(0, ".")
from common.adb_common import camera_photo_count, emmc_list_internal_video_files, get_device_serial, save_step_screenshot, switch_photo_video_set_stayon
from common.common_method import camera_capture_device_state, camera_init_device, camera_is_preview_visible, camera_open_camera_app, camera_restore_device_state, switch_photo_video_click_any, switch_photo_video_ensure_preview, switch_photo_video_is_recording, switch_photo_video_keep_awake_unlock, switch_photo_video_switch_mode
serial = get_device_serial()
device = None
VIDEO_RECORD_SECONDS = 10
SCRIPT_BASENAME = os.path.splitext(os.path.basename(__file__))[0]
SCRIPT_IMG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.realpath(__file__)))), "img", SCRIPT_BASENAME)
MODE_TEXT_ID = "org.codeaurora.snapcam:id/mode_text"


def init_device():
    global device
    if device is None:
        device = camera_init_device(serial)
    return device


def shot(step):
    save_step_screenshot(device, step, img_dir=SCRIPT_IMG_DIR)


def take_photo(round_idx, prefix="step01_take_photo"):
    if not switch_photo_video_switch_mode(device, "Photo", round_idx, MODE_TEXT_ID, shot):
        c = camera_photo_count(serial, verbose=False); return False, c, c
    before = camera_photo_count(serial, verbose=False)
    shutter = [device(resourceId="org.codeaurora.snapcam:id/shutter_button"), device(resourceId="com.android.camera:id/shutter_button"), device(resourceIdMatches=r".*id/shutter_button$"), device(descriptionContains="Shutter"), device(descriptionContains="Capture")]
    for _ in range(2):
        if not switch_photo_video_click_any(shutter):
            continue
        end = time.time() + 16
        while time.time() < end:
            time.sleep(1.5)
            after = camera_photo_count(serial, verbose=False)
            if after > before:
                shot(f"{prefix}_round{round_idx:02d}"); return True, before, after
    return False, before, camera_photo_count(serial, verbose=False)


def record_video(round_idx):
    if not switch_photo_video_switch_mode(device, "Video", round_idx, MODE_TEXT_ID, shot):
        return False, "", 0, [], []
    before = emmc_list_internal_video_files(serial)
    toggle = [device(resourceId="org.codeaurora.snapcam:id/video_button"), device(resourceId="com.android.camera:id/video_button"), device(resourceIdMatches=r".*id/video_button$")]
    if not switch_photo_video_click_any(toggle):
        return False, "", 0, before, before
    t = time.time() + 8
    while time.time() < t and not switch_photo_video_is_recording(device):
        time.sleep(0.3)
    if not switch_photo_video_is_recording(device):
        return False, "", 0, before, before
    time.sleep(VIDEO_RECORD_SECONDS)
    for _ in range(6):
        if not switch_photo_video_is_recording(device):
            break
        switch_photo_video_click_any(toggle); time.sleep(0.8)
    end = time.time() + 55
    while time.time() < end:
        time.sleep(2)
        after = emmc_list_internal_video_files(serial)
        new_files = [p for p in after if p not in set(before)]
        if new_files:
            shot(f"step03_record_video_round{round_idx:02d}"); return True, new_files[-1], 1, before, after
    return False, "", 0, before, before


class Test_L3_Abnormal_SwitchPhotoVideo_ANDROIDCN_34546(unittest.TestCase):
    _suite_pre_state = None
    @classmethod
    def setUpClass(cls):
        if not serial:
            raise RuntimeError("No Android device found. Set ANDROID_SERIAL or connect one device.")
        os.makedirs(SCRIPT_IMG_DIR, exist_ok=True)
        init_device()
        cls._suite_pre_state = camera_capture_device_state(device, serial)
        switch_photo_video_keep_awake_unlock(device, serial)
    @classmethod
    def tearDownClass(cls):
        try:
            switch_photo_video_set_stayon(serial, False)
        finally:
            camera_restore_device_state(cls._suite_pre_state, device, serial)
    def setUp(self):
        switch_photo_video_keep_awake_unlock(device, serial)
    def test_01_abnormal_switch_photo_video_flow(self):
        """
        1. Open Camera and take one photo, then verify photo capture succeeds.
        2. Switch to the video recording screen and verify the switch succeeds.
        3. Record one video and verify recording succeeds.
        4. Repeat steps 1 to 3 for 20 rounds, ensuring both photo and video are successfully generated each round.
        """
        self.assertTrue(camera_open_camera_app(device, serial), "Step1 failed: cannot open camera app")
        self.assertTrue(camera_is_preview_visible(device, serial), "Step1 failed: camera preview not visible")
        ok, b, a = take_photo(0); self.assertTrue(ok, f"Step1 failed: photo not generated, before={b}, after={a}")
        ok, nv, sz, bf, af = record_video(0); self.assertTrue(ok, f"Step3 failed: video not generated, new={nv}, size={sz}, before={bf}, after={af}")
        ok, b, a = take_photo(0, "step05_take_photo_after_video"); self.assertTrue(ok, f"Baseline post-video photo failed, before={b}, after={a}")
        for idx in range(1, 21):
            self.assertTrue(switch_photo_video_ensure_preview(device, serial, idx, shot), f"Round {idx:02d}: preview not visible")
            ok, nv, sz, bf, af = record_video(idx)
            self.assertTrue(ok, f"Round {idx:02d}: video failed, new={nv}, size={sz}, before={bf}, after={af}")
            ok, b, a = take_photo(idx, "step05_take_photo_after_video")
            self.assertTrue(ok, f"Round {idx:02d}: post-video photo failed, before={b}, after={a}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
