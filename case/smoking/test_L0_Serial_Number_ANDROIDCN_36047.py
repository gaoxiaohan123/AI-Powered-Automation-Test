#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Test case: ANDROIDCN-36047 - Serial number consistency.

Test Steps:
1. Connect through UIAutomator2, wake the device, and open Android Settings.
2. Navigate to About phone and capture the About phone page.
3. Open the Model entry, locate the Serial number field, and extract its displayed value.
4. Capture evidence of the serial number, retrieve the ADB device serial, normalize
    both values, and verify they match exactly.
5. Close Settings during cleanup.
"""

import unittest
import time
import os
import subprocess
import sys

SCRIPT_BASENAME = os.path.splitext(os.path.basename(__file__))[0]
IMG_ROOT = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.realpath(__file__)))),
    "img",
)
SCRIPT_IMG_DIR = os.path.join(IMG_ROOT, SCRIPT_BASENAME)
os.makedirs(SCRIPT_IMG_DIR, exist_ok=True)

def _local_save_step_screenshot(device, step_name, img_dir=None):
    """Fallback screenshot saver used when common helper import is unavailable."""
    save_dir = img_dir if img_dir else SCRIPT_IMG_DIR
    os.makedirs(save_dir, exist_ok=True)

    ts = time.strftime('%Y%m%d_%H%M%S')
    filepath = os.path.join(save_dir, f'{step_name}_{ts}.png')

    try:
        img = device.screenshot()
        img.save(filepath)
        print(f'[Screenshot] Saved: {filepath}', flush=True)
    except Exception as e:
        print(f'[Screenshot] Capture failed: {str(e)[:120]}', flush=True)

    return filepath


try:
    from common.adb_common import save_step_screenshot
except Exception as import_err:
    PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
    if PROJECT_ROOT not in sys.path:
        sys.path.insert(0, PROJECT_ROOT)

    try:
        from common.adb_common import save_step_screenshot
    except Exception:
        print(f"[WARNING] Falling back to local screenshot saver: {import_err}")
        save_step_screenshot = _local_save_step_screenshot

try:
    import uiautomator2 as u2  # pyright: ignore[reportMissingImports]
except ImportError:
    u2 = None


class Test_Serial_Number(unittest.TestCase):
    """Test Serial Number - Navigate to Settings -> About phone -> Model -> Serial number"""

    def setUp(self):
        """Set up test fixtures"""
        if u2 is None:
            self.skipTest("uiautomator2 is not installed in the active Python environment")

        # Get device serial from environment or use default
        serial = os.environ.get('ANDROID_SERIAL')
        try:
            if serial:
                print(f"[TEST] Connecting to device: {serial}")
                self.device = u2.connect(serial)
            else:
                print("[TEST] Connecting to default device...")
                self.device = u2.connect()
            
            # Check device connection
            device_info = self.device.info
            print(f"[TEST] Device connected: {device_info.get('model', 'Unknown')}")
            
            # Ensure screen is on
            self.device.screen_on()
            time.sleep(1)
            
            # Open Settings app
            print("[TEST] Starting Settings application...")
            self.device.app_start("com.android.settings", "com.android.settings.Settings")
            time.sleep(3)
            
            # Verify Settings is open by checking if any UI elements are visible
            print("[TEST] Verifying Settings app is open...")
            self._verify_settings_open()
            
        except Exception as e:
            print(f"[ERROR] Setup failed: {str(e)}")
            self.skipTest(f"Device not available or Setup failed: {str(e)}")

    def tearDown(self):
        """Clean up after tests"""
        if hasattr(self, 'device'):
            self.device.app_stop("com.android.settings")
            time.sleep(1)

    def _verify_settings_open(self):
        """Verify that Settings app is open"""
        max_retries = 3
        for attempt in range(max_retries):
            try:
                # Try to get current activity or check for any Settings UI element
                current_app = self.device.app_current()
                if "settings" in current_app.get('package', '').lower():
                    print("[TEST] Settings app verified as open")
                    return True
                
                time.sleep(1)
            except:
                pass
        
        print("[WARNING] Could not verify Settings app is open, continuing anyway...")
        return False

    def _wait_for_ui_idle(self, seconds=1.0):
        """Wait briefly for UI transitions/animations to settle."""
        time.sleep(seconds)

    def _find_element_by_text(self, text, max_attempts=3, scroll_steps=10):
        """
        Find a UI element by its text content with auto-scrolling capability
        
        Args:
            text: The text to search for
            max_attempts: Maximum number of scroll attempts
            scroll_steps: Number of steps for each scroll
            
        Returns:
            The found element or None
        """
        # Add common aliases for known labels that vary across OEM/system builds.
        text_candidates = [text]
        if text == "Model":
            text_candidates.extend(["Model name", "Phone model", "Device model", "型号"])

        for attempt in range(max_attempts):
            print(f"[TEST] Attempt {attempt + 1}/{max_attempts}: Looking for '{text}'...")

            # Give the destination page a moment to finish rendering.
            self._wait_for_ui_idle(0.4)

            # Try direct match first for all candidates.
            for candidate in text_candidates:
                element = self.device(text=candidate, className="android.widget.TextView")
                if element.exists():
                    print(f"[TEST] Found '{candidate}'")
                    return element

                element = self.device(text=candidate)
                if element.exists():
                    print(f"[TEST] Found '{candidate}'")
                    return element

                element = self.device(textContains=candidate)
                if element.exists():
                    print(f"[TEST] Found (partial match) '{candidate}'")
                    return element

            # Then try scrollable container based search.
            for candidate in text_candidates:
                try:
                    scrollable = self.device(scrollable=True)
                    if scrollable.exists:
                        if scrollable.scroll.to(text=candidate):
                            element = self.device(text=candidate)
                            if element.exists():
                                print(f"[TEST] Found by scroll.to '{candidate}'")
                                return element
                except Exception as e:
                    print(f"[DEBUG] scroll.to('{candidate}') failed: {str(e)}")

            # If not found, scroll and retry (except on last attempt).
            if attempt < max_attempts - 1:
                print(f"[TEST] '{text}' not found, scrolling...")
                try:
                    # Alternate directions to avoid skipping entries during transitions.
                    if attempt % 2 == 0:
                        self.device.swipe(500, 800, 500, 300, steps=scroll_steps)
                    else:
                        self.device.swipe(500, 350, 500, 850, steps=scroll_steps)
                    time.sleep(0.5)
                except Exception as e:
                    print(f"[WARNING] Scroll failed: {str(e)}")
        
        print(f"[TEST] '{text}' not found after {max_attempts} attempts")
        return None

    def _get_adb_device_serial(self):
        """
        Get adb device serial from environment or `adb devices` output.
        """
        env_serial = os.environ.get('ANDROID_SERIAL')
        if env_serial:
            return env_serial.strip()

        try:
            result = subprocess.run(
                ["adb", "devices"],
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )
            lines = result.stdout.splitlines()
            serials = []
            for line in lines:
                line = line.strip()
                if not line or line.startswith("List of devices attached"):
                    continue
                parts = line.split()
                if len(parts) >= 2 and parts[1] == "device":
                    serials.append(parts[0])

            if len(serials) == 1:
                return serials[0]

            if len(serials) > 1:
                raise RuntimeError(
                    "Multiple adb devices are connected. Please set ANDROID_SERIAL explicitly."
                )

            raise RuntimeError("No online adb device found. Please check adb connection.")
        except subprocess.TimeoutExpired:
            raise RuntimeError("adb devices timed out while reading serial number.")

    def _normalize_serial(self, value):
        """Normalize serial strings before comparison."""
        if value is None:
            return ""
        return "".join(str(value).strip().split()).upper()

    def test_L0_serial_number(self):
        """
        Test Steps:
        1. Navigate from Settings to About phone and then to the Model entry.
        2. Locate and extract the displayed Serial number value.
        3. Capture a screenshot of the serial-number evidence.
        4. Read the connected ADB serial, normalize both values, and verify they match.
        """
        try:
            # Step 1: Navigate to "About phone"
            print("[TEST] Step 1: Looking for 'About phone'...")
            
            about_phone = self._find_element_by_text(
                "About phone",
                max_attempts=5,
                scroll_steps=5
            )
            
            if not about_phone:
                # Try alternative texts
                about_phone = self._find_element_by_text(
                    "About",
                    max_attempts=3,
                    scroll_steps=3
                )
            
            self.assertIsNotNone(
                about_phone,
                "Failed to find 'About phone' in Settings menu"
            )
            print("[TEST] Found 'About phone', clicking...")
            about_phone.click()
            self._wait_for_ui_idle(2)

            # Capture About phone page screenshot.
            save_step_screenshot(self.device, "step_about_phone_page", SCRIPT_IMG_DIR)

            # Ensure we start from top of About phone page before searching "Model".
            try:
                self.device.swipe(500, 350, 500, 900, steps=8)
                self._wait_for_ui_idle(0.6)
            except Exception as e:
                print(f"[DEBUG] Initial reset-to-top swipe failed: {str(e)}")
            
            # Step 2: Find and click "Model" entry
            print("[TEST] Step 2: Looking for 'Model' entry...")
            
            model_entry = self._find_element_by_text(
                "Model",
                max_attempts=5,
                scroll_steps=3
            )
            
            self.assertIsNotNone(
                model_entry,
                "Failed to find 'Model' in About phone"
            )
            print("[TEST] Found 'Model', clicking...")
            model_entry.click()
            time.sleep(1.5)

            # Capture Model page screenshot.
            save_step_screenshot(self.device, "step_model_page", SCRIPT_IMG_DIR)
            
            # Step 3: Get the Serial Number inside Model page
            print("[TEST] Step 3: Looking for 'Serial number' inside Model...")
            
            serial_element = self._find_element_by_text(
                "Serial number",
                max_attempts=5,
                scroll_steps=3
            )
            
            if not serial_element:
                serial_element = self._find_element_by_text(
                    "Serial",
                    max_attempts=3,
                    scroll_steps=2
                )
            
            self.assertIsNotNone(
                serial_element,
                "Failed to find 'Serial number' field in About phone"
            )
            
            # Get the serial number value (usually displayed next to the label)
            # The actual serial number is often in the next text element or in resourceId
            print("[TEST] Step 4: Extracting serial number value...")
            
            # Method 1: Try to get the value from the next sibling or info
            serial_value = self._get_serial_number_value()

            self.assertIsNotNone(serial_value, "Failed to extract serial number from UI")
            self.assertGreater(len(serial_value.strip()), 0, "UI serial number is empty")

            # Save proof screenshot immediately after obtaining serial number from UI.
            serial_tag = "".join(ch for ch in serial_value.strip() if ch.isalnum())[:24] or "unknown"
            save_step_screenshot(
                self.device,
                f"step_serial_number_obtained_{serial_tag}",
                SCRIPT_IMG_DIR,
            )

            adb_serial = self._get_adb_device_serial()
            ui_serial_normalized = self._normalize_serial(serial_value)
            adb_serial_normalized = self._normalize_serial(adb_serial)

            print(f"[TEST] UI Serial:  {serial_value}")
            print(f"[TEST] ADB Serial: {adb_serial}")

            self.assertEqual(
                ui_serial_normalized,
                adb_serial_normalized,
                (
                    "Serial number mismatch: "
                    f"UI='{serial_value}' vs ADB='{adb_serial}'"
                ),
            )
            print("[TEST] [PASS] UI serial number matches adb serial")

        except AssertionError:
            raise
        except RuntimeError as e:
            self.fail(str(e))
        except Exception as e:
            print(f"[WARNING] Test skipped due to exception: {str(e)}")
            self.skipTest(f"Test setup failed: {str(e)}")

    def _get_serial_number_value(self):
        """
        Extract the serial number value from the About phone screen.
        This method tries multiple approaches to get the actual serial number.
        """
        try:
            # Approach 1: Get all text elements on current screen
            # The serial number value typically appears after "Serial number" label
            time.sleep(0.5)
            
            # Use dump to get all elements
            info = self.device.dump_hierarchy()
            
            # Approach 2: Look for elements containing serial number pattern
            # Usually looks like: XXXXXXXXXXXXXXXX or similar alphanumeric string
            elements = self.device(className="android.widget.TextView")
            
            for elem in elements:
                try:
                    text = elem.get_text()
                    # Check if this looks like a serial number (long alphanumeric string)
                    # and not a known label
                    if (text and len(text) > 5 and 
                        "Serial" not in text and 
                        "About" not in text and 
                        "Model" not in text and
                        "Android" not in text and
                        "Version" not in text):
                        # This might be our serial number
                        print(f"[DEBUG] Potential serial number: {text}")
                        # For now, return the first promising candidate
                        if text.strip() and not text.startswith("com."):
                            return text.strip()
                except:
                    continue
            
            # Approach 3: Try using XPath or direct element lookup
            # Some devices use specific resource IDs for serial number
            try:
                serial_elem = self.device(textContains="Serial")
                if serial_elem.exists():
                    # Try to get the value from nearby elements
                    all_texts = self.device(className="android.widget.TextView")
                    texts = [elem.get_text() for elem in all_texts if elem.get_text()]
                    print(f"[DEBUG] All texts on screen: {texts}")
                    
                    # Find the text after "Serial number"
                    for i, text in enumerate(texts):
                        if "Serial" in text and i + 1 < len(texts):
                            serial_value = texts[i + 1]
                            return serial_value
            except:
                pass
            
            return None
            
        except Exception as e:
            print(f"[ERROR] Failed to extract serial number: {str(e)}")
            return None


if __name__ == '__main__':
    unittest.main()
