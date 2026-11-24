# __author__ = 'H339143'
# -*- coding:utf-8 -*-

"""
L1 Battery Health Value Test

Read the Battery Health percentage from two entries: Honeywell Settings -> Battery Optimizer -> Overall Health
Decision rule: both percentage values are read and fall within 0~100 -> PASS.

Steps:
1. Open Honeywell Settings -> Battery Optimizer -> Overall Health and read the percentage

2. Decision: both values are valid percentages (0~100) -> PASS
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
from common.common_method import battery_optimizer_restore_none

# Connect device via ANDROID_SERIAL environment variable
serial = get_device_serial()
d = u2.connect(serial)

SCRIPT_BASENAME = os.path.splitext(os.path.basename(__file__))[0]
IMG_ROOT = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.realpath(__file__)))), 'img')
SCRIPT_IMG_DIR = os.path.join(IMG_ROOT, SCRIPT_BASENAME)
os.makedirs(SCRIPT_IMG_DIR, exist_ok=True)

_PKG_HW_SETTINGS = 'com.honeywell.settings'
# Possible wordings of each entry's label across different firmware versions
_BATTERY_OPTIMIZER_LABELS = ('Battery Optimizer',)
_OVERALL_HEALTH_LABELS = ('Overall Health', 'Overall health')

_PERCENT_RE = re.compile(r'(\d+)\s*%')


def _adb_shell(command):
    """Run an adb shell command and return the stdout string."""
    out = run_adb_cmd(serial, f'shell {command}', log_print=False)
    if isinstance(out, bytes):
        return out.decode('utf-8', errors='ignore').strip()
    return str(out).strip()


def _click_entry(labels):
    """Locate and click an entry matching one of labels using multiple strategies. Returns True on hit."""
    for kw in labels:
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


def _open_honeywell_settings():
    """Force-restart Honeywell Settings and wait for it to come to the foreground."""
    _adb_shell(f'am force-stop {_PKG_HW_SETTINGS}')
    time.sleep(0.5)
    _adb_shell(f'am start --activity-clear-task -n {_PKG_HW_SETTINGS}/.MainActivity')

    # Wait for Honeywell Settings to actually come to the foreground so the UI can be dumped
    for _ in range(3):
        time.sleep(1)
        if (d.info.get('currentPackageName') or '') == _PKG_HW_SETTINGS:
            break
    else:
        print(f"[Navigation] HW Settings did not come to foreground, current package = '{d.info.get('currentPackageName')}'", flush=True)
    time.sleep(1)


def _navigate_to(labels, description):
    """Locate and click an entry, scrolling/swiping up if needed. Returns True on success."""
    # Prefer scrolling directly to the target item using a scrollable container
    if d(scrollable=True).exists(timeout=1):
        for kw in labels:
            try:
                if d(scrollable=True).scroll.to(textContains=kw):
                    print(f"[Navigation] scroll.to hit '{kw}'", flush=True)
                    break
            except Exception:
                pass

    # Multiple rounds: locate and click -> on failure swipe up and keep searching
    for i in range(3):
        if _click_entry(labels):
            print(f"[Navigation] Round {i + 1}: successfully entered '{description}'", flush=True)
            time.sleep(1.5)
            return True
        d.swipe_ext('up', scale=0.4)
        time.sleep(0.5)

    # On failure, print the current hierarchy to help debug the actually visible text
    print(f"[Navigation] '{description}' not found, current hierarchy:", flush=True)
    try:
        print(d.dump_hierarchy()[:2000], flush=True)
    except Exception as e:
        print(f'[Navigation] dump_hierarchy failed: {e}', flush=True)
    return False


def _read_percentage(labels):
    """Read a percentage value near one of labels (or anywhere on screen). Returns int (0~100) or None."""
    xml = d.dump_hierarchy()
    for label in labels:
        idx = xml.find(label)
        if idx != -1:
            snippet = xml[idx: idx + 600]
            m = _PERCENT_RE.search(snippet)
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

    print('[Read] Failed to extract a percentage value', flush=True)
    return None


class TestL1BatteryHealthValue(unittest.TestCase):
    """L1 Battery Health Value: verify percentage value from Battery Optimizer."""

    def setUp(self):
        d.screen_on()
        d.press('home')
        _adb_shell(f'am force-stop {_PKG_HW_SETTINGS}')
        time.sleep(1)

    def tearDown(self):
        try:
            self.assertTrue(battery_optimizer_restore_none(d, serial), 'Cleanup FAIL: unable to restore the None profile')
        finally:
            _adb_shell(f'am force-stop {_PKG_HW_SETTINGS}')
            d.press('home')

    def test_L1_battery_health_value(self):
        """Step1 read Overall Health under Battery Optimizer; valid percentage -> PASS."""
        # Step 1: Honeywell Settings -> Battery Optimizer -> Overall Health
        print('\n[Step 1] Open Honeywell Settings -> Battery Optimizer -> Overall Health', flush=True)
        _open_honeywell_settings()
        opened = _navigate_to(_BATTERY_OPTIMIZER_LABELS, 'Battery Optimizer')
        self.assertTrue(opened, 'Step 1 FAIL: unable to enter Battery Optimizer')
        opened = _navigate_to(_OVERALL_HEALTH_LABELS, 'Overall Health')
        self.assertTrue(opened, 'Step 1 FAIL: unable to enter Overall Health')
        overall_health = _read_percentage(_OVERALL_HEALTH_LABELS)
        save_step_screenshot(d, 'step1_overall_health', SCRIPT_IMG_DIR)
        self.assertIsNotNone(overall_health, 'Step 1 FAIL: Overall Health percentage not read (value is empty)')
        self.assertTrue(0 <= overall_health <= 100, f'Step 1 FAIL: Overall Health = {overall_health}%, out of range')
        print(f'[Step 1] PASS - Overall Health = {overall_health}%', flush=True)


if __name__ == '__main__':
    unittest.main(verbosity=2)
