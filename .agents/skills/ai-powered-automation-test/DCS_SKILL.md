---
name: ai-powered-automation-test
description: "Use when creating, modifying, or debugging Python Android automation cases in case/, especially DCS barcode scanner tests that use ADB, uiautomator2, two devices, scan verification, screenshots, and unittest."
---

# AI-Powered Android Automation Case Generation

Use this skill for new or changed Android automation cases under `case/`. It is the working guide for DCS scanner cases and follows the existing implementations in `case/dcs/`.

## When to use this skill

Use this skill when asked to:

- Create a Python automation case for an Android feature or scanner symbology.
- Add or change a DCS barcode configuration and scan-validation flow.
- Debug a DCS case that cannot connect to devices, navigate settings, trigger a scan, or verify decoded output.
- Add reliable screenshots, assertions, cleanup, or standalone execution to an existing case.

Do not use this skill for browser/Playwright tests. These cases drive Android devices through the existing ADB and uiautomator2 helpers.

## Required workflow

1. Read the closest existing case in the same `case/<feature>/` directory before editing. For DCS, use matching cases in `case/dcs/` as the primary pattern.
2. Read `.github/instructions/auto-case-coding.instructions.md` before modifying a Python case.
3. Reuse helpers from `common/adb_common.py` and `common/common_method.py`; do not add duplicate ADB or UI automation wrappers in the case file.
4. Keep the edit scoped to the requested behavior. Do not refactor unrelated test steps or common helpers unless they prevent the requested case from working.
5. Run the narrowest available validation after editing, such as `python -m py_compile <case-file>` or the specific case with the required devices configured.

## DCS case structure

New DCS cases should follow this structure unless the closest existing case demonstrates a necessary variation:

1. Preserve `# -*- coding:utf-8 -*-` and include a concise module docstring with the Jira case ID, case name, and expected behavior.
2. Import `os`, `sys`, and `unittest`, then add the project root to `sys.path` using the existing two-parent pattern.
3. Import existing DCS helpers for device setup and cleanup, settings navigation, output-field control, scan triggering, and screenshots.
4. Define `PROJECT_ROOT`, per-case screenshot directory under `img/<script-basename>/`, local barcode-image paths under `files/images/dcs_imgs/`, remote `/sdcard/Pictures/...` paths, and label aliases needed for UI variants.
5. Load `AUTONEXUS_DEV0_SN` and `AUTONEXUS_DEV1_SN` from the environment. Raise a clear `RuntimeError` if either is missing. `dev0` is the scanner device and `dev1` displays the reference barcode.
6. Use a `unittest.TestCase` class with `setUpClass`, `setUp`, and `tearDown`:
   - Wait for both devices and connect with `dcs_test_connect_u2`.
   - Wake and unlock both devices before each test.
   - Return both devices to Home in setup and cleanup.
   - Call `dcs_test_cleanup_devices` in `tearDown`.
7. Put repeated navigation or configuration operations in focused private helpers, such as `_goto_<symbology>_setting`, `_set_<property>`, or `_scan_sample`.
8. End with a `__main__` runner that loads the test class, uses `TextTestRunner(verbosity=2)`, and returns a process status based on `result.wasSuccessful()`.

## Scan verification rules

- Enable Wedge output before verifying scan output through an input field.
- Enable the target symbology or property explicitly before the positive scenario.
- Show the reference barcode on `dev1` with `dcs_test_prepare_image_on_display_device`.
- Focus and clear the scanner input on `dev0` before every scan using `scan_open_input_field` and `scan_clear_input_field`.
- Trigger scans only with `dcs_test_trigger_honeywell_scan` and assert that the trigger succeeds.
- Read outcomes using `scan_verify_decode_result` and `scan_get_input_field_text`.
- Verify every requested scenario at least three times unless the case requirement specifies another count.
- Assert the observable contract: successful decode, rejected decode, exact content, output length, or transformed output as appropriate. Do not rely only on log output.
- Capture a screenshot for each important configuration step and each scan round with `save_step_screenshot`.
- Accumulate repeated-round failures when useful, then fail once with round numbers and observed values so the report is actionable.

## Implementation conventions

- Use descriptive constants for UI labels and image paths. Include known label variants where existing cases do so.
- Use descriptive helper and test names that map directly to the case feature and expected behavior.
- Print numbered test steps and per-round results to make device-run logs readable.
- Keep test data and expected values local to the case unless an existing shared fixture already owns them.
- Prefer existing DCS navigation helpers over direct UI selectors. Use a direct selector only for a setting control that has no suitable helper.
- Preserve existing encoding, import style, and formatting in files being modified.

## Example case outline

```python
class Test_Feature_Symbology(unittest.TestCase):
	@classmethod
	def setUpClass(cls):
		if not dcs_test_wait_device_online(DEV0_SERIAL, 25):
			raise RuntimeError(f"dev0 offline: {DEV0_SERIAL}")
		if not dcs_test_wait_device_online(DEV1_SERIAL, 25):
			raise RuntimeError(f"dev1 offline: {DEV1_SERIAL}")
		cls.d0 = dcs_test_connect_u2(DEV0_SERIAL)
		cls.d1 = dcs_test_connect_u2(DEV1_SERIAL)

	def setUp(self):
		dcs_test_wake_and_unlock(DEV0_SERIAL, self.d0)
		dcs_test_wake_and_unlock(DEV1_SERIAL, self.d1)
		dcs_test_press_home(DEV0_SERIAL)
		dcs_test_press_home(DEV1_SERIAL)

	def tearDown(self):
		dcs_test_cleanup_devices(DEV0_SERIAL, DEV1_SERIAL)
		dcs_test_press_home(DEV0_SERIAL)
		dcs_test_press_home(DEV1_SERIAL)

	def test_feature_symbology(self):
		self.assertTrue(dcs_test_set_option_checked(self.d0, "Wedge", True))
		self.assertTrue(dcs_test_set_option_checked(self.d0, "Symbology", True))
		for round_number in range(1, 4):
			dcs_test_prepare_image_on_display_device(DEV1_SERIAL, self.d1, IMAGE_LOCAL, IMAGE_REMOTE)
			self.assertTrue(scan_open_input_field(self.d0, DEV0_SERIAL))
			scan_clear_input_field(self.d0)
			self.assertTrue(dcs_test_trigger_honeywell_scan(DEV0_SERIAL))
			self.assertTrue(scan_verify_decode_result(self.d0, max_wait_seconds=5))
			save_step_screenshot(self.d0, f"scan_round{round_number}", SCRIPT_IMG_DIR)
```

## Completion checklist

- Case file is in the correct `case/<feature>/` directory and follows its closest local example.
- Both device serial numbers come from `AUTONEXUS_DEV0_SN` and `AUTONEXUS_DEV1_SN`.
- Setup, cleanup, screenshots, and standalone runner are present.
- Every scan scenario has explicit assertions and the required repetition count.
- The generated or changed case passes syntax validation; report any device-dependent validation that could not be run.