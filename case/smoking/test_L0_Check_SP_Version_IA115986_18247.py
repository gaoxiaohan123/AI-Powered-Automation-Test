# -*- coding:utf-8 -*-

"""
Test case: Check_SP_Version

Test Steps:
1. Run on PC: adb shell "getprop | grep security" and expect the security patch properties.
2. Parse ro.build.version.security_patch and ro.vendor.build.security_patch.
3. Verify both values are valid dates (YYYY-MM-DD).
4. Verify both dates are the same, e.g.
   [ro.build.version.security_patch]: [2024-04-01]
   [ro.vendor.build.security_patch]: [2024-04-01]
5. If AUTONEXUS_EXPECTED_SPL is set, verify the date equals the actual SPL.
"""

import os
import re
import sys
import unittest
from datetime import datetime

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from common.adb_common import adb_shell_output, get_device_serial

BUILD_PROP = "ro.build.version.security_patch"
VENDOR_PROP = "ro.vendor.build.security_patch"
PROP_PATTERN = re.compile(r"\[([^\]]+)\]:\s*\[([^\]]*)\]")


class Test_Check_SP_Version(unittest.TestCase):
    """Check the security patch level properties."""

    @classmethod
    def setUpClass(cls):
        cls.serial = (os.environ.get("ANDROID_SERIAL") or "").strip() or get_device_serial()

    def setUp(self):
        if not self.serial:
            self.skipTest("No ADB device available")

    def test_check_sp_version(self):
        """Test Steps:
        1. Run on PC: adb shell "getprop | grep security" and expect the security patch properties.
        2. Parse ro.build.version.security_patch and ro.vendor.build.security_patch.
        3. Verify both values are valid dates (YYYY-MM-DD).
        4. Verify both dates are the same, e.g.
        [ro.build.version.security_patch]: [2024-04-01]
        [ro.vendor.build.security_patch]: [2024-04-01]
        5. If AUTONEXUS_EXPECTED_SPL is set, verify the date equals the actual SPL.
        """
        print("\n[Step 1] adb shell getprop | grep security")
        output = adb_shell_output(self.serial, "getprop | grep security")
        print(output)
        self.assertTrue(output, "getprop | grep security returned no output")

        print("[Step 2] Parse security patch properties")
        props = {key: value.strip() for key, value in PROP_PATTERN.findall(output)}
        for name in (BUILD_PROP, VENDOR_PROP):
            self.assertIn(name, props, f"{name} not found in getprop output")
            print(f"  {name} = {props[name]}")

        print("[Step 3] Verify date format YYYY-MM-DD")
        for name in (BUILD_PROP, VENDOR_PROP):
            try:
                datetime.strptime(props[name], "%Y-%m-%d")
            except ValueError:
                self.fail(f"{name} is not a valid YYYY-MM-DD date: '{props[name]}'")

        print("[Step 4] Verify both dates are the same")
        self.assertEqual(
            props[BUILD_PROP],
            props[VENDOR_PROP],
            f"{BUILD_PROP}={props[BUILD_PROP]} differs from {VENDOR_PROP}={props[VENDOR_PROP]}",
        )

        expected = (os.environ.get("AUTONEXUS_EXPECTED_SPL") or "").strip()
        if expected:
            print(f"[Step 5] Verify SPL equals expected {expected}")
            self.assertEqual(props[BUILD_PROP], expected, "SPL does not match the expected date")
        else:
            print("[Step 5] AUTONEXUS_EXPECTED_SPL not set, skipped")


if __name__ == "__main__":
    suite = unittest.TestLoader().loadTestsFromTestCase(Test_Check_SP_Version)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)
