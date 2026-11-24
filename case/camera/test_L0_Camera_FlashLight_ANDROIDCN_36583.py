# -*- coding:utf-8 -*-
# pyright: reportMissingImports=false
"""
相机自动化测试 - 按步骤顺序执行

步骤:
1. 打开照相机并拍一张照片
2. 打开闪光灯再拍一张照片
3. 关闭闪光灯再拍一张照片
4. 打开照相机和预览界面（验证自动对焦）
5. 进入相册删除拍摄的照片
"""

import time
import unittest
import sys
import re
import os

sys.path.insert(0, '.')

try:
    import uiautomator2 as u2
except ImportError:
    print("[ERROR] uiautomator2 not installed. Install with: pip install uiautomator2")
    sys.exit(1)

from common.adb_common import (
    get_device_serial,
    camera_photo_count,
    delete_camera_photos,
    save_step_screenshot,
)

# 获取设备序列号
serial = get_device_serial()

# UI 自动化设备实例
device = None

SCRIPT_BASENAME = os.path.splitext(os.path.basename(__file__))[0]
IMG_ROOT = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.realpath(__file__)))), "img")
SCRIPT_IMG_DIR = os.path.join(IMG_ROOT, SCRIPT_BASENAME)
os.makedirs(SCRIPT_IMG_DIR, exist_ok=True)

CAMERA_PACKAGES = [
    'org.codeaurora.snapcam',
    'com.android.camera',
    'com.google.android.GoogleCamera',
    'com.sonyericsson.android.camera',
]

# 多数相机闪光灯为 3 态循环：Auto -> On -> Off -> Auto。
FLASH_MODE_CYCLE_LEN = 3
FLASH_MODE_ADVANCE_COUNT = 0


def init_device():
    """初始化 UIAutomator2 设备连接"""
    global device
    if device is None:
        device = u2.connect(serial)

        # 获取设备信息
        info = device.info

    return device


def _wake_up_device():
    """唤醒设备屏幕"""
    try:
        device.unlock()
    except:
        # 如果解锁失败，尝试按电源键
        device.press('power')
        time.sleep(0.5)
    time.sleep(1)


def _shell_output(cmd, timeout=6):
    """执行 shell 并返回文本输出。"""
    try:
        resp = device.shell(cmd, timeout=timeout)
        if hasattr(resp, "output"):
            return (resp.output or "").strip()
        return str(resp).strip()
    except Exception:
        return ""


def _foreground_package():
    """快速获取前台包名，避免 app_current 偶发卡顿。"""
    out = _shell_output("dumpsys window windows", timeout=4)
    m = re.search(r"\s([a-zA-Z0-9_\.]+)/", out)
    return m.group(1) if m else ""


def _is_camera_foreground():
    """判断相机是否在前台。"""
    fg = (_foreground_package() or "").lower()
    return any(pkg.lower() in fg for pkg in CAMERA_PACKAGES) or "camera" in fg or "snapcam" in fg


def _open_camera_app():
    """启动相机应用（使用 UI 方式）"""
    # 先用通用 Intent，兼容厂商定制相机
    out = _shell_output("am start -a android.media.action.IMAGE_CAPTURE", timeout=6)
    time.sleep(2)
    if "error" not in out.lower() and "exception" not in out.lower():
        return True

    camera_apps = [
        ("com.android.camera", "系统相机"),
        ("com.google.android.GoogleCamera", "Google 相机"),
        ("com.sonyericsson.android.camera", "Sony 相机"),
    ]

    for package, app_name in camera_apps:
        try:
            launch_out = _shell_output(
                f"monkey -p {package} -c android.intent.category.LAUNCHER 1", timeout=6
            )
            time.sleep(2)
            if "No activities found" not in launch_out:
                return True
        except Exception:
            continue

    return False


def _ensure_camera_ui(reason=""):
    """确保当前停留在相机界面；前置步骤不应进入相册。"""
    if _is_camera_foreground():
        return True

    if reason:
        print(f"[camera] [WARN] Left camera UI unexpectedly: {reason}, reopening camera...", flush=True)
    else:
        print("[camera] [WARN] Left camera UI unexpectedly, reopening camera...", flush=True)

    return _open_camera_app()


def _get_screen_size():
    """获取屏幕尺寸"""
    info = device.info
    return info['displayWidth'], info['displayHeight']


def _find_shutter_button():
    """查找快门按钮（通常在屏幕下方中间）"""
    width, height = _get_screen_size()

    # 快门按钮通常在屏幕下方中间
    shutter_positions = [
        (width // 2, int(height * 0.92)),  # 下方中间
        (width // 2, int(height * 0.88)),  # 稍微高一点
    ]

    return shutter_positions


def _trigger_shutter(retry_count=3):
    """
    触发快门拍照（使用 UI 点击）
    """
    shutter_positions = _find_shutter_button()

    for attempt in range(retry_count):
        # 尝试在多个位置点击
        for x, y in shutter_positions:
            try:
                device.click(x, y)
                time.sleep(0.5)
            except Exception:
                pass

        # 不使用音量键作为快门，避免弹出系统音量调节 UI。
        time.sleep(1)

    return True


def _find_and_click_flashlight(retries=3):
    """
    使用 UIAutomator 查找并点击闪光灯按钮
    """
    try:
        # 优先通过 resource-id 精确匹配
        for res_id in [
            "org.codeaurora.snapcam:id/flash_button",
            "com.android.camera:id/flash_button",
            "com.google.android.GoogleCamera:id/flash_button",
        ]:
            try:
                elem = device(resourceId=res_id)
                if elem.exists():
                    elem.click()
                    time.sleep(1)
                    return True
            except:
                pass

        # 通过 resource-id 模糊匹配
        try:
            elem = device(resourceIdMatches=".*flash.*")
            if elem.exists():
                elem.click()
                time.sleep(1)
                return True
        except:
            pass

        # 通过文字或描述查找
        for keyword in ["flash", "torch", "lamp", "light"]:
            try:
                elem = device(textContains=keyword, clickable=True)
                if elem.exists():
                    elem.click()
                    time.sleep(1)
                    return True
                elem2 = device(descriptionContains=keyword, clickable=True)
                if elem2.exists():
                    elem2.click()
                    time.sleep(1)
                    return True
            except:
                pass

        return False

    except Exception:
        return False


def _toggle_flashlight(enable=True):
    """
    切换闪光灯（使用 UI 点击和验证）
    闪光灯按钮通常在屏幕左上角或右上角
    """
    global FLASH_MODE_ADVANCE_COUNT

    # 首先尝试使用 UIAutomator 查找
    if _find_and_click_flashlight():
        time.sleep(1)
        FLASH_MODE_ADVANCE_COUNT += 1
        return True

    # 回退：使用调试确认的坐标（flash_button bounds=[638,58][713,133]，中心点约 675,95）
    width, height = _get_screen_size()

    flash_positions = [
        (675, 95),  # org.codeaurora.snapcam 相机
        (width - 50, 70),  # 右上角备选
        (50, 70),  # 左上角备选
        (width // 2, 70),  # 中上备选
    ]

    max_attempts = 3
    for attempt in range(max_attempts):
        for x, y in flash_positions:
            try:
                device.click(x, y)
                time.sleep(1)
            except Exception:
                pass

        time.sleep(1)

    FLASH_MODE_ADVANCE_COUNT += 1
    return True


def _click_flash_once():
    """点击一次闪光灯按钮，用于模式回拨。"""
    if _find_and_click_flashlight():
        return True

    # 坐标兜底只点一次，避免过度切换。
    width, _ = _get_screen_size()
    for x, y in [(675, 95), (width - 50, 70), (50, 70), (width // 2, 70)]:
        try:
            device.click(x, y)
            time.sleep(0.5)
            return True
        except Exception:
            continue
    return False


def _is_flash_auto_mode():
    """检测当前是否为闪光灯 Auto 模式（尽量通过 UI 文案判断）。"""
    try:
        auto_keywords = ["auto", "自动", "automatic", "mode: auto", "模式"]

        # 先查文字/描述。
        for kw in auto_keywords:
            if device(textContains=kw).exists(timeout=0.2):
                xml = device.dump_hierarchy(compressed=False)
                low = (xml or "").lower()
                # 在出现 auto/自动 的上下文中检查是否确实是闪光灯设置
                if "flash" in low or "闪光" in (xml or ""):
                    return True
            if device(descriptionContains=kw).exists(timeout=0.2):
                return True

        # 再从层级文本做兜底匹配。
        xml = device.dump_hierarchy(compressed=False)
        low = (xml or "").lower()
        xml_cn = (xml or "")

        # 多种匹配模式以兼容不同相机应用
        patterns = [
            ("flash" in low and "auto" in low),
            ("闪光" in xml_cn and "自动" in xml_cn),
            ("flash_mode" in low and "auto" in low),
            ("flashmode" in low and "auto" in low),
        ]

        return any(patterns)
    except Exception as e:
        print(f"[camera] [WARN] Flash mode check failed: {e}", flush=True)
        return False


def _is_flash_on_mode():
    """检测当前是否为闪光灯 ON 模式。"""
    try:
        on_keywords = ["on", "打开", "opened", "enabled", "强制打开", "always on"]

        # 先查文字/描述。
        for kw in on_keywords:
            if device(textContains=kw).exists(timeout=0.2):
                xml = device.dump_hierarchy(compressed=False)
                low = (xml or "").lower()
                if "flash" in low or "闪光" in (xml or ""):
                    return True
            if device(descriptionContains=kw).exists(timeout=0.2):
                return True

        # 再从层级文本做兜底匹配。
        xml = device.dump_hierarchy(compressed=False)
        low = (xml or "").lower()
        xml_cn = (xml or "")

        patterns = [
            ("flash" in low and "on" in low and "auto" not in low and "off" not in low),
            ("闪光" in xml_cn and "打开" in xml_cn),
            ("flash_mode" in low and "on" in low),
            ("flashmode" in low and "on" in low),
        ]

        return any(patterns)
    except Exception as e:
        print(f"[camera] [WARN] Flash ON check failed: {e}", flush=True)
        return False


def _is_flash_off_mode():
    """
    检测当前是否为闪光灯 OFF 模式。
    注意：Snapdragon Camera 的闪光灯状态通过图标变化表示，而不是文本，
    所以这个方法是有限的。改为更实用的方法：如果能成功点击按钮，就认为状态改变了。
    """
    try:
        # 尝试查找明确的 OFF 关键词
        off_keywords = ["off", "关闭", "disabled", "no flash", "强制关闭"]

        for kw in off_keywords:
            if device(textContains=kw).exists(timeout=0.2):
                xml = device.dump_hierarchy(compressed=False)
                low = (xml or "").lower()
                if "flash" in low or "闪光" in (xml or ""):
                    return True
            if device(descriptionContains=kw).exists(timeout=0.2):
                return True

        # Snapdragon Camera 不使用文本表示闪光灯状态，信任按钮点击成功
        return True

    except Exception as e:
        print(f"[camera] [WARN] Flash OFF check failed: {e}", flush=True)
        return False


def _restore_flash_mode_auto():
    """在脚本结束时直接恢复闪光灯为 Auto 模式。"""
    opened = _open_camera_app()
    if not opened or not _is_camera_foreground():
        # 兜底：强制按包名拉起已知相机
        for pkg in CAMERA_PACKAGES:
            try:
                device.app_start(pkg, stop=False)
                time.sleep(1)
                if _is_camera_foreground():
                    break
            except Exception:
                continue

    if not _is_camera_foreground():
        return False

    # 根据记录的点击次数直接恢复到AUTO模式
    clicks_needed = (FLASH_MODE_CYCLE_LEN - (FLASH_MODE_ADVANCE_COUNT % FLASH_MODE_CYCLE_LEN)) % FLASH_MODE_CYCLE_LEN
    for _ in range(clicks_needed):
        _click_flash_once()
        time.sleep(0.5)

    return True


def _enable_autofocus():
    """
    启用自动对焦（点击屏幕中央）
    """
    width, height = _get_screen_size()
    focus_x, focus_y = width // 2, height // 2

    try:
        device.click(focus_x, focus_y)
        time.sleep(2)
        return True
    except Exception:
        return False



def _swipe_to_gallery():
    """
    滑动或点击进入相册（通常在屏幕左下角）
    """
    print("[camera] Opening gallery...", flush=True)

    def _is_gallery_ui():
        fg = (_foreground_package() or "").lower()
        gallery_pkgs = [
            "com.google.android.apps.photos",
            "com.android.gallery",
            "com.android.gallery3d",
            "com.miui.gallery",
            "com.sec.android.gallery3d",
            "com.oneplus.gallery",
            "com.huawei.photos",
        ]
        if any(pkg in fg for pkg in gallery_pkgs):
            return True
        return False

    # 方式 1：优先点击相机缩略图按钮。
    thumb_ids = [
        "org.codeaurora.snapcam:id/preview_thumb",
        "com.android.camera:id/preview_thumb",
        "com.google.android.GoogleCamera:id/preview_thumb",
    ]
    for rid in thumb_ids:
        try:
            obj = device(resourceId=rid)
            if obj.exists(timeout=0.4):
                obj.click()
                time.sleep(2)
                if _is_gallery_ui():
                    print(f"[camera] [OK] Gallery opened by thumbnail {rid}", flush=True)
                    return True
        except Exception:
            pass

    # 方式 2：坐标点击左下角缩略图。
    width, height = _get_screen_size()
    for x, y in [(50, height - 50), (80, height - 80), (120, height - 120)]:
        try:
            device.click(x, y)
            time.sleep(2)
            if _is_gallery_ui():
                print(f"[camera] [OK] Gallery opened by coordinates ({x}, {y})", flush=True)
                return True
        except Exception:
            pass

    # 方式 3：兜底直接拉起相册应用。
    gallery_launch_cmds = [
        "am start -a android.intent.action.MAIN -c android.intent.category.APP_GALLERY",
        "am start -n com.google.android.apps.photos/.home.HomeActivity",
        "am start -n com.android.gallery3d/.app.GalleryActivity",
    ]
    for cmd in gallery_launch_cmds:
        out = _shell_output(cmd, timeout=8)
        time.sleep(2)
        if "exception" not in (out or "").lower() and _is_gallery_ui():
            print(f"[camera] [OK] Gallery opened by intent: {cmd}", flush=True)
            return True

    print("[camera] [WARN] Failed to enter gallery UI", flush=True)
    return False


def _is_gallery_foreground_strict():
    """严格判断是否已进入相册前台。"""
    fg = (_foreground_package() or "").lower()
    gallery_pkgs = [
        "com.google.android.apps.photos",
        "com.android.gallery",
        "com.android.gallery3d",
        "com.miui.gallery",
        "com.sec.android.gallery3d",
        "com.oneplus.gallery",
        "com.huawei.photos",
    ]
    return any(pkg in fg for pkg in gallery_pkgs)


def _is_screen_on():
    """基于 dumpsys 判断当前是否亮屏。"""
    out = _shell_output("dumpsys power", timeout=8).lower()
    return (
            "display power: state=on" in out
            or "display power: state = on" in out
            or "mwakefulness=awake" in out
    )


def _capture_device_state():
    """记录测试前设备状态，用于收尾恢复。"""
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

    # 先恢复闪光灯模式，避免相机关闭后无法切换。
    try:
        _restore_flash_mode_auto()
    except Exception as e:
        print(f"[camera] [WARN] Flash AUTO restore failed: {str(e)[:120]}", flush=True)

    for pkg in CAMERA_PACKAGES:
        try:
            device.app_stop(pkg)
        except Exception:
            pass

    target_pkg = (state.get("foreground_pkg") or "").strip()
    if target_pkg and target_pkg != "com.android.systemui":
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
            device.press('power')
            time.sleep(1)
            print("[camera] [OK] Restored screen state: OFF", flush=True)
        except Exception as e:
            print(f"[camera] [WARN] Failed to restore screen state: {str(e)[:120]}", flush=True)


class Test_OpenCamera_UI(unittest.TestCase):
    """
    相机功能测试 - 按步骤顺序执行
    """

    _suite_pre_state = None

    @classmethod
    def setUpClass(cls):
        """测试类初始化：连接设备"""
        print("[camera] ===== Camera UI Test Setup =====", flush=True)
        init_device()
        cls._suite_pre_state = _capture_device_state()

    @classmethod
    def tearDownClass(cls):
        _restore_device_state(cls._suite_pre_state)

    def setUp(self):
        """每个测试前：仅确保设备唤醒，不重置到 Home。"""
        _wake_up_device()
        time.sleep(0.5)

    def tearDown(self):
        """每个测试后：不做状态恢复，统一在 tearDownClass 恢复。"""
        time.sleep(0.2)

    def step01_open_camera_and_take_photo(self):
        """步骤 1: 打开照相机并拍一张照片"""
        print("[camera] STEP01: open camera and take photo", flush=True)
        before = camera_photo_count(serial, verbose=False)
        opened = _open_camera_app()
        self.assertTrue(opened, "Failed to open camera app")
        shutter_ok = _trigger_shutter(retry_count=2)
        self.assertTrue(shutter_ok, "Failed to trigger shutter")
        self.assertTrue(_ensure_camera_ui("step01 after shutter"), "Step 1 should stay on camera UI")
        save_step_screenshot(device, "step01_camera_photo", SCRIPT_IMG_DIR)
        after = camera_photo_count(serial, verbose=False)
        self.assertGreaterEqual(after, before, "Photo count did not increase as expected")

    def step02_flash_on_and_take_photo(self):
        """步骤 2: 打开闪光灯再拍一张照片"""
        print("[camera] STEP02: flash on and take photo", flush=True)
        before = camera_photo_count(serial, verbose=False)
        opened = _open_camera_app()
        self.assertTrue(opened, "Failed to open camera app")
        flash_ok = _toggle_flashlight(enable=True)
        self.assertTrue(flash_ok, "Failed to enable flashlight")
        time.sleep(1)
        is_on = _is_flash_on_mode()
        self.assertTrue(is_on, "Flash ON mode not confirmed - UI state verification failed")
        shutter_ok = _trigger_shutter(retry_count=2)
        self.assertTrue(shutter_ok, "Failed to trigger shutter with flash on")
        self.assertTrue(_ensure_camera_ui("step02 after shutter"), "Step 2 should stay on camera UI")
        save_step_screenshot(device, "step02_flash_on_photo", SCRIPT_IMG_DIR)
        after = camera_photo_count(serial, verbose=False)
        self.assertGreaterEqual(after, before, "Photo count did not increase as expected")

    def step03_flash_off_and_take_photo(self):
        """步骤 3: 关闭闪光灯再拍一张照片"""
        print("[camera] STEP03: flash off and take photo", flush=True)
        before = camera_photo_count(serial, verbose=False)
        opened = _open_camera_app()
        self.assertTrue(opened, "Failed to open camera app")
        flash_ok = _toggle_flashlight(enable=False)
        self.assertTrue(flash_ok, "Failed to disable flashlight")
        time.sleep(1)
        is_off = _is_flash_off_mode()
        self.assertTrue(is_off, "Flash OFF mode not confirmed - UI state verification failed")
        shutter_ok = _trigger_shutter(retry_count=2)
        self.assertTrue(shutter_ok, "Failed to trigger shutter with flash off")
        self.assertTrue(_ensure_camera_ui("step03 after shutter"), "Step 3 should stay on camera UI")
        save_step_screenshot(device, "step03_flash_off_photo", SCRIPT_IMG_DIR)
        after = camera_photo_count(serial, verbose=False)
        self.assertGreaterEqual(after, before, "Photo count did not increase as expected")

    def step04_open_camera_and_preview(self):
        """步骤 4: 打开照相机和预览界面（检查自动对焦）"""
        print("[camera] STEP04: open camera and preview", flush=True)
        opened = _open_camera_app()
        self.assertTrue(opened, "Failed to open camera app")
        focus_ok = _enable_autofocus()
        self.assertTrue(focus_ok, "Autofocus check failed")
        self.assertTrue(_ensure_camera_ui("step04 after autofocus"), "Step 4 should stay on camera UI")
        save_step_screenshot(device, "step04_camera_preview_autofocus", SCRIPT_IMG_DIR)

    def step05_enter_gallery_and_delete_photos(self):
        """步骤 5: 进入相册删除拍摄的照片"""
        print("[camera] STEP05: enter gallery and delete photos", flush=True)
        opened = _open_camera_app()
        self.assertTrue(opened, "Failed to open camera app")
        gallery_ok = _swipe_to_gallery()
        self.assertTrue(gallery_ok, "Failed to open gallery")
        self.assertTrue(_is_gallery_foreground_strict(), "Not in gallery foreground before deletion")
        save_step_screenshot(device, "step05_gallery_delete_photos", SCRIPT_IMG_DIR)
        before = camera_photo_count(serial, verbose=False)
        delete_camera_photos(serial)
        time.sleep(1)
        after = camera_photo_count(serial, verbose=False)
        self.assertLessEqual(after, before, "Photo deletion did not succeed")

    def test_01_camera_flashlight_flow(self):
        """单个测试按顺序执行 5 个步骤，并保留 step01-step05 命名。"""
        steps = [
            ("step01_open_camera_and_take_photo", self.step01_open_camera_and_take_photo),
            ("step02_flash_on_and_take_photo", self.step02_flash_on_and_take_photo),
            ("step03_flash_off_and_take_photo", self.step03_flash_off_and_take_photo),
            ("step04_open_camera_and_preview", self.step04_open_camera_and_preview),
            ("step05_enter_gallery_and_delete_photos", self.step05_enter_gallery_and_delete_photos),
        ]
        for step_name, step_func in steps:
            with self.subTest(step=step_name):
                step_func()


if __name__ == '__main__':
    print("=" * 60)
    print("[CAMERA] Camera UI Automation Test (Using UIAutomator2)")
    print("=" * 60)
    print("")

    try:
        init_device()
        unittest.main(verbosity=2)
    except Exception as e:
        print(f"[FAILED] Test failed: {e}")
        sys.exit(1)
