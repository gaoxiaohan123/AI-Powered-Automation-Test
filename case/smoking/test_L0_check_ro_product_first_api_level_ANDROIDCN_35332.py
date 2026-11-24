# __author__ = 'sophy'
# -*- coding:utf-8 -*-
"""
Test case: ANDROIDCN-35332 - First API level compatibility.

Test Steps:
1. Read `ro.product.first_api_level` from the connected device and verify it is
    present.
2. Read the current Android SDK level from `ro.build.version.sdk` and verify it is
    present.
3. Convert both values to positive integers and report the corresponding Android
    version for the current SDK level.
4. Verify the first API level is not greater than the current SDK level.
"""
import unittest
import os
import sys
from common.adb_common import save_step_screenshot, get_first_api_level, get_android_sdk_version
import uiautomator2 as u2


# Add parent path to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# Connect device via ANDROID_SERIAL environment variable
serial = os.environ.get('ANDROID_SERIAL')
d = u2.connect(serial)


class Test_First_Api_Level(unittest.TestCase):
    """
    Test case: Check ro.product.first_api_level matches current OS version
    Verifies that first API level is valid and compatible with current SDK version
    """

    @classmethod
    def setUpClass(cls):
        """Test class initialization"""
        cls.device = serial

        print(f"\n========== First API Level Test ==========")
        print(f"Test Device: {cls.device}")

    def setUp(self):
        """Setup before each test"""
        print("\n" + "="*60)
        self.device = serial

    def tearDown(self):
        """Cleanup after each test"""
        print("="*60)

    def test_L0_check_first_api_level(self):
        """
        Test Steps:
        1. Read and validate `ro.product.first_api_level`.
        2. Read and validate the current Android SDK level.
        3. Convert both values to positive integers.
        4. Verify the first API level does not exceed the current SDK level.
        """
        print("TEST: Check First API Level Matches OS Version")
        print("="*60)

        # Step 1: Get first API level
        print("\n[Step 1] Get ro.product.first_api_level")
        first_api_level = get_first_api_level(self.device)
        
        # Verify we got a valid result
        self.assertNotEqual(first_api_level, 'error', 
                           "Failed to retrieve first API level from device")
        self.assertIsNotNone(first_api_level, 
                           "First API level is None")
        self.assertTrue(len(first_api_level) > 0, 
                       "First API level is empty")
        
        print(f"First API Level: {first_api_level}")

        # Step 2: Get current SDK version
        print("\n[Step 2] Get current Android SDK version")
        current_sdk = get_android_sdk_version(self.device)
        
        # Verify we got a valid result
        self.assertNotEqual(current_sdk, 'error', 
                           "Failed to retrieve SDK version from device")
        self.assertIsNotNone(current_sdk, 
                           "SDK version is None")
        self.assertTrue(len(current_sdk) > 0, 
                       "SDK version is empty")
        
        print(f"Current SDK Version: {current_sdk}")

        # Step 3: Validate API levels
        print("\n[Step 3] Validate API level compatibility")
        
        # Verify both are numeric
        try:
            first_api_int = int(first_api_level)
            current_sdk_int = int(current_sdk)
            print(f"First API Level (numeric): {first_api_int}")
            print(f"Current SDK Version (numeric): {current_sdk_int}")
        except ValueError as e:
            self.fail(f"API levels must be numeric. "
                     f"First API: '{first_api_level}', Current SDK: '{current_sdk}'. Error: {e}")

        # Verify first API level is positive
        self.assertGreater(first_api_int, 0, 
                          f"First API level must be positive, got: {first_api_int}")
        
        # Verify current SDK is positive
        self.assertGreater(current_sdk_int, 0, 
                          f"Current SDK version must be positive, got: {current_sdk_int}")

        # Verify first API level <= current SDK version
        print(f"\nChecking: First API Level ({first_api_int}) <= Current SDK ({current_sdk_int})")
        
        if first_api_int <= current_sdk_int:
            print(f"\n✓ PASS - First API level is compatible with current OS")
            print(f"  First API Level: {first_api_int}")
            print(f"  Current SDK: {current_sdk_int}")
            print(f"  OS Version: Android {self._get_android_version_name(current_sdk_int)}")
        else:
            error_msg = (f"\n❌ FAIL - First API level is higher than current SDK\n"
                        f"  First API Level: {first_api_int}\n"
                        f"  Current SDK: {current_sdk_int}\n"
                        f"  This indicates a configuration error - device cannot have a first API level "
                        f"higher than its current SDK version.")
            print(error_msg)
            self.fail(error_msg)

    

    def _get_android_version_name(self, sdk_version):
        """
        Convert SDK version to Android version name
        :param sdk_version: SDK API level (int)
        :return: Android version name (string)
        """
        version_map = {
            34: "14",
            33: "13",
            32: "12L",
            31: "12",
            30: "11",
            29: "10",
            28: "9 (Pie)",
            27: "8.1 (Oreo)",
            26: "8.0 (Oreo)",
            25: "7.1 (Nougat)",
            24: "7.0 (Nougat)",
            23: "6.0 (Marshmallow)",
            22: "5.1 (Lollipop)",
            21: "5.0 (Lollipop)",
        }
        return version_map.get(sdk_version, f"API {sdk_version}")
    
        

if __name__ == '__main__':
    # Run only the main first API level test
    suite = unittest.TestSuite()
    suite.addTest(TestFirstApiLevel('test_check_first_api_level_matches_os'))
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

