# __author__ = 'sophy'
# -*- coding:utf-8 -*-
"""
Test case: ANDROIDCN-36298 - IMEI consistency between Dialer and Settings.

Test Steps:
1. Identify the device baseband type; treat WLAN-only APQ devices as not applicable
    and use the single Settings IMEI flow for CK67 devices.
2. For telephony-capable devices, open the Phone application, dial `*#06#`, and
    read and validate the displayed IMEI value for each available SIM slot.
3. Open Settings > About phone, read the IMEI value for SIM slot 1 and, on dual-SIM
    devices, SIM slot 2; capture evidence of each value.
4. Validate every retrieved IMEI format and compare each Settings value with the
    matching Dialer value.
5. Close Dialer and Settings and return to Home during cleanup.
"""
import unittest
import os
import sys
import time
from common.adb_common import get_device_model, save_step_screenshot, imei_get_baseband_type, imei_open_about_phone
from common.common_method import (
    imei_is_valid,
    imei_read_from_dialer,
    imei_read_sim_imei_from_settings,
)
import uiautomator2 as u2
import subprocess

# Add parent path to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))



# Connect device via ANDROID_SERIAL environment variable
serial = os.environ.get('ANDROID_SERIAL')
d = u2.connect(serial)

SCRIPT_BASENAME = os.path.splitext(os.path.basename(__file__))[0]
IMG_ROOT = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.realpath(__file__)))), "img")
SCRIPT_IMG_DIR = os.path.join(IMG_ROOT, SCRIPT_BASENAME)
os.makedirs(SCRIPT_IMG_DIR, exist_ok=True)

class Test_IMEI_Check(unittest.TestCase):
    """
    Test case: Check IMEI information consistency
    Verifies that IMEI shown via *#06# dialer code matches IMEI in Settings -> About phone
    """

    @classmethod
    def setUpClass(cls):
        """Test class initialization"""
        cls.device = serial
        # cls.adb = AdbCommand()
        print(f"\n========== IMEI Check Test ==========")
        print(f"Test Device: {cls.device}")

    def setUp(self):
        """Setup before each test"""
        print("\n" + "="*60)
        # Go to home screen
        d.press("home")
        time.sleep(1)

    def tearDown(self):
        """Cleanup after each test"""
        print("="*60)
        # Close Phone app
        print("[tearDown] Closing Phone app...")
        subprocess.run(f'adb -s {serial} shell am force-stop com.android.dialer', shell=True)
        subprocess.run(f'adb -s {serial} shell am force-stop com.google.android.dialer', shell=True)
        time.sleep(0.5)
       # Close Settings app 
        subprocess.run(f'adb -s {serial} shell am force-stop com.android.settings', shell=True)
        d.press('home')
        print("[tearDown] Cleanup completed")

    def test_L0_imei_consistency_check(self):
        """
        Test Steps:
        1. Identify the baseband type and select the applicable IMEI flow.
        2. On telephony devices, dial `*#06#` and validate each displayed IMEI.
        3. Read the matching IMEI value or values from Settings > About phone.
        4. Capture evidence and verify each Settings value matches its Dialer value.
        5. Close the Phone and Settings applications during teardown.
        """
        print("TEST: Check IMEI Consistency")
        print("="*60)
        
        # ===================================================================
        # Step 0: Check device baseband type
        # ===================================================================
        print("\n[Step 0] Check device baseband type")

        baseband = imei_get_baseband_type(serial)
        device_model = get_device_model(serial).strip().upper()
        print(f"Using serial: {serial!r}")
        print(f"  Baseband: {baseband}")
        print(f"  Device model: {device_model or 'unknown'}")

        if device_model.startswith("CK67"):
            print("\n[CK67] Read the single IMEI from Settings -> About phone")
            imei_open_about_phone(serial)
            settings_imei = imei_read_sim_imei_from_settings(
                d, "sim slot 1", allow_plain_imei_label=True
            )
            save_step_screenshot(d, 'ck67_imei_details', SCRIPT_IMG_DIR)
            self.assertIsNotNone(settings_imei, "Could not read the IMEI value from CK67 About phone")
            print(f"  ✓ PASS - CK67 IMEI: {settings_imei}")
            return

        if baseband == "apq":
            pass_msg = (
                f"\n{'='*60}\n"
                f"✓ PASS - WLAN-only device, IMEI test not applicable\n"
                f"{'='*60}\n"
                f"  Baseband: {baseband.upper()}\n"
                f"  Device Type: WLAN-only (APQ)\n"
                f"  Reason: This device does not support telephony/IMEI\n"
                f"  Result: Test passed (N/A for WLAN devices)\n"
                f"{'='*60}\n"
            )
            print(pass_msg)
            # Return directly, skip all remaining test steps
            return
        elif baseband == "msm":
            print(f"  ✓ Device supports telephony (MSM) - IMEI test will proceed")
        else:
            print(f"  ⚠ Unknown baseband type: {baseband}")
            print(f"  Proceeding with test anyway...")

        # Initialize IMEI variables
        dialer_sim1_imei = None
        dialer_sim2_imei = None
        settings_sim1_imei = None
        settings_sim2_imei = None

        # ===================================================================
        # Step 1: Open Phone app and dial *#06# to get IMEI codes
        # ===================================================================
        print("\n[Step 1] Open Phone app and dial *#06#")

        try:
            d.press("home")
            time.sleep(1)

            dialer_sim1_imei, dialer_sim2_imei = imei_read_from_dialer(d, serial, SCRIPT_IMG_DIR)

            if dialer_sim1_imei is None:
                save_step_screenshot(d, 'no_imei_in_dialog', SCRIPT_IMG_DIR)
                self.fail("Failed to extract IMEI codes from *#06# dialog - IMEI is null")

            if dialer_sim2_imei:
                print(f"  ✓ Dual SIM device detected")
                print(f"    SIM1 IMEI: {dialer_sim1_imei}")
                print(f"    SIM2 IMEI: {dialer_sim2_imei}")
            else:
                print(f"  ✓ Single SIM device detected")
                print(f"    SIM1 IMEI: {dialer_sim1_imei}")

            # Validate SIM1 IMEI (required)
            is_valid, msg = imei_is_valid(dialer_sim1_imei)
            if not is_valid:
                save_step_screenshot(d, 'invalid_sim1_imei', SCRIPT_IMG_DIR)
                self.fail(f"SIM1 IMEI validation failed: {msg}")

            # Validate SIM2 IMEI (if dual SIM)
            if dialer_sim2_imei:
                is_valid, msg = imei_is_valid(dialer_sim2_imei)
                if not is_valid:
                    save_step_screenshot(d, 'invalid_sim2_imei', SCRIPT_IMG_DIR)
                    self.fail(f"SIM2 IMEI validation failed: {msg}")

        except Exception as e:
            save_step_screenshot(d, 'dialer_error', SCRIPT_IMG_DIR)
            print(f"  ❌ Error during dialer IMEI check: {e}")
            self.fail(f"Failed to get IMEI from dialer: {e}")

        # ===================================================================
        # Step 2: Navigate to Settings -> About phone to get IMEI
        # ===================================================================
        print("\n[Step 2] Navigate to Settings -> About phone")

        try:
            imei_open_about_phone(serial)

            # Now in About phone page, scroll to find IMEI menu items
            print("\n  Scrolling to find IMEI menu items...")
            if not d(textContains="IMEI").exists(timeout=2):
                for _ in range(8):
                    d(scrollable=True).scroll.forward()
                    time.sleep(0.5)
                    if d(textContains="IMEI").exists(timeout=1):
                        print("  Found IMEI menu items")
                        break

            save_step_screenshot(d, 'about_phone_imei_menu', SCRIPT_IMG_DIR)

            # Dialer step already told us whether this is a single- or dual-SIM device
            is_dual_sim = dialer_sim2_imei is not None

            # ===================================================================
            # Read IMEI (sim slot 1) / plain IMEI on single-SIM devices
            # ===================================================================
            print("\n  Entering IMEI (sim slot 1) menu...")
            settings_sim1_imei = imei_read_sim_imei_from_settings(
                d, "sim slot 1", allow_plain_imei_label=not is_dual_sim
            )
            if settings_sim1_imei is None:
                save_step_screenshot(d, 'sim1_menu_click_failed', SCRIPT_IMG_DIR)
                self.fail("Could not find/click 'IMEI (sim slot 1)' menu item")
            print(f"    ✓ Settings SIM1 IMEI: {settings_sim1_imei}")
            save_step_screenshot(d, 'sim1_imei_details', SCRIPT_IMG_DIR)
            print("    Returned to About phone page")

            # ===================================================================
            # Read IMEI (sim slot 2), only for dual-SIM devices
            # ===================================================================
            if not is_dual_sim:
                settings_sim2_imei = None
                print("\n  Single SIM device (per dialer result), skipping IMEI (sim slot 2) lookup")
            else:
                print("\n  Entering IMEI (sim slot 2) menu...")
                settings_sim2_imei = imei_read_sim_imei_from_settings(
                    d, "sim slot 2", exclude_imei=settings_sim1_imei
                )
                if settings_sim2_imei is None:
                    print("    INFO: Could not find 'IMEI (sim slot 2)' menu item")
                else:
                    print(f"    ✓ Settings SIM2 IMEI: {settings_sim2_imei}")
                    save_step_screenshot(d, 'sim2_imei_details', SCRIPT_IMG_DIR)
                    print("    Returned to About phone page")

            # Verify and validate SIM1 IMEI from Settings
            is_valid, msg = imei_is_valid(settings_sim1_imei)
            if not is_valid:
                save_step_screenshot(d, 'settings_invalid_sim1', SCRIPT_IMG_DIR)
                self.fail(f"Settings SIM1 IMEI validation failed: {msg}")

            # Validate SIM2 IMEI from Settings if exists
            if settings_sim2_imei:
                is_valid, msg = imei_is_valid(settings_sim2_imei)
                if not is_valid:
                    save_step_screenshot(d, 'settings_invalid_sim2', SCRIPT_IMG_DIR)
                    self.fail(f"Settings SIM2 IMEI validation failed: {msg}")

            print(f"\n  Settings IMEI Summary:")
            print(f"    SIM1 IMEI: {settings_sim1_imei}")
            print(f"    SIM2 IMEI: {settings_sim2_imei or 'Not found'}")

        except Exception as e:
            save_step_screenshot(d, 'settings_error', SCRIPT_IMG_DIR)
            print(f"  ❌ Error during Settings IMEI check: {e}")
            raise

        # ===================================================================
        # Step 3: Compare IMEI codes from dialer and Settings
        # ===================================================================
        print("\n[Step 3] Compare IMEI values")
        print("="*60)
        
        # Compare SIM1 IMEI
        print(f"\nSIM1 IMEI Comparison:")
        print(f"  Dialer:   {dialer_sim1_imei}")
        print(f"  Settings: {settings_sim1_imei}")
 
        
        if dialer_sim1_imei ==  settings_sim1_imei:
            print(f"  ✓ SIM1 IMEI MATCH")
        else:
            error_msg = (f"\n❌ FAIL - SIM1 IMEI values do not match\n"
                        f"  Dialer:   {dialer_sim1_imei}\n"
                        f"  Settings: {settings_sim1_imei}")
            print(error_msg)
            save_step_screenshot(d, 'sim1_mismatch', SCRIPT_IMG_DIR)
            self.fail(error_msg)
        
        # Compare SIM2 IMEI if both sources have it
        if dialer_sim2_imei and settings_sim2_imei:
            
            print(f"\nSIM2 IMEI Comparison:")
            print(f"  Dialer:   {dialer_sim2_imei}")
            print(f"  Settings: {settings_sim2_imei}")
            
            if dialer_sim2_imei == settings_sim2_imei:
                print(f"  ✓ SIM2 IMEI MATCH")
            else:
                error_msg = (f"\n❌ FAIL - SIM2 IMEI values do not match\n"
                            f"  Dialer:   {dialer_sim2_imei}\n"
                            f"  Settings: {settings_sim2_imei}")
                print(error_msg)
                save_step_screenshot(d, 'sim2_mismatch', SCRIPT_IMG_DIR)
                self.fail(error_msg)
        elif dialer_sim2_imei or settings_sim2_imei:
            # One source has SIM2, the other doesn't - this is a FAIL
            error_msg = (f"\n❌ FAIL - SIM2 IMEI count mismatch\n"
                        f"  Dialer SIM2:   {dialer_sim2_imei or 'None'}\n"
                        f"  Settings SIM2: {settings_sim2_imei or 'None'}\n"
                        f"  Both sources must have same number of IMEI codes")
            print(error_msg)
            save_step_screenshot(d, 'sim2_count_mismatch', SCRIPT_IMG_DIR)
            self.fail(error_msg)
        
        # Final result - PASS
        print(f"\n{'='*60}")
        print(f"✓ PASS - All IMEI values match successfully")
        print(f"  SIM1 IMEI: {dialer_sim1_imei}")
        if dialer_sim2_imei:
            print(f"  SIM2 IMEI: {dialer_sim2_imei}")
        print(f"{'='*60}")


if __name__ == '__main__':
    # Run the IMEI consistency test
    suite = unittest.TestSuite()
    suite.addTest(TestIMEICheck('test_imei_consistency_check'))
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Print summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    print(f"Tests run: {result.testsRun}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    print(f"Success: {result.wasSuccessful()}")
    print("="*60)
