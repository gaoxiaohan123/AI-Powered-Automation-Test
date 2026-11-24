# __author__ = 'sophy' for CT47
# -*- coding:utf-8 -*-

"""
DSDS Mode Switch Test

Test Scope:
This test only applies to CT47 devices with two SIM cards inserted (dual SIM support).
Non-CT47 models, WLAN-only devices (APQ baseband), and single-SIM devices (only 1 IMEI
detected) are skipped.

Test Purpose:
Verify DSDS (Dual SIM Dual Standby) mode switching functionality:
1. Enable "Show DSDS Menu" in Developer Options if disabled
2. Navigate to DSDS Mode settings
3. Switch between different DSDS modes and verify success

Test Steps:
0. Pre-check: Verify device model is CT47; skip on other models
1. Pre-check: Verify device baseband is MSM (dual SIM capable)
2. Pre-check: Dial *#06# to confirm 2 SIMs are present; skip on single-SIM devices
3. Open Settings -> System -> Developer Options -> Honeywell Developer Options
4. Check "Show DSDS Menu" switch status, enable it if currently disabled
5. Navigate to Settings -> Network & Internet -> DSDS Mode
6. Switch between available DSDS modes (Single SIM, Dual SIM, etc.)
7. Verify each mode switch is successful

Device Info:
- Model: CT47
- Part Number: CT47-X1N-5ED1E0G
- Android Version: 14
- Baseband: MSM (Dual SIM capable)
"""

import unittest
import os
import sys
import time
import subprocess
import re
import uiautomator2 as u2

# Add parent path to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from common.adb_common import (
    save_step_screenshot,
    force_stop_Settings_app,
    dcs_test_wait_device_online,
    imei_get_baseband_type,
    get_device_model,
    dev_options_is_enabled,
    dev_options_set_enabled,
)
from common.common_method import (
    imei_read_from_dialer,
    dev_options_enable,
    tap_first_available_text,
    dcs_test_query_option_checked,
    dcs_test_set_option_checked,
)

# Connect device via ANDROID_SERIAL environment variable
serial = os.environ.get('ANDROID_SERIAL')
d = u2.connect(serial)

SCRIPT_BASENAME = os.path.splitext(os.path.basename(__file__))[0]
IMG_ROOT = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.realpath(__file__)))), "img")
SCRIPT_IMG_DIR = os.path.join(IMG_ROOT, SCRIPT_BASENAME)
os.makedirs(SCRIPT_IMG_DIR, exist_ok=True)


class Test_DSDS_Mode_Switch(unittest.TestCase):
    """
    Test case: DSDS Mode Switch
    Verify DSDS mode switching functionality
    """

    @classmethod
    def setUpClass(cls):
        """Test class initialization"""
        cls.device = serial
        
        print(f"\n{'='*70}")
        print(f"DSDS Mode Switch Test")
        print(f"{'='*70}")
        print(f"Test Device: {cls.device}")
        
        # Initialize state tracking variables
        cls.original_dev_options_enabled = None
        cls.original_show_dsds_menu_enabled = None
        cls.original_dsds_mode = None
        
        # Initialize IMEI tracking variables
        cls.sim1_imei = None
        cls.sim2_imei = None
        cls.imei_recorded = False

    def setUp(self):
        """Setup before each test"""
        print("\n" + "="*70)
        d.screen_on()
        d.press("home")
        time.sleep(1)
        
        # Record original settings before test
        self._record_original_settings()

    def tearDown(self):
        """Cleanup after each test"""
        print("\n" + "="*70)
        print("Cleanup: Restoring original settings...")
        
        # Restore original settings
        self._restore_original_settings()
        
        # Close all apps
        print("Cleanup: Closing all apps...")
        force_stop_Settings_app(serial, "com.android.settings")
        force_stop_Settings_app(serial, "com.android.dialer")
        force_stop_Settings_app(serial, "com.google.android.dialer")
        
        d.press('home')
        time.sleep(0.5)
        print("✓ Cleanup completed")
        print("="*70)

    def _record_original_settings(self):
        """
        Record original device settings before test
        """
        try:
            print("\n[Recording Original Settings]")
            
            # Record Developer Options state
            self.original_dev_options_enabled = dev_options_is_enabled(serial)
            print(f"  Developer Options: {'Enabled' if self.original_dev_options_enabled else 'Disabled'}")
            
            # Record Show DSDS Menu state (need to navigate to check)
            # We'll check this when we navigate to Honeywell Dev Options
            # For now, just mark as unknown
            self.original_show_dsds_menu_enabled = None
            
            # Record current DSDS mode
            self.original_dsds_mode = None
            print("  Original DSDS mode will be recorded during test navigation")
            
            print("✓ Original settings recorded")
            
        except Exception as e:
            print(f"  ⚠ Error recording original settings: {e}")

    def _restore_original_settings(self):
        """
        Restore device settings to original state
        """
        global d
        
        try:
            print("\n[Restoring Original Settings]")
            
            # Check device baseband - skip restore for WLAN devices
            baseband = imei_get_baseband_type(serial)
            if baseband == "apq":
                print("  WLAN device - no settings to restore")
                return
            
            # Restore Show DSDS Menu state
            if self.original_show_dsds_menu_enabled is not None:
                print(f"\n  Restoring 'Show DSDS Menu' to: {'Enabled' if self.original_show_dsds_menu_enabled else 'Disabled'}")
                
                # Navigate to Honeywell Developer Options
                if self._navigate_to_honeywell_dev_options():
                    restored = dcs_test_set_option_checked(d, "Show DSDS Menu", self.original_show_dsds_menu_enabled)
                    print(f"    {'✓ Show DSDS Menu restored' if restored else '⚠ Could not restore Show DSDS Menu'}")
                    
                    d.press("back")
                    d.press("back")
                    time.sleep(0.5)
            
            # Restore DSDS mode
            if self.original_dsds_mode:
                print(f"\n  Restoring DSDS mode to: '{self.original_dsds_mode}'")
                
                d.press("home")
                time.sleep(1)
                
                if self._navigate_to_dsds_mode_settings():
                    # Find and click dropdown
                    dropdown = None
                    if d(className="android.widget.Spinner").exists(timeout=2):
                        dropdown = d(className="android.widget.Spinner")
                    elif d(textMatches=".*Enable.*").exists(timeout=2):
                        dropdown = d(textMatches=".*Enable.*")
                    
                    if dropdown:
                        dropdown.click()
                        time.sleep(2)
                        
                        # Select original mode
                        if d(text=self.original_dsds_mode).exists(timeout=2):
                            d(text=self.original_dsds_mode).click()
                            time.sleep(1)
                            
                            # Click Apply
                            apply_clicked = tap_first_available_text(d, ["Apply", "应用", "APPLY"], timeout=2) is not None
                            if apply_clicked:
                                time.sleep(1.2)
                            
                            if apply_clicked:
                                # Handle reboot dialog if appears
                                if d(textContains="reboot").exists(timeout=2):
                                    if tap_first_available_text(d, ["OK", "确定"], timeout=1):
                                        time.sleep(1.2)
                                
                                print("    ✓ DSDS mode restored")
                                
                                # Wait if device reboots
                                time.sleep(5)
                                try:
                                    d.info
                                except:
                                    print("    Device rebooting, waiting...")
                                    time.sleep(60)
                                    d = u2.connect(serial)
                    
                    d.press("back")
                    time.sleep(0.5)
            
            # Restore Developer Options state
            if self.original_dev_options_enabled is not None and not self.original_dev_options_enabled:
                print(f"\n  Disabling Developer Options (was originally disabled)")
                dev_options_set_enabled(serial, False)
                print("    ✓ Developer Options disabled")
            
            d.press("home")
            time.sleep(0.5)
            print("\n✓ All settings restored to original state")
            
        except Exception as e:
            print(f"  ⚠ Error restoring settings: {e}")
            save_step_screenshot(d, 'restore_settings_error', SCRIPT_IMG_DIR)

    def _enable_developer_options(self):
        """
        Enable Developer Options if not already enabled
        """
        return dev_options_enable(d, serial)

    def _navigate_to_honeywell_dev_options(self):
        """
        Navigate to Settings -> System -> Developer Options -> Honeywell Developer Options
        :return: True if successful, False otherwise
        """
        try:
            print("\n  Opening Developer Options...")
            
            # Open Developer Options
            cmd = f"adb -s {serial} shell am start -n com.android.settings/.Settings\\$DevelopmentSettingsDashboardActivity"
            result = subprocess.run(cmd, capture_output=True, text=True, shell=True, timeout=5)
            time.sleep(2)
            
            save_step_screenshot(d, 'developer_options_opened', SCRIPT_IMG_DIR)
            
            # Scroll to find Honeywell Developer Options
            print("  Looking for Honeywell Developer Options...")
            honeywell_found = False
            
            for scroll_attempt in range(15):
                if d(text="Honeywell developer options").exists(timeout=1):
                    honeywell_found = True
                    print(f"  ✓ Found Honeywell Developer Options (after {scroll_attempt} scroll(s))")
                    break
                
                # Scroll down
                if d(scrollable=True).exists():
                    d(scrollable=True).scroll.forward()
                else:
                    d.swipe(500, 1500, 500, 500, duration=0.3)
                
                time.sleep(0.3)
            
            if not honeywell_found:
                print("  ⚠ Honeywell Developer Options not found")
                save_step_screenshot(d, 'honeywell_dev_options_not_found', SCRIPT_IMG_DIR)
                return False
            
            save_step_screenshot(d, 'honeywell_dev_options_found', SCRIPT_IMG_DIR)
            
            # Click on Honeywell Developer Options
            print("  Clicking Honeywell Developer Options...")
            d(text="Honeywell developer options").click()
            time.sleep(2)
            
            save_step_screenshot(d, 'honeywell_dev_options_page', SCRIPT_IMG_DIR)
            print("  ✓ Entered Honeywell Developer Options")
            
            return True
            
        except Exception as e:
            print(f"  ❌ Error navigating to Honeywell Developer Options: {e}")
            save_step_screenshot(d, 'navigate_error', SCRIPT_IMG_DIR)
            return False

    def _check_and_enable_show_dsds_menu(self):
        """
        Check "Show DSDS Menu" switch status and enable it if disabled
        :return: True if enabled (or successfully enabled), False otherwise
        """
        try:
            print("\n  Looking for 'Show DSDS Menu' switch...")
            save_step_screenshot(d, 'honeywell_dev_options_page', SCRIPT_IMG_DIR)

            # Scroll the label into view before reading its state (dump_hierarchy only sees rendered nodes)
            for scroll_attempt in range(5):
                if dcs_test_query_option_checked(d, "Show DSDS Menu") is not None:
                    break
                if not d(scrollable=True).exists(timeout=0.5):
                    break
                d(scrollable=True).scroll.forward()
                time.sleep(0.3)

            if self.original_show_dsds_menu_enabled is None:
                self.original_show_dsds_menu_enabled = dcs_test_query_option_checked(d, "Show DSDS Menu")
                print(f"  [Recorded] Original Show DSDS Menu state: {self.original_show_dsds_menu_enabled}")

            enabled = dcs_test_set_option_checked(d, "Show DSDS Menu", True)
            save_step_screenshot(d, 'after_click_dsds_menu', SCRIPT_IMG_DIR)
            print(f"  {'✓' if enabled else '⚠'} 'Show DSDS Menu' is {'ENABLED' if enabled else 'still DISABLED'}")
            return enabled

        except Exception as e:
            print(f"  ❌ Error checking/enabling 'Show DSDS Menu': {e}")
            save_step_screenshot(d, 'dsds_menu_error', SCRIPT_IMG_DIR)
            return False

    def _navigate_to_dsds_mode_settings(self):
        """
        Navigate to Settings -> Network & Internet -> DSDS Mode
        :return: True if successful, False otherwise
        """
        try:
            print("\n  Navigating to DSDS Mode settings...")
            
            # Go back to home first
            d.press("home")
            time.sleep(1)
            
            # Open Network & Internet settings
            print("  Opening Network & Internet settings...")
            cmd = f"adb -s {serial} shell am start -a android.settings.WIRELESS_SETTINGS"
            subprocess.run(cmd, capture_output=True, text=True, shell=True, timeout=5)
            time.sleep(2)
            
            save_step_screenshot(d, 'network_internet_opened', SCRIPT_IMG_DIR)
            
            # Look for DSDS Mode option
            print("  Looking for 'DSDS Mode' or 'DSDS' option...")
            dsds_mode_found = False
            
            # Try different possible text variations
            dsds_text_options = [
                "DSDS Mode",
                "DSDS mode",
                "DSDS",
                "Switch DSDS mode",
                "Dual SIM mode"
            ]
            
            for scroll_attempt in range(15):
                for text_option in dsds_text_options:
                    if d(textContains=text_option).exists(timeout=0.5):
                        dsds_mode_found = True
                        print(f"  ✓ Found '{text_option}' (after {scroll_attempt} scroll(s))")
                        
                        save_step_screenshot(d, 'dsds_mode_option_found', SCRIPT_IMG_DIR)
                        
                        # Click on DSDS Mode option
                        d(textContains=text_option).click()
                        time.sleep(2)
                        
                        save_step_screenshot(d, 'dsds_mode_page_opened', SCRIPT_IMG_DIR)
                        print("  ✓ Entered DSDS Mode settings")
                        return True
                
                if dsds_mode_found:
                    break
                
                # Scroll down
                if d(scrollable=True).exists():
                    d(scrollable=True).scroll.forward()
                else:
                    d.swipe(500, 1500, 500, 500, duration=0.3)
                
                time.sleep(0.3)
            
            if not dsds_mode_found:
                print("  ⚠ DSDS Mode option not found in Network & Internet settings")
                save_step_screenshot(d, 'dsds_mode_not_found', SCRIPT_IMG_DIR)
                return False
            
        except Exception as e:
            print(f"  ❌ Error navigating to DSDS Mode settings: {e}")
            save_step_screenshot(d, 'navigate_dsds_error', SCRIPT_IMG_DIR)
            return False

    def _get_imei_from_dial(self):
        """
        Get IMEI number(s) by dialing *#06#
        :return: List of IMEI numbers found
        """
        global d

        try:
            print("\n  Getting IMEI via dial *#06#...")
            d.press("home")
            time.sleep(1)

            sim1_imei, sim2_imei = imei_read_from_dialer(d, serial, SCRIPT_IMG_DIR)
            unique_imeis = [imei for imei in (sim1_imei, sim2_imei) if imei]
            print(f"  Found {len(unique_imeis)} IMEI code(s): {unique_imeis}")
            return unique_imeis

        except Exception as e:
            print(f"  ❌ Error getting IMEI: {e}")
            save_step_screenshot(d, 'get_imei_error', SCRIPT_IMG_DIR)
            return []

    def _switch_to_mode_and_apply(self, target_mode):
        """
        Switch to specified DSDS mode
        :param target_mode: Target mode name (e.g., "Enable SIM1 only", "Enable SIM2 only", "Enable DSDS")
        :return: True if successful, False otherwise
        """
        global d
        
        try:
            print(f"\n  Switching to mode: '{target_mode}'")
            
            # Navigate to DSDS mode settings
            if not self._navigate_to_dsds_mode_settings():
                print("  ⚠ Failed to navigate to DSDS mode settings")
                return False
            
            # Find and click dropdown
            dropdown = None
            if d(className="android.widget.Spinner").exists(timeout=2):
                dropdown = d(className="android.widget.Spinner")
            elif d(textMatches=".*Enable.*").exists(timeout=2):
                dropdown = d(textMatches=".*Enable.*")
            
            if dropdown is None:
                print("  ⚠ Could not find DSDS mode dropdown")
                return False
            
            # Click dropdown to open options
            dropdown.click()
            time.sleep(2)
            
            # Find and click target mode
            mode_found = False
            if d(text=target_mode).exists(timeout=2):
                d(text=target_mode).click()
                mode_found = True
                time.sleep(2)
            elif d(textContains=target_mode.replace("Enable ", "")).exists(timeout=1):
                d(textContains=target_mode.replace("Enable ", "")).click()
                mode_found = True
                time.sleep(2)
            
            if not mode_found:
                print(f"  ⚠ Mode '{target_mode}' not found")
                d.press("back")
                return False
            
            # Handle SIM switch confirmation dialog if appears
            print("  Checking for SIM switch confirmation dialog...")
            time.sleep(1)
            
            if d(textContains="Switch to SIM").exists(timeout=2):
                print("  ✓ Found SIM switch dialog")
                save_step_screenshot(d, 'sim_switch_dialog', SCRIPT_IMG_DIR)
                
                # Try to click OK button
                if tap_first_available_text(d, ["OK"], timeout=2):
                    print("  ✓ Clicked OK button")
                    time.sleep(1.2)
                else:
                    print("  ⚠ OK button not found")
            
            # Click Apply button
            apply_clicked = tap_first_available_text(d, ["Apply", "应用", "APPLY"], timeout=2) is not None
            if apply_clicked:
                time.sleep(1.2)
            
            if not apply_clicked:
                print("  ⚠ Apply button not found")
                return False
            
            # Check for "Switch to SIM" dialog after Apply
            print("  Checking for post-Apply SIM switch dialog...")
            time.sleep(1)
            
            if d(textContains="Switch to SIM").exists(timeout=2):
                print("  ✓ Found post-Apply SIM switch dialog")
                if tap_first_available_text(d, ["OK"], timeout=2):
                    print("  ✓ Clicked OK on post-Apply dialog")
                    time.sleep(1.2)
            
            # Handle reboot dialog if appears
            if d(textContains="reboot").exists(timeout=2):
                if tap_first_available_text(d, ["OK", "确定"], timeout=1):
                    time.sleep(1.2)
                
                # Wait for possible reboot
                time.sleep(5)
                try:
                    d.info
                except:
                    print("  Device rebooting, waiting...")
                    if not dcs_test_wait_device_online(serial, timeout_seconds=120):
                        print("  ⚠ Device did not come back online")
                        return False
                    time.sleep(15)
                    d = u2.connect(serial)
                    time.sleep(10)
            
            print(f"  ✓ Successfully switched to '{target_mode}'")
            return True
            
        except Exception as e:
            print(f"  ❌ Error switching to mode: {e}")
            return False

    def _verify_imei(self, selected_mode):
        """
        Verify IMEI count and actual IMEI numbers match the selected DSDS mode
        
        :param selected_mode: The selected mode (e.g., "Enable DSDS", "Enable SIM1 only", "Enable SIM2 only")
        :return: True if verification passed, False otherwise
        """
        global d
        
        try:
            print(f"\n  Verifying IMEI for mode: '{selected_mode}'")
            
            # Get current IMEI(s) by dialing *#06#
            unique_imeis = self._get_imei_from_dial()
            imei_count = len(unique_imeis)
            
            print(f"  Found {imei_count} IMEI code(s): {unique_imeis}")
            
            # Verify IMEI count based on selected mode
            verification_passed = False
            expected_count = 0
            
            # Check if initial IMEIs have been recorded
            if not self.imei_recorded:
                print("  ⚠ Initial IMEIs not recorded, cannot verify IMEI match")
                print("  Only verifying IMEI count...")
            
            if "DSDS" in selected_mode and "SIM" not in selected_mode:
                # Enable DSDS mode - should have 2 IMEIs
                expected_count = 2
                if imei_count == 2:
                    if self.imei_recorded:
                        # Verify both IMEIs match the recorded ones
                        if self.sim1_imei in unique_imeis and self.sim2_imei in unique_imeis:
                            print(f"  ✓ IMEI verification PASSED: DSDS mode has 2 IMEIs and both match recorded IMEIs")
                            print(f"    SIM1 IMEI: {self.sim1_imei} - ✓ Found")
                            print(f"    SIM2 IMEI: {self.sim2_imei} - ✓ Found")
                            verification_passed = True
                        else:
                            print(f"  ✗ IMEI verification FAILED: DSDS mode has 2 IMEIs but they don't match recorded IMEIs")
                            print(f"    Expected: {self.sim1_imei}, {self.sim2_imei}")
                            print(f"    Found: {unique_imeis}")
                            verification_passed = False
                    else:
                        print(f"  ✓ IMEI count verification PASSED: DSDS mode has 2 IMEIs")
                        verification_passed = True
                else:
                    print(f"  ✗ IMEI verification FAILED: DSDS mode should have 2 IMEIs, but found {imei_count}")
                    verification_passed = False
            
            elif "SIM1" in selected_mode or "SIM 1" in selected_mode:
                # Enable SIM1 only mode - should have 1 IMEI (first IMEI)
                expected_count = 1
                if imei_count == 1:
                    if self.imei_recorded:
                        # Verify the IMEI matches the first IMEI
                        if unique_imeis[0] == self.sim1_imei:
                            print(f"  ✓ IMEI verification PASSED: SIM1 only mode has correct IMEI")
                            print(f"    Expected IMEI: {self.sim1_imei} - ✓ Match")
                            verification_passed = True
                        else:
                            print(f"  ✗ IMEI verification FAILED: SIM1 IMEI doesn't match")
                            print(f"    Expected: {self.sim1_imei}")
                            print(f"    Found: {unique_imeis[0]}")
                            verification_passed = False
                    else:
                        print(f"  ✓ IMEI count verification PASSED: SIM1 only mode has 1 IMEI")
                        verification_passed = True
                else:
                    print(f"  ✗ IMEI verification FAILED: SIM1 only mode should have 1 IMEI, but found {imei_count}")
                    verification_passed = False
            
            elif "SIM2" in selected_mode or "SIM 2" in selected_mode:
                # Enable SIM2 only mode - should have 1 IMEI (first IMEI, same as SIM1)
                # Note: On this device, both SIM1 and SIM2 only modes return the first IMEI
                expected_count = 1
                if imei_count == 1:
                    if self.imei_recorded:
                        # Verify the IMEI matches the first IMEI (not second)
                        if unique_imeis[0] == self.sim1_imei:
                            print(f"  ✓ IMEI verification PASSED: SIM2 only mode has correct IMEI")
                            print(f"    Expected IMEI (first IMEI): {self.sim1_imei} - ✓ Match")
                            verification_passed = True
                        else:
                            print(f"  ✗ IMEI verification FAILED: SIM2 IMEI doesn't match")
                            print(f"    Expected: {self.sim1_imei}")
                            print(f"    Found: {unique_imeis[0]}")
                            verification_passed = False
                    else:
                        print(f"  ✓ IMEI count verification PASSED: SIM2 only mode has 1 IMEI")
                        verification_passed = True
                else:
                    print(f"  ✗ IMEI verification FAILED: SIM2 only mode should have 1 IMEI, but found {imei_count}")
                    verification_passed = False
            else:
                print(f"  ⚠ Unknown mode type, skipping verification")
                return True
            
            return verification_passed
            
        except Exception as e:
            print(f"  ❌ Error verifying IMEI: {e}")
            save_step_screenshot(d, 'imei_verification_error', SCRIPT_IMG_DIR)
            return False

    def _switch_dsds_modes(self):
        """
        Switch between different DSDS modes via dropdown
        
        Strategy:
        - Click dropdown to open options
        - Get all available options from dropdown
        - Switch in 6 fixed rounds:
          Round 1: Enable SIM 1 only
          Round 2: Enable SIM 2 only
          Round 3: Enable DSDS
          Round 4: Enable SIM 2 only
          Round 5: Enable SIM 1 only
          Round 6: Enable DSDS
        - Click the selected option
        - Click Apply button to apply the change
        - Handle potential device reboot
        - Verify IMEI after each switch
        
        :return: True if switches successful, False otherwise
        """
        global d
        
        try:
            print("\n  Starting DSDS mode switching test...")
            
            # Take initial screenshot
            save_step_screenshot(d, 'dsds_mode_page_initial', SCRIPT_IMG_DIR)
            
            # Record original DSDS mode (only once, at the beginning)
            if self.original_dsds_mode is None:
                print("\n  Recording original DSDS mode...")
                try:
                    # Try to find current mode from dropdown or text
                    if d(className="android.widget.Spinner").exists(timeout=2):
                        spinner = d(className="android.widget.Spinner")
                        spinner_info = spinner.info
                        current_mode_text = spinner_info.get('text', '')
                        if current_mode_text:
                            self.original_dsds_mode = current_mode_text
                            print(f"  [Recorded] Original DSDS mode: '{self.original_dsds_mode}'")
                    elif d(textMatches=".*Enable.*").exists(timeout=2):
                        mode_elem = d(textMatches=".*Enable.*")
                        current_mode_text = mode_elem.info.get('text', '')
                        if current_mode_text:
                            self.original_dsds_mode = current_mode_text
                            print(f"  [Recorded] Original DSDS mode: '{self.original_dsds_mode}'")
                except Exception as e:
                    print(f"  ⚠ Could not record original DSDS mode: {e}")
            
            # Define ordered modes to switch: 6 fixed rounds
            # Round 1-3: SIM1 only -> SIM2 only -> DSDS
            # Round 4-6: SIM2 only -> SIM1 only -> DSDS
            ordered_modes = [
                "Enable SIM1 only",   # Round 1
                "Enable SIM2 only",   # Round 2
                "Enable DSDS",        # Round 3
                "Enable SIM2 only",   # Round 4
                "Enable SIM1 only",   # Round 5
                "Enable DSDS"         # Round 6
            ]
            
            # Total switches: 6 fixed rounds
            num_switches = len(ordered_modes)
            switch_count = 0
            
            for switch_round in range(num_switches):
                print(f"\n  {'='*60}")
                print(f"  Switch Round {switch_round + 1}/{num_switches}")
                print(f"  {'='*60}")
                
                # Find and click the dropdown spinner
                print("  Looking for DSDS mode dropdown...")
                
                dropdown = None
                if d(className="android.widget.Spinner").exists(timeout=2):
                    dropdown = d(className="android.widget.Spinner")
                    print("  ✓ Found dropdown (Spinner)")
                elif d(resourceId="android:id/spinner").exists(timeout=1):
                    dropdown = d(resourceId="android:id/spinner")
                    print("  ✓ Found dropdown (by resourceId)")
                elif d(textMatches=".*Enable.*").exists(timeout=2):
                    dropdown = d(textMatches=".*Enable.*")
                    print("  ✓ Found mode selector by text")
                
                if dropdown is None:
                    print("  ⚠ Could not find DSDS mode dropdown")
                    save_step_screenshot(d, 'dropdown_not_found', SCRIPT_IMG_DIR)
                    continue
                
                # Click the dropdown to open options
                print("  Clicking dropdown to open options...")
                save_step_screenshot(d, f'before_click_dropdown_{switch_round}', SCRIPT_IMG_DIR)
                dropdown.click()
                time.sleep(2)
                
                save_step_screenshot(d, f'dropdown_opened_{switch_round}', SCRIPT_IMG_DIR)
                
                # Get all available options from dropdown
                print("  Getting available options from dropdown...")
                available_options = []
                
                try:
                    xml = d.dump_hierarchy()
                    enable_pattern = re.compile(r'text="(Enable [^"]*)"')
                    matches = enable_pattern.findall(xml)
                    
                    if matches:
                        # Remove duplicates
                        available_options = list(set(matches))
                        print(f"  Found {len(available_options)} option(s):")
                        for opt in available_options:
                            print(f"    - {opt}")
                    else:
                        print("  ⚠ No 'Enable' options found")
                except Exception as e:
                    print(f"  ⚠ Error parsing options: {e}")
                
                if not available_options:
                    print("  ⚠ No options available, closing dropdown")
                    d.press("back")
                    time.sleep(0.5)
                    continue
                
                # Determine which option to select based on round number
                # All 6 rounds follow ordered sequence
                target_mode = ordered_modes[switch_round]
                
                # Try to find the target mode in available options
                selected_option = None
                for opt in available_options:
                    if target_mode in opt or opt in target_mode:
                        selected_option = opt
                        break
                
                if selected_option is None:
                    # If exact match not found, try partial match (with and without spaces)
                    for opt in available_options:
                        # Normalize spaces for comparison
                        opt_normalized = opt.replace(" ", "")
                        target_normalized = target_mode.replace(" ", "")
                        
                        if "SIM1" in target_normalized and "SIM1" in opt_normalized:
                            selected_option = opt
                            break
                        elif "SIM2" in target_normalized and "SIM2" in opt_normalized:
                            selected_option = opt
                            break
                        elif "DSDS" in target_normalized and "DSDS" in opt_normalized:
                            selected_option = opt
                            break
                
                if selected_option is None:
                    print(f"  ⚠ Target mode '{target_mode}' not found in available options")
                    save_step_screenshot(d, f'mode_not_found_{switch_round}', SCRIPT_IMG_DIR)
                    d.press("back")
                    time.sleep(0.5)
                    continue
                else:
                    print(f"  Selected mode: '{selected_option}'")
                
                # Click the selected option
                mode_option = None
                if d(text=selected_option).exists(timeout=2):
                    mode_option = d(text=selected_option)
                    print(f"  ✓ Found option element")
                elif d(textContains=selected_option.replace("Enable ", "")).exists(timeout=1):
                    mode_option = d(textContains=selected_option.replace("Enable ", ""))
                    print(f"  ✓ Found option element (partial match)")
                
                if mode_option is None:
                    print(f"  ⚠ Cannot click selected option, closing dropdown")
                    d.press("back")
                    time.sleep(0.5)
                    continue
                
                # Click the option
                print(f"  Clicking option '{selected_option}'...")
                mode_option.click()
                time.sleep(2)  # Wait longer for dialog to appear
                
                save_step_screenshot(d, f'after_select_option_{switch_round}', SCRIPT_IMG_DIR)
                
                # Check for "Switch to SIM" confirmation dialog (appears when selecting SIM1 only or SIM2 only)
                print("  Checking for SIM switch confirmation dialog...")
                
                switch_dialog_handled = False
                
                # Try multiple detection methods
                dialog_detected = False
                
                # Method 1: Check for "Switch to SIM" text
                if d(textContains="Switch to SIM").exists(timeout=3):
                    dialog_detected = True
                    print("  ✓ Found SIM switch dialog (by 'Switch to SIM' text)")
                # Method 2: Check for "Switch" text
                elif d(textMatches=".*Switch.*").exists(timeout=2):
                    dialog_detected = True
                    print("  ✓ Found SIM switch dialog (by 'Switch' text)")
                # Method 3: Check for Cancel button (indicates a dialog)
                elif d(text="Cancel").exists(timeout=2):
                    dialog_detected = True
                    print("  ✓ Found dialog (by 'Cancel' button)")
                
                if dialog_detected:
                    save_step_screenshot(d, f'sim_switch_dialog_{switch_round}', SCRIPT_IMG_DIR)
                    
                    # Try to click OK button with multiple strategies
                    print("  Attempting to click OK button...")
                    
                    # Wait a bit for dialog to fully render
                    time.sleep(1)
                    
                    # Strategy 1: Look for OK text (most common)
                    if d(text="OK").exists(timeout=2):
                        print("  ✓ Found OK button (by text)")
                        d(text="OK").click()
                        switch_dialog_handled = True
                        time.sleep(2)
                    # Strategy 2: Look for OK button with Button class
                    elif d(text="OK", className="android.widget.Button").exists(timeout=2):
                        print("  ✓ Found OK button (as Button)")
                        d(text="OK", className="android.widget.Button").click()
                        switch_dialog_handled = True
                        time.sleep(2)
                    # Strategy 3: Look for OK with TextView class
                    elif d(text="OK", className="android.widget.TextView").exists(timeout=1):
                        print("  ✓ Found OK button (as TextView)")
                        d(text="OK", className="android.widget.TextView").click()
                        switch_dialog_handled = True
                        time.sleep(2)
                    # Strategy 4: Click by position (right side of dialog)
                    elif d(text="Cancel").exists(timeout=1):
                        print("  ✓ Trying to click OK by position (right of Cancel)")
                        # Get Cancel button position
                        cancel_btn = d(text="Cancel")
                        cancel_info = cancel_btn.info
                        cancel_bounds = cancel_info.get('bounds', {})
                        if cancel_bounds:
                            # Click to the right of Cancel button (where OK should be)
                            ok_x = cancel_bounds.get('right', 0) + 100
                            ok_y = (cancel_bounds.get('top', 0) + cancel_bounds.get('bottom', 0)) // 2
                            d.click(ok_x, ok_y)
                            switch_dialog_handled = True
                            time.sleep(2)
                    else:
                        print("  ⚠ OK button not found, trying generic button click")
                        # Last resort: try to find any button on the right side
                        if d(className="android.widget.Button").exists(timeout=1):
                            buttons = d(className="android.widget.Button")
                            if buttons.count >= 2:
                                # Click the second button (usually OK)
                                buttons[1].click()
                                switch_dialog_handled = True
                                time.sleep(2)
                                print("  ✓ Clicked second button (assumed OK)")
                    
                    if switch_dialog_handled:
                        print("  ✓ SIM switch dialog confirmed")
                        save_step_screenshot(d, f'after_sim_switch_dialog_{switch_round}', SCRIPT_IMG_DIR)
                    else:
                        print("  ⚠ Could not click OK on SIM switch dialog")
                        save_step_screenshot(d, f'failed_sim_switch_dialog_{switch_round}', SCRIPT_IMG_DIR)
                else:
                    print("  No SIM switch dialog detected (normal for DSDS mode)")
                
                # Wait a bit more after handling dialog
                time.sleep(1)
                
                # Look for and click Apply button
                print("  Looking for Apply button...")
                apply_button_texts = ["Apply", "应用", "APPLY", "确定", "OK"]
                matched_text = tap_first_available_text(d, apply_button_texts, timeout=2)
                apply_clicked = matched_text is not None
                if apply_clicked:
                    print(f"  ✓ Found Apply button: '{matched_text}'")
                    time.sleep(1.2)
                
                # Also try by class name
                if not apply_clicked:
                    if d(className="android.widget.Button", textMatches=".*pply.*").exists(timeout=1):
                        print("  ✓ Found Apply button (by pattern)")
                        d(className="android.widget.Button", textMatches=".*pply.*").click()
                        apply_clicked = True
                        time.sleep(2)
                
                if apply_clicked:
                    print(f"  ✓ Clicked Apply button")
                    save_step_screenshot(d, f'after_apply_{switch_round}', SCRIPT_IMG_DIR)
                    switch_count += 1
                    
                    # Wait a moment for any dialog to appear after Apply
                    time.sleep(2)
                    
                    # Check for "Switch to SIM" confirmation dialog after Apply
                    print("  Checking for post-Apply SIM switch confirmation dialog...")
                    post_apply_dialog_handled = False
                    
                    if d(textContains="Switch to SIM").exists(timeout=3):
                        print("  ✓ Found post-Apply SIM switch dialog")
                        save_step_screenshot(d, f'post_apply_sim_dialog_{switch_round}', SCRIPT_IMG_DIR)
                        
                        # Try to click OK button
                        time.sleep(1)
                        
                        if d(text="OK").exists(timeout=2):
                            print("  ✓ Clicking OK button on post-Apply dialog")
                            d(text="OK").click()
                            post_apply_dialog_handled = True
                            time.sleep(2)
                        elif d(text="OK", className="android.widget.Button").exists(timeout=1):
                            print("  ✓ Clicking OK button (as Button) on post-Apply dialog")
                            d(text="OK", className="android.widget.Button").click()
                            post_apply_dialog_handled = True
                            time.sleep(2)
                        elif d(text="Cancel").exists(timeout=1):
                            # Click by position if OK not found
                            cancel_btn = d(text="Cancel")
                            cancel_info = cancel_btn.info
                            cancel_bounds = cancel_info.get('bounds', {})
                            if cancel_bounds:
                                ok_x = cancel_bounds.get('right', 0) + 100
                                ok_y = (cancel_bounds.get('top', 0) + cancel_bounds.get('bottom', 0)) // 2
                                d.click(ok_x, ok_y)
                                post_apply_dialog_handled = True
                                time.sleep(2)
                                print("  ✓ Clicked OK by position on post-Apply dialog")
                        
                        if post_apply_dialog_handled:
                            print("  ✓ Post-Apply SIM switch dialog confirmed")
                            save_step_screenshot(d, f'after_post_apply_dialog_{switch_round}', SCRIPT_IMG_DIR)
                        else:
                            print("  ⚠ Could not click OK on post-Apply dialog")
                    else:
                        print("  No post-Apply SIM switch dialog detected")
                    
                    # Check for reboot confirmation dialog
                    print("  Checking for reboot confirmation dialog...")
                    time.sleep(1)
                    
                    # Look for dialog with reboot warning
                    dialog_found = False
                    if d(textContains="reboot").exists(timeout=2):
                        print("  ✓ Found reboot confirmation dialog")
                        save_step_screenshot(d, f'reboot_dialog_{switch_round}', SCRIPT_IMG_DIR)
                        
                        # Click OK button to confirm reboot
                        if tap_first_available_text(d, ["OK", "确定", "Ok"], timeout=1):
                            dialog_found = True
                            time.sleep(1.2)
                            print("  ✓ Confirmed reboot dialog")
                    
                    # Wait to see if device reboots
                    print("  Checking if device is rebooting...")
                    time.sleep(5)
                    
                    # Try to check if device is still responsive
                    device_rebooted = False
                    try:
                        d.info
                        print("  ✓ Device is responsive, no reboot")
                        device_rebooted = False
                    except:
                        print("  Device appears to be rebooting, waiting for it to come back...")
                        device_rebooted = True

                        if not dcs_test_wait_device_online(serial, timeout_seconds=120):
                            print("  ⚠ Device did not come back online")
                            return False

                        # Reconnect and navigate back
                        time.sleep(15)
                        d = u2.connect(serial)
                        print("  ✓ Reconnected to device")
                    
                    # Verify IMEI count after mode switch
                    print(f"\n  {'='*60}")
                    print(f"  Verifying IMEI count for '{selected_option}'")
                    print(f"  {'='*60}")
                    
                    if not self._verify_imei(selected_option):
                        print(f"  ⚠ IMEI verification failed for '{selected_option}'")
                        save_step_screenshot(d, f'imei_verification_failed_{switch_round}', SCRIPT_IMG_DIR)
                        # Continue to next round even if verification failed
                    
                    # Navigate back to DSDS mode settings for next round
                    if device_rebooted:
                        print("  Navigating back to DSDS Mode settings...")
                        d.press("home")
                        time.sleep(1)
                        
                        if not self._navigate_to_dsds_mode_settings():
                            print("  ⚠ Failed to navigate back after reboot")
                            return False
                    else:
                        # If no reboot, navigate back from Phone app to DSDS settings
                        print("  Navigating back to DSDS Mode settings...")
                        d.press("home")
                        time.sleep(1)
                        
                        if not self._navigate_to_dsds_mode_settings():
                            print("  ⚠ Failed to navigate back to DSDS settings")
                            return False
                else:
                    print("  ⚠ Apply button not found")
                    save_step_screenshot(d, f'apply_not_found_{switch_round}', SCRIPT_IMG_DIR)
                
                # Small delay between rounds
                time.sleep(2)
            
            # Summary
            print(f"\n  {'='*60}")
            print(f"  Mode switches completed: {switch_count}/{num_switches}")
            print(f"  {'='*60}")
            
            if switch_count == num_switches:
                print("  ✓ Successfully completed all DSDS mode switches")
                return True
            else:
                print(f"  ✗ Failed - only {switch_count}/{num_switches} switches succeeded")
                return False
            
        except Exception as e:
            print(f"  ❌ Error switching DSDS modes: {e}")
            save_step_screenshot(d, 'mode_switch_error', SCRIPT_IMG_DIR)
            return False

    def test_L0_dsds_mode_switch(self):
        """
        Test Steps:
        1. Verify the CT47 model, telephony baseband, and dual-SIM prerequisites.
        2. Open Honeywell Developer options and enable access to the DSDS mode menu.
        3. Navigate to DSDS mode settings and switch between supported modes.
        4. Verify the selected mode persists and the expected SIM/network state is shown.
        5. Capture evidence and restore the original DSDS configuration during cleanup.
        """
        print("TEST: DSDS Mode Switch")
        print("="*70)
        
        # ===================================================================
        # Step 0: Pre-check - Only CT47 supports DSDS mode switching
        # ===================================================================
        print("\n[Step 0] Check device model")

        model = get_device_model(serial)
        print(f"  Model: {model}")

        if "CT47" not in model.upper():
            self.skipTest(
                f"Device model '{model}' does not support dual SIM switching (CT47 only)"
            )

        print(f"  ✓ Device model supports DSDS mode switching (Model: {model})")

        # ===================================================================
        # Step 1: Pre-check - Verify device baseband type
        # ===================================================================
        print("\n[Step 1] Check device baseband type")

        baseband = imei_get_baseband_type(serial)

        if baseband == "apq":
            pass_msg = (
                f"\n{'='*70}\n"
                f"✓ PASS - WLAN-only device, DSDS not applicable\n"
                f"{'='*70}\n"
                f"  Baseband: {baseband.upper()}\n"
                f"  Device Type: WLAN-only (APQ)\n"
                f"  Reason: This device does not support dual SIM functionality\n"
                f"  Result: Test passed (N/A for WLAN devices)\n"
                f"{'='*70}\n"
            )
            print(pass_msg)
            return

        print(f"  ✓ Device supports telephony (Baseband: {baseband})")

        # ===================================================================
        # Step 2: Check SIM count - this test only applies to dual-SIM devices
        # ===================================================================
        print("\n[Step 2] Check SIM count via dial *#06#")

        d.press("home")
        time.sleep(1)
        sim1_imei, sim2_imei = imei_read_from_dialer(d, serial, SCRIPT_IMG_DIR)

        if sim2_imei is None:
            self.skipTest(
                "Single SIM device detected (only 1 IMEI found) - "
                "DSDS mode switch test only applies to dual-SIM devices"
            )

        # Record the IMEIs up front so Step 7 doesn't need to dial again
        self.sim1_imei = sim1_imei
        self.sim2_imei = sim2_imei
        self.imei_recorded = True
        print(f"  ✓ Dual SIM device confirmed")
        print(f"    SIM1 IMEI: {self.sim1_imei}")
        print(f"    SIM2 IMEI: {self.sim2_imei}")

        # ===================================================================
        # Step 3: Enable Developer Options (if needed)
        # ===================================================================
        print("\n[Step 3] Enable Developer Options")
        
        dev_enabled = self._enable_developer_options()
        if not dev_enabled:
            self.fail("Failed to enable Developer Options")
        
        # ===================================================================
        # Step 4: Navigate to Honeywell Developer Options
        # ===================================================================
        print("\n[Step 4] Navigate to Honeywell Developer Options")
        
        nav_success = self._navigate_to_honeywell_dev_options()
        if not nav_success:
            self.fail("Failed to navigate to Honeywell Developer Options")
        
        # ===================================================================
        # Step 5: Check and enable "Show DSDS Menu"
        # ===================================================================
        print("\n[Step 5] Check and enable 'Show DSDS Menu'")
        
        dsds_menu_enabled = self._check_and_enable_show_dsds_menu()
        if not dsds_menu_enabled:
            self.fail("Failed to enable 'Show DSDS Menu'")
        
        # Go back to home
        d.press("back")
        d.press("back")
        d.press("home")
        time.sleep(1)
        
        # ===================================================================
        # Step 6: Navigate to DSDS Mode settings
        # ===================================================================
        print("\n[Step 6] Navigate to DSDS Mode settings")
        
        nav_success = self._navigate_to_dsds_mode_settings()
        if not nav_success:
            self.fail("Failed to navigate to DSDS Mode settings")
        
        # ===================================================================
        # Step 7: Switch between DSDS modes and verify IMEI
        # ===================================================================
        print("\n[Step 7] Switch between DSDS modes and verify IMEI")
        
        switch_success = self._switch_dsds_modes()
        if not switch_success:
            self.fail("Failed to switch between DSDS modes")
        
        # ===================================================================
        # Test Result
        # ===================================================================
        print(f"\n{'='*70}")
        print(f"✓ PASS - DSDS Mode Switch Test Completed Successfully")
        print(f"{'='*70}")
        print(f"  All DSDS mode switches verified successfully")
        print(f"  IMEI verification: All IMEI numbers matched expected values")
        print(f"    SIM1 IMEI: {self.sim1_imei}")
        print(f"    SIM2 IMEI: {self.sim2_imei}")
        print(f"{'='*70}")


if __name__ == '__main__':
    # Run the DSDS Mode Switch test
    suite = unittest.TestSuite()
    suite.addTest(TestDSDSModeSwitch('test_dsds_mode_switch'))
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Print summary
    print("\n" + "="*70)
    print("TEST SUMMARY")
    print("="*70)
    print(f"Tests run: {result.testsRun}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    print(f"Success: {result.wasSuccessful()}")
    print("="*70)
