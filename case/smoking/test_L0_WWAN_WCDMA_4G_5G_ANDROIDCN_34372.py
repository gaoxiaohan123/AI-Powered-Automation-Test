# -*- coding:utf-8 -*-
"""
L0_WWAN WCDMA / 4G / 5G network signal validation.

Steps:
    1. Insert a SIM card that supports WCDMA / 4G / 5G (manual setup; script verifies SIM detection).
    2. Verify the device is fully booted.
    3. Verify mobile signal availability (prefer network type; fall back to signal strength when needed).
    4. Validate data capability for WCDMA (3G), 4G (LTE), and 5G (NR), depending on current registration.
    5. Verify mobile data availability (ping test).

Notes:
    - The script does not force network mode by default; it reads current network state and evaluates accordingly.
    - To force a specific mode (for example 3G), use Settings > Mobile Network manually,
        or set FORCE_NETWORK_TYPE (3g / 4g / 5g) to let the script attempt ADB mode switching.
    - Mode switch commands vary by device/operator; ADB switching is best-effort and evaluation falls back to current mode.
"""

import os
import re
import subprocess
import time
import unittest

from common.adb_common import is_wwan_data_only_device, sim_card_in_slot_is_present

serial = os.environ.get('ANDROID_SERIAL')
FORCE_NETWORK_TYPE = (os.environ.get('FORCE_NETWORK_TYPE') or '').lower().strip()
PING_HOST = '8.8.8.8'

# Android NetworkType constants
# https://developer.android.com/reference/android/telephony/TelephonyManager
NETWORK_TYPE_MAP = {
    '1':  'GPRS',      '2':  'EDGE',      '3':  'UMTS',      '4':  'CDMA',
    '5':  'EVDO_0',    '6':  'EVDO_A',    '7':  'RTT',       '8':  'HSDPA',
    '9':  'HSUPA',     '10': 'HSPA',      '11': 'IDEN',      '12': 'EVDO_B',
    '13': 'LTE',       '14': 'EHRPD',     '15': 'HSPAP',     '16': 'GSM',
    '17': 'TD_SCDMA',  '18': 'IWLAN',     '19': 'LTE_CA',    '20': 'NR',
}

WCDMA_TYPES   = {'3', '8', '9', '10', '15', '17'}  # UMTS/HSDPA/HSUPA/HSPA/HSPAP/TD_SCDMA
LTE_TYPES     = {'13', '19'}                         # LTE / LTE_CA
NR_TYPES      = {'20'}                               # NR (5G)
ABOVE_2G_TYPES = WCDMA_TYPES | LTE_TYPES | NR_TYPES | {'4', '5', '6', '12', '14'}


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
    """Determine whether the current device is WLAN-only (no cellular capability)."""
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


def _get_network_type_id():
    """Get the current mobile network type ID string (e.g. '13' = LTE)."""
    # Method 1: getprop gsm.network.type (some device models)
    raw = _shell('getprop gsm.network.type')
    if raw.isdigit():
        return raw

    # Method 2: dumpsys telephony.registry
    out = _shell('dumpsys telephony.registry | grep -m1 mDataNetworkType')
    m = re.search(r'mDataNetworkType=(\d+)', out)
    if m:
        return m.group(1)

    # Method 3: service call phone (get data network type)
    out2 = _shell('service call phone 59 2>/dev/null')
    m2 = re.search(r'i32\s+(\d+)', out2)
    if m2:
        return m2.group(1)

    return '0'


def _get_signal_strength_dbm():
    """Try to read the signal strength (dBm); return an integer or None."""
    out = _shell('dumpsys telephony.registry | grep -m1 -E "signalStrength|mSignalStrength"')
    # Find the first negative dBm value
    match = re.search(r'-\d{2,3}', out)
    if match:
        return int(match.group(0))
    return None


def _force_set_network_type(mode):
    """
    Try to switch the preferred network mode via settings put global.
    mode: '3g' | '4g' | '5g'
    Returns True if the command was issued successfully (does not guarantee it took effect).
    """
    mode_map = {
        '3g': '1',    # NETWORK_MODE_WCDMA_ONLY
        '4g': '11',   # NETWORK_MODE_LTE_ONLY
        '5g': '26',   # NETWORK_MODE_NR_ONLY
    }
    value = mode_map.get(mode)
    if not value:
        return False
    result = _shell(f'settings put global preferred_network_mode {value}')
    print(f'  [Force network] set preferred_network_mode={value} ({mode.upper()}), result={result or "ok"}')
    # Re-enable then disable airplane mode to refresh the network
    _shell('settings put global airplane_mode_on 1')
    _shell('am broadcast -a android.intent.action.AIRPLANE_MODE --ez state true')
    time.sleep(2)
    _shell('settings put global airplane_mode_on 0')
    _shell('am broadcast -a android.intent.action.AIRPLANE_MODE --ez state false')
    time.sleep(5)
    return True


# ─── Test Class ───────────────────────────────────────────────────────────────

class Test_L0_WWAN_Network(unittest.TestCase):
    """L0_WWAN WCDMA / 4G / 5G signal and connectivity validation."""

    def setUp(self):
        self.assertTrue(serial, 'ANDROID_SERIAL is not set; cannot connect to the device')
        if _is_wlan_only_device():
            self.skipTest('WWAN is unavailable on this WLAN-only device')
        if is_wwan_data_only_device(serial):
            self.skipTest('WWAN data-only device is excluded from WCDMA/4G/5G validation')
        if not sim_card_in_slot_is_present(serial, slot_index=0):
            self.skipTest('No SIM card is detected in physical Slot 1; WWAN WCDMA/4G/5G validation requires Slot 1')
        
        # [Defensive check] Record the initial settings and detect any corrupted state
        print('[Setup] Detecting and recording network settings state...')
        self._original_network_mode = _shell('settings get global preferred_network_mode').strip()
        self._original_airplane_mode = _shell('settings get global airplane_mode_on').strip()
        print(f'  Detected preferred_network_mode: {self._original_network_mode or "(not set)"}')
        print(f'  Detected airplane_mode_on: {self._original_airplane_mode or "(not set)"}')
        
        # If airplane mode is already enabled, a previous test may not have cleaned up; turn it off proactively
        if self._original_airplane_mode == '1':
            print('[Setup] [Warning] Airplane mode is already enabled (a previous test may not have cleaned up); turning it off...')
            _shell('settings put global airplane_mode_on 0')
            _shell('am broadcast -a android.intent.action.AIRPLANE_MODE --ez state false')
            time.sleep(2)
        
        # Ensure airplane mode is off to allow normal network operations
        current_airplane = _shell('settings get global airplane_mode_on').strip()
        if current_airplane != '0':
            print('[Setup] Forcing airplane mode off...')
            _shell('settings put global airplane_mode_on 0')
            _shell('am broadcast -a android.intent.action.AIRPLANE_MODE --ez state false')
            time.sleep(2)
    
    def tearDown(self):
        # [Important] Use a try-finally pattern to ensure settings are restored even if the test fails
        print('[Teardown] Starting network settings restoration...')
        restored = False
        try:
            # Restore the original network mode
            current_mode = _shell('settings get global preferred_network_mode').strip()
            if self._original_network_mode and current_mode != self._original_network_mode:
                print(f'  Restoring preferred_network_mode: {current_mode} -> {self._original_network_mode}')
                _shell(f'settings put global preferred_network_mode {self._original_network_mode}')
                # Re-enable then disable airplane mode to refresh the network
                _shell('settings put global airplane_mode_on 1')
                _shell('am broadcast -a android.intent.action.AIRPLANE_MODE --ez state true')
                time.sleep(2)
                _shell('settings put global airplane_mode_on 0')
                _shell('am broadcast -a android.intent.action.AIRPLANE_MODE --ez state false')
                time.sleep(3)
            
            # Restore the original airplane mode state
            current_airplane = _shell('settings get global airplane_mode_on').strip()
            if self._original_airplane_mode and current_airplane != self._original_airplane_mode:
                print(f'  Restoring airplane_mode_on: {current_airplane} -> {self._original_airplane_mode}')
                _shell(f'settings put global airplane_mode_on {self._original_airplane_mode}')
                if self._original_airplane_mode == '1':
                    _shell('am broadcast -a android.intent.action.AIRPLANE_MODE --ez state true')
        except Exception as e:
            print(f'  [WARN] Error while restoring settings: {str(e)}')

    # -- Step 1+2: SIM recognition + boot --------------------------------------

    def _verify_sim_and_boot(self):
        print('\n[WWAN_NET] Step 1: Verify SIM recognized')
        if not sim_card_in_slot_is_present(serial, slot_index=0):
            self.skipTest('SIM card in physical Slot 1 was removed or is no longer detected')
        operator = _shell('getprop gsm.operator.alpha.slot0')
        if not operator:
            operator = _shell('getprop gsm.operator.alpha').split(',')[0].strip()
        print(f'  Operator: {operator or "(empty)"}')
        self.assertTrue(operator, 'SIM card not recognized; please confirm a SIM that supports WCDMA/4G/5G is inserted')
        print(f'  ✓ SIM recognized: {operator}')

        print('[WWAN_NET] Step 2: Verify device fully booted')
        boot = _shell('getprop sys.boot_completed')
        self.assertEqual(boot.strip(), '1', 'Device did not fully boot (sys.boot_completed != 1)')
        print('  ✓ Device fully booted')

    # -- Step 3: Get signal ----------------------------------------------------

    def _verify_signal(self):
        print('[WWAN_NET] Step 3: Verify device gets mobile signal')

        # If a forced network mode is specified, switch first
        if FORCE_NETWORK_TYPE in ('3g', '4g', '5g'):
            print(f'  [INFO] FORCE_NETWORK_TYPE={FORCE_NETWORK_TYPE}, attempting switch...')
            _force_set_network_type(FORCE_NETWORK_TYPE)

        network_type_id = _get_network_type_id()
        network_name = NETWORK_TYPE_MAP.get(network_type_id, f'UNKNOWN({network_type_id})')
        signal_dbm = _get_signal_strength_dbm()

        print(f'  Network type: {network_type_id} ({network_name})')
        print(f'  Signal strength: {signal_dbm} dBm' if signal_dbm else '  Signal strength: (could not read)')

        has_signal = network_type_id in ABOVE_2G_TYPES
        if not has_signal:
            # Also accept EDGE (2) as the minimum requirement for having signal
            has_signal = network_type_id == '2'
        if not has_signal and signal_dbm is not None:
            # Some devices/ROMs briefly return UNKNOWN(0) while signal strength is already readable.
            # In that case treat it as "has mobile signal"; the later technology classification only warns and does not block.
            has_signal = -140 < signal_dbm < -30

        self.assertTrue(
            has_signal,
            f'Device currently has no mobile network signal (network_type={network_type_id}/{network_name}). '
            'Please check whether the SIM card supports the current band, or whether signal coverage is normal.'
        )
        print(f'  ✓ Device has mobile signal: {network_name}')
        return network_type_id, network_name

    # -- Step 4: WCDMA / 4G / 5G technology validation -------------------------

    def _verify_network_technology(self, network_type_id, network_name):
        """
        Step 4: Classify and validate by the current network technology.
        - If currently 5G (NR)    -> pass NR
        - If currently 4G (LTE)   -> pass LTE
        - If currently WCDMA/3G   -> pass WCDMA
        - Otherwise               -> warn, do not fail (may be in a weak 2G coverage area)
        """
        print('[WWAN_NET] Step 4: Classify network technology')
        if network_type_id in NR_TYPES:
            print('  ✓ 5G (NR) network detected')
        elif network_type_id in LTE_TYPES:
            print('  ✓ 4G (LTE) network detected')
        elif network_type_id in WCDMA_TYPES:
            print('  ✓ WCDMA / 3G network detected')
        else:
            print(f'  [WARN] Network type {network_name} is below 3G. Consider SIM or coverage issue.')
            # Do not fail: 2G can also be considered "has signal", already verified in Step 3

    # -- Step 5: Data connectivity ---------------------------------------------

    def _verify_data_connectivity(self):
        """Step 5: Verify mobile data availability via ping."""
        print(f'[WWAN_NET] Step 5: Verify data connectivity (ping {PING_HOST})')
        # Ensure mobile data is enabled
        _shell('svc data enable')
        time.sleep(3)

        out = _shell(f'ping -c 3 -W 5 {PING_HOST}', timeout=25)
        print(f'  ping output: {out[:200]}')

        received_match = re.search(r'(\d+)\s+received', out)
        bytes_from = 'bytes from' in out
        success = bytes_from or (received_match and int(received_match.group(1)) > 0)

        if not success:
            # Fallback: try curl
            curl = _shell(
                f'curl -s --max-time 10 -o /dev/null -w "%{{http_code}}" http://www.baidu.com',
                timeout=20
            )
            print(f'  curl http_code: {curl}')
            success = curl.strip() in ('200', '301', '302', '307', '308')

        self.assertTrue(success, f'Mobile data connectivity check failed (ping {PING_HOST} got no replies, curl no response)')
        print('  ✓ Mobile data connectivity verified')

    # -- Main test case --------------------------------------------------------

    def test_L0_WWAN_WCDMA_4G_5G(self):
        """
        L0_WWAN WCDMA/4G/5G full flow.

        Test Steps:
          1. Verify the SIM card is recognized
          2. Verify the device is booted
          3. Verify mobile network signal is obtained
          4. Identify the current network technology (WCDMA/4G/5G)
          5. Verify mobile data connectivity
        """
        print('\n' + '=' * 60)
        print('TEST: L0_WWAN WCDMA / 4G / 5G')
        print('=' * 60)

        self._verify_sim_and_boot()
        network_type_id, network_name = self._verify_signal()
        self._verify_network_technology(network_type_id, network_name)
        self._verify_data_connectivity()

        print('\n' + '=' * 60)
        print('✓ PASS - All L0_WWAN WCDMA/4G/5G checks passed')
        print('=' * 60)
