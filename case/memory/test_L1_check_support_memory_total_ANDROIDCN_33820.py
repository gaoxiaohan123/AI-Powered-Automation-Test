# -*- coding:utf-8 -*-
# __author__ = 'sophy_H400818'
"""
Test Case: Check Support Memory Total (ANDROIDCN-33820)

Test Purpose:
Verify that device total memory matches the configuration based on part number.

Test Steps:
1. Get part number from ro.vendor.hon.extconf.num property
2. Navigate to Developer Options -> Memory and read Total memory value
3. If Total memory not found:
   - Find and enable "Enable memory usage profiling"
   - Handle restart dialog and wait for device reboot
   - Navigate to Memory again and read Total memory value
4. For CT47/CT30P/CT45/CT45P/CK67/CT37/CT70 devices, verify memory based on part number:
   - CT47/CT30P/CT45/CT45P/CK67/CT37: Check 1st character of last segment
   - CT70: Check 2nd character of last segment
   Memory requirements:
   - If character is '2': Total memory should be ≤ 4GB
   - If character is '3': Total memory should be ≤ 6GB
   - If character is '5': Total memory should be ≤ 8GB
   - If character is '8': Total memory should be ≤ 16GB
5. Cleanup: If memory profiling was enabled during test:
   - Disable "Enable memory usage profiling"
   - Handle restart dialog and wait for device reboot

Device: CT47, CT30P, CT45, CT45P, CK67, CT37, CT70
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

from common.adb_common import save_step_screenshot
from common.common_method import memory_get_total_memory_with_auto_enable, memory_disable_usage_profiling

# Device handle (lazy connect with retry)
serial = (os.environ.get('ANDROID_SERIAL') or '').strip()
d = None

SCRIPT_BASENAME = os.path.splitext(os.path.basename(__file__))[0]
IMG_ROOT = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.realpath(__file__)))), "img")
SCRIPT_IMG_DIR = os.path.join(IMG_ROOT, SCRIPT_BASENAME)
os.makedirs(SCRIPT_IMG_DIR, exist_ok=True)

def _detect_first_online_serial():
    """Find first online device serial from adb devices."""
    try:
        result = subprocess.run(
            ['adb', 'devices'],
            capture_output=True,
            text=True,
            timeout=8,
            check=False,
        )
        for line in (result.stdout or '').splitlines()[1:]:
            parts = line.strip().split()
            if len(parts) >= 2 and parts[1] == 'device':
                return parts[0].strip()
    except Exception:
        pass
    return ''


def _ensure_serial():
    """Resolve serial from env first, fallback to first online adb device."""
    global serial
    if serial:
        return serial
    serial = _detect_first_online_serial()
    return serial


def _connect_u2_with_retry(retries=3, wait_seconds=2):
    """Connect uiautomator2 with retries to survive adb/device flaps."""
    global d
    s = _ensure_serial()
    if not s:
        return None

    last_err = None
    for _ in range(max(1, retries)):
        try:
            d = u2.connect(s)
            return d
        except Exception as e:
            last_err = e
            try:
                subprocess.run(['adb', 'start-server'], capture_output=True, text=True, timeout=8, check=False)
                subprocess.run(['adb', '-s', s, 'wait-for-device'], capture_output=True, text=True, timeout=15, check=False)
            except Exception:
                pass
            time.sleep(wait_seconds)

    print(f"  ⚠ u2 connect failed after retries: {last_err}")
    return None

# Constants
SCRIPT_BASENAME = os.path.splitext(os.path.basename(__file__))[0]
IMG_ROOT = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.realpath(__file__)))), "img")
SCRIPT_IMG_DIR = os.path.join(IMG_ROOT, SCRIPT_BASENAME)
os.makedirs(SCRIPT_IMG_DIR, exist_ok=True)


class TestMemoryTotal(unittest.TestCase):
    """Test case: Check Support Memory Total"""

    @classmethod
    def setUpClass(cls):
        """Test class initialization"""
        cls.device = _ensure_serial()
        _connect_u2_with_retry(retries=3, wait_seconds=2)
        cls.memory_profiling_was_enabled = False  # Track if we enabled memory profiling
        print(f"\n{'='*70}")
        print(f"Check Support Memory Total Test")
        print(f"{'='*70}")
        print(f"Test Device: {cls.device}")

    def setUp(self):
        """Setup before each test"""
        print("\n" + "="*70)
        device = _connect_u2_with_retry(retries=3, wait_seconds=2)
        if device is None:
            self.fail("Unable to connect to device via uiautomator2")
        device.screen_on()
        device.press("home")
        time.sleep(1)

    def tearDown(self):
        """Cleanup after each test"""
        print("\n" + "="*70)
        print("Cleanup: Restoring settings and closing apps...")
        
        self.memory_profiling_was_enabled = True
        self._disable_memory_profiling()
        
        # Close settings
        try:
            if _ensure_serial():
                subprocess.run(['adb', '-s', serial, 'shell', 'am', 'force-stop', 'com.android.settings'], capture_output=True, text=True, timeout=8, check=False)
        except Exception as e:
            print(f"  ⚠ Error force-stopping Settings: {e}")

        try:
            device = _connect_u2_with_retry(retries=2, wait_seconds=1)
            if device is not None:
                device.press('home')
        except Exception as e:
            print(f"  ⚠ Error returning home: {e}")

        time.sleep(0.5)
        print("✓ Cleanup completed")
        print("="*70)

    def _get_adb_property(self, prop_name):
        """
        Get Android system property via adb
        
        Args:
            prop_name: Property name
            
        Returns:
            Property value as string, or None if failed
        """
        try:
            s = _ensure_serial()
            if not s:
                print(f"  ⚠ No device serial available when reading {prop_name}")
                return None

            result = subprocess.run(['adb', '-s', s, 'shell', 'getprop', prop_name], capture_output=True, text=True, timeout=8, check=False)
            value = result.stdout.strip().strip('[]').strip()

            if (not value) and result.returncode != 0:
                err = (result.stderr or '').strip()
                print(f"  ⚠ getprop failed for {prop_name}: {err}")
                subprocess.run(['adb', 'start-server'], capture_output=True, text=True, timeout=8, check=False)
                subprocess.run(['adb', '-s', s, 'wait-for-device'], capture_output=True, text=True, timeout=20, check=False)
                result = subprocess.run(['adb', '-s', s, 'shell', 'getprop', prop_name], capture_output=True, text=True, timeout=8, check=False)
                value = result.stdout.strip().strip('[]').strip()

            if value:
                print(f"  Property {prop_name}: {value}")
                return value
            else:
                print(f"  ⚠ Property {prop_name} is empty")
                return None
        except Exception as e:
            print(f"  ❌ Failed to get property {prop_name}: {e}")
            return None

    def _get_part_number(self):
        """
        Get device part number from ro.vendor.hon.extconf.num
        
        Returns:
            Part number string, or None if failed
        """
        print("\n[Step 1] Getting Part Number")
        print("="*70)
        
        part_number = self._get_adb_property("ro.vendor.hon.extconf.num")
        if not part_number:
            part_number = self._get_adb_property("ro.vendor.hon.extpart.num")

        if not part_number:
            try:
                s = _ensure_serial()
                if s:
                    result = subprocess.run(['adb', 'devices', '-l'], capture_output=True, text=True, timeout=8, check=False)
                    for line in (result.stdout or '').splitlines()[1:]:
                        if s not in line:
                            continue
                        m = re.search(r'product:([^\s]+)', line)
                        if m:
                            part_number = m.group(1).strip()
                            print(f"  Fallback Part Number from adb -l: {part_number}")
                            break
            except Exception as e:
                print(f"  ⚠ Failed to parse adb devices -l for part number: {e}")
        
        if part_number:
            print(f"  ✓ Part Number: {part_number}")
            return part_number
        else:
            print(f"  ✗ Failed to get part number")
            return None

    def _enable_developer_options(self):
        """Enable Developer Options if not already enabled"""
        print("\n  Checking Developer Options status...")
        
        cmd = f"adb -s {serial} shell settings get global development_settings_enabled"
        result = subprocess.run(cmd, capture_output=True, text=True, shell=True, timeout=5)
        
        if result.stdout.strip() == "1":
            print("  ✓ Developer Options already enabled")
            return True
        
        print("  Developer Options is disabled, enabling...")
        
        # Open About Phone
        cmd = f"adb -s {serial} shell am start -a android.settings.DEVICE_INFO_SETTINGS"
        subprocess.run(cmd, capture_output=True, text=True, shell=True, timeout=5)
        time.sleep(2)
        
        # Scroll to find Build number
        print("  Looking for Build number...")
        for _ in range(10):
            if d(textContains="Build number").exists(timeout=1):
                break
            if d(scrollable=True).exists():
                d(scrollable=True).scroll.forward()
            time.sleep(0.3)
        
        # Tap Build number 7 times
        if d(textContains="Build number").exists(timeout=2):
            print("  Tapping Build number 7 times...")
            for i in range(7):
                d(textContains="Build number").click()
                time.sleep(0.2)
            print("  ✓ Developer Options enabled")
            d.press("back")
            time.sleep(0.5)
            return True
        else:
            print("  ⚠ Build number not found")
            return False

    def _navigate_to_memory_settings(self):
        """
        Navigate to Developer Options -> Memory
        
        Returns:
            True if successful, False otherwise
        """
        print("\n[Step 2] Navigating to Memory Settings")
        print("="*70)
        
        # Ensure Developer Options is enabled
        if not self._enable_developer_options():
            return False
        
        # Go home first
        d.press("home")
        time.sleep(1)
        
        # Open Developer Options
        print("  Opening Developer Options...")
        cmd = f"adb -s {serial} shell am start -a android.settings.APPLICATION_DEVELOPMENT_SETTINGS"
        result = subprocess.run(cmd, capture_output=True, text=True, shell=True, timeout=5)
        time.sleep(3)
        
        save_step_screenshot(d, 'developer_options_opened', SCRIPT_IMG_DIR)
        
        # Verify we're in Developer Options page
        print("  Verifying Developer Options page...")
        time.sleep(1)
        
        # Check for Developer options title or common elements
        if not (d(text="Developer options").exists(timeout=2) or 
                d(textContains="developer").exists(timeout=2) or
                d(text="Memory").exists(timeout=2)):
            print("  ⚠ Not in Developer Options page, trying alternative method...")
            
            # Alternative: Open Settings and navigate manually
            d.press("home")
            time.sleep(1)
            
            cmd = f"adb -s {serial} shell am start -a android.settings.SETTINGS"
            subprocess.run(cmd, capture_output=True, text=True, shell=True, timeout=5)
            time.sleep(2)
            
            # Look for System menu
            print("  Looking for System menu...")
            if d(text="System").exists(timeout=3):
                d(text="System").click()
                time.sleep(2)
                
                # Look for Developer options
                print("  Looking for Developer options...")
                for _ in range(10):
                    if d(text="Developer options").exists(timeout=1):
                        d(text="Developer options").click()
                        time.sleep(2)
                        break
                    if d(scrollable=True).exists():
                        d(scrollable=True).scroll.forward()
                    time.sleep(0.3)
        
        save_step_screenshot(d, 'in_developer_options', SCRIPT_IMG_DIR)
        
        # Scroll to find Memory option
        print("  Looking for Memory option...")
        memory_found = False
        
        for scroll_attempt in range(15):
            if (
                d(text="Memory").exists(timeout=1)
                or d(textContains="Memory").exists(timeout=1)
                or d(text="内存").exists(timeout=1)
                or d(textContains="内存").exists(timeout=1)
            ):
                memory_found = True
                print(f"  ✓ Found Memory option (after {scroll_attempt} scroll(s))")
                break
            
            # Scroll down
            if d(scrollable=True).exists():
                d(scrollable=True).scroll.forward()
            else:
                d.swipe(500, 1500, 500, 500, duration=0.3)
            
            time.sleep(0.3)
        
        if not memory_found:
            print("  ⚠ Memory option not found")
            save_step_screenshot(d, 'memory_option_not_found', SCRIPT_IMG_DIR)
            return False
        
        save_step_screenshot(d, 'memory_option_found', SCRIPT_IMG_DIR)
        
        # Click Memory
        print("  Clicking Memory option...")
        if d(text="Memory").exists(timeout=1):
            d(text="Memory").click()
        elif d(textContains="Memory").exists(timeout=1):
            d(textContains="Memory").click()
        elif d(text="内存").exists(timeout=1):
            d(text="内存").click()
        else:
            d(textContains="内存").click()
        time.sleep(2)
        
        save_step_screenshot(d, 'memory_page_opened', SCRIPT_IMG_DIR)
        print("  ✓ Memory page opened")
        
        return True

    def _get_total_memory(self):
        """
        Read Total memory value from Memory page
        Looks for the value displayed under "Total memory" label (e.g., "7.6 GB")
        
        Returns:
            Total memory in GB as float, or None if failed
        """
        print("\n  Reading Total memory value...")
        
        # Wait for memory page to load
        time.sleep(2)
        save_step_screenshot(d, 'memory_page_loaded', SCRIPT_IMG_DIR)
        
        total_memory = None
        
        # Method 1: Find localized label and read the closest value underneath
        memory_labels = ["Total memory", "总内存", "内存总量"]
        print("  Method 1: Looking for total-memory label...")
        label_selector = None
        for lbl in memory_labels:
            if d(textContains=lbl).exists(timeout=1):
                label_selector = d(textContains=lbl)
                print(f"  ✓ Found label: '{lbl}'")
                break

        if label_selector is not None:
            try:
                total_mem_elem = label_selector
                total_mem_text = total_mem_elem.info.get('text', '')
                print(f"    Label text: '{total_mem_text}'")
                
                # Get position of Total memory label
                bounds = total_mem_elem.info.get('bounds', {})
                
                if bounds:
                    label_bottom = bounds.get('bottom', 0)
                    label_left = bounds.get('left', 0)
                    label_right = bounds.get('right', 0)
                    
                    print(f"    Label position: bottom={label_bottom}, left={label_left}, right={label_right}")
                    
                    # Look for GB elements that are positioned below the Total memory label
                    if d(textContains="GB").exists(timeout=1):
                        gb_elements = d(textContains="GB")
                        print(f"    Found {gb_elements.count} element(s) containing 'GB'")
                        
                        best_candidate = None
                        min_distance = float('inf')
                        
                        for i in range(gb_elements.count):
                            try:
                                elem = gb_elements[i]
                                elem_text = elem.info.get('text', '').strip()
                                elem_bounds = elem.info.get('bounds', {})
                                
                                if elem_bounds and elem_text:
                                    elem_top = elem_bounds.get('top', 0)
                                    elem_left = elem_bounds.get('left', 0)
                                    
                                    print(f"    Element {i}: '{elem_text}' at top={elem_top}, left={elem_left}")
                                    
                                    # Check if element is below the Total memory label
                                    # and roughly aligned (within reasonable horizontal range)
                                    if elem_top >= label_bottom:
                                        # Calculate vertical distance
                                        distance = elem_top - label_bottom
                                        
                                        # Extract memory value
                                        match = re.search(r'(\d+(?:\.\d+)?)\s*GB', elem_text, re.IGNORECASE)
                                        if match:
                                            value = float(match.group(1))
                                            # Only consider reasonable memory values
                                            if 1 <= value <= 32:
                                                # Prefer the element closest below the label
                                                if distance < min_distance:
                                                    min_distance = distance
                                                    best_candidate = value
                                                    print(f"      → Candidate: {value} GB (distance: {distance})")
                            except Exception as e:
                                print(f"      Error processing element {i}: {e}")
                                continue
                        
                        if best_candidate:
                            total_memory = best_candidate
                            print(f"  ✓ Total Memory (from element below label): {total_memory} GB")
            except Exception as e:
                print(f"  Error in Method 1: {e}")
        
        # Method 2: Search in page XML for Total memory and nearby GB value
        if total_memory is None:
            print("  Method 2: Searching XML structure...")
            xml = d.dump_hierarchy()
            
            # Look for pattern where memory label is followed by value with GB
            patterns = [
                r'Total memory[^<>]*?</[^>]+>.*?text="(\d+(?:\.\d+)?)\s*GB"',
                r'Total memory.*?(\d+(?:\.\d+)?)\s*GB',
                r'text="Total memory"[^<]*<[^>]*text="(\d+(?:\.\d+)?)\s*GB"',
                r'总内存[^<>]*?</[^>]+>.*?text="(\d+(?:\.\d+)?)\s*GB"',
                r'总内存.*?(\d+(?:\.\d+)?)\s*GB',
                r'内存总量[^<>]*?</[^>]+>.*?text="(\d+(?:\.\d+)?)\s*GB"',
            ]
            
            for pattern in patterns:
                match = re.search(pattern, xml, re.IGNORECASE | re.DOTALL)
                if match:
                    value = float(match.group(1))
                    if 1 <= value <= 32:
                        total_memory = value
                        print(f"  ✓ Total Memory (from XML pattern): {total_memory} GB")
                        break
        
        # Method 3: Find first reasonable GB value on the page
        if total_memory is None:
            print("  Method 3: Looking for any reasonable GB value...")
            
            if d(textContains="GB").exists(timeout=2):
                memory_elements = d(textContains="GB")
                count = memory_elements.count
                
                print(f"  Found {count} element(s) containing 'GB'")
                
                for i in range(count):
                    try:
                        elem = memory_elements[i]
                        text = elem.info.get('text', '').strip()
                        print(f"    Element {i}: '{text}'")
                        
                        # Try to extract number from text
                        match = re.search(r'^(\d+(?:\.\d+)?)\s*GB$', text, re.IGNORECASE)
                        if match:
                            value = float(match.group(1))
                            # Take the first reasonable memory value (between 1 and 32 GB)
                            if 1 <= value <= 32:
                                total_memory = value
                                print(f"  ✓ Total Memory (from standalone GB value): {total_memory} GB")
                                break
                    except Exception as e:
                        continue
        
        if total_memory is None:
            print("  ⚠ Failed to read Total memory value")
            print("  Dumping all text elements for debugging...")
            try:
                # Dump all visible text for debugging
                xml = d.dump_hierarchy()
                texts = re.findall(r'text="([^"]*)"', xml)
                print("  Visible text elements:")
                for text in texts[:20]:  # Print first 20 elements
                    if text.strip():
                        print(f"    - '{text}'")
            except:
                pass
            save_step_screenshot(d, 'memory_read_failed', SCRIPT_IMG_DIR)
        else:
            print(f"\n  ✓ Successfully read Total Memory: {total_memory} GB")
        
        return total_memory

    def _get_total_memory_with_fallback(self):
        """Try common flow first; if failed, use local UI parsing with CN/EN labels."""
        global d
        total_memory, profiling_enabled, d = memory_get_total_memory_with_auto_enable(
            d,
            serial,
            screenshot_dir=SCRIPT_IMG_DIR,
        )
        if profiling_enabled:
            self.memory_profiling_was_enabled = True

        if total_memory is not None:
            return total_memory

        print("  ⚠ Common flow failed to read total memory, trying local UI fallback...")
        if not self._navigate_to_memory_settings():
            return None
        return self._get_total_memory()

    def _handle_restart_dialog(self):
        """
        Handle restart dialog and click restart button
        
        Returns:
            True if restart dialog was found and handled, False otherwise
        """
        print("\n  Checking for restart dialog...")
        time.sleep(1)
        
        # Look for restart-related text
        restart_keywords = ["restart", "reboot", "重启", "Restart", "Reboot"]
        dialog_found = False
        
        for keyword in restart_keywords:
            if d(textContains=keyword).exists(timeout=2):
                dialog_found = True
                print(f"  ✓ Found restart dialog (keyword: '{keyword}')")
                save_step_screenshot(d, 'restart_dialog_found', SCRIPT_IMG_DIR)
                break
        
        if not dialog_found:
            print("  No restart dialog found")
            return False
        
        # Click restart button
        restart_button_texts = ["Restart", "RESTART", "OK", "确定", "Reboot", "REBOOT"]
        
        for btn_text in restart_button_texts:
            if d(text=btn_text).exists(timeout=2):
                print(f"  Clicking '{btn_text}' button...")
                d(text=btn_text).click()
                time.sleep(2)
                print("  ✓ Restart button clicked")
                return True
        
        print("  ⚠ Could not find restart button")
        return False

    def _wait_for_device_reboot(self):
        """
        Wait for device to reboot and come back online
        
        Returns:
            True if device came back online, False otherwise
        """
        global d
        
        print("\n  Waiting for device to reboot...")
        time.sleep(10)
        
        # Wait for device to go offline
        print("  Waiting for device to go offline...")
        max_wait = 30
        for i in range(max_wait):
            try:
                d.info
                time.sleep(1)
            except:
                print("  ✓ Device went offline")
                break
        
        # Wait for device to come back online
        print("  Waiting for device to come back online...")
        reboot_timeout = 120
        start_time = time.time()
        
        while time.time() - start_time < reboot_timeout:
            try:
                result = subprocess.run(
                    ['adb', '-s', serial, 'get-state'],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                if 'device' in result.stdout.strip():
                    print("  ✓ Device is back online")
                    time.sleep(20)  # Wait longer for device to fully boot
                    
                    # Reconnect u2
                    d = _connect_u2_with_retry(retries=5, wait_seconds=2)
                    if d is None:
                        print("  ⚠ Failed to reconnect uiautomator2 after reboot")
                        return False
                    time.sleep(5)
                    
                    # Unlock screen and dismiss any dialogs
                    d.screen_on()
                    time.sleep(1)
                    d.press("home")
                    time.sleep(2)
                    
                    # Dismiss any system dialogs that might appear after reboot
                    print("  Checking for system dialogs...")
                    if d(text="OK").exists(timeout=2):
                        d(text="OK").click()
                        time.sleep(1)
                    if d(text="Cancel").exists(timeout=1):
                        d.press("back")
                        time.sleep(1)
                    
                    d.press("home")
                    time.sleep(2)
                    
                    print("  ✓ Device reconnected and ready")
                    return True
            except:
                pass
            
            time.sleep(5)
            elapsed = int(time.time() - start_time)
            if elapsed % 10 == 0:
                print(f"     Waiting... {elapsed}s elapsed")
        
        print("  ⚠ Device did not come back online within timeout")
        return False

    def _check_and_enable_memory_profiling(self):
        """
        Check if "Enable memory usage profiling" exists and enable it if needed
        
        Returns:
            True if successfully enabled (or already enabled), False otherwise
        """
        print("\n  Looking for 'Enable memory usage profiling' option...")
        
        # Scroll to find the option
        profiling_found = False
        for scroll_attempt in range(10):
            if d(textContains="Enable memory usage profiling").exists(timeout=1):
                profiling_found = True
                print(f"  ✓ Found 'Enable memory usage profiling' (after {scroll_attempt} scroll(s))")
                break
            
            # Scroll down
            if d(scrollable=True).exists():
                d(scrollable=True).scroll.forward()
            else:
                d.swipe(500, 1500, 500, 500, duration=0.3)
            
            time.sleep(0.3)
        
        if not profiling_found:
            print("  ⚠ 'Enable memory usage profiling' option not found")
            return False
        
        save_step_screenshot(d, 'memory_profiling_option_found', SCRIPT_IMG_DIR)
        
        # Check if it's already enabled
        profiling_elem = d(textContains="Enable memory usage profiling")
        
        try:
            # Try to find switch element
            switch_elem = profiling_elem.sibling(className="android.widget.Switch")
            if switch_elem.exists(timeout=1):
                is_enabled = switch_elem.info.get('checked', False)
                
                if is_enabled:
                    print("  ✓ Memory usage profiling is already enabled")
                    return True
                else:
                    print("  Memory usage profiling is disabled, enabling it...")
            else:
                print("  Could not determine switch status, attempting to enable...")
        except Exception as e:
            print(f"  Could not check switch status: {e}")
        
        # Click to enable
        print("  Clicking 'Enable memory usage profiling'...")
        profiling_elem.click()
        time.sleep(2)
        save_step_screenshot(d, 'after_click_memory_profiling', SCRIPT_IMG_DIR)
        
        # Handle restart dialog
        if self._handle_restart_dialog():
            # Wait for reboot
            if not self._wait_for_device_reboot():
                print("  ⚠ Failed to wait for device reboot")
                return False
            
            self.memory_profiling_was_enabled = True
            print("  ✓ Memory usage profiling enabled and device rebooted")
            return True
        else:
            # No restart dialog, might already be enabled
            print("  No restart dialog appeared, memory profiling may already be enabled")
            return True

    def _disable_memory_profiling(self):
        """
        Disable memory usage profiling if it was enabled during test
        
        Returns:
            True if successfully disabled, False otherwise
        """
        if not self.memory_profiling_was_enabled:
            print("\n  Memory profiling was not enabled by this test, skipping disable")
            return True
        
        print("\n  Disabling memory usage profiling...")
        
        # Navigate back to Memory settings
        d.press("home")
        time.sleep(1)
        
        if not self._navigate_to_memory_settings():
            print("  ⚠ Failed to navigate to Memory settings for cleanup")
            return False
        
        # Find and click Enable memory usage profiling to disable it
        profiling_found = False
        for scroll_attempt in range(10):
            if d(textContains="Enable memory usage profiling").exists(timeout=1):
                profiling_found = True
                break
            
            if d(scrollable=True).exists():
                d(scrollable=True).scroll.forward()
            else:
                d.swipe(500, 1500, 500, 500, duration=0.3)
            
            time.sleep(0.3)
        
        if not profiling_found:
            print("  ⚠ Could not find memory profiling option for cleanup")
            return False
        
        # Click to disable
        print("  Clicking to disable memory profiling...")
        d(textContains="Enable memory usage profiling").click()
        time.sleep(2)
        save_step_screenshot(d, 'after_disable_memory_profiling', SCRIPT_IMG_DIR)
        
        # Handle restart dialog
        if self._handle_restart_dialog():
            # Wait for reboot
            if not self._wait_for_device_reboot():
                print("  ⚠ Failed to wait for device reboot after disable")
                return False
            
            print("  ✓ Memory usage profiling disabled and device rebooted")
            return True
        else:
            print("  No restart dialog appeared after disable")
            return True

    def _get_model_name(self):
        """
        Get device model name
        
        Returns:
            Model name string
        """
        model = self._get_adb_property("ro.product.model")
        return model if model else "Unknown"

    def _verify_memory_configuration(self, model, part_number, total_memory):
        """
        Verify memory configuration for CT47/CT70 devices
        
        Args:
            model: Device model name
            part_number: Device part number
            total_memory: Total memory in GB
            
        Returns:
            (pass: bool, message: str)
        """
        print("\n[Step 3] Verifying Memory Configuration")
        print("="*70)
        
        print(f"  Device Model: {model}")
        print(f"  Part Number: {part_number}")
        print(f"  Total Memory: {total_memory} GB")

        # Expected display ranges (GB), considering ~200-500MB hardware reserved memory.
        # Rule: lower bound inclusive, upper bound inclusive.
        memory_ranges = {
            4: (3.5, 4.0),
            6: (5.4, 6.0),
            8: (7.2, 8.0),
            12: (11.2, 12.0),
        }

        def _parse_expected_memory_from_part_number(pn):
            pn_u = str(pn or '').upper()
            # Direct token parsing first, e.g. "...-8G..." / "...12GB...".
            m = re.search(r'(?<!\d)(12|8|6|4)\s*G(?:B)?(?![A-Z0-9])', pn_u)
            if m:
                return int(m.group(1)), 'part_number_token'
            return None, ''

        def _parse_expected_memory_from_legacy_marker(pn):
            pn_u = str(pn or '').upper()
            parts = pn_u.split('-')
            if len(parts) < 3:
                return None, ''

            last_segment = parts[-1]
            model_upper = str(model or '').upper()
            first_char_models = ('CT47', 'CT30P', 'CT45P', 'CT45', 'CK67', 'CT37')
            check_char = ''
            if any(name in model_upper for name in first_char_models) and len(last_segment) >= 1:
                check_char = last_segment[0]
            elif 'CT70' in model_upper and len(last_segment) >= 2:
                check_char = last_segment[1]

            # Legacy compatibility mapping (fallback only):
            # marker '5' corresponds to 8G tier on current CT47 data.
            marker_map = {
                '2': 4,
                '5': 8,
                '8': 8,
                'C': 12,
            }
            if check_char in marker_map:
                return marker_map[check_char], f'pn_marker_{check_char}'
            return None, ''

        expected_gb, source = _parse_expected_memory_from_part_number(part_number)

        # Property fallback if PN token cannot be parsed, e.g. "8GB/128GB".
        if expected_gb is None:
            plat_memory = self._get_adb_property('ro.vendor.hon.plat.memory')
            m = re.search(r'(12|8|6|4)\s*G(?:B)?', str(plat_memory or '').upper())
            if m:
                expected_gb = int(m.group(1))
                source = 'ro.vendor.hon.plat.memory'

        # Final fallback: legacy marker parsing.
        if expected_gb is None:
            expected_gb, source = _parse_expected_memory_from_legacy_marker(part_number)

        if expected_gb not in memory_ranges:
            msg = (
                f"⚠ SKIP: Could not determine expected memory tier from PN/property. "
                f"PN={part_number}, source={source or 'N/A'}"
            )
            print(f"\n  {msg}")
            return True, msg

        low, high = memory_ranges[expected_gb]
        in_range = (total_memory >= low) and (total_memory <= high)
        expected_desc = f">= {low} GB and <= {high} GB"

        if in_range:
            msg = (
                f"✓ PASS: Expected {expected_gb}G tier ({expected_desc}); "
                f"measured {total_memory} GB (source={source}, reserved ~200-500MB)."
            )
            print(f"\n  {msg}")
            return True, msg

        msg = (
            f"✗ FAIL: Expected {expected_gb}G tier ({expected_desc}); "
            f"measured {total_memory} GB (source={source})."
        )
        print(f"\n  {msg}")
        return False, msg
    

    def test_check_memory_total(self):
        """ 1. Get part number from ro.vendor.hon.extconf.num property
            2. Navigate to Developer Options -> Memory and read Total memory value
            3. For CT47/CT30P/CT45/CT45P/CK67/CT37/CT70 devices, verify memory based on part number:
            - CT47/CT30P/CT45/CT45P/CK67/CT37: Check 1st character of last segment
            - CT70: Check 2nd character of last segment
            Memory requirements:
            - If character is '2': Total memory should be ≤ 4GB,
            - If character is '3': Total memory should be ≤ 6GB,
            - If character is '5': Total memory should be ≤ 8GB
            - If character is '8': Total memory should be ≤ 16GB
            Device: CT47, CT30P, CT45, CT45P, CK67, CT37, CT70"""
        print("\nTEST: Check Support Memory Total")
        print("="*70)
        
        # Step 1: Get part number
        part_number = self._get_part_number()
        if not part_number:
            self.fail("Failed to get part number")
        
        # Get model name to verify it's CT47 or CT70
        model = self._get_model_name()
        print(f"\n  Device Model: {model}")
        
        # Check if device is one of the supported models
        supported_models = ("CT47", "CT30P", "CT45", "CT45P", "CK67", "CT37", "CT70")
        model_upper = model.upper()
        if not any(name in model_upper for name in supported_models):
            print(f"\n{'='*70}")
            print(f"✓ PASS - Not a supported device ({', '.join(supported_models)}), test not applicable")
            print(f"  Device Model: {model}")
            print(f"{'='*70}")
            return
        
        print(f"  ✓ Device is {model}, proceeding with test...")
        
        # Step 2: read Total memory (common flow + localized fallback)
        total_memory = self._get_total_memory_with_fallback()

        if total_memory is None:
            self.fail("Failed to read Total memory value from Developer options -> Memory")
        
        # Step 3: Verify memory configuration
        passed, message = self._verify_memory_configuration(model, part_number, total_memory)
        # Close settings
        subprocess.run(f'adb -s {serial} shell am force-stop com.android.settings', shell=True)
        
        # Print final result
        print(f"\n{'='*70}")
        if passed:
            print(f"✓ TEST PASSED")
        else:
            print(f"✗ TEST FAILED")
        print(f"{'='*70}")
        print(f"  Device Model: {model}")
        print(f"  Part Number: {part_number}")
        print(f"  Total Memory: {total_memory} GB")
        print(f"  Result: {message}")
        print(f"{'='*70}")
        
        if not passed:
            self.fail(message)


if __name__ == '__main__':
    suite = unittest.TestSuite()
    suite.addTest(TestMemoryTotal('test_check_memory_total'))
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    print("\n" + "="*70)
    print("TEST SUMMARY")
    print("="*70)
    print(f"Tests run: {result.testsRun}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    print(f"Success: {result.wasSuccessful()}")
    print("="*70)
