# -*- coding:utf-8 -*-
import unittest
import os
import sys
import time
import ast
import re
import json
import importlib.util
import threading
import subprocess
import urllib.request
import types
import sysconfig
from common.sendEmail import SendEmial


def _install_distutils_sysconfig_compat():
    if 'distutils.sysconfig' in sys.modules:
        return

    distutils_module = sys.modules.get('distutils')
    if distutils_module is None:
        distutils_module = types.ModuleType('distutils')
        sys.modules['distutils'] = distutils_module

    sysconfig_module = types.ModuleType('distutils.sysconfig')

    def get_python_lib(plat_specific=False, standard_lib=False, prefix=None):
        base_prefix = prefix or sys.prefix
        scheme = 'nt' if os.name == 'nt' else 'posix_prefix'
        key = 'platlib' if plat_specific else 'purelib'
        if standard_lib:
            key = 'platstdlib' if plat_specific else 'stdlib'
        return sysconfig.get_path(key, scheme=scheme, vars={'base': base_prefix, 'platbase': base_prefix})

    sysconfig_module.get_python_lib = get_python_lib
    distutils_module.sysconfig = sysconfig_module
    sys.modules['distutils.sysconfig'] = sysconfig_module


_install_distutils_sysconfig_compat()
from BeautifulReport import BeautifulReport

_BASE_DIR = os.path.dirname(os.path.realpath(__file__))

# 进度条状态管理（线程安全）
class _ProgressBar:
    def __init__(self):
        self.lock = threading.Lock()
        self.completed = 0
        self.total = 0
        self.start_time = None
        self.status = 'running'  # running / completed / failed
    
    def set_total(self, total):
        with self.lock:
            self.total = total
            self.start_time = time.time()
    
    def increment(self, status='OK'):
        """增加已完成计数，status: OK/FAIL/ERROR/SKIP"""
        with self.lock:
            self.completed += 1
            if status in ('FAIL', 'ERROR'):
                self.status = 'has_failures'
    
    def mark_failed(self):
        """标记测试执行失败（脚本崩溃等）"""
        with self.lock:
            self.status = 'crashed'
    
    def get_progress(self):
        """返回 (completed, total, percentage, status)"""
        with self.lock:
            pct = 0
            if self.total > 0:
                pct = int((self.completed / self.total) * 100)
            return self.completed, self.total, pct, self.status
    
    def display_bar(self):
        """在控制台显示实时进度条"""
        completed, total, pct, status = self.get_progress()
        
        # 颜色代码
        if status == 'crashed':
            color = '\033[91m'  # 红色 - 崩溃/异常
        elif status == 'has_failures':
            color = '\033[93m'  # 黄色 - 有失败但执行完成
        else:
            color = '\033[92m'  # 绿色 - 执行中/成功
        
        reset = '\033[0m'
        
        # 进度条宽度
        bar_width = 30
        filled = int(bar_width * pct / 100)
        bar = '█' * filled + '░' * (bar_width - filled)
        
        # 同一行显示进度条
        msg = f"\r{color}[{bar}]{reset} {pct:3d}% ({completed}/{total})"
        print(msg, end='', flush=True)

_progress_bar = _ProgressBar()


class VerboseBeautifulReport(BeautifulReport):
    """Emit per-case status lines to stdout while generating BeautifulReport."""

    def stopTest(self, test):
        # BeautifulReport formats spendTime with '{:.3}', which renders long
        # durations in scientific notation (e.g. 135s -> '1.35e+02 s').
        # Override to always show a plain fixed-point number of seconds.
        self.end_time = '{:.2f} s'.format(time.time() - self.start_time)
        self.result_list.append(self.get_all_result_info_tuple(test))
        self.complete_output()

    def addSuccess(self, test):
        super().addSuccess(test)
        self.status = 'Pass'
        sys.__stdout__.write('{} ... PASS\n'.format(test.id()))
        sys.__stdout__.flush()

    def addFailure(self, test, err):
        super().addFailure(test, err)
        self.status = 'Fail'
        sys.__stdout__.write('{} ... FAIL\n'.format(test.id()))
        sys.__stdout__.flush()

    def addError(self, test, err):
        super().addError(test, err)
        self.status = 'Error'
        sys.__stdout__.write('{} ... ERROR\n'.format(test.id()))
        sys.__stdout__.flush()

    def addSkip(self, test, reason):
        super().addSkip(test, reason)
        self.status = 'Skip'

# 自定义 TestLoader 以支持 L0_ 前缀的测试方法
class CustomTestLoader(unittest.TestLoader):
    def getTestCaseNames(self, testCaseClass):
        """Return a sorted sequence of method names found matching testMethodPrefix or L0_ prefix"""
        def isTestMethod(attrname, testCaseClass=testCaseClass, prefix=self.testMethodPrefix):
            if attrname.startswith(prefix) or attrname.startswith('L0_'):
                return callable(getattr(testCaseClass, attrname))
            return False
        testFnNames = [name for name in dir(testCaseClass) if isTestMethod(name)]
        testFnNames.sort()
        return testFnNames

# 获取路径
curpath = _BASE_DIR
# curpath = os.getcwd()
# Discover all managed tests under the case root, not only case/demo.
casepath = os.path.join(curpath, "case")

if not os.path.exists(casepath):
    print("test cases should be placed in the 'case' directory")

    os.mkdir(casepath)

reportpath = os.path.join(curpath, "report")
if not os.path.exists(reportpath):
    print("测试报告需放到‘report’文件目录下")

    os.mkdir(reportpath)


def _ensure_local_report_assets(report_dir):
    """Download report CSS/JS once so generated reports can render without external CDN access."""
    assets_dir = os.path.join(report_dir, "_assets")
    os.makedirs(assets_dir, exist_ok=True)

    # url -> local relative path in report html
    assets = {
        "https://cdn.bootcss.com/bootstrap/3.3.5/css/bootstrap.min.css": "_assets/bootstrap.min.css",
        "https://cdn.bootcss.com/font-awesome/4.4.0/css/font-awesome.min.css": "_assets/font-awesome.min.css",
        "https://cdn.bootcss.com/animate.css/3.5.2/animate.min.css": "_assets/animate.min.css",
        "https://cdn.bootcss.com/chosen/1.8.2/chosen.css": "_assets/chosen.css",
        "https://cdn.bootcss.com/jquery/2.1.4/jquery.min.js": "_assets/jquery.min.js",
        "https://cdn.bootcss.com/bootstrap/3.3.5/js/bootstrap.min.js": "_assets/bootstrap.min.js",
        "https://cdn.bootcss.com/echarts/3.8.5/echarts.min.js": "_assets/echarts.min.js",
        "https://cdn.bootcss.com/chosen/1.8.2/chosen.jquery.js": "_assets/chosen.jquery.js",
    }

    mirrors = {
        "https://cdn.bootcss.com/bootstrap/3.3.5/css/bootstrap.min.css": [
            "https://cdn.jsdelivr.net/npm/bootstrap@3.3.5/dist/css/bootstrap.min.css",
        ],
        "https://cdn.bootcss.com/font-awesome/4.4.0/css/font-awesome.min.css": [
            "https://cdn.jsdelivr.net/npm/font-awesome@4.4.0/css/font-awesome.min.css",
        ],
        "https://cdn.bootcss.com/animate.css/3.5.2/animate.min.css": [
            "https://cdn.jsdelivr.net/npm/animate.css@3.5.2/animate.min.css",
        ],
        "https://cdn.bootcss.com/chosen/1.8.2/chosen.css": [
            "https://cdn.jsdelivr.net/npm/chosen-js@1.8.7/chosen.min.css",
        ],
        "https://cdn.bootcss.com/jquery/2.1.4/jquery.min.js": [
            "https://cdn.jsdelivr.net/npm/jquery@2.1.4/dist/jquery.min.js",
        ],
        "https://cdn.bootcss.com/bootstrap/3.3.5/js/bootstrap.min.js": [
            "https://cdn.jsdelivr.net/npm/bootstrap@3.3.5/dist/js/bootstrap.min.js",
        ],
        "https://cdn.bootcss.com/echarts/3.8.5/echarts.min.js": [
            "https://cdn.jsdelivr.net/npm/echarts@3.8.5/dist/echarts.min.js",
        ],
        "https://cdn.bootcss.com/chosen/1.8.2/chosen.jquery.js": [
            "https://cdn.jsdelivr.net/npm/chosen-js@1.8.7/chosen.jquery.min.js",
        ],
    }

    for cdn_url, rel_target in assets.items():
        target = os.path.join(report_dir, rel_target)
        if os.path.exists(target) and os.path.getsize(target) > 0:
            continue
        tried = [cdn_url] + mirrors.get(cdn_url, [])
        ok = False
        for url in tried:
            try:
                urllib.request.urlretrieve(url, target)
                ok = True
                break
            except Exception:
                continue
        if not ok:
            print(f"[WARN] 下载报告资源失败: {rel_target}")

    return assets


def _rewrite_report_asset_links(report_file, assets_map):
    """Replace external CDN links in BeautifulReport html with local asset paths."""
    if not os.path.exists(report_file):
        return
    try:
        with open(report_file, 'r', encoding='utf-8', errors='ignore') as f:
            html = f.read()
    except Exception as e:
        print(f"[WARN] 读取报告文件失败: {e}")
        return

    new_html = html
    for cdn_url, rel_path in assets_map.items():
        new_html = new_html.replace(cdn_url, rel_path.replace('\\', '/'))

    if new_html != html:
        try:
            with open(report_file, 'w', encoding='utf-8', newline='\n') as f:
                f.write(new_html)
        except Exception as e:
            print(f"[WARN] 写入本地化报告失败: {e}")


_REPORT_UI_TRANSLATIONS = {
    '测试用例运行结果': 'Test Case Results',
    '自动化测试报告': 'Automated Test Report',
    '存在报错的用例，请优先查看！': 'There are failed or errored cases. Please review them first.',
    '测试报告': 'Test Report',
    '报告汇总': 'Report Summary',
    '用例名称:': 'Test Name:',
    '用例总数:': 'Total Cases:',
    '用例通过:': 'Passed:',
    '用例失败:': 'Failed:',
    '用例跳过:': 'Skipped:',
    '开始时间:': 'Start Time:',
    '运行时间:': 'Run Time:',
    '详细数据': 'Detailed Results',
    '测试类:': 'Test Class:',
    '结果:': 'Result:',
    '用例数:': 'Cases:',
    '成功:': 'Pass:',
    '失败:': 'Fail:',
    '跳过:': 'Skip:',
    '测试方法': 'Test Method',
    '用例描述': 'Description',
    '运行时长': 'Duration',
    '编号': 'No.',
    '测试类': 'Test Class',
    '结果': 'Result',
    '操作': 'Action',
    '"status": "成功"': '"status": "Pass"',
    '"status": "失败"': '"status": "Fail"',
    '"status": "错误"': '"status": "Error"',
    '"status": "跳过"': '"status": "Skip"',
    "'成功'": "'Pass'",
    "'失败'": "'Fail'",
    "'错误'": "'Error'",
    "'跳过'": "'Skip'",
    '成功</span>': 'Pass</span>',
    '失败</span>': 'Fail</span>',
    '错误</span>': 'Error</span>',
    '跳过</span>': 'Skip</span>',
    '展开': 'Expand',
    '收缩': 'Collapse',
    '运行结果': 'Result',
}


def _localize_report_ui(report_file):
    """Translate BeautifulReport's fixed UI strings without changing case data or logs."""
    if not os.path.exists(report_file):
        return
    try:
        with open(report_file, 'r', encoding='utf-8', errors='ignore') as f:
            html = f.read()
    except Exception as e:
        print(f"[WARN] Failed to read report file (English UI): {e}")
        return

    localized_html = html
    for source, target in _REPORT_UI_TRANSLATIONS.items():
        localized_html = localized_html.replace(source, target)

    if localized_html != html:
        try:
            with open(report_file, 'w', encoding='utf-8', newline='\n') as f:
                f.write(localized_html)
        except Exception as e:
            print(f"[WARN] Failed to write English report UI: {e}")


_SCREENSHOT_VIEWER_CSS = """\
<style id="_ss_style">
#_ssModal{position:fixed;top:0;left:0;width:100%;height:100%;background:rgba(0,0,0,0.9);z-index:9999;overflow-y:auto;padding:24px;display:none}
#_ssModal .ss-inner{max-width:1300px;margin:0 auto}
#_ssModal .ss-hdr{display:flex;justify-content:space-between;align-items:center;margin-bottom:16px}
#_ssModal .ss-hdr h3{color:#fff;font-size:16px;font-weight:700;margin:0}
#_ssModal .ss-close{background:#ef4444;color:#fff;border:none;padding:6px 18px;border-radius:4px;cursor:pointer;font-size:14px;font-weight:600}
#_ssModal .ss-close:hover{background:#dc2626}
#_ssModal .ss-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(320px,1fr));gap:14px}
#_ssModal .ss-card{background:#1e293b;border-radius:8px;overflow:hidden;border:1px solid rgba(255,255,255,0.1)}
#_ssModal .ss-card img{width:100%;display:block;cursor:zoom-in}
#_ssModal .ss-card .ss-label{padding:6px 10px;color:#94a3b8;font-size:11px;font-family:monospace;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
#_ssModal .ss-empty{color:#94a3b8;padding:40px;text-align:center;font-size:14px}
</style>"""

_SCREENSHOT_VIEWER_HTML = """\
<div id="_ssModal">
    <div class="ss-inner">
        <div class="ss-hdr">
            <h3>&#128247; Screenshot Preview (<span id="_ssCount">0</span>)</h3>
            <button class="ss-close" onclick="document.getElementById('_ssModal').style.display='none'">&#10005; Close</button>
        </div>
        <div class="ss-grid" id="_ssGrid"></div>
    </div>
</div>"""

_SCREENSHOT_VIEWER_JS = r"""
<script id="_ss_script">
function _ssHasImgs(n){
    var logs=n["log"]||[];
    for(var s=0;s<logs.length;s++){if(typeof logs[s]==="string"&&/\bimg[\\\/][^\s]+\.png/i.test(logs[s]))return true;}
    return false;
}
function _ssBtn(n,i){
    if(!_ssHasImgs(n))return "";
    return "<button type='button' onclick=\"_showSS("+i+")\" class='btn btn-info btn-xs' style='margin-bottom:0px;margin-left:4px'>View Screenshots</button>";
}
function _showSS(idx){
    var logs=resultData["testResult"][idx]["log"]||[];
    var imgs=[];
    var seen={};
    for(var j=0;j<logs.length;j++){
        var text=typeof logs[j]==="string"?logs[j]:"";
        var matches=text.matchAll(/\b(img[\\\/][^\s"']+\.png)/ig);
        for(var match of matches){
            var path=match[1].replace(/\\/g,"/");
            if(!seen[path]){seen[path]=true;imgs.push(path);}
        }
    }
    var grid=document.getElementById("_ssGrid");
    grid.innerHTML="";
    document.getElementById("_ssCount").textContent=imgs.length;
    if(!imgs.length){
        var empty=document.createElement("div");
        empty.className="ss-empty";
        empty.textContent="No screenshots for this test case";
        grid.appendChild(empty);
    } else {
        imgs.forEach(function(p){
            var label=p.split("/").pop().replace(/_\d{8}_\d{6}\.png$/i,"").replace(/_/g," ");
            var card=document.createElement("div");card.className="ss-card";
            var img=document.createElement("img");
            img.src="/"+p;img.title=label;
            img.addEventListener("click",function(){window.open(this.src);});
            img.addEventListener("error",function(){this.parentNode.style.display="none";});
            var lbl=document.createElement("div");lbl.className="ss-label";lbl.textContent=label;
            card.appendChild(img);card.appendChild(lbl);
            grid.appendChild(card);
        });
    }
    var modal=document.getElementById("_ssModal");
    modal.style.display="block";
    modal.scrollTop=0;
}
document.addEventListener("keydown",function(e){if(e.key==="Escape"){var m=document.getElementById("_ssModal");if(m)m.style.display="none";}});
</script>"""

_OLD_ROW_MARKER_CN = "class='btn btn-primary btn-xs' style='margin-bottom: 0px'>展开</button></td></tr>\""
_OLD_ROW_MARKER_EN = "class='btn btn-primary btn-xs' style='margin-bottom: 0px'>Expand</button></td></tr>\""
_NEW_ROW_MARKER_CN = "class='btn btn-primary btn-xs' style='margin-bottom: 0px'>展开</button>\" + _ssBtn(n, i) + _aiBtn(n, i) + _defectBtn(n, i) + \"</td></tr>\""
_NEW_ROW_MARKER_EN = "class='btn btn-primary btn-xs' style='margin-bottom: 0px'>Expand</button>\" + _ssBtn(n, i) + _aiBtn(n, i) + _defectBtn(n, i) + \"</td></tr>\""

# ── AI Analysis button injection ───────────────────────────────────────────────
_AI_ANALYSIS_CSS = """\
<style id="_ai_style">
.btn-ai{display:inline-block;padding:2px 10px;margin-left:4px;border-radius:4px;
background:linear-gradient(135deg,#6d28d9,#7c3aed);color:#fff;font-size:12px;
font-weight:700;border:none;cursor:pointer;vertical-align:middle;line-height:1.8}
.btn-ai:hover{opacity:.85}
.btn-ai:disabled{opacity:.45;cursor:default}
#_aiModal{display:none;position:fixed;inset:0;background:rgba(15,23,42,.75);
z-index:10000;align-items:center;justify-content:center;backdrop-filter:blur(4px)}
#_aiModal.open{display:flex}
#_aiModalBox{background:#fff;border-radius:14px;width:820px;max-width:95vw;
max-height:86vh;display:flex;flex-direction:column;box-shadow:0 24px 64px rgba(0,0,0,.22);overflow:hidden}
#_aiModalHdr{padding:16px 22px;background:linear-gradient(135deg,#4c1d95,#6d28d9);
color:#fff;display:flex;align-items:center;gap:10px;flex-shrink:0}
#_aiModalHdr h4{flex:1;margin:0;font-size:15px;font-weight:800}
#_aiCloseBtn{background:rgba(255,255,255,.18);border:none;color:#fff;width:30px;
height:30px;border-radius:7px;cursor:pointer;font-size:17px;line-height:30px;text-align:center}
#_aiCloseBtn:hover{background:rgba(255,255,255,.32)}
#_aiMeta{padding:10px 22px;background:#f5f3ff;border-bottom:1px solid #ede9fe;
font-size:12px;color:#6d28d9;font-weight:600;flex-shrink:0}
#_aiBody{padding:18px 22px;overflow-y:auto;flex:1;font-size:13.5px;line-height:1.75;color:#1e293b}
#_aiFtr{padding:12px 22px;border-top:1px solid #f1f5f9;display:flex;gap:8px;
justify-content:flex-end;flex-shrink:0;background:#f8fafc}
#_aiCopyBtn{padding:7px 16px;border-radius:7px;border:1px solid #e2e8f0;
background:#fff;font-size:13px;font-weight:600;cursor:pointer;color:#475569}
#_aiCloseBtn2{padding:7px 16px;border-radius:7px;border:none;
background:linear-gradient(135deg,#6d28d9,#7c3aed);color:#fff;font-size:13px;font-weight:700;cursor:pointer}
.ai-h3{font-size:13px;font-weight:800;color:#4c1d95;margin:14px 0 6px;
padding:5px 10px;background:#f5f3ff;border-left:4px solid #7c3aed;border-radius:0 5px 5px 0}
.ai-h3:first-child{margin-top:0}
.ai-pre{background:#0d1117;color:#c9d1d9;padding:10px 14px;border-radius:7px;
font:12px/1.6 monospace;overflow-x:auto;margin:6px 0;white-space:pre-wrap;word-break:break-all}
.ai-code{background:#f1f5f9;padding:1px 5px;border-radius:3px;
font:12px/1 monospace;color:#0f172a}
#_aiErr{background:#fef2f2;border:1px solid #fecaca;border-radius:7px;
padding:12px 16px;color:#991b1b;font-size:13px}
#_aiLoading{text-align:center;padding:36px 20px;color:#8b5cf6}
</style>"""

_AI_ANALYSIS_HTML = """\
<div id="_aiModal" onclick="if(event.target===this)_aiClose()">
    <div id="_aiModalBox">
        <div id="_aiModalHdr">
            <span style="font-size:20px">&#129302;</span>
            <h4>AI Failure Analysis</h4>
            <button id="_aiCloseBtn" onclick="_aiClose()">&#10005;</button>
        </div>
        <div id="_aiMeta"></div>
        <div id="_aiBody"><div id="_aiLoading">&#9881;&#65039; AI is analyzing...</div></div>
        <div id="_aiFtr">
            <button id="_aiCopyBtn" style="display:none" onclick="_aiCopy()">&#128203; Copy Report</button>
            <button id="_aiCloseBtn2" onclick="_aiClose()">Close</button>
        </div>
    </div>
</div>"""

_AI_ANALYSIS_JS = """\
<script id="_ai_script">
var _aiText='';
function _aiBtn(n,i){
    if(['失败','错误','Fail','Failure','Error'].indexOf(n['status'])===-1)return '';
    var cls=encodeURIComponent(n['className']||'');
    var mth=encodeURIComponent(n['methodName']||'');
    var idx=i;
    return "<button type='button' class='btn-ai' onclick=\\"_aiOpen('"+cls+"','"+mth+"',"+idx+")\\" title='AI Failure Analysis'>&#129302; AI Analysis</button>";
}
function _aiOpen(cls,mth,idx){
    var n=(resultData['testResult']||[])[idx]||{};
    var logs=n['log']||[];
    var errLines=[],outLines=[];
    var inErr=false;
    for(var j=0;j<logs.length;j++){
        var ln=typeof logs[j]==='string'?logs[j]:'';
        if(/Traceback|AssertionError|Error:|Exception:/i.test(ln))inErr=true;
        if(inErr)errLines.push(ln); else outLines.push(ln);
    }
    var errInfo=errLines.join('\\n')||logs.join('\\n');
    var stdOut=outLines.join('\\n');
    var clsDec=decodeURIComponent(cls);
    var mthDec=decodeURIComponent(mth);
    document.getElementById('_aiMeta').textContent=
        '🔖 Class: '+clsDec+'   ⚙️ Method: '+mthDec+'   📊 Status: '+n['status'];
    document.getElementById('_aiBody').innerHTML=
        '<div id="_aiLoading">⚙️ AI is analyzing, please wait...</div>';
    document.getElementById('_aiCopyBtn').style.display='none';
    _aiText='';
    var modal=document.getElementById('_aiModal');
    modal.className='open';
    document.body.style.overflow='hidden';
    fetch(window.location.origin+'/api/ai_fail_analysis',{
        method:'POST',
        headers:{'Content-Type':'application/json'},
        body:JSON.stringify({
            testId:clsDec+'.'+mthDec,
            testClass:clsDec,
            method:mthDec,
            errorInfo:errInfo,
            stdout:stdOut
        })
    }).then(function(r){return r.json();}).then(function(d){
        if(d.err){
            document.getElementById('_aiBody').innerHTML=
                '<div id="_aiErr">&#10060; Analysis failed: '+_aiEsc(d.err)+'<br><small>Please make sure web_console.py is running (python web_console.py)</small></div>';
            return;
        }
        _aiText=d.analysis||'';
        var fileTag=d.caseFile?'<div style="margin-bottom:10px;font-size:12px;color:#64748b">&#128196; Source: <span class="ai-code">'+_aiEsc(d.caseFile)+'</span></div>':'';
        document.getElementById('_aiBody').innerHTML=fileTag+_aiMd(_aiText);
        document.getElementById('_aiCopyBtn').style.display='';
    }).catch(function(e){
        document.getElementById('_aiBody').innerHTML=
            '<div id="_aiErr">&#10060; Request error: '+_aiEsc(String(e))+'</div>';
    });
}
function _aiClose(){
    document.getElementById('_aiModal').className='';
    document.body.style.overflow='';
}
function _aiCopy(){
    if(!_aiText)return;
    navigator.clipboard.writeText(_aiText).then(function(){
        var b=document.getElementById('_aiCopyBtn');
        b.textContent='✓ Copied';
        setTimeout(function(){b.textContent='📋 Copy Report';},2000);
    });
}
function _aiEsc(s){
    return String(s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}
function _aiMd(text){
    var lines=(text||'').split('\\n'),out=[],inCode=false,codeBuf=[];
    for(var i=0;i<lines.length;i++){
        var l=lines[i];
        if(!inCode&&/^```/.test(l)){inCode=true;codeBuf=[];continue;}
        if(inCode){if(/^```/.test(l)){inCode=false;out.push('<pre class="ai-pre">'+_aiEsc(codeBuf.join('\\n'))+'</pre>');codeBuf=[];}else codeBuf.push(l);continue;}
        if(/^#{1,4}\\s/.test(l)){out.push('<div class="ai-h3">'+_aiInl(l.replace(/^#+\\s+/,''))+'</div>');continue;}
        if(/^[\\s]*[-*]\\s/.test(l)){out.push('<li>'+_aiInl(l.replace(/^[\\s]*[-*]\\s+/,''))+'</li>');continue;}
        if(!l.trim()){out.push('<br>');continue;}
        out.push('<p style="margin:4px 0">'+_aiInl(l)+'</p>');
    }
    return out.join('');
}
function _aiInl(s){
    return _aiEsc(s)
        .replace(/\\*\\*([^*]+)\\*\\*/g,'<strong>$1</strong>')
        .replace(/`([^`]+)`/g,'<span class="ai-code">$1</span>');
}
document.addEventListener('keydown',function(e){if(e.key==='Escape')_aiClose();});
</script>"""


# ── Create Defect button injection ───────────────────────────────
_DEFECT_CSS = """\
<style id="_defect_style">
.btn-defect{display:inline-block;padding:2px 10px;margin-left:4px;border-radius:4px;
background:linear-gradient(135deg,#d97706,#f59e0b);color:#fff;font-size:12px;
font-weight:700;border:none;cursor:pointer;vertical-align:middle;line-height:1.8}
.btn-defect:hover{opacity:.85}
.btn-defect:disabled{opacity:.45;cursor:default}
</style>"""

_DEFECT_JS = """\
<script id="_defect_script">
function _defectBtn(n,i){
    if(['失败','错误','Fail','Failure','Error'].indexOf(n['status'])===-1)return '';
    var cls=encodeURIComponent(n['className']||'');
    var mth=encodeURIComponent(n['methodName']||'');
    return "<button type='button' class='btn-defect' onclick=\\"_createDefect(this,'"+cls+"','"+mth+"',"+i+")\\" title='Create Jira Defect'>&#128030; Create Defect</button>";
}
function _createDefect(btn,cls,mth,idx){
    var n=(resultData['testResult']||[])[idx]||{};
    var clsDec=decodeURIComponent(cls), mthDec=decodeURIComponent(mth);
    var logs=n['log']||[];
    var err=(logs.join('\\n')||'').slice(-4000);
    var summary='[Defect] '+clsDec+'.'+mthDec+' '+(n['status']||'FAIL');
    var desc='Class: '+clsDec+'\\nMethod: '+mthDec+'\\nStatus: '+(n['status']||'')+'\\nReport: '+window.location.href+'\\n\\nLog:\\n'+err;
    if(!confirm('Create a defect in Jira project SZMSUS?\\n\\n'+summary))return;
    btn.disabled=true;var o=btn.innerHTML;btn.innerHTML='Creating...';
    fetch(window.location.origin+'/api/jira/create-defect',{
        method:'POST',headers:{'Content-Type':'application/json'},
        body:JSON.stringify({profileName:clsDec,summary:summary,description:desc,result:n['status']||'',reportFile:(window.location.pathname.split('/').pop()||'')})
    }).then(function(r){return r.json();}).then(function(d){
        if(d&&d.code===200&&d.key&&d.url){
            var link=document.createElement('a');
            link.className='btn-defect';
            link.href=d.url;
            link.target='_blank';
            link.rel='noopener noreferrer';
            link.title='Open Jira defect '+d.key;
            link.textContent='✔ '+d.key;
            link.style.background='#16a34a';
            btn.parentNode.replaceChild(link,btn);
        }
        else{alert('Create failed: '+((d&&d.msg)||'unknown error'));btn.innerHTML=o;btn.disabled=false;}
    }).catch(function(e){alert('Create failed: cannot connect to service');btn.innerHTML=o;btn.disabled=false;});
}
</script>"""


_REPORT_ACTIONS_MARKER = 'id="_report_actions_script"'
_REPORT_ACTIONS_BUTTONS = """\
    <div id="_reportActions" style="padding:0 15px 12px;text-align:right">
        <button type="button" class="btn-ai" onclick="_aiReportOpen()">&#129302; AI Overall Analysis</button>
        <button type="button" class="btn-defect" style="margin-left:6px" onclick="_sendReportEmail(this)">Send Email</button>
    </div>"""

_REPORT_ACTIONS_JS = r"""
<script id="_report_actions_script">
function _reportFailedCases(){
    var failedCases=[],results=resultData['testResult']||[];
    for(var i=0;i<results.length;i++){
        var n=results[i]||{};
        if(['失败','错误','Fail','Failure','Error'].indexOf(n['status'])===-1)continue;
        var logs=n['log']||[],errorLines=[],outputLines=[],foundError=false;
        for(var j=0;j<logs.length;j++){
            var line=typeof logs[j]==='string'?logs[j]:'';
            if(/Traceback|AssertionError|Error:|Exception:/i.test(line))foundError=true;
            if(foundError)errorLines.push(line);else outputLines.push(line);
        }
        failedCases.push({reportCaseNumber:i+1,testId:(n['className']||'')+'.'+(n['methodName']||''),testClass:n['className']||'',method:n['methodName']||'',status:n['status']||'',errorInfo:errorLines.join('\n')||logs.join('\n'),stdout:outputLines.join('\n')});
    }
    return failedCases;
}
function _reportJson(response){
    return response.text().then(function(text){
        var data;try{data=JSON.parse(text);}catch(error){throw new Error('Service returned a non-JSON response (HTTP '+response.status+').');}
        if(!response.ok||data.err)throw new Error(data.err||'Request failed (HTTP '+response.status+').');
        return data;
    });
}
function _requestReportAiAnalysis(){
    var failedCases=_reportFailedCases();
    if(!failedCases.length)return Promise.reject(new Error('No failed or errored cases are available for analysis.'));
    return fetch(window.location.origin+'/api/ai_report_analysis',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({failedCases:failedCases})})
        .then(_reportJson).then(function(data){return data.analysis||'';});
}
function _aiReportOpen(){
    document.getElementById('_aiMeta').textContent='Report failed/error cases: '+_reportFailedCases().length;
    document.getElementById('_aiBody').innerHTML='<div id="_aiLoading">AI is analyzing the report...</div>';
    document.getElementById('_aiCopyBtn').style.display='none';
    _aiText='';document.getElementById('_aiModal').className='open';document.body.style.overflow='hidden';
    _requestReportAiAnalysis().then(function(analysis){
        _aiText=analysis;document.getElementById('_aiBody').innerHTML=_aiMd(_aiText);document.getElementById('_aiCopyBtn').style.display='';
    }).catch(function(error){document.getElementById('_aiBody').innerHTML='<div id="_aiErr">&#10060; '+_aiEsc(String(error.message||error))+'</div>';});
}
function _pickEmailRecipients(){
    return fetch(window.location.origin+'/api/report/email-contacts').then(_reportJson).catch(function(){return {contacts:[]};}).then(function(data){
        return new Promise(function(resolve){
            var contacts=data.contacts||[],groups=[],byName={};
            contacts.forEach(function(c){if(!byName[c.name]){byName[c.name]={name:c.name,members:[]};groups.push(byName[c.name]);}byName[c.name].members.push(c.email);});
            var mask=document.createElement('div');
            mask.style.cssText='position:fixed;inset:0;background:rgba(15,23,42,.55);z-index:99999;display:flex;align-items:center;justify-content:center;font-family:Segoe UI,Arial,sans-serif';
            var box=document.createElement('div');
            box.style.cssText='background:#fff;color:#1e293b;border-radius:12px;padding:22px 24px;width:440px;max-width:92%;font-size:14px;box-shadow:0 20px 50px rgba(0,0,0,.35)';
            var btnBase='border:0;border-radius:6px;padding:8px 20px;font-size:14px;cursor:pointer;';
            var html='<div style="font-size:17px;font-weight:600;margin-bottom:14px">&#9993; Select recipients</div><div style="max-height:280px;overflow:auto">';
            if(!groups.length)html+='<div style="color:#94a3b8;padding:8px">No contacts configured in allconfig.config [email_contacts]</div>';
            groups.forEach(function(g,gi){
                html+='<div style="border:1px solid #e2e8f0;border-radius:8px;margin-bottom:8px;overflow:hidden">'+
                '<div class="_emHead" data-g="'+gi+'" style="display:flex;align-items:center;gap:8px;padding:10px 12px;background:#f8fafc;cursor:pointer;user-select:none">'+
                '<span class="_emArrow" style="display:inline-block;width:12px;transition:transform .15s;color:#64748b">&#9656;</span>'+
                '<input type="checkbox" class="_emAll" data-g="'+gi+'" style="width:16px;height:16px;cursor:pointer">'+
                '<span style="font-weight:600;flex:1">'+_aiEsc(g.name)+'</span>'+
                '<span class="_emCount" style="font-size:12px;color:#64748b;background:#e2e8f0;border-radius:10px;padding:1px 8px"></span></div>'+
                '<div class="_emBody" style="display:none;padding:4px 12px 8px 40px">';
                g.members.forEach(function(m,mi){html+='<label style="display:flex;align-items:center;gap:8px;padding:5px 0;cursor:pointer"><input type="checkbox" class="_emMem" data-g="'+gi+'" data-m="'+mi+'" style="width:15px;height:15px"><span>'+_aiEsc(m)+'</span></label>';});
                html+='</div></div>';
            });
            html+='</div><div style="margin:12px 0 6px;color:#64748b;font-size:13px">Other addresses (optional, separated by , or ;)</div><input type="text" id="_emOther" style="width:100%;box-sizing:border-box;padding:8px 10px;border:1px solid #cbd5e1;border-radius:6px;font-size:14px"><div style="text-align:right;margin-top:18px"><button type="button" id="_emCancel" style="'+btnBase+'background:#e2e8f0;color:#334155;margin-right:8px">Cancel</button><button type="button" id="_emOk" style="'+btnBase+'background:#2563eb;color:#fff">Send</button></div>';
            box.innerHTML=html;mask.appendChild(box);document.body.appendChild(mask);
            function close(v){document.body.removeChild(mask);resolve(v);}
            function refresh(gi){
                var mems=box.querySelectorAll('._emMem[data-g="'+gi+'"]'),n=0;
                mems.forEach(function(x){if(x.checked)n++;});
                var all=box.querySelector('._emAll[data-g="'+gi+'"]');
                all.checked=n===mems.length;all.indeterminate=n>0&&n<mems.length;
                box.querySelector('._emHead[data-g="'+gi+'"] ._emCount').textContent=n+'/'+mems.length;
            }
            groups.forEach(function(g,gi){refresh(gi);});
            box.querySelectorAll('._emHead').forEach(function(h){h.onclick=function(e){
                if(e.target.tagName==='INPUT')return;
                var body=h.nextSibling,open=body.style.display==='none';
                body.style.display=open?'block':'none';h.querySelector('._emArrow').style.transform=open?'rotate(90deg)':'';
            };});
            box.querySelectorAll('._emAll').forEach(function(cb){cb.onchange=function(){
                var gi=cb.getAttribute('data-g');
                box.querySelectorAll('._emMem[data-g="'+gi+'"]').forEach(function(x){x.checked=cb.checked;});refresh(gi);
            };});
            box.querySelectorAll('._emMem').forEach(function(cb){cb.onchange=function(){refresh(cb.getAttribute('data-g'));};});
            box.querySelector('#_emCancel').onclick=function(){close(null);};
            box.querySelector('#_emOk').onclick=function(){
                var list=[];
                box.querySelectorAll('._emMem:checked').forEach(function(cb){list.push(groups[+cb.getAttribute('data-g')].members[+cb.getAttribute('data-m')]);});
                box.querySelector('#_emOther').value.split(/[;,\s]+/).forEach(function(a){if(a)list.push(a);});
                list=list.filter(function(a,i){return list.indexOf(a)===i;});
                if(!list.length){alert('Please select at least one recipient.');return;}
                close(list);
            };
        });
    });
}
function _sendReportEmail(btn){
    _pickEmailRecipients().then(function(recipients){if(recipients)_doSendReportEmail(btn,recipients);});
}
function _doSendReportEmail(btn,recipients){
    var originalText=btn.textContent;btn.disabled=true;btn.textContent=_aiText?'Sending...':'Analyzing...';
    var noFailedCases=_reportFailedCases().length===0;
    var analysisPromise=_aiText?Promise.resolve(_aiText):(noFailedCases?Promise.resolve(''):_requestReportAiAnalysis());
    analysisPromise.then(function(analysis){
        if(!analysis&&!noFailedCases)throw new Error('AI analysis returned no result.');
        _aiText=analysis;btn.textContent='Sending...';
        return fetch(window.location.origin+'/api/report/send-email',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({recipients:recipients,reportTitle:document.title,reportUrl:window.location.href,summary:{total:resultData['testAll']||0,passed:resultData['testPass']||0,failed:resultData['testFail']||0,errored:0,skipped:resultData['testSkip']||0},aiAnalysis:_aiText,noFailedCases:noFailedCases})});
    }).then(_reportJson).then(function(data){alert((noFailedCases?'Report':'Report and AI analysis')+' sent to: '+data.recipients.join(', '));})
      .catch(function(error){alert('Email sending failed: '+String(error.message||error));})
      .finally(function(){btn.disabled=false;btn.textContent=originalText;});
}
</script>"""


def _fix_report_table_overflow(report_file):
    """Wrap the Details table in a horizontally-scrollable container.

    Long, unbroken Description text can otherwise force the whole table wider
    than the viewport, pushing the Result/Action columns off-screen and making
    the entire page scroll horizontally instead of just the table.
    """
    if not os.path.exists(report_file):
        return
    try:
        with open(report_file, 'r', encoding='utf-8', errors='ignore') as f:
            html = f.read()
    except Exception as e:
        print(f"[WARN] Failed to read report file (table overflow fix): {e}")
        return

    marker = (
        '                    <table class="table table-bordered">\n'
        '                        <thead>\n'
        '                        <tr>\n'
        '                            <th>No.</th><th>Test Class</th><th>Test Method</th><th>Description</th><th>Duration</th><th>Result</th><th>Action</th>\n'
        '                        </tr>\n'
        '                        </thead>\n'
        '                        <tbody id="detailBody">\n'
        '                        </tbody>\n'
        '                    </table>'
    )
    if marker not in html:
        return  # Template changed or already patched

    wrapped = (
        '                    <div class="autonexus-table-scroll" style="width:100%;overflow-x:hidden;">\n'
        + marker + '\n'
        '                    </div>'
    )
    html = html.replace(marker, wrapped, 1)
    html = html.replace(
        '</head>',
        '<style>'
        # Fill the empty strip on the right: let the content wrapper span the full
        # page width instead of leaving Bootstrap/theme gutter + boxed max-width gaps.
        'html,body{overflow-x:hidden}'
        '.wrapper-content{padding:15px !important}'
        '.wrapper-content>.row{margin-left:0 !important;margin-right:0 !important}'
        '.wrapper-content>.row>[class^="col-"],.wrapper-content>.row>[class*=" col-"]{padding-left:0 !important;padding-right:0 !important}'
        '.autonexus-table-scroll{overflow-x:hidden !important}'
        '.autonexus-table-scroll table{table-layout:fixed;width:100%}'
        '.autonexus-table-scroll td,.autonexus-table-scroll th{overflow-wrap:break-word}'
        # Let action buttons wrap inside their cell instead of forcing the table wider.
        '.autonexus-table-scroll td .btn,.autonexus-table-scroll td button,.autonexus-table-scroll td a{white-space:normal !important;word-break:break-word;max-width:100%;box-sizing:border-box}'
        '.autonexus-table-scroll td:nth-child(1),.autonexus-table-scroll th:nth-child(1){width:4%}'
        '.autonexus-table-scroll td:nth-child(2),.autonexus-table-scroll th:nth-child(2){width:11%}'
        '.autonexus-table-scroll td:nth-child(3),.autonexus-table-scroll th:nth-child(3){width:11%}'
        '.autonexus-table-scroll td:nth-child(4),.autonexus-table-scroll th:nth-child(4){width:44%;word-break:break-word;white-space:pre-line}'
        '.autonexus-table-scroll td:nth-child(5),.autonexus-table-scroll th:nth-child(5){width:7%}'
        '.autonexus-table-scroll td:nth-child(6),.autonexus-table-scroll th:nth-child(6){width:7%}'
        '.autonexus-table-scroll td:nth-child(7),.autonexus-table-scroll th:nth-child(7){width:16%}</style>\n</head>',
        1,
    )

    try:
        with open(report_file, 'w', encoding='utf-8', newline='\n') as f:
            f.write(html)
    except Exception as e:
        print(f"[WARN] Failed to fix report table overflow: {e}")


def _inject_screenshot_viewer(report_file):
    """Inject report tools, aggregate AI analysis, and email actions into BeautifulReport HTML."""
    if not os.path.exists(report_file):
        return
    try:
        with open(report_file, 'r', encoding='utf-8', errors='ignore') as f:
            html = f.read()
    except Exception as e:
        print(f"[WARN] Failed to read report file (injection): {e}")
        return

    row_tools_injected = False
    if _OLD_ROW_MARKER_EN in html:
        html = html.replace(_OLD_ROW_MARKER_EN, _NEW_ROW_MARKER_EN, 1)
        row_tools_injected = True
    elif _OLD_ROW_MARKER_CN in html:
        html = html.replace(_OLD_ROW_MARKER_CN, _NEW_ROW_MARKER_CN, 1)
        row_tools_injected = True

    if row_tools_injected:
        html = html.replace('</head>', _SCREENSHOT_VIEWER_CSS + '\n' + _AI_ANALYSIS_CSS + '\n' + _DEFECT_CSS + '\n</head>', 1)
        html = html.replace(
            '</body>',
            _SCREENSHOT_VIEWER_HTML + '\n' + _SCREENSHOT_VIEWER_JS + '\n' +
            _AI_ANALYSIS_HTML + '\n' + _AI_ANALYSIS_JS + '\n' + _DEFECT_JS + '\n</body>',
            1,
        )

    alert_marker = '    <div id="alert-tips" class="alert alert-danger alert-dismissible" role="alert">'
    if _REPORT_ACTIONS_MARKER not in html and alert_marker in html:
        html = html.replace(alert_marker, _REPORT_ACTIONS_BUTTONS + '\n' + alert_marker, 1)
        html = html.replace('</body>', _REPORT_ACTIONS_JS + '\n</body>', 1)

    try:
        with open(report_file, 'w', encoding='utf-8', newline='\n') as f:
            f.write(html)
    except Exception as e:
        print(f"[WARN] Failed to inject report helpers: {e}")


def _flatten_suite(suite):
    for item in suite:
        if isinstance(item, unittest.TestSuite):
            for inner in _flatten_suite(item):
                yield inner
        else:
            yield item


class _ProgressWrappedCase:
    def __init__(self, test, index, total):
        self._test = test
        self._index = index
        self._total = total

    def __getattr__(self, name):
        return getattr(self._test, name)

    # Expose the real test class so TestSuite runs setUpClass/tearDownClass.
    @property
    def __class__(self):
        return self._test.__class__

    def __str__(self):
        return str(self._test)

    def id(self):
        try:
            return self._test.id()
        except Exception:
            return str(self._test)

    def countTestCases(self):
        return 1

    @staticmethod
    def _count_result_items(value):
        """Support both unittest list-style fields and int counters (e.g. BeautifulReport skipped)."""
        if value is None:
            return 0
        if isinstance(value, int):
            return value
        try:
            return len(value)
        except Exception:
            try:
                return int(value)
            except Exception:
                return 0

    def run(self, result=None):
        case_id = self.id()
        print(f"\n[AUTONEXUS_PROGRESS] START {self._index}/{self._total} {case_id}", flush=True)

        uses_beautiful_report = hasattr(result, 'failure_count')
        before_fail = self._count_result_items(
            getattr(result, 'failure_count', 0) if uses_beautiful_report else getattr(result, 'failures', [])
        )
        before_err = self._count_result_items(getattr(result, 'errors', []))
        before_skip = self._count_result_items(getattr(result, 'skipped', []))

        # Delegate execution to the original test object.
        self._test(result)

        after_fail = self._count_result_items(
            getattr(result, 'failure_count', 0) if uses_beautiful_report else getattr(result, 'failures', [])
        )
        after_err = self._count_result_items(getattr(result, 'errors', []))
        after_skip = self._count_result_items(getattr(result, 'skipped', []))

        outcome = 'OK'
        if not uses_beautiful_report and after_err > before_err:
            outcome = 'ERROR'
        elif after_fail > before_fail:
            outcome = 'FAIL'
        elif after_skip > before_skip:
            outcome = 'SKIP'

        print(f"\n[AUTONEXUS_PROGRESS] END {self._index}/{self._total} {outcome} {case_id}", flush=True)
        
        # 更新进度条
        _progress_bar.increment(outcome)
        _progress_bar.display_bar()

    __call__ = run


def _wrap_suite_with_progress(suite):
    tests = list(_flatten_suite(suite))
    total = len(tests)
    wrapped = unittest.TestSuite()
    for i, test in enumerate(tests, 1):
        wrapped.addTest(_ProgressWrappedCase(test, i, total))
    print(f"[AUTONEXUS_PROGRESS] TOTAL {total}", flush=True)
    
    # 初始化进度条
    _progress_bar.set_total(total)
    _progress_bar.display_bar()  # 显示初始进度条
    print()  # 换行以便显示用例输出
    
    return wrapped


def add_case(case_path=casepath, rule="test*.py"):
    '''加载所有的测试用例'''
    loader = CustomTestLoader()
    discover = loader.discover(case_path, pattern=rule, top_level_dir=None)

    return discover


def _read_env_list(name):
    raw = os.environ.get(name, '').strip()
    if not raw:
        return []
    try:
        data = json.loads(raw)
        return data if isinstance(data, list) else []
    except Exception:
        return []


def _scan_cases(case_path=casepath):
    cases = []
    idx = 1
    if not os.path.exists(case_path):
        return cases

    for root, dirs, files in os.walk(case_path):
        dirs[:] = [d for d in dirs if d not in {'__pycache__', '.git', '.idea', '.vscode'}]
        for fname in sorted(files):
            if not fname.startswith('test') or not fname.endswith('.py'):
                continue
            fpath = os.path.join(root, fname)
            rel_file = os.path.relpath(fpath, case_path).replace('\\', '/')
            try:
                with open(fpath, 'r', encoding='utf-8', errors='ignore') as f:
                    source = f.read()
                tree = ast.parse(source)
                for node in ast.walk(tree):
                    if isinstance(node, ast.ClassDef):
                        cls = node.name
                        for item in node.body:
                            if isinstance(item, ast.FunctionDef) and (item.name.startswith('test') or item.name.startswith('L0_')):
                                cases.append({
                                    'id': idx,
                                    'file': rel_file,
                                    'className': cls,
                                    'name': item.name,
                                })
                                idx += 1
            except Exception:
                continue
    return cases


def _build_selected_suite(case_path=casepath):
    selected_ids_raw = _read_env_list('AUTONEXUS_CASE_IDS')
    selected_list_raw = _read_env_list('AUTONEXUS_CASE_LIST')

    selected_ids = []
    for item in selected_ids_raw:
        try:
            selected_ids.append(int(item))
        except Exception:
            pass

    selected_pairs = set()
    selected_files = set()
    for item in selected_list_raw:
        if not isinstance(item, str):
            continue
        s = item.strip()
        if not s:
            continue
        if s.endswith('.py') or '/' in s or '\\' in s:
            selected_files.add(s.replace('\\', '/'))
            continue
        if '.' not in s:
            continue
        cls, method = s.split('.', 1)
        cls = cls.strip()
        method = method.strip()
        if cls and method:
            selected_pairs.add((cls, method))

    if not selected_ids and not selected_pairs and not selected_files:
        return None

    scanned = _scan_cases(case_path)
    by_id = {c['id']: c for c in scanned}

    picked = []
    if selected_ids:
        for cid in selected_ids:
            c = by_id.get(cid)
            if c:
                picked.append(c)

    if not picked and selected_files:
        for c in scanned:
            if c['file'] in selected_files:
                picked.append(c)

    if not picked and selected_pairs:
        for c in scanned:
            if (c['className'], c['name']) in selected_pairs:
                picked.append(c)

    if not picked:
        print('未匹配到所选用例，终止执行（不回退全量）')
        return unittest.TestSuite()

    # Deduplicate by exact location + method.
    seen = set()
    dedup = []
    for c in picked:
        key = (c['file'], c['className'], c['name'])
        if key in seen:
            continue
        seen.add(key)
        dedup.append(c)

    suite = unittest.TestSuite()
    added = 0
    for i, c in enumerate(dedup):
        abs_path = os.path.join(case_path, c['file'])
        if not os.path.exists(abs_path):
            continue
        module_name = f"autonexus_case_{i}_{abs(hash(abs_path))}"
        try:
            spec = importlib.util.spec_from_file_location(module_name, abs_path)
            if not spec or not spec.loader:
                continue
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            cls = getattr(mod, c['className'], None)
            if cls is None:
                continue
            if not hasattr(cls, c['name']):
                continue
            suite.addTest(cls(c['name']))
            added += 1
        except Exception as e:
            print(f"加载用例失败: {c['file']}::{c['className']}.{c['name']} -> {e}")

    if added == 0:
        print('所选用例加载失败，终止执行（不回退全量）')
        return unittest.TestSuite()

    print(f'按选择执行用例数: {added}')
    return suite

def _get_connected_devices():
    """Get list of connected Android devices"""
    try:
        result = subprocess.run(
            ['adb', 'devices'],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=10
        )
        devices = []
        for line in result.stdout.strip().splitlines()[1:]:
            parts = line.strip().split()
            if len(parts) >= 2 and parts[1] == 'device':
                devices.append(parts[0])
        return devices
    except Exception as e:
        print(f"Failed to get devices: {e}")
        return []


def _resolve_target_serial(devices):
    """Resolve target device serial from env, fallback to first online device."""
    preferred = (os.environ.get('AUTONEXUS_DEVICE_SN') or os.environ.get('ANDROID_SERIAL') or '').strip()
    if preferred:
        if preferred in devices:
            return preferred
        print(f"[WARN] Preferred device not online: {preferred}. Fallback to first online device.")
    return devices[0] if devices else ''


def _build_report_name(device_serial):
    """Build a device-specific report name to avoid collisions in parallel runs."""
    now = time.strftime("%Y-%m-%d_%H-%M-%S")
    safe_serial = re.sub(r'[^A-Za-z0-9._-]+', '_', str(device_serial or 'device'))
    return f"{now}_{safe_serial}_result.html"

if __name__ == "__main__":
    try:
        # 获取连接的设备
        devices = _get_connected_devices()
        if not devices:
            print("No connected Android devices found!")
            sys.exit(1)
        
        # 使用指定设备（若未指定则回退到第一个在线设备）
        serial = _resolve_target_serial(devices)
        if not serial:
            print("No valid Android device selected!")
            sys.exit(1)
        print(f"[INFO] Using device: {serial}")
        os.environ['ANDROID_SERIAL'] = serial
        
        # 用例集合
        selected_suite = _build_selected_suite()
        if selected_suite is None:
            cases = add_case()
        else:
            # Selected run mode: never fallback to full-suite on load failures.
            if selected_suite.countTestCases() == 0:
                print('[AUTONEXUS_PROGRESS] TOTAL 0', flush=True)
                print('所选用例装载失败，执行已终止（未回退全量）', flush=True)
                sys.exit(2)
            cases = selected_suite
        cases = _wrap_suite_with_progress(cases)

        report_name = _build_report_name(serial)
        # Keep execution semantics unchanged; only switch report backend to BeautifulReport.
        result = VerboseBeautifulReport(cases)
        try:
            result.report(
                filename=report_name,
                description='AutoTest Report',
                report_dir=reportpath,
            )
        except TypeError:
            # Backward compatibility for old BeautifulReport versions.
            result.report(
                filename=report_name,
                description='AutoTest Report',
                log_path=reportpath,
            )
        assets_map = _ensure_local_report_assets(reportpath)
        _rewrite_report_asset_links(os.path.join(reportpath, report_name), assets_map)
        _localize_report_ui(os.path.join(reportpath, report_name))
        _fix_report_table_overflow(os.path.join(reportpath, report_name))
        _inject_screenshot_viewer(os.path.join(reportpath, report_name))
        # 发送邮件报告:网络原因暂不支持
        #     # new_report = SendEmial().new_report("report")
        #     # SendEmial().send_mail(new_report)  # 发送测试报告
        
        # 执行完成后显示最终进度条
        print()
        _progress_bar.display_bar()
        print()
    except Exception as e:
        # 脚本崩溃时标记为失败，显示红色
        _progress_bar.mark_failed()
        _progress_bar.display_bar()
        print(f"\n\n脚本执行失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)