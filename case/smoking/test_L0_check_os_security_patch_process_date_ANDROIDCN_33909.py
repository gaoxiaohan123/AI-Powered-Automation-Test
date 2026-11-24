# __author__ = 'sophy'
# -*- coding:utf-8 -*-
"""
Test case: ANDROIDCN-33909 - Android security patch level date validation.

Test Steps:
1. Read the Android security patch level from the connected device.
2. Verify the returned value is non-empty and parse it as an ISO `YYYY-MM-DD` date.
3. Verify the date day component is one of the approved patch release values:
    `01`, `05`, or `06`.
4. Report the full parsed patch date and fail with the invalid value when validation
    does not pass.
"""
import importlib
import unittest
import os
import sys
from datetime import datetime
from common.adb_common import save_step_screenshot, get_security_patch_level
import uiautomator2 as u2


# Add parent path to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# Connect device via ANDROID_SERIAL environment variable
serial = os.environ.get('ANDROID_SERIAL')
d = u2.connect(serial)


class Test_L0_Security_Patch_Date(unittest.TestCase):
    """
    Test case: Check Android security patch level date
    Only accept patch dates with day value 01, 05, or 06
    """

    @classmethod
    def setUpClass(cls):
        """Test class initialization"""
        cls.device = serial
        cls.accepted_days = ['01', '05', '06']
        print(f"\n========== Android Security Patch Level Test ==========")
        print(f"Test Device: {cls.device}")
        print(f"Accepted patch day values: {', '.join(cls.accepted_days)}")

    def setUp(self):
        """Setup before each test"""
        print("\n" + "="*60)
        # Ensure device is accessible in instance methods
        self.device = serial
        self.dev_id = serial
        self.accepted_days = ['01', '05', '06']

    def tearDown(self):
        """Cleanup after each test"""
        print("="*60)

    def test_L0_check_security_patch_date(self):
        """
        Test Steps:
        1. Read the Android security patch level property from the device.
        2. Verify it is non-empty and parse it as a `YYYY-MM-DD` date.
        3. Verify the parsed day is `01`, `05`, or `06`.
        4. Report the parsed date or fail with the invalid patch-level value.
        """
        print("TEST: Check Android Security Patch Level Date")
        print("="*60)

        # Step 1: Get security patch level
        print("\n[Step 1] Get Android security patch level")
        patch_level = get_security_patch_level(self.device)
        
        # Verify we got a valid result
        self.assertNotEqual(patch_level, 'error', 
                           "Failed to retrieve security patch level from device")
        self.assertIsNotNone(patch_level, 
                           "Security patch level is None")
        self.assertTrue(len(patch_level) > 0, 
                       "Security patch level is empty")
        
        print(f"Security Patch Level: {patch_level}")

        # Step 2: Parse the patch date
        print("\n[Step 2] Parse security patch date")
        try:
            # Expected format: YYYY-MM-DD (e.g., 2024-01-05)
            patch_date = datetime.strptime(patch_level, '%Y-%m-%d')
            year = patch_date.strftime('%Y')
            month = patch_date.strftime('%m')
            day = patch_date.strftime('%d')
            
            print(f"Parsed Date: Year={year}, Month={month}, Day={day}")
        except ValueError as e:
            self.fail(f"Invalid security patch date format: {patch_level}. "
                     f"Expected format: YYYY-MM-DD. Error: {e}")

        # Step 3: Check if day value is acceptable
        print("\n[Step 3] Validate patch day value")
        print(f"Day value: {day}")
        print(f"Accepted day values: {', '.join(self.accepted_days)}")
        
        is_valid = day in self.accepted_days
        
        if is_valid:
            print(f"\n✓ PASS - Security patch day '{day}' is ACCEPTED")
            print(f"Full patch date: {patch_level}")
        else:
            error_msg = (f"\n❌ FAIL - Security patch day '{day}' is NOT ACCEPTED\n"
                        f"Full patch date: {patch_level}\n"
                        f"Only patch dates with day values {', '.join(self.accepted_days)} are accepted.\n"
                        f"Current day value: {day}")
            print(error_msg)
            self.fail(error_msg)

    


if __name__ == '__main__':
    # Run only the main security patch date test
    suite = unittest.TestSuite()
    suite.addTest(TestSecurityPatchLevel('test_check_security_patch_date'))
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
