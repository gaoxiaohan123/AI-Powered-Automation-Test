# __author__ = 'H339143'
# -*- coding:utf-8 -*-

"""
L0 Battery Health Test

Read the Battery Health percentage via Honeywell Settings -> Battery.
Decision rule: percentage value is not 0 and not empty -> PASS.

Steps:
1. Open Honeywell Settings and enter the Battery page
2. Read the Battery Health percentage value
3. Decision: value is not 0 and not empty -> PASS
"""

import os
import re
import sys
import time
import unittest

# Ensure project root is importable when running this script directly
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.realpath(__file__)))))

import uiautomator2 as u2

from common.adb_common import get_device_serial, run_adb_cmd, save_step_screenshot

# Connect device via ANDROID_SERIAL environment variable
serial = get_device_serial()
d = u2.connect(serial)

SCRIPT_BASENAME = os.path.splitext(os.path.basename(__file__))[0]
IMG_ROOT = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.realpath(__file__)))), 'img')
SCRIPT_IMG_DIR = os.path.join(IMG_ROOT, SCRIPT_BASENAME)
os.makedirs(SCRIPT_IMG_DIR, exist_ok=True)

_PKG_HW_SETTINGS = 'com.honeywell.settings'
# Possible wordings of the Battery Health label across different firmware versions
_HEALTH_LABELS = ('Battery Health', 'Overall Health', 'Health')
_BATTERY_LABELS = ('Battery Optimizer', 'Battery')


def _adb_shell(command):
    """Run an adb shell command and return the stdout string."""
    out = run_adb_cmd(serial, f'shell {command}', log_print=False)
    if isinstance(out, bytes):
        return out.decode('utf-8', errors='ignore').strip()
    return str(out).strip()


def _click_battery_entry():
    """Locate and click the Battery entry on the current page using multiple strategies. Returns True on hit."""
    for kw in _BATTERY_LABELS:
        # 1) Exact text match
        if d(text=kw).exists(timeout=0.5):
            print(f"[Navigation] text exact match on '{kw}', clicking", flush=True)
            d(text=kw).click()
            return True
        # 2) resource-id(tv_name) + text-contains match (list item text widget)
        el = d(resourceId=f'{_PKG_HW_SETTINGS}:id/tv_name', textContains=kw)
        if el.exists(timeout=0.5):
            print(f"[Navigation] tv_name+textContains match on '{kw}', clicking", flush=True)
            el.click()
            return True
        # 3) Any widget whose text contains the keyword
        if d(textContains=kw).exists(timeout=0.5):
            print(f"[Navigation] textContains match on '{kw}', clicking", flush=True)
            d(textContains=kw).click()
            return True
    return False


def _open_battery_page():
    """Open Honeywell Settings and enter the Battery page. Returns True on success."""
    _adb_shell(f'am force-stop {_PKG_HW_SETTINGS}')
    time.sleep(0.5)
    _adb_shell(f'am start --activity-clear-task -n {_PKG_HW_SETTINGS}/.MainActivity')

    # Wait for Honeywell Settings to actually come to the foreground so the UI can be dumped
    # for _ in range(3):
    #     time.sleep(1)
    #     if (d.info.get('currentPackageName') or '') == _PKG_HW_SETTINGS:
    #         break
    # else:
    #     print(f"[Navigation] HW Settings did not come to foreground, current package = '{d.info.get('currentPackageName')}'", flush=True)
    # time.sleep(1)

    # Prefer scrolling directly to the target item using a scrollable container
    if d(scrollable=True).exists(timeout=1):
        for kw in _BATTERY_LABELS:
            try:
                if d(scrollable=True).scroll.to(textContains=kw):
                    print(f"[Navigation] scroll.to hit '{kw}'", flush=True)
                    break
            except Exception:
                pass

    # Multiple rounds: locate and click -> on failure swipe up and keep searching
    for i in range(3):
        if _click_battery_entry():
            print(f"[Navigation] Round {i+1}: successfully entered the Battery entry", flush=True)
            time.sleep(2)
            return True
        d.swipe_ext('up', scale=0.4)
        time.sleep(0.5)

    # On failure, print the current hierarchy to help debug the actually visible text
    print('[Navigation] Battery entry not found in HW Settings, current hierarchy:', flush=True)
    try:
        print(d.dump_hierarchy()[:2000], flush=True)
    except Exception as e:
        print(f'[Navigation] dump_hierarchy failed: {e}', flush=True)
    return False


def _read_battery_health():
    """Read the Battery Health percentage, return an integer (0~100); return None if not found."""
    # If a STATUS tab exists, switch to it first
    if d(text='STATUS').exists(timeout=2):
        d(text='STATUS').click()
        time.sleep(1)

    # Match "<number> %" near the Battery Health label
    xml = d.dump_hierarchy()
    for label in _HEALTH_LABELS:
        idx = xml.find(label)
        if idx != -1:
            snippet = xml[idx: idx + 600]
            m = re.search(r'(\d+)\s*%', snippet)
            if m:
                val = int(m.group(1))
                print(f"[Read] Parsed {val}% near '{label}'", flush=True)
                return val

    # Fallback: iterate over page elements to find text like "100 %"
    for e in d.xpath('//*[@text]').all():
        text = (e.attrib.get('text') or '').strip()
        m = re.match(r'^(\d+)\s*%$', text)
        if m:
            val = int(m.group(1))
            print(f"[Read] Found percentage text '{text}' -> {val}% while iterating elements", flush=True)
            return val

    print('[Read] Failed to extract the Battery Health percentage', flush=True)
    return None


class Test_L0_BatteryHealth(unittest.TestCase):
    """L0 Battery Health: verify the Battery Health percentage is not 0 or empty."""

    def setUp(self):
        d.screen_on()
        d.press('home')
        _adb_shell(f'am force-stop {_PKG_HW_SETTINGS}')
        time.sleep(1)

    def tearDown(self):
        _adb_shell(f'am force-stop {_PKG_HW_SETTINGS}')
        d.press('home')

    def test_L0_battery_health(self):
        """
        Test Steps:
        1. Open Honeywell Settings and navigate to the Battery page.
        2. Capture the Battery page and read the Battery Health percentage.
        3. Capture the value and verify it is present and greater than zero.
        4. Close Honeywell Settings and return to Home during cleanup.
        """
        # Step 1: Open Honeywell Settings -> Battery
        print('\n[Step 1] Open Honeywell Settings -> Battery', flush=True)
        opened = _open_battery_page()
        save_step_screenshot(d, 'step1_battery_page', SCRIPT_IMG_DIR)
        self.assertTrue(opened, 'Step 1 FAIL: unable to enter the Honeywell Settings Battery page')

        # Step 2: Read the Battery Health percentage
        print('\n[Step 2] Read the Battery Health percentage', flush=True)
        health = _read_battery_health()
        save_step_screenshot(d, 'step2_battery_health', SCRIPT_IMG_DIR)

        self.assertIsNotNone(health, 'Step 2 FAIL: Battery Health percentage not read (value is empty)')
        self.assertNotEqual(health, 0, 'Step 2 FAIL: Battery Health = 0%, abnormal battery health')
        print(f'[Step 2] PASS - Battery Health = {health}% (not 0 or empty)', flush=True)


if __name__ == '__main__':
    unittest.main(verbosity=2)
