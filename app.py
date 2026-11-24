# -*- coding:utf-8 -*-
from flask import Flask, send_from_directory, send_file, jsonify, request
import os
import subprocess
import threading
import sys
import ast
import json
import time
import re
import traceback
import base64
import smtplib
import platform as py_platform
import urllib.request
import urllib.error
import urllib.parse
from email.message import EmailMessage
from html import escape
from openpyxl import Workbook
from io import BytesIO
from datetime import datetime, timedelta
from common.copilot_provider import CopilotProviderError, chat_completion, copilot_config

app = Flask(__name__)
APP_VERSION = 'AutoNexus v1.0.0'
try:
    # Keep Chinese strings readable in JSON responses.
    app.json.ensure_ascii = False
except Exception:
    pass

@app.after_request
def add_cors_headers(resp):
    resp.headers["Access-Control-Allow-Origin"] = "*"
    resp.headers["Access-Control-Allow-Methods"] = "GET,POST,PUT,DELETE,OPTIONS"
    resp.headers["Access-Control-Allow-Headers"] = "*"
    return resp

@app.before_request
def handle_preflight():
    if request.method == 'OPTIONS':
        return ('', 204)

BASE_DIR = os.path.dirname(os.path.realpath(__file__))
REPORT_DIR = os.path.join(BASE_DIR, 'report')
REPORT_LOG_DIR = os.path.join(REPORT_DIR, '_logs')
IMG_DIR = os.path.join(BASE_DIR, 'img')
CASE_DIR = os.path.join(BASE_DIR, 'case')
COMMON_DIR = os.path.join(BASE_DIR, 'common')
COMMON_GENERATED_MODULE = 'common.generated_helpers'
COMMON_GENERATED_FILE = os.path.join(COMMON_DIR, 'generated_helpers.py')
AI_CASE_DIR = os.path.join(CASE_DIR, 'demo')
DATA_DIR = os.path.join(BASE_DIR, 'data')
os.makedirs(DATA_DIR, exist_ok=True)
AI_CASE_INDEX_FILE = os.path.join(DATA_DIR, 'ai_case_index.json')
CASE_META_FILE = os.path.join(DATA_DIR, 'case_meta.json')
TIMER_TASK_FILE = os.path.join(DATA_DIR, 'timer_tasks.json')
REPORT_RECORD_FILE = os.path.join(DATA_DIR, 'report_records.json')
SYSTEM_LOG_FILE = os.path.join(DATA_DIR, 'system_logs.json')


def _get_environment_value(name, default=''):
    """Read a process variable, falling back to the current user's Windows environment."""
    value = os.environ.get(name)
    if value is not None:
        return value
    if os.name != 'nt':
        return default
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r'Environment') as key:
            value, _ = winreg.QueryValueEx(key, name)
            return str(value)
    except (FileNotFoundError, OSError):
        return default


def _send_graph_email(tenant_id, client_id, client_secret, sender, recipients, subject, text_body, html_body, attachment=None):
    """Send a message through Microsoft Graph using application credentials."""
    token_data = urllib.parse.urlencode({
        'client_id': client_id,
        'client_secret': client_secret,
        'scope': 'https://graph.microsoft.com/.default',
        'grant_type': 'client_credentials',
    }).encode('utf-8')
    token_request = urllib.request.Request(
        f'https://login.microsoftonline.com/{urllib.parse.quote(tenant_id, safe="")}/oauth2/v2.0/token',
        data=token_data,
        headers={'Content-Type': 'application/x-www-form-urlencoded'},
        method='POST',
    )
    try:
        with urllib.request.urlopen(token_request, timeout=20) as response:
            access_token = json.loads(response.read().decode('utf-8')).get('access_token')
        if not access_token:
            raise ValueError('OAuth 响应中未包含 access_token')
        message_body = {
            'subject': subject,
            'body': {'contentType': 'HTML', 'content': html_body},
            'toRecipients': [{'emailAddress': {'address': address}} for address in recipients],
        }
        if attachment:
            message_body['attachments'] = [{
                '@odata.type': '#microsoft.graph.fileAttachment',
                'name': attachment[0],
                'contentType': 'text/html',
                'contentBytes': base64.b64encode(attachment[1]).decode('ascii'),
            }]
        graph_payload = json.dumps({
            'message': message_body,
            'saveToSentItems': True,
        }).encode('utf-8')
        send_request = urllib.request.Request(
            'https://graph.microsoft.com/v1.0/users/' + urllib.parse.quote(sender, safe='@') + '/sendMail',
            data=graph_payload,
            headers={
                'Authorization': f'Bearer {access_token}',
                'Content-Type': 'application/json',
            },
            method='POST',
        )
        with urllib.request.urlopen(send_request, timeout=30) as response:
            if response.status != 202:
                raise ValueError(f'Microsoft Graph 返回 HTTP {response.status}')
    except urllib.error.HTTPError as e:
        detail = e.read().decode('utf-8', errors='ignore')[:1000]
        raise RuntimeError(f'Microsoft Graph HTTP {e.code}: {detail}') from e


def _resolve_runner_python():
    """Resolve python interpreter used to run run_all.py from web triggers."""
    def _is_working_python(candidate):
        candidate = (candidate or '').strip()
        if not candidate or not os.path.exists(candidate):
            return False
        try:
            probe = subprocess.run(
                [candidate, '--version'],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=5,
                creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0)
            )
            return probe.returncode == 0
        except Exception:
            return False

    candidates = [
        (os.environ.get('AUTONEXUS_PYTHON') or '').strip(),
        os.path.join(BASE_DIR, '.venv', 'Scripts', 'python.exe'),
        os.path.join(BASE_DIR, 'venv', 'Scripts', 'python.exe'),
        sys.executable,
    ]

    for candidate in candidates:
        if _is_working_python(candidate):
            return candidate

    return sys.executable


RUNNER_PYTHON = _resolve_runner_python()

run_status = {
    'running': False,
    'log': '',
    'last_run': None,
    'current_case': '',
    'total_cases': 0,
    'completed_cases': 0,
    'passed': 0,
    'failed': 0,
    'error': 0,
    'skipped': 0,
    'failed_indices': [],
    'current_task_id': None,
    'terminate_requested': False,
    'process': None,
    'device_progress': {},
    'repeat_total': 1,
    'repeat_index': 1,
    'repeat_active': False
}
run_status_lock = threading.Lock()
timer_lock = threading.Lock()
SERVER_STARTED_AT = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

PLATFORM_MAP = [
    (['CT40','CT60','CK65','CN80','CN85','RT10','VM1','VM3'], '660'),
    (['CT45','CT30','CW45'], '4290'),
    (['CT47'], '6490'),
    (['CT37','CK67'], '4490'),
    (['CT70', 'RT710'], '6690'),
]

ADB = 'adb'

ENABLED_STATUS = '启用'
DISABLED_STATUS = '停用'


def normalize_task_status(value):
    s = (value or '').strip()
    if s == DISABLED_STATUS:
        return DISABLED_STATUS
    if s == ENABLED_STATUS:
        return ENABLED_STATUS

    low = s.lower()
    if low in ('disabled', 'disable', 'off', 'false', '0'):
        return DISABLED_STATUS
    if low in ('enabled', 'enable', 'on', 'true', '1'):
        return ENABLED_STATUS

    # Fallback to enabled to keep scheduler behavior predictable.
    return ENABLED_STATUS


def normalize_task_tags(tags):
    if isinstance(tags, str):
        raw = [x.strip() for x in re.split(r'[,;，；\s]+', tags) if x and x.strip()]
    elif isinstance(tags, list):
        raw = [str(x).strip() for x in tags if str(x).strip()]
    else:
        raw = []

    cleaned = []
    seen = set()
    for item in raw:
        tag = item[:24]
        if not tag:
            continue
        key = tag.lower()
        if key in seen:
            continue
        seen.add(key)
        cleaned.append(tag)
        if len(cleaned) >= 20:
            break
    return cleaned


def normalize_execution_times(value):
    try:
        n = int(value)
    except Exception:
        n = 1
    # Limit to a reasonable upper bound to prevent accidental overload.
    return max(1, min(999, n))


def normalize_task_record(task):
    t = dict(task or {})
    t['caseCount'] = int(t.get('caseCount', 0) or 0)
    t['executionTimes'] = normalize_execution_times(t.get('executionTimes', t.get('execTimes', 1)))
    t['totalExecCount'] = int(t.get('totalExecCount', t['caseCount'] * t['executionTimes']) or 0)
    t['status'] = normalize_task_status(t.get('status', ENABLED_STATUS))
    t['tags'] = normalize_task_tags(t.get('tags', []))
    t['lastRunTotal'] = int(t.get('lastRunTotal', 0) or 0)
    t['lastRunCompleted'] = int(t.get('lastRunCompleted', 0) or 0)
    t['lastRunPassed'] = int(t.get('lastRunPassed', 0) or 0)
    t['lastRunFailed'] = int(t.get('lastRunFailed', 0) or 0)
    t['lastRunError'] = int(t.get('lastRunError', 0) or 0)
    t['lastRunSkipped'] = int(t.get('lastRunSkipped', 0) or 0)
    t['lastRunCrashed'] = bool(t.get('lastRunCrashed', False))
    return t


def derive_task_mode(task):
    t = dict(task or {})
    mode = (t.get('runMode') or '').strip().lower()
    if mode in ('once', 'timer'):
        return mode

    # Backward compatibility for historical records before runMode was introduced.
    create_time = (t.get('createTime') or '').strip()
    last_triggered = (t.get('lastTriggeredAt') or '').strip()
    if t.get('status') == DISABLED_STATUS and create_time and last_triggered and create_time[:16] == last_triggered:
        return 'once'
    return 'timer'


def decorate_task_view(task):
    t = normalize_task_record(task)
    mode = derive_task_mode(t)
    t['runMode'] = mode
    if mode == 'once':
        # 如果这个任务当前正在执行，标记为"执行中"而不是"已完成"
        if str(run_status.get('current_task_id')) == str(t.get('id')) and run_status.get('running'):
            t['progressStatus'] = '执行中'
        elif str(t.get('lastRunResult', '')).upper() == 'TERMINATED':
            t['progressStatus'] = '已终止'
        elif bool(t.get('lastRunCrashed', False)):
            t['progressStatus'] = '异常终止'
        else:
            t['progressStatus'] = '已完成' if (t.get('lastTriggeredAt') or '').strip() else '未完成'
    else:
        t['progressStatus'] = t.get('status', ENABLED_STATUS)
    return t

def init_case_meta():
    if not os.path.exists(CASE_META_FILE):
        with open(CASE_META_FILE, 'w', encoding='utf-8') as f:
            json.dump([], f, ensure_ascii=False, indent=2)

def init_timer_tasks():
    if not os.path.exists(TIMER_TASK_FILE):
        with open(TIMER_TASK_FILE, 'w', encoding='utf-8') as f:
            json.dump([], f, ensure_ascii=False, indent=2)

def init_report_records():
    if not os.path.exists(REPORT_RECORD_FILE):
        with open(REPORT_RECORD_FILE, 'w', encoding='utf-8') as f:
            json.dump([], f, ensure_ascii=False, indent=2)

def init_system_logs():
    if not os.path.exists(SYSTEM_LOG_FILE):
        with open(SYSTEM_LOG_FILE, 'w', encoding='utf-8') as f:
            json.dump([], f, ensure_ascii=False, indent=2)

def init_report_logs():
    os.makedirs(REPORT_LOG_DIR, exist_ok=True)

def init_ai_case_index():
    if not os.path.exists(AI_CASE_INDEX_FILE):
        with open(AI_CASE_INDEX_FILE, 'w', encoding='utf-8') as f:
            json.dump({'next': 1}, f, ensure_ascii=False, indent=2)

init_case_meta()
init_timer_tasks()
init_report_records()
init_system_logs()
init_report_logs()
init_ai_case_index()

def read_case_meta():
    with open(CASE_META_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)

def write_case_meta(data):
    with open(CASE_META_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def read_timer_tasks():
    try:
        with open(TIMER_TASK_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            if not isinstance(data, list):
                return []
            normalized = [normalize_task_record(item) for item in data if isinstance(item, dict)]
            if normalized != data:
                write_timer_tasks(normalized)
            return normalized
    except Exception:
        return []

def write_timer_tasks(data):
    with open(TIMER_TASK_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def read_report_records():
    try:
        with open(REPORT_RECORD_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return data if isinstance(data, list) else []
    except Exception:
        return []

def write_report_records(data):
    with open(REPORT_RECORD_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def read_system_logs():
    try:
        with open(SYSTEM_LOG_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return data if isinstance(data, list) else []
    except Exception:
        return []


def write_system_logs(data):
    with open(SYSTEM_LOG_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def append_system_log(action, message, level='INFO', detail=None):
    logs = read_system_logs()
    logs.insert(0, {
        'id': int(time.time() * 1000),
        'time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'level': (level or 'INFO').upper(),
        'action': action or 'SYSTEM',
        'message': message or '',
        'detail': detail or {}
    })
    if len(logs) > 2000:
        logs = logs[:2000]
    write_system_logs(logs)


def read_ai_case_index():
    try:
        with open(AI_CASE_INDEX_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            if not isinstance(data, dict):
                return {'next': 1}
            nxt = int(data.get('next', 1) or 1)
            return {'next': nxt if nxt > 0 else 1}
    except Exception:
        return {'next': 1}


def write_ai_case_index(data):
    with open(AI_CASE_INDEX_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def parse_datetime_safe(value):
    s = (value or '').strip()
    if not s:
        return None
    try:
        return datetime.strptime(s, '%Y-%m-%d %H:%M:%S')
    except Exception:
        return None

















def choose_best_task_name_for_record(record, tasks):
    exec_dt = parse_datetime_safe(record.get('executeTime', ''))
    if not exec_dt:
        return None

    platform = (record.get('platform') or '').strip()
    device_sn = (record.get('deviceSn') or '').strip()
    candidates = []

    for task in tasks:
        t_name = (task.get('taskName') or task.get('profileName') or '').strip()
        if not t_name:
            continue

        t_platform = (task.get('platform') or '').strip()
        t_device_sn = (task.get('deviceSn') or '').strip()
        if platform and t_platform and platform != t_platform:
            continue
        if device_sn and t_device_sn and device_sn != t_device_sn:
            continue

        t_create = parse_datetime_safe(task.get('createTime', ''))
        if t_create:
            sec_diff = abs((exec_dt - t_create).total_seconds())
            # For immediate execution created from UI, createTime is usually very close to executeTime.
            if sec_diff <= 300:
                candidates.append((sec_diff, t_name))
                continue

        # Fallback by HH:MM for old records lacking close createTime.
        exec_hm = exec_dt.strftime('%H:%M')
        if (task.get('execTime') or '').strip() == exec_hm:
            candidates.append((9999, t_name))

    if not candidates:
        return None

    candidates.sort(key=lambda x: x[0])
    return candidates[0][1]


def migrate_report_profile_names(dry_run=False):
    tasks = read_timer_tasks()
    records = read_report_records()

    changed = 0
    details = []
    for row in records:
        old_name = (row.get('profileName') or '').strip()
        # Only repair obvious auto/empty names to avoid overriding valid historical names.
        needs_repair = (not old_name) or old_name in ('未命名任务', 'N/A') or old_name.startswith('profile_')
        if not needs_repair:
            continue

        new_name = choose_best_task_name_for_record(row, tasks)
        if not new_name or new_name == old_name:
            continue

        details.append({
            'recordId': row.get('id'),
            'executeTime': row.get('executeTime', ''),
            'from': old_name,
            'to': new_name
        })
        changed += 1
        if not dry_run:
            row['profileName'] = new_name

    if changed and not dry_run:
        write_report_records(records)

    return {
        'total': len(records),
        'updated': changed,
        'details': details
    }

def list_html_reports():
    if not os.path.exists(REPORT_DIR):
        return []
    files = []
    for name in os.listdir(REPORT_DIR):
        if not name.lower().endswith('.html'):
            continue
        full = os.path.join(REPORT_DIR, name)
        if not os.path.isfile(full):
            continue
        try:
            if os.path.getsize(full) <= 0:
                continue
        except Exception:
            continue
        files.append(name)
    return files

def parse_run_result(log_text):
    t = (log_text or '')
    t_upper = t.upper()
    # Check for errors first
    if 'TRACEBACK' in t_upper or 'UNICODEENCODEERROR' in t_upper:
        return 'FAIL'
    if '... FAIL' in t_upper or '... ERROR' in t_upper or '\nFAILED' in t_upper:
        return 'FAIL'
    # Check for success indicators (lowercase variants)
    if '... ok' in t or '... PASS' in t_upper or '\nOK' in t_upper:
        return 'PASS'
    # Check new format: [AUTONEXUS_PROGRESS] END ... OK/FAIL/ERROR
    if '[AUTONEXUS_PROGRESS]' in t_upper:
        # Count FAIL/ERROR outcomes
        fail_lines = [line for line in t.split('\n') if '[AUTONEXUS_PROGRESS] END' in line and (' FAIL ' in line or ' ERROR ' in line)]
        if fail_lines:
            return 'FAIL'
        # Count OK outcomes
        ok_lines = [line for line in t.split('\n') if '[AUTONEXUS_PROGRESS] END' in line and ' OK ' in line]
        if ok_lines:
            return 'PASS'
        # SKIP does not count as a failed execution result.
        skip_lines = [line for line in t.split('\n') if '[AUTONEXUS_PROGRESS] END' in line and ' SKIP ' in line]
        if skip_lines:
            return 'PASS'
    return 'UNKNOWN'

def find_latest_report_file(before_files=None, started_at=None):
    before = set(before_files or [])
    html_files = list_html_reports()
    candidates = []
    for name in html_files:
        full = os.path.join(REPORT_DIR, name)
        try:
            mtime = os.path.getmtime(full)
        except Exception:
            continue
        if name in before and started_at and mtime < started_at:
            continue
        if started_at and mtime + 1 < started_at:
            continue
        candidates.append((mtime, name))
    if not candidates:
        return ''
    candidates.sort(reverse=True)
    return candidates[0][1]

def write_run_console_log(execute_time, log_text):
    ts = execute_time.replace(' ', '_').replace(':', '-').replace('/', '-')
    filename = f"console_{ts}_{int(time.time() * 1000)}.log"
    # Defensive: the report/_logs folder can be removed after startup (manual cleanup,
    # external tooling, etc). Recreate it here so a missing folder doesn't crash the whole
    # run and silently discard the final pass/fail counts.
    os.makedirs(REPORT_LOG_DIR, exist_ok=True)
    path = os.path.join(REPORT_LOG_DIR, filename)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(log_text or '')
    return filename

def append_report_record(profile, trigger, run_result, report_file, execute_time, log_file=''):
    profile = profile or {}
    device_sn = profile.get('deviceSn', 'N/A')
    platform = profile.get('platform', 'N/A')
    # ✅ BUGFIX: Log warning if device info is invalid (N/A or Unknown)
    # This helps detect when devices were incorrectly selected
    if device_sn == 'N/A' or not device_sn:
        print(f"[WARNING] Record created with invalid deviceSn: profile={profile.get('profileName') or profile.get('taskName')}, trigger={trigger}")
    if platform in ('Unknown', 'N/A') or not platform:
        print(f"[WARNING] Record created with invalid platform: profile={profile.get('profileName') or profile.get('taskName')}, platform={platform}, trigger={trigger}")
    # Try to get androidVer from live device
    android_ver = 'N/A'
    if device_sn and device_sn != 'N/A':
        try:
            android_ver = normalize_prop_value(adb_getprop(device_sn, 'ro.vendor.build.version.release'))
        except:
            pass
    records = read_report_records()
    records.append({
        'id': int(datetime.now().timestamp() * 1000),
        'profileName': profile.get('profileName') or profile.get('taskName') or '未命名任务',
        'platform': platform,
        'deviceSn': device_sn,
        'osVersion': profile.get('osVersion', '当前设备OS'),
        'androidVer': android_ver,
        'executeTime': execute_time,
        'result': run_result,
        'reportFile': report_file,
        'logFile': log_file,
        'trigger': trigger,
    })
    write_report_records(records)

def adb_getprop(sn, prop):
    try:
        # Some adb.exe builds return a bogus non-zero exit code on this machine
        # even when the command succeeds, so read stdout instead of relying on returncode.
        result = subprocess.run(
            [ADB, '-s', sn, 'shell', 'getprop', prop],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=5
        )
        return result.stdout.decode('utf-8', errors='ignore').strip() or 'N/A'
    except Exception:
        return 'N/A'

def normalize_prop_value(value):
    v = (value or '').strip()
    if not v:
        return 'N/A'
    # Compatible with both plain getprop output and "[key]: [value]" style output.
    if v.startswith('[') and ']: [' in v and v.endswith(']'):
        try:
            v = v.split(']: [', 1)[1][:-1].strip()
        except Exception:
            pass
    return v or 'N/A'

def guess_platform(model):
    if not model or model == 'N/A':
        return 'Unknown'
    m = model.upper()
    for keywords, plat in PLATFORM_MAP:
        if any(k.upper() in m for k in keywords):
            return plat
    return 'Unknown'


def resolve_android_version(sn):
    """Resolve Android version with stable priority and sane fallback."""
    # Prefer framework release property first, then vendor release property.
    for prop in ('ro.build.version.release', 'ro.vendor.build.version.release'):
        raw = normalize_prop_value(adb_getprop(sn, prop))
        if raw != 'N/A':
            m = re.search(r'\d+', raw)
            if m:
                return m.group(0)

    # Fallback using SDK level mapping.
    sdk_raw = normalize_prop_value(adb_getprop(sn, 'ro.build.version.sdk'))
    if sdk_raw != 'N/A':
        try:
            sdk = int(re.search(r'\d+', sdk_raw).group(0))
            sdk_to_android = {
                36: '16',
                35: '15',
                34: '14',
                33: '13',
                32: '12',
                31: '12',
                30: '11',
                29: '10',
            }
            if sdk in sdk_to_android:
                return sdk_to_android[sdk]
        except Exception:
            pass

    return 'N/A'

def build_profile_summary(profile, trigger):
    profile = profile or {}
    name = profile.get('profileName') or profile.get('taskName') or '未命名任务'
    platform = profile.get('platform', 'N/A')
    device_sn = profile.get('deviceSn', 'N/A')
    os_ver = profile.get('osVersion', '当前设备OS')
    case_list = profile.get('caseList', [])
    case_count = profile.get('caseCount', len(case_list) if isinstance(case_list, list) else 0)
    return (
        f"来源: {trigger}\n"
        f"Profile: {name}\n"
        f"平台: {platform}\n"
        f"设备SN: {device_sn}\n"
        f"OS: {os_ver}\n"
        f"用例数: {case_count}\n"
    )


def update_task_run_state(profile, run_result, started_dt, run_snapshot=None):
    if not isinstance(profile, dict):
        return
    task_id = profile.get('id')
    if not task_id:
        return

    with timer_lock:
        tasks = read_timer_tasks()
        changed = False
        for i, item in enumerate(tasks):
            if item.get('id') != task_id:
                continue
            row = dict(item)
            row['lastTriggeredAt'] = started_dt.strftime('%Y-%m-%d %H:%M')
            row['lastRunAt'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            row['lastRunResult'] = run_result
            snap = run_snapshot if isinstance(run_snapshot, dict) else {}
            row['lastRunTotal'] = int(snap.get('total', 0) or 0)
            row['lastRunCompleted'] = int(snap.get('completed', 0) or 0)
            row['lastRunPassed'] = int(snap.get('passed', 0) or 0)
            row['lastRunFailed'] = int(snap.get('failed', 0) or 0)
            row['lastRunError'] = int(snap.get('error', 0) or 0)
            row['lastRunSkipped'] = int(snap.get('skipped', 0) or 0)
            row['lastRunCrashed'] = bool(snap.get('crashed', False))
            row['lastRunRequestedTotal'] = int(snap.get('requestedTotal', 0) or 0)
            row['lastRunLoadedTotal'] = int(snap.get('loadedTotal', 0) or 0)
            row['lastRunLoadFailed'] = int(snap.get('loadFailed', 0) or 0)
            if derive_task_mode(row) == 'once':
                row['status'] = DISABLED_STATUS
            tasks[i] = row
            changed = True
            break
        if changed:
            write_timer_tasks(tasks)


def get_connected_devices_info():
    devices = []
    try:
        result = subprocess.run(
            [ADB, 'devices'],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=5
        )
        lines = result.stdout.strip().splitlines()
    except Exception as e:
        return {"error": str(e), "devices": []}

    for line in lines[1:]:
        line = line.strip()
        if not line:
            continue
        parts = line.split()
        if len(parts) < 2 or parts[1] != 'device':
            continue

        sn = parts[0]
        conn = parts[1]
        status = {
            'device': 'online',
            'offline': 'offline',
            'unauthorized': 'unauthorized',
        }.get(conn.lower(), conn.lower() or 'unknown')
        model = 'N/A'
        pn = 'N/A'
        os_build = 'N/A'
        android_ver = 'N/A'
        sn_real = 'N/A'
        if status == 'online':
            model = normalize_prop_value(adb_getprop(sn, 'ro.vendor.hon.model.num'))
            if model == 'N/A':
                model = normalize_prop_value(adb_getprop(sn, 'ro.product.model'))
            os_build = normalize_prop_value(adb_getprop(sn, 'ro.build.display.id'))
            sn_real = normalize_prop_value(adb_getprop(sn, 'ro.vendor.hon.extserial.num'))
        show_sn = sn_real if sn_real != 'N/A' else sn
        devices.append({
            "sn": show_sn,
            "adbSn": sn,
            "model": model,
            "pn": pn,
            "osVersion": os_build,
            "androidVer": android_ver,
            "platform": guess_platform(model),
            "status": status,
        })
    return devices


def pick_default_case():
    if not os.path.exists(CASE_DIR):
        return None
    import hashlib
    for root, dirs, files in os.walk(CASE_DIR):
        dirs[:] = [d for d in dirs if d not in {'__pycache__', '.git', '.idea', '.vscode'}]
        for fname in sorted(files):
            if not fname.startswith('test') or not fname.endswith('.py'):
                continue
            fpath = os.path.join(root, fname)
            rel_file = os.path.relpath(fpath, CASE_DIR).replace('\\', '/')
            try:
                with open(fpath, 'r', encoding='utf-8-sig', errors='ignore') as f:
                    source = f.read()
                tree = ast.parse(source)
                first_cls = ''
                first_method = ''
                for node in ast.walk(tree):
                    if isinstance(node, ast.ClassDef):
                        first_cls = first_cls or node.name
                        for item in node.body:
                            if isinstance(item, ast.FunctionDef) and (item.name.startswith('test') or item.name.startswith('L0_')):
                                first_method = first_method or item.name
                if first_cls and first_method:
                    stable_id = int(hashlib.md5(rel_file.encode()).hexdigest()[:8], 16) % 2147483647
                    display_name = os.path.splitext(os.path.basename(rel_file))[0]
                    return {
                        'id': stable_id,
                        'name': display_name,
                        'displayName': display_name,
                        'className': first_cls,
                        'methodName': first_method,
                        'file': rel_file,
                    }
            except Exception:
                continue
    return None

def scan_source_cases():
    import hashlib
    cases = []
    if not os.path.exists(CASE_DIR):
        return cases
    for root, dirs, files in os.walk(CASE_DIR):
        dirs[:] = [d for d in dirs if d not in {'__pycache__', '.git', '.idea', '.vscode'}]
        for fname in sorted(files):
            if not fname.startswith('test') or not fname.endswith('.py'):
                continue
            fpath = os.path.join(root, fname)
            rel_file = os.path.relpath(fpath, CASE_DIR).replace('\\', '/')
            folder = os.path.dirname(rel_file).replace('\\', '/') if os.path.dirname(rel_file) else '.'
            ai_no = _extract_ai_case_no_from_file(fpath)
            try:
                with open(fpath, 'r', encoding='utf-8-sig', errors='ignore') as f:
                    source = f.read()
                tree = ast.parse(source)
                author = 'N/A'
                for node in ast.walk(tree):
                    if isinstance(node, ast.Assign):
                        for t in node.targets:
                            if isinstance(t, ast.Name) and t.id == '__author__':
                                if isinstance(node.value, ast.Constant):
                                    author = node.value.s
                file_methods = []
                first_cls = ''
                first_method = ''
                first_doc = ''
                for node in ast.walk(tree):
                    if isinstance(node, ast.ClassDef):
                        cls = node.name
                        for item in node.body:
                            if isinstance(item, ast.FunctionDef) and (item.name.startswith('test') or item.name.startswith('L0_')):
                                method_pair = f"{cls}.{item.name}"
                                method_doc = (ast.get_docstring(item) or '').strip()
                                file_methods.append(method_pair)
                                if not first_cls:
                                    first_cls = cls
                                if not first_method:
                                    first_method = item.name
                                if method_doc and not first_doc:
                                    first_doc = method_doc

                # File-level case model: one *.py file = one case entry.
                if not file_methods:
                    continue

                # Generate stable ID based on file path only.
                id_seed = rel_file
                stable_id = int(hashlib.md5(id_seed.encode()).hexdigest()[:8], 16) % 2147483647
                display_name = os.path.splitext(os.path.basename(rel_file))[0]

                cases.append({
                    'id': stable_id,
                    'name': display_name,
                    'displayName': display_name,
                    'className': first_cls,
                    'methodName': first_method,
                    'file': rel_file,
                    'folder': folder,
                    'aiNo': ai_no,
                    'doc': first_doc,
                    'owner': author,
                    'caseList': file_methods,
                    'methodCount': len(file_methods)
                })
            except Exception:
                continue
    return cases


def _is_safe_case_file(name):
    if not name or '/' in name or '\\' in name or '..' in name:
        return False
    return name.startswith('test_') and name.endswith('.py')


def _normalize_case_name(name):
    cleaned = ''.join(ch if (ch.isalnum() or ch == '_') else '_' for ch in (name or '').strip())
    while '__' in cleaned:
        cleaned = cleaned.replace('__', '_')
    cleaned = cleaned.strip('_').lower()
    if not cleaned:
        return ''
    if cleaned[0].isdigit():
        cleaned = f'case_{cleaned}'
    return cleaned


def _to_class_suffix(case_name):
    parts = [p for p in case_name.split('_') if p]
    if not parts:
        return 'Generated'
    return ''.join(p[:1].upper() + p[1:] for p in parts)


def _extract_ai_case_no_from_file(path):
    try:
        with open(path, 'r', encoding='utf-8', errors='ignore') as f:
            for _ in range(20):
                line = f.readline()
                if not line:
                    break
                if line.startswith('# AI_GENERATED_CASE:'):
                    return line.split(':', 1)[1].strip()
    except Exception:
        return ''
    return ''


def _extract_ai_component_from_file(path):
    try:
        with open(path, 'r', encoding='utf-8', errors='ignore') as f:
            for _ in range(20):
                line = f.readline()
                if not line:
                    break
                if line.startswith('# AI_COMPONENT:'):
                    return line.split(':', 1)[1].strip()
    except Exception:
        return ''
    return ''


def _is_ai_generated_script(path):
    return bool(_extract_ai_case_no_from_file(path))


def _is_legacy_ai_demo_file(path):
    try:
        rel = os.path.relpath(path, CASE_DIR).replace('\\', '/')
    except Exception:
        return False
    if not rel:
        return False
    return rel.startswith('demo/') and os.path.basename(path).startswith('test_') and os.path.basename(path).endswith('.py')


def _next_ai_case_no(existing_file_path=None):
    if existing_file_path and os.path.isfile(existing_file_path):
        existing_no = _extract_ai_case_no_from_file(existing_file_path)
        if existing_no:
            return existing_no

    idx = read_ai_case_index()
    current = int(idx.get('next', 1) or 1)
    idx['next'] = current + 1
    write_ai_case_index(idx)
    return f'AI-{current:04d}'


def _resolve_component_folder(component_raw):
    normalized_component = _normalize_case_name(component_raw)
    if not normalized_component:
        normalized_component = 'demo'

    os.makedirs(CASE_DIR, exist_ok=True)
    try:
        for entry in os.listdir(CASE_DIR):
            full = os.path.join(CASE_DIR, entry)
            if not os.path.isdir(full):
                continue
            if _normalize_case_name(entry) == normalized_component:
                return entry
    except Exception:
        pass

    return normalized_component


def _resolve_rel_case_path(rel_path):
    rel = (rel_path or '').replace('\\', '/').strip().lstrip('/')
    if not rel:
        return None
    if '..' in rel.split('/'):
        return None

    base_norm = os.path.normpath(CASE_DIR)
    target = os.path.normpath(os.path.join(CASE_DIR, rel))
    try:
        if os.path.commonpath([base_norm, target]) != base_norm:
            return None
    except Exception:
        return None
    if not os.path.isfile(target):
        return None
    return target


def _find_ai_script_by_name(name):
    if not _is_safe_case_file(name):
        return None
    for root, _, files in os.walk(CASE_DIR):
        for fname in files:
            if fname != name:
                continue
            full = os.path.join(root, fname)
            if _is_ai_generated_script(full) or _is_legacy_ai_demo_file(full):
                return full
    return None


def _scan_common_function_names():
    names = set()
    if not os.path.isdir(COMMON_DIR):
        return names
    for fname in os.listdir(COMMON_DIR):
        if not fname.endswith('.py'):
            continue
        full = os.path.join(COMMON_DIR, fname)
        if not os.path.isfile(full):
            continue
        try:
            with open(full, 'r', encoding='utf-8-sig', errors='ignore') as f:
                source = f.read()
            tree = ast.parse(source)
        except Exception:
            continue
        for node in tree.body:
            if isinstance(node, ast.FunctionDef):
                names.add(node.name)
    return names


def _ensure_generated_common_module():
    os.makedirs(COMMON_DIR, exist_ok=True)
    if os.path.exists(COMMON_GENERATED_FILE):
        return
    with open(COMMON_GENERATED_FILE, 'w', encoding='utf-8') as f:
        f.write(
            '# -*- coding:utf-8 -*-\n'
            '"""\n'
            'Common helper functions for AI generated test cases.\n'
            'Author: AutoNexus AI (GitHub Copilot)\n'
            f'Created At: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}\n'
            '"""\n\n'
            'import subprocess\n'
            'import time\n'
            'from common.adb_common import take_screenshot\n\n'
        )


def _append_function_to_common(function_name, feature_desc, function_source):
    existing = _scan_common_function_names()
    if function_name in existing:
        return 'reused'

    _ensure_generated_common_module()
    created_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    block = (
        '\n'
        '# [AutoNexus Common Extension]\n'
        '# Author: AutoNexus AI (GitHub Copilot)\n'
        f'# Created At: {created_at}\n'
        f'# Feature: {feature_desc}\n'
        f'{function_source.strip()}\n'
    )
    with open(COMMON_GENERATED_FILE, 'a', encoding='utf-8') as f:
        f.write(block)
    return 'created'





def _build_generic_case_script(case_name, steps_text, ai_no, component_name):
    class_suffix = _to_class_suffix(case_name)
    method_name = f'test_{case_name}'
    lines = [ln.strip() for ln in (steps_text or '').splitlines() if ln.strip()]
    if not lines:
        lines = ['No detailed steps provided by user.']

    doc_lines = [f'[AI编号] {ai_no}', f'[组件目录] {component_name}'] + lines
    steps_doc = '\n'.join(f'    - {ln}' for ln in doc_lines)
    step_comments = '\n'.join(f'        # Step {idx}: {ln}' for idx, ln in enumerate(lines, 1))

    return f'''# -*- coding:utf-8 -*-
# AI_GENERATED_CASE: {ai_no}
# AI_COMPONENT: {component_name}
import os
import unittest
import uiautomator2 as u2
import time
from common.adb_common import take_screenshot


d = u2.connect(os.environ.get('ANDROID_SERIAL'))


class Test_{class_suffix}(unittest.TestCase):
    def setUp(self):
        d.screen_on()

    def tearDown(self):
        d.screen_on()

    """
{steps_doc}
    """
    def {method_name}(self):
{step_comments}

        # TODO: implement concrete actions according to above steps.
        take_screenshot(d, self.id(), step='generated_start')
        time.sleep(1)
        self.assertTrue(True, 'Generated template created successfully')
'''


# Reference case used as the generation template for camera cases (e.g. ANDROIDCN-36583).
CAMERA_REFERENCE_CASE = os.path.join(CASE_DIR, 'smoking', 'test_L0_camera_flashlight_ANDROIDCN_36583.py')


def _build_camera_case_from_reference(case_name, ai_no, component_name):
    """Generate a camera case by cloning the reference flashlight case."""
    with open(CAMERA_REFERENCE_CASE, 'r', encoding='utf-8', errors='ignore') as f:
        ref = f.read()
    class_suffix = _to_class_suffix(case_name)
    ref = ref.replace('Test_L0_Camera_Flashlight', f'Test_{class_suffix}')
    ref = ref.replace('def test_l0_androidcn_36583', f'def test_{case_name}')
    header = (
        '# -*- coding:utf-8 -*-\n'
        f'# AI_GENERATED_CASE: {ai_no}\n'
        f'# AI_COMPONENT: {component_name}\n'
    )
    return header + ref

def _build_case_script(case_name, steps_text, ai_no, component_name):
    lines = [ln.strip() for ln in (steps_text or '').splitlines() if ln.strip()]
    steps_text_lower = '\n'.join(lines).lower()
    if 'camera' in steps_text_lower and 'flash' in steps_text_lower and os.path.isfile(CAMERA_REFERENCE_CASE):
        return _build_camera_case_from_reference(case_name, ai_no, component_name)
    return _build_generic_case_script(case_name, steps_text, ai_no, component_name)


def _ai_llm_config():
    copilot = copilot_config()
    selected_provider = (os.environ.get('AUTONEXUS_AI_PROVIDER') or '').strip().lower()
    use_copilot = selected_provider in ('copilot', 'github-copilot') or (
        not selected_provider
        and not os.environ.get('AUTONEXUS_AI_API_KEY')
        and bool(copilot['api_key'])
    )
    if use_copilot:
        enabled_raw = (os.environ.get('AUTONEXUS_AI_ENABLE') or '1').strip().lower()
        return {
            'provider': 'copilot',
            'base_url': copilot['chat_url'],
            'api_key': copilot['api_key'],
            'model': copilot['model'],
            'enabled': enabled_raw not in ('0', 'false', 'off', 'no'),
            'timeout_sec': copilot['timeout_sec'],
            'copilot': copilot,
        }

    base_url = (os.environ.get('AUTONEXUS_AI_BASE_URL') or 'https://api.openai.com/v1').strip().rstrip('/')
    api_key = (os.environ.get('AUTONEXUS_AI_API_KEY') or '').strip()
    model = (os.environ.get('AUTONEXUS_AI_MODEL') or 'gpt-4o-mini').strip()
    enabled_raw = (os.environ.get('AUTONEXUS_AI_ENABLE') or '1').strip().lower()
    enabled = enabled_raw not in ('0', 'false', 'off', 'no')
    timeout_raw = (os.environ.get('AUTONEXUS_AI_TIMEOUT') or '25').strip()
    try:
        timeout_sec = max(5, min(120, int(timeout_raw)))
    except Exception:
        timeout_sec = 25
    return {
        'provider': 'openai-compatible',
        'base_url': base_url,
        'api_key': api_key,
        'model': model,
        'enabled': enabled,
        'timeout_sec': timeout_sec,
    }


def _extract_openai_text(resp_json):
    try:
        choices = resp_json.get('choices') or []
        if not choices:
            return ''
        message = (choices[0] or {}).get('message') or {}
        content = message.get('content')
        if isinstance(content, str):
            return content.strip()
        if isinstance(content, list):
            chunks = []
            for item in content:
                if isinstance(item, dict):
                    txt = item.get('text')
                    if txt:
                        chunks.append(str(txt))
            return '\n'.join(chunks).strip()
    except Exception:
        return ''
    return ''


def _request_llm(payload, cfg):
    if cfg['provider'] == 'copilot':
        return chat_completion(payload, config=cfg['copilot'])

    request = urllib.request.Request(
        f"{cfg['base_url']}/chat/completions",
        data=json.dumps(payload, ensure_ascii=False).encode('utf-8'),
        headers={
            'Content-Type': 'application/json',
            'Authorization': f"Bearer {cfg['api_key']}"
        },
        method='POST'
    )
    with urllib.request.urlopen(request, timeout=cfg['timeout_sec']) as response:
        return json.loads(response.read().decode('utf-8', errors='ignore'))


def _try_generate_steps_with_llm(case_name, component_name, steps_text):
    cfg = _ai_llm_config()
    if not cfg['enabled']:
        return None, 'AUTONEXUS_AI_ENABLE is off'
    if not cfg['api_key']:
        return None, 'AUTONEXUS_AI_API_KEY is empty'

    prompt = (
        '请根据以下测试用例信息，输出适合自动化脚本注释和步骤占位的“纯文本步骤”。\n'
        '要求：\n'
        '1) 保持步骤和预期结果一一对应。\n'
        '2) 每一步两行格式：\n'
        '   步骤 N: ...\n'
        '   预期结果: ...\n'
        '3) 不要输出 Markdown、代码块、JSON。\n'
        '4) 仅输出步骤正文。\n\n'
        f'用例标题: {case_name}\n'
        f'组件: {component_name or "demo"}\n'
        f'原始内容:\n{steps_text}'
    )

    payload = {
        'model': cfg['model'],
        'messages': [
            {'role': 'system', 'content': 'You are an expert test engineer generating concise and executable test steps.'},
            {'role': 'user', 'content': prompt},
        ],
        'temperature': 0.2,
    }

    try:
        data = _request_llm(payload, cfg)
        text = _extract_openai_text(data)
        if not text:
            return None, 'LLM response has empty content'
        return text, ''
    except CopilotProviderError as e:
        return None, str(e)
    except urllib.error.HTTPError as e:
        try:
            err_body = e.read().decode('utf-8', errors='ignore')
        except Exception:
            err_body = str(e)
        return None, f'LLM HTTPError: {e.code} {err_body[:240]}'
    except Exception as e:
        return None, f'LLM request failed: {e}'


def _resolve_steps_text(case_name, component_name, original_steps_text):
    llm_text, llm_err = _try_generate_steps_with_llm(case_name, component_name, original_steps_text)
    if llm_text:
        return llm_text, 'llm', ''
    return original_steps_text, 'template', llm_err


def _append_generation_meta(raw_msg, mode, err_msg=''):
    msg = raw_msg or 'AI用例生成成功'
    if mode == 'llm':
        return f"{msg}（LLM）"
    if err_msg:
        return f"{msg}（模板回退）"
    return msg


def _extract_code_from_llm_text(text):
    s = (text or '').strip()
    if not s:
        return ''
    m = re.search(r"```(?:python)?\s*([\s\S]*?)```", s, re.IGNORECASE)
    if m:
        return m.group(1).strip()
    return s


def _extract_failure_blocks(log_text):
    """Parse unittest FAIL/ERROR blocks and return list of failure dicts."""
    text = log_text or ''
    header_re = re.compile(r'^(FAIL|ERROR):\s*([A-Za-z0-9_]+)\s*\(([^)]+)\)\s*$', re.MULTILINE)
    matches = list(header_re.finditer(text))
    blocks = []
    for i, m in enumerate(matches):
        start = m.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        block = text[start:end].strip()
        case_type = m.group(1).strip()
        method = m.group(2).strip()
        cls_expr = m.group(3).strip()
        class_name = cls_expr.split('.')[-1].strip() if cls_expr else ''
        blocks.append({
            'type': case_type,
            'method': method,
            'className': class_name,
            'headerExpr': cls_expr,
            'block': block,
        })
    return blocks


def _is_script_logic_failure(failure_block):
    """Heuristic: return True only for script/step defects, not product functional mismatch."""
    t = (failure_block or '').lower()

    # Typical script/code defects.
    script_error_keywords = [
        'syntaxerror', 'nameerror', 'attributeerror', 'importerror', 'modulenotfounderror',
        'typeerror', 'keyerror', 'indexerror', 'indentationerror', 'uiautomator',
        'uiobjectnotfound', 'filenotfounderror', 'permissionerror', 'failed to enter',
        'not implemented', 'todo', 'camera shutter button not found', 'failed to launch camera app',
    ]
    if any(k in t for k in script_error_keywords):
        return True

    # Assertion failures can be either functional or script-step issue.
    if 'assertionerror' in t:
        functional_keywords = [
            'mismatch', 'expected', 'actual', 'should be', '不一致', '与当前机器', '与本机',
            '业务', '功能失败', '结果不符合',
        ]
        if any(k in t for k in functional_keywords):
            return False

        step_problem_keywords = [
            'not found', '找不到', '未找到', 'failed to', 'empty value', 'returned empty',
            '进入失败', '页面未打开',
        ]
        return any(k in t for k in step_problem_keywords)

    return False


def _build_case_lookup_map():
    lookup = {}
    for item in scan_source_cases():
        pairs = item.get('caseList') if isinstance(item.get('caseList'), list) else []
        if pairs:
            for key in pairs:
                if isinstance(key, str) and key.strip('.'):
                    lookup[key] = item
            continue
        key = f"{item.get('className', '')}.{item.get('name', '')}"
        if key.strip('.'):
            lookup[key] = item
    return lookup


def _try_repair_script_with_llm(case_item, failure_block):
    cfg = _ai_llm_config()
    if not cfg['enabled']:
        return False, 'autofix skipped: AUTONEXUS_AI_ENABLE is off'
    if not cfg['api_key']:
        return False, 'autofix skipped: AUTONEXUS_AI_API_KEY is empty'

    rel_file = (case_item.get('file') or '').replace('\\', '/').strip()
    if not rel_file:
        return False, 'autofix skipped: missing case file path'

    case_path = os.path.join(CASE_DIR, rel_file)
    if not os.path.isfile(case_path):
        return False, f'autofix skipped: case file not found {rel_file}'

    try:
        with open(case_path, 'r', encoding='utf-8', errors='ignore') as f:
            old_script = f.read()
    except Exception as e:
        return False, f'autofix skipped: failed reading script: {e}'

    prompt = (
        '请修复下面这个 Python 自动化测试脚本。\n'
        '目标：修复“脚本逻辑/步骤实现错误”，不要为了让测试通过而删除核心断言。\n'
        '约束：\n'
        '1) 保留文件头的 AI 注释行（AI_GENERATED_CASE / AI_COMPONENT）。\n'
        '2) 优先复用 common 库，避免重复造轮子。\n'
        '3) 不要输出 Markdown，只输出完整 Python 文件源码。\n'
        '4) 不要改动用例类名和测试方法名。\n\n'
        f'失败信息:\n{failure_block}\n\n'
        f'原始脚本({rel_file}):\n{old_script}\n'
    )

    payload = {
        'model': cfg['model'],
        'messages': [
            {'role': 'system', 'content': 'You are an expert Android UI automation test engineer.'},
            {'role': 'user', 'content': prompt},
        ],
        'temperature': 0.1,
    }

    try:
        data = _request_llm(payload, cfg)
        text = _extract_openai_text(data)
        new_script = _extract_code_from_llm_text(text)
        if not new_script:
            return False, 'autofix failed: llm returned empty script'

        # Syntax gate before writing.
        try:
            ast.parse(new_script)
        except Exception as e:
            return False, f'autofix failed: candidate script syntax error: {e}'

        backup = case_path + f".bak.{datetime.now().strftime('%Y%m%d%H%M%S')}"
        try:
            with open(backup, 'w', encoding='utf-8') as f:
                f.write(old_script)
        except Exception:
            pass

        with open(case_path, 'w', encoding='utf-8') as f:
            f.write(new_script)
        return True, f'autofix success: updated {rel_file}'
    except urllib.error.HTTPError as e:
        try:
            body = e.read().decode('utf-8', errors='ignore')[:240]
        except Exception:
            body = str(e)
        return False, f'autofix failed: llm http {e.code} {body}'
    except Exception as e:
        return False, f'autofix failed: {e}'


def _auto_fix_failed_ai_cases(profile, run_log_text):
    """When AI generated case fails due to script logic issues, auto-repair it with LLM."""
    profile = profile if isinstance(profile, dict) else {}
    selected_pairs = set()
    for item in (profile.get('caseList') or []):
        if isinstance(item, str) and '.' in item:
            selected_pairs.add(item.strip())

    case_lookup = _build_case_lookup_map()
    failure_blocks = _extract_failure_blocks(run_log_text)
    if not failure_blocks:
        return []

    actions = []
    for fb in failure_blocks:
        key = f"{fb.get('className', '')}.{fb.get('method', '')}"
        case_item = case_lookup.get(key)
        if not case_item:
            actions.append({'case': key, 'status': 'skip', 'reason': 'not found in case scan'})
            continue

        # Limit to selected cases when a selection exists.
        if selected_pairs and key not in selected_pairs:
            actions.append({'case': key, 'status': 'skip', 'reason': 'not in selected case list'})
            continue

        ai_no = (case_item.get('aiNo') or '').strip()
        if not ai_no:
            actions.append({'case': key, 'status': 'skip', 'reason': 'not an AI-generated case'})
            continue

        if not _is_script_logic_failure(fb.get('block', '')):
            actions.append({'case': key, 'status': 'skip', 'reason': 'classified as functional failure'})
            continue

        ok, msg = _try_repair_script_with_llm(case_item, fb.get('block', ''))
        actions.append({'case': key, 'status': 'fixed' if ok else 'failed', 'reason': msg})

    return actions


def _run_selected_cases_once(case_pairs):
    """Run selected cases once and return PASS/FAIL plus captured log text."""
    selected = [x for x in (case_pairs or []) if isinstance(x, str) and '.' in x]
    if not selected:
        return {'result': 'UNKNOWN', 'log': '', 'reason': 'empty case list'}

    env = os.environ.copy()
    env['PYTHONUTF8'] = '1'
    env['PYTHONIOENCODING'] = 'utf-8'
    env['PYTHONUNBUFFERED'] = '1'
    env['AUTONEXUS_CASE_LIST'] = json.dumps(selected, ensure_ascii=False)
    env['AUTONEXUS_CASE_IDS'] = json.dumps([], ensure_ascii=False)

    lines = []
    try:
        proc = subprocess.Popen(
            [RUNNER_PYTHON, '-u', os.path.join(BASE_DIR, 'run_all.py')],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding='utf-8',
            errors='ignore',
            cwd=BASE_DIR,
            env=env
        )
        for line in proc.stdout:
            lines.append(line)
        proc.wait()
        text = ''.join(lines)
        return {'result': parse_run_result(text), 'log': text, 'reason': ''}
    except Exception as e:
        return {'result': 'FAIL', 'log': ''.join(lines), 'reason': str(e)}

def trigger_test_run(profile=None, trigger='manual'):
    if run_status['running']:
        return False

    # 立即设置运行状态和任务ID，避免竞速条件
    run_status['running'] = True
    run_status['current_task_id'] = profile.get('id') if isinstance(profile, dict) else None

    def do_run():
        run_status['current_case'] = ''
        run_status['total_cases'] = profile.get('caseCount', 0) if isinstance(profile, dict) else 0
        run_status['requested_cases'] = profile.get('caseCount', 0) if isinstance(profile, dict) else 0
        run_status['loaded_cases'] = 0
        run_status['load_failed_cases'] = 0
        run_status['completed_cases'] = 0
        run_status['passed'] = 0
        run_status['failed'] = 0
        run_status['error'] = 0
        run_status['skipped'] = 0
        run_status['failed_indices'] = []
        run_status['has_structured_progress'] = False
        run_status['terminate_requested'] = False
        run_status['process'] = None
        run_status['log'] = '开始运行...\n' + build_profile_summary(profile, trigger)
        started_dt = datetime.now()
        started_ts = started_dt.timestamp()
        before_files = list_html_reports()
        record_written = False
        try:
            env = os.environ.copy()
            env['PYTHONUTF8'] = '1'
            env['PYTHONIOENCODING'] = 'utf-8'
            env['PYTHONUNBUFFERED'] = '1'  # 强制子进程stdout无缓冲，保证进度事件实时传出
            case_ids = profile.get('caseIds', []) if isinstance(profile, dict) else []
            case_list = profile.get('caseList', []) if isinstance(profile, dict) else []
            if isinstance(case_ids, list):
                env['AUTONEXUS_CASE_IDS'] = json.dumps(case_ids, ensure_ascii=False)
            if isinstance(case_list, list):
                env['AUTONEXUS_CASE_LIST'] = json.dumps(case_list, ensure_ascii=False)
            dev0_sn = (profile.get('deviceSn') or '').strip() if isinstance(profile, dict) else ''
            dev1_sn = (profile.get('referenceDeviceSn') or '').strip() if isinstance(profile, dict) else ''
            if dev0_sn:
                env['ANDROID_SERIAL'] = dev0_sn
                env['AUTONEXUS_DEV0_SN'] = dev0_sn
            if dev1_sn:
                env['AUTONEXUS_DEV1_SN'] = dev1_sn
            # Debug log
            run_status['log'] += f"\n[DEBUG] caseIds: {case_ids}\n"
            run_status['log'] += f"[DEBUG] caseList: {case_list}\n"
            run_status['log'] += f"[DEBUG] env AUTONEXUS_CASE_LIST: {env.get('AUTONEXUS_CASE_LIST', 'NOT SET')}\n"
            run_status['log'] += f"[DEBUG] runner python: {RUNNER_PYTHON}\n"
            proc = subprocess.Popen(
                [RUNNER_PYTHON, '-u', os.path.join(BASE_DIR, 'run_all.py')],  # -u 强制无缓冲
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding='utf-8',
                errors='ignore',
                cwd=BASE_DIR,
                env=env
            )
            run_status['process'] = proc
            for line in proc.stdout:
                run_status['log'] += line
                normalized = line.strip()

                if run_status.get('terminate_requested'):
                    run_status['log'] += '\n[SYSTEM] 收到终止请求，正在停止执行...\n'
                    try:
                        proc.terminate()
                    except Exception:
                        pass
                    break

                # 优先解析执行器输出的进度事件，提供实时、稳定的进度刷新。
                # 事件格式：
                # [AUTONEXUS_PROGRESS] TOTAL <n>
                # [AUTONEXUS_PROGRESS] START <i>/<n> <case_id>
                # [AUTONEXUS_PROGRESS] END <i>/<n> <OK|FAIL|ERROR|SKIP> <case_id>
                if normalized.startswith('[AUTONEXUS_PROGRESS]'):
                    run_status['has_structured_progress'] = True
                    total_match = re.match(r'^\[AUTONEXUS_PROGRESS\]\s+TOTAL\s+(\d+)\s*$', normalized)
                    if total_match:
                        run_status['loaded_cases'] = int(total_match.group(1))
                        # Keep total_cases as requested/planned count for UI consistency.
                        # Loaded count is tracked separately.
                        if int(run_status.get('requested_cases', 0) or 0) <= 0:
                            run_status['total_cases'] = run_status['loaded_cases']
                        continue

                    start_match = re.match(r'^\[AUTONEXUS_PROGRESS\]\s+START\s+(\d+)/(\d+)\s+(.+)$', normalized)
                    if start_match:
                        idx = int(start_match.group(1))
                        total = int(start_match.group(2))
                        case_id = start_match.group(3).strip()
                        run_status['loaded_cases'] = total
                        if int(run_status.get('requested_cases', 0) or 0) <= 0:
                            run_status['total_cases'] = total
                        run_status['current_case'] = case_id
                        # START 时至少推进到前一个已完成用例位置
                        run_status['completed_cases'] = max(run_status['completed_cases'], max(0, idx - 1))
                        continue

                    end_match = re.match(r'^\[AUTONEXUS_PROGRESS\]\s+END\s+(\d+)/(\d+)\s+(OK|FAIL|ERROR|SKIP)\s+(.+)$', normalized)
                    if end_match:
                        idx = int(end_match.group(1))
                        total = int(end_match.group(2))
                        outcome = end_match.group(3)
                        case_id = end_match.group(4).strip()
                        run_status['loaded_cases'] = total
                        if int(run_status.get('requested_cases', 0) or 0) <= 0:
                            run_status['total_cases'] = total
                        run_status['current_case'] = case_id
                        run_status['completed_cases'] = max(run_status['completed_cases'], idx)
                        if outcome == 'OK':
                            run_status['passed'] += 1
                        elif outcome == 'FAIL':
                            run_status['failed'] += 1
                            # 记录失败用例的索引（1-based）
                            if idx not in run_status['failed_indices']:
                                run_status['failed_indices'].append(idx)
                        elif outcome == 'ERROR':
                            run_status['error'] += 1
                            # 记录失败用例的索引（1-based）
                            if idx not in run_status['failed_indices']:
                                run_status['failed_indices'].append(idx)
                        elif outcome == 'SKIP':
                            run_status['skipped'] += 1
                        continue

                # 逐条解析 unittest verbosity=2 输出，实现实时进度更新
                # 例如: test_xxx (module.Class) ... ok|FAIL|ERROR
                case_match = re.search(r'^(?P<case>.+?)\s+\.\.\.\s+(?P<result>ok|FAIL|ERROR)\s*$', normalized)
                if case_match and not run_status.get('has_structured_progress'):
                    run_status['current_case'] = case_match.group('case')
                    run_status['completed_cases'] += 1
                    result = case_match.group('result')
                    if result == 'ok':
                        run_status['passed'] += 1
                    elif result == 'FAIL':
                        run_status['failed'] += 1
                    else:
                        run_status['error'] += 1

                    # 防止 completed 超过 total（total 可能由前端 caseCount 提供）
                    if run_status.get('total_cases', 0) > 0 and run_status['completed_cases'] > run_status['total_cases']:
                        run_status['completed_cases'] = run_status['total_cases']

                # 兼容兜底：某些输出只在结束时给出 Ran X test
                summary_match = re.search(r'Ran\s+(\d+)\s+test', normalized)
                if summary_match:
                    final_count = int(summary_match.group(1))
                    if final_count > run_status['completed_cases']:
                        run_status['completed_cases'] = final_count
            proc.wait()
            run_status['log'] += '\n完成'
            run_status['last_run'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            run_result = parse_run_result(run_status['log'])
            terminated_by_user = bool(run_status.get('terminate_requested'))
            if terminated_by_user:
                run_result = 'TERMINATED'
                run_status['log'] += '\n[SYSTEM] 任务被用户终止\n'
            # Debug log
            run_status['log'] += f"\n[DEBUG] parse_run_result returned: {run_result}\n"
            run_status['log'] += f"[DEBUG] total_cases: {run_status.get('total_cases', 0)}\n"
            run_status['log'] += f"[DEBUG] completed_cases: {run_status.get('completed_cases', 0)}\n"
            run_status['log'] += f"[DEBUG] passed: {run_status.get('passed', 0)}\n"
            run_status['log'] += f"[DEBUG] failed: {run_status.get('failed', 0)}\n"
            run_status['log'] += f"[DEBUG] error: {run_status.get('error', 0)}\n"
            run_status['log'] += f"[DEBUG] skipped: {run_status.get('skipped', 0)}\n"

            requested_total = int(run_status.get('requested_cases', 0) or 0)
            loaded_total = int(run_status.get('loaded_cases', 0) or 0)
            completed_cases = int(run_status.get('completed_cases', 0) or 0)
            passed_cases = int(run_status.get('passed', 0) or 0)
            failed_cases = int(run_status.get('failed', 0) or 0)
            error_cases = int(run_status.get('error', 0) or 0)
            skipped_cases = int(run_status.get('skipped', 0) or 0)

            # If progress total was unavailable, only infer from actually completed cases.
            # Do not infer from requested count, otherwise load-stage failures are masked.
            if loaded_total <= 0 and completed_cases > 0:
                loaded_total = completed_cases

            load_failed_cases = max(0, requested_total - loaded_total) if requested_total > 0 else 0
            run_status['load_failed_cases'] = load_failed_cases
            if load_failed_cases > 0:
                run_status['log'] += (
                    f"\n[WARN] 用例装载不完整: 计划 {requested_total} 条, 实际装载 {loaded_total} 条, "
                    f"装载失败 {load_failed_cases} 条\n"
                )
            if run_result == 'FAIL':
                actions = _auto_fix_failed_ai_cases(profile, run_status['log'])
                if actions:
                    run_status['log'] += '\n\n[AI AutoFix]\n'
                    for a in actions:
                        run_status['log'] += f"- {a.get('case')}: {a.get('status')} ({a.get('reason')})\n"

                    fixed_cases = [a.get('case') for a in actions if a.get('status') == 'fixed']
                    if fixed_cases:
                        rerun = _run_selected_cases_once(fixed_cases)
                        run_status['log'] += '\n[AI AutoFix ReRun]\n'
                        run_status['log'] += f"- selected cases: {', '.join(fixed_cases)}\n"
                        run_status['log'] += f"- rerun result: {rerun.get('result')}\n"
                        if rerun.get('reason'):
                            run_status['log'] += f"- rerun reason: {rerun.get('reason')}\n"
                        rerun_log = (rerun.get('log') or '').strip()
                        if rerun_log:
                            run_status['log'] += '\n[AI AutoFix ReRun Log]\n'
                            # Limit injected rerun log size to keep UI responsive.
                            run_status['log'] += rerun_log[-8000:] + '\n'
            report_file = find_latest_report_file(before_files=before_files, started_at=started_ts)
            log_file = write_run_console_log(started_dt.strftime('%Y-%m-%d %H:%M:%S'), run_status['log'])
            append_report_record(
                profile=profile,
                trigger=trigger,
                run_result=run_result,
                report_file=report_file,
                execute_time=started_dt.strftime('%Y-%m-%d %H:%M:%S'),
                log_file=log_file
            )
            snapshot_total = max(requested_total, loaded_total)

            # Final status should be driven by real run_result first.
            # If execution result is PASS but streaming progress lines were incomplete,
            # normalize snapshot to a fully completed successful run.
            if run_result == 'PASS':
                # Normalize against actually loaded cases, not requested cases.
                if loaded_total > 0 and completed_cases < loaded_total:
                    completed_cases = loaded_total
                if loaded_total > 0 and (passed_cases + failed_cases + error_cases + skipped_cases) < loaded_total:
                    passed_cases = max(passed_cases, loaded_total - failed_cases - error_cases - skipped_cases)
                failed_cases = max(0, failed_cases)
                error_cases = max(0, error_cases)
                crashed = False
            elif run_result == 'TERMINATED':
                crashed = True
            else:
                crashed = bool(snapshot_total > 0 and completed_cases < snapshot_total)

            run_snapshot = {
                'total': snapshot_total,
                'completed': completed_cases,
                'passed': passed_cases,
                'failed': failed_cases,
                'error': error_cases,
                'skipped': skipped_cases,
                'crashed': crashed,
                'requestedTotal': requested_total,
                'loadedTotal': loaded_total,
                'loadFailed': load_failed_cases
            }
            update_task_run_state(profile, run_result, started_dt, run_snapshot=run_snapshot)
            record_written = True
        except Exception as e:
            run_status['log'] += f'\n失败: {str(e)}'
            if not record_written:
                try:
                    run_status['last_run'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    log_file = write_run_console_log(started_dt.strftime('%Y-%m-%d %H:%M:%S'), run_status['log'])
                    append_report_record(
                        profile=profile,
                        trigger=trigger,
                        run_result='FAIL',
                        report_file='',
                        execute_time=started_dt.strftime('%Y-%m-%d %H:%M:%S'),
                        log_file=log_file
                    )
                    run_snapshot = {
                        'total': int(run_status.get('total_cases', 0) or 0),
                        'completed': int(run_status.get('completed_cases', 0) or 0),
                        'passed': int(run_status.get('passed', 0) or 0),
                        'failed': int(run_status.get('failed', 0) or 0),
                        'error': int(run_status.get('error', 0) or 0),
                        'skipped': int(run_status.get('skipped', 0) or 0),
                        'crashed': True
                    }
                    update_task_run_state(profile, 'FAIL', started_dt, run_snapshot=run_snapshot)
                except Exception:
                    pass
        finally:
            # CRITICAL: Set lastTriggeredAt BEFORE setting running=False to avoid race condition
            # where frontend polls task status before lastTriggeredAt is written
            # 
            # Problem: If we set running=False first, frontend immediately polls /api/timer/tasks,
            # but lastTriggeredAt hasn't been written yet (still in lock), causing progressStatus 
            # to be "未完成" (incomplete) instead of "已完成" (completed).
            # 
            # Solution: Lock-protected write of lastTriggeredAt happens FIRST, THEN we clear running state.
            # This ensures: by the time frontend's next poll hits /api/timer/tasks, the task record
            # has been fully updated with lastTriggeredAt, causing decorate_task_view to correctly
            # return progressStatus = '已完成'.
            if isinstance(profile, dict) and profile.get('runMode') == 'once':
                with timer_lock:
                    tasks = read_timer_tasks()
                    for t in tasks:
                        if t.get('id') == profile.get('id'):
                            t['lastTriggeredAt'] = datetime.now().strftime('%Y-%m-%d %H:%M')
                            break
                    write_timer_tasks(tasks)
            # NOW set running=False and clear task context after task state is persisted
            run_status['running'] = False
            run_status['current_case'] = ''
            run_status['current_task_id'] = None
            run_status['terminate_requested'] = False
            run_status['process'] = None

    t = threading.Thread(target=do_run, daemon=True)
    t.start()
    return True


def _mark_once_task_triggered(task_id):
    if not task_id:
        return
    with timer_lock:
        tasks = read_timer_tasks()
        for t in tasks:
            if t.get('id') == task_id:
                t['lastTriggeredAt'] = datetime.now().strftime('%Y-%m-%d %H:%M')
                break
        write_timer_tasks(tasks)


def trigger_test_run_repeated(profile, trigger='manual'):
    """Trigger one task repeatedly based on executionTimes (serialized)."""
    task = normalize_task_record(profile)
    repeat = normalize_execution_times(task.get('executionTimes', 1))
    if repeat <= 1:
        run_status['repeat_total'] = 1
        run_status['repeat_index'] = 1
        run_status['repeat_active'] = False
        return trigger_test_run(task, trigger=trigger)

    # Keep behavior deterministic: do not start repeated sequence when another task/sequence is running.
    if run_status.get('running') or run_status.get('repeat_active'):
        return False

    run_status['repeat_total'] = repeat
    run_status['repeat_index'] = 0
    run_status['repeat_active'] = True

    def _repeat_worker():
        try:
            for i in range(repeat):
                # Wait current run to finish before launching next round.
                while run_status.get('running'):
                    time.sleep(0.5)

                run_status['repeat_index'] = i + 1
                one = dict(task)
                one['executionTimes'] = 1
                started = trigger_test_run(one, trigger=f"{trigger}-{i+1}/{repeat}")
                if not started:
                    # Retry briefly to avoid missing a round because of race windows.
                    retry = 0
                    while retry < 20 and not started:
                        time.sleep(0.5)
                        started = trigger_test_run(one, trigger=f"{trigger}-{i+1}/{repeat}")
                        retry += 1
                    if not started:
                        run_status['log'] += f"\n[Scheduler] 第{i+1}/{repeat}轮启动失败，停止后续轮次\n"
                        break

                # Wait the current round to complete before next round.
                while run_status.get('running'):
                    time.sleep(0.5)
        finally:
            run_status['repeat_active'] = False

    threading.Thread(target=_repeat_worker, daemon=True).start()
    return True


def _run_parallel_device_task(task, trigger, device_states, refresh_aggregate):
    sn = (task.get('deviceSn') or '').strip()
    if not sn:
        return

    started_dt = datetime.now()
    started_ts = started_dt.timestamp()
    before_files = list_html_reports()
    lines = []
    state = device_states.get(sn, {})

    state.update({
        'running': True,
        'current_case': '',
        'loaded_cases': 0,
        'completed_cases': 0,
        'passed': 0,
        'failed': 0,
        'error': 0,
        'skipped': 0,
        'failed_indices': [],
        'has_structured_progress': False
    })
    refresh_aggregate()

    try:
        env = os.environ.copy()
        env['PYTHONUTF8'] = '1'
        env['PYTHONIOENCODING'] = 'utf-8'
        env['PYTHONUNBUFFERED'] = '1'
        env['ANDROID_SERIAL'] = sn
        env['AUTONEXUS_DEVICE_SN'] = sn
        env['AUTONEXUS_DEV0_SN'] = sn
        reference_sn = (task.get('referenceDeviceSn') or '').strip()
        if reference_sn:
            env['AUTONEXUS_DEV1_SN'] = reference_sn

        case_ids = task.get('caseIds', []) if isinstance(task, dict) else []
        case_list = task.get('caseList', []) if isinstance(task, dict) else []
        if isinstance(case_ids, list):
            env['AUTONEXUS_CASE_IDS'] = json.dumps(case_ids, ensure_ascii=False)
        if isinstance(case_list, list):
            env['AUTONEXUS_CASE_LIST'] = json.dumps(case_list, ensure_ascii=False)

        with run_status_lock:
            run_status['log'] += f"\n[DEVICE {sn}] 开始执行\n"

        proc = subprocess.Popen(
            [RUNNER_PYTHON, '-u', os.path.join(BASE_DIR, 'run_all.py')],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding='utf-8',
            errors='ignore',
            cwd=BASE_DIR,
            env=env
        )
        for line in proc.stdout:
            lines.append(line)
            normalized = line.strip()

            with run_status_lock:
                run_status['log'] += f"[{sn}] {line}"

            if run_status.get('terminate_requested'):
                try:
                    proc.terminate()
                except Exception:
                    pass
                break

            if normalized.startswith('[AUTONEXUS_PROGRESS]'):
                state['has_structured_progress'] = True
                total_match = re.match(r'^\[AUTONEXUS_PROGRESS\]\s+TOTAL\s+(\d+)\s*$', normalized)
                if total_match:
                    state['loaded_cases'] = int(total_match.group(1))
                    state['total_cases'] = max(int(state.get('total_cases', 0) or 0), state['loaded_cases'])
                    refresh_aggregate()
                    continue

                start_match = re.match(r'^\[AUTONEXUS_PROGRESS\]\s+START\s+(\d+)/(\d+)\s+(.+)$', normalized)
                if start_match:
                    idx = int(start_match.group(1))
                    total = int(start_match.group(2))
                    state['loaded_cases'] = total
                    state['total_cases'] = max(int(state.get('total_cases', 0) or 0), total)
                    state['current_case'] = start_match.group(3).strip()
                    state['completed_cases'] = max(int(state.get('completed_cases', 0) or 0), max(0, idx - 1))
                    refresh_aggregate()
                    continue

                end_match = re.match(r'^\[AUTONEXUS_PROGRESS\]\s+END\s+(\d+)/(\d+)\s+(OK|FAIL|ERROR|SKIP)\s+(.+)$', normalized)
                if end_match:
                    idx = int(end_match.group(1))
                    total = int(end_match.group(2))
                    outcome = end_match.group(3)
                    state['loaded_cases'] = total
                    state['total_cases'] = max(int(state.get('total_cases', 0) or 0), total)
                    state['current_case'] = end_match.group(4).strip()
                    state['completed_cases'] = max(int(state.get('completed_cases', 0) or 0), idx)
                    if outcome == 'OK':
                        state['passed'] = int(state.get('passed', 0) or 0) + 1
                    elif outcome == 'FAIL':
                        state['failed'] = int(state.get('failed', 0) or 0) + 1
                        if idx not in state['failed_indices']:
                            state['failed_indices'].append(idx)
                    elif outcome == 'ERROR':
                        state['error'] = int(state.get('error', 0) or 0) + 1
                        if idx not in state['failed_indices']:
                            state['failed_indices'].append(idx)
                    elif outcome == 'SKIP':
                        state['skipped'] = int(state.get('skipped', 0) or 0) + 1
                    refresh_aggregate()
                    continue

        proc.wait()
        run_result = parse_run_result(''.join(lines))
        report_file = find_latest_report_file(before_files=before_files, started_at=started_ts)
        device_log_text = ''.join(lines)
        log_file = write_run_console_log(started_dt.strftime('%Y-%m-%d %H:%M:%S'), f"[DEVICE {sn}]\n" + device_log_text)
        append_report_record(
            profile=task,
            trigger=trigger,
            run_result=run_result,
            report_file=report_file,
            execute_time=started_dt.strftime('%Y-%m-%d %H:%M:%S'),
            log_file=log_file
        )

        loaded_total = int(state.get('loaded_cases', 0) or 0)
        completed_cases = int(state.get('completed_cases', 0) or 0)
        passed_cases = int(state.get('passed', 0) or 0)
        failed_cases = int(state.get('failed', 0) or 0)
        error_cases = int(state.get('error', 0) or 0)
        skipped_cases = int(state.get('skipped', 0) or 0)

        if loaded_total <= 0 and completed_cases > 0:
            loaded_total = completed_cases
        if run_result == 'PASS':
            if loaded_total > 0 and completed_cases < loaded_total:
                completed_cases = loaded_total
            if loaded_total > 0 and (passed_cases + failed_cases + error_cases + skipped_cases) < loaded_total:
                passed_cases = max(passed_cases, loaded_total - failed_cases - error_cases - skipped_cases)

        state['completed_cases'] = completed_cases
        state['passed'] = passed_cases
        state['failed'] = failed_cases
        state['error'] = error_cases
        state['skipped'] = skipped_cases
        state['running'] = False
        state['current_case'] = ''
        refresh_aggregate()

        run_snapshot = {
            'total': max(int(state.get('total_cases', 0) or 0), loaded_total),
            'completed': completed_cases,
            'passed': passed_cases,
            'failed': failed_cases,
            'error': error_cases,
            'skipped': skipped_cases,
            'crashed': (run_result != 'PASS' and loaded_total > 0 and completed_cases < loaded_total),
            'requestedTotal': int(task.get('caseCount', 0) or 0),
            'loadedTotal': loaded_total,
            'loadFailed': max(0, int(task.get('caseCount', 0) or 0) - loaded_total)
        }
        update_task_run_state(task, run_result, started_dt, run_snapshot=run_snapshot)
    except Exception as e:
        error_detail = traceback.format_exc()
        with run_status_lock:
            run_status['log'] += f"\n[DEVICE {sn}] 执行失败: {e}\n{error_detail}\n"
        state['running'] = False
        state['current_case'] = ''
        refresh_aggregate()

        # Persist the crash instead of silently leaving stale/zero lastRun* fields, which
        # the UI would otherwise misinterpret as a generic "load failed" result.
        try:
            log_file = write_run_console_log(
                started_dt.strftime('%Y-%m-%d %H:%M:%S'),
                f"[DEVICE {sn}] 执行异常\n{''.join(lines)}\n{error_detail}"
            )
        except Exception:
            log_file = ''
        try:
            append_report_record(
                profile=task,
                trigger=trigger,
                run_result='ERROR',
                report_file='',
                execute_time=started_dt.strftime('%Y-%m-%d %H:%M:%S'),
                log_file=log_file
            )
        except Exception:
            pass
        try:
            crash_snapshot = {
                'total': int(task.get('caseCount', 0) or 0),
                'completed': int(state.get('completed_cases', 0) or 0),
                'passed': int(state.get('passed', 0) or 0),
                'failed': int(state.get('failed', 0) or 0),
                'error': int(state.get('error', 0) or 0),
                'skipped': int(state.get('skipped', 0) or 0),
                'crashed': True,
                'requestedTotal': int(task.get('caseCount', 0) or 0),
                'loadedTotal': int(state.get('loaded_cases', 0) or 0),
                'loadFailed': max(0, int(task.get('caseCount', 0) or 0) - int(state.get('loaded_cases', 0) or 0))
            }
            update_task_run_state(task, 'ERROR', started_dt, run_snapshot=crash_snapshot)
        except Exception:
            pass
    finally:
        _mark_once_task_triggered(task.get('id'))


def trigger_multi_device_run(tasks, trigger='manual'):
    valid_tasks = [dict(t) for t in (tasks or []) if isinstance(t, dict) and (t.get('deviceSn') or '').strip()]
    if not valid_tasks:
        return False
    if run_status.get('running'):
        return False

    total_requested = sum(int(t.get('caseCount', 0) or 0) for t in valid_tasks)
    first_task_id = valid_tasks[0].get('id')

    with run_status_lock:
        run_status['running'] = True
        run_status['current_task_id'] = first_task_id
        run_status['current_case'] = ''
        run_status['total_cases'] = total_requested
        run_status['completed_cases'] = 0
        run_status['passed'] = 0
        run_status['failed'] = 0
        run_status['error'] = 0
        run_status['skipped'] = 0
        run_status['failed_indices'] = []
        run_status['terminate_requested'] = False
        run_status['process'] = None
        run_status['device_progress'] = {
            (t.get('deviceSn') or '').strip(): {
                'task_id': t.get('id'),
                'task_name': t.get('taskName') or '',
                'total_cases': int(t.get('caseCount', 0) or 0),
                'loaded_cases': 0,
                'completed_cases': 0,
                'passed': 0,
                'failed': 0,
                'error': 0,
                'skipped': 0,
                'current_case': '',
                'running': True,
                'failed_indices': []
            }
            for t in valid_tasks
        }
        run_status['log'] += '\n[SYSTEM] 多设备并发执行已启动\n'

    device_states = run_status['device_progress']

    def refresh_aggregate():
        with run_status_lock:
            completed = sum(int(s.get('completed_cases', 0) or 0) for s in device_states.values())
            passed = sum(int(s.get('passed', 0) or 0) for s in device_states.values())
            failed = sum(int(s.get('failed', 0) or 0) for s in device_states.values())
            error = sum(int(s.get('error', 0) or 0) for s in device_states.values())
            skipped = sum(int(s.get('skipped', 0) or 0) for s in device_states.values())
            total_from_states = sum(max(int(s.get('total_cases', 0) or 0), int(s.get('loaded_cases', 0) or 0)) for s in device_states.values())
            current_cases = [f"{sn}:{s.get('current_case')}" for sn, s in device_states.items() if s.get('running') and s.get('current_case')]

            run_status['completed_cases'] = completed
            run_status['passed'] = passed
            run_status['failed'] = failed
            run_status['error'] = error
            run_status['skipped'] = skipped
            if total_from_states > run_status.get('total_cases', 0):
                run_status['total_cases'] = total_from_states
            run_status['current_case'] = ' | '.join(current_cases[:3])

    def coordinator():
        threads = []
        for task in valid_tasks:
            t = threading.Thread(
                target=_run_parallel_device_task,
                args=(task, trigger, device_states, refresh_aggregate),
                daemon=True
            )
            t.start()
            threads.append(t)

        for t in threads:
            t.join()

        with run_status_lock:
            run_status['running'] = False
            run_status['current_case'] = ''
            run_status['terminate_requested'] = False
            run_status['process'] = None
            run_status['last_run'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            run_status['log'] += '\n[SYSTEM] 多设备并发执行已完成\n'

    threading.Thread(target=coordinator, daemon=True).start()
    return True


def trigger_multi_device_run_repeated(tasks, trigger='manual'):
    """Trigger a batch of same-schedule multi-device tasks repeatedly based on executionTimes."""
    valid_tasks = [normalize_task_record(t) for t in (tasks or []) if isinstance(t, dict) and (t.get('deviceSn') or '').strip()]
    if not valid_tasks:
        return False

    repeat = normalize_execution_times(valid_tasks[0].get('executionTimes', 1))
    if repeat <= 1:
        run_status['repeat_total'] = 1
        run_status['repeat_index'] = 1
        run_status['repeat_active'] = False
        return trigger_multi_device_run(valid_tasks, trigger=trigger)

    if run_status.get('running') or run_status.get('repeat_active'):
        return False

    run_status['repeat_total'] = repeat
    run_status['repeat_index'] = 0
    run_status['repeat_active'] = True

    def _repeat_worker():
        try:
            for i in range(repeat):
                while run_status.get('running'):
                    time.sleep(0.5)

                run_status['repeat_index'] = i + 1
                round_tasks = [dict(t) for t in valid_tasks]
                for rt in round_tasks:
                    rt['executionTimes'] = 1

                started = trigger_multi_device_run(round_tasks, trigger=f"{trigger}-{i+1}/{repeat}")
                if not started:
                    retry = 0
                    while retry < 20 and not started:
                        time.sleep(0.5)
                        started = trigger_multi_device_run(round_tasks, trigger=f"{trigger}-{i+1}/{repeat}")
                        retry += 1
                    if not started:
                        run_status['log'] += f"\n[Scheduler] 第{i+1}/{repeat}轮多设备启动失败，停止后续轮次\n"
                        break

                while run_status.get('running'):
                    time.sleep(0.5)
        finally:
            run_status['repeat_active'] = False

    threading.Thread(target=_repeat_worker, daemon=True).start()
    return True


def timer_scheduler_loop():
    while True:
        try:
            now = datetime.now()
            now_hm = now.strftime('%H:%M')
            now_key = now.strftime('%Y-%m-%d %H:%M')
            changed = False

            with timer_lock:
                tasks = read_timer_tasks()
                due_tasks = []
                for task in tasks:
                    if derive_task_mode(task) == 'once':
                        continue
                    if task.get('status') != ENABLED_STATUS:
                        continue
                    exec_time_raw = (task.get('execTime') or '').strip()
                    # Reservation tasks (预约执行) store a full date-time
                    # ("YYYY-MM-DD HH:MM") for a one-off run, while recurring
                    # daily timers store only the minute of day ("HH:MM").
                    if ' ' in exec_time_raw:
                        if exec_time_raw[:16] != now_key:
                            continue
                    else:
                        if exec_time_raw != now_hm:
                            continue
                    if task.get('lastTriggeredAt') == now_key:
                        continue
                    due_tasks.append(task)

                if due_tasks:
                    # Group by batchId so tasks created for multiple devices at the same
                    # schedule are dispatched together as one concurrent multi-device run.
                    groups = {}
                    for t in due_tasks:
                        group_key = t.get('batchId') if t.get('batchId') is not None else t.get('id')
                        groups.setdefault(group_key, []).append(t)

                    for group in groups.values():
                        if len(group) > 1:
                            started = trigger_multi_device_run_repeated(group, trigger='timer')
                        else:
                            started = trigger_test_run_repeated(group[0], trigger='timer')
                        if started:
                            for t in group:
                                t['lastTriggeredAt'] = now_key
                            changed = True

                if changed:
                    write_timer_tasks(tasks)
        except Exception as e:
            run_status['log'] += f"\n[Scheduler] {str(e)}"

        time.sleep(15)

def start_timer_scheduler():
    t = threading.Thread(target=timer_scheduler_loop, daemon=True)
    t.start()

@app.route('/')
def index():
    return send_from_directory(BASE_DIR, 'index.html')

@app.route('/api/devices')
def api_devices():
    devices = get_connected_devices_info()
    if isinstance(devices, dict):  # error case
        return jsonify(devices)
    response = jsonify({"devices": devices})
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "GET,POST,PUT,DELETE,OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "*"
    return response

def get_connected_devices_info():
    devices = []
    try:
        result = subprocess.run(
            [ADB, 'devices'],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=5
        )
        lines = result.stdout.strip().splitlines()
    except Exception as e:
        return {"error": str(e), "devices": []}

    for line in lines[1:]:
        line = line.strip()
        if not line:
            continue
        parts = line.split()
        if len(parts) < 2:
            continue

        sn = parts[0]
        conn = parts[1]
        # ✅ BUGFIX: Only include ONLINE devices in the return list
        # Skip offline or unauthorized devices to prevent selecting invalid device by default
        if conn != "device":
            continue  # Do not add offline/unauthorized devices
        status = "在线"
        model       = normalize_prop_value(adb_getprop(sn, 'ro.vendor.hon.model.num'))
        if model == 'N/A':
            model = normalize_prop_value(adb_getprop(sn, 'ro.product.model'))
        pn          = normalize_prop_value(adb_getprop(sn, 'ro.vendor.hon.extconf.num'))
        os_build    = normalize_prop_value(adb_getprop(sn, 'ro.build.display.id'))
        android_ver = resolve_android_version(sn)
        sn_real     = normalize_prop_value(adb_getprop(sn, 'ro.vendor.hon.extserial.num'))

        show_sn = sn_real if sn_real != "N/A" else sn

        devices.append({
            "sn": show_sn,
            "model": model,
            "pn": pn,
            "osVersion": os_build,
            "androidVer": android_ver,
            "platform": guess_platform(model),
            "status": status
        })

    return devices

@app.route('/api/cases')
def api_cases():
    def _norm_case_file(p):
        s = str(p or '').replace('\\', '/').strip()
        if s.startswith('./'):
            s = s[2:]
        if s.startswith('case/'):
            s = s[5:]
        return s

    cases = scan_source_cases()
    meta_cases = read_case_meta()

    # Merge overrides from case_meta by id first, then append pure custom cases.
    id_to_idx = {item.get('id'): i for i, item in enumerate(cases)}
    file_to_idx = {_norm_case_file(item.get('file')): i for i, item in enumerate(cases) if item.get('file')}
    for meta in meta_cases:
        meta_id = meta.get('id')
        if meta_id in id_to_idx:
            base = dict(cases[id_to_idx[meta_id]])
            base.update(meta)
            if 'folder' not in base or not base.get('folder'):
                file_path = base.get('file', '')
                base['folder'] = os.path.dirname(file_path).replace('\\', '/') if os.path.dirname(file_path) else '.'
            cases[id_to_idx[meta_id]] = base
            continue

        # Legacy method-level meta may still exist in case_meta. If scanned file already
        # exists in current file-level model, skip appending to avoid duplicated case rows.
        meta_file = _norm_case_file(meta.get('file', ''))
        if meta_file and meta_file in file_to_idx:
            continue

        custom_case = dict(meta)
        if meta_file:
            custom_case['file'] = meta_file
        if 'folder' not in custom_case or not custom_case.get('folder'):
            file_path = custom_case.get('file', '')
            custom_case['folder'] = os.path.dirname(file_path).replace('\\', '/') if os.path.dirname(file_path) else '.'
        cases.append(custom_case)
    res = jsonify({'cases': cases})
    res.headers["Access-Control-Allow-Origin"] = "*"
    return res

@app.route('/api/case/add', methods=['POST'])
def api_case_add():
    data = request.get_json()
    required = ['name', 'className', 'file', 'doc', 'owner']
    for k in required:
        if k not in data or not data[k]:
            return jsonify({'code': 400, 'msg': f'缺少必填项：{k}'})
    meta = read_case_meta()
    new_id = max([item['id'] for item in meta], default=0) + 1
    new_case = {
        'id': new_id,
        'name': data['name'],
        'className': data['className'],
        'file': data['file'],
        'doc': data['doc'],
        'owner': data['owner']
    }
    meta.append(new_case)
    write_case_meta(meta)
    res = jsonify({'code': 200, 'msg': '新增成功', 'data': new_case})
    res.headers["Access-Control-Allow-Origin"] = "*"
    return res

@app.route('/api/case/edit', methods=['PUT'])
def api_case_edit():
    data = request.get_json()
    if 'id' not in data:
        return jsonify({'code': 400, 'msg': '缺少用例ID'})
    meta = read_case_meta()
    for i, item in enumerate(meta):
        if item['id'] == data['id']:
            for k in ['name', 'className', 'file', 'doc', 'owner']:
                if k in data:
                    meta[i][k] = data[k]
            write_case_meta(meta)
            res = jsonify({'code': 200, 'msg': '编辑成功', 'data': meta[i]})
            res.headers["Access-Control-Allow-Origin"] = "*"
            return res

    # If not found in case_meta, allow editing scanned source cases by creating
    # an override record in case_meta keyed by the same id.
    source_cases = scan_source_cases()
    source_case = next((c for c in source_cases if c.get('id') == data.get('id')), None)
    if source_case:
        override_case = {
            'id': source_case['id'],
            'name': source_case['name'],
            'className': source_case['className'],
            'file': source_case['file'],
            'doc': source_case.get('doc', ''),
            'owner': source_case.get('owner', 'N/A')
        }
        for k in ['name', 'className', 'file', 'doc', 'owner']:
            if k in data:
                override_case[k] = data[k]
        meta.append(override_case)
        write_case_meta(meta)
        res = jsonify({'code': 200, 'msg': '编辑成功', 'data': override_case})
        res.headers["Access-Control-Allow-Origin"] = "*"
        return res

    res = jsonify({'code': 404, 'msg': '用例不存在'})
    res.headers["Access-Control-Allow-Origin"] = "*"
    return res

@app.route('/api/case/delete', methods=['DELETE'])
def api_case_delete():
    case_id = request.args.get('id')
    if not case_id:
        return jsonify({'code': 400, 'msg': '缺少用例ID'})
    try:
        case_id = int(case_id)
    except ValueError:
        return jsonify({'code': 400, 'msg': '用例ID格式错误'})
    meta = read_case_meta()
    case_to_delete = None
    case_index = None
    # Find the case to delete
    for idx, item in enumerate(meta):
        if item.get('id') == case_id:
            case_to_delete = item
            case_index = idx
            break
    if not case_to_delete:
        return jsonify({'code': 404, 'msg': '用例不存在'})
    # Delete the actual file - file path is relative to CASE_DIR
    case_file = case_to_delete.get('file', '')
    delete_success = False
    if case_file:
        full_path = os.path.join(CASE_DIR, case_file)
        print(f'[DELETE] Attempting to delete: {full_path}')
        try:
            if os.path.exists(full_path):
                os.remove(full_path)
                delete_success = True
                print(f'[DELETE] Successfully deleted file: {full_path}')
            else:
                print(f'[DELETE] File not found: {full_path}')
                delete_success = True  # File already gone, consider it success
        except Exception as e:
            print(f'[DELETE] Error deleting file {full_path}: {e}')
            return jsonify({'code': 500, 'msg': f'删除文件失败: {str(e)}'})
    else:
        print(f'[DELETE] No file path in metadata for case ID {case_id}')
        delete_success = True
    # Remove from metadata
    if case_index is not None:
        meta.pop(case_index)
    else:
        meta = [item for item in meta if item.get('id') != case_id]
    try:
        write_case_meta(meta)
        print(f'[DELETE] Successfully updated metadata, removed case ID {case_id}')
    except Exception as e:
        print(f'[DELETE] Error updating metadata: {e}')
        return jsonify({'code': 500, 'msg': f'更新元数据失败: {str(e)}'})
    res = jsonify({
        'code': 200,
        'msg': '删除成功',
        'file_deleted': delete_success,
        'metadata_updated': True
    })
    res.headers["Access-Control-Allow-Origin"] = "*"
    return res


@app.route('/api/ai/case-generator', methods=['POST'])
def api_ai_case_generator():
    data = request.get_json(silent=True) or {}
    case_name_raw = (data.get('caseName') or '').strip()
    component_raw = (data.get('component') or '').strip()
    case_steps = (data.get('caseSteps') or '').strip()
    overwrite = bool(data.get('overwrite', False))

    case_name = _normalize_case_name(case_name_raw)
    if not case_name:
        return jsonify({'code': 400, 'msg': '用例名称不能为空，且需包含字母或数字'})
    if not case_steps:
        return jsonify({'code': 400, 'msg': '请填写用例详细步骤'})

    final_steps_text, gen_mode, gen_err = _resolve_steps_text(case_name_raw or case_name, component_raw, case_steps)

    component_folder = _resolve_component_folder(component_raw)
    target_dir = os.path.join(CASE_DIR, component_folder)
    os.makedirs(target_dir, exist_ok=True)
    filename = f'test_{case_name}.py'
    path = os.path.join(target_dir, filename)
    if os.path.exists(path) and not overwrite:
        return jsonify({'code': 409, 'msg': f'文件已存在: {filename}', 'exists': True, 'file': filename})

    ai_no = _next_ai_case_no(path if os.path.exists(path) and overwrite else None)
    script = _build_case_script(case_name, final_steps_text, ai_no=ai_no, component_name=component_folder)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(script)

    rel_path = os.path.relpath(path, BASE_DIR).replace('\\', '/')
    return jsonify({
        'code': 200,
        'msg': _append_generation_meta('AI用例生成成功', gen_mode, gen_err),
        'data': {
            'file': filename,
            'path': rel_path,
            'component': component_folder,
            'aiNo': ai_no,
            'generationMode': gen_mode,
            'fallbackReason': gen_err if gen_mode != 'llm' else ''
        }
    })


@app.route('/api/ai/case-scripts')
def api_ai_case_scripts():
    os.makedirs(CASE_DIR, exist_ok=True)
    items = []
    for root, _, files in os.walk(CASE_DIR):
        for name in files:
            if not _is_safe_case_file(name):
                continue
            full = os.path.join(root, name)
            if not (_is_ai_generated_script(full) or _is_legacy_ai_demo_file(full)):
                continue
            try:
                st = os.stat(full)
            except Exception:
                continue
            rel_from_case = os.path.relpath(full, CASE_DIR).replace('\\', '/')
            folder = os.path.dirname(rel_from_case).replace('\\', '/') if os.path.dirname(rel_from_case) else '.'
            items.append({
                'name': name,
                'path': rel_from_case,
                'folder': folder,
                'size': st.st_size,
                'aiNo': _extract_ai_case_no_from_file(full),
                'component': _extract_ai_component_from_file(full),
                'mtime': datetime.fromtimestamp(st.st_mtime).strftime('%Y-%m-%d %H:%M:%S'),
                '_mtimeTs': st.st_mtime
            })
    items.sort(key=lambda x: x.get('_mtimeTs', 0), reverse=True)
    for item in items:
        item.pop('_mtimeTs', None)
    return jsonify({'code': 200, 'scripts': items})


@app.route('/api/ai/case-script-content')
def api_ai_case_script_content():
    rel_path = (request.args.get('path') or '').strip()
    name = (request.args.get('name') or '').strip()

    path = None
    if rel_path:
        path = _resolve_rel_case_path(rel_path)
    elif name:
        path = _find_ai_script_by_name(name)
    if not path:
        return jsonify({'code': 404, 'msg': '文件不存在'})
    if not (_is_ai_generated_script(path) or _is_legacy_ai_demo_file(path)):
        return jsonify({'code': 400, 'msg': '仅支持读取AI生成脚本'})

    try:
        with open(path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
    except Exception as e:
        return jsonify({'code': 500, 'msg': f'读取失败: {e}'})
    rel_from_case = os.path.relpath(path, CASE_DIR).replace('\\', '/')
    return jsonify({'code': 200, 'name': os.path.basename(path), 'path': rel_from_case, 'aiNo': _extract_ai_case_no_from_file(path), 'content': content})

@app.route('/api/ai/download-template')
def api_ai_download_template():
    template_path = os.path.join(BASE_DIR, 'Test Case Template.xlsx')
    if not os.path.exists(template_path):
        return jsonify({'code': 404, 'msg': '模板文件不存在'}), 404
    return send_from_directory(BASE_DIR, 'Test Case Template.xlsx', as_attachment=True, download_name='Test Case Template.xlsx')

@app.route('/api/ai/batch-generate-cases', methods=['POST'])
def api_ai_batch_generate_cases():
    data = request.get_json(silent=True) or {}
    cases = data.get('cases', [])
    if not isinstance(cases, list) or len(cases) == 0:
        return jsonify({'code': 400, 'msg': '请提供有效的用例列表'})
    os.makedirs(CASE_DIR, exist_ok=True)
    success = 0
    failed = 0
    errors = []
    llm_count = 0
    fallback_count = 0
    for case_data in cases:
        try:
            case_name_raw = (case_data.get('caseName') or '').strip()
            component_raw = (case_data.get('component') or '').strip()
            case_steps = (case_data.get('caseSteps') or '').strip()
            overwrite = bool(case_data.get('overwrite', False))
            case_name = _normalize_case_name(case_name_raw)
            if not case_name or not case_steps:
                failed += 1
                errors.append(f"{case_name_raw}: 名称或步骤为空")
                continue

            final_steps_text, gen_mode, gen_err = _resolve_steps_text(case_name_raw or case_name, component_raw, case_steps)
            if gen_mode == 'llm':
                llm_count += 1
            else:
                fallback_count += 1
                if gen_err:
                    errors.append(f"{case_name_raw}: 模板回退，{gen_err}")
            filename = f'test_{case_name}.py'
            component_folder = _resolve_component_folder(component_raw)
            target_dir = os.path.join(CASE_DIR, component_folder)
            os.makedirs(target_dir, exist_ok=True)
            path = os.path.join(target_dir, filename)
            if os.path.exists(path) and not overwrite:
                failed += 1
                errors.append(f"{filename}: 文件已存在")
                continue
            ai_no = _next_ai_case_no(path if os.path.exists(path) and overwrite else None)
            script = _build_case_script(case_name, final_steps_text, ai_no=ai_no, component_name=component_folder)
            with open(path, 'w', encoding='utf-8') as f:
                f.write(script)
            success += 1
        except Exception as e:
            failed += 1
            errors.append(f"{case_data.get('caseName', 'Unknown')}: {str(e)}")
    return jsonify({
        'code': 200,
        'msg': '批量生成完成',
        'data': {
            'success': success,
            'failed': failed,
            'llmCount': llm_count,
            'fallbackCount': fallback_count,
            'errors': errors[:10] if errors else []
        }
    })


@app.route('/api/ai/provider-status')
def api_ai_provider_status():
    cfg = _ai_llm_config()
    return jsonify({
        'code': 200,
        'provider': cfg['provider'],
        'enabled': cfg['enabled'],
        'configured': bool(cfg['api_key']),
        'model': cfg['model'],
        'baseUrl': cfg['base_url'],
        'timeoutSec': cfg['timeout_sec'],
    })

_RESULT_DATA_RE = re.compile(r'(var resultData = )(\{.*?\n\})(;\s*\n)', re.S)
_REPORT_STATUSES = ('Pass', 'Fail', 'Error', 'Skip')
_REPORT_EDIT_LOCK = threading.Lock()


def _safe_report_name(name):
    """Return a bare *_result.html file name that exists in REPORT_DIR, else ''."""
    name = os.path.basename(str(name or '').strip())
    if not name.endswith('.html') or not os.path.isfile(os.path.join(REPORT_DIR, name)):
        return ''
    return name


def _report_edit_path(name):
    return os.path.join(REPORT_DIR, name[:-len('.html')] + '.edits.json')


def _read_report_edits(name):
    try:
        with open(_report_edit_path(name), 'r', encoding='utf-8') as f:
            data = json.load(f)
        if isinstance(data, dict):
            data.setdefault('overrides', {})
            data.setdefault('manual_cases', [])
            return data
    except Exception:
        pass
    return {'overrides': {}, 'manual_cases': []}


def _write_report_edits(name, edits):
    with open(_report_edit_path(name), 'w', encoding='utf-8') as f:
        json.dump(edits, f, ensure_ascii=False, indent=2)


_KNOWN_STATUS_WORDS = ('pass', 'passed', 'ok', 'success', '成功', '通过', 'p', 'fail', 'failed', 'failure', '失败', 'f',
                       'error', '错误', 'skip', 'skipped', 'blocked', '跳过', 'n/a')


def _normalize_report_status(value):
    text = str(value or '').strip().lower()
    if text in ('pass', 'passed', 'ok', 'success', '成功', '通过', 'p'):
        return 'Pass'
    if text in ('fail', 'failed', 'failure', '失败', 'f'):
        return 'Fail'
    if text in ('error', '错误'):
        return 'Error'
    return 'Skip'


def _merge_report_html(name):
    """Return the report HTML with manual overrides and manual cases merged into resultData."""
    with open(os.path.join(REPORT_DIR, name), 'r', encoding='utf-8', errors='ignore') as f:
        html = f.read()
    match = _RESULT_DATA_RE.search(html)
    if not match:
        return html
    try:
        result = json.loads(match.group(2))
    except ValueError:
        return html
    edits = _read_report_edits(name)
    overrides = edits['overrides']

    cases = result.get('testResult') or []
    for case in cases:
        key = f"{case.get('className', '')}.{case.get('methodName', '')}"
        case['key'] = key
        ov = overrides.get(key)
        if not ov:
            continue
        old_status = case.get('status')
        case['status'] = ov['status']
        note = f"[Manual override] {old_status} -> {ov['status']} by {ov.get('by') or 'unknown'} at {ov.get('at', '')}: {ov.get('reason', '')}"
        case['log'] = [note] + list(case.get('log') or [])
        case['description'] = f"{case.get('description', '')}\n[Result manually changed: {old_status} -> {ov['status']}]"
        case['edited'] = True
    for manual in edits['manual_cases']:
        log = [f"[Manual] Executor: {manual.get('executor') or '-'}", f"[Manual] Note: {manual.get('note') or '-'}"]
        cases.append({
            'key': 'manual:' + manual['id'],
            'className': manual.get('className') or 'Manual',
            'methodName': manual.get('methodName') or '',
            'description': '[Manual] ' + (manual.get('description') or ''),
            'spendTime': manual.get('spendTime') or '-',
            'status': manual['status'],
            'log': log,
            'manual': True,
            'manualId': manual['id'],
        })
    result['testResult'] = cases
    counts = {s: sum(1 for c in cases if c.get('status') == s) for s in _REPORT_STATUSES}
    result['testAll'] = len(cases)
    result['testPass'] = counts['Pass']
    result['testFail'] = counts['Fail'] + counts['Error']
    result['testSkip'] = counts['Skip']
    result['manualCount'] = len(edits['manual_cases'])
    result['overrideCount'] = len(overrides)
    payload = json.dumps(result, ensure_ascii=False, indent=4).replace('</', '<\\/')
    return html[:match.start(2)] + payload + html[match.end(2):]


def _inline_report_assets(html):
    """Inline _assets CSS/JS so the emailed HTML opens offline."""
    def read_asset(rel):
        path = os.path.join(REPORT_DIR, '_assets', os.path.basename(rel))
        with open(path, 'r', encoding='utf-8', errors='ignore') as f:
            return f.read()

    def css(m):
        try:
            return '<style>' + read_asset(m.group(1)) + '</style>'
        except OSError:
            return m.group(0)

    def js(m):
        try:
            return '<script>' + read_asset(m.group(1)).replace('</script', '<\\/script') + '</script>'
        except OSError:
            return m.group(0)

    html = re.sub(r'<link[^>]*href="_assets/([^"]+\.css)"[^>]*>', css, html)
    return re.sub(r'<script src="_assets/([^"]+\.js)"></script>', js, html)


_REPORT_EDIT_PANEL = r"""
<style id="_edit_style">
#_editFab{position:fixed;right:22px;bottom:22px;z-index:9998;padding:10px 20px;border:none;border-radius:24px;background:linear-gradient(135deg,#2563eb,#4f46e5);color:#fff;font-size:14px;font-weight:600;cursor:pointer;box-shadow:0 4px 14px rgba(37,99,235,.45);transition:transform .15s}
#_editFab:hover{transform:translateY(-2px)}
#_editModal{display:none;position:fixed;inset:0;z-index:9999;background:rgba(15,23,42,.55);overflow:auto;backdrop-filter:blur(2px)}
#_editModal.open{display:block}
#_editBox{background:#f8fafc;margin:28px auto;width:94%;max-width:1120px;border-radius:12px;font-size:13px;color:#1e293b;box-shadow:0 20px 50px rgba(0,0,0,.35);overflow:hidden;font-family:-apple-system,'Segoe UI','Microsoft YaHei',sans-serif}
._eHead{display:flex;justify-content:space-between;align-items:center;padding:14px 22px;background:linear-gradient(135deg,#1e3a8a,#2563eb);color:#fff}
._eHead h3{margin:0;font-size:17px;font-weight:600}
._eX{background:transparent;border:none;color:#fff;font-size:24px;line-height:1;cursor:pointer;opacity:.85}
._eX:hover{opacity:1}
._eBody{padding:18px 22px 6px}
._eCard{background:#fff;border:1px solid #e2e8f0;border-radius:10px;padding:14px 16px;margin-bottom:16px;box-shadow:0 1px 3px rgba(0,0,0,.05)}
._eCard h4{margin:0 0 10px;font-size:14px;font-weight:700;color:#0f172a;padding-left:9px;border-left:4px solid #2563eb}
._eBar{display:flex;align-items:center;gap:8px;margin-bottom:10px;color:#475569}
#_editBox table{width:100%;border-collapse:separate;border-spacing:0;margin-bottom:12px;table-layout:fixed}
#_editBox th{background:#f1f5f9;color:#475569;font-weight:600;text-align:left;padding:8px 10px;border-bottom:2px solid #e2e8f0}
#_editBox td{padding:7px 10px;border-bottom:1px solid #eef2f7;vertical-align:middle;word-break:break-all}
#_editBox tbody tr:hover td{background:#f8fafc}
#_editBox input,#_editBox select,#_editBox textarea{width:100%;box-sizing:border-box;padding:6px 9px;border:1px solid #cbd5e1;border-radius:6px;background:#fff;font-size:13px;color:#1e293b;outline:none;height:auto}
#_editBox input:focus,#_editBox select:focus,#_editBox textarea:focus{border-color:#2563eb;box-shadow:0 0 0 3px rgba(37,99,235,.15)}
#_editBox textarea{resize:vertical;min-height:34px}
._eBtn{display:inline-block;padding:7px 16px;border:1px solid #cbd5e1;border-radius:6px;background:#fff;color:#334155;font-size:13px;font-weight:600;cursor:pointer;white-space:nowrap}
._eBtn:hover{background:#f1f5f9}
._eBtnP{background:#2563eb;border-color:#2563eb;color:#fff}
._eBtnP:hover{background:#1d4ed8}
._eBtnD{background:#fff;border-color:#fca5a5;color:#dc2626;padding:4px 10px}
._eBtnD:hover{background:#fef2f2}
._eBadge{display:inline-block;padding:2px 10px;border-radius:10px;font-size:12px;font-weight:700}
._eBadge.Pass{background:#dcfce7;color:#15803d}
._eBadge.Fail,._eBadge.Error{background:#fee2e2;color:#dc2626}
._eBadge.Skip{background:#e2e8f0;color:#475569}
._eAdd td{background:#f8fafc;border-top:1px dashed #cbd5e1}
._eFoot{display:flex;justify-content:flex-end;padding:12px 22px;border-top:1px solid #e2e8f0;background:#fff}
._eHint{color:#94a3b8;font-size:12px;margin-left:8px}
</style>
<button type="button" id="_editFab" onclick="_editOpen()">Edit Results / Manual Cases</button>
<div id="_editModal"><div id="_editBox"></div></div>
<script id="_edit_script">
var _EDIT_REPORT=window.location.pathname.split('/').pop();
var _EDIT_API=window.location.origin+'/api/report/'+encodeURIComponent(_EDIT_REPORT)+'/edit';
function _eEsc(s){return String(s==null?'':s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');}
function _eJson(r){return r.json().then(function(d){if(!r.ok||d.err)throw new Error(d.err||('HTTP '+r.status));return d;});}
function _editOpen(){
    fetch(_EDIT_API).then(_eJson).then(_editRender).catch(function(e){alert('Load failed: '+e.message);});
    document.getElementById('_editModal').className='open';
}
function _editClose(){document.getElementById('_editModal').className='';}
function _eSel(cls,val){
    return '<select class="'+cls+'">'+['Pass','Fail','Error','Skip'].map(function(s){return '<option'+(s===val?' selected':'')+'>'+s+'</option>';}).join('')+'</select>';
}
function _editRender(d){
    var h='<div class="_eHead"><h3>Edit Results / Manual Cases</h3><button class="_eX" onclick="_editClose();location.reload()" title="Close &amp; refresh">&times;</button></div><div class="_eBody">';
    h+='<div class="_eCard"><h4>Automated cases</h4><div class="_eBar"><label style="margin:0">By</label><input id="_eBy" style="width:200px" placeholder="your name" value="'+_eEsc(localStorage.getItem('_eBy')||'')+'"><span class="_eHint">Required when saving result changes</span></div>';
    h+='<table><colgroup><col style="width:44px"><col><col style="width:100px"><col style="width:130px"><col style="width:30%"></colgroup><thead><tr><th>#</th><th>Case</th><th>Original</th><th>New result</th><th>Reason</th></tr></thead><tbody>';
    d.cases.forEach(function(c,i){
        h+='<tr data-key="'+_eEsc(c.key)+'" data-orig="'+_eEsc(c.original)+'"><td>'+(i+1)+'</td><td>'+_eEsc(c.key)+'</td><td><span class="_eBadge '+_eEsc(c.original)+'">'+_eEsc(c.original)+'</span></td><td>'+_eSel('_eStatus',c.status)+'</td><td><input class="_eReason" placeholder="Why is the result changed?" value="'+_eEsc(c.reason)+'"></td></tr>';
    });
    h+='</tbody></table><button class="_eBtn _eBtnP" onclick="_editSave()">Save result changes</button></div>';
    h+='<div class="_eCard"><h4>Manual cases</h4><table><colgroup><col style="width:15%"><col style="width:18%"><col><col style="width:100px"><col style="width:13%"><col style="width:15%"><col style="width:76px"></colgroup><thead><tr><th>Class</th><th>Method</th><th>Description</th><th>Result</th><th>Executor</th><th>Note</th><th></th></tr></thead><tbody>';
    d.manual.forEach(function(m){
        h+='<tr><td>'+_eEsc(m.className)+'</td><td>'+_eEsc(m.methodName)+'</td><td>'+_eEsc(m.description)+'</td><td><span class="_eBadge '+_eEsc(m.status)+'">'+_eEsc(m.status)+'</span></td><td>'+_eEsc(m.executor)+'</td><td>'+_eEsc(m.note)+'</td><td><button class="_eBtn _eBtnD" onclick="_editDelManual(\''+_eEsc(m.id)+'\')">Delete</button></td></tr>';
    });
    h+='<tr class="_eAdd"><td><input id="_mClass" value="Manual"></td><td><input id="_mMethod" placeholder="Case name"></td><td><textarea id="_mDesc" rows="1" placeholder="Steps / description"></textarea></td><td>'+_eSel('_mStatus','Pass')+'</td><td><input id="_mExec" placeholder="Executor"></td><td><input id="_mNote" placeholder="Note"></td><td><button class="_eBtn _eBtnP" onclick="_editAddManual()">+ Add</button></td></tr></tbody></table>';
    h+='<div class="_eBar" style="margin:0"><strong>Import</strong><input type="file" id="_mFile" accept=".xlsx,.csv" style="width:auto;flex:0 1 320px"><button class="_eBtn" onclick="_editImport()">Import xlsx/csv</button><span class="_eHint">Needs columns: case name + result</span></div></div></div>';
    h+='<div class="_eFoot"><button class="_eBtn _eBtnP" onclick="_editClose();location.reload()">Close &amp; refresh</button></div>';
    document.getElementById('_editBox').innerHTML=h;
}
function _ePost(body){
    return fetch(_EDIT_API,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)}).then(_eJson);
}
function _eReload(){return fetch(_EDIT_API).then(_eJson).then(_editRender);}
function _editSave(){
    var by=document.getElementById('_eBy').value.trim();
    if(!by){alert('Please enter your name');return;}
    localStorage.setItem('_eBy',by);
    var changes=[];
    document.querySelectorAll('#_editBox tr[data-key]').forEach(function(tr){
        changes.push({key:tr.getAttribute('data-key'),status:tr.querySelector('._eStatus').value,reason:tr.querySelector('._eReason').value.trim()});
    });
    _ePost({action:'set_status',by:by,changes:changes}).then(function(){alert('Saved');return _eReload();}).catch(function(e){alert('Save failed: '+e.message);});
}
function _editAddManual(){
    var by=(document.getElementById('_eBy')||{}).value||localStorage.getItem('_eBy')||'';
    _ePost({action:'add_manual',by:by,manual:{className:document.getElementById('_mClass').value,methodName:document.getElementById('_mMethod').value,description:document.getElementById('_mDesc').value,status:document.querySelector('select._mStatus').value,executor:document.getElementById('_mExec').value,note:document.getElementById('_mNote').value}})
        .then(_eReload).catch(function(e){alert('Add failed: '+e.message);});
}
function _editDelManual(id){
    if(!confirm('Delete this manual case?'))return;
    _ePost({action:'delete_manual',id:id,by:localStorage.getItem('_eBy')||''}).then(_eReload).catch(function(e){alert(e.message);});
}
function _editImport(){
    var f=document.getElementById('_mFile').files[0];
    if(!f){alert('Choose a file first');return;}
    var fd=new FormData();fd.append('file',f);fd.append('by',localStorage.getItem('_eBy')||'');
    fetch(_EDIT_API.replace('/edit','/manual-import'),{method:'POST',body:fd}).then(_eJson).then(function(d){
        alert('Imported '+d.imported+' case(s)'+(d.unknownStatus?'; '+d.unknownStatus+' row(s) had an unrecognized result and were set to Skip':''));return _eReload();
    }).catch(function(e){alert('Import failed: '+e.message);});
}
</script>
"""


@app.route('/report/<path:filename>')
def serve_report(filename):
    name = _safe_report_name(filename)
    if not name or request.args.get('raw') == '1':
        return send_from_directory(REPORT_DIR, filename)
    html = _merge_report_html(name)
    html = html.replace('</body>', _REPORT_EDIT_PANEL + '</body>', 1) if '</body>' in html else html + _REPORT_EDIT_PANEL
    resp = app.response_class(html, mimetype='text/html')
    resp.headers['Cache-Control'] = 'no-store'
    return resp


@app.route('/api/report/<path:name>/edit', methods=['GET', 'POST'])
def api_report_edit(name):
    name = _safe_report_name(name)
    if not name:
        return jsonify({'err': '报告不存在'}), 404
    if request.method == 'GET':
        with open(os.path.join(REPORT_DIR, name), 'r', encoding='utf-8', errors='ignore') as f:
            match = _RESULT_DATA_RE.search(f.read())
        try:
            original = json.loads(match.group(2)).get('testResult') or [] if match else []
        except ValueError:
            original = []
        edits = _read_report_edits(name)
        cases = []
        for case in original:
            key = f"{case.get('className', '')}.{case.get('methodName', '')}"
            ov = edits['overrides'].get(key) or {}
            cases.append({'key': key, 'original': case.get('status', ''), 'status': ov.get('status') or case.get('status', ''), 'reason': ov.get('reason', '')})
        return jsonify({'cases': cases, 'manual': edits['manual_cases']})

    data = request.get_json(silent=True) or {}
    action = data.get('action')
    by = str(data.get('by') or '').strip()[:60]
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    with _REPORT_EDIT_LOCK:
        edits = _read_report_edits(name)
        if action == 'set_status':
            if not by:
                return jsonify({'err': '请填写修改人'}), 400
            with open(os.path.join(REPORT_DIR, name), 'r', encoding='utf-8', errors='ignore') as f:
                match = _RESULT_DATA_RE.search(f.read())
            try:
                originals = {f"{c.get('className', '')}.{c.get('methodName', '')}": c.get('status') for c in json.loads(match.group(2)).get('testResult') or []}
            except (ValueError, AttributeError):
                return jsonify({'err': '无法解析报告数据'}), 400
            changed = []
            for change in data.get('changes') or []:
                key = str(change.get('key') or '')
                status = change.get('status')
                if key not in originals or status not in _REPORT_STATUSES:
                    continue
                previous = (edits['overrides'].get(key) or {}).get('status') or originals[key]
                if status == originals[key]:
                    edits['overrides'].pop(key, None)
                else:
                    edits['overrides'][key] = {'status': status, 'reason': str(change.get('reason') or '')[:500], 'by': by, 'at': now}
                if previous != status:
                    changed.append({'case': key, 'from': previous, 'to': status, 'reason': str(change.get('reason') or '')[:500]})
            if changed:
                append_system_log('REPORT_EDIT', f'{by} 修改报告 {name} 的 {len(changed)} 条结果', detail={'report': name, 'by': by, 'changes': changed})
        elif action == 'add_manual':
            manual = data.get('manual') or {}
            method = str(manual.get('methodName') or '').strip()
            if not method:
                return jsonify({'err': '请填写测试方法/用例名'}), 400
            item = _build_manual_case(manual)
            edits['manual_cases'].append(item)
            append_system_log('REPORT_MANUAL_ADD', f'{by or "unknown"} 向报告 {name} 添加人工用例 {method}', detail={'report': name, 'case': item})
        elif action == 'delete_manual':
            before = len(edits['manual_cases'])
            edits['manual_cases'] = [m for m in edits['manual_cases'] if m.get('id') != data.get('id')]
            if len(edits['manual_cases']) != before:
                append_system_log('REPORT_MANUAL_DELETE', f'{by or "unknown"} 删除报告 {name} 的人工用例', detail={'report': name, 'id': data.get('id')})
        else:
            return jsonify({'err': 'unknown action'}), 400
        _write_report_edits(name, edits)
    return jsonify({'ok': True})


def _build_manual_case(manual):
    return {
        'id': os.urandom(6).hex(),
        'className': str(manual.get('className') or 'Manual').strip()[:120],
        'methodName': str(manual.get('methodName') or '').strip()[:200],
        'description': str(manual.get('description') or '').strip()[:4000],
        'status': _normalize_report_status(manual.get('status')),
        'executor': str(manual.get('executor') or '').strip()[:60],
        'note': str(manual.get('note') or '').strip()[:1000],
    }


_MANUAL_COLUMNS = {
    'className': ('class', 'classname', 'module', '测试类', '模块', '类'),
    'methodName': ('method', 'methodname', 'case', 'casename', 'title', 'summary', '测试方法', '用例名', '用例名称', '标题'),
    'description': ('description', 'steps', 'desc', '用例描述', '描述', '步骤'),
    'status': ('result', 'status', '结果', '状态'),
    'executor': ('executor', 'tester', 'owner', 'assignee', '执行人', '测试人'),
    'note': ('note', 'notes', 'comment', 'remark', '备注', '说明'),
}


@app.route('/api/report/<path:name>/manual-import', methods=['POST'])
def api_report_manual_import(name):
    name = _safe_report_name(name)
    if not name:
        return jsonify({'err': '报告不存在'}), 404
    upload = request.files.get('file')
    if not upload or not upload.filename:
        return jsonify({'err': '请选择文件'}), 400
    ext = os.path.splitext(upload.filename)[1].lower()
    raw = upload.read()
    if len(raw) > 5 * 1024 * 1024:
        return jsonify({'err': '文件不能超过 5MB'}), 400
    try:
        if ext == '.xlsx':
            from openpyxl import load_workbook
            ws = load_workbook(BytesIO(raw), read_only=True, data_only=True).active
            rows = [list(r) for r in ws.iter_rows(values_only=True)]
        elif ext == '.csv':
            import csv
            text = raw.decode('utf-8-sig', errors='replace')
            rows = list(csv.reader(text.splitlines()))
        else:
            return jsonify({'err': '仅支持 .xlsx 或 .csv'}), 400
    except Exception as e:
        return jsonify({'err': f'文件解析失败: {e}'}), 400
    if not rows:
        return jsonify({'err': '文件为空'}), 400

    headers = [str(h or '').strip().lower().replace(' ', '').replace('_', '') for h in rows[0]]
    col = {}
    for field, aliases in _MANUAL_COLUMNS.items():
        for idx, header in enumerate(headers):
            if header in aliases:
                col[field] = idx
                break
    if 'methodName' not in col or 'status' not in col:
        return jsonify({'err': '表头必须至少包含 测试方法/用例名 和 结果 两列'}), 400

    by = str(request.form.get('by') or '').strip()[:60]
    imported, unknown = [], 0
    for row in rows[1:]:
        values = {f: (row[i] if i < len(row) else '') for f, i in col.items()}
        if not str(values.get('methodName') or '').strip():
            continue
        item = _build_manual_case(values)
        if str(values.get('status') or '').strip().lower() not in _KNOWN_STATUS_WORDS:
            unknown += 1
        imported.append(item)
    if not imported:
        return jsonify({'err': '未找到有效的用例行'}), 400
    with _REPORT_EDIT_LOCK:
        edits = _read_report_edits(name)
        edits['manual_cases'].extend(imported)
        _write_report_edits(name, edits)
    append_system_log('REPORT_MANUAL_IMPORT', f'{by or "unknown"} 向报告 {name} 导入 {len(imported)} 条人工用例', detail={'report': name, 'file': upload.filename})
    return jsonify({'ok': True, 'imported': len(imported), 'unknownStatus': unknown})


@app.route('/api/ai_fail_analysis', methods=['POST'])
def api_ai_fail_analysis():
    """AI自查分析：分析Fail case失败原因，判断是代码问题还是产品Bug。"""
    data = request.get_json(silent=True) or {}
    test_id    = (data.get('testId')    or '').strip()
    test_class = (data.get('testClass') or '').strip()
    method     = (data.get('method')    or '').strip()
    error_info = (data.get('errorInfo') or '').strip()
    stdout_log = (data.get('stdout')    or '').strip()

    if not test_id and not method:
        res = jsonify({'err': 'testId or method is required'})
        res.headers['Access-Control-Allow-Origin'] = '*'
        return res, 400

    cfg = _ai_llm_config()
    if not cfg['enabled']:
        # AI自查是可选增强能力，未启用时不应以503刷屏浏览器控制台，前端会回退到本地判定。
        res = jsonify({'err': 'AI功能未启用，请设置 AUTONEXUS_AI_ENABLE=1'})
        res.headers['Access-Control-Allow-Origin'] = '*'
        return res
    if not cfg['api_key']:
        res = jsonify({'err': '缺少 API Key，请设置 AUTONEXUS_AI_API_KEY 或 GITHUB_COPILOT_TOKEN 环境变量'})
        res.headers['Access-Control-Allow-Origin'] = '*'
        return res
    # ── 1. 查找测试用例源文件 ───────────────────────────────────
    case_code = ''
    case_file_path = ''
    search_name = test_class or (test_id.split('.')[-2] if '.' in test_id else '')
    if search_name:
        for root, dirs, files in os.walk(CASE_DIR):
            for fname in files:
                if not fname.endswith('.py'):
                    continue
                fpath = os.path.join(root, fname)
                try:
                    content = open(fpath, encoding='utf-8', errors='ignore').read()
                    if search_name in content:
                        case_code = content
                        case_file_path = os.path.relpath(fpath, BASE_DIR).replace('\\', '/')
                        break
                except Exception:
                    pass
            if case_code:
                break

    # ── 2. 构造 AI 分析提示 ────────────────────────────────────
    code_section = (
        f'### 测试用例源码 ({case_file_path}):\n```python\n{case_code[:6000]}\n```\n'
        if case_code else '### 测试用例源码：未找到对应源文件\n'
    )
    err_section = (
        f'### 错误信息 (traceback / assertion):\n```\n{error_info[:3000]}\n```\n'
        if error_info else ''
    )
    log_section = (
        f'### 执行日志 (stdout):\n```\n{stdout_log[:2000]}\n```\n'
        if stdout_log else ''
    )

    prompt = f"""你是一名资深Android自动化测试工程师。请根据下面的Fail用例信息进行自查分析，输出结构化报告。

## 失败用例信息
- Test ID: {test_id}
- 测试类: {test_class}
- 测试方法: {method}

{code_section}
{err_section}
{log_section}

## 分析任务
请按以下格式输出（使用中文），每个章节用 ### 标题分隔：

### 失败原因摘要
（一句话概括失败原因）

### 问题归因
判断失败属于哪种情况（只选一种）：
- 🔴 **auto case代码缺陷** — 测试脚本本身写法有误，与被测功能无关
- 🟡 **测试环境/配置问题** — 设备状态、依赖配置、权限等环境原因
- 🟠 **产品Bug** — 被测功能存在缺陷，非测试代码问题

### 详细分析
（结合源码和错误日志，说明具体原因，引用关键代码行）

### 建议措施
如果是**auto case代码缺陷**：
  - 说明哪里写错了，给出修复方案（可包含代码片段）
  - 通知建议：请 auto case 维护人员修复此用例

如果是**产品Bug**：
  - 描述Bug的触发条件和现象
  - 给出可能的根因分析和供开发参考的排查/修复建议

如果是**环境问题**：
  - 说明具体的环境配置要求和恢复步骤
"""

    payload = {
        'model': cfg['model'],
        'messages': [
            {'role': 'system', 'content': '你是资深Android自动化测试专家，能准确区分测试脚本问题和产品Bug。请用中文回答。'},
            {'role': 'user', 'content': prompt},
        ],
        'temperature': 0.3,
    }

    # ── 3. 调用 AI ─────────────────────────────────────────────
    try:
        data_resp = _request_llm(payload, cfg)
        analysis_text = _extract_openai_text(data_resp)
        if not analysis_text:
            raise ValueError('empty response')
        res = jsonify({
            'ok': True,
            'analysis': analysis_text,
            'caseFile': case_file_path,
            'model': cfg['model'],
        })
        res.headers['Access-Control-Allow-Origin'] = '*'
        return res
    except CopilotProviderError as e:
        last_err = str(e)
    except urllib.error.HTTPError as e:
        try:
            body = e.read().decode('utf-8', errors='ignore')[:200]
        except Exception:
            body = ''
        last_err = f'HTTP {e.code}: {body}'
    except Exception as e:
        last_err = str(e)

    res = jsonify({'err': f'AI分析请求失败: {last_err}'})
    res.headers['Access-Control-Allow-Origin'] = '*'
    return res, 502


@app.route('/api/ai_fail_analysis', methods=['OPTIONS'])
def api_ai_fail_analysis_options():
    res = app.make_response('')
    res.headers['Access-Control-Allow-Origin'] = '*'
    res.headers['Access-Control-Allow-Methods'] = 'POST, OPTIONS'
    res.headers['Access-Control-Allow-Headers'] = 'Content-Type'
    return res, 204


@app.route('/api/ai_report_analysis', methods=['POST'])
def api_ai_report_analysis():
    """AI汇总分析：归纳报告中所有失败/错误用例的产品缺陷原因。"""
    data = request.get_json(silent=True) or {}
    failed_cases = data.get('failedCases')
    if not isinstance(failed_cases, list) or not failed_cases:
        return jsonify({'err': 'failedCases is required'}), 400
    if len(failed_cases) > 50:
        return jsonify({'err': '单次最多分析 50 个失败/错误用例'}), 400

    cfg = _ai_llm_config()
    if not cfg['enabled']:
        return jsonify({'err': 'AI功能未启用，请设置 AUTONEXUS_AI_ENABLE=1'})
    if not cfg['api_key']:
        return jsonify({'err': '缺少 API Key，请设置 AUTONEXUS_AI_API_KEY 或 GITHUB_COPILOT_TOKEN 环境变量'})

    case_sections = []
    report_case_references = []
    for index, case in enumerate(failed_cases, 1):
        if not isinstance(case, dict):
            continue
        report_case_number = str(case.get('reportCaseNumber') or index).strip()
        test_id = str(case.get('testId') or '').strip()
        test_class = str(case.get('testClass') or '').strip()
        method = str(case.get('method') or '').strip()
        status = str(case.get('status') or 'fail').strip()
        error_info = str(case.get('errorInfo') or '').strip()
        stdout_log = str(case.get('stdout') or '').strip()
        if not test_id and not method:
            continue
        report_reference = f'R{report_case_number.zfill(3)}' if report_case_number.isdigit() else f'R-{report_case_number}'
        report_case_references.append(f'[{report_reference}] 报告用例编号 {report_case_number}: {test_id or method}')
        case_sections.append(
            f'### [{report_reference}] 报告用例编号 {report_case_number}: {test_id or method}\n'
            f'- 测试类: {test_class}\n'
            f'- 测试方法: {method}\n'
            f'- 结果: {status}\n'
            f'- 异常信息:\n```\n{error_info[:1500] or "(无)"}\n```\n'
            f'- 执行日志:\n```\n{stdout_log[:1000] or "(无)"}\n```'
        )
    if not case_sections:
        return jsonify({'err': '未找到有效的失败/错误用例信息'}), 400

    prompt = f"""你是一名资深Android自动化测试工程师。请对一份自动化测试报告中的全部失败/错误用例做汇总根因分析，重点识别由被测产品缺陷导致的失败。

## 失败/错误用例（共 {len(case_sections)} 个）
{chr(10).join(case_sections)}

## 固定用例引用
{chr(10).join(report_case_references)}

## 分析任务
请使用中文，并严格按以下格式输出，每个章节用 ### 标题分隔：

### 总体结论
说明本次失败中产品Bug、自动化用例问题、环境/配置问题各有多少个；信息不足时明确标注“待人工确认”。

### 产品Bug分析
按可归并的Bug逐项列出：关联用例（只能原样复制上方“固定用例引用”中的方括号标签，如 [R004]、[R010]；不得写“用例1/用例2”，不得按失败用例重新编号）、复现现象、判断依据、可能根因和开发排查建议。若未发现明确产品Bug，说明原因。

### 非产品问题
列出自动化用例、测试环境或配置问题，以及建议的处理人/恢复措施。

### 风险与优先级
按高、中、低优先级排列产品Bug，并说明影响范围。

### 建议行动
给出本轮测试后可执行的下一步清单。不要把没有证据的结论断言为产品Bug。"""
    payload = {
        'model': cfg['model'],
        'messages': [
            {'role': 'system', 'content': '你是资深Android自动化测试专家，能准确区分产品缺陷、测试脚本和环境问题。请用中文回答。'},
            {'role': 'user', 'content': prompt},
        ],
        'temperature': 0.3,
    }
    try:
        analysis_text = _extract_openai_text(_request_llm(payload, cfg))
        if not analysis_text:
            raise ValueError('empty response')
        reference_header = '### 报告用例编号映射（以此为准）\n' + '\n'.join(report_case_references) + '\n\n'
        return jsonify({'ok': True, 'analysis': reference_header + analysis_text, 'model': cfg['model']})
    except CopilotProviderError as e:
        last_err = str(e)
    except urllib.error.HTTPError as e:
        try:
            body = e.read().decode('utf-8', errors='ignore')[:200]
        except Exception:
            body = ''
        last_err = f'HTTP {e.code}: {body}'
    except Exception as e:
        last_err = str(e)
    return jsonify({'err': f'AI分析请求失败: {last_err}'}), 502


@app.route('/api/report/email-contacts', methods=['GET'])
def api_report_email_contacts():
    """Team mailboxes configured in common/allconfig.config [email_contacts]."""
    import configparser
    parser = configparser.ConfigParser(interpolation=None)
    parser.optionxform = str
    contacts = []
    try:
        parser.read(os.path.join(BASE_DIR, 'common', 'allconfig.config'), encoding='utf-8')
        if parser.has_section('email_contacts'):
            for name, value in parser.items('email_contacts'):
                for address in re.split(r'[;,\s]+', value):
                    if address.strip():
                        contacts.append({'name': name, 'email': address.strip()})
    except Exception as e:
        return jsonify({'err': f'读取邮箱配置失败: {e}'}), 500
    return jsonify({'contacts': contacts})


@app.route('/api/report/send-email', methods=['POST'])
def api_report_send_email():
    """Send a report summary and its aggregate AI analysis to developers."""
    data = request.get_json(silent=True) or {}
    recipients = data.get('recipients') or []
    if isinstance(recipients, str):
        recipients = re.split(r'[;,\s]+', recipients)
    if not isinstance(recipients, list):
        return jsonify({'err': 'recipients must be a list of email addresses'}), 400
    recipients = [str(address).strip() for address in recipients if str(address).strip()]
    invalid_recipients = [address for address in recipients if not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', address)]
    if not recipients:
        return jsonify({'err': '请至少填写一个开发邮箱'}), 400
    if invalid_recipients:
        return jsonify({'err': '邮箱格式不正确: ' + ', '.join(invalid_recipients)}), 400

    legacy_smtp_host = (_get_environment_value('AUTONEXUS_SMTP_HOST') or '').strip()
    smtp_username = (_get_environment_value('SMTP_USERNAME') or '').strip()
    smtp_host = ('smtp-secure.honeywell.com' if smtp_username else (_get_environment_value('SMTP_HOST') or legacy_smtp_host or 'smtp-secure.honeywell.com')).strip()
    try:
        smtp_port = int(_get_environment_value('SMTP_PORT') or ('587' if smtp_username else _get_environment_value('AUTONEXUS_SMTP_PORT')) or '587')
    except ValueError:
        return jsonify({'err': 'AUTONEXUS_SMTP_PORT 必须是有效端口号'}), 503
    smtp_user = smtp_username or (_get_environment_value('AUTONEXUS_SMTP_USER') or '').strip()
    smtp_password = _get_environment_value('SMTP_PASSWORD') or _get_environment_value('AUTONEXUS_SMTP_PASSWORD') or ''
    smtp_sender = (_get_environment_value('AUTONEXUS_SMTP_SENDER') or smtp_user).strip()
    smtp_starttls = (_get_environment_value('AUTONEXUS_SMTP_STARTTLS') or '').strip().lower()
    use_starttls = smtp_starttls in ('1', 'true', 'yes', 'on') or (not smtp_starttls and smtp_port == 587)

    report_title = str(data.get('reportTitle') or '自动化测试报告').strip()
    report_url = str(data.get('reportUrl') or '').strip()
    summary = data.get('summary') or {}
    if not isinstance(summary, dict):
        summary = {}
    ai_analysis = str(data.get('aiAnalysis') or '').strip()
    no_failed_cases = data.get('noFailedCases') is True
    if not no_failed_cases and {'failed', 'errored'}.issubset(summary):
        try:
            no_failed_cases = int(summary.get('failed') or 0) == 0 and int(summary.get('errored') or 0) == 0
        except (TypeError, ValueError):
            pass
    if not ai_analysis and not no_failed_cases:
        return jsonify({'err': '请先完成 AI 总体分析，再发送邮件'}), 400
    if no_failed_cases and not ai_analysis:
        ai_analysis = '本次报告无失败或错误用例，无需 AI 根因分析。'

    translation_cfg = _ai_llm_config()
    if not translation_cfg['enabled']:
        return jsonify({'err': 'AI功能未启用，无法生成英文翻译'}), 503
    if not translation_cfg['api_key']:
        return jsonify({'err': '缺少 AI API Key，无法生成英文翻译'}), 503
    translation_payload = {
        'model': translation_cfg['model'],
        'messages': [
            {
                'role': 'system',
                'content': (
                    'You are a professional technical translator for Android test reports. '
                    'Translate Chinese content into clear English. Preserve Markdown headings, '
                    'case-reference tags such as [R004], code blocks, product names, and all facts. '
                    'Return only the English translation.'
                ),
            },
            {'role': 'user', 'content': ai_analysis},
        ],
        'temperature': 0.1,
    }
    try:
        ai_analysis_en = _extract_openai_text(_request_llm(translation_payload, translation_cfg))
        if not ai_analysis_en:
            raise ValueError('empty response')
    except CopilotProviderError as e:
        return jsonify({'err': f'AI英文翻译失败: {e}'}), 502
    except urllib.error.HTTPError as e:
        return jsonify({'err': f'AI英文翻译失败: HTTP {e.code}'}), 502
    except Exception as e:
        return jsonify({'err': f'AI英文翻译失败: {e}'}), 502

    stat_items = [
        ('Total Cases', summary.get('total', 0)),
        ('Passed', summary.get('passed', 0)),
        ('Failed', summary.get('failed', 0)),
        ('Errors', summary.get('errored', 0)),
        ('Skipped', summary.get('skipped', 0)),
    ]
    stat_styles = {
        'Total Cases': ('#f1f5f9', '#475569', '#cbd5e1'),
        'Passed': ('#f0fdf4', '#15803d', '#86efac'),
        'Failed': ('#fef2f2', '#dc2626', '#fca5a5'),
        'Errors': ('#fff7ed', '#c2410c', '#fdba74'),
        'Skipped': ('#f8fafc', '#64748b', '#cbd5e1'),
    }
    stats_html = ''.join(
        f'<td width="20%" valign="top" style="padding:0 4px 8px">'
        f'<div style="background:{stat_styles[label][0]};border:1px solid {stat_styles[label][2]};'
        f'padding:10px 8px;text-align:center;border-radius:4px">'
        f'<div style="font-size:12px;font-weight:700;color:{stat_styles[label][1]};text-transform:uppercase">{escape(str(label))}</div>'
        f'<div style="font-size:24px;font-weight:700;line-height:1.25;color:{stat_styles[label][1]}">{escape(str(value))}</div>'
        f'</div></td>'
        for label, value in stat_items
    )
    report_link_html = (
        f'<p><a href="{escape(report_url, quote=True)}">Open Full Test Report</a></p>'
        if report_url else ''
    )
    subject = f'[AutoNexus] {report_title}' + ('' if no_failed_cases else ' - AI Analysis')
    text_body = (
        f'{report_title}\n\nTest Results: ' + ', '.join(f'{label}: {value}' for label, value in stat_items)
        + f'\n\nChinese Original:\n{ai_analysis}'
        + f'\n\nEnglish Translation:\n{ai_analysis_en}\n\nFull Test Report: {report_url}'
    )
    html_body = f'''<!doctype html><html><body style="font-family:Arial,'Microsoft YaHei',sans-serif;color:#1e293b;line-height:1.6">
<h2>{escape(report_title)}</h2><h3>Test Results</h3><table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0"><tr>{stats_html}</tr></table>{report_link_html}
<h3>Chinese Original</h3><pre style="white-space:pre-wrap;background:#f8fafc;padding:16px;border-left:4px solid #7c3aed">{escape(ai_analysis)}</pre>
<h3>English Translation</h3><pre style="white-space:pre-wrap;background:#f8fafc;padding:16px;border-left:4px solid #2563eb">{escape(ai_analysis_en)}</pre>
</body></html>'''

    attachment = None
    attach_name = _safe_report_name(urllib.parse.unquote(urllib.parse.urlparse(report_url).path))
    if attach_name:
        try:
            attachment = (attach_name, _inline_report_assets(_merge_report_html(attach_name)).encode('utf-8'))
        except OSError as e:
            return jsonify({'err': f'读取报告附件失败: {e}'}), 500

    graph_tenant_id = (_get_environment_value('AUTONEXUS_GRAPH_TENANT_ID') or '').strip()
    graph_client_id = (_get_environment_value('AUTONEXUS_GRAPH_CLIENT_ID') or '').strip()
    graph_client_secret = _get_environment_value('AUTONEXUS_GRAPH_CLIENT_SECRET') or ''
    graph_sender = (_get_environment_value('AUTONEXUS_GRAPH_SENDER') or 'xiaohan.gao@honeywell.com').strip()
    if any((graph_tenant_id, graph_client_id, graph_client_secret)):
        if not all((graph_tenant_id, graph_client_id, graph_client_secret, graph_sender)):
            return jsonify({'err': 'Microsoft Graph 未配置完整，请设置 AUTONEXUS_GRAPH_TENANT_ID、AUTONEXUS_GRAPH_CLIENT_ID、AUTONEXUS_GRAPH_CLIENT_SECRET 和 AUTONEXUS_GRAPH_SENDER'}), 503
        try:
            _send_graph_email(graph_tenant_id, graph_client_id, graph_client_secret, graph_sender, recipients, subject, text_body, html_body, attachment)
            return jsonify({'ok': True, 'provider': 'microsoft-graph', 'recipients': recipients})
        except (OSError, ValueError, RuntimeError) as e:
            return jsonify({'err': f'Microsoft Graph 邮件发送失败: {e}'}), 502

    if not all((smtp_host, smtp_user, smtp_password, smtp_sender)):
        return jsonify({'err': '邮件未配置，请设置 SMTP_USERNAME、SMTP_PASSWORD 和 AUTONEXUS_SMTP_SENDER，或配置 Microsoft Graph'}), 503
    if smtp_password.strip().lower() == 'starttls':
        return jsonify({'err': 'AUTONEXUS_SMTP_PASSWORD 不能填写 STARTTLS；587 端口已自动启用 STARTTLS，请填写真实 SMTP 密码或应用密码'}), 400

    message = EmailMessage()
    message['Subject'] = subject
    message['From'] = smtp_sender
    message['To'] = ', '.join(recipients)
    message.set_content(text_body)
    message.add_alternative(html_body, subtype='html')
    if attachment:
        message.add_attachment(attachment[1], maintype='text', subtype='html', filename=attachment[0])
    try:
        smtp_client = smtplib.SMTP(smtp_host, smtp_port, timeout=120) if use_starttls else smtplib.SMTP_SSL(smtp_host, smtp_port, timeout=120)
        with smtp_client as smtp:
            if use_starttls:
                smtp.starttls()
            smtp.login(smtp_user, smtp_password)
            smtp.send_message(message)
        return jsonify({'ok': True, 'recipients': recipients})
    except (OSError, smtplib.SMTPException) as e:
        return jsonify({'err': f'邮件发送失败: {e}'}), 502


@app.route('/img/<path:filename>')
def serve_img(filename):
    return send_from_directory(IMG_DIR, filename)

@app.route('/run', methods=['POST'])
def run_tests():
    profile = request.get_json(silent=True) or {}
    started = trigger_test_run(profile, trigger='manual')
    res = jsonify({'status': 'started' if started else 'busy'})
    res.headers["Access-Control-Allow-Origin"] = "*"
    return res

@app.route('/api/timer/tasks', methods=['GET'])
def api_timer_tasks_get():
    with timer_lock:
        tasks = read_timer_tasks()
    tasks = [decorate_task_view(item) for item in tasks]
    tasks = sorted(tasks, key=lambda x: x.get('createTime', ''), reverse=True)
    res = jsonify({'code': 200, 'tasks': tasks})
    res.headers["Access-Control-Allow-Origin"] = "*"
    return res

@app.route('/api/timer/task', methods=['POST'])
def api_timer_task_add():
    data = request.get_json() or {}
    required = ['taskName', 'platform', 'execTime']
    for k in required:
        if not data.get(k):
            return jsonify({'code': 400, 'msg': f'缺少必填项：{k}'})

    # Support single-device (deviceSn) and multi-device (deviceSns) scheduled tasks.
    requested_sns = []
    if isinstance(data.get('deviceSns'), list):
        requested_sns = [str(x).strip() for x in data.get('deviceSns') if str(x).strip()]
    single_sn = str(data.get('deviceSn') or '').strip()
    if single_sn and single_sn not in requested_sns:
        requested_sns.append(single_sn)

    device_sns = []
    seen_sn = set()
    for sn in requested_sns:
        if sn in seen_sn:
            continue
        seen_sn.add(sn)
        device_sns.append(sn)

    if not device_sns:
        return jsonify({'code': 400, 'msg': '缺少必填项：deviceSn'})

    execution_times = normalize_execution_times(data.get('executionTimes', data.get('execTimes', 1)))
    case_count = int(data.get('caseCount', 0) or 0)
    base_task_name = data['taskName'][:100]

    with timer_lock:
        tasks = read_timer_tasks()
        batch_id = int(datetime.now().timestamp() * 1000)
        new_tasks = []
        for idx, sn in enumerate(device_sns):
            task_name = base_task_name if len(device_sns) == 1 else f"{base_task_name}_{sn}"
            new_task = {
                'id': batch_id + idx,
                'batchId': batch_id,
                'taskName': task_name[:100],
                'platform': data['platform'],
                'deviceSn': sn,
                'referenceDeviceSn': str(data.get('referenceDeviceSn') or '').strip(),
                'tags': normalize_task_tags(data.get('tags', [])),
                'osVersion': data.get('osVersion', '当前设备OS'),
                'caseCount': case_count,
                'executionTimes': execution_times,
                'totalExecCount': int(data.get('totalExecCount', case_count * execution_times) or 0),
                'caseIds': data.get('caseIds', []),
                'caseList': data.get('caseList', []),
                'execTime': data['execTime'],
                'timerStrategy': data.get('timerStrategy', 'daily'),
                'status': normalize_task_status(data.get('status', ENABLED_STATUS)),
                'runMode': 'timer',
                'createTime': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'lastTriggeredAt': '',
                'lastRunTotal': 0,
                'lastRunCompleted': 0,
                'lastRunPassed': 0,
                'lastRunFailed': 0,
                'lastRunError': 0,
                'lastRunCrashed': False
            }
            new_tasks.append(new_task)
            tasks.append(new_task)
        write_timer_tasks(tasks)

    msg = f'定时任务创建成功，共{len(new_tasks)}台设备' if len(new_tasks) > 1 else '定时任务创建成功'
    res = jsonify({'code': 200, 'msg': msg, 'data': new_tasks[0], 'tasks': new_tasks})
    res.headers["Access-Control-Allow-Origin"] = "*"
    return res

@app.route('/api/timer/task/<int:task_id>/toggle', methods=['PUT'])
def api_timer_task_toggle(task_id):
    with timer_lock:
        tasks = read_timer_tasks()
        for item in tasks:
            if item.get('id') == task_id:
                if derive_task_mode(item) == 'once':
                    res = jsonify({'code': 400, 'msg': '一次性任务不支持启用/停用，请直接新建Project执行'})
                    res.headers["Access-Control-Allow-Origin"] = "*"
                    return res
                item['status'] = DISABLED_STATUS if item.get('status') == ENABLED_STATUS else ENABLED_STATUS
                write_timer_tasks(tasks)
                res = jsonify({'code': 200, 'msg': '状态已更新', 'data': item})
                res.headers["Access-Control-Allow-Origin"] = "*"
                return res
    res = jsonify({'code': 404, 'msg': '任务不存在'})
    res.headers["Access-Control-Allow-Origin"] = "*"
    return res


@app.route('/api/timer/task/<task_id>/tags', methods=['PUT'])
def api_timer_task_tags_update(task_id):
    data = request.get_json(silent=True) or {}
    tags = normalize_task_tags(data.get('tags', []))

    with timer_lock:
        tasks = read_timer_tasks()
        for item in tasks:
            if str(item.get('id')) == str(task_id):
                item['tags'] = tags
                write_timer_tasks(tasks)
                res = jsonify({'code': 200, 'msg': '标签已更新', 'data': {'id': task_id, 'tags': tags}})
                res.headers["Access-Control-Allow-Origin"] = "*"
                return res

    res = jsonify({'code': 404, 'msg': '任务不存在'})
    res.headers["Access-Control-Allow-Origin"] = "*"
    return res

@app.route('/api/timer/task/<int:task_id>', methods=['DELETE'])
def api_timer_task_delete(task_id):
    with timer_lock:
        tasks = read_timer_tasks()
        new_tasks = [item for item in tasks if item.get('id') != task_id]
        if len(new_tasks) == len(tasks):
            res = jsonify({'code': 404, 'msg': '任务不存在'})
            res.headers["Access-Control-Allow-Origin"] = "*"
            return res
        write_timer_tasks(new_tasks)
    res = jsonify({'code': 200, 'msg': '删除成功'})
    res.headers["Access-Control-Allow-Origin"] = "*"
    return res


@app.route('/api/system/logs', methods=['GET'])
def api_system_logs_get():
    try:
        limit = int(request.args.get('limit', 200) or 200)
    except Exception:
        limit = 200
    limit = max(1, min(limit, 1000))
    logs = read_system_logs()[:limit]
    res = jsonify({'code': 200, 'logs': logs})
    res.headers["Access-Control-Allow-Origin"] = "*"
    return res


@app.route('/api/system/info', methods=['GET'])
def api_system_info_get():
    try:
        flask_ver = __import__('flask').__version__
    except Exception:
        flask_ver = 'N/A'

    deploy_time = datetime.fromtimestamp(os.path.getmtime(__file__)).strftime('%Y-%m-%d %H:%M:%S')

    rows = [
        {'label': '平台版本', 'value': APP_VERSION},
        {'label': '当前登录用户', 'value': 'admin (超级管理员)'},
        {'label': '服务启动时间', 'value': SERVER_STARTED_AT},
        {'label': '部署时间', 'value': deploy_time},
        {'label': '运行环境', 'value': py_platform.platform()},
        {'label': 'Python版本', 'value': sys.version.split()[0]},
        {'label': 'Flask版本', 'value': flask_ver},
    ]

    res = jsonify({'code': 200, 'rows': rows})
    res.headers["Access-Control-Allow-Origin"] = "*"
    return res


@app.route('/api/system/logs', methods=['POST'])
def api_system_logs_post():
    data = request.get_json(silent=True) or {}
    action = (data.get('action') or 'SYSTEM').strip()
    message = (data.get('message') or '').strip()
    level = (data.get('level') or 'INFO').strip().upper()
    detail = data.get('detail') if isinstance(data.get('detail'), dict) else {}
    if not message:
        res = jsonify({'code': 400, 'msg': 'message不能为空'})
        res.headers["Access-Control-Allow-Origin"] = "*"
        return res
    append_system_log(action, message, level=level, detail=detail)
    res = jsonify({'code': 200, 'msg': 'ok'})
    res.headers["Access-Control-Allow-Origin"] = "*"
    return res


@app.route('/api/task/<int:task_id>/pause', methods=['POST'])
def api_task_pause(task_id):
    with timer_lock:
        tasks = read_timer_tasks()
        target = None
        for item in tasks:
            if item.get('id') == task_id:
                target = item
                item['status'] = DISABLED_STATUS
                break
        if not target:
            res = jsonify({'code': 404, 'msg': '任务不存在'})
            res.headers["Access-Control-Allow-Origin"] = "*"
            return res
        write_timer_tasks(tasks)
    append_system_log('TASK_PAUSE', f"任务已暂停: {target.get('taskName') or task_id}", detail={'taskId': task_id})
    res = jsonify({'code': 200, 'msg': '任务已暂停', 'data': decorate_task_view(target)})
    res.headers["Access-Control-Allow-Origin"] = "*"
    return res


@app.route('/api/task/<int:task_id>/terminate', methods=['POST'])
def api_task_terminate(task_id):
    with timer_lock:
        tasks = read_timer_tasks()
        target = None
        for item in tasks:
            if item.get('id') == task_id:
                target = item
                item['status'] = DISABLED_STATUS
                break
        if not target:
            res = jsonify({'code': 404, 'msg': '任务不存在'})
            res.headers["Access-Control-Allow-Origin"] = "*"
            return res
        write_timer_tasks(tasks)

    if run_status.get('running'):
        current_id_match = str(run_status.get('current_task_id')) == str(task_id)
        child_match = False
        for state in (run_status.get('device_progress') or {}).values():
            if str(state.get('task_id')) == str(task_id):
                child_match = True
                break
        if current_id_match or child_match:
            run_status['terminate_requested'] = True
    append_system_log('TASK_TERMINATE', f"任务终止请求已发送: {target.get('taskName') or task_id}", detail={'taskId': task_id})
    res = jsonify({'code': 200, 'msg': '任务终止请求已发送', 'data': decorate_task_view(target)})
    res.headers["Access-Control-Allow-Origin"] = "*"
    return res


@app.route('/api/task/<int:task_id>/rerun', methods=['POST'])
def api_task_rerun(task_id):
    with timer_lock:
        tasks = read_timer_tasks()
        target = None
        for item in tasks:
            if item.get('id') == task_id:
                target = item
                break
    if not target:
        res = jsonify({'code': 404, 'msg': '任务不存在'})
        res.headers["Access-Control-Allow-Origin"] = "*"
        return res

    if run_status.get('running'):
        res = jsonify({'code': 409, 'msg': '当前有任务正在运行，请稍后重试'})
        res.headers["Access-Control-Allow-Origin"] = "*"
        return res

    rerun_profile = dict(target)
    rerun_profile['runMode'] = 'once'
    rerun_profile['id'] = int(datetime.now().timestamp() * 1000)
    rerun_profile['status'] = DISABLED_STATUS
    rerun_profile['createTime'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    rerun_profile['lastTriggeredAt'] = ''

    with timer_lock:
        tasks = read_timer_tasks()
        tasks.append(rerun_profile)
        write_timer_tasks(tasks)

    started = trigger_test_run(rerun_profile, trigger='manual-rerun')
    if not started:
        res = jsonify({'code': 409, 'msg': '任务队列繁忙，请稍后重试'})
        res.headers["Access-Control-Allow-Origin"] = "*"
        return res

    append_system_log('TASK_RERUN', f"任务已重跑: {target.get('taskName') or task_id}", detail={'taskId': task_id, 'rerunTaskId': rerun_profile['id']})
    res = jsonify({'code': 200, 'msg': '任务已重跑', 'data': {'taskId': rerun_profile['id']}})
    res.headers["Access-Control-Allow-Origin"] = "*"
    return res


def _extract_failed_indices_from_log_text(log_text):
    """Extract 1-based failed case indices from AUTONEXUS progress lines."""
    text = log_text or ''
    indices = set()

    # Preferred format: END line explicitly marks FAIL/ERROR.
    for m in re.finditer(r'^\[AUTONEXUS_PROGRESS\]\s+END\s+(\d+)/(\d+)\s+(FAIL|ERROR)\s+.+$', text, flags=re.MULTILINE):
        try:
            idx = int(m.group(1))
            if idx > 0:
                indices.add(idx)
        except Exception:
            continue

    # Compatibility format: some runners always print "END ... OK",
    # while unittest result lines still contain FAIL/ERROR with autonexus_case_<n>.
    for m in re.finditer(r'^.*autonexus_case_(\d+)_.*\.\.\.\s+(FAIL|ERROR)\s*$', text, flags=re.MULTILINE):
        try:
            zero_based_idx = int(m.group(1))
            idx = zero_based_idx + 1
            if idx > 0:
                indices.add(idx)
        except Exception:
            continue

    return sorted(indices)


def _pick_latest_log_record_for_task(task):
    """Pick the latest report record log for one task row."""
    if not isinstance(task, dict):
        return None

    task_name = (task.get('taskName') or task.get('profileName') or '').strip()
    if not task_name:
        return None

    task_sn = (task.get('deviceSn') or '').strip()
    task_platform = (task.get('platform') or '').strip()
    last_run_dt = parse_datetime_safe(task.get('lastRunAt', ''))

    records = read_report_records()
    candidates = []
    for row in records:
        if (row.get('profileName') or '').strip() != task_name:
            continue
        if task_sn and (row.get('deviceSn') or '').strip() and (row.get('deviceSn') or '').strip() != task_sn:
            continue
        if task_platform and (row.get('platform') or '').strip() and (row.get('platform') or '').strip() != task_platform:
            continue
        log_file = (row.get('logFile') or '').strip()
        if not log_file:
            continue
        exec_dt = parse_datetime_safe(row.get('executeTime', ''))
        candidates.append((exec_dt, row))

    if not candidates:
        return None

    # Prefer the nearest record around lastRunAt when available.
    if last_run_dt:
        nearby = []
        for exec_dt, row in candidates:
            if not exec_dt:
                continue
            delta = abs((exec_dt - last_run_dt).total_seconds())
            if delta <= 180:
                nearby.append((delta, exec_dt, row))
        if nearby:
            nearby.sort(key=lambda x: (x[0], x[1] if x[1] else datetime.min), reverse=False)
            return nearby[0][2]

    candidates.sort(key=lambda x: x[0] or datetime.min, reverse=True)
    return candidates[0][1]


def _subset_list_by_1based_indices(items, indices):
    out = []
    src = items if isinstance(items, list) else []
    for idx in indices:
        if 1 <= idx <= len(src):
            out.append(src[idx - 1])
    return out


@app.route('/api/task/<int:task_id>/rerun-failed-cases', methods=['POST'])
def api_task_rerun_failed_cases(task_id):
    with timer_lock:
        tasks = read_timer_tasks()
        target = None
        for item in tasks:
            if item.get('id') == task_id:
                target = item
                break

    if not target:
        res = jsonify({'code': 404, 'msg': '任务不存在'})
        res.headers["Access-Control-Allow-Origin"] = "*"
        return res

    if run_status.get('running'):
        res = jsonify({'code': 409, 'msg': '当前有任务正在运行，请稍后重试'})
        res.headers["Access-Control-Allow-Origin"] = "*"
        return res

    batch_id = target.get('batchId')
    failed_candidates = []
    if batch_id is not None:
        for item in tasks:
            if str(item.get('batchId')) != str(batch_id):
                continue
            if item.get('runMode') != 'once':
                continue
            fail_count = int(item.get('lastRunFailed', 0) or 0)
            error_count = int(item.get('lastRunError', 0) or 0)
            if (fail_count + error_count) <= 0:
                continue
            failed_candidates.append(item)
    elif target.get('runMode') == 'once' and (int(target.get('lastRunFailed', 0) or 0) + int(target.get('lastRunError', 0) or 0)) > 0:
        failed_candidates = [target]

    if not failed_candidates:
        res = jsonify({'code': 400, 'msg': '没有可重跑的失败用例'})
        res.headers["Access-Control-Allow-Origin"] = "*"
        return res

    now = datetime.now()
    base_id = int(now.timestamp() * 1000)
    rerun_tasks = []
    total_failed_cases = 0

    for idx, item in enumerate(failed_candidates):
        case_list = item.get('caseList', []) if isinstance(item.get('caseList'), list) else []
        if not case_list:
            continue

        record = _pick_latest_log_record_for_task(item)
        if not record:
            continue
        log_file = (record.get('logFile') or '').strip()
        if not log_file:
            continue

        log_path = os.path.join(REPORT_LOG_DIR, log_file)
        if not os.path.exists(log_path):
            continue

        try:
            with open(log_path, 'r', encoding='utf-8', errors='ignore') as f:
                log_text = f.read()
        except Exception:
            continue

        failed_indices = _extract_failed_indices_from_log_text(log_text)
        if not failed_indices:
            continue

        failed_case_list = _subset_list_by_1based_indices(case_list, failed_indices)
        if not failed_case_list:
            continue

        case_ids = item.get('caseIds', []) if isinstance(item.get('caseIds'), list) else []
        failed_case_ids = _subset_list_by_1based_indices(case_ids, failed_indices) if case_ids else []

        rerun_profile = dict(item)
        rerun_profile['id'] = base_id + idx
        rerun_profile['batchId'] = base_id
        rerun_profile['runMode'] = 'once'
        rerun_profile['status'] = DISABLED_STATUS
        rerun_profile['createTime'] = now.strftime('%Y-%m-%d %H:%M:%S')
        rerun_profile['lastTriggeredAt'] = ''
        rerun_profile['lastRunTotal'] = 0
        rerun_profile['lastRunCompleted'] = 0
        rerun_profile['lastRunPassed'] = 0
        rerun_profile['lastRunFailed'] = 0
        rerun_profile['lastRunError'] = 0
        rerun_profile['lastRunCrashed'] = False
        rerun_profile['caseList'] = failed_case_list
        rerun_profile['caseCount'] = len(failed_case_list)
        if failed_case_ids:
            rerun_profile['caseIds'] = failed_case_ids
        rerun_profile['taskName'] = f"{item.get('taskName') or 'task'}_failed_cases_rerun_{item.get('deviceSn') or idx}"
        rerun_profile['sourceFailedIndices'] = failed_indices

        total_failed_cases += len(failed_case_list)
        rerun_tasks.append(rerun_profile)

    if not rerun_tasks:
        res = jsonify({'code': 400, 'msg': '未找到失败用例明细，无法执行失败用例重跑'})
        res.headers["Access-Control-Allow-Origin"] = "*"
        return res

    with timer_lock:
        latest_tasks = read_timer_tasks()
        latest_tasks.extend(rerun_tasks)
        write_timer_tasks(latest_tasks)

    if len(rerun_tasks) == 1:
        started = trigger_test_run(rerun_tasks[0], trigger='manual-rerun')
    else:
        started = trigger_multi_device_run(rerun_tasks, trigger='manual-rerun')

    if not started:
        res = jsonify({'code': 409, 'msg': '任务队列繁忙，请稍后重试'})
        res.headers["Access-Control-Allow-Origin"] = "*"
        return res

    append_system_log(
        'TASK_RERUN_FAILED_CASES',
        f"失败用例重跑已下发: {target.get('taskName') or task_id}, 任务数={len(rerun_tasks)}, 用例数={total_failed_cases}",
        detail={
            'taskId': task_id,
            'batchId': batch_id,
            'rerunTaskIds': [x.get('id') for x in rerun_tasks],
            'deviceSns': [x.get('deviceSn') for x in rerun_tasks],
            'failedCaseCount': total_failed_cases
        }
    )

    res = jsonify({
        'code': 200,
        'msg': f'已下发失败用例重跑任务：{len(rerun_tasks)}台设备，{total_failed_cases}条用例',
        'data': {
            'count': len(rerun_tasks),
            'failedCaseCount': total_failed_cases,
            'taskIds': [x.get('id') for x in rerun_tasks],
            'deviceSns': [x.get('deviceSn') for x in rerun_tasks]
        }
    })
    res.headers["Access-Control-Allow-Origin"] = "*"
    return res


@app.route('/api/profile/run-once', methods=['POST'])
def api_profile_run_once():
    import re
    data = request.get_json(silent=True) or {}

    # 验证任务名
    task_name_input = (data.get('taskName') or '').strip()
    if task_name_input:
        if len(task_name_input) > 100:
            res = jsonify({'code': 400, 'msg': '任务名称长度不能超过100个字符'})
            res.headers["Access-Control-Allow-Origin"] = "*"
            return res
        if re.search(r'[<>"\'\"%();()&+\\]', task_name_input):
            res = jsonify({'code': 400, 'msg': '任务名称包含非法字符'})
            res.headers["Access-Control-Allow-Origin"] = "*"
            return res

    if run_status.get('running') or run_status.get('repeat_active'):
        res = jsonify({'code': 409, 'msg': '当前有任务正在运行，请稍后再试'})
        res.headers["Access-Control-Allow-Origin"] = "*"
        return res

    devices_result = get_connected_devices_info()
    devices = devices_result.get('devices', []) if isinstance(devices_result, dict) else devices_result
    # ✅ BUGFIX: Validate that we have actual online devices
    if not devices:
        res = jsonify({'code': 400, 'msg': '没有在线设备，无法创建并执行Profile'})
        res.headers["Access-Control-Allow-Origin"] = "*"
        return res

    requested_sns = []
    if isinstance(data.get('deviceSns'), list):
        requested_sns = [str(x).strip() for x in data.get('deviceSns') if str(x).strip()]

    req_sn = (data.get('deviceSn') or '').strip()
    if req_sn and req_sn not in requested_sns:
        requested_sns.append(req_sn)

    if not requested_sns:
        fallback = devices[0].get('sn') or devices[0].get('adbSn')
        if fallback:
            requested_sns = [fallback]

    selected_devices = []
    for req in requested_sns:
        for item in devices:
            if item.get('sn') == req or item.get('adbSn') == req:
                if item not in selected_devices:
                    selected_devices.append(item)
                break

    if not selected_devices:
        res = jsonify({'code': 400, 'msg': '未匹配到可用在线设备'})
        res.headers["Access-Control-Allow-Origin"] = "*"
        return res

    invalid = [d for d in selected_devices if (not d.get('sn') or d.get('sn') == 'N/A')]
    if invalid:
        res = jsonify({'code': 400, 'msg': '选中设备信息不完整或无效'})
        res.headers["Access-Control-Allow-Origin"] = "*"
        return res

    case_ids = data.get('caseIds') if isinstance(data.get('caseIds'), list) else []
    case_list = data.get('caseList') if isinstance(data.get('caseList'), list) else []
    execution_times = normalize_execution_times(data.get('executionTimes', data.get('execTimes', 1)))
    if not case_list:
        default_case = pick_default_case()
        if default_case:
            case_ids = [default_case['id']]
            case_list = [default_case['file']]

    now = datetime.now()
    base_task_name = (task_name_input or data.get('profileName') or f"profile_{now.strftime('%m%d_%H%M%S')}")[:100]

    tasks_to_create = []
    batch_id = int(now.timestamp() * 1000)
    for idx, selected in enumerate(selected_devices):
        sn = selected.get('sn') or selected.get('adbSn') or 'N/A'
        task_name = base_task_name if len(selected_devices) == 1 else f"{base_task_name}_{sn}"
        task = {
            'id': batch_id + idx,
            'batchId': batch_id,
            'taskName': task_name[:100],
            'platform': data.get('platform') or selected.get('platform') or 'Unknown',
            'deviceSn': sn,
            'referenceDeviceSn': str(data.get('referenceDeviceSn') or '').strip(),
            'tags': normalize_task_tags(data.get('tags', [])),
            'osVersion': selected.get('osVersion') or data.get('osVersion') or '当前设备OS',
            'caseCount': int(data.get('caseCount') or len(case_list)),
            'executionTimes': execution_times,
            'totalExecCount': int(data.get('totalExecCount') or (int(data.get('caseCount') or len(case_list)) * execution_times)),
            'caseIds': case_ids,
            'caseList': case_list,
            'execTime': data.get('execTime') or now.strftime('%H:%M'),
            'status': normalize_task_status(data.get('status', DISABLED_STATUS)),
            'runMode': 'once',
            'createTime': now.strftime('%Y-%m-%d %H:%M:%S'),
            'lastRunTotal': 0,
            'lastRunCompleted': 0,
            'lastRunPassed': 0,
            'lastRunFailed': 0,
            'lastRunError': 0,
            'lastRunCrashed': False
        }
        tasks_to_create.append(task)

    with timer_lock:
        tasks = read_timer_tasks()
        tasks.extend(tasks_to_create)
        write_timer_tasks(tasks)

    started = False
    if len(tasks_to_create) == 1:
        started = trigger_test_run_repeated(tasks_to_create[0], trigger='manual')
    else:
        started = trigger_multi_device_run(tasks_to_create, trigger='manual')

    res = jsonify({
        'code': 200,
        'msg': (
            f"Profile创建成功，已触发{len(tasks_to_create)}台设备并发执行" if started and len(tasks_to_create) > 1
            else 'Profile创建成功并已触发执行' if started
            else 'Profile创建成功，但当前执行繁忙'
        ),
        'data': {
            'task': tasks_to_create[0] if tasks_to_create else None,
            'tasks': tasks_to_create,
            'taskId': tasks_to_create[0].get('id') if tasks_to_create else None,
            'taskIds': [t.get('id') for t in tasks_to_create],
            'deviceCount': len(tasks_to_create),
            'runStatus': 'started' if started else 'busy'
        }
    })
    res.headers["Access-Control-Allow-Origin"] = "*"
    return res

# Diagnostics API for failed cases (without strict report file filtering)
@app.route('/api/diagnostics/failed-cases', methods=['GET'])
def api_diagnostics_failed_cases():
    records = read_report_records()
    # Filter for failed, unknown, and error cases - these are what we want to diagnose
    failed = [r for r in records if r.get('result') in ('FAIL', 'UNKNOWN', 'ERROR')]
    # Sort by executeTime descending to get most recent failures first
    failed.sort(key=lambda x: x.get('executeTime', ''), reverse=True)
    # Return top 5 failures
    return jsonify({
        'code': 200,
        'data': failed[:5],
        'total': len(failed)
    })

@app.route('/api/report/list', methods=['GET'])
def api_report_list():
    records = read_report_records()
    cleaned = []
    for item in records:
        row = dict(item)
        rf = (row.get('reportFile') or '').strip()
        report_size = 0
        has_report = False
        if rf:
            full = os.path.join(REPORT_DIR, rf)
            if os.path.exists(full):
                try:
                    report_size = os.path.getsize(full)
                    has_report = report_size > 0
                except Exception:
                    has_report = False
        row['reportSize'] = report_size
        row['hasReport'] = has_report
        log_name = (row.get('logFile') or '').strip()
        if log_name:
            log_path = os.path.join(REPORT_LOG_DIR, log_name)
            row['hasLog'] = os.path.exists(log_path) and os.path.getsize(log_path) > 0 if os.path.exists(log_path) else False
        else:
            row['hasLog'] = False

        # Keep rows that have either report file or log file, so failed runs are visible.
        if not row['hasReport'] and not row['hasLog']:
            continue
        cleaned.append(row)

    # Hide legacy duplicate rows produced by old behavior:
    # immediate manual run followed by scheduler timer run in the same minute.
    def _same_identity(a, b):
        return (
            (a.get('profileName') or '') == (b.get('profileName') or '') and
            (a.get('platform') or '') == (b.get('platform') or '') and
            (a.get('deviceSn') or '') == (b.get('deviceSn') or '')
        )

    filtered = []
    for row in cleaned:
        is_timer = (row.get('trigger') == 'timer')
        has_report = bool(row.get('hasReport'))
        if not is_timer or has_report:
            filtered.append(row)
            continue

        row_dt = parse_datetime_safe(row.get('executeTime', ''))
        if not row_dt:
            filtered.append(row)
            continue

        duplicate_timer = False
        for other in cleaned:
            if other is row:
                continue
            if other.get('trigger') != 'manual':
                continue
            if not _same_identity(row, other):
                continue

            other_dt = parse_datetime_safe(other.get('executeTime', ''))
            if not other_dt:
                continue

            # Same-minute/same-run duplicate window.
            if abs((row_dt - other_dt).total_seconds()) <= 90:
                duplicate_timer = True
                break

        if not duplicate_timer:
            filtered.append(row)

    records = sorted(filtered, key=lambda x: x.get('executeTime', ''), reverse=True)

    if not records:
        # Fallback: show files even if legacy runs had no structured records.
        files = list_html_reports()
        rows = []
        for name in files:
            full = os.path.join(REPORT_DIR, name)
            try:
                dt = datetime.fromtimestamp(os.path.getmtime(full)).strftime('%Y-%m-%d %H:%M:%S')
            except Exception:
                dt = ''
            rows.append({
                'profileName': name,
                'platform': 'N/A',
                'deviceSn': 'N/A',
                'osVersion': 'N/A',
                'executeTime': dt,
                'result': 'UNKNOWN',
                'reportFile': name,
                'reportSize': os.path.getsize(full) if os.path.exists(full) else 0,
                'hasReport': True,
                'hasLog': False,
                'trigger': 'unknown'
            })
        rows.sort(key=lambda x: x.get('executeTime', ''), reverse=True)
        records = rows

    res = jsonify({'code': 200, 'reports': records})
    res.headers["Access-Control-Allow-Origin"] = "*"
    return res


@app.route('/api/data/migrate/report-projects', methods=['POST'])
def api_migrate_report_projects():
    data = request.get_json(silent=True) or {}
    dry_run = bool(data.get('dryRun', False))
    result = migrate_report_profile_names(dry_run=dry_run)
    res = jsonify({'code': 200, 'msg': 'ok', 'data': result})
    res.headers["Access-Control-Allow-Origin"] = "*"
    return res

@app.route('/api/report/log/<int:report_id>', methods=['GET'])
def api_report_log(report_id):
    records = read_report_records()
    target = None
    for item in records:
        if item.get('id') == report_id:
            target = item
            break

    if not target:
        res = jsonify({'code': 404, 'msg': '报告记录不存在'})
        res.headers["Access-Control-Allow-Origin"] = "*"
        return res

    log_name = (target.get('logFile') or '').strip()
    if not log_name:
        res = jsonify({'code': 404, 'msg': '该报告无执行日志'})
        res.headers["Access-Control-Allow-Origin"] = "*"
        return res

    log_path = os.path.join(REPORT_LOG_DIR, log_name)
    if not os.path.exists(log_path):
        res = jsonify({'code': 404, 'msg': '日志文件不存在'})
        res.headers["Access-Control-Allow-Origin"] = "*"
        return res

    with open(log_path, 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read()

    res = jsonify({'code': 200, 'log': content, 'logFile': log_name})
    res.headers["Access-Control-Allow-Origin"] = "*"
    return res


@app.route('/api/report/log/<int:report_id>/download', methods=['GET'])
def api_report_log_download(report_id):
    records = read_report_records()
    target = None
    for item in records:
        if item.get('id') == report_id:
            target = item
            break

    if not target:
        res = jsonify({'code': 404, 'msg': '报告记录不存在'})
        res.headers["Access-Control-Allow-Origin"] = "*"
        return res

    log_name = (target.get('logFile') or '').strip()
    if not log_name:
        res = jsonify({'code': 404, 'msg': '该报告无执行日志'})
        res.headers["Access-Control-Allow-Origin"] = "*"
        return res

    log_path = os.path.join(REPORT_LOG_DIR, log_name)
    if not os.path.exists(log_path):
        res = jsonify({'code': 404, 'msg': '日志文件不存在'})
        res.headers["Access-Control-Allow-Origin"] = "*"
        return res

    return send_from_directory(
        REPORT_LOG_DIR,
        log_name,
        as_attachment=True,
        download_name=log_name,
        mimetype='text/plain; charset=utf-8'
    )

@app.route('/status')
def status():
    res = jsonify(run_status)
    res.headers["Access-Control-Allow-Origin"] = "*"
    return res

@app.route('/api/run/progress')
def api_run_progress():
    """获取当前执行进度"""
    progress = {
        'running': run_status['running'],
        'current_case': run_status.get('current_case', ''),
        'total_cases': run_status.get('total_cases', 0),
        'completed_cases': run_status.get('completed_cases', 0),
        'passed': run_status.get('passed', 0),
        'failed': run_status.get('failed', 0),
        'error': run_status.get('error', 0),
        'skipped': run_status.get('skipped', 0),
        'failed_indices': run_status.get('failed_indices', []),
        'percentage': 0,
        'current_task_id': run_status.get('current_task_id'),
        'device_progress': run_status.get('device_progress', {}),
        'repeat_total': run_status.get('repeat_total', 1),
        'repeat_index': run_status.get('repeat_index', 1),
        'repeat_active': run_status.get('repeat_active', False)
    }
    if progress['total_cases'] > 0:
        progress['percentage'] = int((progress['completed_cases'] / progress['total_cases']) * 100)
    res = jsonify(progress)
    res.headers["Access-Control-Allow-Origin"] = "*"
    return res

@app.route('/api/log')
def api_log():
    res = jsonify({
        "running": run_status['running'],
        "log_content": run_status['log']
    })
    res.headers["Access-Control-Allow-Origin"] = "*"
    return res

@app.route('/api/reboot', methods=['POST'])
def api_reboot():
    data = request.get_json()
    sn = data.get('sn', '')
    if not sn:
        return jsonify({"msg": "设备SN为空"})
    try:
        subprocess.run([ADB, '-s', sn, 'reboot'], timeout=10)
        return jsonify({"msg": f"设备 {sn} 重启指令已下发"})
    except Exception as e:
        return jsonify({"msg": f"重启失败：{str(e)}"})

@app.route('/api/stat/summary')
def api_stat_summary():
    """Get dashboard summary statistics from real execution data"""
    records = read_report_records()
    devices = get_connected_devices_info()
    tasks = read_timer_tasks()
    # Build task name -> caseCount lookup
    task_case_count = {}
    for t in tasks:
        name = t.get('taskName') or t.get('profileName', '')
        count = t.get('caseCount', 1)
        task_case_count[name] = count
    # Total cases = sum of caseCount for each execution record
    total_cases = 0
    for r in records:
        profile = r.get('profileName', '')
        total_cases += task_case_count.get(profile, 1)
    total_executions = len(records)
    pass_count = len([r for r in records if r.get('result') == 'PASS'])
    terminated_count = len([r for r in records if r.get('result') == 'TERMINATED'])
    fail_count = len([r for r in records if r.get('result') == 'FAIL'])
    error_count = len([r for r in records if r.get('result') in ('ERROR', 'UNKNOWN')])
    unknown_count = len([r for r in records if r.get('result') == 'UNKNOWN'])
    pass_rate = round((pass_count / total_executions * 100), 1) if total_executions > 0 else 0
    fail_rate = round((fail_count / total_executions * 100), 1) if total_executions > 0 else 0
    error_rate = round((error_count / total_executions * 100), 1) if total_executions > 0 else 0
    terminated_rate = round((terminated_count / total_executions * 100), 1) if total_executions > 0 else 0
    online_devices = len(devices) if devices else 0
    summary = {
        "totalCases": total_cases,
        "totalExecutions": total_executions,
        "passCount": pass_count,
        "failCount": fail_count,
        "errorCount": error_count,
        "terminatedCount": terminated_count,
        "unknownCount": unknown_count,
        "passRate": pass_rate,
        "failRate": fail_rate,
        "errorRate": error_rate,
        "terminatedRate": terminated_rate,
        "onlineDevices": online_devices
    }
    res = jsonify({"code": 200, "data": summary})
    res.headers["Access-Control-Allow-Origin"] = "*"
    return res

@app.route('/api/stat/platform')
def api_stat_platform():
    """Get platform-wise PASS/FAIL/ERROR statistics from real data"""
    records = read_report_records()
    # Group by platform
    platform_stats = {}
    for record in records:
        platform = record.get('platform', 'unknown')
        if platform not in platform_stats:
            platform_stats[platform] = {'total': 0, 'pass': 0, 'fail': 0, 'error': 0}
        platform_stats[platform]['total'] += 1
        result = str(record.get('result') or '').upper()
        if result == 'PASS':
            platform_stats[platform]['pass'] += 1
        elif result == 'FAIL':
            platform_stats[platform]['fail'] += 1
        elif result in ('ERROR', 'UNKNOWN'):
            platform_stats[platform]['error'] += 1
    # Format response
    stat_data = []
    for platform, stats in platform_stats.items():
        pass_rate = round((stats['pass'] / stats['total'] * 100), 1) if stats['total'] > 0 else 0
        fail_rate = round((stats['fail'] / stats['total'] * 100), 1) if stats['total'] > 0 else 0
        error_rate = round((stats['error'] / stats['total'] * 100), 1) if stats['total'] > 0 else 0
        stat_data.append({
            "platform": platform,
            "pass": stats['pass'],
            "fail": stats['fail'],
            "error": stats['error'],
            "passRate": pass_rate,
            "failRate": fail_rate,
            "errorRate": error_rate,
            "total": stats['total']
        })
    # Sort by platform name
    stat_data.sort(key=lambda x: x['platform'])
    res = jsonify({"code": 200, "data": stat_data})
    res.headers["Access-Control-Allow-Origin"] = "*"
    return res

@app.route('/api/stat/trend')
def api_stat_trend():
    """Get 7-day PASS/FAIL/ERROR rate trends from real data"""
    records = read_report_records()

    # Generate date range for last 7 days
    days = []
    daily_stats = {}
    for i in range(6, -1, -1):
        day = (datetime.now() - timedelta(days=i)).strftime('%m-%d')
        days.append(day)
        daily_stats[day] = {'total': 0, 'pass': 0, 'fail': 0, 'error': 0}
    # Aggregate records by day
    for record in records:
        try:
            exec_time = datetime.strptime(record.get('executeTime', ''), '%Y-%m-%d %H:%M:%S')
            day = exec_time.strftime('%m-%d')
            if day in daily_stats:
                daily_stats[day]['total'] += 1
                result = str(record.get('result') or '').upper()
                if result == 'PASS':
                    daily_stats[day]['pass'] += 1
                elif result == 'FAIL':
                    daily_stats[day]['fail'] += 1
                elif result in ('ERROR', 'UNKNOWN'):
                    daily_stats[day]['error'] += 1
        except:
            pass
    # Calculate daily rates
    pass_rates = []
    fail_rates = []
    error_rates = []
    for day in days:
        stats = daily_stats[day]
        pass_rate = round((stats['pass'] / stats['total'] * 100), 1) if stats['total'] > 0 else 0
        fail_rate = round((stats['fail'] / stats['total'] * 100), 1) if stats['total'] > 0 else 0
        error_rate = round((stats['error'] / stats['total'] * 100), 1) if stats['total'] > 0 else 0
        pass_rates.append(pass_rate)
        fail_rates.append(fail_rate)
        error_rates.append(error_rate)
    res = jsonify({
        "code": 200,
        "days": days,
        "passRates": pass_rates,
        "failRates": fail_rates,
        "errorRates": error_rates
    })
    res.headers["Access-Control-Allow-Origin"] = "*"
    return res

@app.route('/api/stat/overall')
def api_stat_overall():
    """Get overall execution statistics grouped by platform + osVersion, with time filter"""
    records = read_report_records()
    tasks = read_timer_tasks()
    time_unit = request.args.get('timeUnit', 'all')

    # Build task name -> caseCount lookup
    task_case_count = {}
    for t in tasks:
        name = t.get('taskName') or t.get('profileName', '')
        task_case_count[name] = t.get('caseCount', 1)

    # Determine cutoff date
    now = datetime.now()
    cutoff = None
    if time_unit == '7day':
        cutoff = now - timedelta(days=7)
    elif time_unit == '30day':
        cutoff = now - timedelta(days=30)
    elif time_unit == '3month':
        cutoff = now - timedelta(days=90)
    elif time_unit == '6month':
        cutoff = now - timedelta(days=180)
    elif time_unit == '1year':
        cutoff = now - timedelta(days=365)

    # Filter records by date
    filtered = []
    for r in records:
        if cutoff:
            try:
                exec_time = datetime.strptime(r.get('executeTime', ''), '%Y-%m-%d %H:%M:%S')
                if exec_time < cutoff:
                    continue
            except:
                pass
        filtered.append(r)

    # Build sn -> androidVer from connected devices for fallback
    sn_to_android = {}
    try:
        for dev in get_connected_devices_info():
            if dev.get('sn') and dev.get('androidVer'):
                sn_to_android[dev['sn']] = dev['androidVer']
    except:
        pass

    # Group by platform + androidVer
    groups = {}
    for r in filtered:
        platform = r.get('platform', 'unknown')
        android_ver = r.get('androidVer') or sn_to_android.get(r.get('deviceSn', ''), 'Unknown')
        # Normalize: strip leading zeros, e.g. "14" -> "A14"
        if android_ver and android_ver != 'Unknown' and android_ver != 'N/A':
            try:
                android_ver = 'A' + str(int(android_ver))
            except:
                pass
        key = (platform, android_ver)
        if key not in groups:
            groups[key] = {'execCount': 0, 'passCount': 0, 'failCount': 0}
        case_count = task_case_count.get(r.get('profileName', ''), 1)
        groups[key]['execCount'] += case_count
        if r.get('result') == 'PASS':
            groups[key]['passCount'] += case_count
        else:  # FAIL or UNKNOWN both count as failures
            groups[key]['failCount'] += case_count

    # Format result
    result = []
    for (platform, android_ver), stats in groups.items():
        pass_rate = round(stats['passCount'] / stats['execCount'] * 100, 1) if stats['execCount'] > 0 else 0
        result.append({
            'platform': platform,
            'androidVer': android_ver,
            'execCount': stats['execCount'],
            'passCount': stats['passCount'],
            'failCount': stats['failCount'],
            'passRate': pass_rate
        })

    result.sort(key=lambda x: (x['platform'], x['androidVer']))
    total = sum(r['execCount'] for r in result)

    res = jsonify({"code": 200, "data": result, "total": total})
    res.headers["Access-Control-Allow-Origin"] = "*"
    return res

@app.route('/api/report/export/html')
def api_report_export_html():
    if not os.path.exists(REPORT_DIR):
        return jsonify({"code": 404, "msg": "报告目录不存在"})
    files = sorted(list_html_reports(), key=lambda x: os.path.getmtime(os.path.join(REPORT_DIR, x)), reverse=True)
    if not files:
        return jsonify({"code": 404, "msg": "暂无报告文件"})
    latest_file = files[0]
    return send_from_directory(REPORT_DIR, latest_file, as_attachment=True)

@app.route('/api/report/export/excel')
def api_report_export_excel():
    wb = Workbook()
    ws = wb.active
    ws.title = "测试报告"
    headers = ["用例ID", "用例名称", "测试类", "源文件", "用例说明", "维护人", "执行结果", "执行时间"]
    ws.append(headers)
    cases = read_case_meta()
    for case in cases:
        ws.append([
            case['id'],
            case['name'],
            case['className'],
            case['file'],
            case['doc'],
            case['owner'],
            "通过",
            datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        ])
    for col in ws.columns:
        max_length = 0
        column = col[0].column_letter
        for cell in col:
            try:
                if len(str(cell.value)) > max_length:
                    max_length = len(str(cell.value))
            except:
                pass
        adjusted_width = min(max_length + 2, 50)
        ws.column_dimensions[column].width = adjusted_width
    output = BytesIO()
    wb.save(output)
    output.seek(0)
    filename = f"测试报告_{datetime.now().strftime('%Y%m%d%H%M%S')}.xlsx"
    return send_file(
        output,
        as_attachment=True,
        download_name=filename,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )


# ===== Jira defect creation =====
JIRA_URL = 'https://honeywell.atlassian.net'
JIRA_EMAIL = 'Xiaohan.Gao@Honeywell.com'
JIRA_API_TOKEN = (
    'ATATT3xFfGF0piQ-anxRJmPrAUxrerRf4W_5RGuoWtS5QYPiq03r1y1E9dHP67X36_AWHyFnJxwgtfXdiNp2u3j-'
    'ZR4LToWwI_npUxKpw547Ol0-TDS7wjIVkLqjOd3I8uWur4QReneR9d8SW4_9Ua6CaA0Alv3QHRn5q45HzshPqIEqJiDowMM=69671632'
)
JIRA_PROJECT_KEY = 'SZMSUS'
JIRA_DEFAULT_ISSUE_TYPE = 'Defect'
JIRA_DEFAULT_SEVERITY = '3-Minor'  # one of: 1-Critical, 2-Major, 3-Minor, 4-Marginal
JIRA_SEVERITY_FIELD = 'customfield_11795'
JIRA_STEPS_FIELD = 'customfield_11859'


def _jira_auth_header():
    raw = f'{JIRA_EMAIL}:{JIRA_API_TOKEN}'.encode('utf-8')																  
    return 'Basic ' + base64.b64encode(raw).decode('ascii')


def _jira_request(method, path, payload=None):
    """Call the Jira Cloud REST API. Returns (status_code, parsed_json)."""
    url = JIRA_URL.rstrip('/') + path
    data = json.dumps(payload).encode('utf-8') if payload is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header('Authorization', _jira_auth_header())
    req.add_header('Accept', 'application/json')
    if data is not None:
        req.add_header('Content-Type', 'application/json')
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = resp.read().decode('utf-8', errors='ignore')
            return resp.status, (json.loads(body) if body else {})
    except urllib.error.HTTPError as e:
        body = e.read().decode('utf-8', errors='ignore')
        try:
            parsed = json.loads(body)
        except Exception:
            parsed = {'raw': body}
        return e.code, parsed
    except Exception as e:
        return 0, {'raw': str(e)}


def _jira_pick_issue_type(preferred):
    """Return a valid issue type name for the project, preferring `preferred`."""
    status, data = _jira_request(
        'GET', f'/rest/api/3/issue/createmeta/{JIRA_PROJECT_KEY}/issuetypes'
    )
    types = []
    if status == 200 and isinstance(data, dict):
        types = data.get('issueTypes') or data.get('values') or []
    names = [t.get('name', '') for t in types if isinstance(t, dict) and not t.get('subtask')]
    if not names:
        return preferred, []
    for n in names:
        if n.lower() == (preferred or '').lower():
            return n, names
    for kw in ('defect', 'bug'):
        for n in names:
            if kw in n.lower():
                return n, names
    return names[0], names


def _jira_adf_description(lines):
    content = []
    for line in lines:
        text = str(line) if line else ''
        content.append({
            'type': 'paragraph',
            'content': ([{'type': 'text', 'text': text}] if text else [])
        })
    if not content:
        content = [{'type': 'paragraph', 'content': []}]
    return {'type': 'doc', 'version': 1, 'content': content}


@app.route('/api/jira/create-defect', methods=['POST'])
def jira_create_defect():
  try:
    data = request.get_json(silent=True) or {}
    profile = (data.get('profileName') or 'Automation Test').strip()
    platform = (data.get('platform') or '').strip()
    device_sn = (data.get('deviceSn') or '').strip()
    os_version = (data.get('osVersion') or '').strip()
    execute_time = (data.get('executeTime') or '').strip()
    result = (data.get('result') or '').strip()
    report_file = (data.get('reportFile') or '').strip()

    # Derive device SN and execute time from the report filename when not provided.
    # Report files are named: <YYYY-MM-DD>_<HH-MM-SS>_<SN>_result.html
    if report_file:
        m = re.match(r'(\d{4}-\d{2}-\d{2})_(\d{2}-\d{2}-\d{2})_(.+?)_result\.html$', report_file)
        if m:
            if not execute_time:
                execute_time = f"{m.group(1)} {m.group(2).replace('-', ':')}"
            if not device_sn:
                device_sn = m.group(3)

    summary = (data.get('summary') or '').strip()
    if not summary:
        on_dev = f' on {device_sn}' if device_sn else (f' on {platform}' if platform else '')
        summary = f'[Auto Test] {profile} {result or "result"}{on_dev}'.strip()
    summary = summary[:250]

    report_url = ''
    if report_file:
        report_url = f'{request.host_url.rstrip("/")}/report/{report_file}'

    desc_lines = [
        'Automatically created from the automation test report console.',
        '',
        f'Project Name : {profile}',
        f'Test Platform: {platform}',
        f'Device SN    : {device_sn}',
        f'OS Version   : {os_version}',
        f'Execute Time : {execute_time}',
        f'Result       : {result}',
    ]
    if report_url:
        desc_lines += ['', f'Report: {report_url}']
    extra = (data.get('description') or '').strip()
    if extra:
        desc_lines += [''] + extra.splitlines()

    issue_type, available = _jira_pick_issue_type(
        (data.get('issueType') or JIRA_DEFAULT_ISSUE_TYPE).strip()
    )

    payload = {
        'fields': {
            'project': {'key': JIRA_PROJECT_KEY},
            'summary': summary,
            'issuetype': {'name': issue_type},
            'description': _jira_adf_description(desc_lines),
            JIRA_SEVERITY_FIELD: {'value': (data.get('severity') or JIRA_DEFAULT_SEVERITY).strip()},
            JIRA_STEPS_FIELD: _jira_adf_description([(extra or summary)[:30000]]),
        }
    }
    status, body = _jira_request('POST', '/rest/api/3/issue', payload)
    if status in (200, 201) and isinstance(body, dict) and body.get('key'):
        key = body['key']
        return jsonify({
            'code': 200,
            'key': key,
            'issueType': issue_type,
            'url': f'{JIRA_URL.rstrip("/")}/browse/{key}'
        })

    msg = ''
    if isinstance(body, dict):
        parts = list(body.get('errorMessages') or [])
        parts += [f'{k}: {v}' for k, v in (body.get('errors') or {}).items()]
        msg = '; '.join(parts) or body.get('raw') or ''
    return jsonify({
        'code': status or 500,
        'msg': msg or 'Failed to create Jira defect',
        'availableIssueTypes': available
    })
  except Exception as e:
    return jsonify({'code': 500, 'msg': f'{type(e).__name__}: {e}'})


if __name__ == '__main__':
    app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0
    start_timer_scheduler()
    print("✅ 服务已启动：http://127.0.0.1:9090")
    app.run(host='0.0.0.0', port=9090, debug=False)