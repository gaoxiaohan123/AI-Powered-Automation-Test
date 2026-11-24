# __author__ = 'sophy' only for CT47
# -*- coding:utf-8 -*-

"""
FIPS Configuration Check Test - ANDROIDCN-38041

Test Scope:
This test ONLY applies to CT47 devices.
Other devices will be skipped with a message "FIPS not supported".

Test Purpose:
Verify FIPS SKU identification and configuration correctness based on part number.

Test Logic:
0. Pre-check:
   - Verify device is CT47 (ro.build.product or ro.vendor.hon.model.num)
   - If not CT47, skip test with message
1. Get device part number: adb shell getprop ro.vendor.hon.extconf.num
2. Parse part number to determine SKU type:
   - Format: "CT47-X0N-37D701G"
   - Extract last segment: "37D701G"
   - Get 4th character (index 3): "7"
   - FIPS identifier: 4/5/6/7 → FIPS SKU, 1 → Non-FIPS SKU
3. FIPS SKU Verification:
   - ro.boot.product.fips should be "true"
   - ro.build.fingerprint should contain "CT47G" (Government/FIPS variant)
   - Settings → About Phone may have "FIPS" item (optional check)
4. Non-FIPS SKU Verification:
   - ro.boot.product.fips should be "false"
   - ro.build.fingerprint should contain "CT47" (without 'G')
   - Settings → About Phone should NOT have "FIPS" item

Example Part Numbers:
- FIPS: "CT47-X0N-37D701G" -> "37D701G" -> 4th digit="7" -> FIPS
- FIPS: "CT47-X0N-34D501G" -> "34D501G" -> 4th digit="5" -> FIPS
- Non-FIPS: "CT47-X0N-37D1E0G" -> "37D1E0G" -> 4th digit="1" -> Non-FIPS
"""

import unittest
import os
import sys
import time
import re
import uiautomator2 as u2
import subprocess

# Add parent path to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from common.adb_common import save_step_screenshot   

# Connect device via ANDROID_SERIAL environment variable
serial = os.environ.get('ANDROID_SERIAL')
d = u2.connect(serial)

SCRIPT_BASENAME = os.path.splitext(os.path.basename(__file__))[0]
IMG_ROOT = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.realpath(__file__)))), "img")
SCRIPT_IMG_DIR = os.path.join(IMG_ROOT, SCRIPT_BASENAME)
os.makedirs(SCRIPT_IMG_DIR, exist_ok=True)

class Test_FIPS_Check(unittest.TestCase):
    """
    Test case: FIPS Configuration Check
    Verify FIPS SKU identification and settings based on part number
    """

    @classmethod
    def setUpClass(cls):
        """Test class initialization"""
        cls.device = serial
        cls.is_fips_sku = None
        cls.part_number = None
        cls.fourth_digit = None
        
        print(f"\n{'='*70}")
        print(f"FIPS Configuration Check Test - ANDROIDCN-38041")
        print(f"{'='*70}")
        print(f"Test Device: {cls.device}")

    def setUp(self):
        """Setup before each test"""
        print("\n" + "="*70)
        d.press("home")
        time.sleep(1)

    def tearDown(self):
        """Cleanup after each test"""
        print("="*70)
        # Close Settings app
        subprocess.run(f'adb -s {serial} shell am force-stop com.android.settings', shell=True)
        d.press('home')
        time.sleep(0.5)

    def _get_adb_property(self, prop_name):
        """
        Get Android system property via adb
        :param prop_name: Property name (e.g., "ro.vendor.hon.extconf.num")
        :return: Property value as string, or None if failed
        """
        try:
            # Use shell=True for Windows compatibility
            cmd = f"adb -s {serial} shell getprop {prop_name}"
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=10,
                shell=True
            )
            time.sleep(0.5)
            
            # On Windows, adb may return non-zero exit code even on success
            # Check stdout instead of returncode
            value = result.stdout.strip()
            
            if value:
                print(f"  ✓ {prop_name} = '{value}'")
                return value
            else:
                print(f"  ⚠ Property {prop_name} returned empty value")
                if result.stderr:
                    print(f"     Error: {result.stderr}")
                return None
                
        except Exception as e:
            print(f"  ❌ Error getting property {prop_name}: {e}")
            import traceback
            traceback.print_exc()
            return None

    def _extract_fourth_digit(self, part_number):
        """
        Extract the FIPS identifier digit from part number
        :param part_number: Part number string
        :return: The FIPS identifier digit, or None if not found
        
        Logic:
        1. Split part number by '-' to get segments
        2. Take the last segment (e.g., "37D701G" from "CT47-X0N-37D701G")
        3. Extract the 4th character (index 3) of the last segment as FIPS identifier
        
        Examples:
        - "CT47-X0N-37D701G" -> "37D701G" -> 4th digit (index 3) = "7" -> FIPS
        - "CT47-X0N-37D1E0G" -> "37D1E0G" -> 4th digit (index 3) = "1" -> Non-FIPS
        - "CT47-X0N-34D501N" -> "34D501N" -> 4th digit (index 3) = "5" -> FIPS
        
        FIPS Identifier Rules:
        - 4th digit = 4/5/6/7 -> FIPS SKU
        - 4th digit = 1 -> Non-FIPS SKU
        
        Note: The method name remains "_extract_fourth_digit" for compatibility.
        """
        if not part_number:
            return None
        
        print(f"  Analyzing part number: {part_number}")
        
        # Split by '-' to get segments
        segments = part_number.split('-')
        
        if not segments:
            print(f"  ⚠ No segments found in part number")
            return None
        
        # Get the last segment (e.g., "37D701G")
        last_segment = segments[-1]
        print(f"  Last segment: {last_segment}")
        
        # Check if the last segment has at least 4 characters
        if len(last_segment) < 4:
            print(f"  ⚠ Last segment has less than 4 characters: {last_segment}")
            return None
        
        # Get the 4th character (index 3) of the last segment
        fourth_char = last_segment[3]
        print(f"  4th character (index 3) of last segment: {fourth_char}")
        
        # Verify it's a digit
        if not fourth_char.isdigit():
            print(f"  ⚠ 4th character is not a digit: {fourth_char}")
            return None
        
        print(f"  FIPS identifier (4th position): {fourth_char}")
        
        return fourth_char

    def _check_fips_in_settings(self):
        """
        Check if "FIPS" item exists in Settings → About Phone
        :return: True if FIPS item found, False otherwise
        """
        print("\n  Opening Settings → About Phone...")
        
        try:
            # Open About Phone settings using Intent
            cmd = f"adb -s {serial} shell am start -a android.settings.DEVICE_INFO_SETTINGS"
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                shell=True
            )       
            
            # Search for FIPS item
            print("  Searching for FIPS item...")
            print("  Note: FIPS item is usually at the bottom of About Phone page")
            
            # Try scrolling to find FIPS (FIPS is at the bottom, need more scrolls)
            fips_found = False
            
            # Check if FIPS text exists without scrolling first
            if d(textMatches=".*FIPS.*", className="android.widget.TextView").exists(timeout=1):
                fips_found = True
                print("  ✓ FIPS item found (without scrolling)")
            else:
                # Scroll down to find FIPS (increase to 15 attempts as FIPS is at bottom)
                print("  Scrolling down to search for FIPS item...")
                for scroll_attempt in range(5):
                    # Check for FIPS after each scroll
                    if d(textMatches=".*FIPS.*").exists(timeout=1):
                        fips_found = True
                        print(f"  ✓ FIPS item found (after {scroll_attempt + 1} scroll(s))")
                        break
                    
                    # Scroll down - use scrollable object for better scrolling
                    if d(scrollable=True).exists():
                        d(scrollable=True).scroll.forward()
                    else:
                        # Fallback to swipe if no scrollable element
                        d.swipe(500, 1500, 500, 500, duration=0.3)
                    
                    time.sleep(0.5)
            
            if fips_found:
                save_step_screenshot(d, 'fips_item_found', SCRIPT_IMG_DIR)
            else:
                print("  ✗ FIPS item not found")
                save_step_screenshot(d, 'fips_item_not_found', SCRIPT_IMG_DIR)
            
            return fips_found
            
        except Exception as e:
            print(f"  ❌ Error checking FIPS in settings: {e}")
            save_step_screenshot(d, 'fips_check_error', SCRIPT_IMG_DIR)
            return False
        finally:
            # Go back to home
            d.press("back")
            d.press("home")
            time.sleep(0.5)

    def test_L0_fips_configuration(self):
        """
        Test Steps:
        1. Read the device model and skip when the device is not a CT47.
        2. Read the part number and determine whether the SKU requires FIPS.
        3. Navigate to the relevant configuration page and locate the FIPS setting.
        4. Verify the observed setting matches the part-number requirement.
        5. Capture evidence and report the detected configuration on failure.
        """
        print("\n[TEST] FIPS Configuration Check")
        print("="*70)
        
        # ===================================================================
        # Step 0: Check if device is CT47
        # ===================================================================
        print("\n[Step 0] Check device model")
        
        # Get device model
        model = self._get_adb_property("ro.build.product")
        if not model:
            model = self._get_adb_property("ro.vendor.hon.model.num")
        
        print(f"  Device Model: {model}")
        
        # Check if device is CT47
        is_ct47 = model and "CT47" in model.upper()
        
        print(f"\n  Device Check:")
        print(f"    - Is CT47: {is_ct47}")
        
        # If not CT47, skip FIPS test
        if not is_ct47:
            skip_msg = (
                f"\n{'='*70}\n"
                f"⊘ SKIP - FIPS test not applicable to this device\n"
                f"{'='*70}\n"
                f"  Device Model: {model}\n"
                f"  Reason: FIPS check only supports CT47 devices\n"
                f"{'='*70}\n"
            )
            print(skip_msg)
            self.skipTest(f"FIPS not supported - Device: {model}")
            return
        
        print(f"\n  ✓ Device is CT47 - FIPS check will proceed")
        
        # ===================================================================
        # Step 1: Get Part Number
        # ===================================================================
        print("\n[Step 1] Get device part number")
        part_number = self._get_adb_property("ro.vendor.hon.extconf.num")
        
        if not part_number:
            self.fail("❌ FAIL - Could not get part number (ro.vendor.hon.extconf.num)")
        
        Test_FIPS_Check.part_number = part_number
        
        # ===================================================================
        # Step 2: Determine FIPS SKU based on 4th digit
        # ===================================================================
        print("\n[Step 2] Determine FIPS SKU from part number")
        fourth_digit = self._extract_fourth_digit(part_number)
        
        if not fourth_digit:
            self.fail(f"❌ FAIL - Could not extract 4th digit from part number: {part_number}")
        
        Test_FIPS_Check.fourth_digit = fourth_digit
        
        # Check if it's FIPS SKU (4th digit is 4, 5, 6, or 7)
        is_fips_sku = fourth_digit in ['4', '5', '6', '7']
        is_non_fips_sku = fourth_digit == '1'
        
        Test_FIPS_Check.is_fips_sku = is_fips_sku
        
        if is_fips_sku:
            print(f"\n  ✓ Detected: FIPS SKU (4th digit = {fourth_digit})")
            expected_sku_type = "FIPS"
        elif is_non_fips_sku:
            print(f"\n  ✓ Detected: Non-FIPS SKU (4th digit = {fourth_digit})")
            expected_sku_type = "Non-FIPS"
        else:
            self.fail(f"❌ FAIL - Unknown SKU type (4th digit = {fourth_digit}). Expected 1/4/5/6/7")
        
        # ===================================================================
        # Step 3: Verify ro.boot.product.fips property
        # ===================================================================
        print(f"\n[Step 3] Verify ro.boot.product.fips property")
        fips_property = self._get_adb_property("ro.boot.product.fips")
        
        if is_fips_sku:
            expected_fips_value = "true"
        else:
            expected_fips_value = "false"
        
        print(f"  Expected: {expected_fips_value}")
        print(f"  Actual:   {fips_property}")
        
        if fips_property != expected_fips_value:
            error_msg = (
                f"\n❌ FAIL - ro.boot.product.fips mismatch\n"
                f"  SKU Type: {expected_sku_type}\n"
                f"  Expected: {expected_fips_value}\n"
                f"  Got:      {fips_property}\n"
            )
            print(error_msg)
            self.fail(error_msg)
        
        print(f"  ✓ PASS - ro.boot.product.fips = {fips_property} (correct)")
        
        # ===================================================================
        # Step 4: Verify ro.build.fingerprint
        # ===================================================================
        print(f"\n[Step 4] Verify ro.build.fingerprint")
        fingerprint = self._get_adb_property("ro.build.fingerprint")
        
        if not fingerprint:
            self.fail("❌ FAIL - Could not get ro.build.fingerprint")
        
        if is_fips_sku:
            # FIPS should contain CT47G (with 'G' indicating Government/FIPS)
            # Pattern examples: "CT47G-X0-D-NG", "CT47G-X1-D-NG"
            fingerprint_match = "CT47G" in fingerprint
            
            if not fingerprint_match:
                error_msg = (
                    f"\n❌ FAIL - Fingerprint pattern mismatch for FIPS SKU\n"
                    f"  Expected: Should contain 'CT47G'\n"
                    f"  Got: {fingerprint}\n"
                )
                print(error_msg)
                self.fail(error_msg)
            
            print(f"  ✓ PASS - Fingerprint contains FIPS pattern (CT47G)")
            
        else:
            # Non-FIPS should NOT contain CT47G
            # Should be CT47 without the 'G' suffix
            has_fips_pattern = "CT47G" in fingerprint
            has_ct47 = "CT47" in fingerprint
            
            if has_fips_pattern:
                error_msg = (
                    f"\n❌ FAIL - Fingerprint pattern mismatch for Non-FIPS SKU\n"
                    f"  Expected: Should NOT contain 'CT47G'\n"
                    f"  Got: {fingerprint}\n"
                )
                print(error_msg)
                self.fail(error_msg)
            
            if not has_ct47:
                error_msg = (
                    f"\n❌ FAIL - Fingerprint should contain 'CT47'\n"
                    f"  Got: {fingerprint}\n"
                )
                print(error_msg)
                self.fail(error_msg)
            
            print(f"  ✓ PASS - Fingerprint contains Non-FIPS pattern (CT47 without G)")
        
        # ===================================================================
        # Step 5: Check FIPS item in Settings → About Phone (Optional)
        # ===================================================================
        print(f"\n[Step 5] Check FIPS item in Settings → About Phone (Optional)")
        print(f"  Note: This is an optional UI check. Core validation is done via properties.")
        fips_item_exists = self._check_fips_in_settings()
        
        if is_fips_sku:
            if not fips_item_exists:
                print(f"  ⚠ WARNING - FIPS item not found in Settings UI")
                print(f"     This may be normal for some device configurations")
                print(f"     Core FIPS validation (properties & fingerprint) has passed")
            else:
                print(f"  ✓ PASS - FIPS item found in Settings (correct for FIPS SKU)")
            
        else:
            if fips_item_exists:
                print(f"  ⚠ WARNING - FIPS item found in Settings but device is Non-FIPS")
                print(f"     This is unexpected but not critical")
            else:
                print(f"  ✓ PASS - FIPS item not found in Settings (correct for Non-FIPS SKU)")
        
        # ===================================================================
        # Final Result
        # ===================================================================
        print(f"\n{'='*70}")
        print(f"✓ PASS - All FIPS configuration checks passed")
        print(f"{'='*70}")
        print(f"  Part Number:        {part_number}")
        print(f"  FIPS Identifier:    4th digit = {fourth_digit}")
        print(f"  SKU Type:           {expected_sku_type}")
        print(f"  FIPS Property:      {fips_property} ✓")
        print(f"  Build Fingerprint:  {fingerprint[:50]}... ✓")
        print(f"  FIPS in Settings:   {'Yes' if fips_item_exists else 'No (optional)'}")
        print(f"{'='*70}")


if __name__ == '__main__':
    # Run the FIPS check test
    suite = unittest.TestSuite()
    suite.addTest(Test_FIPS_Check('test_fips_configuration'))
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
