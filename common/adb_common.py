# __author__ = 'H339143'
# -*- coding:utf-8 -*-

"""
    Define the various adb commands
"""

import os
import re
import subprocess
import time
import shutil
from urllib.parse import quote
from common.common_method import CommonMethod

# img directory: auto_test/img/
_IMG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.realpath(__file__))), 'img')


def _resolve_adb_bin():
    adb_on_path = shutil.which('adb')
    if adb_on_path:
        return adb_on_path

    env_candidates = [
        os.environ.get('ADB'),
        os.environ.get('ADB_PATH'),
    ]
    for key in ('ANDROID_SDK_ROOT', 'ANDROID_HOME'):
        root = os.environ.get(key)
        if root:
            env_candidates.append(os.path.join(root, 'platform-tools', 'adb.exe'))

    env_candidates.extend([
        os.path.join(os.path.expanduser('~'), 'AppData', 'Local', 'Android', 'Sdk', 'platform-tools', 'adb.exe'),
        r'C:\ADB\adb.exe',
        r'C:\platform-tools\adb.exe',
    ])

    for candidate in env_candidates:
        if candidate and os.path.exists(candidate):
            return candidate

    return 'adb'


ADB_BIN = _resolve_adb_bin()


def get_device_serial():
    """
    获取连接的设备 serial。
    优先使用环境变量 ANDROID_SERIAL；未设置时返回 adb devices 中的第一台设备。
    """
    serial = os.environ.get("ANDROID_SERIAL")
    if serial:
        return serial
    try:
        output = subprocess.run([ADB_BIN, "devices"], capture_output=True, text=True, check=False, timeout=10)
        for line in (output.stdout or "").splitlines()[1:]:
            line = line.strip()
            if line.endswith("\tdevice"):
                return line.split("\t")[0].strip()
    except Exception:
        pass
    return None


def adb_command(serial, *cmd_parts, timeout=8):
    """Execute an ADB command and return its completed-process result."""
    try:
        return subprocess.run(
            [ADB_BIN, "-s", serial, *cmd_parts],
            capture_output=True,
            text=True,
            errors="ignore",
            check=False,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        class _Ret:
            returncode = 1
            stdout = ""
            stderr = "adb command timeout"

        return _Ret()


def adb_shell(serial, *cmd_parts, timeout=8):
    """
    执行 adb shell 命令，包含超时保护。
    """
    return adb_command(serial, "shell", *cmd_parts, timeout=timeout)


def adb_shell_output(serial, *cmd_parts, timeout=8):
    """Execute an ADB shell command and return stripped stdout."""
    ret = adb_shell(serial, *cmd_parts, timeout=timeout)
    return (ret.stdout or "").strip()


# General_Settings_Method_Frank_Xu_2026-08-24
# Purpose: Read and write Android Settings-provider values for General Settings tests.
def setting_value(serial, namespace, key):
    """Return an Android Settings-provider value."""
    ret = adb_shell(serial, "settings", "get", namespace, key, timeout=15)
    if ret.returncode != 0:
        raise AssertionError("Unable to read {} setting '{}'".format(namespace, key))
    return (ret.stdout or "").strip()


def set_setting(serial, namespace, key, value):
    """Write an Android Settings-provider value."""
    ret = adb_shell(serial, "settings", "put", namespace, key, str(value), timeout=15)
    if ret.returncode != 0:
        raise AssertionError("Unable to write {} setting '{}'".format(namespace, key))


def device_file_exists(serial, remote_path, timeout=8):
    """Return whether a remote device file exists and is accessible."""
    out = adb_shell_output(serial, f"ls {remote_path} 2>/dev/null", timeout=timeout)
    return bool(out) and "No such file" not in out and "not found" not in out.lower()


def sdcard_find_mount_path(serial):
    """Return an accessible external SD card path, or None when unavailable."""
    mounts = adb_shell_output(serial, "cat /proc/mounts", timeout=12)
    if not mounts:
        return None

    volume_ids = []
    for line in mounts.splitlines():
        parts = line.split()
        if len(parts) < 2:
            continue
        mount_point = parts[1].strip()
        if not mount_point.startswith("/mnt/media_rw/"):
            continue
        volume_id = mount_point.rsplit("/", 1)[-1].strip()
        if not volume_id or volume_id.lower() in ("emulated", "self"):
            continue
        if volume_id not in volume_ids:
            volume_ids.append(volume_id)

    for volume_id in volume_ids:
        storage_path = f"/storage/{volume_id}"
        ls_out = adb_shell_output(serial, f"ls {storage_path}/ 2>/dev/null", timeout=8)
        if ls_out and "No such file" not in ls_out and "Permission denied" not in ls_out:
            return storage_path

    return None


def sdcard_push_media_file(serial, local_path, remote_dir, remote_filename):
    """Push a media file to external storage and notify MediaStore.

    Returns the full remote file path.
    """
    if not os.path.isfile(local_path):
        raise AssertionError(f"Local media file not found: {local_path}")

    remote_path = f"{remote_dir.rstrip('/')}/{remote_filename}"
    adb_shell(serial, f"mkdir -p {remote_dir}", timeout=10)

    print(f"[sdcard] Pushing media to {remote_path} ...", flush=True)
    ret = adb_command(serial, "push", local_path, remote_path, timeout=120)
    if ret.returncode != 0:
        raise AssertionError(
            f"adb push failed (rc={ret.returncode}): "
            f"{(ret.stderr or ret.stdout or '').strip()[:200]}"
        )

    adb_shell(
        serial,
        f"am broadcast -a android.intent.action.MEDIA_SCANNER_SCAN_FILE "
        f"-d file://{remote_path}",
        timeout=10,
    )
    time.sleep(2)
    print(f"[sdcard] [OK] Media pushed: {remote_path}", flush=True)
    return remote_path


def media_start_video(serial, video_path):
    """Start an MP4 with Google Photos, falling back to an implicit view intent."""
    command = (
        "am", "start",
        "-a", "android.intent.action.VIEW",
        "-d", f"file://{video_path}",
        "-t", "video/mp4",
        "--grant-read-uri-permission",
    )
    ret = adb_command(
        serial,
        "shell",
        *command,
        "-n", "com.google.android.apps.photos/.pager.HostPhotoPagerActivity",
        timeout=15,
    )
    if ret.returncode != 0:
        ret = adb_command(serial, "shell", *command, timeout=15)
    return ret


def media_is_player_active(serial):
    """Return whether a media-player app is foregrounded or playing."""
    window_out = adb_shell_output(
        serial,
        "dumpsys window | grep -E 'mCurrentFocus|mFocusedApp'",
        timeout=12,
    )
    media_indicators = ["photos", "gallery", "video", "media", "player", "vlc", "mx"]
    if any(keyword in window_out.lower() for keyword in media_indicators):
        return True

    media_session = adb_shell_output(serial, "dumpsys media_session", timeout=12).lower()
    return "state=playing" in media_session or "state=3" in media_session


def media_delete_via_photos_app(device, serial, media_path):
    """Delete media through Photos, with an ADB removal fallback."""
    media_start_video(serial, media_path)
    time.sleep(3)

    for selector in [
        lambda: device(description="More options"),
        lambda: device(descriptionContains="More"),
        lambda: device(description="Options"),
    ]:
        try:
            button = selector()
            if button.exists(timeout=1.5):
                button.click()
                time.sleep(1)
                break
        except Exception:
            pass

    deleted_via_ui = False
    for selector in [
        lambda: device(text="Delete"),
        lambda: device(text="Move to Trash"),
        lambda: device(text="Move to trash"),
        lambda: device(descriptionContains="Delete"),
        lambda: device(descriptionContains="trash"),
        lambda: device(description="Delete"),
    ]:
        try:
            button = selector()
            if button.exists(timeout=2):
                button.click()
                time.sleep(1.5)
                deleted_via_ui = True
                break
        except Exception:
            pass

    for selector in [
        lambda: device(text="Delete"),
        lambda: device(text="OK"),
        lambda: device(text="Move to trash"),
        lambda: device(textContains="Confirm"),
    ]:
        try:
            button = selector()
            if button.exists(timeout=2):
                button.click()
                time.sleep(2)
                break
        except Exception:
            pass

    if not device_file_exists(serial, media_path):
        return True

    if not deleted_via_ui:
        print("[sdcard] UI delete not available; falling back to ADB rm", flush=True)

    adb_shell(serial, f"rm -f {media_path}", timeout=10)
    media_dir = media_path.rsplit("/", 1)[0]
    adb_shell(
        serial,
        f"am broadcast -a android.intent.action.MEDIA_MOUNTED -d file://{media_dir}",
        timeout=8,
    )
    time.sleep(1)
    return not device_file_exists(serial, media_path)


def run_adb_cmd(dev, cmd, log_print=True):
    """Compatibility helper for legacy callers that pass full adb command segments."""
    try:
        command = f'"{ADB_BIN}" -s {dev} {cmd}'
        return subprocess.check_output(
            command,
            stderr=subprocess.STDOUT,
            shell=True,
        )
    except Exception:
        return 'error'


#EnableDisable_UPC_E1_Method_Alice_2026-8-7
def dcs_test_wait_device_online(serial, timeout_seconds=30):
    """Wait for a configured UPC-E1 test device to report the device state."""
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        try:
            state = subprocess.run(
                [ADB_BIN, "-s", serial, "get-state"],
                capture_output=True,
                text=True,
                errors="ignore",
                check=False,
                timeout=8,
            ).stdout.strip()
        except (subprocess.SubprocessError, OSError):
            state = ""
        if state == "device":
            return True
        time.sleep(1)
    return False


#EnableDisable_UPC_E1_Method_Alice_2026-8-7
def dcs_test_wake_and_unlock(serial, device):
    """Wake and unlock a UPC-E1 test device."""
    try:
        device.screen_on()
    except Exception:
        pass
    adb_shell(serial, "input", "keyevent", "224", timeout=6)
    time.sleep(0.4)
    adb_shell(serial, "input", "keyevent", "82", timeout=6)
    time.sleep(0.6)


#EnableDisable_UPC_E1_Method_Alice_2026-8-7
def dcs_test_press_home(serial):
    """Return a UPC-E1 test device to the home screen."""
    adb_shell(serial, "input", "keyevent", "3", timeout=6)
    time.sleep(1)


#EnableDisable_UPC_E1_Method_Alice_2026-8-7
def dcs_test_open_honeywell_settings(serial):
    """Launch Honeywell Settings with a clean activity task."""
    adb_shell(serial, "am", "force-stop", "com.honeywell.settings", timeout=8)
    time.sleep(0.5)
    adb_shell(
        serial,
        "am",
        "start",
        "--activity-clear-task",
        "-n",
        "com.honeywell.settings/.MainActivity",
        timeout=10,
    )
    return True


#EnableDisable_UPC_E1_Method_Alice_2026-8-7
def dcs_test_trigger_honeywell_scan(serial):
    """Trigger and release the Honeywell scanner for the UPC-E1 case."""
    down_ok = scan_send_scan_button_broadcast(serial, 1)
    time.sleep(0.8)
    up_ok = scan_send_scan_button_broadcast(serial, 0)
    return bool(down_ok and up_ok)


#EnableDisable_UPC_E1_Method_Alice_2026-8-7
def dcs_test_prepare_image_on_display_device(serial, device, local_image_path, remote_image_path):
    """Push and display the UPC-E1 reference image on the display device."""
    from common.common_method import dcs_test_handle_image_viewer_chooser

    if not os.path.exists(local_image_path):
        raise AssertionError(f"Image file not found: {local_image_path}")

    remote_directory, remote_filename = os.path.split(remote_image_path)
    remote_stem, remote_extension = os.path.splitext(remote_filename)
    display_remote_path = os.path.join(
        remote_directory or "/sdcard/Pictures",
        f"{remote_stem}_{time.time_ns()}{remote_extension or '.jpg'}",
    ).replace("\\", "/")
    display_image_uri = f"file://{quote(display_remote_path, safe='/:')}"

    adb_shell(serial, "svc", "power", "stayon", "true", timeout=8)
    dcs_test_wake_and_unlock(serial, device)
    dcs_test_press_home(serial)

    try:
        push_out = subprocess.run(
            [ADB_BIN, "-s", serial, "push", local_image_path, display_remote_path],
            capture_output=True,
            text=True,
            errors="ignore",
            check=False,
            timeout=30,
        )
    except (subprocess.SubprocessError, OSError) as error:
        raise AssertionError(f"Failed to push image to dev1: {local_image_path}") from error
    if push_out.returncode != 0:
        raise AssertionError(f"Failed to push image to dev1: {local_image_path}")

    adb_shell(
        serial,
        "am",
        "broadcast",
        "-a",
        "android.intent.action.MEDIA_SCANNER_SCAN_FILE",
        "-d",
        display_image_uri,
        timeout=10,
    )
    adb_shell(serial, "am", "force-stop", "com.google.android.apps.photos", timeout=10)
    start_out = adb_shell(
        serial,
        "am",
        "start",
        "-a",
        "android.intent.action.VIEW",
        "-d",
        display_image_uri,
        "-t",
        "image/jpeg",
        timeout=10,
    )
    if start_out.returncode != 0:
        raise AssertionError(
            f"Failed to display reference image: {display_remote_path}; {start_out.stderr.strip()}"
        )
    print(f"[display] Opened reference image: {display_remote_path}")
    time.sleep(2)
    dcs_test_handle_image_viewer_chooser(device)
    adb_shell(serial, "cmd", "statusbar", "collapse", timeout=8)
    time.sleep(0.5)
    try:
        current_package = (device.app_current().get("package") or "").lower()
    except Exception:
        current_package = ""
    if current_package.startswith("com.android.launcher"):
        retry_out = adb_shell(
            serial,
            "am",
            "start",
            "-a",
            "android.intent.action.VIEW",
            "-d",
            display_image_uri,
            "-t",
            "image/jpeg",
            timeout=10,
        )
        if retry_out.returncode != 0:
            raise AssertionError(
                f"Failed to redisplay reference image: {display_remote_path}; {retry_out.stderr.strip()}"
            )
        print(f"[display] Retried reference image: {display_remote_path}")
        time.sleep(1)


#EnableDisable_UPC_E1_Method_Alice_2026-8-7
def dcs_test_cleanup_devices(scanner_serial, display_serial):
    """Restore UPC-E1 test devices after a test run."""
    try:
        from common.common_method import dcs_test_connect_u2, dcs_test_scroll_find_and_click

        device = dcs_test_connect_u2(scanner_serial)
        if not dcs_test_open_honeywell_settings(scanner_serial):
            raise RuntimeError("Cannot open Honeywell Settings")

        navigation = [
            (["Scanning"], "Scanning"),
            (["Internal Scanner", "Internal scanner"], "Internal Scanner"),
            (["Default profile", "Default Profile"], "Default profile"),
            (["Symbology Settings", "Symbology"], "Symbology Settings"),
        ]
        for labels, description in navigation:
            if not dcs_test_scroll_find_and_click(device, labels):
                raise RuntimeError(f"Cannot find '{description}'")

        more_options = device(descriptionMatches=r"(?i).*more options.*")
        if not more_options.exists(timeout=1):
            more_options = device(resourceIdMatches=r".*:id/action_more")
        if not more_options.exists(timeout=1):
            raise RuntimeError("Cannot find Symbology Settings more-options menu")
        more_options.click()

        restore_defaults = device(text="Restore all defaults")
        if not restore_defaults.exists(timeout=1):
            restore_defaults = device(textContains="Restore all defaults")
        if not restore_defaults.exists(timeout=1):
            raise RuntimeError("Cannot find 'Restore all defaults'")
        restore_defaults.click()
        time.sleep(1)
        print("[cleanup] Restored Symbology Settings defaults")
    except Exception as error:
        print(f"[cleanup] Failed to restore Symbology Settings defaults: {error}")
    finally:
        adb_shell(scanner_serial, "am", "force-stop", "com.honeywell.settings", timeout=8)
        # adb_shell(display_serial, "svc", "power", "stayon", "false", timeout=8)


def get_connected_devices():
    """
    Return a list of all device serials currently connected via ADB.
    :return: ['emulator-5554', '192.168.1.100:5555', ...]
    """
    try:
        output = subprocess.check_output(f'"{ADB_BIN}" devices', shell=True).decode('utf-8', errors='ignore')
        devices = []
        for line in output.splitlines()[1:]:
            line = line.strip()
            if line and '\tdevice' in line:
                serial = line.split('\t')[0].strip()
                devices.append(serial)
        return devices
    except Exception as e:
        print('[ADB] Failed to get device list: {}'.format(e))
        return []


def save_step_screenshot(device, step_name, img_dir=None):
    """
    Capture and save a device screenshot under the img directory.

    :param device:    uiautomator2 device object
    :param step_name: step label for file naming, e.g. 'step01_screen_on'
    :param img_dir:   screenshot directory, defaults to auto_test/img/
    :return:          absolute path to the saved screenshot
    """
    save_dir = img_dir if img_dir else _IMG_DIR
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


# sophy_get_current_api_level_2026-06-10
def get_current_api_level(serial):
    import os

    cmd = f'adb -s {serial} shell "getprop ro.build.version.sdk"'

    result = os.popen(cmd).read().strip()

    if not result.isdigit():
        return "error"

    return int(result)


# sophy_get security patch level_2026-06-10
def get_security_patch_level(serial):
    import os

    cmd = r'adb -s {} shell "getprop ro.build.version.security_patch"'.format(serial)

    result = os.popen(cmd).read().strip()
    print(result)

    if not result:
        return "error"
    return result


# sophy_get_first_api_level_2026-06-10
def get_first_api_level(serial):
    """
    Get first API level of the device.
    :param serial: device id
    :return: first API level (string) or 'error' if failed
    """
    import os

    cmd = r'adb -s {} shell "getprop ro.product.first_api_level"'.format(serial)

    result = os.popen(cmd).read().strip()
    print(result)

    if not result:
        return "error"
    return result


# sophy_get_android_sdk_version_2026-06-10
def get_android_sdk_version(serial):
    """
    Get current Android SDK version (API level).
    :param serial: device id
    :return: SDK version (string) or 'error' if failed
    """
    import os

    cmd = r'adb -s {} shell "getprop ro.build.version.sdk"'.format(serial)

    result = os.popen(cmd).read().strip()
    print(result)

    if not result:
        return "error"
    return result

# sophy_get_system_date_2026-06-18
def get_system_date(serial):
    """
    Get current system date from device.
    :param serial: device serial
    :return: date string in format "YYYY-MM-DD" or None if failed
    """
    import os

    cmd = r'adb -s {} shell "date +%Y-%m-%d"'.format(serial)
    result = os.popen(cmd).read().strip()

    if not result or len(result) != 10:
        return None
    return result

# sophy_get_imei_information_2026-06-11
def get_imei(serial):
    """
    Get device IMEI (International Mobile Equipment Identity).
    Tries multiple methods to retrieve IMEI from device.
    :param serial: device id
    :return: IMEI string (15 digits) or 'error' if failed
    """
    import os

    # Method 1: Try service call iphonesubinfo
    # This works on most Android devices
    cmd1 = r'C:\ADB\adb.exe -s {} shell "service call iphonesubinfo 1"'.format(serial)
    result = os.popen(cmd1).read().strip()

    if result and "Result: Parcel" in result:
        # Parse the IMEI from service call output
        # The output format is like: Result: Parcel(xxxx '1' '5' '3' '4' ...)
        imei_digits = []
        lines = result.split('\n')
        for line in lines:
            # Extract single quoted characters which are the IMEI digits
            parts = line.split("'")
            for i in range(1, len(parts), 2):
                char = parts[i].strip()
                if char and char != '.' and len(char) == 1:
                    if char.isdigit():
                        imei_digits.append(char)

        imei = ''.join(imei_digits)
        if len(imei) >= 14:  # Valid IMEI is typically 15 digits
            print(f"IMEI retrieved via service call: {imei[:15]}")
            return imei[:15]

    # Method 2: Try getprop for various IMEI properties
    imei_props = [
        'ril.IMEI',
        'persist.radio.imei',
        'ro.ril.oem.imei',
        'gsm.device.imei',
        'persist.sys.imei'
    ]

    for prop in imei_props:
        cmd = r'C:\ADB\adb.exe -s {} shell "getprop {}"'.format(serial, prop)
        result = os.popen(cmd).read().strip()

        if result and len(result) >= 14:
            # Filter to get only digits
            imei = ''.join(filter(str.isdigit, result))
            if len(imei) >= 14:
                print(f"IMEI retrieved via getprop {prop}: {imei[:15]}")
                return imei[:15]

    # Method 3: Try dumpsys iphonesubinfo
    cmd3 = r'C:\ADB\adb.exe -s {} shell "dumpsys iphonesubinfo"'.format(serial)
    result = os.popen(cmd3).read().strip()

    if result:
        # Look for IMEI in dumpsys output
        for line in result.split('\n'):
            if 'Device ID' in line or 'IMEI' in line:
                # Extract digits from the line
                imei = ''.join(filter(str.isdigit, line))
                if len(imei) >= 14:
                    print(f"IMEI retrieved via dumpsys: {imei[:15]}")
                    return imei[:15]

    print("Failed to retrieve IMEI from device")
    return "error"


# sophy_press_back_key_2026-06-12
def press_back_key(serial):
    """
    Press the Back key
    :param serial: device id
    """
    cmd = "shell input keyevent KEYCODE_BACK"
    run_adb_cmd(serial, cmd, log_print=False)
    time.sleep(0.5)


# Keyremap_Method_2026-08-27
def keyremap_swipe_up(serial):
    """Swipe up one page via ADB.

    Args: serial is the target device serial number.
    Returns: None. Waits for the page scroll to finish before returning.
    Precondition: swipe coordinates are scaled from the 1080x2160 baseline to the device's actual resolution.
    """
    size_output = run_adb_cmd(serial, "shell wm size", log_print=False)
    size_text = size_output.decode("utf-8", errors="ignore") if isinstance(size_output, bytes) else str(size_output)
    sizes = re.findall(r"(?:Override|Physical) size:\s*(\d+)x(\d+)", size_text)
    if sizes:
        screen_width, screen_height = (int(value) for value in sizes[-1])
        swipe_x = round(screen_width * 540 / 1080)
        swipe_y_start = round(screen_height * 1400 / 2160)
        swipe_y_end = round(screen_height * 400 / 2160)
    else:
        swipe_x, swipe_y_start, swipe_y_end = 540, 1400, 400
    run_adb_cmd(serial, f"shell input swipe {swipe_x} {swipe_y_start} {swipe_x} {swipe_y_end} 600", log_print=False)
    time.sleep(1.5)


# Keyremap_Method_2026-08-27
def keyremap_click_virtual_back(serial):
    """Tap the leftmost virtual Back icon inside the Keyremap key-capture dialog.

    Args: serial is the target device serial number.
    Returns: None. Waits for the dialog to update after tapping.
    Precondition: the "Please press the key to be mapped" dialog is open.
    """
    size_output = run_adb_cmd(serial, "shell wm size", log_print=False)
    size_text = size_output.decode("utf-8", errors="ignore") if isinstance(size_output, bytes) else str(size_output)
    sizes = re.findall(r"(?:Override|Physical) size:\s*(\d+)x(\d+)", size_text)
    if sizes:
        screen_width, screen_height = (int(value) for value in sizes[-1])
        tap_x = round(screen_width * 252 / 1080)
        tap_y = round(screen_height * 1203 / 2160)
    else:
        tap_x, tap_y = 252, 1203
    run_adb_cmd(serial, f"shell input tap {tap_x} {tap_y}", log_print=False)
    time.sleep(1)


# Keyremap_Method_2026-08-27
def keyremap_get_home_package(serial):
    """Get the package name of the device's default HOME activity.

    Args: serial is the target device serial number.
    Returns: the package name on success, or an empty string if it cannot be parsed.
    Precondition: the device supports the Android `cmd package resolve-activity` command.
    """
    output = run_adb_cmd(
        serial,
        "shell cmd package resolve-activity -c android.intent.category.HOME",
        log_print=False,
    )
    output_text = output.decode("utf-8", errors="ignore") if isinstance(output, bytes) else str(output)
    match = re.search(r"packageName=([\w.]+)", output_text)
    return match.group(1) if match else ""


# Keyremap_Method_2026-08-27
def keyremap_is_on_home_screen(serial, timeout=8):
    """Poll window and activity state to determine whether the device has reached the default launcher.

    Args: serial is the target device serial number; timeout is the max polling duration in seconds.
    Returns: (is_on_home, most recent focused window info).
    Precondition: the launcher may report mCurrentFocus=null on some devices, so window, resumed activity,
          and the default HOME package are all checked together.
    """
    home_package = keyremap_get_home_package(serial)
    deadline = time.time() + timeout
    last_focus = ""

    # The single focused window can be empty on the Launcher, so combine multiple dumpsys signals for stability.
    while time.time() < deadline:
        signals = []

        window_output = run_adb_cmd(serial, "shell dumpsys window", log_print=False)
        window_text = (
            window_output.decode("utf-8", errors="ignore")
            if isinstance(window_output, bytes)
            else str(window_output)
        )
        for line in window_text.splitlines():
            if "mCurrentFocus" in line or "mFocusedApp" in line:
                signals.append(line.strip())
                if "mCurrentFocus" in line:
                    last_focus = line.strip()

        activity_output = run_adb_cmd(serial, "shell dumpsys activity activities", log_print=False)
        activity_text = (
            activity_output.decode("utf-8", errors="ignore")
            if isinstance(activity_output, bytes)
            else str(activity_output)
        )
        for line in activity_text.splitlines():
            if "mResumedActivity" in line or "topResumedActivity" in line:
                signals.append(line.strip())

        state_text = " ".join(signals).lower()
        focus = last_focus or (signals[0] if signals else "")
        if "launcher" in state_text or "home" in state_text:
            return True, focus
        if home_package and home_package.lower() in state_text:
            return True, focus
        time.sleep(1)

    return False, last_focus

# sophy_press_recent_key_2026-06-12
def press_recent_key(serial):
    """
    Press the Recent Apps/App Switch key
    :param serial: device id
    """
    cmd = "shell input keyevent KEYCODE_APP_SWITCH"
    run_adb_cmd(serial, cmd, log_print=False)
    time.sleep(0.5)


# sophy_press_home_key_2026-06-12
def press_home_key(serial):
    """
    Press the Home key
    :param serial: device id
    """
    cmd = "shell input keyevent KEYCODE_HOME"
    run_adb_cmd(serial, cmd, log_print=False)
    time.sleep(0.5)


# sophy_press_power_key_2026-06-12
def press_power_key(serial):
    """
    Press the Power key (short press - toggles screen on/off)
    :param serial: device id
    """
    cmd = "shell input keyevent KEYCODE_POWER"
    run_adb_cmd(serial, cmd, log_print=False)
    time.sleep(0.5)


# sophy_is_screen_on_2026-06-12
def is_screen_on(serial):
    """
    Check if device screen is on
    :param serial: device id
    :return: True if screen is on, False if off
    """
    power_out = adb_shell_output(serial, "dumpsys power", timeout=8)

    if 'mScreenOn=true' in power_out or 'mInteractive=true' in power_out:
        return True
    if 'mScreenOn=false' in power_out or 'mInteractive=false' in power_out:
        return False

    display_out = adb_shell_output(serial, "dumpsys display", timeout=8)
    if 'mScreenState' in display_out:
        return 'mScreenState=ON' in display_out or (
                    'mScreenState=OFF' not in display_out and 'ON' in display_out.upper())
    return 'ON' in display_out.upper()

# sophy_long_press_power_key_2026-06-12
def long_press_power_key(serial):
    """
    Long press the Power key to show power menu (reboot/power off options)
    :param serial: device id
    Note: This shows the power menu but does NOT actually reboot the device
    """
    cmd = "shell input keyevent --longpress KEYCODE_POWER"
    run_adb_cmd(serial, cmd, log_print=False)
    time.sleep(1)

# Detect the default camera activity on device via 'cmd package resolve-activity'-Alice
def detect_default_camera_activity(serial, preferred_packages=None):
    """
    Detect the default camera activity on device via 'cmd package resolve-activity'.

    Strategy (in order):
      1. cmd package resolve-activity --brief -a android.media.action.IMAGE_CAPTURE
      2. cmd package resolve-activity --brief  (no -a flag, some ROMs)
      3. dumpsys package activity-resolver cache (last-resort fallback)

    :param serial:              adb device serial string
    :param preferred_packages:  optional list of package names to prioritise
    :return:                    component string 'pkg/activity', or None if undetected
    """
    preferred_packages = preferred_packages or []

    def _shell(cmd_list):
        adb_cmd = ['adb', 'shell'] + cmd_list
        if serial:
            adb_cmd = ['adb', '-s', serial, 'shell'] + cmd_list
        proc = subprocess.run(
            adb_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            encoding='utf-8',
            errors='ignore',
        )
        return (proc.stdout or '').strip()

    def _parse_component(text):
        """Extract a package/Activity component from resolve-activity output."""
        fallback = None
        for line in text.splitlines():
            line = line.strip()
            if '/' not in line:
                continue
            # Handle lines like "  name=pkg/Activity" or bare "pkg/Activity"
            cand = line.split('=', 1)[-1].strip()
            if '/' not in cand:
                continue
            # Must look like a valid component (no spaces)
            if ' ' in cand:
                continue
            if not preferred_packages or any(cand.startswith(p + '/') for p in preferred_packages):
                return cand
            fallback = fallback or cand
        return fallback

    # --- Attempt 1: standard resolve-activity with action ---
    out = _shell(['cmd', 'package', 'resolve-activity', '--brief',
                  '-a', 'android.media.action.IMAGE_CAPTURE'])
    comp = _parse_component(out)
    if comp:
        return comp

    # --- Attempt 2: resolve without -a (some AOSP variants) ---
    out = _shell(['cmd', 'package', 'resolve-activity', '--brief',
                  'android.media.action.IMAGE_CAPTURE'])
    comp = _parse_component(out)
    if comp:
        return comp

    # --- Attempt 3: query via pm resolve-activity (older API) ---
    out = _shell(['pm', 'resolve-activity', '-a', 'android.media.action.IMAGE_CAPTURE'])
    comp = _parse_component(out)
    if comp:
        return comp


# ============= Camera_Method_Sally: Camera ADB Helpers =============
# Camera_Method_Sally
def camera_photo_count(serial, verbose=True):
    """
    统计常见相册目录中的照片数量。

    :param serial:  设备 serial
    :param verbose: 是否输出详细日志
    :return:        照片总数
    """
    paths = [
        "/sdcard/DCIM/Camera",
        "/storage/emulated/0/DCIM/Camera",
        "/sdcard/Pictures/Camera",
        "/storage/emulated/0/Pictures/Camera",
        "/sdcard/DCIM",
        "/storage/emulated/0/DCIM",
    ]
    total = 0
    for p in paths:
        ret = adb_shell(serial, "ls", "-1", p, timeout=15)
        if ret.returncode == 0 and ret.stdout:
            lines = [x.strip() for x in (ret.stdout or "").splitlines() if x.strip()]
            # 只统计常见图片文件，避免目录数量影响判断
            photos = [x for x in lines if x.lower().endswith((".jpg", ".jpeg", ".png", ".heic", ".webp", ".bmp"))]
            if photos:
                if verbose:
                    print(f"[camera] Found {len(photos)} photos in {p}: {photos[:3]}...", flush=True)
                total += len(photos)
        elif verbose and ret.returncode != 0:
            print(f"[camera] Cannot access {p}: {ret.stderr if ret.stderr else 'Permission denied'}", flush=True)

    if verbose:
        print(f"[camera] Total photos found: {total}", flush=True)
    return total


def save_debug_screenshot(serial, name, img_dir=None):
    """
    通过 adb 截图，避免 uiautomator 截图偶发卡住。

    :param serial:  设备 serial
    :param name:    截图名称前缀
    :param img_dir: 截图保存目录，默认为 auto_test/img/
    :return:        截图保存的完整路径
    """
    save_dir = img_dir if img_dir else _IMG_DIR
    os.makedirs(save_dir, exist_ok=True)
    path = os.path.join(save_dir, f"{name}_{time.strftime('%Y%m%d_%H%M%S')}.png")
    try:
        with open(path, "wb") as f:
            subprocess.run(
                ["adb", "-s", serial, "exec-out", "screencap", "-p"],
                stdout=f,
                stderr=subprocess.DEVNULL,
                check=False,
                timeout=10,
            )
    except Exception:
        pass
    return path


def get_screen_resolution(serial):
    """
    获取设备屏幕分辨率。

    :param serial: 设备 serial
    :return:       (width, height) 元组，失败返回 (1080, 2280)
    """
    ret = adb_shell(serial, "wm", "size")
    width, height = 1080, 2280
    if ret.returncode == 0 and ret.stdout:
        raw = ret.stdout.strip().split(":")[-1].strip()
        if "x" in raw:
            try:
                width = int(raw.split("x")[0])
                height = int(raw.split("x")[1])
            except Exception:
                pass
    return width, height


# Camera_Method_Sally
def delete_camera_photos(serial):
    """
    删除设备上的所有相机照片（从常见目录）。

    :param serial: 设备 serial
    :return:       删除的照片总数
    """
    paths = [
        "/sdcard/DCIM/Camera",
        "/storage/emulated/0/DCIM/Camera",
        "/sdcard/Pictures/Camera",
        "/storage/emulated/0/Pictures/Camera",
    ]
    total_deleted = 0
    for p in paths:
        ret = adb_shell(serial, "find", p, "-type", "f", "-delete")
        if ret.returncode == 0:
            # 验证删除
            ret_verify = adb_shell(serial, "ls", "-1", p)
            if ret_verify.returncode != 0:
                # 目录不存在或为空，说明删除成功
                total_deleted += 1
    return total_deleted


# Camera_Method_Sally
def verify_camera_app(serial, verbose=True):
    """
    验证相机应用是否正常运行且有必要权限。

    :param serial:  设备 serial
    :param verbose: 是否输出日志
    :return:        (app_name, is_running, has_permissions) 元组
    """
    camera_apps = {
        "com.android.camera": "System Camera",
        "com.google.android.GoogleCamera": "Google Camera",
        "com.sonyericsson.android.camera": "Sony Camera",
        "com.samsung.android.gallery3d": "Samsung Gallery",
    }

    for app_package, app_name in camera_apps.items():
        # 检查应用是否在运行
        ret = adb_shell(serial, "pidof", app_package, timeout=5)
        if ret.returncode == 0 and ret.stdout.strip():
            if verbose:
                print(f"[camera] {app_name} ({app_package}) is running", flush=True)

            # 检查权限
            ret_perms = adb_shell(serial, "dumpsys", "package", app_package, timeout=10)
            has_perms = "android.permission.CAMERA" in (ret_perms.stdout or "")
            if verbose:
                perm_status = "✓ has" if has_perms else "✗ missing"
                print(f"[camera] Camera permission: {perm_status}", flush=True)

            return app_name, True, has_perms

    if verbose:
        print(f"[camera] ✗ No known camera app is running", flush=True)
    return None, False, False


# Camera_Method_Sally
def grant_camera_permissions(serial, app_package="com.android.camera", verbose=True):
    """
    授予相机应用权限。

    :param serial:      设备 serial
    :param app_package: 应用包名
    :param verbose:     是否输出日志
    :return:            是否授予成功
    """
    perms = [
        "android.permission.CAMERA",
        "android.permission.WRITE_EXTERNAL_STORAGE",
        "android.permission.READ_EXTERNAL_STORAGE",
    ]

    success = True
    for perm in perms:
        ret = adb_shell(serial, "pm", "grant", app_package, perm, timeout=5)
        if verbose:
            status = "✓" if ret.returncode == 0 else "✗"
            print(f"[camera] {status} Grant {perm.split('.')[-1]}", flush=True)
        if ret.returncode != 0:
            success = False

    return success


# Camera_Method_Sally
CAMERA_PACKAGES = [
    "org.codeaurora.snapcamera",
    "org.codeaurora.snapcam",
    "com.android.camera",
    "com.google.android.GoogleCamera",
    "com.sonyericsson.android.camera",
]


# Camera_Method_Sally
def camera_is_screen_on(serial):
    """基于 dumpsys 判断屏幕是否点亮。"""
    ret = adb_shell(serial, "dumpsys", "power", timeout=8)
    out = (ret.stdout or "").lower() if ret.returncode == 0 else ""
    return (
            "display power: state=on" in out
            or "display power: state = on" in out
            or "mwakefulness=awake" in out
    )


# Camera_Method_Sally_09-20
def camera_foreground_package(serial):
    """通过 adb 获取当前前台包名。"""
    model = adb_shell(serial, "getprop", "ro.product.model", timeout=4)
    is_ck67 = "ck67" in (model.stdout or "").lower()
    ret = adb_shell(serial, "dumpsys", "window", timeout=4) if is_ck67 else adb_shell(
        serial, "dumpsys", "window", "windows", timeout=4
    )
    out = (ret.stdout or "") if ret.returncode == 0 else ""
    if is_ck67:
        focused = re.search(
            r"(?:mCurrentFocus|mFocusedApp)[\s\S]*?\bu\d+\s+([a-zA-Z0-9_.]+)/",
            out,
        )
        if focused:
            return focused.group(1)
    m = re.search(r"\s([a-zA-Z0-9_\.]+)/", out)
    return m.group(1) if m else ""

# Camera_Method_Sally
def camera_is_camera_foreground(serial):
    """判断当前前台是否为相机应用。"""
    pkg = camera_foreground_package(serial)
    return any(x in pkg for x in CAMERA_PACKAGES)


class AdbCommand(object):
    def __init__(self):
        pass

    # open a specified page
    def open_settings(self, serial, settings_name):
        adb_shell(serial, "am", "start", "-n", f"com.android.settings/.{settings_name}")

    def goto_home_screen(self, serial):
        adb_shell(serial, "input", "keyevent", "3")

    # Function to push file
    # Usage: push(self.tc_details['dev0'], "../video/video.3gp", "/sdcard/Video" )
    def push(self, serial, from_path, to_path):
        ret = subprocess.run(
            ["adb", "-s", serial, "push", from_path, to_path],
            capture_output=True,
            text=True,
            errors="ignore",
            check=False,
            timeout=30,
        )
        return (ret.stdout or ret.stderr or "").strip()

    def take_screenshot(self, device, test_name, step='', img_dir=None):
        """Instance entry for screenshot capture; delegates to module-level take_screenshot."""
        return take_screenshot(device, test_name, step=step, img_dir=img_dir)

# Scan_Method_Sally_0624
def scan_shell_output(serial, *cmd_parts, timeout=8):
    """Execute adb shell command and return stdout text."""
    ret = adb_shell(serial, *cmd_parts, timeout=timeout)
    return (ret.stdout or "").strip()


# Scan_Method_Sally_0624
def scan_is_screen_on(serial):
    """Check whether screen is currently ON."""
    out = scan_shell_output(serial, "dumpsys", "power", timeout=8)
    return "Display Power: state=ON" in out or "mWakefulness=Awake" in out


# Scan_Method_Sally_0624
def scan_wait_power_state(serial, expect_on, timeout=1.2, interval=0.1):
    """Wait until display power reaches target state."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        if scan_is_screen_on(serial) == expect_on:
            return True
        time.sleep(interval)
    return scan_is_screen_on(serial) == expect_on


# Scan_Method_Sally_0624
def scan_is_lockscreen_showing(serial):
    """Check whether lockscreen/keyguard is still visible."""
    try:
        policy = scan_shell_output(serial, "dumpsys", "window", "policy", timeout=8)
        window_state = scan_shell_output(serial, "dumpsys", "window", timeout=8)
        combined = f"{policy}\n{window_state}"
        indicators = [
            "isStatusBarKeyguard=true",
            "mShowingLockscreen=true",
            "mKeyguardShowing=true",
            "showing=true",
        ]
        return any(flag in combined for flag in indicators)
    except Exception:
        return False


# Scan_Method_Sally_0624
def scan_move_cursor_to_end(serial):
    """Move EditText cursor to end via keyevent."""
    try:
        adb_shell(serial, "input", "keyevent", "279")
    except Exception:
        pass


# Scan_Method_Sally_0624
def scan_get_current_user_id(serial):
    """Get current Android user id, return None on failure."""
    commands = [
        ("am", "get-current-user"),
        ("cmd", "activity", "get-current-user"),
    ]
    for cmd in commands:
        try:
            out = scan_shell_output(serial, *cmd, timeout=5)
            for line in out.splitlines():
                token = line.strip()
                if token.isdigit():
                    return int(token)
                m = re.search(r"(\d+)", token)
                if m:
                    return int(m.group(1))
            token = out.strip()
            if token.isdigit():
                return int(token)
        except Exception:
            continue
    return None


# Scan_Method_Sally_0624
def scan_get_owner_user_id(serial):
    """Get Owner/Main/Admin user id, fallback to 0."""
    try:
        out = scan_shell_output(serial, "pm", "list", "users", timeout=8)
        for line in out.splitlines():
            lower = line.lower()
            if "owner" in lower or "main" in lower or "admin" in lower or "system" in lower:
                m = re.search(r"\{(\d+):", line)
                if m:
                    return int(m.group(1))
    except Exception:
        pass
    return 0


# Scan_Method_Sally_0624
def scan_get_guest_user_id(serial):
    """Get Guest user id from pm list users, return None if not found."""
    try:
        out = scan_shell_output(serial, "pm", "list", "users", timeout=8)
        for line in out.splitlines():
            lower = line.lower()
            if "guest" in lower or "访客" in lower:
                m = re.search(r"\{(\d+):", line)
                if m:
                    return int(m.group(1))
    except Exception:
        pass
    return None


# Scan_Method_Sally_0624
def scan_create_guest_user_id(serial):
    """Try creating a Guest user and return new user id."""
    candidates = [
        ("pm", "create-user", "--guest", "Guest"),
        ("cmd", "user", "create", "--guest", "Guest"),
    ]
    for cmd in candidates:
        try:
            out = scan_shell_output(serial, *cmd, timeout=15)
            m = re.search(r"id\s*=\s*(\d+)|created user id\s*(\d+)", out, flags=re.IGNORECASE)
            if m:
                for g in m.groups():
                    if g and g.isdigit():
                        return int(g)
        except Exception:
            continue
    return None


# Scan_Method_Sally_0624
def scan_switch_user_by_id(serial, user_id, max_wait_seconds=12):
    """Switch to target user and wait until it takes effect."""
    if user_id is None:
        return False
    try:
        adb_shell(serial, "am", "switch-user", str(user_id), timeout=10)
    except Exception:
        return False

    deadline = time.time() + max_wait_seconds
    while time.time() < deadline:
        current = scan_get_current_user_id(serial)
        if current == user_id:
            return True
        time.sleep(0.3)
    return False


# Scan_Method_Alice_1008
def scan_enable_u2_for_user(serial, user_id):
    """Enable the uiautomator2 accessibility service for another Android user (e.g. Guest), else its UI dump fails."""
    service = "com.github.uiautomator/com.github.uiautomator.AccessibilityService"
    uid = str(user_id)
    for pkg in ("com.github.uiautomator", "com.github.uiautomator.test"):
        adb_shell(serial, "pm", "install-existing", "--user", uid, pkg, timeout=15)
    adb_shell(serial, "settings", "--user", uid, "put", "secure", "enabled_accessibility_services", service, timeout=8)
    adb_shell(serial, "settings", "--user", uid, "put", "secure", "accessibility_enabled", "1", timeout=8)
    for pkg in ("com.github.uiautomator", "com.github.uiautomator.test"):
        adb_shell(serial, "am", "force-stop", pkg, timeout=8)
    time.sleep(1)


# Scan_Method_Sally_0624
def scan_send_scan_button_broadcast(serial, test_value, current_user_id=None):
    """Send Honeywell SCAN_BUTTON broadcast.

    Honeywell scanner HW service runs at system level (user 0), so the broadcast
    must reach user 0 regardless of which UI user is currently active.
    Strategy:
      1. Always send to user 0 (system) with --ez boolean extra.
      2. Also send to the current user when in Guest mode.
      3. Final fallback: broadcast without --user scope.
    """
    current_user = current_user_id
    if current_user is None:
        current_user = scan_get_current_user_id(serial)

    sent = False

    # Strategy 1: Send to user 0 (system) — where the HW service lives
    try:
        ret = adb_shell(
            serial,
            "am", "broadcast",
            "--user", "0",
            "-a", "com.honeywell.intent.action.SCAN_BUTTON",
            "--ez", "test", str(test_value),
            timeout=8,
        )
        print(f"[scan] broadcast --user 0 test={test_value}: rc={ret.returncode} out={ret.stdout.strip()}", flush=True)
        sent = True
    except Exception as e:
        print(f"[scan] [WARN] broadcast --user 0 failed: {e}", flush=True)

    # Strategy 2: Also send to current user when in Guest (belt-and-suspenders)
    if current_user is not None and current_user != 0:
        try:
            ret = adb_shell(
                serial,
                "am", "broadcast",
                "--user", str(current_user),
                "-a", "com.honeywell.intent.action.SCAN_BUTTON",
                "--ez", "test", str(test_value),
                timeout=8,
            )
            print(f"[scan] broadcast --user {current_user} test={test_value}: rc={ret.returncode} out={ret.stdout.strip()}", flush=True)
            sent = True
        except Exception as e:
            print(f"[scan] [WARN] broadcast --user {current_user} failed: {e}", flush=True)

    if sent:
        return True

    # Strategy 3: Final fallback — no --user scope
    try:
        ret = adb_shell(
            serial,
            "am", "broadcast",
            "-a", "com.honeywell.intent.action.SCAN_BUTTON",
            "--ez", "test", str(test_value),
            timeout=8,
        )
        print(f"[scan] broadcast (no user) test={test_value}: rc={ret.returncode} out={ret.stdout.strip()}", flush=True)
        return True
    except Exception as e:
        print(f"[scan] [ERROR] All broadcast strategies failed: {e}", flush=True)
        return False


# Scan_Method_Sally_0624
def scan_cancel_guest_reset_via_adb(serial, device=None):
    """Handle the reset guest session popup; the hierarchy comes from the caller's u2 device."""
    keep_texts = [
        "cancel",
        "not now",
        "keep",
        "don't reset",
        "取消",
        "稍后",
        "保留",
        "不重置",
        "否",
        "继续使用",
    ]
    prompt_texts = ["reset guest session", "reset session", "重置访客会话", "重置会话", "start over", "reset", "重置"]
    reset_texts = ["reset", "重置", "start over", "清除", "delete"]

    try:
        # 'adb shell uiautomator dump' kills the uiautomator2 accessibility service, and u2.connect() restarts it.
        if device is None:
            return False
        dump = device.dump_hierarchy()
        if not dump:
            return False

        dump_lower = dump.lower()
        has_prompt = any(k in dump_lower for k in [t.lower() for t in prompt_texts])
        if not has_prompt:
            return False

        for text in keep_texts:
            pattern = rf'text="[^"]*{re.escape(text)}[^"]*"[^>]*bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"'
            m = re.search(pattern, dump, flags=re.IGNORECASE)
            if m:
                x1, y1, x2, y2 = map(int, m.groups())
                cx = (x1 + x2) // 2
                cy = (y1 + y2) // 2
                adb_shell(serial, "input", "tap", str(cx), str(cy), timeout=5)
                time.sleep(0.1)
                return True

        button_pattern = r'class="android\.widget\.Button"[^>]*text="([^"]*)"[^>]*bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"'
        candidates = []
        for m in re.finditer(button_pattern, dump, flags=re.IGNORECASE):
            text = (m.group(1) or "").strip()
            x1, y1, x2, y2 = map(int, m.groups()[1:])
            lower = text.lower()
            if any(k in lower for k in [t.lower() for t in reset_texts]):
                continue
            if "重置" in text or "清除" in text:
                continue
            candidates.append((x1, y1, x2, y2))

        if candidates:
            candidates.sort(key=lambda x: x[0])
            x1, y1, x2, y2 = candidates[0]
            cx = (x1 + x2) // 2
            cy = (y1 + y2) // 2
            adb_shell(serial, "input", "tap", str(cx), str(cy), timeout=5)
            time.sleep(0.1)
            return True

        adb_shell(serial, "input", "keyevent", "4", timeout=5)
        time.sleep(0.1)
        return True
    except Exception:
        return False


# Scan_Method_Sally_0624
def scan_handle_guest_reset_prompt(serial, retries=4, interval=0.15, device=None):
    """Retry guest reset popup handling for better stability."""
    for _ in range(retries):
        if scan_cancel_guest_reset_via_adb(serial, device=device):
            return True
        time.sleep(interval)
    return False

# Reboot_Method_Sally_0625
def reboot_run_adb(serial, cmd_parts, timeout=15):
    """Run a non-shell adb command and return CompletedProcess."""
    return subprocess.run(
        ["adb", "-s", serial, *cmd_parts],
        capture_output=True,
        text=True,
        errors="ignore",
        check=False,
        timeout=timeout,
    )

# Reboot_Method_Sally_0625
def reboot_run_adb_shell(serial, shell_cmd, timeout=15):
    """Run an adb shell command given as a single string and return stripped stdout."""
    ret = reboot_run_adb(serial, ["shell", shell_cmd], timeout=timeout)
    return (ret.stdout or "").strip()

# Reboot_Method_Sally_0625
def reboot_get_foreground_pkg(serial):
    """Return the package name of the current foreground app."""
    out = reboot_run_adb_shell(serial, "dumpsys window | grep -E 'mCurrentFocus|mFocusedApp'", timeout=12)
    m = re.search(r"([a-zA-Z0-9_\.]+)/[a-zA-Z0-9_\.\$]+", out)
    return m.group(1) if m else ""

# Reboot_Method_Sally_0625
def reboot_capture_pre_state(serial):
    """Capture device state before test for later restoration."""
    state = {
        "screen_on": scan_is_screen_on(serial),
        "foreground_pkg": reboot_get_foreground_pkg(serial),
    }
    print(
        f"[reboot] Captured pre-state: screen_on={state['screen_on']}, "
        f"foreground_pkg={state['foreground_pkg'] or 'unknown'}",
        flush=True,
    )
    return state


# Reboot_Method_Sally_0625
def reboot_enable_usb_debugging(serial):
    """Enable USB debugging via adb settings commands."""
    print("[reboot] Enabling USB debugging...", flush=True)
    try:
        reboot_run_adb(serial, ["shell", "settings", "put", "global", "adb_enabled", "1"], timeout=10)
        reboot_run_adb(serial, ["shell", "settings", "put", "secure", "android_debugging_enabled", "1"], timeout=10)
        print("[reboot] [OK] USB debugging enabled via adb settings", flush=True)

        return True
    except Exception as e:
        print(f"[reboot] [WARN] adb settings failed: {str(e)[:120]}", flush=True)
        return False

# Reboot_Method_Sally_0625
def reboot_verify_usb_debugging_enabled(serial):
    """Verify USB debugging is enabled by reading the global setting."""
    try:
        val = reboot_run_adb_shell(serial, "settings get global adb_enabled", timeout=8).strip()
        print(f"[reboot] [DEBUG] adb_enabled setting: {val}", flush=True)
        if val == "1":
            print("[reboot] [OK] USB debugging verified as enabled", flush=True)
            return True
    except Exception as e:
        print(f"[reboot] [WARN] Verification check failed: {str(e)[:120]}", flush=True)
    return False


# Reboot_Method_Sally_0625
def reboot_wait_device_success(serial, old_boot_id, timeout_sec=240):
    """Wait for reboot to complete and verify via boot_id change + boot_completed=1."""
    deadline = time.time() + timeout_sec

    # Wait for old adb session to drop.
    disconnected = False
    while time.time() < deadline:
        out = reboot_run_adb_shell(serial, "echo ping", timeout=5)
        if "device offline" in out.lower() or out == "":
            disconnected = True
            break
        time.sleep(1)
    if not disconnected:
        print("[reboot] [WARN] Did not observe disconnect; continue waiting for reconnect", flush=True)

    # Wait for reconnect + boot completed.
    reboot_run_adb(serial, ["wait-for-device"], timeout=180)

    boot_ok = False
    new_boot_id = ""
    while time.time() < deadline:
        completed = reboot_run_adb_shell(serial, "getprop sys.boot_completed", timeout=8)
        new_boot_id = reboot_run_adb_shell(serial, "cat /proc/sys/kernel/random/boot_id", timeout=8)
        if completed.strip() == "1" and new_boot_id and new_boot_id != old_boot_id:
            boot_ok = True
            break
        time.sleep(2)

    print(
        f"[reboot] reboot check: boot_ok={boot_ok}, old_boot_id={old_boot_id}, new_boot_id={new_boot_id}",
        flush=True,
    )
    return boot_ok

# IPSM_Method_Sally_0625
def ipsm_get_prop(serial, prop):
    """Get Android device property via adb."""
    ret = adb_shell(serial, "getprop", prop, timeout=8)
    return (ret.stdout or "").strip()


# IPSM_Method_Sally_0625
def ipsm_normalize_usb_function(usb_cfg):
    """Normalize USB configuration string to recognized function name."""
    cfg = (usb_cfg or "").strip().lower()
    if not cfg:
        return ""
    if cfg == "adb":
        return "adb"
    if "mtp" in cfg:
        return "mtp"
    if "ptp" in cfg:
        return "ptp"
    if "rndis" in cfg:
        return "rndis"
    if "midi" in cfg:
        return "midi"
    if "none" in cfg:
        return "none"
    return cfg.split(",")[0]


# IPSM_Method_Sally_2026-09-20 CK67 compatibility
def ipsm_is_mtp_enabled(serial):
    """Check if USB is in MTP/File transfer mode via device properties."""
    props = [
        ipsm_get_prop(serial, "sys.usb.state").lower(),
        ipsm_get_prop(serial, "sys.usb.config").lower(),
        ipsm_get_prop(serial, "persist.sys.usb.config").lower(),
    ]
    if any("mtp" in p for p in props if p):
        return True

    model = adb_shell(serial, "getprop", "ro.product.model", timeout=4)
    if "ck67" not in (model.stdout or "").lower():
        return False

    # CK67 can keep the legacy sys.usb properties at "adb" while the USB
    # service has already switched the active transport to MTP.
    usb_dump = adb_shell(serial, "dumpsys", "usb", timeout=8)
    usb_text = (usb_dump.stdout or "").lower() if usb_dump.returncode == 0 else ""
    return bool(re.search(r"(?:current_functions|mcurrentfunctions)\s*[=:]\s*[^\n]*\bmtp\b", usb_text))

# IPSM_Method_Sally_0625
def ipsm_restore_usb_mode(serial, pre_usb_config):
    """Restore USB mode to previous configuration."""
    target = ipsm_normalize_usb_function(pre_usb_config)
    if not target:
        return
    try:
        adb_shell(serial, "svc", "usb", "setFunctions", target, timeout=12)
        time.sleep(1)
        now_state = ipsm_get_prop(serial, "sys.usb.state").lower()
        print(f"[ipsm] Restore USB mode target={target}, now_state={now_state}", flush=True)
    except Exception as e:
        print(f"[ipsm] [WARN] Failed to restore USB mode: {e}", flush=True)


# IPSM_Method_Sally_2026-09-11
def ipsm_enable_mtp_by_adb_fallback(serial):
    """Enable MTP mode via adb commands with multiple fallback strategies."""
    attempts = [
        ["svc", "usb", "setFunctions", "mtp,adb"],
        ["cmd", "usb", "set-functions", "mtp", "true"],
        ["svc", "usb", "setFunctions", "mtp"],
        ["cmd", "usb", "set-functions", "mtp"],
    ]

    for cmd in attempts:
        try:
            result = adb_shell(serial, *cmd, timeout=12)
            # Switching USB functions can briefly tear down ADB, especially when
            # the target function excludes adb. Poll after the disconnect instead
            # of treating the first failed property read as a permanent failure.
            deadline = time.time() + 8
            while time.time() < deadline:
                if ipsm_is_mtp_enabled(serial):
                    print(
                        f"[ipsm] [OK] MTP enabled by ADB fallback: {' '.join(cmd)} "
                        f"(returncode={getattr(result, 'returncode', None)})",
                        flush=True,
                    )
                    return True
                time.sleep(0.5)
        except Exception:
            pass

    raw_attempts = [
        "svc usb setFunctions mtp,adb",
        "cmd usb set-functions mtp true",
        "svc usb setFunctions mtp",
        "cmd usb set-functions mtp",
    ]
    for raw in raw_attempts:
        try:
            result = subprocess.run(
                ["adb", "-s", serial, "shell", raw],
                capture_output=True,
                text=True,
                timeout=12,
                check=False,
            )
            deadline = time.time() + 8
            while time.time() < deadline:
                if ipsm_is_mtp_enabled(serial):
                    print(
                        f"[ipsm] [OK] MTP enabled by raw ADB fallback: {raw} "
                        f"(returncode={result.returncode})",
                        flush=True,
                    )
                    return True
                time.sleep(0.5)
        except Exception:
            pass

    print("[ipsm] [WARN] ADB fallback could not enable MTP", flush=True)
    return False

# ============= EMMC_Method_Sally: EMMC Video & Storage Helpers (2026-07-01) =============

# EMMC_Method_Sally_2026-07-01
def emmc_list_internal_video_files(serial):
    """
    枚举 internal storage 下常见目录的视频文件。
    
    :param serial: 设备 serial
    :return: 按字典序排序的视频文件完整路径列表
    """
    VIDEO_DIRS = [
        "/sdcard/DCIM/Camera",
        "/storage/emulated/0/DCIM/Camera",
        "/sdcard/Movies",
        "/storage/emulated/0/Movies",
    ]
    VIDEO_EXTS = (".mp4", ".3gp", ".mkv", ".webm")
    
    files = []
    for d in VIDEO_DIRS:
        ret = adb_shell(serial, "ls", "-1", d, timeout=8)
        out = (ret.stdout or "").strip()
        if ret.returncode != 0:
            continue
        for name in out.splitlines():
            n = name.strip()
            if not n:
                continue
            if n.lower().endswith(VIDEO_EXTS):
                files.append(f"{d.rstrip('/')}/{n}")
    return sorted(set(files))


# EMMC_Method_Sally_2026-07-01
def emmc_latest_internal_video_file(serial):
    """
    从内部存储中获取最新的视频文件。
    
    :param serial: 设备 serial
    :return: 最新视频文件路径，或空字符串如果未找到
    """
    files = emmc_list_internal_video_files(serial)
    if not files:
        return ""
    return sorted(set(files))[-1]


# EMMC_Method_Sally_2026-07-01
def emmc_device_has_sd_card(serial):
    """
    通过外置卷挂载证据判断是否存在 SD 卡，避免 EMMC 机型误判。
    
    CT47/CT70 上 IPSM 卡常出现为固定 UUID（'IPSM' 的十六进制）。
    该卷属于设备内部业务分区，不应判定为外置 SD 卡。
    
    :param serial: 设备 serial
    :return: True 如果有外置 SD 卡，否则 False
    """
    ignore_uuid = {"4950-534D"}

    def _is_external_uuid(u):
        return bool(u) and u.upper() not in ignore_uuid

    ret = adb_shell(serial, "ls", "-1", "/storage", timeout=8)
    out_storage = (ret.stdout or "").strip()
    storage_items = [x.strip() for x in out_storage.splitlines() if x.strip()]

    # 证据 1：/storage 下出现 UUID 目录（如 0123-4567）或明确外置目录名。
    for it in storage_items:
        lower = it.lower()
        if lower in ("self", "emulated", "enc_emulated"):
            continue
        if re.match(r"^[0-9a-f]{4}-[0-9a-f]{4}$", lower):
            if not _is_external_uuid(it):
                print(f"[emmc] [DEBUG] ignore internal IPSM uuid in /storage: {it}", flush=True)
                continue
            print(f"[emmc] [DEBUG] external UUID mount found in /storage: {it}", flush=True)
            return True
        if any(k in lower for k in ["sdcard1", "extsd", "external_sd", "micro_sd"]):
            print(f"[emmc] [DEBUG] external-like mount name found in /storage: {it}", flush=True)
            return True

    # 证据 2：sm list-volumes all 中存在 public 类型且命中外置 UUID。
    # 注意：仅出现 mounted/public 不足以证明有外置 SD，避免内部卷误判。
    ret = adb_shell(serial, "sm", "list-volumes", "all", timeout=8)
    out_vols = (ret.stdout or "").strip()
    for line in out_vols.splitlines():
        l = line.strip().lower()
        if not l:
            continue
        if "public" not in l:
            continue
        if "emulated" in l:
            continue
        m = re.search(r"\b([0-9a-f]{4}-[0-9a-f]{4})\b", l)
        if m and not _is_external_uuid(m.group(1)):
            print(f"[emmc] [DEBUG] ignore internal IPSM public volume: {line.strip()}", flush=True)
            continue
        if m and _is_external_uuid(m.group(1)):
            print(f"[emmc] [DEBUG] external public volume found: {line.strip()}", flush=True)
            return True

    # 证据 3：mount 中出现明确外置卡目录。
    ret = adb_shell(serial, "mount", timeout=8)
    out_mount = (ret.stdout or "").strip()
    lower_mount = out_mount.lower()
    
    uuid_matches = re.findall(r"/storage/([0-9a-f]{4}-[0-9a-f]{4})", lower_mount)
    uuid_matches = [u.upper() for u in uuid_matches if _is_external_uuid(u)]
    if uuid_matches:
        print("[emmc] [DEBUG] /storage UUID path found in mount output", flush=True)
        return True

    media_rw_uuids = re.findall(r"/mnt/media_rw/([0-9a-f]{4}-[0-9a-f]{4})", lower_mount)
    media_rw_uuids = [u.upper() for u in media_rw_uuids if _is_external_uuid(u)]
    if media_rw_uuids:
        print("[emmc] [DEBUG] external media_rw UUID path found in mount output", flush=True)
        return True

    if "sdcard1" in lower_mount or "extsd" in lower_mount or "external_sd" in lower_mount or "micro_sd" in lower_mount:
        print("[emmc] [DEBUG] external storage marker found in mount output", flush=True)
        return True

    print(
        f"[emmc] [DEBUG] no external SD evidence; /storage={storage_items}, sm_volumes={(out_vols or '').strip()}",
        flush=True,
    )
    return False


# EMMC_Method_Sally_2026-07-01
def emmc_verify_video_deleted_on_device(serial, video_path):
    """
    验证视频文件是否已从设备中删除。
    
    :param serial: 设备 serial
    :param video_path: 视频文件的完整路径
    :return: True 如果文件已删除或不存在，否则 False
    """
    ret = adb_shell(serial, "ls", "-l", video_path, timeout=8)
    text = ((ret.stdout or "") + "\n" + (ret.stderr or "")).lower()
    if ret.returncode != 0:
        return True
    if "no such file" in text or "not found" in text:
        return True
    return False


# EMMC_Method_Sally_2026-07-01
def emmc_sleep_then_wake(serial):
    """
    熄屏再亮屏，确保可回到可操作状态。

    使用确定性的 SLEEP/WAKEUP 键值代替电源键（KEYCODE_POWER=26）切换，
    因为带息屏显示(Doze/AOD)的设备上电源键会进入 Dozing 状态，双击切换不可靠。

    :param serial: 设备 serial
    :return: True 如果屏幕已点亮（Awake），否则 False
    """
    # KEYCODE_SLEEP=223 always sleeps (never wakes); KEYCODE_WAKEUP=224 always wakes.
    adb_shell(serial, "input", "keyevent", "223", timeout=8)
    time.sleep(2)
    adb_shell(serial, "input", "keyevent", "224", timeout=8)
    time.sleep(1)

    # Verify the device is actually interactive again. mWakefulness=Awake is the
    # authoritative signal on modern Android; retry a few times to absorb the
    # transition from Dozing -> Awake.
    for _ in range(10):
        ret = adb_shell(serial, "dumpsys", "power", timeout=8)
        out = (getattr(ret, "stdout", "") or "")
        if "mWakefulness=Awake" in out:
            return True
        # Re-issue wake in case the first event was dropped during suspend.
        adb_shell(serial, "input", "keyevent", "224", timeout=8)
        time.sleep(1)

    return is_screen_on(serial)


# EMMC_Method_Sally_2026-07-01
def emmc_normalize_internal_relpath(video_path):
    """
    将设备内部路径转换为 MTP 内部存储相对路径。
    
    :param video_path: 设备端的视频文件完整路径
    :return: MTP 相对路径（使用反斜杠分隔），或空字符串如果路径不支持
    """
    p = video_path.strip()
    for prefix in ("/sdcard/", "/storage/emulated/0/"):
        if p.startswith(prefix):
            return p[len(prefix):].replace("/", "\\")
    return ""


# EMMC_Method_Sally_2026-07-01
def emmc_delete_video_from_pc(video_path):
    """
    Delete video file from device via ADB (直接在设备上删除，无需 MTP 对话框).
    通过 ADB 从设备删除视频文件，避免 Windows MTP 删除确认对话框问题。
    EMMC_Method_Sally_2026-07-01
    
    :param video_path: 设备内部存储的完整视频路径（如 /sdcard/DCIM/Camera/video.mp4 或 /storage/emulated/0/DCIM/Camera/video.mp4）
    :return: True 如果删除成功，否则 False
    """
    if not video_path or not isinstance(video_path, str):
        return False

    serial = get_device_serial()
    if not serial:
        print(f"[emmc] [ERROR] Cannot get device serial for delete", flush=True)
        return False

    # Path already in correct format, just normalize slashes
    norm_path = video_path.replace('\\', '/').strip()
    if not norm_path.startswith('/'):
        norm_path = '/' + norm_path

    try:
        # Execute delete command
        cmd = ['adb', '-s', serial, 'shell', 'rm', norm_path]
        subprocess.run(cmd, capture_output=True, text=True, timeout=30, check=False)
        
        # Verify deletion
        check_cmd = ['adb', '-s', serial, 'shell', 'test', '-e', norm_path]
        check = subprocess.run(check_cmd, capture_output=True, text=True, timeout=10, check=False)
        
        # test -e returns 0 if file exists, non-zero if not
        if check.returncode != 0:
            return True
        else:
            return False
    except Exception:
        return False
    
# ============= IPSM_Method_Sally_2026-07-06 =============
# IPSM_Method_Sally_2026-07-06
def ipsm_locate_file_on_device(serial, file_name):
    """
    在 IPSM 卡常见挂载点上查找文件一次，返回命中的完整路径，找不到返回空串。

    :param serial: 设备 serial
    :param file_name: 目标文件名
    :return: 命中的设备路径，或空串
    """
    if not serial or not file_name:
        return ""

    # IPSM 卡常见挂载路径下的直达候选。
    candidates = [
        f"/storage/4950-534D/files/{file_name}",
        f"/storage/4950-534D/{file_name}",
        f"/mnt/media_rw/4950-534D/files/{file_name}",
        f"/mnt/media_rw/4950-534D/{file_name}",
    ]

    # 兜底：读取 /storage 下真实 UUID 目录，补进候选，兼容非固定 UUID 机型
    # 及实际大小写（观察到设备上为小写 4950-534d，与固定候选的大写不一致）。
    ls_storage = adb_shell(serial, "ls", "-1", "/storage", timeout=8)
    for line in (ls_storage.stdout or "").splitlines():
        item = (line or "").strip()
        low = item.lower()
        if not item or low in ("self", "emulated", "enc_emulated"):
            continue
        if re.match(r"^[0-9a-f]{4}-[0-9a-f]{4}$", low):
            candidates.append(f"/storage/{item}/files/{file_name}")
            candidates.append(f"/storage/{item}/{file_name}")

    for path in candidates:
        check = adb_shell(serial, "test", "-e", path, timeout=8)
        if check.returncode == 0:
            return path
    return ""


# IPSM_Method_Sally_2026-07-06
def ipsm_wait_file_on_device(serial, file_name, timeout=30, interval=1.5):
    """
    轮询等待文件出现在 IPSM 卡上，直到超时。

    Windows Shell 的 CopyHere 复制到 MTP 设备是异步/即发即弃的，PC 侧确认
    (Explorer Items() 枚举) 有时会因驱动缓存或被卡住的对话框而落空，因此这里
    直接以设备文件系统为准进行轮询确认，而不是信任 PC 侧的复制返回结果。

    :param serial: 设备 serial
    :param file_name: 目标文件名
    :param timeout: 最长等待秒数
    :param interval: 轮询间隔秒数
    :return: 命中的设备路径，或空串（超时未找到）
    """
    deadline = time.time() + timeout
    while True:
        found = ipsm_locate_file_on_device(serial, file_name)
        if found:
            return found
        if time.time() >= deadline:
            return ""
        time.sleep(interval)


# IPSM_Method_Sally_2026-07-06
def ipsm_delete_file_on_device(serial, copied_path):
    """
    Delete a copied IPSM file from device side via ADB and verify deletion.
    通过 ADB 在设备侧删除 IPSM 文件，避免 Windows 删除确认弹框。

    IPSM 卡在设备上的固定 UUID 为 4950-534D（'IPSM' 的十六进制），
    因此直接在已知挂载点定位并删除，风格与 emmc_delete_video_from_pc 一致。

    :param serial: 设备 serial
    :param copied_path: 复制后的路径（可为主机显示路径或仅文件名）
    :return: True 如果删除成功，否则 False
    """
    file_name = os.path.basename((copied_path or "").replace("\\", "/").strip())
    if not serial or not file_name:
        return False

    try:
        # PC 端的复制 (Windows Shell 异步 CopyHere / MTP) 可能在本函数运行时
        # 还未真正落盘完成，因此轮询查找而不是只检查一次，避免误报删除失败。
        found_path = ipsm_wait_file_on_device(serial, file_name, timeout=15, interval=1.5)
        if not found_path:
            print(f"[ipsm] [WARN] no on-device match found for file: {file_name}", flush=True)
            return False

        # IPSM 卷经由 FUSE/媒体存储代理，删除后可能有短暂延迟才对 test -e 可见，
        # 因此重试校验，而不是只检查一次就判定失败。
        for attempt in range(6):
            adb_shell(serial, "rm", "-f", found_path, timeout=10)
            verify = adb_shell(serial, "test", "-e", found_path, timeout=8)
            if verify.returncode != 0:
                print(f"[ipsm] [OK] delete file success via adb: {found_path}", flush=True)
                return True
            time.sleep(1)

        print(f"[ipsm] [WARN] file still exists after delete: {found_path}", flush=True)
        return False
    except Exception as e:
        print(f"[ipsm] [ERROR] delete failed: {e}", flush=True)
        return False


# ============= WiFi_Method_Sally: WiFi ADB Command Helpers =============

# WIFI_Method_Sally_0709
def _wifi_shell_output(serial, *cmd_parts, timeout=10):
    """Execute adb shell and return stdout text."""
    ret = adb_shell(serial, *cmd_parts, timeout=timeout)
    return (ret.stdout or "").strip()


# WIFI_Method_Sally_0709
def _wifi_is_enabled(serial):
    """Check if WiFi is enabled."""
    out = _wifi_shell_output(serial, "settings", "get", "global", "wifi_on")
    return out.strip() == "1"


# WIFI_Method_Sally_0709
def _wifi_enable(serial):
    """Enable WiFi."""
    adb_shell(serial, "svc", "wifi", "enable")
    time.sleep(2)
    return _wifi_is_enabled(serial)


# WIFI_Method_Sally_0709
def _wifi_disable(serial):
    """Disable WiFi."""
    adb_shell(serial, "svc", "wifi", "disable")
    time.sleep(2)
    return not _wifi_is_enabled(serial)


# WIFI_Method_Sally_0709
def _wifi_get_active_ssid(serial):
    """Return the SSID of the CURRENT live WiFi connection (empty if none).

    Reads ONLY the live ``mWifiInfo`` summary line and requires the supplicant
    state to be COMPLETED. The connection-history log (``rec[...]``) in
    ``dumpsys wifi`` is deliberately ignored, because it contains stale entries
    (old SSIDs / L3ConnectedState) that otherwise cause false positives.
    """
    out = _wifi_shell_output(serial, "dumpsys", "wifi", timeout=20)
    for line in out.splitlines():
        if "mWifiInfo" not in line or "SSID:" not in line:
            continue
        sup = re.search(r'Supplicant state:\s*(\w+)', line)
        if not sup or sup.group(1).strip().upper() != "COMPLETED":
            continue
        m = re.search(r'SSID:\s*(.+?),\s*BSSID:', line)
        if not m:
            continue
        ssid = m.group(1).strip().strip('"')
        if ssid and "<" not in ssid and "unknown" not in ssid.lower():
            return ssid
    return ""


# WIFI_Method_Sally_0709
def _wifi_is_connected(serial, ssid):
    """Check whether the device is CURRENTLY connected to the specified SSID.

    Uses the live ``mWifiInfo`` state only (see ``_wifi_get_active_ssid``), so an
    SSID that appears merely in scan results, saved networks, or the historical
    connection log is NOT treated as connected. This fixes the false positive of
    reporting "connected to Test01" while actually disconnected.
    """
    ssid_norm = (ssid or "").strip().strip('"').lower()
    if not ssid_norm:
        return False

    active = _wifi_get_active_ssid(serial)
    if not active:
        print(f"[wifi] [DEBUG] No active WiFi connection (target '{ssid}')", flush=True)
        return False

    if active.strip().lower() == ssid_norm:
        return True

    print(
        f"[wifi] [DEBUG] Active connection is '{active}', not target '{ssid}'",
        flush=True,
    )
    return False


def _wifi_wait_until_connected(serial, ssid, timeout_sec=18, interval_sec=2):
    """Poll connection state until connected to target SSID or timeout."""
    loops = max(1, int(timeout_sec / interval_sec))
    for _ in range(loops):
        if _wifi_is_connected(serial, ssid):
            return True
        time.sleep(interval_sec)
    return False


# WIFI_Method_Sally_0709
def _wifi_ssid_in_scan(serial, ssid):
    """Check whether target SSID currently appears in scan results (cmd/wpa_cli)."""
    target = (ssid or "").strip().lower()
    if not target:
        return False

    scan_results = adb_shell(serial, "cmd", "wifi", "list-scan-results", timeout=10)
    if scan_results.returncode == 0 and target in (scan_results.stdout or "").lower():
        return True

    wpa_scan = adb_shell(serial, "wpa_cli", "scan_results", timeout=10)
    if wpa_scan.returncode == 0 and target in (wpa_scan.stdout or "").lower():
        return True

    return False


def _wifi_wait_ssid_in_scan(serial, ssid, attempts=4, interval_sec=3):
    """Rescan and wait until target SSID shows up in scan results."""
    for i in range(1, attempts + 1):
        adb_shell(serial, "cmd", "wifi", "start-scan", timeout=12)
        time.sleep(interval_sec)
        if _wifi_ssid_in_scan(serial, ssid):
            print(f"[wifi] [OK] SSID '{ssid}' found in scan (attempt {i}/{attempts})", flush=True)
            return True
        print(f"[wifi] SSID '{ssid}' not in scan yet (attempt {i}/{attempts}), rescanning...", flush=True)
    return False


def _wifi_connect(serial, ssid=None, password=None, max_retries=3):
    """Connect to target WiFi with scan-wait and multi-attempt retry for stability."""
    ssid = (ssid or os.environ.get('WIFI_SSID') or 'CH3U_SUCN2_5G').strip()
    password = password or os.environ.get('WIFI_PASSWORD') or os.environ.get('WIFI_PASS') or 'mobility'
    if not serial or not ssid:
        return False

    for attempt in range(1, max_retries + 1):
        print(f"[wifi] [CONNECT] Attempt {attempt}/{max_retries} for SSID: {ssid}", flush=True)

        if not _wifi_is_enabled(serial):
            _wifi_enable(serial)
            time.sleep(2)

        # 先确保目标网络已被扫描到，避免因扫描未就绪导致关联失败。
        _wifi_wait_ssid_in_scan(serial, ssid, attempts=4, interval_sec=3)

        if _wifi_connect_once(serial, ssid, password):
            return True

        if attempt < max_retries:
            # 关联失败后重置 WiFi 状态再重试，清理半连接状态。
            print(f"[wifi] Retry {attempt} failed, toggling WiFi before next attempt...", flush=True)
            adb_shell(serial, "svc", "wifi", "disable")
            time.sleep(2)
            _wifi_enable(serial)
            time.sleep(3)

    print(f"[wifi] [FAILED] Connect exhausted after {max_retries} attempts for SSID: {ssid}", flush=True)
    _wifi_diagnose_state(serial, ssid)
    return False


def _wifi_connect_once(serial, ssid, password):
    """Connect to target WiFi with robust fallback strategies and detailed diagnostics."""
    print(f"[wifi] [START] Connecting to SSID: {ssid}", flush=True)

    if not _wifi_is_enabled(serial):
        print(f"[wifi] WiFi is off, enabling...", flush=True)
        _wifi_enable(serial)
        time.sleep(2)

    print(f"[wifi] Verifying WiFi is enabled...", flush=True)
    if not _wifi_is_enabled(serial):
        print(f"[wifi] [ERROR] WiFi still off after enable attempt", flush=True)
        return False

    print(f"[wifi] Scanning for networks...", flush=True)
    scan_ret = adb_shell(serial, "cmd", "wifi", "start-scan", timeout=12)
    print(f"[wifi] Scan command result code: {scan_ret.returncode}", flush=True)
    time.sleep(3)

    print(f"[wifi] Listing available networks:", flush=True)
    list_ret = adb_shell(serial, "cmd", "wifi", "list-networks", timeout=10)
    if list_ret.returncode == 0:
        networks_list = list_ret.stdout or ""
        print(f"[wifi] Available networks output:\n{networks_list}", flush=True)
        # Check if target SSID is in the list
        if ssid.lower() not in networks_list.lower():
            print(f"[wifi] [WARN] Target SSID '{ssid}' NOT found in available networks", flush=True)
    else:
        print(f"[wifi] [WARN] cmd wifi list-networks failed, trying wpa_cli list_networks...", flush=True)
        # Fallback to wpa_cli for network list (usually unrestricted)
        wpa_list = adb_shell(serial, "wpa_cli", "list_networks", timeout=10)
        if wpa_list.returncode == 0:
            networks_list = wpa_list.stdout or ""
            print(f"[wifi] wpa_cli Available networks:\n{networks_list}", flush=True)
            if ssid.lower() not in networks_list.lower():
                print(f"[wifi] [WARN] Target SSID '{ssid}' NOT found in networks", flush=True)
        else:
            print(f"[wifi] [ERROR] Both list methods failed: {wpa_list.stderr}", flush=True)

    print(f"[wifi] Checking scan results for target SSID...", flush=True)
    scan_results = adb_shell(serial, "cmd", "wifi", "list-scan-results", timeout=10)
    if scan_results.returncode == 0:
        scan_output = scan_results.stdout or ""
        # Print all scan results for visibility
        print(f"[wifi] Scan results:\n{scan_output}", flush=True)
        if ssid.lower() not in scan_output.lower():
            print(f"[wifi] [WARN] Target SSID '{ssid}' NOT found in scan results", flush=True)
    else:
        print(f"[wifi] [WARN] cmd wifi list-scan-results failed, trying wpa_cli...", flush=True)
        # Fallback to wpa_cli for scan results (usually unrestricted)
        wpa_scan = adb_shell(serial, "wpa_cli", "scan_results", timeout=10)
        if wpa_scan.returncode == 0:
            scan_output = wpa_scan.stdout or ""
            print(f"[wifi] wpa_cli Scan results:\n{scan_output}", flush=True)
            if ssid.lower() not in scan_output.lower():
                print(f"[wifi] [WARN] Target SSID '{ssid}' NOT found in scan results", flush=True)
        else:
            print(f"[wifi] [ERROR] Both scan methods failed: {wpa_scan.stderr}", flush=True)

    security_modes = ["wpa2", "wpa", "wpa3", "open"]
    cmd_method_available = True

    for idx, security in enumerate(security_modes, 1):
        if not cmd_method_available:
            print(f"[wifi] Skipping cmd method (permission denied on this ROM), using wpa_cli instead...", flush=True)
            break

        print(f"[wifi] Attempt {idx}/4: Trying security mode: {security}", flush=True)
        try:
            if security == "open":
                conn_ret = adb_shell(serial, "cmd", "wifi", "connect-network", ssid, security, timeout=12)
            else:
                conn_ret = adb_shell(serial, "cmd", "wifi", "connect-network", ssid, security, password, timeout=12)
            print(f"[wifi] connect-network result code: {conn_ret.returncode}", flush=True)

            if conn_ret.stderr:
                error_msg = conn_ret.stderr
                print(f"[wifi] Error: {error_msg}", flush=True)

                # Check for permission denied
                if "does not have access" in error_msg or "SecurityException" in error_msg:
                    print(f"[wifi] [WARN] This ROM restricts cmd wifi connect-network (permission denied)", flush=True)
                    cmd_method_available = False
                    continue

            if _wifi_wait_until_connected(serial, ssid, timeout_sec=16, interval_sec=2):
                print(f"[wifi] [SUCCESS] Connected via {security}", flush=True)
                return True
            else:
                print(f"[wifi] Connection via {security} did not complete in time", flush=True)
        except Exception as e:
            print(f"[wifi] Exception on {security}: {e}", flush=True)

    print(f"[wifi] Fallback: Using wpa_cli method...", flush=True)
    ret = adb_shell(serial, "wpa_cli", "add_network", timeout=10)
    if ret.returncode == 0:
        network_id = (ret.stdout or "").strip()
        print(f"[wifi] Created network with ID: {network_id}", flush=True)
        if network_id.isdigit():
            adb_shell(serial, "wpa_cli", "set_network", network_id, "ssid", f'\\"{ssid}\\"', timeout=10)
            if password:
                adb_shell(serial, "wpa_cli", "set_network", network_id, "psk", f'\\"{password}\\"', timeout=10)
            else:
                adb_shell(serial, "wpa_cli", "set_network", network_id, "key_mgmt", "NONE", timeout=10)
            adb_shell(serial, "wpa_cli", "enable_network", network_id, timeout=10)
            adb_shell(serial, "wpa_cli", "select_network", network_id, timeout=10)
            print(f"[wifi] Waiting for wpa_cli connection...", flush=True)
            if _wifi_wait_until_connected(serial, ssid, timeout_sec=18, interval_sec=2):
                print(f"[wifi] [SUCCESS] Connected via wpa_cli", flush=True)
                return True
            else:
                print(f"[wifi] wpa_cli method did not complete in time", flush=True)

    print(f"[wifi] [FAILED] All connection attempts exhausted", flush=True)
    return False


# WIFI_Method_Sally_0709
def _wifi_diagnose_state(serial, target_ssid=""):
    """Capture detailed WiFi state for debugging."""
    print(f"\n{'=' * 60}", flush=True)
    print(f"[wifi] [DIAGNOSTIC] WiFi State Snapshot", flush=True)
    print(f"{'=' * 60}", flush=True)

    print(f"[wifi] 1. WiFi enabled: {_wifi_is_enabled(serial)}", flush=True)

    print(f"[wifi] 2. List networks:", flush=True)
    list_ret = adb_shell(serial, "cmd", "wifi", "list-networks", timeout=10)
    if list_ret.returncode == 0:
        print(list_ret.stdout, flush=True)
    else:
        print(f"[wifi] cmd failed, trying wpa_cli...", flush=True)
        wpa_ret = adb_shell(serial, "wpa_cli", "list_networks", timeout=10)
        if wpa_ret.returncode == 0:
            print(wpa_ret.stdout, flush=True)
        else:
            print(f"[wifi] Both methods failed", flush=True)

    print(f"[wifi] 3. Scan results:", flush=True)
    scan_ret = adb_shell(serial, "cmd", "wifi", "list-scan-results", timeout=10)
    if scan_ret.returncode == 0:
        for line in (scan_ret.stdout or "").splitlines()[:20]:
            if target_ssid.lower() in line.lower() or not target_ssid:
                print(line, flush=True)
    else:
        print(f"[wifi] cmd failed, trying wpa_cli...", flush=True)
        wpa_scan = adb_shell(serial, "wpa_cli", "scan_results", timeout=10)
        if wpa_scan.returncode == 0:
            for line in (wpa_scan.stdout or "").splitlines()[:20]:
                if target_ssid.lower() in line.lower() or not target_ssid:
                    print(line, flush=True)

    print(f"[wifi] 4. Current connection state:", flush=True)
    wifi_ret = adb_shell(serial, "dumpsys", "wifi", timeout=20)
    lines = (wifi_ret.stdout or "").splitlines()
    for i, line in enumerate(lines):
        if any(kw in line for kw in
               ["mConnectedNetwork", "mWifiInfo", "mNetworkInfo", "state:", "SSID", "Supplicant", "L3ConnectedState"]):
            print(line, flush=True)

    print(f"[wifi] 5. Network info:", flush=True)
    info_ret = adb_shell(serial, "dumpsys", "connectivity", timeout=10)
    lines = (info_ret.stdout or "").splitlines()
    for line in lines:
        if "WIFI" in line or "state" in line.lower() or "ip" in line.lower():
            print(line, flush=True)

    print(f"{'=' * 60}", flush=True)


# WIFI_Method_Sally_0709
def _wifi_get_gateway(serial):
    """Get default gateway address."""
    out = _wifi_shell_output(serial, "ip", "route", "show", timeout=10)
    for line in out.splitlines():
        if "default via" in line:
            parts = line.split()
            try:
                return parts[parts.index("via") + 1]
            except Exception:
                pass
    return None


# WIFI_Method_Sally_0709
def _wifi_is_internet_reachable(serial):
    """Check internet connectivity by gateway/public ping."""
    gw = _wifi_get_gateway(serial)
    if gw:
        ret = adb_shell(serial, "ping", "-c", "2", "-W", "3", gw, timeout=15)
        if "bytes from" in (ret.stdout or ""):
            return True

    for host in ["223.5.5.5", "180.76.76.76", "8.8.8.8"]:
        ret = adb_shell(serial, "ping", "-c", "2", "-W", "3", host, timeout=15)
        if "bytes from" in (ret.stdout or ""):
            return True
    return False


# WIFI_Method_Sally_0709
def _wifi_sleep_then_wake_up(serial):
    """Sleep then wake and unlock device."""
    print("[wifi] Entering sleep mode...", flush=True)
    adb_shell(serial, "input", "keyevent", "26")
    time.sleep(2)

    print("[wifi] Waking up screen...", flush=True)
    adb_shell(serial, "input", "keyevent", "26")
    time.sleep(1)
    adb_shell(serial, "input", "keyevent", "82")
    time.sleep(2)  # Give device time to stabilize after wake

    power_out = _wifi_shell_output(serial, "dumpsys", "power", timeout=10)
    awake = "Display Power: state=ON" in power_out or "mWakefulness=Awake" in power_out

    if awake:
        print("[wifi] [OK] Device awake, waiting for WiFi to stabilize...", flush=True)
        time.sleep(2)  # Additional wait for WiFi subsystem to recover

    return awake


# WIFI_Method_Sally_0709
def _wifi_current_focus_text(serial):
    """Get current top page marker text from dumpsys output."""
    out = _wifi_shell_output(serial, "dumpsys", "activity", "top", timeout=8)
    m = re.search(r"ACTIVITY\s+([a-zA-Z0-9_\.]+/[a-zA-Z0-9_\.$]+)", out)
    if m:
        return m.group(1)

    out2 = _wifi_shell_output(serial, "dumpsys", "window", "windows", timeout=8)
    m2 = re.search(r"mCurrentFocus.+", out2)
    if m2:
        return m2.group(0)

    out3 = _wifi_shell_output(serial, "dumpsys", "activity", "activities", timeout=8)
    m3 = re.search(r"mResumedActivity:.*? ([a-zA-Z0-9_\.]+/[a-zA-Z0-9_\.$]+)", out3)
    return m3.group(1) if m3 else ""


# WIFI_Method_Sally_0709
def _wifi_icon_disappeared_proxy_check(serial):
    """Proxy check for WiFi icon disappearance."""
    wifi_off = not _wifi_is_enabled(serial)
    conn_out = _wifi_shell_output(serial, "dumpsys", "connectivity", timeout=10)
    not_connected = "WIFI" not in conn_out or "CONNECTED" not in conn_out
    return wifi_off and not_connected


# WIFI_Method_Sally_0709
def _wifi_icon_disappeared_ui_check(serial):
    """WiFi icon disappearance check based on wifi_on=0."""
    return not _wifi_is_enabled(serial)


# WIFI_Method_Sally_0709
def _wifi_get_focus_text_with_retry(serial, retries=5, interval=0.4):
    """Retry focus text read during page transitions."""
    last = ""
    for _ in range(retries):
        last = _wifi_current_focus_text(serial)
        if last:
            return last
        time.sleep(interval)
    return last


# WIFI_Method_Sally_0709
def _wifi_press_back_and_verify_return(serial):
    """Press back from WiFi page and verify return to upper Settings menu."""
    before = _wifi_current_focus_text(serial)
    adb_shell(serial, "input", "keyevent", "4")
    time.sleep(1.5)
    after = _wifi_current_focus_text(serial)

    before_is_wifi_page = (
            "com.android.settings" in before
            and (
                    "SubSettings" in before
                    or "Wifi" in before
                    or "WIFI" in before
                    or "wlan" in before.lower()
            )
    )
    after_is_settings_upper = (
            "com.android.settings/com.android.settings.Settings" in after
            or (
                    "com.android.settings" in after
                    and "SubSettings" not in after
                    and "Wifi" not in after
                    and "WIFI" not in after
                    and "wlan" not in after.lower()
            )
    )
    return before != after and before_is_wifi_page and after_is_settings_upper

# SwitchPhotoVideo_Method_Sally_2026-08-03
def switch_photo_video_is_device_awake(serial):
    """Check whether device display is awake via dumpsys power."""
    out = (adb_shell(serial, "dumpsys", "power", timeout=8).stdout or "").lower()
    return (
        "display power: state=on" in out
        or "mwakefulness=awake" in out
        or "isinteractive=true" in out
    )

# SwitchPhotoVideo_Method_Sally_2026-08-03
def switch_photo_video_set_stayon(serial, enabled=True):
    """Enable or disable stay-on for SwitchPhotoVideo case."""
    adb_shell(serial, "svc", "power", "stayon", "true" if enabled else "false", timeout=6)

# Force stop settings app_Sophy_H400818_2026-08-13
def force_stop_Settings_app(serial, package_name):
    """
    Force stop an Android application.

    :param serial: device serial
    :param package_name: package name to stop, e.g. com.android.settings
    :return: True if command executed without raising exception, else False
    """
    cmd = f"shell am force-stop {package_name}"
    result = run_adb_cmd(serial, cmd, log_print=False)
    return result != 'error'


# RTC_Method_Read Time format_Sophy_H400818_2026-08-13
def rtc_settings_get_time_format_value(serial, namespace, key, timeout=8):
    """Read value from adb shell settings get <namespace> <key>."""
    if not serial:
        return ""
    ret = adb_shell(serial, "settings", "get", namespace, key, timeout=timeout)
    if ret.returncode != 0:
        return ""
    return (ret.stdout or "").strip()


# RTC_Method_Sophy_H400818_2026-08-13
def rtc_date_output(serial, date_pattern, timeout=8):
    """Run adb shell date with a pattern and return (stdout, stderr)."""
    if not serial:
        return "", ""
    ret = adb_shell(serial, "date", date_pattern, timeout=timeout)
    out = (ret.stdout or "").strip()
    err = (ret.stderr or "").strip()
    return out, err


# Open Date&time settings_Sophy_H400818_2026-08-13
def rtc_open_date_time_setting(serial, restart_settings=False, timeout=10):
    """Open Android Date & time settings page via adb am start."""
    if not serial:
        return False
    cmd_parts = ["am", "start"]
    if restart_settings:
        cmd_parts.append("-S")
    cmd_parts.extend(["-a", "android.settings.DATE_SETTINGS"])
    ret = adb_shell(serial, *cmd_parts, timeout=timeout)
    return ret.returncode == 0


# RTC_Method_get_time_zone_Sophy_H400818_2026-08-13
def rtc_get_time_zone(serial, prop_name, timeout=8):
    """Read Android system property via adb shell getprop."""
    if not serial:
        return ""
    ret = adb_shell(serial, "getprop", prop_name, timeout=timeout)
    if ret.returncode != 0:
        return ""
    return (ret.stdout or "").strip()


# RTC_Method_Set date by adb_Sophy_H400818_2026-08-13
def rtc_set_device_date(serial, year, month, day, hhmm="1200", timeout=5):
    """Set device date using adb shell date MMDDhhmmYYYY."""
    if not serial:
        return False, "serial is empty"
    date_cmd = f"{int(month):02d}{int(day):02d}{hhmm}{int(year):04d}"
    ret = adb_shell(serial, "date", date_cmd, timeout=timeout)
    out = (ret.stdout or "").strip()
    err = (ret.stderr or "").strip()
    if ret.returncode == 0 and "invalid" not in out.lower() and "invalid" not in err.lower():
        return True, ""
    return False, err or out or "date command failed"


# RTC_Method_Reboot device_Sophy_H400818_2026-08-13
def rtc_reboot_device(serial, timeout=10):
    """Reboot device via adb reboot."""
    if not serial:
        return False
    try:
        ret = subprocess.run(
            ["adb", "-s", serial, "reboot"],
            capture_output=True,
            text=True,
            errors="ignore",
            check=False,
            timeout=timeout,
        )
        return ret.returncode == 0
    except Exception:
        return False


# RTC_Method_Wait device_Sophy_H400818_2026-08-13
def rtc_wait_for_device(serial, timeout=60):
    """Wait until adb can see the target device."""
    if not serial:
        return False
    try:
        ret = subprocess.run(
            ["adb", "-s", serial, "wait-for-device"],
            capture_output=True,
            text=True,
            errors="ignore",
            check=False,
            timeout=timeout,
        )
        return ret.returncode == 0
    except Exception:
        return False


# RTC_Method_Check boot completed_Sophy_H400818_2026-08-13
def rtc_is_boot_completed(serial, timeout=8):
    """Return True when getprop sys.boot_completed is 1."""
    if not serial:
        return False
    ret = adb_shell(serial, "getprop", "sys.boot_completed", timeout=timeout)
    if ret.returncode != 0:
        return False
    return (ret.stdout or "").strip() == "1"


# RTC_Method_Run shell raw_Sophy_H400818_2026-08-13
def rtc_shell_run_raw(serial, shell_command, timeout=8):
    """Run raw adb shell command string via sh -c and return CompletedProcess."""
    if not serial:
        return None
    try:
        return subprocess.run(
            ["adb", "-s", serial, "shell", "sh", "-c", shell_command],
            capture_output=True,
            text=True,
            errors="ignore",
            check=False,
            timeout=timeout,
        )
    except Exception:
        return None


# RTC_Method_Detect power input device_Sophy_H400818_2026-08-13
def rtc_detect_power_input_device(serial, timeout=6):
    """Detect input event node for KEY_POWER, fallback to /dev/input/event0."""
    cmd = "getevent -lp 2>/dev/null | grep -B 20 'KEY_POWER' | grep 'add device' | head -1 | awk '{print $4}'"
    ret = rtc_shell_run_raw(serial, cmd, timeout=timeout)
    if ret is None:
        return "/dev/input/event0"
    detected = (ret.stdout or "").strip()
    if detected.startswith("/dev/input/event"):
        return detected
    return "/dev/input/event0"


# RTC_Method_Start hold-power 8s script_Sophy_H400818_2026-08-13
def rtc_start_hold_power_script(serial, input_device, hold_seconds=10, script_path="/data/local/tmp/hold_power.sh"):
    """Push and start a remote shell script that holds KEY_POWER for forced reboot."""
    if not serial:
        return False
    hold_seconds = max(1, int(hold_seconds))
    hold_script = (
        "#!/system/bin/sh\n"
        f"INPUT_DEV=\"{input_device}\"\n"
        "sendevent $INPUT_DEV 1 116 1\n"
        "sendevent $INPUT_DEV 0 0 0\n"
        f"for i in $(seq 1 {hold_seconds}); do\n"
        "  sleep 1\n"
        "  sendevent $INPUT_DEV 1 116 1\n"
        "  sendevent $INPUT_DEV 0 0 0\n"
        "done\n"
        "sendevent $INPUT_DEV 1 116 0\n"
        "sendevent $INPUT_DEV 0 0 0\n"
    )
    escaped = hold_script.replace("'", "'\\''")
    write_ret = rtc_shell_run_raw(serial, f"printf '%s' '{escaped}' > {script_path}", timeout=8)
    if write_ret is None or write_ret.returncode != 0:
        return False
    chmod_ret = rtc_shell_run_raw(serial, f"chmod 755 {script_path}", timeout=5)
    if chmod_ret is None or chmod_ret.returncode != 0:
        return False
    run_ret = rtc_shell_run_raw(serial, f"sh {script_path} >/dev/null 2>&1 &", timeout=4)
    return run_ret is not None and run_ret.returncode == 0


# RTC_Method_Send power keyevent_Sophy_H400818_2026-08-13
def rtc_send_power_keyevent(serial, timeout=2):
    """Send one POWER keyevent."""
    if not serial:
        return False
    ret = adb_shell(serial, "input", "keyevent", "KEYCODE_POWER", timeout=timeout)
    return ret.returncode == 0

# Settings_Common_Open_Sophy_H400818_2026-08-14
def open_settings(serial, timeout=8):
    """Open the main Android Settings page via adb."""
    if not serial:
        return False
    ret = adb_shell(serial, "am", "start", "-a", "android.settings.SETTINGS", timeout=timeout)
    return ret.returncode == 0


# wwan_enable_mobile_data_Sophy_H400818_2026-08-17
def wwan_enable_mobile_data(serial, timeout=8):
    """Enable mobile data so network time synchronization can use WWAN."""
    if not serial:
        return False
    ret = adb_shell(serial, "svc", "data", "enable", timeout=timeout)
    return ret.returncode == 0


# ScanDemo_Open_Sophy_H400818_2026-08-17
def scandemo_open(serial, device=None, timeout=10):
    """Open ScanDemo and click the optional initial scan action icon."""
    if not serial:
        return False
    ret = adb_shell(
        serial,
        "am",
        "start",
        "-n",
        "com.honeywell.demos.scandemo/.ScanDemoMainActivity",
        timeout=timeout,
    )
    if ret.returncode != 0:
        return False

    if device is not None:
        scan_action = device(resourceId="com.honeywell.demos.scandemo:id/ivScanAction")
        if scan_action.exists(timeout=2):
            print("  ivScanAction found, clicking it before Scan...", flush=True)
            try:
                scan_action.click()
                time.sleep(0.5)
            except Exception as error:
                print(f"  Failed to click ivScanAction: {error}", flush=True)
                return False
        else:
            print("  ivScanAction not found, continuing directly to Scan...", flush=True)

    return True

# WIFI_Method_Open settings/wifi by adb_Sophy_H400818_2026-08-21
def wifi_open_settings_by_adb(serial, timeout=8):
    """Open Android WiFi settings directly through adb."""
    if not serial:
        return False
    ret = adb_shell(serial, "am", "start", "-a", "android.settings.WIFI_SETTINGS", timeout=timeout)
    return ret.returncode == 0

# RTC_sophy_H400818_get_os_build_date_2026-08-21
def get_os_build_date(serial):
    """Get the current OS build date from ro.build.date."""
    if not serial:
        return "error"

    ret = adb_shell(serial, "getprop", "ro.build.date", timeout=8)
    result = (ret.stdout or "").strip()
    return result if result else "error"

# RTC_sophy_H400818_Check SIM Card status_2026-09-21
def sim_card_is_present(serial, timeout=8):
    """Return whether a SIM card is detected via operator numeric properties."""
    operator_numeric = adb_shell_output(
        serial, "getprop", "gsm.sim.operator.numeric", timeout=timeout
    ).strip()
    if operator_numeric:
        return True

    slot0_operator_numeric = adb_shell_output(
        serial, "getprop", "gsm.sim.operator.numeric.slot0", timeout=timeout
    ).strip()
    return bool(slot0_operator_numeric)

# Keyremap_Method_Sophy_H400818_2026-08-27
def keyremap_click_virtual_appswitch(serial):
    """Tap the rightmost virtual Overview(App Switch) icon inside the Keyremap key-capture dialog.

    Args: serial is the target device serial number.
    Returns: None. Waits for the dialog to update after tapping.
    Precondition: the "Please press the key to be mapped" dialog is open; tap coordinates are scaled
          from the 1080x2160 baseline to the device's actual resolution.
    """
    size_output = run_adb_cmd(serial, "shell wm size", log_print=False)
    size_text = size_output.decode("utf-8", errors="ignore") if isinstance(size_output, bytes) else str(size_output)
    sizes = re.findall(r"(?:Override|Physical) size:\s*(\d+)x(\d+)", size_text)
    if sizes:
        screen_width, screen_height = (int(value) for value in sizes[-1])
        tap_x = round(screen_width * 828 / 1080)
        tap_y = round(screen_height * 1203 / 2160)
    else:
        tap_x, tap_y = 828, 1203
    run_adb_cmd(serial, f"shell input tap {tap_x} {tap_y}", log_print=False)
    time.sleep(1)

# Keyremap_Method_Sophy_H400818_2026-08-27
def keyremap_tap_navbar_appswitch(serial, wait=2):
    """Tap the rightmost Overview(App Switch) button on the software nav bar, triggering the kernel-level key remap.

    Args: serial is the target device serial number; wait is the settle delay in seconds after the tap
          (use a small value when the remap needs rapid repeated presses, e.g. VOLUME_UP steps).
    Returns: None. Waits for the event to take effect.
    Precondition: device is 1080x2160; the nav bar is at the bottom of the screen with Overview on the far right,
          symmetric with the Back button coordinate (150, 2088) already verified by the Keyremap test case.
    """
    size_output = run_adb_cmd(serial, "shell wm size", log_print=False)
    size_text = size_output.decode("utf-8", errors="ignore") if isinstance(size_output, bytes) else str(size_output)
    match = re.search(r"Physical size:\s*(\d+)x(\d+)", size_text)
    if match:
        screen_width, screen_height = (int(value) for value in match.groups())
        tap_x = round(screen_width * 789 / 1080)
        tap_y = round(screen_height * 2088 / 2160)
    else:
        tap_x, tap_y = 789, 2120
    run_adb_cmd(serial, f"shell input tap {tap_x} {tap_y}", log_print=False)
    time.sleep(wait)
    
# Keyremap_Method_Sophy_H400818_2026-08-28
def keyremap_tap_navbar_back(serial, wait=2):
    """Tap the leftmost Back button on the software nav bar, triggering the kernel-level key remap.
 
    Args: serial is the target device serial number; wait is the settle delay in seconds after the tap
          (use a small value when the remap needs rapid repeated presses, e.g. VOLUME_UP steps).
    Returns: None. Waits for the event to take effect.
    Precondition: the nav bar is at the bottom of the screen with Back on the far left.
    """
    window_output = run_adb_cmd(serial, "shell dumpsys window windows", log_print=False)
    window_text = (
        window_output.decode("utf-8", errors="ignore")
        if isinstance(window_output, bytes)
        else str(window_output)
    )
    nav_frame = re.search(
        r"NavigationBar0[\s\S]*?Frames:.*?frame=\[(\d+),(\d+)\]\[(\d+),(\d+)\]",
        window_text,
    )
    if nav_frame:
        left, top, right, bottom = (int(value) for value in nav_frame.groups())
        tap_x = left + round((right - left) / 4)
        tap_y = top + round((bottom - top) / 2)
    else:
        size_output = run_adb_cmd(serial, "shell wm size", log_print=False)
        size_text = size_output.decode("utf-8", errors="ignore") if isinstance(size_output, bytes) else str(size_output)
        match = re.search(r"Physical size:\s*(\d+)x(\d+)", size_text)
        if match:
            screen_width, screen_height = (int(value) for value in match.groups())
            tap_x = round(screen_width * 150 / 1080)
            tap_y = screen_height - 72
        else:
            tap_x, tap_y = 150, 2120
    run_adb_cmd(serial, f"shell input tap {tap_x} {tap_y}", log_print=False)
    time.sleep(wait)

# Keyremap_Method_Sophy_H400818_2026-08-28
def keyremap_click_virtual_home(serial):
    """Tap the middle virtual Home icon inside the Keyremap key-capture dialog.

    Args: serial is the target device serial number.
    Returns: None. Waits for the dialog to update after tapping.
    Precondition: the "Please press the key to be mapped" dialog is open; tap coordinates are scaled
          from the 1080x2160 baseline to the device's actual resolution.
    """
    size_output = run_adb_cmd(serial, "shell wm size", log_print=False)
    size_text = size_output.decode("utf-8", errors="ignore") if isinstance(size_output, bytes) else str(size_output)
    sizes = re.findall(r"(?:Override|Physical) size:\s*(\d+)x(\d+)", size_text)
    if sizes:
        screen_width, screen_height = (int(value) for value in sizes[-1])
        tap_x = round(screen_width * 540 / 1080)
        tap_y = round(screen_height * 1203 / 2160)
    else:
        tap_x, tap_y = 540, 1203
    run_adb_cmd(serial, f"shell input tap {tap_x} {tap_y}", log_print=False)
    time.sleep(1)

# Keyremap_Method_Sophy_H400818_2026-08-28
def keyremap_tap_navbar_home(serial, wait=2, hold_ms=0):
    """Tap the middle Home button on the software nav bar, triggering the kernel-level key remap.

        Args: serial is the target device serial number; wait is the settle delay in seconds after the tap
            (use a small value when the remap needs rapid repeated presses, e.g. VOLUME_UP steps);
            hold_ms optionally holds the Home touch for the given duration in milliseconds.
    Returns: None. Waits for the event to take effect.
    Precondition: the nav bar is at the bottom of the screen with Home centered between the Back and
          Overview(App Switch) buttons; both axes are scaled from the 1080x2160 baseline (470, 2088)
          to the device's actual resolution.
    """
    size_output = run_adb_cmd(serial, "shell wm size", log_print=False)
    size_text = size_output.decode("utf-8", errors="ignore") if isinstance(size_output, bytes) else str(size_output)
    match = re.search(r"Physical size:\s*(\d+)x(\d+)", size_text)
    if match:
        screen_width, screen_height = (int(value) for value in match.groups())
        tap_x = round(screen_width * 470 / 1080)
        tap_y = round(screen_height * 2088 / 2160)
    else:
        tap_x, tap_y = 470, 2120
    if hold_ms > 0:
        run_adb_cmd(
            serial,
            f"shell input swipe {tap_x} {tap_y} {tap_x} {tap_y} {int(hold_ms)}",
            log_print=False,
        )
    else:
        run_adb_cmd(serial, f"shell input tap  {tap_x} {tap_y}", log_print=False)

    time.sleep(wait)

# Keyremap_Method_Sophy_H400818_2026-08-27
def keyremap_is_stream_muted(serial, stream_name="STREAM_MUSIC"):
    """Parse `dumpsys audio` output to determine whether the given audio stream is muted.

    Args: serial is the target device serial number; stream_name is the audio stream to check, default STREAM_MUSIC.
    Returns: True if muted, False if not muted, None if it cannot be parsed.
    Precondition: the device's `dumpsys audio` output contains a section like "- STREAM_MUSIC:\\n   Muted: true".
    """
    output = run_adb_cmd(serial, "shell dumpsys audio", log_print=False)
    output_text = output.decode("utf-8", errors="ignore") if isinstance(output, bytes) else str(output)
    match = re.search(rf"{stream_name}:.*?Muted:\s*(true|false)", output_text, re.DOTALL | re.IGNORECASE)
    if not match:
        return None
    return match.group(1).lower() == "true"


# Keyremap_Method_Sophy_H400818_2026-08-27
def keyremap_get_stream_volume_index(serial, stream_name="STREAM_MUSIC"):
    """Parse `dumpsys audio` output to get the current volume index of the given audio stream (0 means the progress bar is at the far left).

    Args: serial is the target device serial number; stream_name is the audio stream to check, default STREAM_MUSIC.
    Returns: the current volume index (int) on success, None if it cannot be parsed.
    Precondition: the device's `dumpsys audio` output contains a section like "- STREAM_MUSIC:\n   Current: ...: 0, ...".
    """
    output = run_adb_cmd(serial, "shell dumpsys audio", log_print=False)
    output_text = output.decode("utf-8", errors="ignore") if isinstance(output, bytes) else str(output)
    match = re.search(rf"{stream_name}:.*?Current:\s*[^:]*:\s*(\d+)", output_text, re.DOTALL | re.IGNORECASE)
    if not match:
        return None
    return int(match.group(1))


# Keyremap_Method_Sophy_H400818_2026-08-28
def keyremap_is_media_volume_zero_by_media_session(serial, stream=3):
    """Use `adb shell cmd media_session volume --stream <stream> --get` to check whether the volume is 0 (muted).

    Args: serial is the target device serial number; stream is the audio stream index for media_session volume,
          default 3 (STREAM_MUSIC).
    Returns: True if the parsed volume is 0, False if it is a positive number, None if it cannot be parsed.
    Precondition: the device's `cmd media_session volume --stream <stream> --get` output contains a line like
          "volume is 0".
    """
    output = run_adb_cmd(serial, f"shell cmd media_session volume --stream {stream} --get", log_print=False)
    output_text = output.decode("utf-8", errors="ignore") if isinstance(output, bytes) else str(output)
    match = re.search(r"volume is\s*(\d+)", output_text, re.IGNORECASE)
    if not match:
        return None
    return int(match.group(1)) == 0

# Keyremap_Method_Sophy_H400818_2026-09-01
def keyremap_set_stream_volume_index(serial, index, stream_name="STREAM_MUSIC", max_steps=30):
    """Step the volume with VOLUME_UP/DOWN keyevents until the stream reaches the target index.

    Args: serial is the target device serial number; index is the target volume index; stream_name is the
          audio stream read back from `dumpsys audio`; max_steps caps the number of key presses.
    Returns: True when the target index was reached, otherwise False.
    Precondition: `cmd media_session volume --set` is silently ignored on this platform, so volume keys are
          used instead and the level is re-read after every press.
    """
    for _ in range(max_steps):
        current = keyremap_get_stream_volume_index(serial, stream_name)
        if current is None:
            return False
        if current == index:
            return True
        # 24 = KEYCODE_VOLUME_UP, 25 = KEYCODE_VOLUME_DOWN
        run_adb_cmd(serial, f"shell input keyevent {24 if current < index else 25}", log_print=False)
        time.sleep(0.4)
    return keyremap_get_stream_volume_index(serial, stream_name) == index                                   

# Keyremap_Method_Sophy_H400818_2026-08-28
def keyremap_force_stop_honeywell_settings(serial):
    """Force-stop the Honeywell Settings app (com.honeywell.settings) via ADB.

    Args: serial is the target device serial number.
    Returns: True if the command executed without raising an exception, otherwise False.
    Precondition: none.
    """
    result = run_adb_cmd(serial, "shell am force-stop com.honeywell.settings", log_print=False)
    return result != "error"

 # Keyremap_Method_Sophy_H400818_2026-09-02
def keyremap_dump_recents_ui_markers(serial):
    """Dump the current UI hierarchy and return the Overview-only markers found in it.

    Args: serial is the target device serial number.
    Returns: a set of marker strings that only exist on the Recent apps (Overview) screen.
    Precondition: uiautomator2 is installed and the device is reachable.
    """
    # On Quickstep launchers (Launcher3 + SearchLauncher) the Overview screen is an overlay inside
    # the launcher window, so dumpsys keeps reporting the launcher activity. These view ids/labels
    # are the only reliable signals. Note: overview_actions_view also exists on the home screen,
    # so it must NOT be used as a marker.
    overview_markers = (
        "com.android.launcher3:id/overview_panel",
        "com.android.launcher3:id/action_screenshot",
        "com.android.launcher3:id/action_clear_all",
        "com.android.launcher3:id/clear_all",
        "com.android.quickstep:id/overview_panel",
    )
    try:
        import uiautomator2 as u2

        hierarchy = u2.connect(serial).dump_hierarchy()
    except Exception:
        return set()
    return {marker for marker in overview_markers if marker in hierarchy}                      
# Keyremap_Method_Sophy_H400818_2026-08-28
def keyremap_is_on_recent_apps(serial, timeout=8):
    """Poll window/activity state and the UI hierarchy to detect the Recent apps (Overview) screen.

    Args: serial is the target device serial number; timeout is the max polling duration in seconds.
    Returns: (is_on_recents, most recent focused window info or the matched Overview marker).
    Precondition: the Overview screen is either a standalone recents activity or a Quickstep overlay
          rendered inside the launcher window.
    """
    recents_keywords = ("recents", "recentsactivity", "overview", "quickstep", "taskswitcher")
    deadline = time.time() + timeout
    last_focus = ""

    while time.time() < deadline:
        signals = []

        window_output = run_adb_cmd(serial, "shell dumpsys window", log_print=False)
        window_text = (
            window_output.decode("utf-8", errors="ignore")
            if isinstance(window_output, bytes)
            else str(window_output)
        )
        for line in window_text.splitlines():
            if "mCurrentFocus" in line or "mFocusedApp" in line:
                signals.append(line.strip())
                if "mCurrentFocus" in line:
                    last_focus = line.strip()

        activity_output = run_adb_cmd(serial, "shell dumpsys activity recents", log_print=False)
        activity_text = (
            activity_output.decode("utf-8", errors="ignore")
            if isinstance(activity_output, bytes)
            else str(activity_output)
        )
        for line in activity_text.splitlines():
            if "mResumedActivity" in line or "topResumedActivity" in line or "Recent tasks" in line:
                signals.append(line.strip())

        state_text = " ".join(signals).lower()
        focus = last_focus or (signals[0] if signals else "")
        if any(keyword in state_text for keyword in recents_keywords):
            return True, focus
            
        # Quickstep fallback: dumpsys still reports the launcher, so check the UI hierarchy.
        ui_markers = keyremap_dump_recents_ui_markers(serial)
        if ui_markers:
            return True, f"{focus} | overview markers: {sorted(ui_markers)}"                                                                                                                                                                                        
        time.sleep(1)

    return False, last_focus


# Keyremap_Method_Sophy_H400818_2026-08-27
def keyremap_input_text(serial, text):
    """Input text into the currently focused input box via ADB.

    Args: serial is the target device serial number; text is the text to input (no spaces).
    Returns: None. Waits for the input to take effect.
    Precondition: the target input box already has focus.
    """
    run_adb_cmd(serial, f"shell input text {text}", log_print=False)
    time.sleep(1)

# PictureQuality_Method_Sally_2026-08-27
PICTURE_QUALITY_PHOTO_EXTENSIONS = ("jpg", "jpeg", "png", "heic")

# PictureQuality_Method_Sally_2026-08-27
# /sdcard and /storage/emulated/0 are the same mount, so only one form is listed.
PICTURE_QUALITY_PHOTO_DIRECTORIES = ("/sdcard/DCIM/Camera", "/sdcard/Pictures/Camera")

# PictureQuality_Method_Sally_2026-08-27
def picture_quality_list_photos_with_size(serial, directories=None, extensions=None):
    """Return camera photos as {full_path: size_bytes} from the given media folders."""
    directories = directories or PICTURE_QUALITY_PHOTO_DIRECTORIES
    extensions = extensions or PICTURE_QUALITY_PHOTO_EXTENSIONS
    photos = {}
    for directory in directories:
        patterns = [f"{directory}/*.{ext}" for ext in extensions]
        result = adb_shell(serial, "stat", "-c", "'%s %n'", *patterns, "2>/dev/null", timeout=20)
        for line in result.stdout.splitlines():
            size, _, path = line.strip().partition(" ")
            if size.isdigit() and path:
                photos[path] = int(size)
    return photos
# IMEI_Method_Sophy_H400818_2026-09-01
def imei_get_baseband_type(serial):
    """Read ro.baseband to tell if the device has telephony (msm) or is WLAN-only (apq).

    Args: serial is the target device serial number.
    Returns: the lowercased baseband value, or '' if the property could not be read.
    Precondition: none.
    """
    try:
        result = subprocess.run(
            f"adb -s {serial} shell getprop ro.baseband",
            capture_output=True, text=True, shell=True, timeout=5,
        )
        return result.stdout.strip().lower()
    except Exception:
        return ""


# Model_Method_Sophy_H400818_2026-09-01
def get_device_model(serial):
    """Read ro.product.model via adb getprop.

    Args: serial is the target device serial number.
    Returns: the model string (e.g. "CT47"), or '' if it could not be read.
    Precondition: none.
    """
    try:
        result = subprocess.run(
            f"adb -s {serial} shell getprop ro.product.model",
            capture_output=True, text=True, shell=True, timeout=5,
        )
        return result.stdout.strip()
    except Exception:
        return ""


# IMEI_Method_Sophy_H400818_2026-09-01
def imei_open_about_phone(serial):
    """Open Settings -> About phone via the DEVICE_INFO_SETTINGS intent.

    Args: serial is the target device serial number.
    Returns: None.
    Precondition: none.
    """
    subprocess.run(
        f"adb -s {serial} shell am start -a android.settings.DEVICE_INFO_SETTINGS",
        capture_output=True, text=True, shell=True,
    )


# DevOptions_Method_Sophy_H400818_2026-09-01
def dev_options_is_enabled(serial):
    """Check whether Developer Options is enabled via the global setting.

    Args: serial is the target device serial number.
    Returns: True if development_settings_enabled == 1, else False.
    Precondition: none.
    """
    result = subprocess.run(
        f"adb -s {serial} shell settings get global development_settings_enabled",
        capture_output=True, text=True, shell=True, timeout=5,
    )
    return result.stdout.strip() == "1"


# DevOptions_Method_Sophy_H400818_2026-09-01
def dev_options_set_enabled(serial, enabled):
    """Directly set the development_settings_enabled global setting via adb.

    Args: serial is the target device serial number; enabled is the desired boolean state.
    Returns: None.
    Precondition: none.
    """
    subprocess.run(
        f"adb -s {serial} shell settings put global development_settings_enabled {1 if enabled else 0}",
        shell=True, timeout=5,
    )

# WWAN_Method_Frank_Xu_2026-09-07
# Author: Frank Xu
# Date: 2026-09-07
# Purpose: Provide SIM-slot readiness and data-only-device checks shared by WWAN GSM/GPRS
# and WCDMA/4G/5G test cases.
def sim_card_in_slot_is_present(serial, slot_index=0, timeout=8):
    """Return whether the requested physical SIM slot has a ready SIM for WWAN testing."""
    state = adb_shell_output(serial, "getprop", "gsm.sim.state.slot{}".format(slot_index), timeout=timeout).upper()
    if not state:
        states = adb_shell_output(serial, "getprop", "gsm.sim.state", timeout=timeout).upper().split(",")
        state = states[slot_index].strip() if len(states) > slot_index else ""
    absent_keywords = ("", "ABSENT", "UNKNOWN", "NOT_READY", "CARD_IO_ERROR", "PERM_DISABLED")
    return not any(keyword in state for keyword in absent_keywords)


def is_wwan_data_only_device(serial):
    """Return whether the device supports WWAN data only and must skip voice/SMS checks."""
    return get_device_model(serial).strip().upper() in ("CK67", "RT710")


# WIFI_Method_Sally_0907
def _wifi_is_baidu_reachable(serial, timeout=15):
    """Verify https://www.baidu.com is actually reachable via an on-device HTTP request."""
    ret = adb_shell(
        serial,
        "curl", "-s", "-k", "--max-time", "10", "-o", "/dev/null", "-w", "%{http_code}",
        "https://www.baidu.com",
        timeout=timeout,
    )
    http_code = (ret.stdout or "").strip()
    return http_code in ("200", "301", "302", "307", "308")

# CameraPreview_Method_Sally_2026-09-08
def camera_stop_packages(serial, packages=None):
    """通过 ADB 停止候选相机应用。"""
    for package in packages or CAMERA_PACKAGES:
        adb_shell(serial, "am", "force-stop", package, timeout=8)

# EMMC_Method_Sally_2026-09-08
def emmc_list_internal_videos_with_meta(serial, min_size=1):
    """枚举内部存储视频并带上 (mtime, size)，用于按修改时间挑选真正录好的文件。

    snapcam 录制时会先产生 0 字节占位文件，且文件名按录制开始时间命名，仅靠文件名
    字母序容易选错。用 stat 的 mtime + size 才能可靠定位刚录好的视频。

    :return: [(path, mtime_int, size_int), ...]，仅包含 size >= min_size 的文件
    """
    VIDEO_DIRS = [
        "/sdcard/DCIM/Camera",
        "/storage/emulated/0/DCIM/Camera",
        "/sdcard/Movies",
        "/storage/emulated/0/Movies",
    ]
    globs = " ".join(
        f"{d}/*.mp4 {d}/*.3gp {d}/*.mkv {d}/*.webm" for d in VIDEO_DIRS
    )
    cmd = f"stat -c '%Y %s %n' {globs} 2>/dev/null"
    ret = adb_shell(serial, cmd, timeout=12)
    out = (ret.stdout or "").strip()
    results = []
    seen = set()
    for line in out.splitlines():
        parts = line.strip().split(" ", 2)
        if len(parts) != 3:
            continue
        mtime_s, size_s, path = parts
        try:
            mtime_i, size_i = int(mtime_s), int(size_s)
        except ValueError:
            continue
        if size_i < min_size or path in seen:
            continue
        seen.add(path)
        results.append((path, mtime_i, size_i))
    return results


# EMMC_Method_Sally_2026-09-08
def emmc_newest_valid_video_file(serial, min_size=1):
    """返回按修改时间最新、且大小非零的视频文件路径（挑真正录好的那个）。"""
    metas = emmc_list_internal_videos_with_meta(serial, min_size=min_size)
    if not metas:
        return ""
    metas.sort(key=lambda t: t[1])
    return metas[-1][0]


# Keyremap_Method_Sophy_H400818_2026-09-02
def keyremap_is_app_installed(serial, package_name):
    """Check whether a package is installed on the device.

    Args: serial is the target device serial number; package_name is the package to look for.
    Returns: True if `pm list packages` reports the package, otherwise False.
    Precondition: none.
    """
    output = adb_shell_output(serial, "pm", "list", "packages", package_name, timeout=15)
    return f"package:{package_name}" in output


# Keyremap_Method_Sophy_H400818_2026-09-02
def keyremap_install_app(serial, apk_path, package_name):
    """Install an APK from the host and verify the package shows up on the device.

    Args: serial is the target device serial number; apk_path is the local APK path;
          package_name is the expected package name used for verification.
    Returns: (is_installed, message). message carries the adb output when the install fails.
    Precondition: `-r` reinstalls over an existing copy and `-g` pre-grants runtime permissions,
            so the test does not have to dismiss permission dialogs later.
    """
    if not os.path.isfile(apk_path):
        return False, f"APK not found: {apk_path}"

    import threading

    result_holder = {}

    def _run_install():
        result_holder["ret"] = adb_command(serial, "install", "-r", "-g", apk_path, timeout=180)

    install_thread = threading.Thread(target=_run_install, daemon=True)
    install_thread.start()
    install_thread.join(timeout=5)

    ret = result_holder.get("ret")
    output = f"{(ret.stdout or '').strip()} {(ret.stderr or '').strip()}".strip() if ret else "install did not complete"
    if not keyremap_is_app_installed(serial, package_name):
        return False, output or "install failed"
    return True, output


# Keyremap_Method_Sophy_H400818_2026-09-02
def keyremap_uninstall_app(serial, package_name):
    """Uninstall a package so the next run starts from a clean device.







    Args: serial is the target device serial number; package_name is the package to remove.
    Returns: True when the package is gone after the command, otherwise False.
    Precondition: none.
    """
    adb_command(serial, "uninstall", package_name, timeout=60)
    return not keyremap_is_app_installed(serial, package_name)


# Keyremap_Method_Sophy_H400818_2026-09-02
def keyremap_wait_app_foreground(serial, package_name, timeout=10):
    """Poll window and activity state until the given package is foregrounded.

    Args: serial is the target device serial number; package_name is the expected foreground package;
          timeout is the max polling duration in seconds.
    Returns: (is_foreground, most recent focused window info).
    Precondition: used to confirm the remapped key actually launched the mapped app.
    """
    deadline = time.time() + timeout
    last_focus = ""

    while time.time() < deadline:
        signals = []

        window_output = run_adb_cmd(serial, "shell dumpsys window", log_print=False)
        window_text = (
            window_output.decode("utf-8", errors="ignore")
            if isinstance(window_output, bytes)
            else str(window_output)
        )
        for line in window_text.splitlines():
            if "mCurrentFocus" in line or "mFocusedApp" in line:
                signals.append(line.strip())
                if "mCurrentFocus" in line:
                    last_focus = line.strip()

        activity_output = run_adb_cmd(serial, "shell dumpsys activity activities", log_print=False)
        activity_text = (
            activity_output.decode("utf-8", errors="ignore")
            if isinstance(activity_output, bytes)
            else str(activity_output)
        )
        for line in activity_text.splitlines():
            if "mResumedActivity" in line or "topResumedActivity" in line:
                signals.append(line.strip())

        if package_name.lower() in " ".join(signals).lower():
            return True, last_focus or (signals[0] if signals else "")
        time.sleep(1)

    return False, last_focus

#package_is_installed_Peter_20260917
def package_is_installed(serial, package_name, timeout=15):
    """Return whether an Android package is installed on the device."""
    result = adb_shell(serial, "pm", "path", package_name, timeout=timeout)
    return result.returncode == 0 and bool((result.stdout or "").strip())

#wait_for_package_state_Peter_20260917
def wait_for_package_state(serial, package_name, should_be_installed, timeout=60):
    """Wait until an Android package reaches the requested installed state."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        if package_is_installed(serial, package_name) == should_be_installed:
            return True
        time.sleep(1)
    return False

#push_device_file_Peter_20260917
def push_device_file(serial, local_path, remote_path, timeout=60):
    """Push a local file to an Android device and return the ADB result."""
    return adb_command(serial, "push", local_path, remote_path, timeout=timeout)

#remove_device_file_Peter_20260917
def remove_device_file(serial, remote_path, timeout=30):
    """Remove a device file and return whether it is absent afterward."""
    removed = adb_shell(serial, "rm", "-f", remote_path, timeout=timeout)
    if removed.returncode != 0:
        return False
    absent = adb_shell(serial, "test", "!", "-e", remote_path, timeout=15)
    return absent.returncode == 0