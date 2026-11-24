# __author__ = 'sophy'
# -*- coding:utf-8 -*-

"""
RTC (Real Time Clock) Test - Automated Version

Tests that system date persists after a soft reboot.

Test Steps:
1. Automatically set date via Settings UI to a future date (current + 1 day)
2. Soft reset: adb reboot
3. Verify date is unchanged after soft reset

Features:
- Fully automated date setting via UI automation (uiautomator2)
- No root permission required
- No manual intervention needed
- Test date auto-generated (current date + 1 day)
- Validates date persistence after soft reset (adb reboot)

Note: If automated date setting fails, it may be due to:
  - Non-standard Settings UI on device
  - Device policy enforcing automatic date/time
  - Different UI element IDs/text
"""

import unittest
import os
import sys
import time
from datetime import datetime, timedelta

# Add project root before importing shared modules.
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from uiautomator import device
from common.adb_common import get_system_date,save_step_screenshot
from common.common_method import (
    close_settings_app,
    rtc_enable_automatic_time,
    rtc_soft_reboot_and_wait,
    rtc_set_date_via_settings_ui,
)
import uiautomator2 as u2

# Connect device via ANDROID_SERIAL environment variable
serial = os.environ.get('ANDROID_SERIAL')
d = u2.connect(serial)

SCRIPT_BASENAME = os.path.splitext(os.path.basename(__file__))[0]
IMG_ROOT = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.realpath(__file__)))), "img")
SCRIPT_IMG_DIR = os.path.join(IMG_ROOT, SCRIPT_BASENAME)
os.makedirs(SCRIPT_IMG_DIR, exist_ok=True)

class Test_RTC(unittest.TestCase):
    """
    Test case: RTC (Real Time Clock) Test
    Verify that system date persists after device reboot
    """

    @classmethod
    def setUpClass(cls):
        """Test class initialization"""
        cls.device = serial
        
        # Get device system date and add 7 days as test date
        device_date_str = get_system_date(serial)
        if not device_date_str:
            # Fallback: use local time if unable to get device date
            print("Warning: Failed to get device system date, using local time as fallback")
            device_date = datetime.now()
        else:
            # Parse device date (format: "YYYY-MM-DD")
            device_date = datetime.strptime(device_date_str, "%Y-%m-%d")
        
        # Test date: device current date + 1 day
        future_date = device_date + timedelta(days=1)
        cls.test_date = future_date.strftime("%Y%m%d")
        cls.test_year = cls.test_date[:4]
        cls.test_month = cls.test_date[4:6]
        cls.test_day = cls.test_date[6:8]
        
        print(f"\n========== RTC Test ==========")
        print(f"Test Device: {cls.device}")
        print(f"Device Current Date: {device_date_str}")
        print(f"Test Date (Device Date + 1 day): {cls.test_year}-{cls.test_month}-{cls.test_day}")

    def setUp(self):
        """Setup before each test"""
        print("\n" + "="*60)
        d.press("home")
        time.sleep(1)
        # Ensure class attributes exist (defensive programming)
        if not hasattr(Test_RTC, 'test_year'):
            # If setUpClass wasn't called, initialize here using device date
            device_date_str = get_system_date(serial)
            if not device_date_str:
                print("Warning: Failed to get device system date, using local time as fallback")
                device_date = datetime.now()
            else:
                device_date = datetime.strptime(device_date_str, "%Y-%m-%d")
            
            future_date = device_date + timedelta(days=1)
            Test_RTC.test_date = future_date.strftime("%Y%m%d")
            Test_RTC.test_year = Test_RTC.test_date[:4]
            Test_RTC.test_month = Test_RTC.test_date[4:6]
            Test_RTC.test_day = Test_RTC.test_date[6:8]
            Test_RTC.device = serial
            print(f"Warning: setUpClass not called, initializing in setUp")
            print(f"Device Current Date: {device_date_str}")
            print(f"Test Date (Device Date + 1 day): {Test_RTC.test_year}-{Test_RTC.test_month}-{Test_RTC.test_day}")
        
        # Set instance attributes as well
        self.dev_id = serial
        self.device = d
        self.test_year = Test_RTC.test_year
        self.test_month = Test_RTC.test_month
        self.test_day = Test_RTC.test_day
        
        

    def tearDown(self):
        """Cleanup after each test"""
        print("="*60)
        #close set time automatically to ON after test
        rtc_enable_automatic_time(self.device, self.dev_id)

         # Close Settings app 
        close_settings_app(serial)

        d.press('home')
        time.sleep(0.5)

    def _set_date_via_settings_ui(self, year, month, day):
        """Thin wrapper: delegate heavy UI flow to common_method helper."""
        fallback = getattr(self, '_set_date_manual_navigation', None)
        return rtc_set_date_via_settings_ui(
            device=d,
            serial=serial,
            year=year,
            month=month,
            day=day,
            img_dir=SCRIPT_IMG_DIR,
            manual_fallback=fallback,
        )

    def test_L0_rtc(self):
        """
        Verify RTC date persists after soft reset.

        Test Steps:
        1. Automatically set date via Settings UI (using uiautomator2)
        2. Soft reset (adb reboot) and verify date
        """
        global d, serial
        
        print("TEST: RTC Date Persistence")
        print("="*60)

        expected_date = f"{Test_RTC.test_year}-{Test_RTC.test_month}-{Test_RTC.test_day}"

        # ===================================================================
        # Step 1: Set date via Settings UI (Automated)
        # ===================================================================
        print("\n[Step 1] Set date via Settings UI")
        print(f"  Target date: {expected_date}")
        
        # Automatically set date via Settings UI
        set_result = self._set_date_via_settings_ui(
            Test_RTC.test_year, 
            Test_RTC.test_month, 
            Test_RTC.test_day
        )
        
        if not set_result:
            print(f"  ⚠ Automated date setting may have failed")
            print(f"  Please check if date was set correctly")
        
        # Verify date was set
        time.sleep(2)
        current_date = get_system_date(serial)
        print(f"  Current date: {current_date}")
        
        if current_date != expected_date:
            error_msg = (
                f"\n❌ FAIL - Failed to set date\n"
                f"  Expected: {expected_date}\n"
                f"  Got:      {current_date}\n"
                f"\n"
                f"  Possible reasons:\n"
                f"  1. Device Settings UI differs from standard Android\n"
                f"  2. Automatic date/time is enforced by device policy\n"
                f"  3. UI elements have different IDs/text\n"
            )
            print(error_msg)
            save_step_screenshot(d, "date_set_failed", SCRIPT_IMG_DIR)
            self.fail(error_msg)
        
        print(f"  ✓ Date set successfully: {current_date}")
        save_step_screenshot(d, "date_set_complete", SCRIPT_IMG_DIR)
        time.sleep(20)

        # ===================================================================
        # Step 2: Soft reset (adb reboot)
        # ===================================================================
        print("\n[Step 2] Soft reset device (adb reboot)")
        print("  Waiting for device to reboot (60 seconds)...")
        if rtc_soft_reboot_and_wait(serial, initial_wait_sec=60, checks=12, interval_sec=10):
            print("  ✓ Soft reset completed")
        else:
            self.fail("\n❌ FAIL - Soft reset boot completion check failed")
        
        time.sleep(5)
        
        # Reconnect uiautomator2
        d = u2.connect(serial)
        d.press("home")
        time.sleep(2)
        
        save_step_screenshot(d, "after_soft_reset",SCRIPT_IMG_DIR)

        # ===================================================================
        # Step 3: Verify date after soft reset
        # ===================================================================
        print("\n[Step 3] Verify date after soft reset")
        current_date = get_system_date(serial)
        
        print(f"  Expected date: {expected_date}")
        print(f"  Current date:  {current_date}")
        
        if current_date != expected_date:
            error_msg = (
                f"\n❌ FAIL - Date changed after soft reset\n"
                f"  Expected: {expected_date}\n"
                f"  Got:      {current_date}\n"
                f"\n"
                f"  RTC did not persist the date through soft reset!"
            )
            print(error_msg)
            save_step_screenshot(d, "soft_reset_date_mismatch", SCRIPT_IMG_DIR)
            self.fail(error_msg)
        
        print(f"  ✓ Date verified after soft reset: {current_date}")

        # Final result - PASS
        print(f"\n{'='*60}")
        print(f"✓ PASS - RTC date persisted through soft reset")
        print(f"  Test date: {expected_date}")
        print(f"  Verified after soft reset: ✓")
        print(f"{'='*60}")



if __name__ == '__main__':
    # Run the RTC test
    suite = unittest.TestSuite()
    suite.addTest(Test_RTC('test_rtc_date_persistence'))
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
