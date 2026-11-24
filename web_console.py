# -*- coding: utf-8 -*-
"""
Android automation test web console
Start: python web_console.py  ->  http://localhost:5000
"""
import os, subprocess, time, json, threading, base64, csv, io, re, ast, uuid
import urllib.request
import urllib.error
from flask import Flask, jsonify, request, send_from_directory, render_template_string
from common.copilot_provider import CopilotProviderError, chat_completion, copilot_config

app = Flask(__name__)
BASE_DIR = os.path.dirname(os.path.realpath(__file__))
REPORT_DIR = os.path.join(BASE_DIR, 'report')
CASE_ROOT_DIR = os.path.join(BASE_DIR, 'case')


def _resolve_runner_python():
    """Resolve the python interpreter used to run test cases.

    Prefer the project venv (which has the required dependencies such as
    uiautomator2 / adbutils / deprecation) over whatever interpreter happens
    to have started this web server.
    """
    import sys as _sys
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
        _sys.executable,
    ]

    for candidate in candidates:
        if _is_working_python(candidate):
            return candidate

    return _sys.executable


RUNNER_PYTHON = _resolve_runner_python()
DEFAULT_COMPONENT = 'smoking'
CAMERA_SHUTTER_ID = 'org.codeaurora.snapcam:id/shutter_button'
CAMERA_FLASH_ID = 'org.codeaurora.snapcam:id/flash_button'
CAMERA_APP_PACKAGE = 'org.codeaurora.snapcam'
CAMERA_APP_ACTIVITY = 'com.android.camera.CameraLauncher'
CAMERA_APP_COMPONENT = f'{CAMERA_APP_PACKAGE}/{CAMERA_APP_ACTIVITY}'

_state = {'status': 'idle', 'log': ''}
_case_gen_jobs = {}
_case_gen_lock = threading.Lock()


def _append_case_gen_log(job_id, line):
    with _case_gen_lock:
        job = _case_gen_jobs.get(job_id)
        if not job:
            return
        line = '' if line is None else str(line)
        job['log'] += line + '\n'
        job['updated_at'] = time.time()


def _create_case_gen_job(case_name, component_name):
    ts = time.strftime('%Y%m%d_%H%M%S', time.localtime())
    suffix = uuid.uuid4().hex[:8]
    job_id = f'{ts}_{case_name}_{suffix}'

    with _case_gen_lock:
        _case_gen_jobs[job_id] = {
            'jobId': job_id,
            'status': 'running',
            'log': '',
            'err': '',
            'component': component_name,
            'file': '',
            'path': '',
            'generatedBy': 'copilot-ai',
            'created_at': time.time(),
            'updated_at': time.time(),
            'log_file': '',
        }
    return job_id


def _is_safe_case_file(name):
    if not name or '/' in name or '\\' in name or '..' in name:
        return False
    return name.startswith('test_') and name.endswith('.py')

def _get_devices():
    try:
        out = subprocess.check_output('adb devices', shell=True).decode('utf-8', errors='ignore')
        serials = [l.split('\t')[0] for l in out.splitlines()[1:] if '\tdevice' in l]
        result = []
        for s in serials:
            try:
                model = subprocess.check_output(
                    f'adb -s {s} shell getprop ro.product.model',
                    shell=True, timeout=5
                ).decode('utf-8', errors='ignore').strip()
            except Exception:
                model = 'unknown'
            result.append({'serial': s, 'model': model})
        return result
    except Exception:
        return []


def _normalize_case_name(name):
    cleaned = ''.join(ch if (ch.isalnum() or ch == '_') else '_' for ch in (name or '').strip())
    while '__' in cleaned:
        cleaned = cleaned.replace('__', '_')
    cleaned = cleaned.strip('_')
    if not cleaned:
        return ''
    if cleaned[0].isdigit():
        cleaned = f'case_{cleaned}'
    return cleaned


def _normalize_component_name(name):
    cleaned = ''.join(ch for ch in (name or '').strip() if (ch.isalnum() or ch == '_'))
    return cleaned


def _resolve_component_dir(component_raw, create=False):
    normalized = _normalize_component_name(component_raw) or DEFAULT_COMPONENT
    os.makedirs(CASE_ROOT_DIR, exist_ok=True)

    # Reuse existing folder with the same name (case-insensitive) to avoid duplicates like Camera/camera.
    actual = normalized
    low = normalized.lower()
    for entry in os.listdir(CASE_ROOT_DIR):
        full = os.path.join(CASE_ROOT_DIR, entry)
        if os.path.isdir(full) and entry.lower() == low:
            actual = entry
            break

    comp_dir = os.path.join(CASE_ROOT_DIR, actual)
    if create:
        os.makedirs(comp_dir, exist_ok=True)
        init_file = os.path.join(comp_dir, '__init__.py')
        if not os.path.exists(init_file):
            with open(init_file, 'w', encoding='utf-8') as f:
                f.write('')
    return actual, comp_dir


def _to_class_suffix(case_name):
    parts = [p for p in case_name.split('_') if p]
    if not parts:
        return 'Generated'
    return ''.join(p[:1].upper() + p[1:] for p in parts)


def _normalize_step_pairs(raw_pairs):
    pairs = []
    for item in (raw_pairs or []):
        if not isinstance(item, dict):
            continue
        step = (item.get('step') or '').strip()
        expected = (item.get('expected') or '').strip()
        if not step:
            continue
        pairs.append({'step': step, 'expected': expected})
    return pairs


def _compose_steps_text(step_pairs, fallback_text=''):
    pairs = _normalize_step_pairs(step_pairs)
    if pairs:
        lines = []
        for row in pairs:
            if row['expected']:
                lines.append(f"{row['step']} - Expected Result: {row['expected']}")
            else:
                lines.append(row['step'])
        return '\n'.join(lines)
    return (fallback_text or '').strip()


def _copilot_ai_config():
    enabled_raw = str(os.environ.get('COPILOT_AI_ENABLE', '1')).strip().lower()
    copilot = copilot_config()

    return {
        'enabled': enabled_raw in ('1', 'true', 'yes', 'on'),
        'api_key': copilot['api_key'],
        'chat_url': copilot['chat_url'],
        'model': copilot['model'],
        'timeout_sec': copilot['timeout_sec'],
        'copilot': copilot,
    }


def _extract_openai_text(data):
    if not isinstance(data, dict):
        return ''
    choices = data.get('choices')
    if not isinstance(choices, list) or not choices:
        return ''
    msg = choices[0].get('message') if isinstance(choices[0], dict) else None
    if not isinstance(msg, dict):
        return ''
    content = msg.get('content')
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict) and isinstance(item.get('text'), str):
                parts.append(item['text'])
        return '\n'.join(parts)
    return ''


def _extract_code_from_llm_text(text):
    s = (text or '').strip()
    if not s:
        return ''
    m = re.search(r"```(?:python)?\s*([\s\S]*?)```", s, re.IGNORECASE)
    if m:
        return m.group(1).strip()
    return s


def _sanitize_generated_python(text):
    s = (text or '').replace('\r\n', '\n').replace('\r', '\n').strip()
    if not s:
        return ''

    # SDK responses can use language labels other than exactly ```python.
    fenced_blocks = re.findall(r'```[^\n]*\n([\s\S]*?)```', s)
    if fenced_blocks:
        s = max(fenced_blocks, key=len).strip()
    else:
        s = re.sub(r'^```[^\n]*\n?', '', s)
        s = re.sub(r'\n?```\s*$', '', s)

    lines = s.split('\n')
    start_idx = None
    py_start = re.compile(
        r'^\s*(?:#.*coding[:=]|import\s+|from\s+|class\s+|def\s+|@|"""|\'\'\'|if __name__\s*==)'
    )
    for i, ln in enumerate(lines):
        if py_start.search(ln):
            start_idx = i
            break
    if start_idx is None:
        # No line-start marker matched (e.g. unusual formatting). Only treat this
        # as non-code when there is no python keyword anywhere in the text; otherwise
        # keep the full text so ast.parse can report a precise syntax error downstream.
        if not re.search(r'\bimport\s+\w|\bclass\s+\w|\bdef\s+\w|\bfrom\s+\w+\s+import\b', s):
            return ''
        start_idx = 0
    lines = lines[start_idx:]

    # Drop trailing explanation text that often appears after code blocks.
    for i, ln in enumerate(lines):
        if re.match(r'^\s*(Explanation|Notes?|Usage|Output)\s*:\s*$', ln, flags=re.IGNORECASE):
            lines = lines[:i]
            break

    return '\n'.join(lines).strip()


def _strip_camera_code_for_bt(code):
    if not code:
        return code

    code = _strip_camera_template_code(code)

    # Enforce BT verification by ADB state instead of UI text assertion.
    code = re.sub(
        r"^\s*assert\s+d\(text\s*=\s*['\"]Bluetooth['\"]\)\.exists\(timeout\s*=\s*\d+\)\s*,\s*['\"][^'\"]*Bluetooth[^'\"]*['\"]\s*$",
        "        bt_state = _run_adb_shell('settings get global bluetooth_on').strip()\n        self.assertEqual(bt_state, '1', 'Bluetooth should be enabled')",
        code,
        flags=re.MULTILINE,
    )
    code = re.sub(
        r"^\s*self\.assertTrue\(\s*d\(text\s*=\s*['\"]Bluetooth['\"]\)\.exists\(timeout\s*=\s*\d+\)\s*,\s*['\"][^'\"]*Bluetooth[^'\"]*['\"]\s*\)\s*$",
        "        bt_state = _run_adb_shell('settings get global bluetooth_on').strip()\n        self.assertEqual(bt_state, '1', 'Bluetooth should be enabled')",
        code,
        flags=re.MULTILINE,
    )

    code = re.sub(r'\n{3,}', '\n\n', code).strip() + '\n'
    return code


def _ensure_camera_import(code):
    if not code:
        return code
    required = 'from common.adb_common import save_step_screenshot, detect_default_camera_activity, run_adb_cmd'
    needs = 'detect_default_camera_activity' in code
    if not needs:
        return code
    if re.search(r'^from common\.adb_common import .*detect_default_camera_activity', code, flags=re.MULTILINE):
        return code
    if re.search(r'^from common\.adb_common import .*$', code, flags=re.MULTILINE):
        return re.sub(r'^from common\.adb_common import .*$', required, code, count=1, flags=re.MULTILINE)
    return re.sub(r'(^import [^\n]*\n)', r'\1' + required + '\n', code, count=1, flags=re.MULTILINE)


def _ensure_method_self_params(code):
    if not code:
        return code
    # Class methods defined without 'self' but called via self.<name>(...) cause arg-count errors.
    def repl(m):
        indent, name, params = m.group(1), m.group(2), m.group(3).strip()
        if indent and f'self.{name}(' in code and not params.startswith('self'):
            new_params = 'self' if not params else 'self, ' + params
            return f'{indent}def {name}({new_params}):'
        return m.group(0)
    return re.sub(r'^(\s+)def (\w+)\(([^)]*)\):', repl, code, flags=re.MULTILINE)


def _ensure_module_globals(code):
    if not code:
        return code
    # Replace placeholder literal serial assignments with the real env-based one.
    code = re.sub(
        r"^\s*serial\s*=\s*['\"][^'\"]*['\"].*$",
        "serial = os.environ.get('ANDROID_SERIAL')",
        code,
        flags=re.MULTILINE,
    )
    lines = code.split('\n')
    needs_os = (bool(re.search(r'\bos\.environ\b', code)) or not re.search(r'^\s*serial\s*=\s*os\.environ', code, flags=re.MULTILINE)) and not re.search(r'^\s*import os\b', code, flags=re.MULTILINE)
    needs_u2 = bool(re.search(r'\bu2\.connect\b|\bserial\b', code))
    has_serial = bool(re.search(r'^\s*serial\s*=\s*os\.environ', code, flags=re.MULTILINE))
    has_connect = bool(re.search(r'^\s*d\s*=\s*u2\.connect', code, flags=re.MULTILINE))
    has_u2_import = bool(re.search(r'^\s*import uiautomator2 as u2', code, flags=re.MULTILINE))
    inserts = []
    if needs_os:
        inserts.append('import os')
    if needs_u2 and not has_u2_import:
        inserts.append('import uiautomator2 as u2')
    last_import = 0
    for i, ln in enumerate(lines):
        if re.match(r'^\s*(import |from )', ln):
            last_import = i + 1
    if inserts:
        lines[last_import:last_import] = inserts
    globals_block = []
    if not has_serial:
        globals_block.append("serial = os.environ.get('ANDROID_SERIAL')")
    if not has_connect and re.search(r'\bd\(', code):
        globals_block.append('d = u2.connect(serial)')
    if globals_block:
        idx = 0
        for i, ln in enumerate(lines):
            if re.match(r'^\s*(import |from )', ln):
                idx = i + 1
        lines[idx:idx] = [''] + globals_block
    # Ensure serial is defined before any u2.connect(serial) call.
    serial_def_re = re.compile(r"^\s*serial\s*=\s*os\.environ", re.MULTILINE)
    connect_re = re.compile(r"^\s*d\s*=\s*u2\.connect", re.MULTILINE)
    serial_idx = next((i for i, ln in enumerate(lines) if serial_def_re.match(ln)), None)
    connect_idx = next((i for i, ln in enumerate(lines) if connect_re.match(ln)), None)
    if serial_idx is not None and connect_idx is not None and serial_idx > connect_idx:
        serial_line = lines.pop(serial_idx)
        lines.insert(connect_idx, serial_line)
    return '\n'.join(lines)


def _strip_camera_template_code(code):
    if not code:
        return code
    lines = []
    for line in code.split('\n'):
        if line.startswith('from common.adb_common import'):
            line = 'from common.adb_common import run_adb_cmd'
        lines.append(line)
    code = '\n'.join(lines)

    # Remove camera constants commonly injected by camera-oriented template.
    code = re.sub(r'(?ms)^CAMERA_ACTIVITIES\s*=\s*\[\n.*?^\]\n', '', code)
    code = re.sub(r'(?ms)^CAMERA_PACKAGES\s*=\s*\[\n.*?^\]\n', '', code)

    # Remove camera helper blocks for Bluetooth-only auto cases.
    for fn_name in [
        '_launch_camera',
        '_camera_ready',
        '_count_photos',
        '_flash_mode_enabled',
        '_set_flash',
        '_capture_picture',
    ]:
        code = re.sub(
            rf'(?ms)^def {fn_name}\([^\n]*\):\n(?:^[ \t].*\n|^\n)*',
            '',
            code,
        )

    # Remove camera app force-stop lines from tearDown.
    code = re.sub(
        r"^\s*subprocess\.run\(\['adb',\s*'-s',\s*serial,\s*'shell',\s*'am',\s*'force-stop',\s*'(?:com\.android\.camera2|com\.google\.android\.GoogleCamera|org\.codeaurora\.snapcam)'.*\n",
        '',
        code,
        flags=re.MULTILINE,
    )

    code = re.sub(r'\n{3,}', '\n\n', code).strip() + '\n'
    return code


def _normalize_reboot_power_press(code):
    if not code:
        return code

    # Reboot cases must use long-press power key via ADB, not d.press('power').
    code = re.sub(
        r"^\s*d\.press\(\s*['\"]power['\"]\s*\)\s*$",
        "        subprocess.run(['adb', '-s', serial, 'shell', 'input', 'keyevent', '--longpress', '26'])",
        code,
        flags=re.MULTILINE,
    )

    code = re.sub(r'\n{3,}', '\n\n', code).strip() + '\n'
    return code


def _normalize_reboot_menu_click(code):
    if not code:
        return code

    # Avoid hardcoded single reboot text which is device-locale dependent.
    code = re.sub(
        r"^\s*d\(text=['\"](?:Restart|Reboot|重启)['\"]\)\.click\(\)\s*$",
        "        if d(text='Restart').exists(timeout=2):\n"
        "            d(text='Restart').click()\n"
        "        elif d(text='Reboot').exists(timeout=2):\n"
        "            d(text='Reboot').click()\n"
        "        elif d(text='重启').exists(timeout=2):\n"
        "            d(text='重启').click()\n"
        "        else:\n"
        "            subprocess.run(['adb', '-s', serial, 'shell', 'input', 'keyevent', '20'])\n"
        "            time.sleep(1)\n"
        "            subprocess.run(['adb', '-s', serial, 'shell', 'input', 'keyevent', '23'])",
        code,
        flags=re.MULTILINE,
    )

    code = re.sub(r'\n{3,}', '\n\n', code).strip() + '\n'
    return code


def _find_missing_called_helpers(code, target_class_name=None):
    try:
        tree = ast.parse(code)
    except Exception:
        return set(), set()

    imported_names = set()
    module_functions = set()
    class_methods = {}

    for node in tree.body:
        if isinstance(node, ast.Import):
            for alias in node.names:
                imported_names.add(alias.asname or alias.name.split('.')[0])
        elif isinstance(node, ast.ImportFrom):
            for alias in node.names:
                imported_names.add(alias.asname or alias.name)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            module_functions.add(node.name)
        elif isinstance(node, ast.ClassDef):
            methods = {
                n.name
                for n in node.body
                if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
            }
            class_methods[node.name] = methods

    builtins_obj = __builtins__
    builtin_names = set(builtins_obj.keys()) if isinstance(builtins_obj, dict) else set(dir(builtins_obj))

    missing_module_helpers = set()
    missing_self_methods = set()

    class _CallVisitor(ast.NodeVisitor):
        def __init__(self):
            self._class_stack = []

        def visit_ClassDef(self, node):
            self._class_stack.append(node.name)
            self.generic_visit(node)
            self._class_stack.pop()

        def visit_Call(self, node):
            func = node.func

            if isinstance(func, ast.Name):
                name = func.id
                if (
                    name.startswith('_')
                    and name not in module_functions
                    and name not in imported_names
                    and name not in builtin_names
                ):
                    missing_module_helpers.add(name)

            elif isinstance(func, ast.Attribute):
                if isinstance(func.value, ast.Name) and func.value.id == 'self' and func.attr.startswith('_'):
                    current_class = self._class_stack[-1] if self._class_stack else target_class_name
                    methods = class_methods.get(current_class, set())
                    if func.attr not in methods:
                        missing_self_methods.add(func.attr)

            self.generic_visit(node)

    _CallVisitor().visit(tree)
    return missing_module_helpers, missing_self_methods


def _inject_run_adb_shell_helper(code):
    if re.search(r'^\s*def\s+_run_adb_shell\s*\(', code, flags=re.MULTILINE):
        return code

    helper_block = (
        '\n\n'
        'def _run_adb_shell(command):\n'
        "    return run_adb_cmd(serial, f'shell {command}', log_print=False)\n"
    )

    m = re.search(r'^\s*d\s*=\s*u2\.connect\(serial\)\s*$', code, flags=re.MULTILINE)
    if m:
        return code[:m.end()] + helper_block + code[m.end():]

    m = re.search(r'^\s*class\s+\w+\s*\(', code, flags=re.MULTILINE)
    if m:
        return code[:m.start()] + helper_block + '\n' + code[m.start():]

    return code + helper_block + '\n'


def _inject_bt_dismiss_method(code, class_name):
    if re.search(r'^\s*def\s+_dismiss_bt_permission_dialog\s*\(', code, flags=re.MULTILINE):
        return code

    method_block = (
        '\n'
        '    def _dismiss_bt_permission_dialog(self, timeout_sec=3):\n'
        '        for _ in range(timeout_sec):\n'
        "            for label in ('ALLOW', 'Allow', 'OK', 'Yes', 'Turn on', 'Turn off'):\n"
        '                btn = d(text=label)\n'
        '                if btn.exists:\n'
        '                    btn.click()\n'
        '                    time.sleep(1)\n'
        '                    return\n'
        '            time.sleep(1)\n'
    )

    class_pattern = rf'(^\s*class\s+{re.escape(class_name)}\(unittest\.TestCase\):\s*$)'
    updated = re.sub(class_pattern, r'\1' + method_block, code, count=1, flags=re.MULTILINE)
    if updated != code:
        return updated

    fallback_pattern = r'(^\s*class\s+\w+\(unittest\.TestCase\):\s*$)'
    return re.sub(fallback_pattern, r'\1' + method_block, code, count=1, flags=re.MULTILINE)


# Module-level camera helpers that live in the camera reference file. When the
# LLM imitates the reference but drops one of these definitions while still
# calling it, we pull the original definition (and its dependencies) back in.
_CAMERA_HELPER_NAMES = frozenset({
    '_run_adb_shell', '_screen_size', '_tap_ratio', '_current_focus', 'remove_dir',
    '_dismiss_camera_dialog', '_launch_camera', '_camera_ready', '_count_photos',
    '_tap_first_existing', '_flash_mode_enabled', '_set_flash', '_capture_picture',
})


def _camera_reference_path():
    return os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        'case', 'smoking', 'test_L0_camera_flashlight_ANDROIDCN_36583.py',
    )


def _inject_camera_helpers_from_reference(code, missing_names):
    """Inject missing camera helper definitions (and their helper dependencies)
    from the camera reference file. Returns (new_code, injected_names)."""
    wanted = [n for n in missing_names if n in _CAMERA_HELPER_NAMES]
    if not wanted:
        return code, []

    ref_path = _camera_reference_path()
    if not os.path.isfile(ref_path):
        return code, []
    try:
        with open(ref_path, 'r', encoding='utf-8', errors='ignore') as rf:
            ref_src = rf.read()
        ref_tree = ast.parse(ref_src)
    except Exception:
        return code, []

    # name -> source segment, and name -> set of camera helper names it calls
    ref_sources = {}
    ref_deps = {}
    for node in ref_tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in _CAMERA_HELPER_NAMES:
            seg = ast.get_source_segment(ref_src, node)
            if not seg:
                continue
            ref_sources[node.name] = seg
            deps = set()
            for sub in ast.walk(node):
                if isinstance(sub, ast.Call) and isinstance(sub.func, ast.Name):
                    if sub.func.id in _CAMERA_HELPER_NAMES:
                        deps.add(sub.func.id)
            ref_deps[node.name] = deps

    # Resolve transitive dependencies among camera helpers
    needed = []
    seen = set()
    stack = list(wanted)
    while stack:
        name = stack.pop()
        if name in seen or name not in ref_sources:
            continue
        seen.add(name)
        stack.extend(ref_deps.get(name, set()))

    # Already-defined names in the generated code must not be re-injected
    try:
        code_tree = ast.parse(code)
        already_defined = {
            n.name for n in code_tree.body
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
        }
    except Exception:
        already_defined = set()

    # Emit in reference definition order for stable, readable output
    inject_order = [n.name for n in ref_tree.body
                    if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
                    and n.name in seen and n.name not in already_defined]
    if not inject_order:
        return code, []

    blocks = [ref_sources[name] for name in inject_order]
    helper_block = '\n\n' + '\n\n'.join(blocks) + '\n'

    # Insert before the first class definition; fall back to after d = u2.connect
    m = re.search(r'^\s*class\s+\w+\s*\(', code, flags=re.MULTILINE)
    if m:
        new_code = code[:m.start()] + helper_block.lstrip('\n') + '\n\n' + code[m.start():]
    else:
        m2 = re.search(r'^\s*d\s*=\s*u2\.connect\(serial\)\s*$', code, flags=re.MULTILINE)
        if m2:
            new_code = code[:m2.end()] + helper_block + code[m2.end():]
        else:
            new_code = code + helper_block

    return new_code, inject_order


def _ensure_camera_support_present(code):
    """Ensure imports/constants the injected camera helpers rely on exist."""
    additions_made = []

    if re.search(r'(^|\n)\s*def\s+_screen_size\s*\(', code) and 'import re' not in code:
        code = re.sub(r'(^import os\s*$)', r'\1\nimport re', code, count=1, flags=re.MULTILINE)
        additions_made.append('import re')

    needs_constants = '_launch_camera' in code and 'CAMERA_ACTIVITIES' in code \
        and not re.search(r'^\s*CAMERA_ACTIVITIES\s*=', code, flags=re.MULTILINE)
    if needs_constants:
        const_block = (
            "\nCAMERA_ACTIVITIES = [\n"
            "    'com.android.camera2/com.android.camera.CameraLauncher',\n"
            "    'org.codeaurora.snapcam/com.android.camera.CameraLauncher',\n"
            "]\n"
            "CAMERA_PACKAGES = [\n"
            "    'org.codeaurora.snapcam',\n"
            "    'com.android.camera2',\n"
            "    'com.android.camera',\n"
            "]\n"
        )
        m = re.search(r'^\s*d\s*=\s*u2\.connect\(serial\)\s*$', code, flags=re.MULTILINE)
        if m:
            code = code[:m.end()] + '\n' + const_block + code[m.end():]
            additions_made.append('CAMERA_ACTIVITIES/CAMERA_PACKAGES')

    return code, additions_made


def _ensure_called_helpers_defined(code, class_name):
    applied_fixes = []
    missing_module, missing_self = _find_missing_called_helpers(code, target_class_name=class_name)

    if '_run_adb_shell' in missing_module:
        updated = _inject_run_adb_shell_helper(code)
        if updated != code:
            code = updated
            applied_fixes.append('Injected missing helper: _run_adb_shell')

    if '_dismiss_bt_permission_dialog' in missing_self:
        updated = _inject_bt_dismiss_method(code, class_name)
        if updated != code:
            code = updated
            applied_fixes.append('Injected missing class method: _dismiss_bt_permission_dialog')

    # Pull any missing camera helpers (and their dependencies) from the reference
    missing_module, missing_self = _find_missing_called_helpers(code, target_class_name=class_name)
    camera_missing = [n for n in missing_module if n in _CAMERA_HELPER_NAMES]
    if camera_missing:
        code, injected = _inject_camera_helpers_from_reference(code, camera_missing)
        if injected:
            code, support = _ensure_camera_support_present(code)
            applied_fixes.append('Injected missing camera helpers: ' + ', '.join(injected))
            for item in support:
                applied_fixes.append('Added camera support: ' + item)

    missing_module, missing_self = _find_missing_called_helpers(code, target_class_name=class_name)
    return code, sorted(missing_module), sorted(missing_self), applied_fixes


def _generate_case_script_with_copilot(case_name, steps_text, log_fn=None):
    import time as _time

    def _log(line):
        if log_fn:
            try:
                log_fn(line)
            except Exception:
                pass

    cfg = _copilot_ai_config()
    if not cfg['enabled']:
        raise ValueError('COPILOT_AI_ENABLE is off')
    if not cfg['api_key']:
        raise ValueError('Missing token: set GITHUB_COPILOT_TOKEN (or COPILOT_API_KEY/GITHUB_TOKEN)')

    class_suffix = _to_class_suffix(case_name)
    method_name = f'test_{case_name}'
    is_bt_case = bool(
        re.search(r'(^|[_\s-])(bt|bluetooth)($|[_\s-])', case_name or '', re.IGNORECASE)
        or re.search(r'bluetooth|REQUEST_ENABLE|REQUEST_DISABLE', steps_text or '', re.IGNORECASE)
    )
    is_reboot_case = bool(
        re.search(r'(^|[_\s-])(reboot|restart|powercycle|power_cycle|boot)($|[_\s-])', case_name or '', re.IGNORECASE)
        or re.search(r'\breboot\b|\brestart\b|\bboot\b|keyevent\s*26|keyevent\s*223|REQUEST_REBOOT', steps_text or '', re.IGNORECASE)
    )
    is_camera_case = bool(
        re.search(r'(^|[_\s-])(camera|cam)($|[_\s-])', case_name or '', re.IGNORECASE)
        or re.search(r'\bcamera\b|\bcapture\s+(?:a\s+)?(?:picture|photo)\b|\bpicture\b|\bphoto\b|\bflash\b|\bshutter\b|dcim', steps_text or '', re.IGNORECASE)
    )
    camera_reference = ''
    ref_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'case', 'smoking', 'test_L0_camera_flashlight_ANDROIDCN_36583.py')
    if is_camera_case and os.path.isfile(ref_path):
        try:
            with open(ref_path, 'r', encoding='utf-8', errors='ignore') as _rf:
                camera_reference = _rf.read()
        except Exception:
            camera_reference = ''
    camera_block = (
        '=== IMITATE THIS REFERENCE FILE EXACTLY ===\n'
        'Generate the camera case by closely following the structure, imports, helpers and test flow of the reference below.\n'
        'Keep the import line "from common.adb_common import save_step_screenshot, detect_default_camera_activity, run_adb_cmd" intact.\n'
        f'Only change the class name to Test_{class_suffix}, the test method name to {method_name}, and adapt steps as needed.\n'
        '\n' + camera_reference + '\n'
    ) if camera_reference else ''
    prompt = (
        '# -*- coding:utf-8 -*-\n'
        'Generate one complete Python unittest file for Android UI automation using uiautomator2.\n'
        'Output Python source code only — no Markdown, no explanations.\n'
        f'Class name must be exactly: Test_{class_suffix}\n'
        f'Class definition must be exactly: class Test_{class_suffix}(unittest.TestCase):\n'
        f'Test method name must be exactly: {method_name}\n'
        '\n'
        + camera_block +
        'RULES:\n'
        '- class Test_*(unittest.TestCase) is mandatory.\n'
        '- Required module-level header BEFORE the class, in this exact order:\n'
        '    import os\n'
        '    import unittest\n'
        '    import uiautomator2 as u2\n'
        "    serial = os.environ.get('ANDROID_SERIAL')\n"
        '    d = u2.connect(serial)\n'
        "  serial MUST be defined before d = u2.connect(serial). Never use a placeholder like 'your_device_serial_here'.\n"
        '- Do NOT add device.alive checks.\n'
        '- Do NOT add flash-state assertions.\n'
        '- Do NOT import _run_adb_shell/remove_dir from common modules.\n'
        '- Do NOT create new common module files.\n'
        '\n'
        'Bluetooth rules (bluetooth-related cases only):\n'
        '- Use these exact shell intents for Bluetooth switching:\n'
        "  enable: adb shell am start -a android.bluetooth.adapter.action.REQUEST_ENABLE\n"
        "  disable: adb shell am start -a android.bluetooth.adapter.action.REQUEST_DISABLE\n"
        '- Do NOT use bluetooth_manager commands for BT switching in generated scripts.\n'
        '- Do NOT use settings put global bluetooth_on to simulate BT state changes.\n'
        '- For REQUEST_ENABLE, wait 2 seconds first, then call self._dismiss_bt_permission_dialog().\n'
        '- For REQUEST_DISABLE, wait 2 seconds first, then call self._dismiss_bt_permission_dialog().\n'
        '- Preferred sequence for REQUEST_ENABLE:\n'
        "  subprocess.run(['adb', '-s', serial, 'shell', 'am', 'start', '-a', 'android.bluetooth.adapter.action.REQUEST_ENABLE'])\n"
        '  time.sleep(2)\n'
        '  self._dismiss_bt_permission_dialog()\n'
        '- Preferred sequence for REQUEST_DISABLE:\n'
        '  time.sleep(2)\n'
        "  subprocess.run(['adb', '-s', serial, 'shell', 'am', 'start', '-a', 'android.bluetooth.adapter.action.REQUEST_DISABLE'])\n"
        '  time.sleep(2)\n'
        '  self._dismiss_bt_permission_dialog()\n'
        '- Add inside class:\n'
        '  def _dismiss_bt_permission_dialog(self, timeout_sec=3):\n'
        '      for _ in range(timeout_sec):\n'
        "          for label in ('ALLOW', 'Allow', 'OK', 'Yes', 'Turn on', 'Turn off'):\n"
        '              btn = d(text=label)\n'
        '              if btn.exists:\n'
        '                  btn.click()\n'
        '                  time.sleep(1)\n'
        '                  return\n'
        '          time.sleep(1)\n'
        '- If the test method calls _run_adb_shell(...), you MUST define module-level helper:\n'
        '  def _run_adb_shell(command):\n'
        "      return run_adb_cmd(serial, f'shell {command}', log_print=False)\n"
        '- Bluetooth-only cleanup rule: remove all camera-related unused code.\n'
        '- For bluetooth-related cases, do NOT include camera imports/constants/helpers.\n'
        '- Forbidden in bluetooth-related cases: detect_default_camera_activity, take_screenshot, CAMERA_ACTIVITIES, CAMERA_PACKAGES, _launch_camera, _camera_ready, _count_photos, _flash_mode_enabled, _set_flash, _capture_picture.\n'
        '- Do NOT add camera force-stop calls in tearDown for bluetooth-related cases.\n'
        '- For non-camera cases, remove all camera-related template code and camera app force-stop calls.\n'
        '- For Bluetooth enabled verification, use ADB state check, not UI text exists assertion.\n'
        "- Forbidden: assert d(text='Bluetooth').exists(timeout=5), 'Bluetooth should be enabled'\n"
        '- Poll bluetooth state for up to 8s before asserting (state does not flip instantly).\n'
        '- Preferred BT enable verification:\n'
        '  for _ in range(8):\n'
        "      bt_state = _run_adb_shell('settings get global bluetooth_on').strip()\n"
        "      if bt_state == '1': break\n"
        '      time.sleep(1)\n'
        "  self.assertEqual(bt_state, '1', 'Bluetooth should be enabled')\n"
        '- Preferred BT disable verification:\n'
        '  for _ in range(8):\n'
        "      bt_state = _run_adb_shell('settings get global bluetooth_on').strip()\n"
        "      if bt_state == '0': break\n"
        '      time.sleep(1)\n'
        "  self.assertEqual(bt_state, '0', 'Bluetooth should be disabled')\n"
        '\n'
        'Reboot cases (reboot-related cases only):\n'
        '- Do NOT use d.info["currentPackage"] or any UI element-based verification for reboot status.\n'
        '- Do NOT use d.press("power") for reboot action.\n'
        '- Use ADB long-press power key instead:\n'
        "  subprocess.run(['adb', '-s', serial, 'shell', 'input', 'keyevent', '--longpress', '26'])\n"
        '- Do NOT hardcode only one reboot menu text (for example only Restart).\n'
        '- Prefer multi-locale candidates and fallback keyevents:\n'
        "  if d(text='Restart').exists(timeout=2): d(text='Restart').click()\n"
        "  elif d(text='Reboot').exists(timeout=2): d(text='Reboot').click()\n"
        "  elif d(text='重启').exists(timeout=2): d(text='重启').click()\n"
        "  else: keyevent 20 then keyevent 23\n"
        '- For reboot verification, use ADB sys.boot_completed property check.\n'
        '- After device reboots, poll getprop sys.boot_completed in a loop (max 30s timeout).\n'
        '- Verify sys.boot_completed returns "1" to confirm full system boot.\n'
        '- Example reboot verification:\n'
        '  deadline = time.time() + 30\n'
        '  boot_completed = False\n'
        '  while time.time() < deadline:\n'
        '      try:\n'
        "          result = subprocess.run(['adb', '-s', serial, 'shell', 'getprop', 'sys.boot_completed'], stdout=subprocess.PIPE, stderr=subprocess.PIPE, encoding='utf-8', errors='ignore', timeout=5)\n"
        "          if result.stdout.strip() == '1':\n"
        '              boot_completed = True\n'
        '              break\n'
        '      except Exception:\n'
        '          pass\n'
        '      time.sleep(1)\n'
        "  self.assertTrue(boot_completed, 'Device did not reboot successfully')\n"
        '\n'
        f'Case name: {case_name}\n'
        f'Test steps:\n{steps_text}\n'
    )

    payload = {
        'model': cfg['model'],
        'messages': [
            {'role': 'system', 'content': 'You are GitHub Copilot writing production-grade Android auto-test scripts.'},
            {'role': 'user', 'content': prompt},
        ],
        'temperature': 0.2,
    }

    thinking_log = []
    steps_lines = [ln for ln in (steps_text or '').splitlines() if ln.strip()]
    thinking_log.append('═══════════════════════════════════════════════════════'); _log(thinking_log[-1])
    thinking_log.append('🤖 Copilot Script Generation Process'); _log(thinking_log[-1])
    thinking_log.append('═══════════════════════════════════════════════════════'); _log(thinking_log[-1])
    thinking_log.append(''); _log(thinking_log[-1])
    thinking_log.append(f'📋 Case Name: {case_name}'); _log(thinking_log[-1])
    thinking_log.append(f'🏷️  Class Name: Test_{class_suffix}'); _log(thinking_log[-1])
    thinking_log.append(f'📝 Method Name: {method_name}'); _log(thinking_log[-1])
    thinking_log.append(f'🔧 Model: {cfg["model"]}'); _log(thinking_log[-1])
    thinking_log.append(f'🌐 Endpoint: {cfg["chat_url"]}'); _log(thinking_log[-1])
    thinking_log.append(f'⏱️  Timeout: {cfg["timeout_sec"]}s'); _log(thinking_log[-1])
    thinking_log.append(''); _log(thinking_log[-1])
    thinking_log.append(f'📊 Input Steps ({len(steps_text or "")} chars):'); _log(thinking_log[-1])
    for line in steps_lines[:2]:
        s = line.strip()
        thinking_log.append(f'   └─ {s[:72]}{"..." if len(s) > 72 else ""}'); _log(thinking_log[-1])
    if len(steps_lines) > 2:
        thinking_log.append(f'   └─ ... ({len(steps_lines)} total lines)'); _log(thinking_log[-1])
    thinking_log.append(''); _log(thinking_log[-1])
    thinking_log.append('🔄 Generating Script...'); _log(thinking_log[-1])
    thinking_log.append(''); _log(thinking_log[-1])

    last_err = ''
    all_start = _time.time()
    for i, url in enumerate([cfg['chat_url']], start=1):
        thinking_log.append(f'[Attempt {i}] 📡 Endpoint: {url}'); _log(thinking_log[-1])
        try:
            req_start = _time.time()
            data = chat_completion(payload, config=cfg['copilot'])
            elapsed = _time.time() - req_start
            thinking_log.append(f'         ✓ Response received ({elapsed:.2f}s)'); _log(thinking_log[-1])

            msg = _extract_openai_text(data)
            thinking_log.append(f'         📦 Raw response: {len(msg)} chars'); _log(thinking_log[-1])
            msg_preview = (msg or '').strip().replace('\n', ' ')
            if msg_preview:
                thinking_log.append(f'         🔍 Preview: {msg_preview[:80]}{"..." if len(msg_preview) > 80 else ""}'); _log(thinking_log[-1])

            parse_start = _time.time()
            code = _sanitize_generated_python(_extract_code_from_llm_text(msg))
            parse_elapsed = _time.time() - parse_start
            if not code:
                detail = msg_preview[:200] if msg_preview else '<no text in response>'
                last_err = f'endpoint {url} returned no python code. Response was: {detail}'
                thinking_log.append(f'         ✗ Code extraction failed, response had no python: {detail}'); _log(thinking_log[-1])
                thinking_log.append(''); _log(thinking_log[-1])
                continue

            # No post-processing modifications — the prompt defines exact output.
            # Only remove legacy device.alive checks if present.
            code2 = re.sub(
                r'if\s+not\s+self\.d\.alive\s*:\s*\n\s*raise\s+RuntimeError\([^)]*\)\s*\n',
                '',
                code,
                flags=re.MULTILINE,
            )
            if code2 != code:
                code = code2
                thinking_log.append('         ✓ Removed device.alive check from setUp'); _log(thinking_log[-1])

            code2 = _ensure_module_globals(code)
            if code2 != code:
                code = code2
                thinking_log.append('         ✓ Restored module-level globals (serial/d)'); _log(thinking_log[-1])

            code2 = _ensure_method_self_params(code)
            if code2 != code:
                code = code2
                thinking_log.append('         ✓ Fixed class method missing self parameter'); _log(thinking_log[-1])

            if is_bt_case:
                code2 = _strip_camera_code_for_bt(code)
                if code2 != code:
                    code = code2
                    thinking_log.append('         ✓ Removed camera-related template code for Bluetooth case'); _log(thinking_log[-1])
            elif is_reboot_case or not is_camera_case:
                code2 = _strip_camera_template_code(code)
                if code2 != code:
                    code = code2
                    if is_reboot_case:
                        thinking_log.append('         ✓ Removed camera-related template code for reboot case'); _log(thinking_log[-1])
                    else:
                        thinking_log.append('         ✓ Removed camera-related template code for non-camera case'); _log(thinking_log[-1])
            elif is_camera_case:
                code2 = _ensure_camera_import(code)
                if code2 != code:
                    code = code2
                    thinking_log.append('         ✓ Restored camera helper import for camera case'); _log(thinking_log[-1])

            if is_reboot_case:
                code2 = _normalize_reboot_power_press(code)
                if code2 != code:
                    code = code2
                    thinking_log.append("         ✓ Replaced d.press('power') with ADB long-press power key"); _log(thinking_log[-1])

                code2 = _normalize_reboot_menu_click(code)
                if code2 != code:
                    code = code2
                    thinking_log.append('         ✓ Normalized reboot menu click with Restart/Reboot/重启 fallback'); _log(thinking_log[-1])

            thinking_log.append(f'         ✓ Code extracted ({parse_elapsed:.3f}s): {len(code)} chars'); _log(thinking_log[-1])

            syntax_start = _time.time()
            try:
                ast.parse(code)
            except SyntaxError as se:
                fallback = _sanitize_generated_python(msg)
                if fallback and fallback != code:
                    try:
                        ast.parse(fallback)
                        code = fallback
                        thinking_log.append('         ✓ Recovered from wrapped response, syntax repaired by sanitizer'); _log(thinking_log[-1])
                    except SyntaxError as se2:
                        last_err = f'endpoint {url} returned invalid python syntax (line {se2.lineno}): {se2.msg}'
                        thinking_log.append(f'         ✗ Syntax invalid (line {se2.lineno}): {se2.msg}'); _log(thinking_log[-1])
                        thinking_log.append(''); _log(thinking_log[-1])
                        continue
                else:
                    last_err = f'endpoint {url} returned invalid python syntax (line {se.lineno}): {se.msg}'
                    thinking_log.append(f'         ✗ Syntax invalid (line {se.lineno}): {se.msg}'); _log(thinking_log[-1])
                    thinking_log.append(''); _log(thinking_log[-1])
                    continue
            syntax_elapsed = _time.time() - syntax_start
            thinking_log.append(f'         ✓ Python syntax valid ({syntax_elapsed:.3f}s)'); _log(thinking_log[-1])

            code2 = re.sub(
                rf'^class\s+Test_{re.escape(class_suffix)}\s*:\s*$',
                f'class Test_{class_suffix}(unittest.TestCase):',
                code,
                flags=re.MULTILINE,
            )
            if code2 != code:
                code = code2
                thinking_log.append('         ✓ Normalized test class to inherit unittest.TestCase'); _log(thinking_log[-1])

            if f'class Test_{class_suffix}' not in code:
                last_err = f'endpoint {url} missing class Test_{class_suffix}'
                thinking_log.append(f'         ✗ Class validation failed: missing "class Test_{class_suffix}"'); _log(thinking_log[-1])
                thinking_log.append(''); _log(thinking_log[-1])
                continue
            thinking_log.append(f'         ✓ Class "Test_{class_suffix}" found'); _log(thinking_log[-1])

            if f'class Test_{class_suffix}(unittest.TestCase):' not in code:
                last_err = f'endpoint {url} class Test_{class_suffix} does not inherit unittest.TestCase'
                thinking_log.append(f'         ✗ Class validation failed: Test_{class_suffix} must inherit unittest.TestCase'); _log(thinking_log[-1])
                thinking_log.append(''); _log(thinking_log[-1])
                continue
            thinking_log.append(f'         ✓ Class "Test_{class_suffix}(unittest.TestCase)" confirmed'); _log(thinking_log[-1])

            if f'def {method_name}' not in code:
                last_err = f'endpoint {url} missing method {method_name}'
                thinking_log.append(f'         ✗ Method validation failed: missing "def {method_name}"'); _log(thinking_log[-1])
                thinking_log.append(''); _log(thinking_log[-1])
                continue
            thinking_log.append(f'         ✓ Method "def {method_name}(...)" found'); _log(thinking_log[-1])

            code, missing_module_helpers, missing_self_methods, applied_fixes = _ensure_called_helpers_defined(
                code,
                f'Test_{class_suffix}'
            )
            for fix_line in applied_fixes:
                thinking_log.append(f'         ✓ {fix_line}'); _log(thinking_log[-1])

            if missing_module_helpers or missing_self_methods:
                parts = []
                if missing_module_helpers:
                    parts.append('module helpers: ' + ', '.join(missing_module_helpers))
                if missing_self_methods:
                    parts.append('class methods: ' + ', '.join(missing_self_methods))
                missing_desc = '; '.join(parts)
                last_err = f'endpoint {url} has undefined method calls ({missing_desc})'
                thinking_log.append(f'         ✗ Helper completeness failed: {missing_desc}'); _log(thinking_log[-1])
                thinking_log.append(''); _log(thinking_log[-1])
                continue

            try:
                ast.parse(code)
            except SyntaxError as se:
                last_err = f'endpoint {url} became invalid after helper fix (line {se.lineno}): {se.msg}'
                thinking_log.append(f'         ✗ Post-fix syntax invalid (line {se.lineno}): {se.msg}'); _log(thinking_log[-1])
                thinking_log.append(''); _log(thinking_log[-1])
                continue
            thinking_log.append('         ✓ Helper completeness check passed'); _log(thinking_log[-1])

            imports = len(re.findall(r'^\s*(?:from\s+\S+\s+import\s+\S+|import\s+\S+)', code, flags=re.MULTILINE))
            methods = len(re.findall(r'^\s*def\s+\w+\s*\(', code, flags=re.MULTILINE))
            thinking_log.append(f'         📊 Analysis: {imports} imports, {methods} methods'); _log(thinking_log[-1])
            thinking_log.append(''); _log(thinking_log[-1])
            thinking_log.append('═══════════════════════════════════════════════════════'); _log(thinking_log[-1])
            thinking_log.append(f'✅ SUCCESS! Generated script with {len(code)} bytes'); _log(thinking_log[-1])
            thinking_log.append(f'⏱️  Total time: {_time.time() - all_start:.2f}s'); _log(thinking_log[-1])
            thinking_log.append('═══════════════════════════════════════════════════════'); _log(thinking_log[-1])
            return code, '\n'.join(thinking_log)
        except CopilotProviderError as e:
            last_err = f'endpoint {url} failed: {e}'
            thinking_log.append(f'         ✗ Copilot request failed: {e}'); _log(thinking_log[-1])
            thinking_log.append(''); _log(thinking_log[-1])
        except Exception as e:
            last_err = f'endpoint {url} failed: {e}'
            thinking_log.append(f'         ✗ Exception: {e}'); _log(thinking_log[-1])
            thinking_log.append(''); _log(thinking_log[-1])

    err_msg = last_err or 'Copilot request failed on all candidate endpoints'
    raise ValueError(err_msg)


def _run_tests(devices):
    global _state
    _state = {'status': 'running', 'log': ''}

    import subprocess as sp
    import sys

    base_dir = os.path.dirname(os.path.realpath(__file__))
    log_lock = threading.Lock()
    device_results = {}   # serial -> True(PASS) / False(FAIL)

    def _get_display(serial):
        """Return serial_model display name; fallback to serial on failure."""
        try:
            model = subprocess.check_output(
                f'adb -s {serial} shell getprop ro.product.model',
                shell=True, timeout=5
            ).decode('utf-8', errors='ignore').strip()
            return f'{serial}_{model}' if model else serial
        except Exception:
            return serial

    def _run_one(serial):
        display = _get_display(serial)
        dev_pass = True

        with log_lock:
            _state['log'] += f'[Device] {display} started\n'

        cmd = [
            RUNNER_PYTHON, '-c',
            f"import os, sys; "
            f"os.environ['ANDROID_SERIAL']='{serial}'; "
            f"sys.path.insert(0, r'{base_dir}'); "
            f"from run_all import run_on_device; run_on_device('{serial}')"
        ]
        try:
            proc = sp.Popen(cmd, stdout=sp.PIPE, stderr=sp.STDOUT,
                            text=True, encoding='utf-8', errors='replace',
                            cwd=base_dir)
            for line in proc.stdout:
                line = line.rstrip()
                if not line:
                    continue
                if ' ... PASS' in line:
                    case_name = line.split(' ... ')[0].rsplit('.', 1)[-1]
                    with log_lock:
                        _state['log'] += f'  [{display}] {case_name} -> PASS\n'
                elif ' ... FAIL' in line:
                    case_name = line.split(' ... ')[0].rsplit('.', 1)[-1]
                    dev_pass = False
                    with log_lock:
                        _state['log'] += f'  [{display}] {case_name} -> FAIL\n'
                elif ' ... ERROR' in line:
                    case_name = line.split(' ... ')[0].rsplit('.', 1)[-1]
                    dev_pass = False
                    with log_lock:
                        _state['log'] += f'  [{display}] {case_name} -> ERROR\n'
            proc.wait()
            if proc.returncode != 0:
                dev_pass = False
                with log_lock:
                    _state['log'] += f'[Device] {display} process exited abnormally (code={proc.returncode})\n'
        except Exception as e:
            dev_pass = False
            with log_lock:
                _state['log'] += f'[Device] {display} execution error: {e}\n'

        result_str = 'PASS' if dev_pass else 'FAIL'
        with log_lock:
            _state['log'] += f'[Device] {display} all cases finished, final result -> {result_str}\n'
            device_results[serial] = dev_pass

    try:
        # Start one independent thread per device for parallel execution.
        threads = [threading.Thread(target=_run_one, args=(s,), daemon=True) for s in devices]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        all_pass = all(device_results.get(s, False) for s in devices)
        _state['status'] = 'done'
        _state['log'] += '\nAll device tests completed -> {}\n'.format('PASS' if all_pass else 'FAIL')
    except Exception as e:
        _state['status'] = 'error'
        _state['log'] += f'\nError: {e}'


def _run_case_generation_job(job_id, case_name, case_steps, component_name, component_dir, filename, path):
    _append_case_gen_log(job_id, f'🧩 Job started: {job_id}')
    _append_case_gen_log(job_id, f'🗂️  Target file: case/{component_name}/{filename}')

    try:
        script, _ = _generate_case_script_with_copilot(
            case_name,
            case_steps,
            log_fn=lambda line: _append_case_gen_log(job_id, line)
        )
        with open(path, 'w', encoding='utf-8') as f:
            f.write(script)

        rel_path = os.path.relpath(path, BASE_DIR).replace('\\', '/')
        with _case_gen_lock:
            job = _case_gen_jobs.get(job_id)
            if job:
                job['status'] = 'done'
                job['file'] = filename
                job['path'] = rel_path
                job['component'] = component_name
                job['updated_at'] = time.time()
        _append_case_gen_log(job_id, f'📦 Saved file: {rel_path}')
        _append_case_gen_log(job_id, '🏁 Job finished.')
    except Exception as e:
        with _case_gen_lock:
            job = _case_gen_jobs.get(job_id)
            if job:
                job['status'] = 'error'
                job['err'] = f'Copilot generation failed: {e}'
                job['updated_at'] = time.time()
        _append_case_gen_log(job_id, f'❌ Job failed: {e}')


@app.route('/')
def index():
    return render_template_string(PAGE)


@app.route('/api/devices')
def api_devices():
    return jsonify(_get_devices())


@app.route('/api/run', methods=['POST'])
def api_run():
    if _state['status'] == 'running':
        return jsonify({'err': 'Test is already running'}), 409
    devs = request.json.get('devices', [])
    if not devs:
        return jsonify({'err': 'No devices selected'}), 400
    threading.Thread(target=_run_tests, args=(devs,), daemon=True).start()
    return jsonify({'ok': True})


@app.route('/api/status')
def api_status():
    return jsonify(_state)


@app.route('/api/reports')
def api_reports():
    if not os.path.isdir(REPORT_DIR):
        return jsonify([])
    import time as _time
    files = sorted([f for f in os.listdir(REPORT_DIR) if f.endswith('.html')], reverse=True)
    result = []
    for f in files:
        mtime = os.path.getmtime(os.path.join(REPORT_DIR, f))
        t = _time.strftime('%Y-%m-%d %H:%M:%S', _time.localtime(mtime))
        result.append({'name': f, 'time': t})
    return jsonify(result)


@app.route('/api/reports/delete', methods=['POST'])
def api_reports_delete():
    data = request.get_json() or {}
    files = data.get('files', [])
    deleted = 0
    for f in files:
        # Safety check: only delete html files under report directory
        if '..' in f or '/' in f or '\\' in f:
            continue
        path = os.path.join(REPORT_DIR, f)
        if os.path.isfile(path) and f.endswith('.html'):
            os.remove(path)
            deleted += 1
    return jsonify({'deleted': deleted})


@app.route('/api/case-generator', methods=['POST'])
def api_case_generator():
    data = request.get_json() or {}
    case_name_raw = (data.get('caseName') or '').strip()
    component_raw = (data.get('component') or '').strip()
    case_steps = (data.get('stepsText') or '').strip()
    # Fallback: support legacy stepPairs / caseSteps format
    if not case_steps:
        case_steps = _compose_steps_text(data.get('stepPairs'), data.get('caseSteps'))
    overwrite = bool(data.get('overwrite', False))

    case_name = _normalize_case_name(case_name_raw)
    if not case_name:
        return jsonify({'err': 'Case name is required and must contain letters or numbers.'}), 400
    if not case_steps:
        return jsonify({'err': 'Case detailed steps are required.'}), 400

    component_name, component_dir = _resolve_component_dir(component_raw, create=True)
    filename = f'test_{case_name}.py'
    path = os.path.join(component_dir, filename)
    if os.path.exists(path) and not overwrite:
        return jsonify({'err': f'File already exists: {filename}', 'exists': True, 'file': filename}), 409

    try:
        script, _thinking_log = _generate_case_script_with_copilot(case_name, case_steps)
    except Exception as e:
        return jsonify({'err': f'Copilot generation failed: {e}'}), 502

    with open(path, 'w', encoding='utf-8') as f:
        f.write(script)

    rel_path = os.path.relpath(path, BASE_DIR).replace('\\', '/')
    return jsonify({
        'ok': True,
        'file': filename,
        'path': rel_path,
        'component': component_name,
        'generatedBy': 'copilot-ai'
    })


@app.route('/api/case-generator/start', methods=['POST'])
def api_case_generator_start():
    data = request.get_json() or {}
    case_name_raw = (data.get('caseName') or '').strip()
    component_raw = (data.get('component') or '').strip()
    case_steps = (data.get('stepsText') or '').strip()
    if not case_steps:
        case_steps = _compose_steps_text(data.get('stepPairs'), data.get('caseSteps'))
    overwrite = bool(data.get('overwrite', False))

    case_name = _normalize_case_name(case_name_raw)
    if not case_name:
        return jsonify({'err': 'Case name is required and must contain letters or numbers.'}), 400
    if not case_steps:
        return jsonify({'err': 'Case detailed steps are required.'}), 400

    component_name, component_dir = _resolve_component_dir(component_raw, create=True)
    filename = f'test_{case_name}.py'
    path = os.path.join(component_dir, filename)
    if os.path.exists(path) and not overwrite:
        return jsonify({'err': f'File already exists: {filename}', 'exists': True, 'file': filename}), 409

    job_id = _create_case_gen_job(case_name, component_name)
    t = threading.Thread(
        target=_run_case_generation_job,
        args=(job_id, case_name, case_steps, component_name, component_dir, filename, path),
        daemon=True,
    )
    t.start()
    return jsonify({'ok': True, 'jobId': job_id})


@app.route('/api/case-generator/status')
def api_case_generator_status():
    job_id = (request.args.get('jobId') or '').strip()
    if not job_id:
        return jsonify({'err': 'jobId is required'}), 400
    with _case_gen_lock:
        job = _case_gen_jobs.get(job_id)
        if not job:
            return jsonify({'err': f'Job not found: {job_id}'}), 404
        payload = {
            'ok': True,
            'jobId': job['jobId'],
            'status': job['status'],
            'log': job['log'],
            'err': job['err'],
            'component': job['component'],
            'file': job['file'],
            'path': job['path'],
            'generatedBy': job['generatedBy'],
            'logFile': job['log_file'],
            'updatedAt': job['updated_at'],
        }
    return jsonify(payload)


@app.route('/api/case-scripts')
def api_case_scripts():
    component_raw = (request.args.get('component') or '').strip()
    component_name, component_dir = _resolve_component_dir(component_raw, create=True)
    items = []
    for name in os.listdir(component_dir):
        if not _is_safe_case_file(name):
            continue
        full = os.path.join(component_dir, name)
        if not os.path.isfile(full):
            continue
        mtime = os.path.getmtime(full)
        items.append({
            'name': name,
            'mtime': time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(mtime))
        })
    items.sort(key=lambda x: x['name'])
    return jsonify({'count': len(items), 'items': items, 'component': component_name})


@app.route('/api/case-script-content')
def api_case_script_content():
    component_raw = (request.args.get('component') or '').strip()
    component_name, component_dir = _resolve_component_dir(component_raw, create=False)
    name = (request.args.get('file') or '').strip()
    if not _is_safe_case_file(name):
        return jsonify({'err': 'Invalid file name.'}), 400

    path = os.path.join(component_dir, name)
    if not os.path.isfile(path):
        return jsonify({'err': 'File not found.'}), 404

    with open(path, 'r', encoding='utf-8', errors='replace') as f:
        content = f.read()
    rel_path = os.path.relpath(path, BASE_DIR).replace('\\', '/')
    return jsonify({'file': name, 'path': rel_path, 'content': content, 'component': component_name})


@app.route('/api/parse-csv', methods=['POST'])
def api_parse_csv():
    if 'file' not in request.files:
        return jsonify({'err': 'No file provided'}), 400
    
    file = request.files['file']
    if not file.filename:
        return jsonify({'err': 'Empty filename'}), 400
    
    try:
        stream = io.StringIO(file.read().decode('utf-8', errors='replace'))
        reader = csv.DictReader(stream)
        rows = []
        for row in reader:
            action = (row.get('Action') or row.get('action') or '').strip()
            expected = (row.get('Expected Result') or row.get('expected_result') or row.get('expected') or '').strip()
            if action:
                rows.append({'step': action, 'expected': expected})
        
        filename = file.filename
        case_name = os.path.splitext(filename)[0]
        
        return jsonify({
            'ok': True,
            'case_name': case_name,
            'rows': rows,
            'filename': filename
        })
    except Exception as e:
        return jsonify({'err': f'CSV parse error: {str(e)}'}), 400


@app.route('/api/run-case', methods=['POST'])
def api_run_case():
    data = request.get_json() or {}
    file_name = (data.get('file') or '').strip()
    component_raw = (data.get('component') or '').strip()
    serial = (data.get('serial') or '').strip()

    if not _is_safe_case_file(file_name):
        return jsonify({'err': 'Invalid case file.'}), 400

    component_name, component_dir = _resolve_component_dir(component_raw, create=False)
    case_path = os.path.join(component_dir, file_name)
    if not os.path.isfile(case_path):
        return jsonify({'err': f'Case file not found: {file_name}'}), 404

    devices = _get_devices()
    if not devices:
        return jsonify({'err': 'No connected devices detected.'}), 400

    if not serial:
        serial = devices[0]['serial']
    elif serial not in [d['serial'] for d in devices]:
        return jsonify({'err': f'Selected device not connected: {serial}'}), 400

    module_name = f"case.{component_name}.{os.path.splitext(file_name)[0]}"
    cmd = [RUNNER_PYTHON, '-m', 'unittest', module_name, '-v']
    env = os.environ.copy()
    env['ANDROID_SERIAL'] = serial

    try:
        proc = subprocess.run(
            cmd,
            cwd=BASE_DIR,
            env=env,
            shell=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            encoding='utf-8',
            errors='replace',
            timeout=1200,
        )
        out = proc.stdout or ''
        status = 'PASS' if proc.returncode == 0 else 'FAIL'
        return jsonify({
            'ok': True,
            'status': status,
            'returncode': proc.returncode,
            'file': file_name,
            'component': component_name,
            'serial': serial,
            'output': out,
        })
    except subprocess.TimeoutExpired as e:
        return jsonify({
            'ok': False,
            'status': 'TIMEOUT',
            'file': file_name,
            'component': component_name,
            'serial': serial,
            'output': (e.stdout or '') + '\n[Timeout] Single case execution exceeded 1200s.',
        }), 504
    except Exception as e:
        return jsonify({'err': f'Run case error: {e}'}), 500


@app.route('/report/<path:name>')
def report(name):
    return send_from_directory(REPORT_DIR, name)


@app.route('/api/ai_fail_analysis', methods=['POST'])
def api_ai_fail_analysis():
    """AI自查分析接口：分析Fail case的失败原因，判断是代码问题还是真实Bug。"""
    data = request.get_json() or {}
    test_id    = (data.get('testId')    or '').strip()
    test_class = (data.get('testClass') or '').strip()
    method     = (data.get('method')    or '').strip()
    error_info = (data.get('errorInfo') or '').strip()
    stdout_log = (data.get('stdout')    or '').strip()

    if not test_id and not method:
        return jsonify({'err': 'testId or method is required'}), 400

    cfg = _copilot_ai_config()
    if not cfg['enabled']:
        return jsonify({'err': 'AI功能未启用，请设置 COPILOT_AI_ENABLE=1'}), 503
    if not cfg['api_key']:
        return jsonify({'err': '缺少 API Token，请设置 GITHUB_COPILOT_TOKEN 环境变量'}), 503

    # ── 1. 查找测试用例源文件 ──────────────────────────────────
    case_code = ''
    case_file_path = ''
    search_name = test_class or (test_id.split('.')[-2] if '.' in test_id else '')
    if search_name:
        for root, dirs, files in os.walk(CASE_ROOT_DIR):
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

    prompt = f"""你是一名资深Android自动化测试工程师。请根据下面的Fail用例信息，进行自查分析，并输出结构化报告。

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
  - 说明哪里写错了
  - 给出修复方案（可包含代码片段）
  - 通知建议：请 auto case 维护人员修复此用例

如果是**产品Bug**：
  - 描述Bug的触发条件和现象
  - 给出可能的根因分析
  - 给出供开发参考的排查/修复建议

如果是**环境问题**：
  - 说明具体的环境配置要求
  - 给出恢复步骤
"""

    payload = {
        'model': cfg['model'],
        'messages': [
            {'role': 'system', 'content': '你是资深Android自动化测试专家，能够准确区分测试脚本问题和产品Bug。请用中文回答。'},
            {'role': 'user', 'content': prompt},
        ],
        'temperature': 0.3,
    }

    # ── 3. 调用 AI ─────────────────────────────────────────────
    try:
        data_resp = chat_completion(payload, config=cfg['copilot'])
        analysis_text = _extract_openai_text(data_resp)
        if not analysis_text:
            raise ValueError('empty response')
        return jsonify({
            'ok': True,
            'analysis': analysis_text,
            'caseFile': case_file_path,
            'model': cfg['model'],
        })
    except CopilotProviderError as e:
        last_err = str(e)
    except Exception as e:
        last_err = str(e)

    return jsonify({'err': f'AI分析请求失败: {last_err}'}), 502


# ──────────────────── HTML ────────────────────
PAGE = r'''<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Automation AI Agent</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font:15px/1.6 "Segoe UI","Microsoft YaHei",sans-serif;background:linear-gradient(135deg,#2a3f5f,#3a5575);color:#d4dde8;min-height:100vh}
header{padding:16px 28px;background:rgba(20,35,60,.7);border-bottom:1px solid rgba(0,229,255,.15);display:flex;align-items:center;gap:14px}
header h1{font-size:22px;color:#00e5ff}
header small{color:#6a9ab8;font-size:13px}
.wrap{margin:20px 28px;padding:0}
.row{display:flex;gap:20px;align-items:stretch}
.col-left{flex:1;min-width:0}
.col-right{flex:1.5;min-width:0}
.box{background:rgba(20,40,65,.75);border:1px solid rgba(0,229,255,.12);border-radius:10px;padding:20px;margin-bottom:18px;backdrop-filter:blur(2px);height:100%}
.box-t{font-size:15px;color:#00e5ff;font-weight:700;margin-bottom:14px;border-left:3px solid #00e5ff;padding-left:10px}
.bar{display:flex;align-items:center;gap:12px;flex-wrap:wrap}
button{padding:8px 20px;border:1px solid rgba(0,229,255,.3);border-radius:5px;background:rgba(0,229,255,.06);color:#00e5ff;font-size:14px;font-weight:600;cursor:pointer;transition:.15s}
button:hover{background:rgba(0,229,255,.15);box-shadow:0 0 8px rgba(0,229,255,.12)}
button.go{border-color:rgba(0,255,120,.4);color:#00ff78;background:rgba(0,255,120,.05);font-size:15px;padding:10px 28px}
button.go:hover{background:rgba(0,255,120,.15)}
button:disabled{opacity:.3;cursor:default}
.devs{display:flex;flex-wrap:wrap;gap:10px;margin-top:14px}
.d{padding:10px 18px;border:1px solid rgba(0,229,255,.15);border-radius:6px;cursor:pointer;font-size:14px;transition:.15s;background:rgba(0,40,70,.3);display:flex;align-items:center;gap:8px}
.d input[type="checkbox"]{width:16px;height:16px;accent-color:#00e5ff;cursor:pointer}
.d:hover{border-color:#00e5ff;background:rgba(0,60,100,.3)}
.d.on{border-color:#00e5ff;background:rgba(0,229,255,.1);color:#fff;box-shadow:0 0 8px rgba(0,229,255,.12)}
.cnt{font-size:13px;color:#5a8a9f;margin-left:auto}
.lnk{font-size:13px;color:#6aaccf;cursor:pointer;text-decoration:underline}
.lnk:hover{color:#00e5ff}
.badge{font-size:13px;padding:4px 12px;border-radius:4px;margin-left:10px}
.b-idle{background:rgba(255,255,255,.05);color:#5a8a9f}
.b-run{background:rgba(255,170,0,.12);color:#ffa726;animation:bk 1.2s infinite}
.b-done{background:rgba(0,255,120,.08);color:#00ff78}
@keyframes bk{50%{opacity:.5}}
.prog{height:6px;background:rgba(255,255,255,.04);border-radius:3px;margin:12px 0;overflow:hidden}
.prog i{display:block;height:100%;background:linear-gradient(90deg,#00e5ff,#00ff78);width:0%;transition:width .4s}
.log{background:rgba(5,15,30,.6);border:1px solid rgba(0,229,255,.06);border-radius:6px;padding:14px;font:13px/1.6 monospace;color:#6ad8d8;height:calc(100% - 130px);min-height:200px;overflow-y:auto;white-space:pre-wrap;margin-top:10px}
table{width:100%;border-collapse:collapse;margin-top:12px;font-size:14px}
th{text-align:left;color:#5a8a9f;padding:8px 12px;border-bottom:1px solid rgba(255,255,255,.06);font-size:13px}
td{padding:8px 12px;border-bottom:1px solid rgba(255,255,255,.03)}
tr:hover td{background:rgba(0,229,255,.03)}
td a{color:#00e5ff;text-decoration:none;border:1px solid rgba(0,229,255,.25);padding:4px 12px;border-radius:4px;font-size:13px}
td a:hover{background:rgba(0,229,255,.1)}
.no{color:#3a6080;font-size:14px;padding:12px 0}
.tabs{display:flex;gap:10px;margin-bottom:14px;flex-wrap:wrap}
.tab-btn{padding:8px 18px;border:1px solid rgba(0,229,255,.22);border-radius:18px;background:rgba(6,38,62,.5);color:#86b8d3;font-weight:700;cursor:pointer}
.tab-btn:hover{border-color:#00e5ff;color:#c8f8ff}
.tab-btn.on{background:linear-gradient(90deg,rgba(0,229,255,.18),rgba(0,255,120,.18));color:#d6ffff;border-color:rgba(0,255,200,.45)}
.panel{display:none}
.panel.on{display:block}
.fm{display:flex;flex-direction:column;gap:10px;margin-top:8px}
.ipt,.txa{width:100%;background:rgba(5,15,30,.6);border:1px solid rgba(0,229,255,.14);border-radius:6px;color:#d4dde8;padding:10px;font-size:14px}
.txa{min-height:160px;resize:vertical;line-height:1.5}
.hint{font-size:13px;color:#5a8a9f}
.step-grid{display:grid;grid-template-columns:84px 1.2fr 1fr 140px;gap:8px;align-items:center}
.step-head{font-size:12px;color:#6fa8c5;font-weight:700;margin-top:4px}
.step-row{margin-top:6px}
.small-btn{padding:7px 10px;font-size:12px}
.step-no{font-size:12px;color:#8ec9df;padding-left:8px}
.step-ops{display:flex;gap:6px;justify-content:flex-end}
.drag-btn{cursor:grab}
.step-row.dragging{opacity:.5}
.step-row.drag-over{outline:1px dashed rgba(0,229,255,.5);border-radius:6px}
.showcase{display:grid;grid-template-columns:280px minmax(0,1fr);gap:14px;margin-top:14px;min-width:0}
.list-pane{background:rgba(5,15,30,.45);border:1px solid rgba(0,229,255,.12);border-radius:8px;padding:10px;max-height:360px;display:flex;flex-direction:column;gap:8px}
.script-list{flex:1;min-height:240px;overflow-y:auto;overflow-x:scroll;border:1px solid rgba(0,229,255,.08);border-radius:8px;padding:6px 4px 6px 8px;scrollbar-gutter:stable}
.script-list-inner{min-width:100%;width:max-content;padding-left:0}
.code-pane{background:rgba(5,15,30,.45);border:1px solid rgba(0,229,255,.12);border-radius:8px;padding:10px;min-width:0;overflow:hidden}
.file-item{padding:8px 10px;border-radius:6px;border:1px solid transparent;cursor:pointer;display:block;gap:8px;color:#9fc5dd;font-size:13px;min-width:100%;width:max-content}
.file-item:hover{border-color:rgba(0,229,255,.25);background:rgba(0,229,255,.08)}
.file-item.on{border-color:rgba(0,255,200,.45);background:rgba(0,229,255,.14);color:#e5fcff}
.file-name{display:block;white-space:nowrap;line-height:1.35;user-select:text}
.file-time{display:block;color:#5a8a9f;font-size:12px;margin-top:4px}
.code-title{font-size:13px;color:#8cbcd9;margin-bottom:8px}
.code-view{background:rgba(5,15,30,.7);border:1px solid rgba(0,229,255,.08);border-radius:6px;padding:12px;font:12px/1.5 Consolas,Monaco,monospace;color:#bde4ff;white-space:pre;overflow:auto;max-height:320px;max-width:100%;width:100%}
.run-tools{margin-top:10px;padding-top:10px;border-top:1px dashed rgba(0,229,255,.15)}
.run-log{background:rgba(5,15,30,.7);border:1px solid rgba(0,229,255,.1);border-radius:6px;padding:10px;font:12px/1.5 Consolas,Monaco,monospace;color:#bde4ff;white-space:pre-wrap;max-height:220px;overflow:auto;margin-top:8px}
.fix-tag{display:inline-block;background:rgba(251,191,36,.12);border:1px solid rgba(251,191,36,.3);border-radius:4px;padding:1px 6px;font-size:12px;color:#fbbf24;margin:2px 0}
@media (max-width: 980px){.showcase{grid-template-columns:1fr}}
</style>
</head>
<body>
<header><h1>Automation AI Agent</h1><small>AI Agent Auto-Generates Intelligent Test Scripts</small></header>
<div class="wrap">
<div class="tabs">
    <!-- <button class="tab-btn on" id="tab-main" onclick="switchTab('main')">Execution Console</button> -->
    <!--<button class="tab-btn on" id="tab-gen" onclick="switchTab('gen')">Case Script Generator</button> -->
</div>

<!-- <div class="panel on" id="panel-main">
<div class="row">

<div class="col-left"><div class="box"><div class="box-t">🔌 Device List</div>
<div class="bar"><button onclick="scan()">Scan Devices</button><span class="lnk" onclick="ckAll()">Select All</span><span class="lnk" onclick="unAll()">Clear</span><span class="cnt" id="ct"></span></div>
<div class="devs" id="dv"><span class="no">Click scan to detect devices</span></div></div></div>

<div class="col-right"><div class="box"><div class="box-t">▶ Run Tests</div>
<div class="bar"><button class="go" id="rb" onclick="go()">Start Test</button><span class="badge b-idle" id="bd">Idle</span></div>
<div class="prog"><i id="pg"></i></div>
<div class="log" id="lg">Waiting for action...</div></div></div>
</div>

<div class="box"><div class="box-t">📊 Test Reports</div>
<button onclick="rpt()">Refresh</button>
<table><thead><tr><th>Report File</th><th>Device</th><th>Generated At</th><th>Action</th></tr></thead><tbody id="tb"><tr><td colspan="4" class="no">No reports yet</td></tr></tbody></table></div>
</div> -->

<div class="panel on" id="panel-gen">
    <div class="box">
        <div class="box-t">🧩 Auto Generate Case Script</div>
        <div class="hint">Input: Component + Case name + per-step action and expected result. Output: auto-created script in case/&lt;Component&gt; as test_case_name.py.</div>
        <div class="fm">
            <div class="bar" style="gap:8px; margin-bottom:8px">
                <input id="csvFile" type="file" accept=".csv,.xlsx,.xls" style="flex:1; padding:6px; font-size:13px; background:rgba(5,15,30,.6); border:1px solid rgba(0,229,255,.14); border-radius:6px; color:#d4dde8" />
                <button class="small-btn" onclick="parseCsv()">Upload CSV</button>
            </div>
            <div class="bar" style="gap:8px; margin-bottom:0">
                <input id="caseName" class="ipt" type="text" placeholder="Case name, e.g.: backlight_15s" style="flex:2" />
                <input id="componentName" class="ipt" type="text" placeholder="Component, e.g.: Camera" style="flex:1; min-width:200px" />
            </div>
            <div class="hint" style="margin-top:4px">Step format: action description <code style="color:#00e5ff;background:rgba(0,229,255,.08);padding:1px 5px;border-radius:3px">-verify:</code> expected result to validate in code. One step per line, numeric prefixes are supported (for example <code style="color:#00e5ff">1.</code>)</div>
            <textarea id="stepsText" class="txa" style="min-height:180px;font-family:Consolas,Monaco,monospace;font-size:13px;line-height:1.6" placeholder="1. Lauch camera and capture a picture -verify: Verify camera works nornally&#10;2. Enable flashlight and capture a picture -verify: Verify that flashlight works when taking pictures.&#10;3. Disable flashlight and capture a picture -verify: Verify that flashlight does not works when taking pictures.&#10;4. Turn on the camera preview function -verify: Camera app can automatically focus and take pictures&#10;5. Save and delete the photos taken -verify: Saving and deleting is easy"></textarea>
            <div class="bar">
                <button onclick="genCase(false)">Generate Script</button>
                <button onclick="genCase(true)">Overwrite Existing</button>
                <span class="cnt" id="genResult">Ready</span>
            </div>
            <pre id="genThinkingLog" class="run-log" style="max-height:300px">Thinking log will appear here...</pre>
            <div class="run-tools">
                <div class="bar" style="gap:8px">
                    <select id="runSerial" class="ipt" style="max-width:320px;padding:8px" onmousedown="loadRunDevices()">
                        <option value="">Auto-select first connected device</option>
                    </select>
                    <button id="runCaseBtn" onclick="runSelectedCase()">Run Selected Case</button>
                    <span class="cnt" id="runCaseStatus">No run yet</span>
                </div>
                <div id="runCaseLog" class="run-log">Execution log will appear here...</div>
            </div>
        </div>
        <div class="showcase">
            <div class="list-pane">
                <div class="box-t" id="scriptListTitle" style="margin-bottom:8px;font-size:13px">📁 case/smoking Scripts</div>
                <div id="scriptList" class="script-list"><div class="script-list-inner"><div class="no">Loading...</div></div></div>
            </div>
            <div class="code-pane">
                <div class="code-title" id="codeTitle">No script selected</div>
                <pre class="code-view" id="codeView">Select a script from the left list to preview code.</pre>
            </div>
        </div>
    </div>
</div>

<script>
let D=[],S=new Set()
let draggedStepRow = null
let currentCaseFile = ''
let currentComponent = 'smoking'
let currentCaseComponent = 'smoking'
let caseGenPollTimer = null

function normalizeComponentName(raw){
    const cleaned = (raw || '').trim().replace(/[^A-Za-z0-9_]/g, '')
    return cleaned || 'smoking'
}

function getSelectedComponent(){
    const ipt = document.getElementById('componentName')
    const normalized = normalizeComponentName(ipt ? ipt.value : '')
    if(ipt){ipt.value = normalized}
    return normalized
}

function setScriptListTitle(component){
    const title = document.getElementById('scriptListTitle')
    if(title){title.textContent = `📁 case/${component} Scripts`}
}

function switchTab(tab){
    const isMain = tab === 'main'
    const tabMain = document.getElementById('tab-main')
    const tabGen = document.getElementById('tab-gen')
    const panelMain = document.getElementById('panel-main')
    const panelGen = document.getElementById('panel-gen')
    if(tabMain){tabMain.classList.toggle('on', isMain)}
    if(tabGen){tabGen.classList.toggle('on', !isMain)}
    if(panelMain){panelMain.classList.toggle('on', isMain)}
    if(panelGen){panelGen.classList.toggle('on', !isMain)}
    if(!isMain){
        const comp = getSelectedComponent()
        currentComponent = comp
        setScriptListTitle(comp)
        loadScriptList(undefined, comp)
        loadRunDevices()
    }
}

async function scan(){const r=await(await fetch('/api/devices')).json();D=r;S.clear();const e=document.getElementById('dv');e.innerHTML=D.length?D.map(d=>`<label class="d" data-s="${d.serial}"><input type="checkbox" class="dev-ck" value="${d.serial}" onchange="tg2(this)">${d.serial}_${d.model}</label>`).join(''):'<span class="no" style="color:#ff5252">No devices detected</span>';uc()}
function tg2(cb){const s=cb.value;if(cb.checked){S.add(s);cb.parentElement.classList.add('on')}else{S.delete(s);cb.parentElement.classList.remove('on')}uc()}
function ckAll(){document.querySelectorAll('.dev-ck').forEach(c=>{c.checked=true;c.parentElement.classList.add('on');S.add(c.value)});uc()}
function unAll(){document.querySelectorAll('.dev-ck').forEach(c=>{c.checked=false;c.parentElement.classList.remove('on')});S.clear();uc()}
function uc(){document.getElementById('ct').textContent=S.size+'/'+D.length+' devices'}
async function go(){if(!S.size)return alert('Please select at least one device');const r=await fetch('/api/run',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({devices:[...S]})});const d=await r.json();if(d.err)return alert(d.err);document.getElementById('rb').disabled=true;badge('run');document.getElementById('pg').style.width='15%';poll(0)}
function badge(s){const b=document.getElementById('bd');b.className='badge '+(s==='run'?'b-run':s==='done'?'b-done':'b-idle');b.textContent=s==='run'?'Running':s==='done'?'Done':'Idle'}
async function poll(n){const d=await(await fetch('/api/status')).json();document.getElementById('lg').textContent=d.log||'Running...';n++;document.getElementById('pg').style.width=Math.min(15+n*7,95)+'%';if(d.status==='running')setTimeout(()=>poll(n),1500);else{document.getElementById('pg').style.width='100%';badge('done');document.getElementById('rb').disabled=false;rpt()}}
async function rpt(){const r=await(await fetch('/api/reports')).json();const t=document.getElementById('tb');if(!r.length){t.innerHTML='<tr><td colspan="4" class="no">No reports yet</td></tr>';return}t.innerHTML=r.map(f=>{const m=f.name.match(/\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2}_(.+?)_\s*result/);return`<tr><td>${f.name}</td><td>${m?m[1]:'—'}</td><td>${f.time}</td><td><a href="/report/${f.name}" target="_blank">View Report</a></td></tr>`}).join('')}

async function loadRunDevices(){
    const sel = document.getElementById('runSerial')
    if(!sel){return}
    const old = sel.value
    try{
        const r = await fetch('/api/devices')
        const devs = await r.json()
        const opts = ['<option value="">Auto-select first connected device</option>']
        devs.forEach(d=>opts.push(`<option value="${d.serial}">${d.serial}_${d.model}</option>`))
        sel.innerHTML = opts.join('')
        if(old && devs.some(d=>d.serial===old)){sel.value = old}
    }catch(e){
        sel.innerHTML = '<option value="">Failed to load devices</option>'
    }
}

function setRunLog(text){
    const logEl = document.getElementById('runCaseLog')
    if(logEl){logEl.textContent = text || ''}
}

async function runSelectedCase(){
    const statusEl = document.getElementById('runCaseStatus')
    const btn = document.getElementById('runCaseBtn')
    const serialEl = document.getElementById('runSerial')
    if(!currentCaseFile){
        alert('Please select a script first')
        return
    }
    const serial = serialEl ? (serialEl.value || '') : ''
    const component = currentCaseComponent || currentComponent || getSelectedComponent()
    btn.disabled = true
    statusEl.textContent = 'Running...'
    setRunLog(`[Start] Running ${currentCaseFile} ${serial?`on ${serial}`:'on first connected device'}...`)
    try{
        const r = await fetch('/api/run-case', {
            method:'POST',
            headers:{'Content-Type':'application/json'},
            body: JSON.stringify({file: currentCaseFile, component, serial})
        })
        const d = await r.json()
        if(d.err){throw new Error(d.err)}
        statusEl.textContent = `${d.status} (${d.serial || 'N/A'})`
        setRunLog((d.output || '[No output]') + `\n\n[Result] ${d.status}`)
    }catch(e){
        statusEl.textContent = 'Run failed'
        setRunLog(`[Error] ${e.message || 'Unknown error'}`)
    }finally{
        btn.disabled = false
    }
}

async function parseCsv(){
    const fileInput = document.getElementById('csvFile')
    if(!fileInput.files.length){
        alert('Please select a CSV file first')
        return
    }
    const file = fileInput.files[0]
    const formData = new FormData()
    formData.append('file', file)
    try{
        const r = await fetch('/api/parse-csv', {method:'POST', body:formData})
        const d = await r.json()
        if(d.err){
            alert('CSV parse error: ' + d.err)
            return
        }
        if(!d.ok){
            alert('Failed to parse CSV')
            return
        }
        document.getElementById('caseName').value = d.case_name
        const lines = d.rows.map((row, idx) => {
            const step = (row.step || '').trim()
            const expected = (row.expected || '').trim()
            return expected ? `${idx+1}. ${step} -verify: ${expected}` : `${idx+1}. ${step}`
        })
        document.getElementById('stepsText').value = lines.join('\n')
        alert(`✓ CSV loaded successfully: ${d.rows.length} steps imported`)
    }catch(e){
        alert('Error uploading CSV: ' + e.message)
    }
}

function addStepRow(step='', expected=''){
    const box = document.getElementById('stepRows')
    const row = document.createElement('div')
    row.className = 'step-grid step-row'
    row.setAttribute('draggable', 'true')
    row.innerHTML = `
      <div class="step-no">Step ?</div>
            <input class="ipt step-input" placeholder="Example: Launch camera and capture a picture" value="${step.replace(/"/g,'&quot;')}">
            <input class="ipt expected-input" placeholder="Example: Verify camera works normally" value="${expected.replace(/"/g,'&quot;')}">
      <div class="step-ops">
                <button class="small-btn drag-btn" title="Drag to reorder">Drag</button>
        <button class="small-btn" onclick="deleteStepRow(this)">Delete</button>
      </div>
    `
    bindStepRowDnD(row)
    box.appendChild(row)
    updateStepNumbers()
}

function bindStepRowDnD(row){
    row.addEventListener('dragstart', ()=>{
        draggedStepRow = row
        row.classList.add('dragging')
    })
    row.addEventListener('dragover', (e)=>{
        e.preventDefault()
        if(draggedStepRow && draggedStepRow !== row){
            row.classList.add('drag-over')
        }
    })
    row.addEventListener('dragleave', ()=>row.classList.remove('drag-over'))
    row.addEventListener('drop', (e)=>{
        e.preventDefault()
        row.classList.remove('drag-over')
        if(!draggedStepRow || draggedStepRow === row){return}
        const box = document.getElementById('stepRows')
        const rows = [...box.querySelectorAll('.step-row')]
        const from = rows.indexOf(draggedStepRow)
        const to = rows.indexOf(row)
        if(from < to){
            box.insertBefore(draggedStepRow, row.nextSibling)
        }else{
            box.insertBefore(draggedStepRow, row)
        }
        updateStepNumbers()
    })
    row.addEventListener('dragend', ()=>{
        row.classList.remove('dragging')
        document.querySelectorAll('#stepRows .step-row').forEach(r=>r.classList.remove('drag-over'))
        draggedStepRow = null
    })
}

function deleteStepRow(btn){
    const row = btn.closest('.step-row')
    if(row){row.remove()}
    updateStepNumbers()
}

function updateStepNumbers(){
    document.querySelectorAll('#stepRows .step-row').forEach((row, idx)=>{
        const el = row.querySelector('.step-no')
        if(el){el.textContent = `Step ${idx+1}`}
    })
}

function getStepPairs(){
    const rows = document.querySelectorAll('#stepRows .step-row')
    const pairs = []
    rows.forEach(r=>{
      const step = (r.querySelector('.step-input')?.value || '').trim()
      const expected = (r.querySelector('.expected-input')?.value || '').trim()
      if(step){pairs.push({step, expected})}
    })
    return pairs
}

async function genCase(overwrite){
    const caseName = document.getElementById('caseName').value
    const component = getSelectedComponent()
    currentComponent = component
    setScriptListTitle(component)
    const stepsText = (document.getElementById('stepsText')?.value || '').trim()
    const out = document.getElementById('genResult')
    const thinkingEl = document.getElementById('genThinkingLog')
    if(!stepsText){
        out.textContent = 'Failed: Please input at least one test step'
        if(thinkingEl){thinkingEl.textContent = 'Please input at least one test step.'}
        return
    }

    if(caseGenPollTimer){
        clearTimeout(caseGenPollTimer)
        caseGenPollTimer = null
    }

    out.textContent = '🤔 Copilot is thinking...'
    if(thinkingEl){
        thinkingEl.textContent = '⏳ Starting generation task...'
    }

    try{
        const res = await fetch('/api/case-generator/start', {
            method:'POST',
            headers:{'Content-Type':'application/json'},
            body: JSON.stringify({caseName, component, stepsText, overwrite})
        })
        const data = await res.json()
        if(data.err){throw new Error(data.err)}
        if(!data.jobId){throw new Error('Missing jobId from server')}

        const poll = async () => {
            try{
                const sr = await fetch(`/api/case-generator/status?jobId=${encodeURIComponent(data.jobId)}`)
                const sd = await sr.json()
                if(sd.err){throw new Error(sd.err)}

                if(thinkingEl){
                    thinkingEl.textContent = sd.log || '⏳ Waiting for generation logs...'
                    thinkingEl.scrollTop = thinkingEl.scrollHeight
                }

                if(sd.status === 'running'){
                    out.textContent = '🤔 Copilot is thinking...'
                    caseGenPollTimer = setTimeout(poll, 700)
                    return
                }

                if(sd.status === 'done'){
                    if(sd.component){
                        currentComponent = sd.component
                        const compIpt = document.getElementById('componentName')
                        if(compIpt){compIpt.value = sd.component}
                        setScriptListTitle(sd.component)
                    }
                    out.textContent = `✓ Generated (Copilot AI): ${sd.path}`
                    await loadScriptList(sd.file, currentComponent)
                    return
                }

                out.textContent = `✗ Failed: ${sd.err || 'Unknown error'}`
            }catch(pe){
                out.textContent = `✗ Failed: ${pe.message || 'Unknown poll error'}`
            }
        }

        await poll()
    }catch(e){
        out.textContent = `✗ Failed: ${e.message || 'Unknown error'}`
        if(thinkingEl){thinkingEl.textContent = e.message || 'Unknown error'}
    }
}

function escHtml(s){return (s||'').replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]))}
async function loadScriptList(selectName, componentParam){
    const box=document.getElementById('scriptList')
    const component = normalizeComponentName(componentParam || currentComponent || getSelectedComponent())
    currentComponent = component
    setScriptListTitle(component)
    try{
        const r=await fetch(`/api/case-scripts?component=${encodeURIComponent(component)}`)
        const d=await r.json()
        if(d.component){
            currentComponent = d.component
            const compIpt = document.getElementById('componentName')
            if(compIpt){compIpt.value = d.component}
            setScriptListTitle(d.component)
        }
        const items=d.items||[]
        if(!items.length){box.innerHTML='<div class="script-list-inner"><div class="no">No generated scripts yet</div></div>'; currentCaseFile=''; currentCaseComponent=currentComponent; return}
        box.innerHTML=`<div class="script-list-inner">${items.map(it=>`<div class="file-item ${selectName===it.name?'on':''}" data-f="${it.name}" onclick="viewScript('${it.name}','${currentComponent}')"><span class="file-name">${it.name}</span><span class="file-time">${it.mtime}</span></div>`).join('')}</div>`
        const target = selectName || items[0].name
        await viewScript(target, currentComponent)
    }catch(e){
        box.innerHTML=`<div class="script-list-inner"><div class="no" style="color:#ff7b7b">${escHtml(e.message||'Load failed')}</div></div>`
    }
}

async function viewScript(name, componentParam){
    const component = normalizeComponentName(componentParam || currentComponent || getSelectedComponent())
    try{
        const r=await fetch(`/api/case-script-content?component=${encodeURIComponent(component)}&file=${encodeURIComponent(name)}`)
        const d=await r.json()
        if(d.err){throw new Error(d.err)}
        currentCaseFile = name
        currentCaseComponent = d.component || component
        document.getElementById('codeTitle').textContent=`${d.path}`
        document.getElementById('codeView').textContent=d.content||''
        document.querySelectorAll('.file-item').forEach(el=>el.classList.toggle('on', el.getAttribute('data-f')===name))
    }catch(e){
        document.getElementById('codeTitle').textContent='Preview failed'
        document.getElementById('codeView').textContent=e.message||'Unknown error'
    }
}

const _componentInput = document.getElementById('componentName')
if(_componentInput && !_componentInput.value.trim()){
    _componentInput.value = 'smoking'
}
currentComponent = getSelectedComponent()
setScriptListTitle(currentComponent)
loadScriptList(undefined, currentComponent)
loadRunDevices()
rpt()
</script>
</body>
</html>'''

if __name__ == '__main__':
    print('Web console started: http://localhost:5000')
    app.run(host='0.0.0.0', port=5000, debug=False)
