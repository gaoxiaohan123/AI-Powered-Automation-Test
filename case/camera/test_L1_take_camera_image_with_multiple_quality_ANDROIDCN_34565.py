# -*- coding:utf-8 -*-
# pyright: reportMissingImports=false
"""
相机自动化测试 - 多画质拍照（UIAutomator2 优先）

1. 进入设置的 Picture quality，确认默认值为 High，返回预览拍照
2. 依次切换 Standard、Low，每次返回预览拍照
3. 对比三张照片大小：High > Standard > Low
"""
import os
import sys
import unittest
sys.path.insert(0, ".")
from common.adb_common import get_device_serial, save_step_screenshot, switch_photo_video_set_stayon
from common.common_method import camera_capture_device_state, camera_init_device, camera_is_preview_visible, camera_open_camera_app, camera_restore_device_state, picture_quality_back_to_preview, picture_quality_dismiss_popups, picture_quality_is_option_selected, picture_quality_open_camera_settings, picture_quality_open_entry, picture_quality_restore_high, picture_quality_select_option, picture_quality_take_photo, switch_photo_video_keep_awake_unlock
serial = get_device_serial()
device = None
SCRIPT_BASENAME = os.path.splitext(os.path.basename(__file__))[0]
SCRIPT_IMG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.realpath(__file__)))), "img", SCRIPT_BASENAME)


def shot(step):
    save_step_screenshot(device, step, img_dir=SCRIPT_IMG_DIR)


class Test_L1_TakeCameraImageWithMultipleQuality_ANDROIDCN_34565(unittest.TestCase):
    _suite_pre_state = None
    @classmethod
    def setUpClass(cls):
        global device
        if not serial:
            raise RuntimeError("No Android device found. Set ANDROID_SERIAL or connect one device.")
        os.makedirs(SCRIPT_IMG_DIR, exist_ok=True)
        device = camera_init_device(serial)
        cls._suite_pre_state = camera_capture_device_state(device, serial)
        switch_photo_video_keep_awake_unlock(device, serial)
    @classmethod
    def tearDownClass(cls):
        try:
            picture_quality_restore_high(device, serial)
        finally:
            try:
                switch_photo_video_set_stayon(serial, False)
            finally:
                camera_restore_device_state(cls._suite_pre_state, device, serial)
    def setUp(self):
        global device
        self._initialized_in_setup = False
        if not serial:
            raise RuntimeError("No Android device found. Set ANDROID_SERIAL or connect one device.")
        if device is None:
            os.makedirs(SCRIPT_IMG_DIR, exist_ok=True)
            device = camera_init_device(serial)
            type(self)._suite_pre_state = camera_capture_device_state(device, serial)
            self._initialized_in_setup = True
        switch_photo_video_keep_awake_unlock(device, serial)

    def tearDown(self):
        global device
        if not self._initialized_in_setup:
            return
        try:
            picture_quality_restore_high(device, serial)
        finally:
            try:
                switch_photo_video_set_stayon(serial, False)
            finally:
                camera_restore_device_state(type(self)._suite_pre_state, device, serial)
                device = None

    def _switch_quality_and_capture(self, quality, step_no, step_name):
        self.assertTrue(picture_quality_open_camera_settings(device), f"Step{step_no} failed: cannot reopen camera settings")
        self.assertTrue(picture_quality_open_entry(device), f"Step{step_no} failed: cannot reopen Picture quality settings")
        self.assertTrue(picture_quality_select_option(device, quality), f"Step{step_no} failed: cannot select Picture quality={quality}")
        self.assertTrue(picture_quality_back_to_preview(device), f"Step{step_no} failed: cannot return to camera preview")
        ok, photo_size = picture_quality_take_photo(device, serial, step_name, shot)
        self.assertTrue(ok, f"Step{step_no} failed: {quality} photo was not created")
        return photo_size

    def test_01_take_camera_image_with_multiple_quality(self):
        """Capture one photo at High, Standard and Low, then compare their file sizes."""
        self.assertTrue(camera_open_camera_app(device, serial), "Step1 failed: cannot open camera app")
        picture_quality_dismiss_popups(device)
        self.assertTrue(camera_is_preview_visible(device, serial), "Step1 failed: camera preview not visible")
        shot("step01_camera_preview_ready")

        self.assertTrue(picture_quality_open_camera_settings(device), "Step2 failed: cannot open camera settings")
        self.assertTrue(picture_quality_open_entry(device), "Step2 failed: cannot open Picture quality settings")
        shot("step02_open_picture_quality")
        self.assertTrue(picture_quality_is_option_selected(device, "High"), "Step3 failed: default Picture quality is not High")
        shot("step03_default_picture_quality_high")

        self.assertTrue(picture_quality_back_to_preview(device), "Step4 failed: cannot return to camera preview for High")
        ok, high_size = picture_quality_take_photo(device, serial, "step04_capture_high_success", shot)
        self.assertTrue(ok, "Step4 failed: High photo was not created")

        standard_size = self._switch_quality_and_capture("Standard", 7, "step07_capture_standard_success")
        low_size = self._switch_quality_and_capture("Low", 10, "step10_capture_low_success")

        self.assertGreater(high_size, standard_size, f"Step11 failed: High ({high_size}) is not larger than Standard ({standard_size})")
        self.assertGreater(standard_size, low_size, f"Step11 failed: Standard ({standard_size}) is not larger than Low ({low_size})")
        shot("step11_picture_size_comparison_success")


if __name__ == "__main__":
    unittest.main(verbosity=2)