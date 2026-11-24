# ANDROIDCN-33117 Keyremap Test Notes

## Scope

Test case: `test_L2_EWR_31439_remapping_a_string_of_key_strokes_to_a_single_key_ANDROIDCN_33117.py`

The case verifies HOME remaps to `a`, `b`, `CTRL_LEFT,C`, and `CTRL_LEFT,V` using the launcher Google Search field.

## Observed Issues

### Launcher search field cannot be opened reliably

The launcher search container differs by device and launcher implementation. Fixed coordinates and a small set of resource IDs can miss the target search entry.

Impact: the remapped HOME event has no text input target.

### Search text is read as empty although text is visible

Google Search can assign focus to an empty wrapper node while the actual visible text is stored in a nested `android.widget.EditText`.

Impact: `scan_get_input_field_text()` may return an empty string even when the screenshot shows text such as `a`.

### TEXT editor confirmation button can be blocked by the soft keyboard

After entering a Keyremap TEXT value, the soft keyboard can cover or obstruct the `OK` action.

Impact: the mapping may not be saved before the test returns to the launcher.

### Copy verification can paste the value twice

When HOME is remapped to `CTRL_LEFT,C`, the search field contains `COPYTEST`. Clearing through an empty focused wrapper can leave the real EditText unchanged. A subsequent paste produces `COPYTESTCOPYTEST`.

Impact: step 3 fails even though the copy shortcut worked.

## Case-Specific Handling

After the HOME copy shortcut runs, the test must reopen the launcher search field and ensure it is empty before sending `KEYCODE_PASTE`:

```python
keyremap_tap_navbar_home(serial)
time.sleep(1)
if not self._open_empty_search():
    save_step_screenshot(d, "step3_search_not_reopened", SCRIPT_IMG_DIR)
    self.fail("Could not reopen and clear Search after the HOME copy shortcut")
run_adb_cmd(serial, "shell input keyevent KEYCODE_PASTE", log_print=False)
```

This keeps the fix local to ANDROIDCN-33117 and avoids changing shared scan behavior used by DCS and Scan Wedge cases.

## Verification History

- HOME -> `a`: passed.
- HOME -> `b`: passed.
- HOME -> `CTRL_LEFT,C`: copy action ran, but the initial test produced `COPYTESTCOPYTEST` because the original text was not cleared.
- Next validation: rerun step 3 and confirm the post-paste field is exactly `COPYTEST`.