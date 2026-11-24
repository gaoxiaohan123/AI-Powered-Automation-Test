# -*- coding: utf-8 -*-
# __author__ = 'sophy_H400818'

"""
Test case: L2 Key Remap - APP_SWITCH -> COMMAND

Steps:
1. Install files/apps/LockAction-signed.apk.
2. Open Keyremap, tap '+', capture App Switch, then select COMMAND.
3. Enter the configured command and save the mapping.
4. Return to Home and press Appswitch.
5. Verify LockAction is foregrounded.
6. Edit the saved mapping with the configured broadcast command.
7. Press Appswitch and verify LockAction displays the broadcast result.
8. Edit the saved mapping with the configured service command.
9. Press Appswitch and verify LockAction displays the service result.
10. Edit the saved mapping with the configured URL view command.
11. Press Appswitch and verify the requested website is displayed.

Author: Sophy H400818
Date: 2026-09-04
"""

import os
import sys
import time
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import uiautomator2 as u2

from common.adb_common import (
	get_device_serial,
	keyremap_click_virtual_appswitch,
	keyremap_force_stop_honeywell_settings,
	keyremap_install_app,
	keyremap_is_on_home_screen,
	keyremap_tap_navbar_appswitch,
	keyremap_uninstall_app,
	keyremap_wait_app_foreground,
	press_home_key,
	run_adb_cmd,
	save_step_screenshot,
)
from common.common_method import (
	close_settings_app,
	disable_play_protect_app_scanning,
	dismiss_chrome_first_run_prompts,
	enable_play_protect_app_scanning,
	get_case_config,
	get_package_name,
	keyremap_clear_all,
	keyremap_dialog_is_open,
	keyremap_find_text_center,
	keyremap_input_text_value,
	keyremap_open_page,
	keyremap_tap_add_button,
	keyremap_tap_ok_button,
	keyremap_tap_text,
)

serial = get_device_serial()
if not serial:
	print("Error: No Android device found. Connect a device or set ANDROID_SERIAL.")
	sys.exit(1)

d = u2.connect(serial)

SCRIPT_BASENAME = os.path.splitext(os.path.basename(__file__))[0]
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.realpath(__file__))))
SCRIPT_IMG_DIR = os.path.join(PROJECT_ROOT, "img", SCRIPT_BASENAME)
os.makedirs(SCRIPT_IMG_DIR, exist_ok=True)

SETTINGS_PKG = get_package_name("settings")
KEYREMAP_PKG = get_package_name("keyremap")
CASE_CONFIG_SECTION = "keyremap_command_case"
APK_FILE_NAME = get_case_config(CASE_CONFIG_SECTION, "apk_file_name")
APK_PATH = os.path.join(PROJECT_ROOT, "files", "apps", APK_FILE_NAME)
APP_PACKAGE = get_case_config(CASE_CONFIG_SECTION, "app_package")
REMAP_COMMAND = get_case_config(CASE_CONFIG_SECTION, "remap_command")
BROADCAST_COMMAND = get_case_config(CASE_CONFIG_SECTION, "broadcast_command")
BROADCAST_RECEIVED_TEXT = get_case_config(CASE_CONFIG_SECTION, "broadcast_received_text")
SERVICE_COMMAND = get_case_config(CASE_CONFIG_SECTION, "service_command")
SERVICE_STARTED_TEXT = get_case_config(CASE_CONFIG_SECTION, "service_started_text")
VIEW_COMMAND = get_case_config(CASE_CONFIG_SECTION, "view_command")
VIEW_URL = get_case_config(CASE_CONFIG_SECTION, "view_url")


class TestKeyremapAppSwitchToCommand(unittest.TestCase):
	"""L2 test for Honeywell Keyremap: APP_SWITCH remapped to a shell command."""

	@classmethod
	def setUpClass(cls):
		cls.dev_id = serial
		print(f"\n[Setup] Device: {cls.dev_id}")

	def setUp(self):
		print(f"\n{'=' * 60}\nTest: {self.id()}\n{'=' * 60}")
		d.press("home")
		time.sleep(1)

	def tearDown(self):
		run_adb_cmd(serial, f"shell am force-stop {APP_PACKAGE}", log_print=False)

		if keyremap_open_page(d, serial, SETTINGS_PKG, KEYREMAP_PKG):
			keyremap_clear_all(d, serial)
			run_adb_cmd(serial, "shell input keyevent KEYCODE_BACK", log_print=False)

		keyremap_force_stop_honeywell_settings(serial)
		close_settings_app(serial)
		keyremap_uninstall_app(serial, APP_PACKAGE)
		
		if enable_play_protect_app_scanning(d):
			print("  Play Protect app scanning is enabled")
		else:
			print("  Play Protect app scanning could not be restored")
		run_adb_cmd(serial, "shell am force-stop com.android.vending", log_print=False)
		d.screen_on()
		d.press("home")
		print(f"[TearDown] Completed: {self.id()}")

	def test_keyremap_appswitch_to_command(self):
		"""
		L2 Keyremap end-to-end test: APP_SWITCH -> COMMAND.
		Step 1: Install LockAction and map APP_SWITCH to its activity command;
				press App Switch and verify the app opens.
		Step 2: Update the mapping to a broadcast command, press App Switch, and
				verify the broadcast result in LockAction.
		Step 3: Update the mapping to a service command, press App Switch, and
				verify the service result.
		Step 4: Update the mapping to a URL view command, press App Switch, and
				verify the requested web page is displayed.
		"""
		print("\n[L2_Keyremap] Testing APP_SWITCH -> COMMAND\n" + "=" * 60)

		if disable_play_protect_app_scanning(d):
			print("  Play Protect app scanning is disabled")
		else:
			print("  Play Protect configuration was unavailable; continuing installation flow")

		print(f"\n[Step 1/11] Install '{APK_FILE_NAME}' from files/apps")
		installed, install_output = keyremap_install_app(serial, APK_PATH, APP_PACKAGE)
		if not installed:
			save_step_screenshot(d, "step1_install_failed", SCRIPT_IMG_DIR)
			self.fail(f"Step 1 Failed: could not install {APK_FILE_NAME} ({install_output})")
		save_step_screenshot(d, "step1_app_installed", SCRIPT_IMG_DIR)

		print("\n[Step 2/11] Keyremap: '+' -> App Switch -> OK -> COMMAND")
		if not keyremap_open_page(d, serial, SETTINGS_PKG, KEYREMAP_PKG):
			save_step_screenshot(d, "step2_navigation_failed", SCRIPT_IMG_DIR)
			self.fail("Step 2 Failed: could not navigate to the Keyremap page")

		keyremap_tap_add_button(d, serial)
		if not keyremap_dialog_is_open(d):
			save_step_screenshot(d, "step2_dialog_not_opened", SCRIPT_IMG_DIR)
			self.fail("Step 2 Failed: '+' did not open the key-capture dialog")

		keyremap_click_virtual_appswitch(serial)
		time.sleep(1)
		if not keyremap_tap_ok_button(d, serial):
			save_step_screenshot(d, "step2_capture_not_saved", SCRIPT_IMG_DIR)
			self.fail("Step 2 Failed: could not confirm the App Switch key capture")

		if not keyremap_tap_text(d, serial, "COMMAND", contains=False, max_swipes=10):
			save_step_screenshot(d, "step2_command_not_found", SCRIPT_IMG_DIR)
			self.fail("Step 2 Failed: 'COMMAND' target was not found")

		print(f"\n[Step 3/11] Enter command: {REMAP_COMMAND}")
		if not keyremap_input_text_value(d, KEYREMAP_PKG, REMAP_COMMAND):
			save_step_screenshot(d, "step3_editor_not_found", SCRIPT_IMG_DIR)
			self.fail("Step 3 Failed: COMMAND edit field was not found")
		if not keyremap_tap_ok_button(d, serial):
			save_step_screenshot(d, "step3_command_not_saved", SCRIPT_IMG_DIR)
			self.fail("Step 3 Failed: could not save the COMMAND mapping")
		if keyremap_find_text_center(d, "APP_SWITCH", contains=False) is None:
			save_step_screenshot(d, "step3_entry_not_confirmed", SCRIPT_IMG_DIR)
			self.fail("Step 3 Failed: APP_SWITCH entry was not shown after saving")
		save_step_screenshot(d, "step3_remap_saved", SCRIPT_IMG_DIR)

		print("\n[Step 4/11] Return to Home and press Appswitch")
		press_home_key(serial)
		is_on_home, last_focus = keyremap_is_on_home_screen(serial)
		if not is_on_home:
			save_step_screenshot(d, "step4_not_on_home", SCRIPT_IMG_DIR)
			self.fail(f"Step 4 Failed: could not return to Home (focus={last_focus})")
		keyremap_tap_navbar_appswitch(serial)
		save_step_screenshot(d, "step4_appswitch_pressed", SCRIPT_IMG_DIR)

		print("\n[Step 5/11] Verify LockAction was launched")
		app_shown, focus_info = keyremap_wait_app_foreground(serial, APP_PACKAGE)
		if not app_shown:
			save_step_screenshot(d, "step5_app_not_launched", SCRIPT_IMG_DIR)
			self.fail(
				f"Step 5 Failed: {APP_PACKAGE} was not foregrounded after Appswitch "
				f"(focus={focus_info})"
			)
		save_step_screenshot(d, "step5_app_launched", SCRIPT_IMG_DIR)
		print(f"  App foreground: {APP_PACKAGE}")

		print("\n[Step 6/11] Edit APP_SWITCH mapping -> COMMAND broadcast")
		if not keyremap_open_page(d, serial, SETTINGS_PKG, KEYREMAP_PKG):
			save_step_screenshot(d, "step6_navigation_failed", SCRIPT_IMG_DIR)
			self.fail("Step 6 Failed: could not navigate to the Keyremap page")
		if not keyremap_tap_text(d, serial, "APP_SWITCH", contains=False, max_swipes=10):
			save_step_screenshot(d, "step6_entry_not_found", SCRIPT_IMG_DIR)
			self.fail("Step 6 Failed: saved APP_SWITCH entry was not found")
		time.sleep(1)
		if not keyremap_tap_text(d, serial, "COMMAND", contains=False, max_swipes=10):
			save_step_screenshot(d, "step6_command_not_found", SCRIPT_IMG_DIR)
			self.fail("Step 6 Failed: COMMAND target was not found after opening APP_SWITCH")
		if not keyremap_input_text_value(d, KEYREMAP_PKG, BROADCAST_COMMAND):
			save_step_screenshot(d, "step6_editor_not_found", SCRIPT_IMG_DIR)
			self.fail("Step 6 Failed: COMMAND edit field was not found")
		if not keyremap_tap_ok_button(d, serial):
			save_step_screenshot(d, "step6_broadcast_not_saved", SCRIPT_IMG_DIR)
			self.fail("Step 6 Failed: could not save the broadcast COMMAND mapping")
		save_step_screenshot(d, "step6_broadcast_remap_saved", SCRIPT_IMG_DIR)

		print("\n[Step 7/11] Press Appswitch and verify broadcast receipt")
		press_home_key(serial)
		is_on_home, last_focus = keyremap_is_on_home_screen(serial)
		if not is_on_home:
			save_step_screenshot(d, "step7_not_on_home", SCRIPT_IMG_DIR)
			self.fail(f"Step 7 Failed: could not return to Home (focus={last_focus})")
		keyremap_tap_navbar_appswitch(serial)

		app_shown, focus_info = keyremap_wait_app_foreground(serial, APP_PACKAGE)
		if not app_shown:
			save_step_screenshot(d, "step7_app_not_launched", SCRIPT_IMG_DIR)
			self.fail(
				f"Step 7 Failed: {APP_PACKAGE} was not foregrounded after the broadcast "
				f"Appswitch command (focus={focus_info})"
			)

		broadcast_received = False
		for _ in range(10):
			if d(text=BROADCAST_RECEIVED_TEXT).exists(timeout=1):
				broadcast_received = True
				break
		if not broadcast_received:
			save_step_screenshot(d, "step7_broadcast_not_received", SCRIPT_IMG_DIR)
			self.fail(f"Step 7 Failed: '{BROADCAST_RECEIVED_TEXT}' was not displayed by LockAction")
		save_step_screenshot(d, "step7_broadcast_received", SCRIPT_IMG_DIR)
		print(f"  Broadcast result displayed: {BROADCAST_RECEIVED_TEXT}")

		print("\n[Step 8/11] Edit APP_SWITCH mapping -> COMMAND service")
		if not keyremap_open_page(d, serial, SETTINGS_PKG, KEYREMAP_PKG):
			save_step_screenshot(d, "step8_navigation_failed", SCRIPT_IMG_DIR)
			self.fail("Step 8 Failed: could not navigate to the Keyremap page")
		if not keyremap_tap_text(d, serial, "APP_SWITCH", contains=False, max_swipes=10):
			save_step_screenshot(d, "step8_entry_not_found", SCRIPT_IMG_DIR)
			self.fail("Step 8 Failed: saved APP_SWITCH entry was not found")
		time.sleep(1)
		if not keyremap_tap_text(d, serial, "COMMAND", contains=False, max_swipes=10):
			save_step_screenshot(d, "step8_command_not_found", SCRIPT_IMG_DIR)
			self.fail("Step 8 Failed: COMMAND target was not found after opening APP_SWITCH")
		if not keyremap_input_text_value(d, KEYREMAP_PKG, SERVICE_COMMAND):
			save_step_screenshot(d, "step8_editor_not_found", SCRIPT_IMG_DIR)
			self.fail("Step 8 Failed: COMMAND edit field was not found")
		if not keyremap_tap_ok_button(d, serial):
			save_step_screenshot(d, "step8_service_not_saved", SCRIPT_IMG_DIR)
			self.fail("Step 8 Failed: could not save the service COMMAND mapping")
		save_step_screenshot(d, "step8_service_remap_saved", SCRIPT_IMG_DIR)

		print("\n[Step 9/11] Press Appswitch and verify service result")
		press_home_key(serial)
		is_on_home, last_focus = keyremap_is_on_home_screen(serial)
		if not is_on_home:
			save_step_screenshot(d, "step9_not_on_home", SCRIPT_IMG_DIR)
			self.fail(f"Step 9 Failed: could not return to Home (focus={last_focus})")
		keyremap_tap_navbar_appswitch(serial)

		app_shown, focus_info = keyremap_wait_app_foreground(serial, APP_PACKAGE)
		if not app_shown:
			save_step_screenshot(d, "step9_app_not_launched", SCRIPT_IMG_DIR)
			self.fail(
				f"Step 9 Failed: {APP_PACKAGE} was not foregrounded after the service "
				f"Appswitch command (focus={focus_info})"
			)

		service_started = False
		for _ in range(10):
			if d(text=SERVICE_STARTED_TEXT).exists(timeout=1):
				service_started = True
				break
		if not service_started:
			save_step_screenshot(d, "step9_service_not_started", SCRIPT_IMG_DIR)
			self.fail(f"Step 9 Failed: '{SERVICE_STARTED_TEXT}' was not displayed by LockAction")
		save_step_screenshot(d, "step9_service_started", SCRIPT_IMG_DIR)
		print(f"  Service result displayed: {SERVICE_STARTED_TEXT}")

		print("\n[Step 10/11] Edit APP_SWITCH mapping -> COMMAND URL view")
		if not keyremap_open_page(d, serial, SETTINGS_PKG, KEYREMAP_PKG):
			save_step_screenshot(d, "step10_navigation_failed", SCRIPT_IMG_DIR)
			self.fail("Step 10 Failed: could not navigate to the Keyremap page")
		if not keyremap_tap_text(d, serial, "APP_SWITCH", contains=False, max_swipes=10):
			save_step_screenshot(d, "step10_entry_not_found", SCRIPT_IMG_DIR)
			self.fail("Step 10 Failed: saved APP_SWITCH entry was not found")
		time.sleep(1)
		if not keyremap_tap_text(d, serial, "COMMAND", contains=False, max_swipes=10):
			save_step_screenshot(d, "step10_command_not_found", SCRIPT_IMG_DIR)
			self.fail("Step 10 Failed: COMMAND target was not found after opening APP_SWITCH")
		if not keyremap_input_text_value(d, KEYREMAP_PKG, VIEW_COMMAND):
			save_step_screenshot(d, "step10_editor_not_found", SCRIPT_IMG_DIR)
			self.fail("Step 10 Failed: COMMAND edit field was not found")
		if not keyremap_tap_ok_button(d, serial):
			save_step_screenshot(d, "step10_view_not_saved", SCRIPT_IMG_DIR)
			self.fail("Step 10 Failed: could not save the URL view COMMAND mapping")
		save_step_screenshot(d, "step10_view_remap_saved", SCRIPT_IMG_DIR)

		print(f"\n[Step 11/11] Press Appswitch and verify {VIEW_URL} is displayed")
		press_home_key(serial)
		is_on_home, last_focus = keyremap_is_on_home_screen(serial)
		if not is_on_home:
			save_step_screenshot(d, "step11_not_on_home", SCRIPT_IMG_DIR)
			self.fail(f"Step 11 Failed: could not return to Home (focus={last_focus})")
		keyremap_tap_navbar_appswitch(serial)
		dismiss_chrome_first_run_prompts(d)

		website_displayed = False
		for _ in range(15):
			if d(textContains=VIEW_URL).exists(timeout=1):
				website_displayed = True
				break
		if not website_displayed:
			save_step_screenshot(d, "step11_website_not_displayed", SCRIPT_IMG_DIR)
			self.fail(f"Step 11 Failed: '{VIEW_URL}' was not displayed after Appswitch")
		save_step_screenshot(d, "step11_website_displayed", SCRIPT_IMG_DIR)
		print(f"  Website displayed: {VIEW_URL}")


if __name__ == "__main__":
	unittest.main()
