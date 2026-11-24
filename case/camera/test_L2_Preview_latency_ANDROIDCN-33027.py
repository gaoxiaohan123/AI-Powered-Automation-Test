# -*- coding:utf-8 -*-
# pyright: reportMissingImports=false
"""Camera preview latency test using UIAutomator2."""

import os
import sys
import unittest

sys.path.insert(0, ".")

from common.adb_common import camera_stop_packages, get_device_serial, save_step_screenshot, switch_photo_video_set_stayon
from common.common_method import camera_capture_device_state, camera_init_device, camera_restore_device_state, camera_start_package_and_measure_preview, switch_photo_video_keep_awake_unlock


serial = get_device_serial()
device = None
PREVIEW_LATENCY_LIMIT_MS = 2000
CAMERA_PACKAGE = "org.codeaurora.snapcam"
SCRIPT_BASENAME = os.path.splitext(os.path.basename(__file__))[0]
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.realpath(__file__))))
SCRIPT_IMG_DIR = os.path.join(PROJECT_ROOT, "img", SCRIPT_BASENAME)


class Test_L2_PreviewLatency_ANDROIDCN_33027(unittest.TestCase):
    _pre_state = None

    def setUp(self):
        global device
        if not serial:
            raise RuntimeError("No Android device found. Set ANDROID_SERIAL or connect one device.")
        os.makedirs(SCRIPT_IMG_DIR, exist_ok=True)
        if device is None:
            device = camera_init_device(serial)
        type(self)._pre_state = camera_capture_device_state(device, serial)
        switch_photo_video_keep_awake_unlock(device, serial)

    def tearDown(self):
        try:
            switch_photo_video_set_stayon(serial, False)
        finally:
            camera_restore_device_state(type(self)._pre_state, device, serial)

    def test_01_camera_preview_latency(self):
        """
        1. Return to the launcher and directly start the Camera package.
        2. Measure the time until the preview UI appears.
        3. Verify that the camera preview latency is less than 2000 ms.
        """
        camera_stop_packages(serial)
        device.press("home")
        save_step_screenshot(device, "step01_launcher_ready", img_dir=SCRIPT_IMG_DIR)

        latency_ms = camera_start_package_and_measure_preview(
            device, CAMERA_PACKAGE, PREVIEW_LATENCY_LIMIT_MS, serial
        )
        self.assertIsNotNone(latency_ms, "Step2 failed: camera preview did not appear within 2000 ms")
        save_step_screenshot(device, "step02_camera_preview_visible", img_dir=SCRIPT_IMG_DIR)

        print(f"[camera] Preview latency: {latency_ms:.1f} ms", flush=True)
        self.assertLess(
            latency_ms,
            PREVIEW_LATENCY_LIMIT_MS,
            f"Step3 failed: camera preview latency {latency_ms:.1f} ms is not less than 2000 ms",
        )
        save_step_screenshot(device, "step03_preview_latency_under_2000ms", img_dir=SCRIPT_IMG_DIR)


if __name__ == "__main__":
    unittest.main(verbosity=2)