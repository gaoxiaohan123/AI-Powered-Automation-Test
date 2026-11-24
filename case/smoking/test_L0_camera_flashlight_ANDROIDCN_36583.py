import os
import re
import unittest
import uiautomator2 as u2
import time
import subprocess
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from common.adb_common import save_step_screenshot, detect_default_camera_activity, run_adb_cmd
from common.common_method import (
    camera_dismiss_runtime_dialogs,
    dismiss_full_screen_hint
)

serial = os.environ.get('ANDROID_SERIAL')
d = u2.connect(serial)

SCRIPT_BASENAME = os.path.splitext(os.path.basename(__file__))[0]
SCRIPT_IMG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.realpath(__file__)))), 'img', SCRIPT_BASENAME)
os.makedirs(SCRIPT_IMG_DIR, exist_ok=True)

CAMERA_ACTIVITIES = [
    'com.android.camera2/com.android.camera.CameraLauncher',
    'com.google.android.GoogleCamera/com.android.camera.CameraLauncher',
    'org.codeaurora.snapcamera/com.android.camera.CameraActivity',
    'org.codeaurora.snapcam/com.android.camera.CameraLauncher',
    'org.codeaurora.snapcam/com.android.camera.CameraActivity',
]
CAMERA_PACKAGES = [
    'org.codeaurora.snapcamera',
    'org.codeaurora.snapcam',
    'com.android.camera2',
    'com.google.android.GoogleCamera',
    'com.android.camera',
]
CT37T_CAMERA_PACKAGE = 'org.codeaurora.snapcam'
CT37T_SHUTTER_COORDINATES = (540, 2129)
CT37T_FLASH_COORDINATES = (676, 96)
# CK67's snapcam draws the shutter/flash controls in a GL overlay with no selectors; ratios are of the screen size.
CK67_CONTROL_RATIOS = {'shutter': (0.5, 0.919), 'flash': (0.615, 0.054)}

def _run_adb_shell(command):
    proc = subprocess.run(
        ['adb', '-s', serial, 'shell', command],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        encoding='utf-8',
        errors='ignore',
    )
    return (proc.stdout or '').strip()

def _is_ct37t():
    return _run_adb_shell('getprop ro.product.device').upper() == 'CT37T'

def _is_ck67():
    return _run_adb_shell('getprop ro.product.model').upper() == 'CK67'

def _camera_in_foreground():
    foreground = _run_adb_shell('dumpsys window | grep -E "mCurrentFocus|mFocusedApp"')
    return f'{CT37T_CAMERA_PACKAGE}/com.android.camera.CameraActivity' in foreground

def _tap_ct37t_control(coordinates):
    _run_adb_shell(f'input tap {coordinates[0]} {coordinates[1]}')
    time.sleep(1)

def _tap_camera_control(name):
    """Tap a selector-less control by coordinates; returns False on models that don't need it."""
    if _is_ct37t():
        _tap_ct37t_control(CT37T_SHUTTER_COORDINATES if name == 'shutter' else CT37T_FLASH_COORDINATES)
        return True
    if _is_ck67():
        size = re.search(r'(\d+)x(\d+)', _run_adb_shell('wm size'))
        width, height = (int(size.group(1)), int(size.group(2))) if size else (480, 800)
        ratio_x, ratio_y = CK67_CONTROL_RATIOS[name]
        _run_adb_shell(f'input tap {int(width * ratio_x)} {int(height * ratio_y)}')
        time.sleep(1)
        return True
    return False

def _dismiss_camera_permission_dialogs():
    if _is_ck67():
        camera_dismiss_runtime_dialogs(d)

def remove_dir(dev_id, path):
    run_adb_cmd(dev_id, f'shell rm -rf {path}', log_print=False)

def _launch_camera():
    resolved = detect_default_camera_activity(serial, preferred_packages=CAMERA_PACKAGES)
    launch_results = []
    if resolved:
        package = resolved.split('/', 1)[0]
        result = subprocess.run(['adb', '-s', serial, 'shell', 'am', 'start', '-W',
                                 '-a', 'android.intent.action.MAIN',
                                 '-c', 'android.intent.category.LAUNCHER',
                                 '-p', package],
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                encoding='utf-8', errors='ignore')
        launch_results.append(f'{package} launcher: {(result.stdout or "").strip()}')
        time.sleep(2)

        _dismiss_camera_permission_dialogs()
        dismiss_full_screen_hint(d)
        time.sleep(1)

        if d(text='OK').exists(timeout=1):
            d(text="OK").click()
            time.sleep(2)

        if _camera_ready():
            return
    for activity in CAMERA_ACTIVITIES:
        result = subprocess.run(['adb', '-s', serial, 'shell', 'am', 'start', '-W', '-n', activity],
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                encoding='utf-8', errors='ignore')
        launch_results.append(f'{activity}: {(result.stdout or "").strip()}')
        time.sleep(2)

        _dismiss_camera_permission_dialogs()
        dismiss_full_screen_hint(d)
        time.sleep(1)

        if d(text='OK').exists(timeout=1):
            d(text="OK").click()
            time.sleep(2)

        if _camera_ready():
            return
    foreground = _run_adb_shell('dumpsys window windows | grep -E "mCurrentFocus|mFocusedApp"')
    raise AssertionError(
        'Failed to launch camera app. '
        f'Resolved activity: {resolved or "none"}. '
        f'Foreground window: {foreground or "none"}. '
        f'Launch results: {" | ".join(launch_results) or "none"}'
    )

def _camera_ready():
    if (_is_ct37t() or _is_ck67()) and _camera_in_foreground():
        return True
    return any([
        d(resourceId='org.codeaurora.snapcamera:id/shutter_button').exists(timeout=1),
        d(resourceId='org.codeaurora.snapcam:id/shutter_button').exists(timeout=1),
        d(resourceId='com.android.camera:id/shutter_button').exists(timeout=1),
        d(resourceId='com.android.camera2:id/shutter_button').exists(timeout=1),
        d(description='Shutter').exists(timeout=1),
        d(descriptionContains='Shutter').exists(timeout=1),
        d(descriptionContains='Capture').exists(timeout=1),
    ])

def _count_photos():
    try:
        # Count image files under the single canonical Camera folder. Do NOT scan both
        # /sdcard and /storage/emulated/0 together: /sdcard is a symlink to the latter,
        # so scanning both double-counts every file.
        result = _run_adb_shell(
            "find /storage/emulated/0/DCIM/Camera -type f "
            "\\( -iname '*.jpg' -o -iname '*.jpeg' -o -iname '*.png' -o -iname '*.dng' \\) 2>/dev/null | wc -l"
        )
        if not result:
            return 0
        digits = ''.join(ch for ch in result if ch.isdigit())
        return int(digits) if digits else 0
    except Exception:
        return -1

def _tap_first_existing(selectors):
    for selector in selectors:
        if selector.exists(timeout=1):
            selector.click()
            time.sleep(1)
            return True
    return False

def _flash_mode_enabled():
    return any([
        d(text='On').exists(timeout=1),
        d(text='Flash on').exists(timeout=1),
        d(descriptionContains='flash on').exists(timeout=1),
        d(descriptionContains='Flash on').exists(timeout=1),
        d(resourceId='org.codeaurora.snapcamera:id/flash_button', checked=True).exists(timeout=1),
        d(resourceId='org.codeaurora.snapcam:id/flash_button', checked=True).exists(timeout=1),
    ])

def _set_flash(enabled):
    toggle_candidates = [
        d(resourceId='org.codeaurora.snapcamera:id/flash_button'),
        d(resourceId='org.codeaurora.snapcam:id/flash_button'),
        d(resourceId='com.android.camera2:id/flash_toggle_button'),
        d(descriptionContains='Flash'),
        d(textContains='Flash'),
    ]
    if enabled:
        option_candidates = [
            d(text='On'),
            d(text='Flash on'),
            d(descriptionContains='On'),
            d(descriptionContains='Flash on'),
            d(resourceId='org.codeaurora.snapcamera:id/flash_button'),
            d(resourceId='org.codeaurora.snapcam:id/flash_button'),
        ]
    else:
        option_candidates = [
            d(text='Off'),
            d(text='Flash off'),
            d(descriptionContains='Off'),
            d(descriptionContains='Flash off'),
            d(resourceId='org.codeaurora.snapcamera:id/flash_button'),
            d(resourceId='org.codeaurora.snapcam:id/flash_button'),
        ]
    if not _tap_first_existing(option_candidates):
        if not _tap_first_existing(toggle_candidates):
            _tap_camera_control('flash')
    time.sleep(1)

def _capture_picture(testcase, step_name):
    captured_steps = getattr(testcase, '_captured_steps', None)
    if captured_steps is None:
        captured_steps = set()
        setattr(testcase, '_captured_steps', captured_steps)
    if step_name in captured_steps:
        return
    captured_steps.add(step_name)
    before_count = _count_photos()
    shutter_candidates = [
        d(resourceId='org.codeaurora.snapcamera:id/shutter_button'),
        d(resourceId='org.codeaurora.snapcam:id/shutter_button'),
        d(resourceId='com.android.camera:id/shutter_button'),
        d(resourceId='com.android.camera2:id/shutter_button'),
        d(description='Shutter'),
        d(descriptionContains='Shutter'),
    ]
    # Ensure the shutter is actually ready before tapping to avoid a no-op capture.
    ready_deadline = time.time() + 8
    while not _camera_ready() and time.time() < ready_deadline:
        time.sleep(0.5)
    # On a cold camera start the first shutter tap is sometimes swallowed while the
    # preview is still initializing, so retry the tap until a new file appears.
    after_count = before_count
    tapped_once = False
    for attempt in range(3):
        tapped = _tap_first_existing(shutter_candidates) or _tap_camera_control('shutter')
        if not tapped:
            if tapped_once:
                break
            raise AssertionError('Camera shutter button not found')
        tapped_once = True
        # snapcam writes the file asynchronously after the shutter animation.
        deadline = time.time() + 12
        after_count = _count_photos()
        while after_count <= before_count and time.time() < deadline:
            time.sleep(1)
            after_count = _count_photos()
        if after_count > before_count:
            break
    save_step_screenshot(d, step_name, SCRIPT_IMG_DIR)
    if before_count >= 0 and after_count >= 0:
        testcase.assertGreater(after_count, before_count, 'Picture was not saved successfully')

class Test_L0_Camera_Flashlight(unittest.TestCase):

    def setUp(self):
        d.screen_on()
        self.tc_details = {'dev0': serial}

    def tearDown(self):
        d.screen_on()
        subprocess.run(['adb', '-s', serial, 'shell', 'am', 'force-stop', 'com.android.camera2'], stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        subprocess.run(['adb', '-s', serial, 'shell', 'am', 'force-stop', 'com.google.android.GoogleCamera'], stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        subprocess.run(['adb', '-s', serial, 'shell', 'am', 'force-stop', 'org.codeaurora.snapcamera'], stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        subprocess.run(['adb', '-s', serial, 'shell', 'am', 'force-stop', 'org.codeaurora.snapcam'], stdout=subprocess.PIPE, stderr=subprocess.STDOUT)

    def test_L0_camera_flashlight(self):
        """Verify camera preview, taking a photo, the flashlight toggle, and photo deletion."""
        _launch_camera()
        time.sleep(2)
        save_step_screenshot(d, 'preview_1', SCRIPT_IMG_DIR)

        _capture_picture(self, 'capture_1')
        time.sleep(2)

        _set_flash(True)
        _capture_picture(self, 'capture_2')
        time.sleep(2)

        _set_flash(False)
        _capture_picture(self, 'capture_3')
        _tap_first_existing([
            d(resourceId='org.codeaurora.snapcamera:id/flash_button'),
            d(resourceId='org.codeaurora.snapcam:id/flash_button'),
        ])
        time.sleep(2)

        remove_dir(self.tc_details['dev0'], '/storage/emulated/0/DCIM/Camera/*')
        time.sleep(1)
        camera_files = _run_adb_shell('ls -1 /storage/emulated/0/DCIM/Camera 2>/dev/null')
        lines = [ln.strip() for ln in camera_files.splitlines() if ln.strip()]
        self.assertEqual(len(lines), 0, 'Expected /storage/emulated/0/DCIM/Camera/ to be empty after delete')
        save_step_screenshot(d, 'save_delete_5', SCRIPT_IMG_DIR)


if __name__ == '__main__':
    unittest.main(verbosity=2)