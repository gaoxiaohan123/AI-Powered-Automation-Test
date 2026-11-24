# __author__Sophy = 'auto_test'
# -*- coding:utf-8 -*-
"""
Test case: ANDROIDCN-36483
Test ScanDemo barcode scanning functionality
Author: auto_test
Date: 2026-06-12

Test Steps:
1. Verify both the scanner device and reference-display device are online, then
    display the expected barcode image on the reference device.
2. Open ScanDemo on the scanner device and verify its package is in the foreground.
3. Trigger one warm-up scan, then perform the configured number of scans against
    the reference barcode and record every decoded value.
4. Compare each decoded value with the expected barcode, save evidence for the
    first and final scan, and fail when any scan is missing or mismatched.
5. Run the configured sleep/wake follow-up scan and verify decoding remains valid.
"""
import subprocess
import unittest
import time
import os
import sys
import importlib
import uiautomator2 as u2

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from common.adb_common import (
    save_step_screenshot,
    scandemo_open,
    dcs_test_cleanup_devices,
    dcs_test_prepare_image_on_display_device,
    dcs_test_press_home,
    dcs_test_wait_device_online,
    dcs_test_wake_and_unlock,
)
from common.common_method import scandemo_verify_decode_result, dcs_test_connect_u2

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.realpath(__file__))))
DEV0_SERIAL = (os.environ.get("AUTONEXUS_DEV0_SN") or os.environ.get("ANDROID_SERIAL") or "").strip()
DEV1_SERIAL = (os.environ.get("AUTONEXUS_DEV1_SN") or "").strip()
if not DEV0_SERIAL or not DEV1_SERIAL:
    raise RuntimeError("AUTONEXUS_DEV0_SN and AUTONEXUS_DEV1_SN are required")

serial = DEV0_SERIAL
reference_serial = DEV1_SERIAL
if not dcs_test_wait_device_online(DEV0_SERIAL, timeout_seconds=25):
    raise RuntimeError(f"Scanner device is offline: {DEV0_SERIAL}")
if not dcs_test_wait_device_online(DEV1_SERIAL, timeout_seconds=25):
    raise RuntimeError(f"Reference device is offline: {DEV1_SERIAL}")

d = dcs_test_connect_u2(DEV0_SERIAL)
reference_device = dcs_test_connect_u2(DEV1_SERIAL)

SCRIPT_BASENAME = os.path.splitext(os.path.basename(__file__))[0]
IMG_ROOT = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.realpath(__file__)))), "img")
SCRIPT_IMG_DIR = os.path.join(IMG_ROOT, SCRIPT_BASENAME)
os.makedirs(SCRIPT_IMG_DIR, exist_ok=True)
REFERENCE_IMAGE = os.path.join(PROJECT_ROOT, "files", "images", "scandemo_img", "12345ABCDEF.jpg")
REFERENCE_REMOTE_PATH = "/sdcard/Pictures/12345ABCDEF.jpg"


def _trigger_scan_button(device, retries=3):
    """Click the ScanDemo scan button by resource ID with retries."""
    resource_id = "com.honeywell.demos.scandemo:id/scanbutton"
    for attempt in range(1, retries + 1):
        try:
            scan_button = device(resourceId=resource_id)
            if scan_button.exists(timeout=2):
                scan_button.long_click()
                time.sleep(0.5)
                return True
        except Exception as error:
            print(
                f"  [WARN] Scan button click failed (attempt {attempt}/{retries}): {error}"
            )
        time.sleep(0.5)
    print(f"  [WARN] Could not find/click Scan button resource ID: {resource_id}")
    return False


class Test_Scan_Demo(unittest.TestCase):
    """Test ScanDemo barcode scanning functionality"""

    @classmethod
    def setUpClass(cls):
        """Class setup - initialize ADB command instance"""
        cls.dev_id = serial
        #cls.expected_barcode = "swttest123456"
        cls.expected_barcode = "12345ABCDEF"
        print("\n[Setup] Device: {}".format(cls.dev_id))
        print("[Setup] Expected Barcode: {}".format(cls.expected_barcode))

    def setUp(self):
        """Test setup before each test"""
        print("\n" + "=" * 60)
        print("Test: {}".format(self.id()))
        print("=" * 60)
        # Ensure instance attributes are accessible
        self.dev_id = serial
        #self.expected_barcode = "swttest123456"
        self.expected_barcode = "12345ABCDEF"
        # Go to home screen
        d.press("home")
        reference_device.press("home")
        dcs_test_wake_and_unlock(DEV0_SERIAL, d)
        dcs_test_wake_and_unlock(DEV1_SERIAL, reference_device)
        time.sleep(1)

    def tearDown(self):
        """Test teardown after each test"""
        # Close ScanDemo app
        subprocess.run(f'adb -s {serial} shell am force-stop com.honeywell.demos.scandemo', shell=True)

        # Make sure device is awake and at home screen
        d.screen_on()
        d.press("home")
        # dcs_test_cleanup_devices(DEV0_SERIAL, DEV1_SERIAL)
        dcs_test_press_home(DEV0_SERIAL)
        dcs_test_press_home(DEV1_SERIAL)
        time.sleep(1)
        print("[TearDown] Test completed: {}".format(self.id()))

    def test_L0_scan_demo(self):
        """
        Test Steps:
        1. Display the expected reference barcode on the second device.
        2. Launch ScanDemo and verify its package is foregrounded.
        3. Perform a warm-up scan, then execute the configured repeated scans.
        4. Record and compare each decoded result with the expected barcode.
        5. Run the sleep/wake follow-up scan and verify decoding still succeeds.
        """
        print("\n[ANDROIDCN-36483] Testing Barcode Scan Functionality - 5 Scans + Sleep-Wake")
        print("=" * 60)
        self.assertTrue(os.path.exists(REFERENCE_IMAGE), f"Reference image not found: {REFERENCE_IMAGE}")
        print(f"Reference device: {DEV1_SERIAL}")
        dcs_test_prepare_image_on_display_device(
            DEV1_SERIAL,
            reference_device,
            REFERENCE_IMAGE,
            REFERENCE_REMOTE_PATH,
        )
        save_step_screenshot(reference_device, "reference_barcode_display", SCRIPT_IMG_DIR)

        # Initialize scan results list
        scan_results = []  # Store detailed scan info: {'num': 1, 'result': '123', 'success': True/False, 'error': None}
        total_scans = 5  # Reduced from 10 to 5 to avoid timeout

        # ============== Step 1: Open ScanDemo App ==============
        print("\n[Step 1/4] Opening ScanDemo App")
        print("-" * 60)

        # Launch ScanDemo app
        print("  Launching ScanDemo app...")
        self.assertTrue(scandemo_open(serial, device=d), "Failed to open ScanDemo app")
        time.sleep(3)

        # Verify app is open
        if not d(packageName="com.honeywell.demos.scandemo").exists(timeout=5):
            save_step_screenshot(d, 'step1_app_not_opened', SCRIPT_IMG_DIR)
            self.fail("Step 1 Failed: ScanDemo app did not open")

        print("  ✓ ScanDemo app opened successfully")
        print("  ✓ Step 1 completed")

        # ============== Step 2: Prepare for Scanning ==============
        print("\n[Step 2/4] Preparing for Scanning")
        print("-" * 60)
        print("  ✓ Ready to scan")
        print("  ✓ Step 2 completed")

        # ============== Step 3: Scan Barcode 10 Times ==============
        print(f"\n[Step 3/4] Scanning Barcode {total_scans} Times")
        print("-" * 60)
        print(f"  Expected Barcode: {self.expected_barcode}")
        print()

        #Skip the first scan
        _trigger_scan_button(d)
        time.sleep(3)

        for scan_num in range(1, total_scans + 1):
            print(f"\n  --- Scan {scan_num}/{total_scans} ---")
            # Trigger scan
            print(f"  Triggering scan...")
            _trigger_scan_button(d)

            print(f"  ⚠ Please scan barcode now (Scan {scan_num}/{total_scans})...")
            time.sleep(3)  # Wait for scan to complete (reduced from 5s to 3s)

            decode_result, is_match = scandemo_verify_decode_result(d, self.expected_barcode)

            # Verify result was found
            if decode_result is None:
                save_step_screenshot(d, f'scan{scan_num}_no_result',SCRIPT_IMG_DIR)
                print(f"  ✗ Scan {scan_num}: Could not find decode result (FAIL)")
                # Record failed scan
                scan_results.append({
                    'num': scan_num,
                    'result': None,
                    'success': False,
                    'error': 'No result found'
                })
                continue  # Continue to next scan instead of failing immediately

            decode_result_clean = decode_result

            # Store result with details
            scan_results.append({
                'num': scan_num,
                'result': decode_result_clean,
                'success': is_match,
                'error': None if is_match else 'Barcode mismatch'
            })

            # Display result
            if is_match:
                print(f"  ✓ Scan {scan_num} Result: {decode_result_clean} (Match)")
            else:
                print(f"  ✗ Scan {scan_num} Result: {decode_result_clean} (Expected: {self.expected_barcode}) (FAIL)")

            # Take screenshot for this scan
            if scan_num == 1 or scan_num == total_scans:
                save_step_screenshot(d, f'scan{scan_num}_result', SCRIPT_IMG_DIR)

        print("\n  ✓ Step 3 completed - All scans finished")

        # ============== Verify All Results ==============
        print("\n[Verification] Analyzing Scan Results")
        print("=" * 60)

        # Calculate statistics
        total_completed = len(scan_results)
        successful_scans = [s for s in scan_results if s['success']]
        failed_scans = [s for s in scan_results if not s['success']]

        success_count = len(successful_scans)
        fail_count = len(failed_scans)
        fail_rate = (fail_count / total_scans * 100) if total_scans > 0 else 0
        success_rate = (success_count / total_scans * 100) if total_scans > 0 else 0

        # Display detailed results
        print("\n  Detailed Scan Results:")
        for scan in scan_results:
            status = "✓ PASS" if scan['success'] else "✗ FAIL"
            result_str = scan['result'] if scan['result'] else "No Result"
            error_str = f" ({scan['error']})" if scan['error'] else ""
            print(f"    Scan {scan['num']:2d}: {result_str:15s} {status}{error_str}")

        # Display statistics
        print(f"\n  ==================== Statistics ====================")
        print(f"  Expected Barcode:    {self.expected_barcode}")
        print(f"  Total Scans:         {total_scans}")
        print(f"  Completed Scans:     {total_completed}")
        print(f"  Successful Scans:    {success_count}")
        print(f"  Failed Scans:        {fail_count}")
        print(f"  Success Rate:        {success_rate:.1f}%")
        print(f"  Fail Rate:           {fail_rate:.1f}%")
        print(f"  ====================================================")

        # List failed scan numbers if any
        if fail_count > 0:
            failed_scan_nums = [s['num'] for s in failed_scans]
            print(f"\n  Failed Scan Numbers: {failed_scan_nums}")

            # Group by error type
            error_types = {}
            for s in failed_scans:
                error = s['error'] or 'Unknown'
                if error not in error_types:
                    error_types[error] = []
                error_types[error].append(s['num'])

            print(f"\n  Failure Breakdown:")
            for error, nums in error_types.items():
                print(f"    {error}: {len(nums)} scan(s) - {nums}")

        # Determine if test passes based on fail rate
        # You can adjust the threshold as needed (e.g., allow up to 10% failure)
        acceptable_fail_rate = 0  # 0% - all scans must pass

        if fail_rate <= acceptable_fail_rate:
            print(f"\n  ✓ PASS: Fail rate ({fail_rate:.1f}%) is within acceptable range (<= {acceptable_fail_rate}%)")
            print(f"  ✓ All {success_count} scans successful")
        else:
            print(f"\n  ⚠ WARNING: Fail rate ({fail_rate:.1f}%) exceeds acceptable threshold ({acceptable_fail_rate}%)")
            print(f"  {fail_count} out of {total_scans} scans failed")

        # ============== Step 4: Sleep-Wake Test ==============
        print("\n[Step 4/4] Sleep-Wake Scan Test")
        print("=" * 60)
        print("  Testing scan functionality after sleep-wake cycle")

        # Initialize sleep-wake test status
        sleep_wake_success = True
        sleep_wake_error = None
        sleep_wake_result = None

        # Put device to sleep
        print("\n  [4.1] Putting device to sleep...")
        d.press("power")  # Press power button to sleep
        time.sleep(2)
        print("  ✓ Device sleeping")

        # Wait in sleep mode
        print("  Waiting 3 seconds in sleep mode...")
        time.sleep(3)  # Reduced from 5s to 3s

        # Wake up device
        print("\n  [4.2] Waking up device...")
        d.screen_on()  # Wake up device
        time.sleep(5)

        # Unlock device if needed (swipe up)
        d.swipe(360, 1000, 360, 300, 0.1)  # Swipe up to unlock
        time.sleep(1)
        print("  ✓ Device awake and unlocked")

        # Verify ScanDemo app is still running, if not, reopen it
        print("\n  [4.3] Checking ScanDemo app status...")
        app_ready = True
        if not d(packageName="com.honeywell.demos.scandemo").exists(timeout=2):
            print("  App was closed, reopening...")
            scandemo_open(serial)
            time.sleep(3)

            if not d(packageName="com.honeywell.demos.scandemo").exists(timeout=5):
                save_step_screenshot(d, 'sleep_wake_app_not_opened',SCRIPT_IMG_DIR)
                print("  ✗ WARNING: ScanDemo app did not reopen")
                sleep_wake_success = False
                sleep_wake_error = "App failed to reopen"
                app_ready = False
            else:
                print("  ✓ App reopened successfully")
        else:
            print("  ✓ App still running")

        # Only proceed with scan if app is ready
        if app_ready:
            # Perform scan after wake up
            print("\n  [4.4] Scanning barcode after wake up...")
            _trigger_scan_button(d)
            _trigger_scan_button(d)

            print("  ⚠ Please scan barcode now (Sleep-Wake Test)...")
            time.sleep(3)  # Wait for scan to complete (reduced from 5s to 3s)

            # Get decode result
            wake_decode_result, wake_is_match = scandemo_verify_decode_result(
                d,
                self.expected_barcode,
            )

            # Take screenshot
            save_step_screenshot(d, 'sleep_wake_scan_result', SCRIPT_IMG_DIR)

            # Verify result and record status
            if wake_decode_result is None:
                print("  ✗ Could not find decode result after wake up")
                sleep_wake_success = False
                sleep_wake_error = "No result found"
                sleep_wake_result = None
            else:
                # Clean up the result (strip whitespace but keep all characters)
                wake_decode_result_clean = wake_decode_result.strip()

                # If the result contains the expected barcode as a substring, extract it
                if self.expected_barcode in wake_decode_result_clean:
                    # Find the position of the expected barcode in the result
                    idx = wake_decode_result_clean.find(self.expected_barcode)
                    wake_decode_result_clean = wake_decode_result_clean[idx:idx + len(self.expected_barcode)]
                # Otherwise, try to extract barcode-like text (remove common prefixes)
                else:
                    # Remove common prefixes like "Decode Result:", "Barcode:", "Data:" etc.
                    for prefix in ['Decode Result:', 'Barcode:', 'Data:', 'Result:', 'Code:']:
                        if prefix in wake_decode_result_clean:
                            wake_decode_result_clean = wake_decode_result_clean.split(prefix, 1)[1].strip()
                            break

                sleep_wake_result = wake_decode_result_clean

                print(f"\n  Sleep-Wake Scan Result:")
                print(f"  Expected: {self.expected_barcode}")
                print(f"  Got:      {wake_decode_result_clean}")

                if wake_decode_result_clean == self.expected_barcode:
                    print(f"\n  ✓ PASS: Scan successful after sleep-wake cycle")
                    print(f"  ✓ Barcode: {wake_decode_result_clean}")
                    sleep_wake_success = True
                    sleep_wake_error = None
                else:
                    print(f"\n  ✗ FAIL: Barcode mismatch after sleep-wake")
                    sleep_wake_success = False
                    sleep_wake_error = f"Expected {self.expected_barcode}, Got {wake_decode_result_clean}"

        if sleep_wake_success:
            print("\n  ✓ Step 4 completed - Sleep-Wake test passed")
        else:
            print(f"\n  ✗ Step 4 completed - Sleep-Wake test failed: {sleep_wake_error}")

        # ============== Final Test Summary ==============
        print("\n" + "=" * 60)
        print("FINAL TEST SUMMARY")
        print("=" * 60)

        # Calculate overall statistics
        total_tests = total_scans + 1  # 10 scans + 1 sleep-wake test
        total_failures = fail_count + (0 if sleep_wake_success else 1)
        overall_fail_rate = (total_failures / total_tests * 100) if total_tests > 0 else 0
        overall_success_rate = ((total_tests - total_failures) / total_tests * 100) if total_tests > 0 else 0

        print(f"\n  Regular Scans:        {success_count}/{total_scans} passed ({success_rate:.1f}% success rate)")
        print(f"  Sleep-Wake Test:      {'PASS' if sleep_wake_success else 'FAIL'}")
        print(f"\n  Total Tests:          {total_tests}")
        print(f"  Total Passed:         {total_tests - total_failures}")
        print(f"  Total Failed:         {total_failures}")
        print(f"  Overall Success Rate: {overall_success_rate:.1f}%")
        print(f"  Overall Fail Rate:    {overall_fail_rate:.1f}%")

        # Determine final test result
        acceptable_overall_fail_rate = 0  # Adjust threshold as needed

        print("\n" + "=" * 60)
        if overall_fail_rate <= acceptable_overall_fail_rate:
            print(f"✓ TEST PASSED")
            print(f"  All {total_tests} tests successful")
            print(f"  Fail rate: {overall_fail_rate:.1f}% (acceptable: ≤ {acceptable_overall_fail_rate}%)")
        else:
            print(f"✗ TEST FAILED")
            print(f"  {total_failures} out of {total_tests} tests failed")
            print(f"  Fail rate: {overall_fail_rate:.1f}% (acceptable: ≤ {acceptable_overall_fail_rate}%)")

            # List all failures
            if fail_count > 0:
                failed_scan_nums = [s['num'] for s in failed_scans]
                print(f"  - Failed scans: {failed_scan_nums}")
            if not sleep_wake_success:
                print(f"  - Sleep-Wake test failed: {sleep_wake_error}")

            # Fail the test at the end with comprehensive error message
            failure_details = []
            if fail_count > 0:
                failure_details.append(f"{fail_count} scan failures")
            if not sleep_wake_success:
                failure_details.append("sleep-wake test failure")

            self.fail(f"Test failed with {overall_fail_rate:.1f}% fail rate. " + ", ".join(failure_details))

        print("=" * 60)


if __name__ == "__main__":
    unittest.main(verbosity=2)
