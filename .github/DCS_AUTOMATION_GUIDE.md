# DCS Automation Test Authoring Guide

This guide captures the verified conventions for Data Collection Service (DCS) automation cases in this repository. It is based on the existing DCS framework and the real-device QR Code cases validated on 2026-08-28.

## Scope and Principles

- Store DCS cases in `case/dcs/`.
- Name each file `test_L<level>_<feature>_<symbology>_ANDROIDCN_<id>.py`.
- Keep one Jira case per test script and express the source case's expected result as a direct assertion.
- Reuse helpers from `common/adb_common.py` and `common/common_method.py`; do not introduce duplicate ADB or uiautomator2 wrappers.
- Preserve `# -*- coding:utf-8 -*-`, the existing `unittest` style, and focused changes.
- Implement and validate one case at a time. Do not begin the next source case until the current script passes on real hardware.

## Test Topology

Most scan-behavior cases use two Android devices:

| Role | Environment variable | Responsibility |
| --- | --- | --- |
| Scanner | `AUTONEXUS_DEV0_SN` | Configures Honeywell settings, triggers the scanner, and receives Wedge output. |
| Display device | `AUTONEXUS_DEV1_SN` | Displays the barcode fixture pushed by the test. |

Settings-only cases, such as input validation, only require `AUTONEXUS_DEV0_SN`.

All cases must load required serials explicitly. Do not silently select an arbitrary connected device:

```python
def _load_device_serials_from_environment():
    dev0 = (os.environ.get("AUTONEXUS_DEV0_SN") or "").strip()
    dev1 = (os.environ.get("AUTONEXUS_DEV1_SN") or "").strip()
    if not dev0 or not dev1:
        raise RuntimeError("AUTONEXUS_DEV0_SN and AUTONEXUS_DEV1_SN must be provided by the web task")
    return dev0, dev1
```

Before authoring a device test, confirm each serial is visible to ADB and can connect through `dcs_test_connect_u2`.

## Standard Case Lifecycle

Use a class-level uiautomator2 connection and reset both devices around every test:

```python
@classmethod
def _ensure_device_sessions(cls):
    if hasattr(cls, "d0") and hasattr(cls, "d1"):
        return
    if not dcs_test_wait_device_online(DEV0_SERIAL, 25) or not dcs_test_wait_device_online(DEV1_SERIAL, 25):
        raise RuntimeError("Configured test devices are offline")
    cls.d0 = dcs_test_connect_u2(DEV0_SERIAL)
    cls.d1 = dcs_test_connect_u2(DEV1_SERIAL)

def setUp(self):
    self.__class__._ensure_device_sessions()
    dcs_test_wake_and_unlock(DEV0_SERIAL, self.d0)
    dcs_test_wake_and_unlock(DEV1_SERIAL, self.d1)
    dcs_test_press_home(DEV0_SERIAL)
    dcs_test_press_home(DEV1_SERIAL)

def tearDown(self):
    dcs_test_cleanup_devices(DEV0_SERIAL, DEV1_SERIAL)
    dcs_test_press_home(DEV0_SERIAL)
    dcs_test_press_home(DEV1_SERIAL)
```

For settings-only tests, use one scanner session and call `dcs_test_cleanup_devices(DEV0_SERIAL, DEV0_SERIAL)` in `tearDown`. Before cleanup, dismiss an open value dialog with `android:id/button2` when it exists.

## Navigation and Configuration

Define label fallbacks once at module level and navigate via existing helpers:

```python
_SCANNING_LABELS = ["Scanning"]
_INTERNAL_SCANNER_LABELS = ["Internal Scanner", "Internal scanner"]
_DEFAULT_PROFILE_LABELS = ["Default profile", "Default Profile"]
_DATA_PROCESSING_LABELS = ["Data Processing Settings", "Data Processing"]
_SYMBOLOGY_LABELS = ["Symbology Settings", "Symbology"]
_QR_CODE_LABELS = ["QR Code", "QR code"]
```

Required helper flow:

1. Call `dcs_test_goto_data_processing_settings(...)` and set `Wedge` with `dcs_test_set_option_checked(device, "Wedge", True)`.
2. Call `dcs_test_goto_symbology_setting(...)` with the configured symbology labels.
3. Enable or disable the symbology with `dcs_test_set_option_checked`.
4. Capture a screenshot after meaningful configuration changes with `save_step_screenshot`.

Avoid raw coordinate taps and duplicated navigation code. The helpers already contain the required UI fallback behavior.

## Barcode Fixture and Scan Assertions

Place source barcode images under `files/images/dcs_imgs/`. Use a stable local path and an Android display path:

```python
QR_IMAGE_LOCAL = os.path.join(PROJECT_ROOT, "files", "images", "dcs_imgs", "QR.jpg")
QR_IMAGE_REMOTE = "/sdcard/Pictures/QR.jpg"
```

For every scan attempt:

1. Show the fixture using `dcs_test_prepare_image_on_display_device`.
2. Focus the scanner's target field using `scan_open_input_field`.
3. Clear prior content using `scan_clear_input_field`.
4. Trigger scan using `dcs_test_trigger_honeywell_scan`.
5. Detect output using `scan_verify_decode_result`.
6. Read output only if detected with `scan_get_input_field_text`.
7. Assert both the expected decode state and, when relevant, the decoded content.

The QR fixture used in the verified cases decoded to `ABCDEFGH` with length `8`. Do not hard-code a fixture payload or length unless the source case requires that exact data. A robust boundary case first scans a known-valid fixture, derives `sample_length = len(sample_value)`, and then tests the adjacent boundaries.

When a source case says "more than one times", run at least three independent fixture-display and scan rounds. For enabled behavior, check that all results are non-empty and consistent. For disabled or rejected behavior, assert that every round has no detected output.

## Length Setting Cases

Length configuration uses Android dialog resource IDs:

```python
_EDIT_RESOURCE_ID = "android:id/edit"
_OK_RESOURCE_ID = "android:id/button1"
_CANCEL_RESOURCE_ID = "android:id/button2"
```

Use the following behavior for valid values:

```python
device(text=setting_name).click()
edit = device(resourceId=_EDIT_RESOURCE_ID)
self.assertTrue(edit.exists, f"{setting_name} dialog did not open")
edit.set_text(str(value))
device(resourceId=_OK_RESOURCE_ID).click()
```

For invalid values, the product may reject a save in either of two valid UI forms:

- The dialog remains open after pressing `OK`. This directly proves the candidate was not saved; screenshot the dialog and press `Cancel`.
- The dialog closes but reopening the setting shows the original value. Assert that the persisted value remains unchanged.

Do not assume all symbologies share the same allowed maximum. The verified QR Code range was `1` through `7089`; discover or read each symbology's actual bounds before constructing an upper-bound test. To avoid a false result, navigate back to the symbology page before locating a setting that may be off-screen after an earlier dialog interaction.

## Screenshot Evidence

Every case must create its own image directory:

```python
SCRIPT_BASENAME = os.path.splitext(os.path.basename(__file__))[0]
SCRIPT_IMG_DIR = os.path.join(PROJECT_ROOT, "img", SCRIPT_BASENAME)
os.makedirs(SCRIPT_IMG_DIR, exist_ok=True)
```

Use stable, ordered step names such as `step02_qr_enabled_round1` and `step05_maximum_above_accepted_limit`. Screenshots are the evidence retained in the HTML report and help distinguish product behavior from a navigation failure.

## Real-Device Validation Gate

Run each new case alone immediately after writing it:

```powershell
$env:AUTONEXUS_DEV0_SN='<scanner-serial>'
$env:AUTONEXUS_DEV1_SN='<display-serial>'
& .\.venv\Scripts\python.exe .\case\dcs\test_L1_EnableDisable_QR_Code_ANDROIDCN_37437.py
```

For scanner-only cases, set only `AUTONEXUS_DEV0_SN`. A successful Python exit code and `OK` from `unittest` are required before authoring the next case. A syntax check or a mocked run is not a replacement for real-device validation.

After all cases in a source workbook pass individually, run a filtered regression through `run_all.py`:

```powershell
$env:AUTONEXUS_DEV0_SN='<scanner-serial>'
$env:AUTONEXUS_DEV1_SN='<display-serial>'
$env:AUTONEXUS_CASE_LIST='["dcs/test_L1_MinimumLength_QR_Code_ANDROIDCN_37400.py","dcs/test_L1_EnableDisable_QR_Code_ANDROIDCN_37437.py"]'
& .\.venv\Scripts\python.exe .\run_all.py
```

`AUTONEXUS_CASE_LIST` must be a JSON array of paths relative to `case/`. Read the final HTML report rather than relying only on progress text. The report is the authoritative aggregate result; it contains per-test failure details and screenshots.

## Troubleshooting Checklist

| Symptom | Likely cause | Action |
| --- | --- | --- |
| Device is offline | Missing serial, disconnected USB, or unavailable ADB | Check `adb devices`, set the appropriate `AUTONEXUS_DEV*_SN`, and rerun the smallest affected test. |
| Barcode never decodes while enabled | Incorrect fixture, image not displayed, input lacks focus, or symbology is disabled | Verify the fixture manually on the display device, then inspect the step screenshot and setup assertions. |
| Expected rejection logs `No barcode detected` | This is expected for a rejection assertion | Evaluate the test's `detected == False` assertion, not the helper's informational log label. |
| Invalid value leaves a dialog open | Product rejected the save without dismissing the dialog | Assert the dialog remains open, capture evidence, and cancel it before cleanup. |
| Setting row cannot be found in a suite but works standalone | Current screen is not the symbology page or the row is outside the visible viewport | Re-enter the symbology settings through `dcs_test_goto_symbology_setting` before locating the row. |
| A filtered regression progress marker says OK while the report has a failure | Progress wrapper can be misleading for some failures | Treat the `unittest` result and generated HTML report as the source of truth. |

## Verified QR Examples

- `ANDROIDCN-37400`: minimum length rejects a fixture at `length + 1` and accepts it at its exact length, each boundary exercised three times.
- `ANDROIDCN-37437`: enabling QR Code yields three consistent decoded values; disabling it yields three rejected scans.
- `ANDROIDCN-37443`: non-numeric and invalid min/max values cannot be saved; valid rejection can retain the dialog on screen.
- `ANDROIDCN-37515`: maximum length rejects a fixture at `length - 1` and accepts it at its exact length, each boundary exercised three times.

Reference implementations are in `case/dcs/test_L1_*_QR_Code_ANDROIDCN_*.py`.