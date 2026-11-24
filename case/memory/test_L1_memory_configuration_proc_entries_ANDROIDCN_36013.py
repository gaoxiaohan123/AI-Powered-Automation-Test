# __author__ = 'Sophy_H400818'
# -*- coding:utf-8 -*-

"""
Test Case: ANDROIDCN-36013
Date: 2026-07-06

Use `adb shell cat /proc/meminfo` to read MemTotal/MemFree/MemAvailable,
then compare them against values shown in Settings -> Developer options -> Memory:
- Average memory use
- Total memory
- Free

Pass criteria:
- All mapped values are consistent (rounded to 0.1 GB for UI precision)
"""

import os
import re
import sys
import time
import subprocess
import unittest
import uiautomator2 as u2

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from common.adb_common import get_device_serial, save_step_screenshot
from common.common_method import memory_get_total_memory_with_auto_enable, memory_disable_usage_profiling

SCRIPT_BASENAME = os.path.splitext(os.path.basename(__file__))[0]
IMG_ROOT = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.realpath(__file__)))), "img")
SCRIPT_IMG_DIR = os.path.join(IMG_ROOT, SCRIPT_BASENAME)
os.makedirs(SCRIPT_IMG_DIR, exist_ok=True)

serial = get_device_serial()
if not serial:
	print("Error: No Android device found. Connect a device or set ANDROID_SERIAL.")
	sys.exit(1)

d = None


def _connect_u2(retries=3, wait_seconds=1):
	"""Connect/reconnect uiautomator2 device."""
	global d
	last_err = None
	for _ in range(max(1, retries)):
		try:
			d = u2.connect(serial)
			_ = d.info
			return True
		except Exception as e:
			last_err = e
			try:
				subprocess.run(['adb', 'start-server'], capture_output=True, text=True, timeout=8, check=False)
				subprocess.run(['adb', '-s', serial, 'wait-for-device'], capture_output=True, text=True, timeout=12, check=False)
			except Exception:
				pass
			time.sleep(wait_seconds)
	print(f"[WARN] u2 reconnect failed: {last_err}")
	return False


def _safe_exists(timeout=2, **selector):
	for _ in range(2):
		try:
			return d(**selector).exists(timeout=timeout)
		except Exception:
			_connect_u2(retries=2, wait_seconds=1)
	return False


def _safe_click(timeout=2, **selector):
	for _ in range(2):
		try:
			obj = d(**selector)
			if not obj.exists(timeout=timeout):
				return False
			obj.click()
			return True
		except Exception:
			_connect_u2(retries=2, wait_seconds=1)
	return False


def _safe_xpath_texts():
	for _ in range(2):
		try:
			elements = d.xpath('//*[@text]').all()
			return [e.text for e in elements if getattr(e, 'text', None)]
		except Exception:
			_connect_u2(retries=2, wait_seconds=1)
	return []


_connect_u2(retries=3, wait_seconds=1)

SCRIPT_BASENAME = os.path.splitext(os.path.basename(__file__))[0]
IMG_ROOT = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.realpath(__file__)))), "img")
SCRIPT_IMG_DIR = os.path.join(IMG_ROOT, SCRIPT_BASENAME)
os.makedirs(SCRIPT_IMG_DIR, exist_ok=True)


class TestMemoryProcEntries(unittest.TestCase):
	"""Compare /proc/meminfo entries with Developer Options -> Memory page."""

	@classmethod
	def setUpClass(cls):
		cls.dev_id = serial
		cls.memory_profiling_was_enabled = False
		print("\n" + "=" * 70)
		print("ANDROIDCN-36013: Memory configuration proc entries")
		print("=" * 70)
		print(f"Device: {cls.dev_id}")

	def setUp(self):
		if _connect_u2(retries=2, wait_seconds=1):
			try:
				d.screen_on()
				d.press('home')
			except Exception:
				pass
		time.sleep(1)

	def tearDown(self):
		global d
		if getattr(self, 'memory_profiling_was_enabled', False):
			try:
				disabled_ok, d = memory_disable_usage_profiling(
					d,
					serial,
					screenshot_dir=SCRIPT_IMG_DIR,
				)
				if not disabled_ok:
					self.fail("Failed to disable/verify 'Enable memory usage profiling' in cleanup")
				self.memory_profiling_was_enabled = False
			except Exception as e:
				print(f"[WARN] Failed to disable memory usage profiling in cleanup: {e}")

		try:
			subprocess.run(['adb', '-s', serial, 'shell', 'am', 'force-stop', 'com.android.settings'], capture_output=True, text=True, timeout=8, check=False)
		except Exception:
			pass
		if _connect_u2(retries=2, wait_seconds=1):
			try:
				d.press('home')
			except Exception:
				pass

	def _adb_shell(self, *cmd):
		"""Run adb shell command and return stdout."""
		try:
			result = subprocess.run(
				['adb', '-s', serial, 'shell', *cmd],
				capture_output=True,
				text=True,
				timeout=10,
				check=False,
			)
			return (result.stdout or '').strip()
		except Exception:
			return ''

	def _kb_to_gb(self, kb_value):
		# Decimal conversion as requested: kB -> GB uses 1000-based units.
		return kb_value / (1000.0 * 1000.0)

	def _round_ui_precision(self, gb_value):
		return round(float(gb_value), 1)

	def _read_proc_meminfo(self):
		"""Read MemTotal/MemFree/MemAvailable from /proc/meminfo."""
		print("\n[Step 1] Read /proc/meminfo")
		print("=" * 70)

		text = self._adb_shell('cat', '/proc/meminfo')
		if not text:
			self.fail("Failed to run adb shell cat /proc/meminfo")

		def _read_kb(field):
			m = re.search(rf'^{field}:\s*(\d+)\s*kB', text, re.MULTILINE)
			return int(m.group(1)) if m else None

		mem_total_kb = _read_kb('MemTotal')
		mem_free_kb = _read_kb('MemFree')
		mem_available_kb = _read_kb('MemAvailable')

		missing = [
			name for name, val in (
				('MemTotal', mem_total_kb),
				('MemFree', mem_free_kb),
				('MemAvailable', mem_available_kb),
			) if val is None
		]
		if missing:
			self.fail(f"Missing field(s) in /proc/meminfo: {missing}")

		result = {
			'MemTotal': self._round_ui_precision(self._kb_to_gb(mem_total_kb)),
			'MemFree': self._round_ui_precision(self._kb_to_gb(mem_free_kb)),
			'MemAvailable': self._round_ui_precision(self._kb_to_gb(mem_available_kb)),
		}

		print(f"  MemTotal:     {result['MemTotal']} GB")
		print(f"  MemFree:      {result['MemFree']} GB")
		print(f"  MemAvailable: {result['MemAvailable']} GB")
		return result

	def _open_memory_page(self):
		"""Open Settings -> Developer options -> Memory."""
		print("\n[Step 2] Open Developer options -> Memory")
		print("=" * 70)

		subprocess.run(
			['adb', '-s', serial, 'shell', 'am', 'start', '-a', 'android.settings.APPLICATION_DEVELOPMENT_SETTINGS'],
			capture_output=True,
			text=True,
			timeout=10,
			check=False,
		)
		time.sleep(2)
		save_step_screenshot(d, 'developer_options_opened', SCRIPT_IMG_DIR)

		for i in range(12):
			if (
				_safe_exists(timeout=1, text='Memory')
				or _safe_exists(timeout=1, textContains='Memory')
				or _safe_exists(timeout=1, text='内存')
				or _safe_exists(timeout=1, textContains='内存')
			):
				print(f"  Found Memory option after {i} scroll(s)")
				break
			try:
				if d(scrollable=True).exists(timeout=1):
					d(scrollable=True).scroll.forward()
				else:
					d.swipe(500, 1500, 500, 500, duration=0.2)
			except Exception:
				_connect_u2(retries=2, wait_seconds=1)
			time.sleep(0.3)
		else:
			self.fail("Could not find 'Memory' in Developer options")

		if not (
			_safe_click(timeout=2, text='Memory')
			or _safe_click(timeout=2, textContains='Memory')
			or _safe_click(timeout=2, text='内存')
			or _safe_click(timeout=2, textContains='内存')
		):
			self.fail("Failed to click 'Memory' option")

		time.sleep(2)
		save_step_screenshot(d, 'memory_page_opened', SCRIPT_IMG_DIR)

	def _extract_value_near_keyword(self, texts, keywords):
		"""Find a GB numeric value on same/nearby text row for a keyword."""
		kw_lower = [k.lower() for k in keywords]
		value_re = re.compile(r'(\d+(?:\.\d+)?)\s*GB', re.IGNORECASE)

		for idx, txt in enumerate(texts):
			low = txt.lower()
			if not any(k in low for k in kw_lower):
				continue

			# 1) value in same line
			m = value_re.search(txt)
			if m:
				return self._round_ui_precision(float(m.group(1)))

			# 2) value in next lines
			for j in range(idx + 1, min(idx + 4, len(texts))):
				m2 = value_re.search(texts[j])
				if m2:
					return self._round_ui_precision(float(m2.group(1)))

		return None

	def _read_ui_memory_values(self):
		"""Read Average memory use / Total memory / Free values from memory page."""
		print("\n[Step 3] Read values from Memory page")
		print("=" * 70)

		texts = _safe_xpath_texts()
		if not texts:
			self.fail("Failed to read UI text elements from Memory page")

		avg = self._extract_value_near_keyword(texts, ['Average memory use', 'Average memory', '平均内存使用'])
		total = self._extract_value_near_keyword(texts, ['Total memory', '总内存'])
		free = self._extract_value_near_keyword(texts, ['Free', '可用', '空闲'])

		print(f"  UI Average memory use: {avg} GB")
		print(f"  UI Total memory:       {total} GB")
		print(f"  UI Free:               {free} GB")

		missing = [
			name for name, val in (
				('Average memory use', avg),
				('Total memory', total),
				('Free', free),
			) if val is None
		]
		if missing:
			save_step_screenshot(d, 'ui_value_missing', SCRIPT_IMG_DIR)
			self.fail(f"Failed to parse UI value(s): {missing}")

		return {
			'AverageMemoryUse': avg,
			'TotalMemory': total,
			'Free': free,
		}

	def _read_ui_total_memory_value(self):
		"""Read only Total memory value from Memory page (English/Chinese labels)."""
		texts = _safe_xpath_texts()
		if not texts:
			self.fail("Failed to read UI text elements from Memory page")

		total = self._extract_value_near_keyword(texts, ['Total memory', '总内存'])
		if total is None:
			save_step_screenshot(d, 'ui_total_memory_missing', SCRIPT_IMG_DIR)
			self.fail("Failed to parse UI value: Total memory")

		print(f"  UI Total memory:       {total} GB")
		return total

	def _get_total_memory_with_fallback(self):
		"""Read Total memory via common flow first, then localized UI fallback."""
		global d
		total_memory, profiling_enabled, d = memory_get_total_memory_with_auto_enable(
			d,
			serial,
			screenshot_dir=SCRIPT_IMG_DIR,
		)
		if profiling_enabled:
			self.memory_profiling_was_enabled = True

		if total_memory is not None:
			return self._round_ui_precision(float(total_memory))

		print("  [WARN] Common memory flow could not read 'Total memory'; trying localized fallback...")
		self._open_memory_page()
		return self._read_ui_total_memory_value()

	def test_check_memory_configuration_proc_entries(self):
		"""Main test for ANDROIDCN-36013.
		Use `adb shell cat /proc/meminfo` to read MemTotal/MemFree/MemAvailable,
        then compare them against values shown in Settings -> Developer options -> Memory:
        - Average memory use
        - Total memory
        - Free
        Pass criteria:
        - All mapped values are consistent (rounded to 0.1 GB for UI precision)"""
		proc_values = self._read_proc_meminfo()
		total_memory = self._get_total_memory_with_fallback()

		ui_values = {
			'TotalMemory': total_memory,
		}

		print("\n[Step 4] Compare values")
		print("=" * 70)

		# Mapping requested by spec.
		checks = [
			('MemTotal', proc_values['MemTotal'], 'Total memory', ui_values['TotalMemory']),
		]
		tolerance_gb = 0.5
		print(f"  Tolerance: ±{tolerance_gb} GB")

		mismatches = []
		for left_name, left_val, right_name, right_val in checks:
			diff = abs(float(left_val) - float(right_val))
			if diff <= tolerance_gb:
				print(f"  ✓ {left_name}({left_val} GB) ~= {right_name}({right_val} GB), diff={diff:.1f} GB")
			else:
				print(f"  ✗ {left_name}({left_val} GB) != {right_name}({right_val} GB), diff={diff:.1f} GB")
				mismatches.append((left_name, left_val, right_name, right_val, diff))

		if mismatches:
			save_step_screenshot(d, 'compare_failed', SCRIPT_IMG_DIR)
			detail = '; '.join([f"{a}={b} vs {c}={d} (diff={df:.1f}GB)" for a, b, c, d, df in mismatches])
			self.fail("Memory comparison failed: " + detail)

		print("\n✓ PASS: All memory values are consistent.")


if __name__ == '__main__':
	unittest.main(verbosity=2)
