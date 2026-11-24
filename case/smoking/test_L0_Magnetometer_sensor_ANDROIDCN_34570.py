# -*- coding:utf-8 -*-
"""
Test case: ANDROIDCN-34570 - Magnetometer sensor validation.

Test Steps:
1. Locate an approved Android Sensor Box APK in `files/apps` and install or update
	it on the connected device.
2. Wake and unlock the device, launch Sensor Box, and open the Magnetometer page.
3. Capture evidence and verify that the page does not report an unsupported,
	unavailable, or error state.
4. Verify the page contains an expected magnetic-sensor indicator or measurement
	marker, confirming that the magnetometer is available to the application.
"""

import os
import subprocess
import sys
import time
import unittest

try:
	import uiautomator2 as u2
except ImportError:
	print("[ERROR] uiautomator2 not installed. Install with: pip install uiautomator2")
	sys.exit(1)

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.realpath(__file__))))
if ROOT_DIR not in sys.path:
	sys.path.insert(0, ROOT_DIR)

from common.adb_common import get_device_serial, save_step_screenshot
from common.common_method import (
	CounterUiLifecycle,
	disable_play_protect_app_scanning,
	enable_play_protect_app_scanning,
)


serial = get_device_serial()
device = None

APK_CANDIDATES = [
	os.path.join(ROOT_DIR, "files", "apps", "AndroidSensorBox.apk"),
	os.path.join(ROOT_DIR, "files", "apps", "Sensor Box for Android_v6.93_apkpure.com.apk"),
]

SCRIPT_BASENAME = os.path.splitext(os.path.basename(__file__))[0]
IMG_ROOT = os.path.join(ROOT_DIR, "img")
SCRIPT_IMG_DIR = os.path.join(IMG_ROOT, SCRIPT_BASENAME)
os.makedirs(SCRIPT_IMG_DIR, exist_ok=True)

APP_COMPONENT = "imoblife.androidsensorbox/.SplashActivity"
APP_PACKAGE = "imoblife.androidsensorbox"


def init_device():
	"""初始化 UIAutomator2 设备连接。"""
	global device
	if device is None:
		device = u2.connect(serial)
	return device


def resolve_apk_path():
	"""返回首个存在的 Sensor Box 安装包路径。"""
	for path in APK_CANDIDATES:
		if os.path.exists(path):
			return path
	return None


class SensorBoxUiLifecycle(CounterUiLifecycle):
	"""复用 Counter 的界面安装流程(含 Play Protect 的 Install anyway)安装 Sensor Box。"""

	app_package = APP_PACKAGE
	apk_filename = "SensorBox.apk"  # 设备端文件名不含空格，便于 adb rm
	device_apk_path = "/sdcard/Download/SensorBox.apk"

	def _click_install(self, timeout):
		clicked = super()._click_install(timeout)
		if not clicked:
			return False
		# Play Protect 扫描需数秒才弹出 Unsafe app blocked，基类仅等 1 秒
		deadline = time.time() + 12
		while time.time() < deadline:
			if self._wait_for_package(True, 1) or self._text_visible(("App installed.", "App installed"), 0.1):
				break
			if self._accept_play_protect_warning_if_needed(1):
				break
		return True


def install_android_sensor_box_apk(test_case):
	"""测试步骤1: 通过界面安装 Sensor Box APK。"""
	if not serial:
		print("[FAIL] No Android device found. Connect a device or set ANDROID_SERIAL.")
		return False

	apk_path = resolve_apk_path()
	if not apk_path:
		print("[FAIL] APK file not found. Checked:")
		for candidate in APK_CANDIDATES:
			print(f"[FAIL]   - {candidate}")
		return False

	print("\n[TEST] Step 1: Install AndroidSensorBox.apk from files/apps/")
	print(f"[INFO] Device: {serial}")
	print(f"[INFO] APK: {apk_path}")

	lifecycle = SensorBoxUiLifecycle(test_case, serial, apk_path, SCRIPT_IMG_DIR)
	test_case.addCleanup(lifecycle.remove_downloaded_apk)
	# 关闭 Play Protect 扫描后安装不再弹 Unsafe app blocked
	device.press("home")
	if disable_play_protect_app_scanning(device):
		print("[INFO] Play Protect app scanning is disabled")
	else:
		print("[WARN] Play Protect configuration unavailable; continuing installation flow")
	test_case.addCleanup(enable_play_protect_app_scanning, device)
	device.press("home")
	try:
		lifecycle.ensure_installed()
	except AssertionError as e:
		print(f"[FAIL] Step 1 failed: Sensor Box installation failed: {e}")
		return False

	print("[PASS] Step 1 completed: Sensor Box installed successfully")
	return True


def open_sensor_box_and_check_magnetometer():
	"""测试步骤2: 打开 Sensor Box，进入 Magnetometer 并检查状态。"""
	if not serial:
		print("[FAIL] No Android device found. Connect a device or set ANDROID_SERIAL.")
		return False

	init_device()

	print("\n[TEST] Step 2: Open Sensor Box app, find Magnetometer, and verify status")
	print(f"[INFO] Device: {serial}")

	try:
		device.screen_on()
		device.unlock()
	except Exception:
		pass

	try:
		subprocess.run(
			["adb", "-s", serial, "shell", "am", "start", "-n", APP_COMPONENT],
			capture_output=True,
			text=True,
			timeout=20,
			check=False,
		)
		time.sleep(8)
	except Exception as e:
		print(f"[FAIL] Failed to launch Sensor Box app: {e}")
		save_step_screenshot(device, "step2_launch_sensor_box_failed", SCRIPT_IMG_DIR)
		return False

	try:
		# 进入 Magnetometer 页面：入口图标(iv_magn)才是可点击对象，下方文字仅为标签不可点击
		mag_clicked = False
		icon_selector = device(resourceId=f"{APP_PACKAGE}:id/iv_magn")
		label_selector = device(textMatches=r"(?i)magnet")

		if icon_selector.exists(timeout=6):
			icon_selector.click()
			mag_clicked = True
		elif device(text="Magnetometer").exists(timeout=2):
			device(text="Magnetometer").click()
			mag_clicked = True
		elif label_selector.exists(timeout=2):
			# 兜底: 文字标签不可点击，点击其正上方的图标区域
			label_bounds = label_selector.info.get("bounds", {})
			label_top = label_bounds.get("top")
			label_left = label_bounds.get("left")
			label_right = label_bounds.get("right")
			if label_top and label_left is not None and label_right is not None:
				device.click((label_left + label_right) // 2, max(label_top - 100, 0))
				mag_clicked = True

		if not mag_clicked:
			print("[FAIL] Magnetometer entry not found in Sensor Box app")
			save_step_screenshot(device, "step2_magnetometer_entry_not_found", SCRIPT_IMG_DIR)
			return False

		time.sleep(2)
		save_step_screenshot(device, "step2_magnetometer_opened", SCRIPT_IMG_DIR)

		hierarchy = device.dump_hierarchy()
		lower_hierarchy = hierarchy.lower()

		# 出现不支持类提示则判失败
		negative_keywords = ["not supported", "unsupported", "not available", "error"]
		for kw in negative_keywords:
			if kw in lower_hierarchy:
				print(f"[FAIL] Magnetometer page shows abnormal status: {kw}")
				save_step_screenshot(device, "step2_magnetometer_abnormal_status", SCRIPT_IMG_DIR)
				return False

		# 正常判定: 页面中可见 Magnetic Sensor 标题及 μT 单位读数
		positive_markers = ["magnetic sensor", "μt", "hardware info"]
		marker_hit = any(marker in lower_hierarchy for marker in positive_markers)

		if not marker_hit:
			print("[FAIL] Magnetometer page opened but no valid sensor markers were detected")
			save_step_screenshot(device, "step2_magnetometer_markers_missing", SCRIPT_IMG_DIR)
			return False

		print("[PASS] Step 2 completed: Magnetometer is visible and status looks normal")
		save_step_screenshot(device, "step2_magnetometer_verified", SCRIPT_IMG_DIR)
		return True
	except Exception as e:
		print(f"[FAIL] Exception during Magnetometer validation: {e}")
		save_step_screenshot(device, "step2_magnetometer_exception", SCRIPT_IMG_DIR)
		return False
	finally:
		try:
			subprocess.run(
				["adb", "-s", serial, "shell", "am", "force-stop", APP_PACKAGE],
				capture_output=True,
				text=True,
				timeout=10,
				check=False,
			)
		except Exception:
			pass


class Test_Magnetometer_Sensor(unittest.TestCase):
	"""L0 Magnetometer Sensor smoke test."""

	@classmethod
	def setUpClass(cls):
		if not serial:
			raise RuntimeError("No Android device found. Connect one device or set ANDROID_SERIAL.")
		init_device()

	def test_L0_magnetometer_sensor(self):
		"""
		Test Steps:
		1. Locate and install the supported Android Sensor Box APK from `files/apps`.
		2. Launch Sensor Box and open the Magnetometer page.
		3. Capture the page and verify it has no unsupported, unavailable, or error state.
		4. Verify a magnetic-sensor indicator or measurement marker is displayed.
		"""
		self.device = init_device()
		self.assertTrue(
			install_android_sensor_box_apk(self),
			"Failed to install AndroidSensorBox.apk from files/apps/",
		)
		
		self.assertTrue(
			open_sensor_box_and_check_magnetometer(),
			"Failed to open Sensor Box or verify Magnetometer status",
		)


if __name__ == '__main__':
	unittest.main(verbosity=2)
