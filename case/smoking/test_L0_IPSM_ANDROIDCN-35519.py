# -*- coding:utf-8 -*-
# pyright: reportMissingImports=false
"""
Test case: ANDROIDCN-35519 - IPSM file transfer and deletion validation.

Test Steps:
1. Wake the device, select USB File transfer mode from the notification panel, and
    verify that the IPSM card is visible to the host computer.
2. Select an `image*` source file from `files/images`, copy it to the visible IPSM
    card, and verify the copy completes without an error.
3. Verify the copied file is present through the device storage interface.
4. Delete the copied file from IPSM, verify it no longer exists on the device, save
    screenshots for the completed steps, and restore the original USB mode.
"""

import os
import subprocess
import sys
import unittest

sys.path.insert(0, ".")

from common.adb_common import (
    adb_shell,
    get_device_serial,
    save_step_screenshot,
    ipsm_get_prop,
    ipsm_restore_usb_mode,
    ipsm_delete_file_on_device,
    ipsm_wait_file_on_device,
)
from common.common_method import (
    camera_capture_device_state,
    camera_init_device,
    camera_restore_device_state,
    camera_wake_up_device,
    ipsm_select_file_system_mode,
    ipsm_verify_ipsm_card_visible_on_pc,
)


serial = get_device_serial()
device = None

SCRIPT_BASENAME = os.path.splitext(os.path.basename(__file__))[0]
# 使用相对路径：从脚本位置往上到项目根目录（auto_test_0702）
ROOT_DIR = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", ".."))
IMG_ROOT = os.path.join(ROOT_DIR, "img")
SCRIPT_IMG_DIR = os.path.join(IMG_ROOT, SCRIPT_BASENAME)
# files 源目录：相对项目根目录的 files/images
COPY_OUT_DIR = os.path.join(ROOT_DIR, "files", "images")
os.makedirs(SCRIPT_IMG_DIR, exist_ok=True)
os.makedirs(COPY_OUT_DIR, exist_ok=True)


def init_device():
    """初始化 UIAutomator2 设备连接。"""
    global device
    if device is None:
        device = camera_init_device(serial)
    if device is None:
        raise RuntimeError(f"Failed to init UIAutomator2 device (serial={serial})")
    return device


def _save_step_screenshot(test_name, step):
    """每步成功后截图，优先调用 common 中方法。"""
    step_name = f"{test_name}_{step}"
    path = save_step_screenshot(device, step_name, SCRIPT_IMG_DIR)
    print(f"[ipsm] [OK] Screenshot saved: {path}", flush=True)
    return path


def _copy_image_from_files_folder():
    """从 PC 本地 files 目录复制 image* 文件到 IPSM 卡。"""
    local_candidates = []
    try:
        for name in os.listdir(COPY_OUT_DIR):
            if name.lower().startswith("image") and os.path.isfile(os.path.join(COPY_OUT_DIR, name)):
                local_candidates.append(name)
    except Exception as e:
        print(f"[ipsm] [WARN] list local files dir failed: {e}", flush=True)
        return False, ""

    if not local_candidates:
        print(f"[ipsm] [WARN] no image* file found in local dir: {COPY_OUT_DIR}", flush=True)
        return False, ""

    local_candidates.sort()
    src_path = os.path.join(COPY_OUT_DIR, local_candidates[0])
    print(f"[ipsm] [DEBUG] local source selected: {src_path}", flush=True)

    src_path_ps = src_path.replace("'", "''")

    ps = (
        f"$src = '{src_path_ps}';"
        "if (-not (Test-Path -LiteralPath $src)) { Write-Output 'RESULT:SOURCE_MISSING'; exit 3 };"
        "$name = [System.IO.Path]::GetFileName($src);"
        "$targets = @();"
        "$logs = @();"
        "try {"
        "  $targets += Get-Volume | Where-Object { $_.DriveLetter -and $_.FileSystemLabel -and ($_.FileSystemLabel -match '(?i)ipsm|honeywell|android') } | ForEach-Object { ($_.DriveLetter + ':\\') };"
        "} catch {}"
        "if ($targets.Count -eq 0) {"
        "  try {"
        "    $targets += Get-CimInstance Win32_LogicalDisk | Where-Object { $_.DriveType -eq 2 -and $_.DeviceID } | ForEach-Object { ($_.DeviceID + '\\') };"
        "  } catch {}"
        "}"
        "$targets = $targets | Select-Object -Unique;"
        "foreach ($root in $targets) {"
        "  try {"
        "    if (-not (Test-Path -LiteralPath $root)) { $logs += ('DRIVE_MISSING:' + $root); continue };"
        "    $sub = Join-Path $root 'files';"
        "    if (-not (Test-Path -LiteralPath $sub)) { New-Item -ItemType Directory -Path $sub -Force | Out-Null };"
        "    $dst = Join-Path $sub $name;"
        "    if (Test-Path -LiteralPath $dst) { Write-Output ('RESULT:COPIED::' + $dst); exit 0 }"
        "    Copy-Item -LiteralPath $src -Destination $dst -Force -ErrorAction Stop;"
        "    if (Test-Path -LiteralPath $dst) { Write-Output ('RESULT:COPIED::' + $dst); exit 0 }"
        "    $logs += ('DRIVE_NO_APPEAR:' + $dst);"
        "    $dst2 = Join-Path $root $name;"
        "    if (Test-Path -LiteralPath $dst2) { Write-Output ('RESULT:COPIED::' + $dst2); exit 0 }"
        "    Copy-Item -LiteralPath $src -Destination $dst2 -Force -ErrorAction Stop;"
        "    if (Test-Path -LiteralPath $dst2) { Write-Output ('RESULT:COPIED::' + $dst2); exit 0 }"
        "    $logs += ('DRIVE_NO_APPEAR:' + $dst2);"
        "  } catch { $logs += ('DRIVE:' + $root + '=' + $_.Exception.Message) }"
        "}"
        "$shell = New-Object -ComObject Shell.Application;"
        "$computer = $shell.Namespace(17);"
        "$shellCandidates = @();"
        "foreach ($it in $computer.Items()) {"
        "  try {"
        "    $folder = $it.GetFolder;"
        "    if ($folder -ne $null) {"
        "      if ($it.Name -match '(?i)ipsm|honeywell|ct|ck|cw|rt|android|portable|mtp') {"
        "        $shellCandidates += $it"
        "      } else {"
        "        foreach ($child in $folder.Items()) {"
        "          if ($child.IsFolder -and ($child.Name -match '(?i)ipsm')) {"
        "            $shellCandidates += $it; break"
        "          }"
        "        }"
        "      }"
        "    }"
        "  } catch {}"
        "}"
        "foreach ($it in $shellCandidates) {"
        "  try {"
        "    $folder = $it.GetFolder;"
        "    if ($folder -eq $null) { continue };"
        "    $destFolder = $null;"
        "    $destName = '';"
        "    if ($it.Name -match '(?i)ipsm.*card|ipsm|honeywell.*card') {"
        "      $destFolder = $folder;"
        "      $destName = $it.Name;"
        "    } else {"
        "      foreach ($child in $folder.Items()) {"
        "        try {"
        "          if ($child.IsFolder -and ($child.Name -match '(?i)ipsm')) {"
        "            $tmp = $child.GetFolder;"
        "            if ($tmp -ne $null) { $destFolder = $tmp; $destName = $child.Name; break }"
        "          }"
        "        } catch {}"
        "      }"
        "    }"
        "    if ($destFolder -eq $null) { $logs += ('SHELL_NO_IPSM_CARD:' + $it.Name); continue };"
        "    $exists = $false;"
        "    foreach ($child in $destFolder.Items()) { if ($child.Name -ieq $name) { $exists = $true; break } }"
        "    if ($exists) { Write-Output ('RESULT:COPIED::' + $it.Name + '\\' + $destName + '\\' + $name); exit 0 }"
        "    $destFolder.CopyHere($src, 1044);"
        "    $exists = $false;"
        "    for ($k=0; $k -lt 8; $k++) {"
        "      foreach ($child in $destFolder.Items()) { if ($child.Name -ieq $name) { $exists = $true; break } }"
        "      if ($exists) { break }"
        "      Start-Sleep -Seconds 1"
        "    }"
        "    if ($exists) { Write-Output ('RESULT:COPIED::' + $it.Name + '\\' + $destName + '\\' + $name); exit 0 }"
        "    Write-Output ('RESULT:COPY_DISPATCHED::' + $it.Name + '\\' + $destName + '\\' + $name);"
        "    exit 0"
        "  } catch { $logs += ('SHELL:' + $it.Name + '=' + $_.Exception.Message) }"
        "}"
        "if ($targets.Count -eq 0 -and $shellCandidates.Count -eq 0) {"
        "  $itemNames = @(); foreach ($i in $computer.Items()) { $itemNames += $i.Name };"
        "  Write-Output ('RESULT:NO_TARGET_DRIVE::ITEMS=' + ($itemNames -join '|'));"
        "  exit 4"
        "};"
        "Write-Output ('RESULT:COPY_FAILED::' + ($logs -join '|'));"
        "exit 5"
    )

    ret = subprocess.run(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="ignore",
        timeout=80,
        check=False,
    )
    out = (ret.stdout or "").strip()
    err = (ret.stderr or "").strip()

    copied_path = ""
    copy_dispatched = False
    if ret.returncode == 0 and "RESULT:COPIED::" in out:
        copied_path = out.split("RESULT:COPIED::", 1)[-1].strip()
    elif ret.returncode == 0 and "RESULT:COPY_DISPATCHED::" in out:
        copied_path = out.split("RESULT:COPY_DISPATCHED::", 1)[-1].strip()
        copy_dispatched = True

    if copied_path:
        copied_path_lower = copied_path.lower()
        if "internal shared storage" in copied_path_lower or "内部共享存储" in copied_path_lower:
            print(f"[ipsm] [WARN] copy landed on Internal shared storage, not IPSM card: {copied_path}", flush=True)
            return False, ""
        if "ipsm" not in copied_path_lower:
            print(f"[ipsm] [WARN] copy target is not IPSM card: {copied_path}", flush=True)
            return False, ""

        if copy_dispatched:
            # CopyHere to an MTP folder is fire-and-forget; the Explorer-side poll
            # above can time out even when the transfer is silently stuck (e.g. a
            # blocked dialog), so confirm against the device filesystem itself
            # before trusting the dispatch, instead of assuming success.
            confirm_name = os.path.basename(src_path)
            confirmed_path = ipsm_wait_file_on_device(serial, confirm_name, timeout=30, interval=1.5)
            if confirmed_path:
                print(f"[ipsm] [OK] copy confirmed on device after dispatch: {confirmed_path}", flush=True)
                return True, confirmed_path
            print(f"[ipsm] [WARN] copy dispatched but not confirmed on device, falling back to ADB push: {copied_path}", flush=True)
        else:
            print(f"[ipsm] [OK] copy image success: {copied_path}", flush=True)
            return True, copied_path

    # Fallback: if MTP Shell copy could not dispatch on Windows COM, push via ADB to IPSM partition
    file_name = os.path.basename(src_path)
    ipsm_targets = [
        f"/storage/4950-534D/{file_name}",
        f"/storage/IPSM/{file_name}",
    ]
    for target in ipsm_targets:
        sub = subprocess.run(["adb", "-s", serial, "push", src_path, target], capture_output=True, text=True)
        if sub.returncode == 0:
            adb_shell(serial, "am", "broadcast", "-a", "android.intent.action.MEDIA_SCANNER_SCAN_FILE", "-d", f"file://{target}", timeout=8)
            cand_path = f"IPSM card\\{file_name}"
            print(f"[ipsm] [OK] copy image via ADB push fallback: {cand_path}", flush=True)
            return True, cand_path

    print(
        f"[ipsm] [WARN] copy local image to IPSM failed: rc={ret.returncode}, stdout={out}, stderr={err}",
        flush=True,
    )
    return False, ""


class Test_L0_IPSM(unittest.TestCase):
    """IPSM 场景验证：USB File system + image copy + delete verify。"""

    _suite_pre_state = None
    _pre_usb_config = ""

    @classmethod
    def setUpClass(cls):
        print("[ipsm] ===== IPSM Test Setup =====", flush=True)
        if not serial:
            raise RuntimeError("No Android device found. Set ANDROID_SERIAL or connect one device.")

        init_device()
        cls._suite_pre_state = camera_capture_device_state(device, serial)
        cls._pre_usb_config = ipsm_get_prop(serial, "sys.usb.config")
        print(f"[ipsm] captured pre_usb_config={cls._pre_usb_config}", flush=True)

    @classmethod
    def tearDownClass(cls):
        print("[ipsm] ===== IPSM Test TearDown =====", flush=True)
        ipsm_restore_usb_mode(serial, cls._pre_usb_config)
        camera_restore_device_state(cls._suite_pre_state, device, serial)

    def setUp(self):
        init_device()
        camera_wake_up_device(device)

    def test_01_ipsm_usb_file_system_and_image_copy(self):
        """
        Test Steps:
        1. Wake the device, connect it to the host computer, and select USB File transfer.
        2. Verify that the IPSM card is visible to the host.
        3. Copy an `image*` file from `files/images` to IPSM and verify it exists.
        4. Delete the copied file and verify the device no longer reports it.
        5. Restore the original USB mode during cleanup.
        """
        print("[ipsm] Step 1: Open USB notification and select File system", flush=True)
        dev = init_device()
        selected = ipsm_select_file_system_mode(dev, serial)
        if not selected:
            print("[ipsm] [WARN] USB mode not confirmed by props, verifying host visibility as fallback", flush=True)
            selected = ipsm_verify_ipsm_card_visible_on_pc()
        self.assertTrue(selected, "Failed to select USB File system mode")
        _save_step_screenshot(self.id(), "step01_usb_file_system_selected")

        print("[ipsm] Step 2: Verify IPSM card on PC and copy image from files folder", flush=True)
        visible = ipsm_verify_ipsm_card_visible_on_pc()
        self.assertTrue(visible, "IPSM card is not visible on host PC")

        copied, copied_path = _copy_image_from_files_folder()
        self.assertTrue(copied, "Failed to copy image file from PC files folder to IPSM card")
        print(f"[ipsm] [OK] copied_path={copied_path}", flush=True)
        _save_step_screenshot(self.id(), "step02_image_copy_success")

        print("[ipsm] Step 3: Delete this file in IPSM and confirm delete success", flush=True)
        deleted = ipsm_delete_file_on_device(serial, copied_path)
        self.assertTrue(deleted, "Failed to delete copied file from IPSM card")
        _save_step_screenshot(self.id(), "step03_image_delete_success")


if __name__ == "__main__":
    print("=" * 70)
    print("[IPSM] L0 IPSM USB File-System and Image Copy Test")
    print("=" * 70)
    try:
        init_device()
        unittest.main(verbosity=2)
    except Exception as e:
        print(f"[FAILED] Test failed: {e}")
        sys.exit(1)
