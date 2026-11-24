"""ANDROIDCN-42196: L1_New user should able to access HON app.

Description:
Enable Allow multiple users and add user, then check the function.
"""

import os
import re
import time
import unittest

from common.common_method import GeneralSettingsTestCase, screenshot, shell


APP_TARGETS = (
    ("Demos", "com.honeywell.demos.scandemo", "com.honeywell.demos.scandemo/.ScanDemoMainActivity", True),
    ("RFID", "com.honeywell.datacollection.rfid", "com.honeywell.datacollection.rfid/.splashscreen.SplashScreenActivity", True),
    ("Scanner Edge", "com.honeywell.tools.smu", "com.honeywell.tools.smu/.SplashScreen", True),
)


class TestL1NewUserHonAppsAndroidcn42196(GeneralSettingsTestCase):

    def _create_secondary_user(self):
        output = shell(self.serial, "pm", "create-user", "HON_AutoTest")
        match = re.search(r"created user id (\d+)", output)
        if not match:
            self.fail("Unable to create a secondary user: {}".format(output or "no response"))

        user_id = match.group(1)
        shell(self.serial, "am", "start-user", "-w", user_id, timeout=60)
        shell(self.serial, "am", "switch-user", user_id)
        deadline = time.time() + 30
        while time.time() < deadline:
            if shell(self.serial, "am", "get-current-user") == user_id:
                break
            time.sleep(1)
        self.assertEqual(shell(self.serial, "am", "get-current-user"), user_id, "Failed to switch to secondary user")
        return user_id

    def _package_is_available(self, user_id, package_name):
        output = shell(self.serial, "pm", "list", "packages", "--user", user_id, package_name)
        return "package:{}".format(package_name) in output

    def _launch_app(self, user_id, app_name, package_name, activity_name):
        last_focus = ""
        for attempt in range(2):
            output = shell(self.serial, "am", "start", "--user", user_id, "-n", activity_name, timeout=30)
            self.assertNotIn("Error:", output, "Unable to launch {}: {}".format(app_name, output))
            deadline = time.time() + 10
            while time.time() < deadline:
                last_focus = shell(self.serial, "dumpsys", "window", "windows")
                if package_name in last_focus:
                    return
                time.sleep(1)

        self.fail("{} did not become the foreground app after retry: {}".format(app_name, last_focus))

    def _restore_owner_interactive_state(self):
        deadline = time.time() + 15
        while time.time() < deadline:
            shell(self.serial, "input", "keyevent", "KEYCODE_WAKEUP")
            time.sleep(2)
            shell(self.serial, "input", "keyevent", "KEYCODE_WAKEUP")
            shell(self.serial, "wm", "dismiss-keyguard")
            time.sleep(1)
            self.device.press("home")

            power_state = shell(self.serial, "dumpsys", "power")
            keyguard_state = shell(self.serial, "dumpsys", "window", "policy")
            is_awake = "mWakefulness=Awake" in power_state
            is_unlocked = "mIsShowing=true" not in keyguard_state
            if is_awake and is_unlocked:
                return
            time.sleep(1)

        self.fail("Owner session did not return to an awake, unlocked display")

    def test_l1_new_user_can_launch_hon_apps(self):
        """Create a new user and verify that required HON apps launch for that user."""
        user_id = self._create_secondary_user()
        try:
            for app_name, package_name, activity_name, required in APP_TARGETS:
                available = self._package_is_available(user_id, package_name)
                if required:
                    self.assertTrue(available, "{} is not available to the new user".format(app_name))
                elif not available:
                    print("[INFO] {} is not installed on this device; skipping its launch check".format(app_name))
                    continue

                if activity_name:
                    self._launch_app(user_id, app_name, package_name, activity_name)

            screenshot(self.device, __file__, "step03_hon_apps_available")
        finally:
            shell(self.serial, "am", "switch-user", "0")
            deadline = time.time() + 30
            while time.time() < deadline:
                if shell(self.serial, "am", "get-current-user") == "0":
                    break
                time.sleep(1)
            self.assertEqual(shell(self.serial, "am", "get-current-user"), "0", "Failed to switch back to Owner")
            shell(self.serial, "pm", "remove-user", user_id, timeout=30)
            self._restore_owner_interactive_state()


if __name__ == "__main__":
    unittest.main(verbosity=2)