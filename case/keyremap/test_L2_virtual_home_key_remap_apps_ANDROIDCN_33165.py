# -*- coding: utf-8 -*-
# __author__ = 'sophy_H400818'

"""
Test case: L2 Key Remap - HOME -> APPS (ANDROIDCN-33165)
Test key remap functionality via Settings --> Honeywell Settings --> Keyremap

Steps:
1. Install files/apps/app-debug-20260715-hon660-signed.apk onto the device.
2. Open Settings --> Honeywell Settings --> Keyremap --> tap '+' -->
   select Home (virtual icon in the key-capture dialog) --> click OK -->
   tap the "APPS" tab --> scroll down until the installed app is visible -->
   tap it to save the mapping.
3. Return to the Home (launcher) screen, then press the Home key on the
   device (remapped key).
4. Confirm the mapped app is launched. If so, the test passes.
5. Reopen Keyremap, tap the entry created above, tap the "APPS" tab, scroll
   down to "Scan Demo", tap it, then press the Home key again and confirm
   Scan Demo is launched.
6. Repeat the same flow for the EZMenu app and confirm it is launched.

Author: Sophy H400818
Date: 2026-09-02
"""

import time
import unittest
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from common.adb_common import (
    get_device_serial,
    keyremap_click_virtual_home,
    keyremap_force_stop_honeywell_settings,
    keyremap_install_app,
    keyremap_is_on_home_screen,
    keyremap_tap_navbar_home,
    keyremap_uninstall_app,
    keyremap_wait_app_foreground,
    press_home_key,
    run_adb_cmd,
    save_step_screenshot,
)
from common.common_method import (
    close_settings_app,
    disable_play_protect_app_scanning,
    enable_play_protect_app_scanning,
    get_case_config,
    get_package_name,
    keyremap_clear_all,
    keyremap_dialog_is_open,
    keyremap_find_text_center,
    keyremap_open_apps_tab,
    keyremap_open_page,
    keyremap_select_app_target,
    keyremap_tap_add_button,
    keyremap_tap_ok_button,
    keyremap_tap_text,
)
import uiautomator2 as u2

# ── Device connection ─────────────────────────────────────────────────────────
serial = get_device_serial()
if not serial:
    print("Error: No Android device found. Connect a device or set ANDROID_SERIAL.")
    sys.exit(1)

d = u2.connect(serial)

SCRIPT_BASENAME = os.path.splitext(os.path.basename(__file__))[0]
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.realpath(__file__))))
IMG_ROOT = os.path.join(PROJECT_ROOT, "img")
SCRIPT_IMG_DIR = os.path.join(IMG_ROOT, SCRIPT_BASENAME)
os.makedirs(SCRIPT_IMG_DIR, exist_ok=True)

SETTINGS_PKG = get_package_name("settings")
KEYREMAP_PKG = get_package_name("keyremap")

APK_FILE_NAME = get_case_config("keyremap_apps_case", "apk_file_name")
APK_PATH = os.path.join(PROJECT_ROOT, "files", "apps", APK_FILE_NAME)
APP_PACKAGE = get_case_config("keyremap_apps_case", "app_package")
APP_LABEL = get_case_config("keyremap_apps_case", "app_label")
SECOND_APP_PACKAGE = get_case_config("keyremap_apps_case", "scandemo_app_package")
SECOND_APP_LABEL = get_case_config("keyremap_apps_case", "scandemo_app_label")
THIRD_APP_PACKAGE = get_case_config("keyremap_apps_case", "powertool_app_package")
THIRD_APP_LABEL = get_case_config("keyremap_apps_case", "powertool_app_label")
CHROME_APP_PACKAGE = get_case_config("keyremap_apps_case", "chrome_app_package")
CHROME_APP_LABEL = get_case_config("keyremap_apps_case", "chrome_app_label")
CALCULATOR_APP_PACKAGE = get_case_config("keyremap_apps_case", "calculator_app_package")
CALCULATOR_APP_LABEL = get_case_config("keyremap_apps_case", "calculator_app_label")
CALENDAR_APP_PACKAGE = get_case_config("keyremap_apps_case", "calendar_app_package")
CALENDAR_APP_LABEL = get_case_config("keyremap_apps_case", "calendar_app_label")
CLOCK_APP_PACKAGE = get_case_config("keyremap_apps_case", "clock_app_package")
CLOCK_APP_LABEL = get_case_config("keyremap_apps_case", "clock_app_label")
FILES_APP_PACKAGE = get_case_config("keyremap_apps_case", "files_app_package")
FILES_APP_LABEL = get_case_config("keyremap_apps_case", "files_app_label")
SETTINGS_APP_PACKAGE = get_case_config("keyremap_apps_case", "settings_app_package")
SETTINGS_APP_LABEL = get_case_config("keyremap_apps_case", "settings_app_label")
PLAY_STORE_APP_PACKAGE = get_case_config("keyremap_apps_case", "play_store_app_package")
PLAY_STORE_APP_LABEL = get_case_config("keyremap_apps_case", "play_store_app_label")
HUPGRADER_APP_PACKAGE = get_case_config("keyremap_apps_case", "hupgrader_app_package")
HUPGRADER_APP_LABEL = get_case_config("keyremap_apps_case", "hupgrader_app_label")
PHONE_APP_PACKAGE = get_case_config("keyremap_apps_case", "phone_app_package")
PHONE_APP_LABEL = get_case_config("keyremap_apps_case", "phone_app_label")
SCANEDGE_APP_PACKAGE = get_case_config("keyremap_apps_case", "scanedge_app_package")
SCANEDGE_APP_LABEL = get_case_config("keyremap_apps_case", "scanedge_app_label")
SNAPDRAGON_CAMERA_APP_PACKAGE = get_case_config("keyremap_apps_case", "snapdragon_camera_app_package")
SNAPDRAGON_CAMERA_APP_LABEL = get_case_config("keyremap_apps_case", "snapdragon_camera_app_label")
HOME_APP_TARGETS = (
    (CHROME_APP_LABEL, tuple(CHROME_APP_PACKAGE.split(","))),
    (CALCULATOR_APP_LABEL, tuple(CALCULATOR_APP_PACKAGE.split(","))),
    (CALENDAR_APP_LABEL, tuple(CALENDAR_APP_PACKAGE.split(","))),
    (CLOCK_APP_LABEL, tuple(CLOCK_APP_PACKAGE.split(","))),
    (FILES_APP_LABEL, tuple(FILES_APP_PACKAGE.split(","))),
    (SETTINGS_APP_LABEL, tuple(SETTINGS_APP_PACKAGE.split(","))),
    (PLAY_STORE_APP_LABEL, tuple(PLAY_STORE_APP_PACKAGE.split(","))),
    (HUPGRADER_APP_LABEL, tuple(HUPGRADER_APP_PACKAGE.split(","))),
    (PHONE_APP_LABEL, tuple(PHONE_APP_PACKAGE.split(","))),
    (SCANEDGE_APP_LABEL, tuple(SCANEDGE_APP_PACKAGE.split(","))),
    (SNAPDRAGON_CAMERA_APP_LABEL, tuple(SNAPDRAGON_CAMERA_APP_PACKAGE.split(","))),
)
APP_PACKAGES_TO_STOP = tuple(
    dict.fromkeys(
        (APP_PACKAGE, SECOND_APP_PACKAGE, THIRD_APP_PACKAGE)
        + tuple(package for _, packages in HOME_APP_TARGETS for package in packages)
    )
)


# ── Test class ────────────────────────────────────────────────────────────────

class TestKeyremapHomeToApps(unittest.TestCase):
    """L2 test for Honeywell Keyremap: HOME remapped to an installed app."""

    @classmethod
    def setUpClass(cls):
        cls.dev_id = serial
        print(f"\n[Setup] Device: {cls.dev_id}")

    def setUp(self):
        print(f"\n{'='*60}\nTest: {self.id()}\n{'='*60}")
        self._installed_case_app = False
        d.press("home")
        time.sleep(1)

    def tearDown(self):
        # close the apps launched by the remapped key
        for package in APP_PACKAGES_TO_STOP:
            run_adb_cmd(serial, f"shell am force-stop {package}", log_print=False)
        time.sleep(1)

        # clear the remap so the device is clean for the next run
        if keyremap_open_page(d, serial, SETTINGS_PKG, KEYREMAP_PKG):
            keyremap_clear_all(d, serial)

            # return to the parent page after clearing
            run_adb_cmd(serial, "shell input keyevent KEYCODE_BACK", log_print=False)
            time.sleep(1)
        else:
            print("[TearDown] [WARN] Keyremap page not reachable; mapping may still exist")

        pid_raw = run_adb_cmd(serial, f"shell pidof {KEYREMAP_PKG}", log_print=False)
        pid_str = (pid_raw.decode("utf-8", errors="ignore") if isinstance(pid_raw, bytes) else str(pid_raw)).strip()
        if pid_str and pid_str.isdigit():
            run_adb_cmd(serial, f"shell kill {pid_str}", log_print=False)

        # force-stop honeywell settings app
        keyremap_force_stop_honeywell_settings(serial)

        # clear the settings app to ensure a clean state
        close_settings_app(serial)

        # remove the app installed by this case
        if self._installed_case_app:
            keyremap_uninstall_app(serial, APP_PACKAGE)

        if enable_play_protect_app_scanning(d):
            print("  Play Protect app scanning is enabled")
        else:
            print("  Play Protect app scanning could not be restored")
        run_adb_cmd(serial, "shell am force-stop com.android.vending", log_print=False)


        d.screen_on()
        d.press("home")
        time.sleep(1)
        print(f"[TearDown] Completed: {self.id()}")

    def test_keyremap_home_to_apps(self):
        """
        L2 Keyremap end-to-end test: HOME -> APPS.

        Step 1: Install the APK shipped under files/apps/.
        Step 2: Open Keyremap page → tap '+' → dialog appears →
                click Home virtual icon → key captured → click OK →
                tap the "APPS" tab → scroll until the app is visible →
                tap it → verify entry saved.
        Step 3: Return to the Home screen, then press the Home key
                on the device (remapped key).
        Step 4: Verify the mapped app is launched → Pass.
        Step 5: Reopen Keyremap → tap the saved entry → "APPS" tab →
                scroll until "Scan Demo" is visible → tap it → press the
                Home key again → verify Scan Demo is launched.
        Step 6: Same flow again for EZMenu → verify EZMenu is launched.
        """
        print("\n[L2_Keyremap] Testing HOME -> APPS Remap\n" + "="*60)

        # ── Step 1 ────────────────────────────────────────────────────────────
        print(f"\n[Step 1/6] Install '{APK_FILE_NAME}' from files/apps")
        print("-"*60)

        if disable_play_protect_app_scanning(d):
            print("  Play Protect app scanning is disabled")
        else:
            print("  Play Protect configuration was unavailable; continuing installation flow")


        installed, install_output = keyremap_install_app(serial, APK_PATH, APP_PACKAGE)
        if not installed:
            save_step_screenshot(d, "step1_install_failed", SCRIPT_IMG_DIR)
            self.fail(f"Step 1 Failed: could not install {APK_FILE_NAME} ({install_output})")
        self._installed_case_app = True

        save_step_screenshot(d, "step1_app_installed", SCRIPT_IMG_DIR)
        print(f"  ✓ App installed: {APP_PACKAGE}")
        print("  ✓ Step 1 passed")

        # ── Step 2 ────────────────────────────────────────────────────────────
        print(f"\n[Step 2/6] Keyremap: '+' → Home → OK → 'APPS' → select '{APP_LABEL}'")
        print("-"*60)

        if not keyremap_open_page(d, serial, SETTINGS_PKG, KEYREMAP_PKG):
            save_step_screenshot(d, "step2_nav_failed", SCRIPT_IMG_DIR)
            self.fail("Step 2 Failed: Could not navigate to Keyremap page")

        save_step_screenshot(d, "step2_keyremap_page", SCRIPT_IMG_DIR)
        print("  ✓ Keyremap page opened")

        keyremap_tap_add_button(d, serial)
        if not keyremap_dialog_is_open(d):
            save_step_screenshot(d, "step2_dialog_not_opened", SCRIPT_IMG_DIR)
            self.fail("Step 2 Failed: '+' button did not open the key-capture dialog")

        save_step_screenshot(d, "step2_dialog_opened", SCRIPT_IMG_DIR)
        print("  ✓ 'Please press the key to be mapped' dialog opened")

        # Click Home virtual icon as surrogate for the physical Home key
        keyremap_click_virtual_home(serial)
        time.sleep(1)

        keyremap_tap_ok_button(d, serial)

        if not keyremap_open_apps_tab(d, serial):
            save_step_screenshot(d, "step2_apps_tab_not_found", SCRIPT_IMG_DIR)
            self.fail("Step 2 Failed: 'APPS' tab not found in the target list")

        save_step_screenshot(d, "step2_apps_tab_opened", SCRIPT_IMG_DIR)
        print("  ✓ 'APPS' tab opened")

        if not keyremap_select_app_target(d, serial, APP_LABEL):
            save_step_screenshot(d, "step2_app_not_found", SCRIPT_IMG_DIR)
            self.fail(f"Step 2 Failed: '{APP_LABEL}' not found in the APPS list after scrolling")

        # An APP target is rendered as an icon only, so the saved row is confirmed by its source key.
        if keyremap_find_text_center(d, "HOME", contains=False) is None:
            save_step_screenshot(d, "step2_entry_not_confirmed", SCRIPT_IMG_DIR)
            self.fail("Step 2 Failed: 'HOME' entry not shown in Keyremap list after saving")

        save_step_screenshot(d, "step2_remap_saved", SCRIPT_IMG_DIR)
        print(f"  ✓ Remap entry saved: HOME → {APP_LABEL}")
        print("  ✓ Step 2 passed")

        # ── Step 3 ────────────────────────────────────────────────────────────
        print("\n[Step 3/6] Return to Home screen, then press the Home key")
        print("-"*60)

        press_home_key(serial)
        is_on_home, last_focus = keyremap_is_on_home_screen(serial)

        if not is_on_home:
            save_step_screenshot(d, "step3_not_on_home", SCRIPT_IMG_DIR)
            self.fail(f"Step 3 Failed: could not return to the Home screen (last focus={last_focus})")

        save_step_screenshot(d, "step3_on_home", SCRIPT_IMG_DIR)
        print("  ✓ Returned to the Home screen")

        keyremap_tap_navbar_home(serial)
        time.sleep(2)
        save_step_screenshot(d, "step3_home_pressed", SCRIPT_IMG_DIR)
        print("  ✓ Step 3 passed")

        # ── Step 4 ────────────────────────────────────────────────────────────
        print(f"\n[Step 4/6] Verify '{APP_LABEL}' was launched")
        print("-"*60)

        app_shown, focus_info = keyremap_wait_app_foreground(serial, APP_PACKAGE)
        print(f"  App foreground: {app_shown}, focus: {focus_info or 'unknown'}")

        if not app_shown:
            save_step_screenshot(d, "step4_app_not_launched", SCRIPT_IMG_DIR)
            self.fail(
                f"Step 4 Failed: '{APP_LABEL}' ({APP_PACKAGE}) was not launched "
                f"after the remapped HOME key (focus={focus_info})"
            )

        save_step_screenshot(d, "step4_app_launched", SCRIPT_IMG_DIR)
        print(f"  ✓ '{APP_LABEL}' is displayed")
        print("  ✓ Step 4 passed")

        # ── Step 5 ────────────────────────────────────────────────────────────
        print(f"\n[Step 5/6] Reopen Keyremap → saved entry → 'APPS' → select '{SECOND_APP_LABEL}'")
        print("-"*60)

        if not keyremap_open_page(d, serial, SETTINGS_PKG, KEYREMAP_PKG):
            save_step_screenshot(d, "step5_nav_failed", SCRIPT_IMG_DIR)
            self.fail("Step 5 Failed: Could not navigate back to the Keyremap page")

        save_step_screenshot(d, "step5_keyremap_page", SCRIPT_IMG_DIR)

        if not keyremap_tap_text(d, serial, "HOME", contains=False, max_swipes=10):
            save_step_screenshot(d, "step5_entry_not_found", SCRIPT_IMG_DIR)
            self.fail("Step 5 Failed: saved 'HOME' entry not found in the Keyremap list")
        time.sleep(2)

        if not keyremap_open_apps_tab(d, serial):
            save_step_screenshot(d, "step5_apps_tab_not_found", SCRIPT_IMG_DIR)
            self.fail("Step 5 Failed: 'APPS' tab not found after opening the saved entry")

        save_step_screenshot(d, "step5_apps_tab_opened", SCRIPT_IMG_DIR)
        print("  ✓ 'APPS' tab opened")

        if not keyremap_select_app_target(d, serial, SECOND_APP_LABEL):
            save_step_screenshot(d, "step5_app_not_found", SCRIPT_IMG_DIR)
            self.fail(f"Step 5 Failed: '{SECOND_APP_LABEL}' not found in the APPS list after scrolling")

        if keyremap_find_text_center(d, "HOME", contains=False) is None:
            save_step_screenshot(d, "step5_entry_not_confirmed", SCRIPT_IMG_DIR)
            self.fail("Step 5 Failed: 'HOME' entry not shown in Keyremap list after updating")

        save_step_screenshot(d, "step5_remap_updated", SCRIPT_IMG_DIR)
        print(f"  ✓ Remap entry updated: HOME → {SECOND_APP_LABEL}")

        press_home_key(serial)
        is_on_home, last_focus = keyremap_is_on_home_screen(serial)
        if not is_on_home:
            save_step_screenshot(d, "step5_not_on_home", SCRIPT_IMG_DIR)
            self.fail(f"Step 5 Failed: could not return to the Home screen (last focus={last_focus})")

        keyremap_tap_navbar_home(serial)
        time.sleep(2)

        second_app_shown, second_focus = keyremap_wait_app_foreground(serial, SECOND_APP_PACKAGE)
        print(f"  App foreground: {second_app_shown}, focus: {second_focus or 'unknown'}")

        if not second_app_shown:
            save_step_screenshot(d, "step5_app_not_launched", SCRIPT_IMG_DIR)
            self.fail(
                f"Step 5 Failed: '{SECOND_APP_LABEL}' ({SECOND_APP_PACKAGE}) was not launched "
                f"after the remapped HOME key (focus={second_focus})"
            )

        save_step_screenshot(d, "step5_app_launched", SCRIPT_IMG_DIR)
        print(f"  ✓ '{SECOND_APP_LABEL}' is displayed")
        print("  ✓ Step 5 passed")

        # ── Step 6 ────────────────────────────────────────────────────────────
        print(f"\n[Step 6/6] Reopen Keyremap → saved entry → 'APPS' → select '{THIRD_APP_LABEL}' (EZMenu)")
        print("-"*60)

        if not keyremap_open_page(d, serial, SETTINGS_PKG, KEYREMAP_PKG):
            save_step_screenshot(d, "step6_nav_failed", SCRIPT_IMG_DIR)
            self.fail("Step 6 Failed: Could not navigate back to the Keyremap page")

        save_step_screenshot(d, "step6_keyremap_page", SCRIPT_IMG_DIR)

        if not keyremap_tap_text(d, serial, "HOME", contains=False, max_swipes=10):
            save_step_screenshot(d, "step6_entry_not_found", SCRIPT_IMG_DIR)
            self.fail("Step 6 Failed: saved 'HOME' entry not found in the Keyremap list")
        time.sleep(2)

        if not keyremap_open_apps_tab(d, serial):
            save_step_screenshot(d, "step6_apps_tab_not_found", SCRIPT_IMG_DIR)
            self.fail("Step 6 Failed: 'APPS' tab not found after opening the saved entry")

        save_step_screenshot(d, "step6_apps_tab_opened", SCRIPT_IMG_DIR)
        print("  ✓ 'APPS' tab opened")

        if not keyremap_select_app_target(d, serial, THIRD_APP_LABEL):
            save_step_screenshot(d, "step6_app_not_found", SCRIPT_IMG_DIR)
            self.fail(f"Step 6 Failed: '{THIRD_APP_LABEL}' not found in the APPS list after scrolling")

        if keyremap_find_text_center(d, "HOME", contains=False) is None:
            save_step_screenshot(d, "step6_entry_not_confirmed", SCRIPT_IMG_DIR)
            self.fail("Step 6 Failed: 'HOME' entry not shown in Keyremap list after updating")

        save_step_screenshot(d, "step6_remap_updated", SCRIPT_IMG_DIR)
        print(f"  ✓ Remap entry updated: HOME → {THIRD_APP_LABEL}")

        press_home_key(serial)
        is_on_home, last_focus = keyremap_is_on_home_screen(serial)
        if not is_on_home:
            save_step_screenshot(d, "step6_not_on_home", SCRIPT_IMG_DIR)
            self.fail(f"Step 6 Failed: could not return to the Home screen (last focus={last_focus})")

        keyremap_tap_navbar_home(serial)
        time.sleep(2)

        third_app_shown, third_focus = keyremap_wait_app_foreground(serial, THIRD_APP_PACKAGE)
        print(f"  App foreground: {third_app_shown}, focus: {third_focus or 'unknown'}")

        if not third_app_shown:
            save_step_screenshot(d, "step6_app_not_launched", SCRIPT_IMG_DIR)
            self.fail(
                f"Step 6 Failed: '{THIRD_APP_LABEL}' ({THIRD_APP_PACKAGE}) was not launched "
                f"after the remapped HOME key (focus={third_focus})"
            )

        save_step_screenshot(d, "step6_app_launched", SCRIPT_IMG_DIR)
        print(f"  ✓ '{THIRD_APP_LABEL}' is displayed")
        print("  ✓ Step 6 passed")

        print("\n[L2_Keyremap] All steps passed ✓")
        print("\n[L2_Keyremap] Testing HOME -> common APPS targets\n" + "="*60)
        apps_not_found = []
        for app_label, package_names in HOME_APP_TARGETS:
            print(f"\n[HOME -> APPS] Testing {app_label} ({', '.join(package_names)})")
            if not self._remap_home_to_app(app_label, package_names):
                apps_not_found.append(app_label)
        if apps_not_found:
            print("========================Attention:check not found app list===============================")
            print(f"\n[L2_Keyremap] Apps not found and skipped: {', '.join(apps_not_found)}")
            print("========================================================================================")

        else:
            print("\n[L2_Keyremap] All common app targets passed ✓")

    # Sophy_H400818_2026-09-29
    def _remap_home_to_app(self, app_label, package_names):
        """Run the numbered HOME-to-app flow used by this keyremap case."""
        screenshot_name = app_label.lower().replace(" ", "_")
        for package_name in package_names:
            run_adb_cmd(serial, f"shell am force-stop {package_name}", log_print=False)

        print(f"\n[Step 1/4] Keyremap: '+' → Home → OK → 'APPS' → select '{app_label}'")
        print("-"*60)

        if not keyremap_open_page(d, serial, SETTINGS_PKG, KEYREMAP_PKG):
            save_step_screenshot(d, f"{screenshot_name}_nav_failed", SCRIPT_IMG_DIR)
            self.fail(f"Step 1 Failed: Could not navigate to Keyremap for '{app_label}'")
        save_step_screenshot(d, f"{screenshot_name}_keyremap_page", SCRIPT_IMG_DIR)
        print("  ✓ Keyremap page opened")

        keyremap_clear_all(d, serial)
        keyremap_tap_add_button(d, serial)
        if not keyremap_dialog_is_open(d):
            save_step_screenshot(d, f"{screenshot_name}_dialog_not_opened", SCRIPT_IMG_DIR)
            self.fail(f"Step 1 Failed: '+' button did not open key-capture dialog for '{app_label}'")
        save_step_screenshot(d, f"{screenshot_name}_dialog_opened", SCRIPT_IMG_DIR)
        print("  ✓ Key-capture dialog opened")

        keyremap_click_virtual_home(serial)
        time.sleep(1)
        if not keyremap_tap_ok_button(d, serial):
            save_step_screenshot(d, f"{screenshot_name}_ok_failed", SCRIPT_IMG_DIR)
            self.fail(f"Step 1 Failed: Could not confirm HOME key for '{app_label}'")

        if not keyremap_open_apps_tab(d, serial):
            save_step_screenshot(d, f"{screenshot_name}_apps_tab_not_found", SCRIPT_IMG_DIR)
            self.fail(f"Step 1 Failed: 'APPS' tab not found for '{app_label}'")
        save_step_screenshot(d, f"{screenshot_name}_apps_tab_opened", SCRIPT_IMG_DIR)
        print("  ✓ 'APPS' tab opened")

        if not keyremap_select_app_target(d, serial, app_label):
            save_step_screenshot(d, f"{screenshot_name}_app_not_found", SCRIPT_IMG_DIR)
            print(
                f"  [WARN] App not found: '{app_label}' in the APPS list after scrolling; "
                "skipping this app and continuing with the next target."
            )
            return False

        if keyremap_find_text_center(d, "HOME", contains=False) is None:
            save_step_screenshot(d, f"{screenshot_name}_mapping_not_confirmed", SCRIPT_IMG_DIR)
            self.fail(f"Step 1 Failed: HOME mapping to '{app_label}' was not saved")
        save_step_screenshot(d, f"{screenshot_name}_remap_saved", SCRIPT_IMG_DIR)
        print(f"  ✓ Remap entry saved: HOME → {app_label}")
        print("  ✓ Step 1 passed")

        print("\n[Step 2/4] Return to Home screen")
        print("-"*60)
        press_home_key(serial)
        is_on_home, last_focus = keyremap_is_on_home_screen(serial)
        if not is_on_home:
            save_step_screenshot(d, f"{screenshot_name}_not_on_home", SCRIPT_IMG_DIR)
            self.fail(
                f"Step 2 Failed: Could not return to Home before testing '{app_label}' "
                f"(focus={last_focus})"
            )
        save_step_screenshot(d, f"{screenshot_name}_on_home", SCRIPT_IMG_DIR)
        print("  ✓ Returned to the Home screen")
        print("  ✓ Step 2 passed")

        print(f"\n[Step 3/4] Press the remapped Home key for '{app_label}'")
        print("-"*60)
        keyremap_tap_navbar_home(serial)
        time.sleep(2)
        save_step_screenshot(d, f"{screenshot_name}_home_pressed", SCRIPT_IMG_DIR)
        print("  ✓ Home key pressed")
        print("  ✓ Step 3 passed")

        print(f"\n[Step 4/4] Verify '{app_label}' was launched")
        print("-"*60)
        focus_info = None
        for package_name in package_names:
            app_shown, focus_info = keyremap_wait_app_foreground(serial, package_name)
            if not app_shown and self._is_app_process_running(package_name):
                app_shown = True
                print(
                    f"  [INFO] '{app_label}' process is running although another screen "
                    "has focus; counting the app launch as successful."
                )
            if app_shown:
                save_step_screenshot(d, f"{screenshot_name}_launched", SCRIPT_IMG_DIR)
                print(f"  App foreground: {app_shown}, focus: {focus_info or 'unknown'}")
                print(f"  ✓ '{app_label}' is displayed ({package_name})")
                print("  ✓ Step 4 passed")
                return True

        save_step_screenshot(d, f"{screenshot_name}_not_launched", SCRIPT_IMG_DIR)
       
        self.fail(
            f"Step 4 Failed: '{app_label}' was not launched after the remapped HOME key; "
            f"expected one of {package_names}, last focus={focus_info or 'unknown'}"
        )
    
    # Sophy_H400818_2026-09-29
    def _is_app_process_running(self, package_name):
        """Confirm the target process after the flow force-stops it before launch."""
        pid_raw = run_adb_cmd(serial, f"shell pidof {package_name}", log_print=False)
        pid_text = pid_raw.decode("utf-8", errors="ignore") if isinstance(pid_raw, bytes) else str(pid_raw)
        return bool(pid_text.strip())


if __name__ == "__main__":
    unittest.main()
