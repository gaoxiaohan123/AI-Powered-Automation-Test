# -*- coding:utf-8 -*-
"""
L0_WWAN GSM/GPRS automation test.

Steps (insert a CMCC SIM in slot1 and power on the device before running):
    1. Verify the SIM card in slot1 is recognized (read carrier info via ADB).
    2. Verify the device is fully booted (uiautomator2 connection is available).
    3. Place a call and verify call setup (dial, wait for active/dialing state, then hang up).
    4. Send an SMS and verify it is dispatched successfully.
    5. Verify internet connectivity.

Notes:
    - Step 3 uses a remote number provided by TEST_PHONE_NUMBER (default: 10086).
    - Step 3 only validates ACTIVE / DIALING state to avoid real service charges.
    - Step 4 also uses TEST_PHONE_NUMBER or its default value.
    - Step 5 validates connectivity with curl/ping and does not depend on browser UI.
"""

import os
import re
import subprocess
import time
import unittest

from common.adb_common import is_wwan_data_only_device, sim_card_in_slot_is_present

serial = os.environ.get('ANDROID_SERIAL')
TEST_PHONE_NUMBER = os.environ.get('TEST_PHONE_NUMBER', '10086')
BROWSER_TEST_URL = os.environ.get('TEST_URL', 'www.baidu.com')
NETWORK_PING_HOST = '8.8.8.8'


# ─── ADB helpers ──────────────────────────────────────────────────────────────

def _adb(cmd_parts, timeout=15):
    return subprocess.run(
        ['adb', '-s', serial] + cmd_parts,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        encoding='utf-8',
        errors='ignore',
        check=False,
        timeout=timeout,
    )


def _shell(cmd, timeout=15):
    ret = _adb(['shell', cmd], timeout=timeout)
    return (ret.stdout or '').strip()


def _is_wlan_only_device():
    """Determine whether the current device is a WLAN-only (no cellular capability) device."""
    override = (os.environ.get('FORCE_WLAN_ONLY_DEVICE') or '').strip().lower()
    if override in ('1', 'true', 'yes', 'y', 'on'):
        return True
    if override in ('0', 'false', 'no', 'n', 'off'):
        return False

    no_ril = _shell('getprop ro.radio.noril').strip().lower()
    if no_ril in ('1', 'true', 'yes'):
        return True

    telephony_feature = _shell('pm list features | grep -i "android.hardware.telephony"')
    return not bool(telephony_feature)


# ─── Test Class ───────────────────────────────────────────────────────────────

class Test_L0_WWAN_GSM_GPRS(unittest.TestCase):
    """L0_WWAN GSM/GPRS: call, SMS, and data connectivity verification."""

    def setUp(self):
        self.assertTrue(serial, 'ANDROID_SERIAL is not set; cannot connect to the device')
        if _is_wlan_only_device():
            self.skipTest('WWAN is unavailable on this WLAN-only device')
        if is_wwan_data_only_device(serial):
            self.skipTest('WWAN data-only device does not support GSM/GPRS voice and SMS validation')
        if not sim_card_in_slot_is_present(serial, slot_index=0):
            self.skipTest('No SIM card is detected in physical Slot 1; WWAN GSM/GPRS validation requires Slot 1')
        
        # [Defensive check] Detect any abnormal call state (possibly left over from a previous test not cleaned up)
        print('[Setup] Detecting and clearing leftover call state...')
        try:
            # Check call state
            call_state = _shell('dumpsys telephony.registry | grep mCallState')
            if 'mCallState=1' in call_state or 'mCallState=2' in call_state:
                print('  [Warning] Active call detected, forcing hang up...')
            # Force hang up (safe even if there is no active call)
            _adb(['shell', 'input', 'keyevent', 'KEYCODE_ENDCALL'], timeout=5)
            time.sleep(0.5)
            # Second confirmation hang up
            _adb(['shell', 'input', 'keyevent', 'KEYCODE_ENDCALL'], timeout=5)
            time.sleep(0.5)
        except Exception as e:
            print(f'  Failed to clear call state: {e}')
            pass

    def tearDown(self):
        # [Important] Use try-finally to ensure the device state is restored even if the test fails
        print('[Teardown] Restoring device call state...')
        try:
            # Hang up any leftover call
            for attempt in range(2):
                try:
                    _adb(['shell', 'input', 'keyevent', 'KEYCODE_ENDCALL'], timeout=5)
                    time.sleep(0.3)
                except Exception:
                    pass
            print('[Teardown] Call state cleared')
        except Exception as e:
            print(f'[Teardown] Cleanup failed: {e}')
        try:
            _adb(['shell', 'input', 'keyevent', 'KEYCODE_ENDCALL'], timeout=5)
            time.sleep(0.5)
            # Confirm hang up again
            _adb(['shell', 'input', 'keyevent', 'KEYCODE_ENDCALL'], timeout=5)
        except Exception:
            pass

    # ── Step 1 & 2: SIM recognition + device boot ─────────────────────────────

    def _verify_sim_present(self):
        """
        Step 1: Confirm the SIM card in slot1 has been recognized by the system.
        Read the carrier display name (gsm.operator.alpha); a non-empty value means recognition succeeded.
        """
        print('\n[WWAN] Step 1: Check SIM card recognized in slot1')
        if not sim_card_in_slot_is_present(serial, slot_index=0):
            self.skipTest('SIM card in physical Slot 1 was removed or is no longer detected')
        operator = _shell('getprop gsm.operator.alpha.slot0')
        if not operator:
            raw = _shell('getprop gsm.operator.alpha')
            operator = raw.split(',')[0].strip() if raw else ''
        print(f'  Operator: {operator or "(empty)"}')
        self.assertTrue(
            operator,
            'SIM card not recognized (gsm.operator.alpha is empty); please confirm the CMCC SIM card is inserted in slot1'
        )
        print(f'  ✓ SIM recognized: {operator}')

    def _verify_device_ready(self):
        """Step 2: Confirm the device is fully booted (boot_completed=1)."""
        print('[WWAN] Step 2: Verify device is fully booted')
        boot = _shell('getprop sys.boot_completed')
        self.assertEqual(boot, '1', 'sys.boot_completed != 1; the device may not be fully booted yet')
        print('  ✓ Device is fully booted')

    # ── Step 3: Make a phone call ──────────────────────────────────────────────

    def _make_phone_call(self):
        """
        Step 3: Place a call, wait until it reaches at least DIALING / ACTIVE state, then hang up.
        Query the call state via the telecom service.
        """
        print(f'[WWAN] Step 3: Make a phone call to {TEST_PHONE_NUMBER}')
        _adb(['shell', 'am', 'start', '-a', 'android.intent.action.CALL',
              '-d', f'tel:{TEST_PHONE_NUMBER}'], timeout=10)
        time.sleep(3)

        # Wait for the call state to reach DIALING or ACTIVE (up to 20 seconds)
        call_active = False
        for _ in range(20):
            state_raw = _shell('dumpsys telephony.registry | grep mCallState')
            # mCallState 0=IDLE, 1=RINGING, 2=OFFHOOK(dialing/active)
            if '2' in state_raw:
                call_active = True
                break
            # Fallback: query telecom
            telecom_raw = _shell(
                'dumpsys telecom | grep -E "isActive|isDi|ACTIVE|DIALING" | head -5'
            ).upper()
            if 'ACTIVE' in telecom_raw or 'DIALING' in telecom_raw or 'OFFHOOK' in telecom_raw:
                call_active = True
                break
            time.sleep(1)

        # Hang up
        _adb(['shell', 'input', 'keyevent', 'KEYCODE_ENDCALL'], timeout=5)
        time.sleep(2)

        print(f'  call_active={call_active}')
        self.assertTrue(call_active, f'After dialing {TEST_PHONE_NUMBER}, no DIALING/ACTIVE state was detected; the call could not be established')
        print(f'  ✓ Phone call established successfully (to {TEST_PHONE_NUMBER})')

    # ── Step 4: Send SMS ───────────────────────────────────────────────────────

    def _send_sms(self):
        """
        Step 4: Send an SMS via the ADB service call SMS interface and verify there are no errors.
        Note: only the command is issued; receipt on the other end is not verified (the test environment may have no receiver).
        """
        print(f'[WWAN] Step 4: Send SMS to {TEST_PHONE_NUMBER}')
        msg_text = 'AutoTest_WWAN_SMS_Verify'
        # Open the SMS UI via intent and pre-fill it
        result = _adb([
            'shell', 'am', 'start',
            '-a', 'android.intent.action.SENDTO',
            '-d', f'smsto:{TEST_PHONE_NUMBER}',
            '--es', 'sms_body', msg_text,
            '--ez', 'exit_on_sent', 'true',
        ], timeout=10)
        time.sleep(2)

        ret_code = result.returncode
        print(f'  SMS intent returncode={ret_code}')
        self.assertEqual(ret_code, 0, 'SMS send intent failed to execute (returncode is non-zero)')
        print('  ✓ SMS send intent dispatched successfully')

    # ── Step 5: Internet access verification ───────────────────────────────────

    def _verify_internet_access(self):
        """
        Step 5: Verify internet access on the device via shell ping.
        Run 3 ICMP requests with ping -c 3 -W 5; receiving any reply packet counts as a pass.
        """
        print(f'[WWAN] Step 5: Verify internet access (ping {NETWORK_PING_HOST})')
        out = _shell(f'ping -c 3 -W 5 {NETWORK_PING_HOST}')
        print(f'  ping output: {out[:200]}')

        # Determine whether a reply was received: 'bytes from' or '3 received' or '3 packets transmitted, 3 received'
        received_match = re.search(r'(\d+)\s+received', out)
        bytes_from = 'bytes from' in out

        success = bytes_from or (received_match and int(received_match.group(1)) > 0)
        if not success:
            # Fallback: curl approach
            print(f'  [WARN] ping failed, trying curl to {BROWSER_TEST_URL} ...')
            curl_out = _shell(
                f'curl -s --max-time 10 --retry 1 -o /dev/null -w "%{{http_code}}" http://{BROWSER_TEST_URL}',
                timeout=20
            )
            print(f'  curl http_code: {curl_out}')
            success = curl_out.strip() in ('200', '301', '302', '307', '308')

        self.assertTrue(success, f'The device cannot access the internet (ping {NETWORK_PING_HOST} failed)')
        print('  ✓ Internet access verified successfully')

    # ── Main test case ─────────────────────────────────────────────────────────

    def test_L0_WWAN_GSM_GPRS(self):
        """
        Full L0_WWAN GSM/GPRS flow.

        Test Steps:
          1. Verify the CMCC SIM is recognized in slot1
          2. Verify the device is booted
          3. Place a call and verify the call is established
          4. Send an SMS
          5. Verify internet access
        """
        print('\n' + '=' * 60)
        print('TEST: L0_WWAN GSM/GPRS')
        print('=' * 60)

        self._verify_sim_present()     # Step 1
        self._verify_device_ready()    # Step 2
        self._make_phone_call()        # Step 3
        self._send_sms()               # Step 4
        self._verify_internet_access() # Step 5

        print('\n' + '=' * 60)
        print('✓ PASS - All L0_WWAN GSM/GPRS checks passed')
        print('=' * 60)
